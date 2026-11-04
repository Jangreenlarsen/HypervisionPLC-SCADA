#!/bin/sh
# Let's Encrypt fra System › Certifikater. Køres som ROOT af systemd (hypervisionplc-scada-le.service, udløst af .path-enheden
# når le.request findes) — aldrig direkte af tjenesten. Selve arbejdet gøres af hypervision-letsencrypt (tls-letsencrypt.sh).
#
# Anmodningen er én linje "<id> <handling> [argumenter]":
#   install                                  installér certbot (apt) og aktivér automatisk fornyelse
#   dns-config <zone> <navn>                 deSEC-zone/navn; tokenet (valgfrit) ligger i <data>/config/le-token
#   issue <dns|http> <hostnavn> <e-mail> <live|dry>
#   info                                     opdatér kun le-info.json
# Status:  <state>/le-status.json  {"id","action","state":"running|ok|error","message","started","ts"}
# Log:     <state>/le-run.log      (seneste kørsel; certbots output — indeholder aldrig tokenet)
# Overblik: <state>/le-info.json   {"certbot","timer","token","zone","sub","lineage","last":{method,host,email,ts}}
#
# SIKKERHED: anmodning og token flyttes (mv) ind i rootens egen mappe, før de læses; symlinks afvises; alle argumenter valideres
# med faste mønstre her OG igen af hypervision-letsencrypt; tokenet gives kun via stdin og slettes straks.
#
# Til test kan kommandoer og mapper overstyres: DATA, STATE, PRIV, LE, LE_CONF, CERTBOT_LIVE, SYSTEMCTL.
set -u
set -f
umask 077
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

DATA=${DATA:-/var/lib/hypervisionplc-scada}
W=${STATE:-/var/lib/hypervisionplc-scada-net}
PRIV=${PRIV:-/var/lib/hypervisionplc-scada-tls}
LE=${LE:-/usr/local/sbin/hypervision-letsencrypt}
CONF=${LE_CONF:-/etc/hypervisionplc-scada/letsencrypt}
LIVE=${CERTBOT_LIVE:-/etc/letsencrypt/live/hypervision-scada}
SYSTEMCTL=${SYSTEMCTL:-systemctl}
REQ=$DATA/config/le.request
TOKEN_REQ=$DATA/config/le-token
RUNLOG=$W/le-run.log

clean() { printf '%s' "$1" | tr '\n' ' ' | tr -cd ' -~' | tr -d '"\\' | cut -c1-280; }
is_host() { printf '%s' "$1" | grep -Eqx '[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+'; }
is_mail() { printf '%s' "$1" | grep -Eqx '[A-Za-z0-9][A-Za-z0-9._+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'; }

ID=""; ACTION=""; STARTED=$(date +%s)
status() {   # $1 = running|ok|error, $2 = besked
    printf '{"id":"%s","action":"%s","state":"%s","message":"%s","started":%s,"ts":%s}\n' \
        "$ID" "$(clean "$ACTION")" "$1" "$(clean "$2")" "$STARTED" "$(date +%s)" > "$W/le-status.json.tmp"
    chmod 0644 "$W/le-status.json.tmp"
    mv -f "$W/le-status.json.tmp" "$W/le-status.json"
}

write_info() {
    certbot=false; timer=false; token=false; lineage=false; zone=""; sub=""
    command -v certbot >/dev/null 2>&1 && certbot=true
    $SYSTEMCTL is-enabled certbot.timer >/dev/null 2>&1 && timer=true
    [ -f "$CONF/desec.ini" ] && token=true
    [ -f "$LIVE/fullchain.pem" ] && lineage=true
    if [ -f "$CONF/target.conf" ]; then
        zone=$(sed -n 's/^DESEC_ZONE=//p' "$CONF/target.conf" | head -n 1)
        sub=$(sed -n 's/^DESEC_SUB=//p' "$CONF/target.conf" | head -n 1)
    fi
    last="null"
    [ -f "$PRIV/le-last" ] && last=$(cat "$PRIV/le-last")
    printf '{"certbot":%s,"timer":%s,"token":%s,"zone":"%s","sub":"%s","lineage":%s,"last":%s,"ts":%s}\n' \
        "$certbot" "$timer" "$token" "$(clean "$zone")" "$(clean "$sub")" "$lineage" "$last" "$(date +%s)" > "$W/le-info.json.tmp"
    chmod 0644 "$W/le-info.json.tmp"
    mv -f "$W/le-info.json.tmp" "$W/le-info.json"
}

mkdir -p "$W" "$PRIV"
chmod 0700 "$PRIV"

# ExecStopPost: blev kørslen dræbt (timeout, OOM, strømsvigt), står status stadig på "running" — sæt den til fejl
if [ "${1:-}" = stop-post ]; then
    if [ -f "$W/le-status.json" ] && grep -q '"state":"running"' "$W/le-status.json"; then
        ID=$(sed -n 's/.*"id":"\([0-9a-f]*\)".*/\1/p' "$W/le-status.json"); ACTION=$(sed -n 's/.*"action":"\([a-z-]*\)".*/\1/p' "$W/le-status.json")
        status error "Afbrudt (tidsgrænse eller genstart) — se loggen"
    fi
    exit 0
fi

[ -e "$REQ" ] || [ -L "$REQ" ] || exit 0
if [ -L "$REQ" ]; then rm -f "$REQ"; exit 0; fi
rm -f "$PRIV/le.req" "$PRIV/le.token"
mv -f "$REQ" "$PRIV/le.req" 2>/dev/null || exit 0
if [ -L "$PRIV/le.req" ] || [ ! -f "$PRIV/le.req" ]; then rm -f "$PRIV/le.req"; exit 0; fi
read -r ID ACTION A1 A2 A3 A4 REST < "$PRIV/le.req" || true
rm -f "$PRIV/le.req"
[ "${ACTION:-}" = dns-config ] || rm -f "$TOKEN_REQ"     # et efterladt token bruges kun af den anmodning, det fulgte med
printf '%s' "${ID:-}" | grep -Eqx '[0-9a-f]{8}' || { ID=""; exit 0; }
A1=${A1:-}; A2=${A2:-}; A3=${A3:-}; A4=${A4:-}
if [ -n "${REST:-}" ]; then status error "Ugyldig anmodning"; exit 0; fi

status running "I gang"
: > "$RUNLOG"; chmod 0644 "$RUNLOG"
case "$ACTION" in
    install)
        set -- install ;;
    dns-config)
        is_host "$A1" || { status error "Ugyldig deSEC-zone"; write_info; exit 0; }
        printf '%s' "$A2" | grep -Eqx '[a-z0-9]([a-z0-9-]{0,60}[a-z0-9])?' || { status error "Ugyldigt navn (ét led, fx scada-acme)"; write_info; exit 0; }
        if [ -e "$TOKEN_REQ" ] || [ -L "$TOKEN_REQ" ]; then
            mv -f "$TOKEN_REQ" "$PRIV/le.token" 2>/dev/null
            if [ -L "$PRIV/le.token" ] || [ ! -f "$PRIV/le.token" ] || [ "$(wc -c < "$PRIV/le.token")" -gt 200 ]; then
                rm -f "$PRIV/le.token"; status error "Tokenet kunne ikke overtages"; write_info; exit 0
            fi
            if ! out=$("$LE" set-token < "$PRIV/le.token" 2>&1); then
                rm -f "$PRIV/le.token"; status error "$out"; write_info; exit 0
            fi
            rm -f "$PRIV/le.token"
        fi
        set -- set-target "$A1" "$A2" ;;
    issue)
        case "$A1" in dns|http) ;; *) status error "Ukendt metode"; write_info; exit 0 ;; esac
        is_host "$A2" || { status error "Ugyldigt værtsnavn"; write_info; exit 0; }
        is_mail "$A3" || { status error "Ugyldig e-mailadresse"; write_info; exit 0; }
        case "$A4" in live|dry) ;; *) status error "Ugyldig anmodning"; write_info; exit 0 ;; esac
        set -- issue "$A2" "$A3" --method "$A1"
        [ "$A4" = dry ] && set -- "$@" --dry-run ;;
    info)
        write_info; status ok "Opdateret"; exit 0 ;;
    *)
        status error "Ukendt handling"; exit 0 ;;
esac

if "$LE" "$@" >> "$RUNLOG" 2>&1; then
    if [ "$ACTION" = issue ] && [ "$A4" = live ]; then
        printf '{"method":"%s","host":"%s","email":"%s","ts":%s}' "$A1" "$A2" "$A3" "$(date +%s)" > "$PRIV/le-last"
    fi
    write_info
    status ok "$(tail -n 1 "$RUNLOG")"
else
    write_info
    msg=$(grep -E 'FEJL|Error|error|Detail|Problem' "$RUNLOG" | tail -n 3 | tr '\n' ' ')
    status error "${msg:-Mislykkedes — se loggen}"
fi
exit 0
