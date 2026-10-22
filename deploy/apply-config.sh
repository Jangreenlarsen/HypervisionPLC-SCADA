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
set -u
set -f   # ingen glob-udvidelse af uquotede variabler
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

NMCLI=${NMCLI:-nmcli}
HOSTNAMECTL=${HOSTNAMECTL:-hostnamectl}
TIMEOUT_CMD=${TIMEOUT_CMD:-timeout}
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

# ---------------------------------------------------------------- --recover (ExecStopPost): scriptet døde midt i en ændring
if [ "${1:-}" = "--recover" ]; then
    state=$(sed -n 's/.*"state": *"\([a-z_]*\)".*/\1/p' "$STATUS" 2>/dev/null | head -n 1)
    case "$state" in
        applying|waiting_confirm)
            log "Gendanner efter afbrudt ændring (tilstand $state)"
            nm connection reload >> "$LOG" 2>&1
            for u in $(nm -g UUID connection show --active 2>/dev/null); do nm connection up uuid "$u" >> "$LOG" 2>&1; done
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
IFACE=$(field IFACE); MODE=$(field MODE); IP=$(field IP); PREFIX=$(field PREFIX)
GATEWAY=$(field GATEWAY); DNS=$(field DNS); HOSTNAME_NEW=$(field HOSTNAME)
rm -f "$WORKREQ" "$CONFIRM" "$REVERT"

# ---------------------------------------------------------------- validering
is_ipv4() {
    [ -n "$1" ] || return 1
    printf '%s' "$1" | awk -F. 'NF==4 { for (i=1;i<=4;i++) { if ($i !~ /^[0-9]+$/ || length($i) > 3 || $i+0 > 255) exit 1 } exit 0 } { exit 1 }'
}
printf '%s' "$IFACE" | grep -Eq '^[A-Za-z0-9_.-]{1,15}$' || fail "Ugyldigt netkort"
case "$MODE" in dhcp|static|dhcp_static) ;; *) fail "Ugyldig tilstand" ;; esac
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

# ---------------------------------------------------------------- profilen på netkortet
CON=$(nm -g GENERAL.CONNECTION device show "$IFACE" 2>>"$LOG") || fail "Netkortet findes ikke, eller NetworkManager svarer ikke"
{ [ -n "$CON" ] && [ "$CON" != "--" ]; } || fail "Netkortet har ingen aktiv NetworkManager-profil"
UUID=$(nm -g connection.uuid connection show "$CON" 2>>"$LOG") || fail "Profilen kunne ikke læses"
printf '%s' "$UUID" | grep -Eq '^[0-9A-Fa-f-]{8,40}$' || fail "Profilens id er ugyldigt"
log "Anmodet af $BY: $MODE ip=$IP/$PREFIX gw=$GATEWAY dns=$DNS host=$HOSTNAME_NEW iface=$IFACE profil=$CON"

# ---------------------------------------------------------------- argumenter til nmcli
case "$MODE" in
    dhcp)
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
        if [ -n "$HOSTNAME_NEW" ]; then $TIMEOUT_CMD "$NM_T" $HOSTNAMECTL set-hostname "$HOSTNAME_NEW" >> "$LOG" 2>&1 || log "Værtsnavn kunne ikke sættes"; fi
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
