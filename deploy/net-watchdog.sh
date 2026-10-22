#!/bin/sh
# DHCP-vagt: kører som ROOT hvert 30. sekund (hypervisionplc-scada-netwatch.timer).
#
# Formål (System › Konfiguration):
#   * dhcp / dhcp_static: DHCP forsøges uden ende (NetworkManager med dhcp-timeout uendelig); vagten overvåger og melder status.
#   * dhcp_fallback ("fast IP efter N fejl"): tæller kontroller UDEN DHCP-svar; efter N lægges den faste reserve-IP på
#     (MIDLERTIDIGT, --temporary — en genstart starter altid forfra med ren DHCP) og tages af igen, så snart DHCP svarer.
#   * static: ingenting at gøre.
#
# Tilstand læses fra <state>/watchdog.conf (skrives af apply-config.sh EFTER bekræftelse — root-ejet). Intet her kommer fra
# tjenesten (brugeren 'scada'). Vagten rører ikke netværket, mens apply-config.sh arbejder (status applying/waiting_confirm).
# Status til siden: <state>/watchdog.json.
#
# To backends: NetworkManager (nmcli) og ifupdown (iproute2: en DHCP-lease er en adresse med flaget 'dynamic').
# Til test kan kommandoer og mapper overstyres: NMCLI, IPCMD, STATE, TIMEOUT_CMD, SYSNET (standard /sys/class/net).
set -u
set -f
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

NMCLI=${NMCLI:-nmcli}
IPCMD=${IPCMD:-ip}
SYSNET=${SYSNET:-/sys/class/net}
TIMEOUT_CMD=${TIMEOUT_CMD:-timeout}
W=${STATE:-/var/lib/hypervisionplc-scada-net}
CONF=$W/watchdog.conf
WSTATE=$W/watchdog.state
OUT=$W/watchdog.json
LOG=$W/watchdog.log
NM_T=20

nm() { $TIMEOUT_CMD "$NM_T" $NMCLI "$@"; }
log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 200000 ] && tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"; }
conf() { sed -n "s/^$1=//p" "$CONF" | head -n 1; }

[ -f "$CONF" ] && [ ! -L "$CONF" ] || exit 0

BACKEND=$(conf BACKEND); case "$BACKEND" in ifupdown) ;; *) BACKEND=nm ;; esac
MODE=$(conf MODE); IFACE=$(conf IFACE); UUID=$(conf UUID); IP=$(conf IP); PREFIX=$(conf PREFIX)
GATEWAY=$(conf GATEWAY); N=$(conf FALLBACK_AFTER)
printf '%s' "$IFACE" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9_.-]{0,14}$' || exit 0
printf '%s' "$IP" | grep -Eq '^[0-9.]{0,15}$' || IP=
printf '%s' "$GATEWAY" | grep -Eq '^[0-9.]{0,15}$' || GATEWAY=
if [ "$BACKEND" = nm ]; then printf '%s' "$UUID" | grep -Eq '^[0-9A-Fa-f-]{8,40}$' || exit 0; fi
printf '%s' "$N" | grep -Eq '^[0-9]{1,2}$' || N=5
[ "$N" -ge 1 ] || N=5

report() {
    # $1 = tilstand (ok|searching|fallback|nolink|idle), $2 = besked
    printf '{"state":"%s","message":"%s","mode":"%s","fails":%s,"threshold":%s,"fallback_active":%s,"ts":%s}\n' \
        "$1" "$2" "$MODE" "${FAILS:-0}" "$N" "$([ "${FALLBACK:-0}" = 1 ] && echo true || echo false)" "$(date +%s)" > "$OUT.tmp"
    chmod 0644 "$OUT.tmp"
    mv "$OUT.tmp" "$OUT"
}

FAILS=0; FALLBACK=0
BOOT=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo none)
# tilstanden gælder kun siden sidste start: efter en genstart er en midlertidig reserve-IP væk, og tælleren begynder forfra
if [ -f "$WSTATE" ] && [ ! -L "$WSTATE" ] && [ "$(sed -n 's/^boot=//p' "$WSTATE" | head -n 1)" = "$BOOT" ]; then
    FAILS=$(sed -n 's/^fails=//p' "$WSTATE" | head -n 1); FALLBACK=$(sed -n 's/^fallback=//p' "$WSTATE" | head -n 1)
    ROUTE=$(sed -n 's/^route=//p' "$WSTATE" | head -n 1); [ "$ROUTE" = 1 ] || ROUTE=0
    printf '%s' "$FAILS" | grep -Eq '^[0-9]{1,6}$' || FAILS=0
    [ "$FALLBACK" = 1 ] || FALLBACK=0
fi
ROUTE=${ROUTE:-0}
save() { printf 'boot=%s\nfails=%s\nfallback=%s\nroute=%s\n' "$BOOT" "$FAILS" "$FALLBACK" "${ROUTE:-0}" > "$WSTATE.tmp" && mv "$WSTATE.tmp" "$WSTATE"; }

if [ "$MODE" = static ]; then report idle "Fast IP — DHCP bruges ikke"; exit 0; fi

# Ikke i gang med en ændring
cur=$(sed -n 's/.*"state": *"\([a-z_]*\)".*/\1/p' "$W/status.json" 2>/dev/null | head -n 1)
cur_ts=$(sed -n 's/.*"ts": *\([0-9][0-9]*\).*/\1/p' "$W/status.json" 2>/dev/null | head -n 1)
printf '%s' "$cur_ts" | grep -Eq '^[0-9]{1,12}$' || cur_ts=0
# en status der er mere end 10 min gammel er en ændring, der døde (strømsvigt) — den blokerer ikke vagten for evigt
case "$cur" in applying|waiting_confirm) [ $(( $(date +%s) - cur_ts )) -lt 600 ] && exit 0 ;; esac

# --- backend-specifikke handlinger -------------------------------------------------------------------------------
# link_ok: netkortet er oppe og forsøger at få en adresse (ellers, fx kabel ude, tælles ikke)
# has_lease: DHCP har givet en adresse; fallback_on/fallback_off: læg reserve-IP'en på / tag den af (begge MIDLERTIDIGE)
if [ "$BACKEND" = ifupdown ]; then
    link_ok() { [ "$(cat "$SYSNET/$IFACE/carrier" 2>/dev/null)" = 1 ]; }
    has_lease() { $IPCMD -4 -o addr show dev "$IFACE" 2>/dev/null | grep -v " $IP/" | grep -q ' dynamic'; }
    has_addr() { $IPCMD -4 -o addr show dev "$IFACE" 2>/dev/null | grep -q " $IP/"; }
    fallback_on() {
        has_addr || $IPCMD addr add "$IP/$PREFIX" dev "$IFACE" >> "$LOG" 2>&1 || return 1
        if [ -n "$GATEWAY" ] && ! $IPCMD -4 route show default 2>/dev/null | grep -q default; then
            $IPCMD route add default via "$GATEWAY" dev "$IFACE" >> "$LOG" 2>&1 && ROUTE=1
        fi
        return 0
    }
    fallback_off() {
        if [ "${ROUTE:-0}" = 1 ] && [ -n "$GATEWAY" ]; then $IPCMD route del default via "$GATEWAY" dev "$IFACE" >> "$LOG" 2>&1; fi
        if has_addr; then $IPCMD addr del "$IP/$PREFIX" dev "$IFACE" >> "$LOG" 2>&1; fi    # væk i forvejen (fx efter genstart) er ikke en fejl
    }
else
    link_ok() {
        # 70 = henter IP, 80/90 = tjekker, 100 = tilsluttet
        code=$(nm -g GENERAL.STATE device show "$IFACE" 2>/dev/null | head -n 1 | sed -n 's/^\([0-9]*\).*/\1/p')
        case "$code" in 70|80|90|100) return 0 ;; *) return 1 ;; esac
    }
    has_lease() { [ -n "$(nm -g DHCP4.OPTION device show "$IFACE" 2>/dev/null | head -n 1)" ]; }   # DHCP4.*-felterne findes kun med en lease
    fallback_on() {
        nm connection modify --temporary uuid "$UUID" ipv4.addresses "$IP/$PREFIX" ipv4.gateway "$GATEWAY" >> "$LOG" 2>&1 \
            && nm device reapply "$IFACE" >> "$LOG" 2>&1
    }
    fallback_off() {
        nm connection modify --temporary uuid "$UUID" ipv4.addresses "" ipv4.gateway "" >> "$LOG" 2>&1 \
            && nm device reapply "$IFACE" >> "$LOG" 2>&1
    }
fi

link_ok || { report nolink "Netkortet er ikke tilsluttet (kabel?) — tæller ikke som DHCP-fejl"; exit 0; }

if has_lease; then
    if [ "$FALLBACK" = 1 ]; then
        log "DHCP svarer igen — fjerner reserve-IP"
        if fallback_off; then FALLBACK=0; ROUTE=0; else log "Kunne ikke fjerne reserve-IP"; fi
    fi
    FAILS=0; save
    report ok "DHCP svarer"
    exit 0
fi

FAILS=$((FAILS + 1))
if [ "$MODE" = dhcp_fallback ] && [ "$FALLBACK" = 0 ] && [ "$FAILS" -ge "$N" ]; then
    case "$PREFIX" in ''|*[!0-9]*) PREFIX= ;; esac
    if [ -n "$IP" ] && [ -n "$PREFIX" ]; then
        log "Ingen DHCP-svar i $FAILS kontroller — tager reserve-IP $IP/$PREFIX i brug"
        if fallback_on; then
            FALLBACK=1
        else
            log "Kunne ikke tage reserve-IP i brug"
        fi
    fi
fi
save
if [ "$FALLBACK" = 1 ]; then report fallback "Ingen DHCP-svar — kører på reserve-IP $IP"; else report searching "Ingen DHCP-svar endnu"; fi
exit 0
