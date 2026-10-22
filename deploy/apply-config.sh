#!/bin/sh
# Anvend en netværksændring fra System › Konfiguration. Køres som ROOT af systemd
# (hypervisionplc-scada-config.service, udløst af .path-enheden når network.request findes) — aldrig direkte af tjenesten.
#
# Kopieres af install.sh til /usr/local/lib/hypervisionplc-scada/ — UDEN FOR programmappen, som en opdatering erstatter.
#
# SIKKERHED: Tjenesten (brugeren 'scada') ejer <data>/config og kan lægge hvad som helst dér, også symlinks. Derfor
#   * læser/skriver root KUN i sin egen mappe $W (root-ejet, 0755) — status, log og arbejdskopien af anmodningen;
#   * anmodningen flyttes (mv, ikke kopi) ind i $W før den læses, og et symlink afvises;
#   * confirm/revert i <data>/config bruges kun som "findes?"-signaler (aldrig læst) og fjernes med rm;
#   * ingen værdi fra anmodningen når et shell: alt valideres her igen (samme regler som backend/app/services/netconfig.py).
#
# LOCKOUT-BESKYTTELSE: ændringen anvendes med --temporary (kun i hukommelsen) og gøres først varig, når brugeren har
# BEKRÆFTET fra den nye adresse. Uden bekræftelse (eller ved Fortryd) genindlæses den gemte profil. Dør scriptet, eller
# genstarter maskinen, mens der ventes, er den varige profil urørt → den gamle opsætning vender tilbage af sig selv;
# ExecStopPost kører desuden `--recover`.
#
# Til test kan kommandoer og mapper overstyres: NMCLI, HOSTNAMECTL, DATA, STATE, TIMEOUT_CMD.
# Efter en bekræftet ændring skrives <state>/watchdog.conf til DHCP-vagten (deploy/net-watchdog.sh).
set -u
set -f   # ingen glob-udvidelse af uquotede variabler
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

NMCLI=${NMCLI:-nmcli}
HOSTNAMECTL=${HOSTNAMECTL:-hostnamectl}
TIMEOUT_CMD=${TIMEOUT_CMD:-timeout}
HOSTNAME_CMD=${HOSTNAME_CMD:-hostname}
DATA=${DATA:-/var/lib/hypervisionplc-scada}
W=${STATE:-/var/lib/hypervisionplc-scada-net}
C=$DATA/config
REQ=$C/network.request
CONFIRM=$C/network.confirm
REVERT=$C/network.revert
STATUS=$W/status.json
LOG=$W/network.log
WORKREQ=$W/request.work
NM_T=40   # sekunder pr. nmcli-kald (hænger NetworkManager, skal vi stadig nå at gendanne)
IFUP=${IFUP:-ifup}
IFDOWN=${IFDOWN:-ifdown}
IFFILE=${IFFILE:-/etc/network/interfaces}
RESOLV=${RESOLV:-/etc/resolv.conf}
HOSTS=${HOSTS:-/etc/hosts}
CAPS=$W/capabilities     # skrives af install.sh: backend=nm|ifupdown og dhcp=0|1
# ifup/ifdown starter DHCP-klienten som en baggrundsproces. Kørt direkte herfra ville den ligge i denne tjenestes cgroup/sandkasse og
# blive dræbt, når tjenesten slutter (adressen forsvinder så, når leasen udløber). Derfor køres de i en transient enhed med
# KillMode=process. Tom IFRUN (test) eller uden systemd-run = direkte kørsel.
if [ "${IFRUN+set}" != set ]; then
    if command -v systemd-run >/dev/null 2>&1; then IFRUN="systemd-run --quiet --wait --collect --pipe -p KillMode=process"; else IFRUN=""; fi
fi
NEWFILE=$W/interfaces.new

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }
nm() { $TIMEOUT_CMD "$NM_T" $NMCLI "$@"; }

BY=ukendt
# Kun tegn der er sikre i JSON (beskederne er vores egne konstanter)
status() {
    # $1 = tilstand, $2 = besked, $3 = frist (epoch, valgfri)
    printf '{"state":"%s","message":"%s","deadline":%s,"by":"%s","ts":%s}\n' "$1" "$2" "${3:-0}" "$BY" "$(date +%s)" > "$STATUS.tmp"
    chmod 0644 "$STATUS.tmp"
    mv "$STATUS.tmp" "$STATUS"
}

# Tilbage til den GEMTE profil (kasserer den midlertidige ændring)
reload_saved() {
    nm connection reload >> "$LOG" 2>&1
    [ -n "${UUID:-}" ] && nm connection up uuid "$UUID" >> "$LOG" 2>&1
}

mkdir -p "$W" || exit 1
chmod 0755 "$W"

BACKEND=$(sed -n 's/^backend=//p' "$CAPS" 2>/dev/null | head -n 1)
case "$BACKEND" in nm|ifupdown) ;; *) BACKEND=nm ;; esac     # ældre installationer har kun NetworkManager
DHCP_OK=$(sed -n 's/^dhcp=//p' "$CAPS" 2>/dev/null | head -n 1)

# Værtsnavn (begge backends): sættes først EFTER bekræftelse. /etc/hosts' 127.0.1.1-linje følger med.
apply_hostname() {
    [ -n "$HOSTNAME_NEW" ] || return 0
    old=$($HOSTNAME_CMD 2>/dev/null || true)
    $TIMEOUT_CMD "$NM_T" $HOSTNAMECTL set-hostname "$HOSTNAME_NEW" >> "$LOG" 2>&1 || { log "Værtsnavn kunne ikke sættes"; return 0; }
    # Det gamle navn kan stamme fra systemet (ikke fra os): kun sikre tegn, og ingen sed-regex (ingen injektion). Temp-filen i $W,
    # ikke i /etc (ProtectSystem=strict).
    if printf '%s' "$old" | grep -Eq '^[A-Za-z0-9.-]+$' && [ "$old" != "$HOSTNAME_NEW" ] && [ -f "$HOSTS" ] && [ ! -L "$HOSTS" ]; then
        awk -v o="$old" -v n="$HOSTNAME_NEW" '$1 == "127.0.1.1" { for (i = 2; i <= NF; i++) if ($i == o) $i = n } { print }' "$HOSTS" > "$W/hosts.tmp" \
            && cat "$W/hosts.tmp" > "$HOSTS" || log "/etc/hosts kunne ikke opdateres"
        rm -f "$W/hosts.tmp"
    fi
}

# ifupdown: stanzaen for netkortet efter tilstand
stanza() {
    printf 'auto %s\n' "$IFACE"
    case "$MODE" in
        static)
            printf 'iface %s inet static\n    address %s/%s\n' "$IFACE" "$IP" "$PREFIX"
            if [ -n "$GATEWAY" ]; then printf '    gateway %s\n' "$GATEWAY"; fi
            if [ -n "$DNS" ]; then printf '    dns-nameservers %s\n' "$(printf '%s' "$DNS" | tr ',' ' ')"; fi
            ;;
        dhcp_static)
            printf 'iface %s inet dhcp\n    post-up ip addr add %s/%s dev %s || true\n    pre-down ip addr del %s/%s dev %s || true\n' \
                "$IFACE" "$IP" "$PREFIX" "$IFACE" "$IP" "$PREFIX" "$IFACE"
            ;;
        *)  # dhcp og dhcp_fallback (reserve-IP'en lægges på af net-watchdog.sh)
            printf 'iface %s inet dhcp\n' "$IFACE" ;;
    esac
    return 0
}

# ifupdown: kan filen omskrives sikkert? Afvises: CRLF, indrykkede nøgleord (iface/auto/source …) og ukendte linjer uden indrykning.
check_if_file() {
    if [ "$(tr -d '\r' < "$IFFILE" | wc -c)" != "$(wc -c < "$IFFILE")" ]; then return 1; fi      # CR i filen (CRLF)
    awk '
        /^[ \t]*$/ { next }
        /^[ \t]*#/ { next }
        /^[ \t]+(iface|auto|allow-[a-z-]+|mapping|source|source-directory|rename|no-auto-down|no-scripts)[ \t]/ { bad = 1 }
        /^[^ \t]/ { if ($1 !~ /^(auto|allow-[a-z-]+|iface|mapping|source|source-directory|rename|no-auto-down|no-scripts)$/) bad = 1 }
        END { exit bad ? 1 : 0 }
    ' "$IFFILE"
}
iface_exists() {
    awk -v n="$IFACE" '/^[^ \t]/ && $1 == "iface" && $2 == n && $3 == "inet" { f = 1 } END { exit f ? 0 : 1 }' "$IFFILE"
}

# ifupdown: filen uden netkortets gamle stanzaer (andre netkort, kommentarer og source-linjer bevares) + den nye stanza
build_new_file() {
    DIR=$(dirname "$IFFILE") awk -v IFN="$IFACE" '
        /^[ \t]*$/ { print; next }
        /^[ \t]*#/ { print; next }
        /^[^ \t]/ {
            skip = 0
            n = split($0, w, /[ \t]+/)
            kw = w[1]
            if (kw == "auto" || kw ~ /^allow-/) {
                out = kw; cnt = 0
                for (i = 2; i <= n; i++) if (w[i] != IFN) { out = out " " w[i]; cnt++ }
                if (cnt > 0) print out
                next
            }
            if (kw == "iface" && w[2] == IFN && w[3] == "inet") { skip = 1; next }
            if ((kw == "source" || kw == "source-directory") && n >= 2 && w[2] !~ /^\//) { print kw " " ENVIRON["DIR"] "/" w[2]; next }   # filen læses fra en anden mappe
            print; next
        }
        { if (!skip) print }
    ' "$IFFILE" > "$NEWFILE.tmp" || return 1
    { printf '\n# Sat af HypervisionPLC SCADA (System > Konfiguration)\n'; stanza; } >> "$NEWFILE.tmp"
    mv "$NEWFILE.tmp" "$NEWFILE"
}

restore_if() {
    log "Gendanner den gamle opsætning (ifupdown)"
    $IFRUN $TIMEOUT_CMD 60 $IFDOWN --force -i "$NEWFILE" "$IFACE" >> "$LOG" 2>&1
    $IFRUN $TIMEOUT_CMD 90 $IFUP -i "$IFFILE" "$IFACE" >> "$LOG" 2>&1
}

# ifupdown: gør ændringen varig — sikkerhedskopi (de 3 nyeste beholdes), atomisk udskiftning, DNS i en almindelig resolv.conf
finalize_if() {
    bak="$IFFILE.hypervision-bak-$(date +%Y%m%d%H%M%S)"
    cp -p "$IFFILE" "$bak" || return 1
    cp -p "$IFFILE" "$IFFILE.hv-new" && cat "$NEWFILE" > "$IFFILE.hv-new" && mv "$IFFILE.hv-new" "$IFFILE" || return 1
    rm -f "$W/ifupdown.state"     # ændringen er varig: --recover må ikke længere rulle den tilbage
    find "$(dirname "$IFFILE")" -maxdepth 1 -name "$(basename "$IFFILE").hypervision-bak-*" 2>/dev/null | sort -r | tail -n +4 | while read -r f; do rm -f "$f"; done
    if [ -n "$DNS" ] && [ -f "$RESOLV" ] && [ ! -L "$RESOLV" ]; then
        { grep -v '^nameserver' "$RESOLV" 2>/dev/null; for d in $(printf '%s' "$DNS" | tr ',' ' '); do printf 'nameserver %s\n' "$d"; done; } > "$W/resolv.tmp" \
            && cat "$W/resolv.tmp" > "$RESOLV" || log "DNS kunne ikke skrives"
        rm -f "$W/resolv.tmp"
    elif [ -n "$DNS" ]; then
        log "DNS er ikke ændret: $RESOLV styres af systemet (symlink)"
    fi
    return 0
}

# ---------------------------------------------------------------- --recover (ExecStopPost): scriptet døde midt i en ændring
if [ "${1:-}" = "--recover" ]; then
    state=$(sed -n 's/.*"state": *"\([a-z_]*\)".*/\1/p' "$STATUS" 2>/dev/null | head -n 1)
    case "$state" in
        applying|waiting_confirm)
            log "Gendanner efter afbrudt ændring (tilstand $state)"
            if [ "$BACKEND" = ifupdown ]; then
                IFACE=$(sed -n 's/^iface_changed=//p' "$W/ifupdown.state" 2>/dev/null | head -n 1)
                if printf '%s' "$IFACE" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9_.-]{0,14}$' && [ -f "$NEWFILE" ]; then restore_if; fi
            else
                nm connection reload >> "$LOG" 2>&1
                for u in $(nm -g UUID connection show --active 2>/dev/null); do nm connection up uuid "$u" >> "$LOG" 2>&1; done
            fi
            status reverted "Afbrudt — den gamle opsætning er gendannet" ;;
    esac
    exit 0
fi

[ -e "$REQ" ] || [ -L "$REQ" ] || exit 0

# Tag anmodningen ind i root-mappen med ÉT atomisk mv (et symlink flyttes som symlink og afvises nedenfor)
rm -f "$WORKREQ"
mv "$REQ" "$WORKREQ" 2>/dev/null || exit 0
: > "$LOG"
status applying "Læser anmodningen"   # straks, så en gammel status ikke bliver stående mens der valideres
fail() { log "FEJL: $1"; status failed "$1"; rm -f "$WORKREQ"; exit 1; }
[ -L "$WORKREQ" ] && fail "Anmodningen er ikke en almindelig fil"
[ -f "$WORKREQ" ] || fail "Anmodningen mangler"

field() { sed -n "s/^$1=//p" "$WORKREQ" | head -n 1; }
BY=$(field BY | tr -cd 'A-Za-z0-9_.@-' | cut -c1-64); BY=${BY:-ukendt}
CONFIRM_S=$(field CONFIRM_S)
FALLBACK_AFTER=$(field FALLBACK_AFTER); IFACE=$(field IFACE); MODE=$(field MODE); IP=$(field IP); PREFIX=$(field PREFIX)
GATEWAY=$(field GATEWAY); DNS=$(field DNS); HOSTNAME_NEW=$(field HOSTNAME)
rm -f "$WORKREQ" "$CONFIRM" "$REVERT"

# ---------------------------------------------------------------- validering
is_ipv4() {
    [ -n "$1" ] || return 1
    printf '%s' "$1" | awk -F. 'NF==4 { for (i=1;i<=4;i++) { if ($i !~ /^[0-9]+$/ || length($i) > 3 || $i+0 > 255) exit 1 } exit 0 } { exit 1 }'
}
printf '%s' "$IFACE" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9_.-]{0,14}$' || fail "Ugyldigt netkort"
case "$MODE" in dhcp|static|dhcp_static|dhcp_fallback) ;; *) fail "Ugyldig tilstand" ;; esac
printf '%s' "$FALLBACK_AFTER" | grep -Eq '^[1-9][0-9]?$' || FALLBACK_AFTER=5
[ "$FALLBACK_AFTER" -le 20 ] || FALLBACK_AFTER=5
# 1–999 uden foranstillet 0 (ellers læser shellen det som oktal), derefter 20–180 s
printf '%s' "$CONFIRM_S" | grep -Eq '^[1-9][0-9]{0,2}$' || CONFIRM_S=90
[ "$CONFIRM_S" -ge 20 ] || CONFIRM_S=20
[ "$CONFIRM_S" -le 180 ] || CONFIRM_S=180
if [ "$MODE" != dhcp ]; then
    is_ipv4 "$IP" || fail "Ugyldig IP-adresse"
    printf '%s' "$PREFIX" | grep -Eq '^[1-9][0-9]?$' || fail "Ugyldigt subnet"
    [ "$PREFIX" -ge 8 ] && [ "$PREFIX" -le 30 ] || fail "Subnet-præfikset skal være mellem 8 og 30"
    if [ -n "$GATEWAY" ]; then is_ipv4 "$GATEWAY" || fail "Ugyldig gateway"; fi
fi
if [ -n "$DNS" ]; then
    for d in $(printf '%s' "$DNS" | tr ',' ' '); do is_ipv4 "$d" || fail "Ugyldig DNS-adresse"; done
fi
if [ -n "$HOSTNAME_NEW" ]; then
    printf '%s' "$HOSTNAME_NEW" | grep -Eq '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$' || fail "Ugyldigt værtsnavn"
fi

# ================================================================ ifupdown (Debian/Ubuntu-servere, ESXi-VM'er)
# Samme sikkerhedsmodel som NetworkManager-delen: ændringen anvendes UDEN at røre /etc/network/interfaces (ifup -i <ny fil>),
# og filen skrives først varigt, når brugeren har bekræftet. Genstart/død undervejs = den gamle fil gælder igen.
if [ "$BACKEND" = ifupdown ]; then
    if [ "$MODE" != static ] && [ "$DHCP_OK" != 1 ]; then
        fail "Ingen understøttet DHCP-klient (ifupdown kræver dhcpcd: apt install dhcpcd-base) — vælg Fast IP, eller installér klienten"
    fi
    { [ -f "$IFFILE" ] && [ ! -L "$IFFILE" ]; } || fail "Netværksfilen findes ikke eller er et symlink"
    check_if_file || fail "Netværksfilen har et format, der ikke kan omskrives sikkert (CRLF, indrykkede nøgleord eller ukendte linjer) — ret den selv"
    iface_exists || fail "Netkortets opsætning står ikke i netværksfilen (fx i interfaces.d) — ændringen er afvist"
    build_new_file || fail "Den nye netværksfil kunne ikke bygges"
    printf 'iface_changed=%s\n' "$IFACE" > "$W/ifupdown.state"
    log "Anmodet af $BY: $MODE ip=$IP/$PREFIX gw=$GATEWAY dns=$DNS host=$HOSTNAME_NEW iface=$IFACE (ifupdown)"

    status applying "Anvender netværksopsætningen"
    $IFRUN $TIMEOUT_CMD 60 $IFDOWN --force -i "$IFFILE" "$IFACE" >> "$LOG" 2>&1 || log "ifdown meldte fejl (fortsætter)"
    if ! $IFRUN $TIMEOUT_CMD 90 $IFUP -i "$NEWFILE" "$IFACE" >> "$LOG" 2>&1; then
        restore_if; status failed "Netkortet kunne ikke komme op med den nye opsætning — den gamle er gendannet"; exit 1
    fi

    DEADLINE=$(( $(date +%s) + CONFIRM_S ))
    status waiting_confirm "Åbn siden på den nye adresse og tryk Bekræft — ellers gendannes den gamle opsætning" "$DEADLINE"
    log "Venter på bekræftelse til $DEADLINE"
    while [ "$(date +%s)" -lt "$DEADLINE" ]; do
        if [ -e "$CONFIRM" ]; then
            rm -f "$CONFIRM" "$REVERT"
            if ! finalize_if; then
                log "Kunne ikke gemme varigt"; restore_if; status failed "Ændringen kunne ikke gemmes varigt — den gamle opsætning er gendannet"; exit 1
            fi
            apply_hostname
            { printf 'BACKEND=ifupdown\nMODE=%s\nIFACE=%s\nUUID=\nIP=%s\nPREFIX=%s\nGATEWAY=%s\nFALLBACK_AFTER=%s\n' \
                "$MODE" "$IFACE" "$IP" "$PREFIX" "$GATEWAY" "$FALLBACK_AFTER"; } > "$W/watchdog.conf.tmp" && mv "$W/watchdog.conf.tmp" "$W/watchdog.conf"
            rm -f "$W/watchdog.state" "$W/ifupdown.state"
            log "Bekræftet og gemt"
            status confirmed "Netværksopsætningen er bekræftet og gemt"
            exit 0
        fi
        if [ -e "$REVERT" ]; then
            rm -f "$REVERT" "$W/ifupdown.state"
            log "Fortrudt"
            restore_if; status reverted "Fortrudt — den gamle opsætning er gendannet"
            exit 0
        fi
        sleep 1
    done
    log "Ingen bekræftelse inden fristen"
    rm -f "$W/ifupdown.state"
    restore_if
    status reverted "Ingen bekræftelse inden for ${CONFIRM_S} sekunder — den gamle opsætning er gendannet"
    exit 0
fi

# ================================================================ NetworkManager
# ---------------------------------------------------------------- profilen på netkortet
CON=$(nm -g GENERAL.CONNECTION device show "$IFACE" 2>>"$LOG") || fail "Netkortet findes ikke, eller NetworkManager svarer ikke"
{ [ -n "$CON" ] && [ "$CON" != "--" ]; } || fail "Netkortet har ingen aktiv NetworkManager-profil"
UUID=$(nm -g connection.uuid connection show "$CON" 2>>"$LOG") || fail "Profilen kunne ikke læses"
printf '%s' "$UUID" | grep -Eq '^[0-9A-Fa-f-]{8,40}$' || fail "Profilens id er ugyldigt"
log "Anmodet af $BY: $MODE ip=$IP/$PREFIX gw=$GATEWAY dns=$DNS host=$HOSTNAME_NEW iface=$IFACE profil=$CON"

# ---------------------------------------------------------------- argumenter til nmcli
case "$MODE" in
    dhcp|dhcp_fallback)
        # dhcp_fallback: profilen er ren DHCP; reserve-IP'en lægges på af net-watchdog.sh efter N kontroller uden svar
        set -- ipv4.method auto ipv4.addresses "" ipv4.gateway "" ipv4.may-fail yes ipv4.dhcp-timeout 2147483647 ;;
    static)
        set -- ipv4.method manual ipv4.addresses "$IP/$PREFIX" ipv4.gateway "$GATEWAY" ipv4.may-fail no ipv4.dhcp-timeout 0 ;;
    dhcp_static)
        # DHCP forsøges uden ende; den faste adresse ligger ved siden af (gateway leveres af DHCP)
        set -- ipv4.method auto ipv4.addresses "$IP/$PREFIX" ipv4.gateway "" ipv4.may-fail yes ipv4.dhcp-timeout 2147483647 ;;
esac
if [ -n "$DNS" ]; then
    set -- "$@" ipv4.dns "$DNS" ipv4.ignore-auto-dns yes
else
    set -- "$@" ipv4.dns "" ipv4.ignore-auto-dns no
fi

# ---------------------------------------------------------------- anvend MIDLERTIDIGT
status applying "Anvender netværksopsætningen"
if ! nm connection modify --temporary uuid "$UUID" "$@" >> "$LOG" 2>&1; then
    reload_saved; status failed "NetworkManager afviste opsætningen — den gamle opsætning er gendannet"; exit 1
fi
if ! nm --wait 30 connection up uuid "$UUID" >> "$LOG" 2>&1; then
    reload_saved; status failed "Netkortet kunne ikke komme op med den nye opsætning — den gamle er gendannet"; exit 1
fi

# ---------------------------------------------------------------- vent på bekræftelse
DEADLINE=$(( $(date +%s) + CONFIRM_S ))
status waiting_confirm "Åbn siden på den nye adresse og tryk Bekræft — ellers gendannes den gamle opsætning" "$DEADLINE"
log "Venter på bekræftelse til $DEADLINE"
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    if [ -e "$CONFIRM" ]; then
        rm -f "$CONFIRM" "$REVERT"
        # Først nu gøres ændringen varig (samme argumenter, uden --temporary) og værtsnavnet sættes
        if ! nm connection modify uuid "$UUID" "$@" >> "$LOG" 2>&1; then
            log "Kunne ikke gemme varigt"
            reload_saved; status failed "Ændringen kunne ikke gemmes varigt — den gamle opsætning er gendannet"; exit 1
        fi
        apply_hostname
        # DHCP-vagten (net-watchdog.sh) læser tilstanden her; skrevet atomisk i root-mappen
        {
            printf 'BACKEND=nm\nMODE=%s\nIFACE=%s\nUUID=%s\nIP=%s\nPREFIX=%s\nGATEWAY=%s\nFALLBACK_AFTER=%s\n' "$MODE" "$IFACE" "$UUID" "$IP" "$PREFIX" "$GATEWAY" "$FALLBACK_AFTER"
        } > "$W/watchdog.conf.tmp" && mv "$W/watchdog.conf.tmp" "$W/watchdog.conf"
        rm -f "$W/watchdog.state"
        log "Bekræftet og gemt"
        status confirmed "Netværksopsætningen er bekræftet og gemt"
        exit 0
    fi
    if [ -e "$REVERT" ]; then
        rm -f "$REVERT"
        log "Fortrudt"
        reload_saved; status reverted "Fortrudt — den gamle opsætning er gendannet"
        exit 0
    fi
    sleep 1
done
log "Ingen bekræftelse inden fristen"
reload_saved
status reverted "Ingen bekræftelse inden for ${CONFIRM_S} sekunder — den gamle opsætning er gendannet"
exit 0
