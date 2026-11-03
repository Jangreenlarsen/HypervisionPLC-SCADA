#!/bin/sh
# certbot --manual-auth-hook / --manual-cleanup-hook mod deSEC's REST API (DNS-01). Køres som ROOT af certbot:
#   desec-acme-hook.sh auth       sæt TXT-posten med udfordringen (CERTBOT_VALIDATION) i din deSEC-zone
#   desec-acme-hook.sh cleanup    fjern den igen
#
# Hvorfor ikke Debians certbot-plugin: pakken python3-certbot-dns-desec (1.2.1 i Trixie) leder efter en zone for selve
# `_acme-challenge.<navn>` hos deSEC og følger IKKE CNAME'er — men en CNAME fra one.com til en deSEC-zone er hele pointen.
# Denne hook skriver derfor direkte i zonen, som CNAME'en peger på: <DESEC_SUB>.<DESEC_ZONE> (TXT-posten findes dér; Let's Encrypt
# følger CNAME'en `_acme-challenge.<navn>` → <DESEC_SUB>.<DESEC_ZONE> og læser TXT-posten).
#
# Opsætning: <conf>/desec.ini  (dns_desec_token = …; root 0600)  og  <conf>/target.conf  (DESEC_ZONE=… og DESEC_SUB=…).
# Tokenet står aldrig på en kommandolinje (curl læser headeren fra en 0600-fil) og skrives aldrig til log/udskrift.
# Til test kan kommandoer og mapper overstyres: LE_CONF, CURL, SLEEP_S.
set -u
umask 077
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

CONF=${LE_CONF:-/etc/hypervisionplc-scada/letsencrypt}
CURL=${CURL:-curl}
API=${DESEC_API:-https://desec.io/api/v1}
WAIT=${SLEEP_S:-45}      # deSEC skal nå at sende ændringen til sine navneservere, før Let's Encrypt spørger

say() { printf '%s\n' "$*"; }
fail() { say "desec-acme-hook: $*" >&2; exit 1; }

mode=${1:-}
case "$mode" in auth|cleanup) ;; *) fail "brug: desec-acme-hook.sh auth|cleanup" ;; esac

TOKEN=$(sed -n 's/^dns_desec_token *= *//p' "$CONF/desec.ini" 2>/dev/null | head -n 1)
printf '%s' "$TOKEN" | grep -Eq '^[A-Za-z0-9_-]{20,100}$' || fail "intet gyldigt deSEC-token i $CONF/desec.ini (kør: hypervision-letsencrypt set-token)"
DESEC_ZONE=$(sed -n 's/^DESEC_ZONE=//p' "$CONF/target.conf" 2>/dev/null | head -n 1)
DESEC_SUB=$(sed -n 's/^DESEC_SUB=//p' "$CONF/target.conf" 2>/dev/null | head -n 1)
printf '%s' "$DESEC_ZONE" | grep -Eq '^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$' || fail "ingen gyldig deSEC-zone i $CONF/target.conf (kør: hypervision-letsencrypt set-target <zone>)"
printf '%s' "$DESEC_SUB" | grep -Eq '^[a-z0-9]([a-z0-9-]{0,60}[a-z0-9])?$' || fail "ugyldigt navn til udfordringen i $CONF/target.conf"

URL="$API/domains/$DESEC_ZONE/rrsets/$DESEC_SUB/TXT/"
HDR=$(mktemp "${TMPDIR:-/tmp}/desec-hdr.XXXXXX") || fail "kan ikke oprette en midlertidig fil"
trap 'rm -f "$HDR"' EXIT HUP INT TERM
printf 'Authorization: Token %s\n' "$TOKEN" > "$HDR"; chmod 0600 "$HDR"

case "$mode" in
auth)
    V=${CERTBOT_VALIDATION:-}
    printf '%s' "$V" | grep -Eq '^[A-Za-z0-9_-]{20,100}$' || fail "CERTBOT_VALIDATION mangler eller ser forkert ud"
    BODY=$(printf '{"subname":"%s","type":"TXT","ttl":3600,"records":["\\"%s\\""]}' "$DESEC_SUB" "$V")
    code=$(printf '%s' "$BODY" | $CURL -sS -m 60 -o /dev/null -w '%{http_code}' -X PUT -H @"$HDR" -H 'Content-Type: application/json' --data-binary @- "$URL") || fail "kunne ikke nå deSEC (internet?)"
    case "$code" in 200|201) ;; 401|403) fail "deSEC afviste tokenet (HTTP $code)" ;; 404) fail "zonen $DESEC_ZONE findes ikke på denne deSEC-konto (HTTP 404)" ;; *) fail "deSEC svarede HTTP $code" ;; esac
    say "TXT-posten er sat på $DESEC_SUB.$DESEC_ZONE — venter $WAIT s på deSEC's navneservere"
    sleep "$WAIT"
    ;;
cleanup)
    code=$($CURL -sS -m 60 -o /dev/null -w '%{http_code}' -X DELETE -H @"$HDR" "$URL") || fail "kunne ikke nå deSEC (internet?)"
    case "$code" in 204|404) ;; *) say "ADVARSEL: TXT-posten kunne ikke fjernes (HTTP $code) — den ligger ufarligt og overskrives næste gang" >&2 ;; esac
    ;;
esac
exit 0
