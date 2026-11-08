#!/bin/sh
# Modtag et Let's Encrypt-certifikat fra en reverse proxy foran SCADA'en (v4.11.0), så SCADA'en bruger SAMME certifikat som
# proxyen — klienter på LAN, der går direkte til SCADA'en, og proxyens forbindelse bagud kan så stole på TLS.
#
# Køres som ROOT af sshd som "forced command" for én bestemt nøgle (root's authorized_keys):
#   from="<proxyens IP>",command="/usr/local/lib/hypervisionplc-scada/cert-receive.sh",restrict ssh-ed25519 AAAA… proxy-cert
# Proxyen sender en ukomprimeret tar med præcis fullchain.pem og privkey.pem på stdin (deploy/proxy-cert-push.sh).
# Nøglen kan intet andet: kommandoen er fast, og `restrict` slår pty, port- og agent-videresendelse fra.
#
# Filerne kontrolleres (kun de to navne, almindelige filer, PEM, højst 64 KB, CN/SAN er SCADA'ens navn), lægges i
# /etc/letsencrypt/live/hypervision-scada og installeres af cert-deploy.sh (passer nøgle og certifikat, nginx -t,
# det forrige gemmes som .prev og gendannes ved fejl — ingen lockout). Resultatet logges i <state>/cert-receive.log.
#
# Til test kan mapper og kommandoer overstyres: LIVE, HOOK, STATE, TLSDIR, WANT_NAME, OPENSSL.
set -u
set -f
umask 077
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

LIVE=${LIVE:-/etc/letsencrypt/live/hypervision-scada}
HOOK=${HOOK:-/usr/local/lib/hypervisionplc-scada/cert-deploy.sh}
STATE=${STATE:-/var/lib/hypervisionplc-scada-net}
OPENSSL=${OPENSSL:-openssl}
TLSDIR=${TLSDIR:-/etc/hypervisionplc-scada/tls}
MAX=65536
LOG=$STATE/cert-receive.log

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG" 2>/dev/null; printf '%s\n' "$*"; }
fail() { log "FEJL: $*"; exit 1; }

mkdir -p "$STATE"
T=$(mktemp -d) || fail "kan ikke lave en midlertidig mappe"
trap 'rm -rf "$T"' EXIT INT TERM

# Højst 2 × 64 KB + tar-overhead læses; tar pakker KUN de to navne ud (ingen stier, ingen andre filer)
head -c $((2 * MAX + 10240)) > "$T/in.tar"
mkdir "$T/x"
tar -xf "$T/in.tar" -C "$T/x" --no-same-owner --no-same-permissions fullchain.pem privkey.pem 2>/dev/null \
    || fail "pakken skal indeholde præcis fullchain.pem og privkey.pem"
for f in fullchain.pem privkey.pem; do
    p=$T/x/$f
    [ -f "$p" ] && [ ! -L "$p" ] || fail "$f er ikke en almindelig fil"
    [ "$(wc -c < "$p")" -le $MAX ] || fail "$f er for stor"
done
grep -q -- '-----BEGIN CERTIFICATE-----' "$T/x/fullchain.pem" || fail "fullchain.pem er ikke et PEM-certifikat"
grep -q -- '-----BEGIN .*PRIVATE KEY-----' "$T/x/privkey.pem" || fail "privkey.pem er ikke en PEM-nøgle"

# Certifikatet skal gælde for SCADA'ens navn (WANT_NAME, ellers det navn, det nuværende certifikat er udstedt til)
if [ -z "${WANT_NAME:-}" ] && [ -f "$TLSDIR/fullchain.pem" ]; then
    WANT_NAME=$($OPENSSL x509 -in "$TLSDIR/fullchain.pem" -noout -subject -nameopt multiline 2>/dev/null \
        | sed -n 's/^ *commonName *= *//p' | head -n 1)
fi
if [ -n "${WANT_NAME:-}" ]; then
    $OPENSSL x509 -in "$T/x/fullchain.pem" -noout -checkhost "$WANT_NAME" 2>/dev/null | grep -q 'does match' \
        || fail "certifikatet gælder ikke for $WANT_NAME — intet er ændret"
fi
$OPENSSL x509 -in "$T/x/fullchain.pem" -noout -checkend 0 >/dev/null 2>&1 || fail "certifikatet er udløbet — intet er ændret"

# Samme fil som sidst? Så er der intet at gøre (fornyelsen af et andet certifikat på proxyen)
if [ -f "$LIVE/fullchain.pem" ] && cmp -s "$LIVE/fullchain.pem" "$T/x/fullchain.pem" \
        && cmp -s "$TLSDIR/fullchain.pem" "$T/x/fullchain.pem"; then
    log "uændret: certifikatet er allerede installeret"
    exit 0
fi

mkdir -p "$LIVE"
chmod 0700 "$LIVE"
install -m 0600 "$T/x/privkey.pem" "$LIVE/privkey.pem.new" && install -m 0644 "$T/x/fullchain.pem" "$LIVE/fullchain.pem.new" \
    && mv -f "$LIVE/privkey.pem.new" "$LIVE/privkey.pem" && mv -f "$LIVE/fullchain.pem.new" "$LIVE/fullchain.pem" \
    || fail "kunne ikke gemme certifikatet i $LIVE"

if out=$(RENEWED_LINEAGE=$LIVE "$HOOK" 2>&1); then
    log "installeret: $($OPENSSL x509 -in "$LIVE/fullchain.pem" -noout -subject -enddate 2>/dev/null | tr '\n' ' ')"
else
    fail "cert-deploy.sh afviste certifikatet: $(printf '%s' "$out" | tail -n 3 | tr '\n' ' ')"
fi
