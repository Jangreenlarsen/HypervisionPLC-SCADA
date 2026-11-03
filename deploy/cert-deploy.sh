#!/bin/sh
# Certifikat-hook (root). Kaldes af certbot efter hver udstedelse OG fornyelse (--deploy-hook; certbot sætter RENEWED_LINEAGE),
# og med "info" af install.sh og tls-letsencrypt.sh for blot at opdatere certifikatets metadata til System › Status.
#
#   cert-deploy.sh            installér certifikatet fra $RENEWED_LINEAGE (kun under /etc/letsencrypt/live/)
#   cert-deploy.sh info       skriv <state>/cert.json ud fra det certifikat nginx bruger nu (ændrer ikke noget andet)
#
# Installation: nøgle og certifikat kontrolleres (passer nøglen til certifikatet?), det forrige gemmes som *.prev (og det
# SELVSIGNEREDE som *.selfsigned første gang), de nye filer lægges ved siden af og flyttes på plads (mv), parret kontrolleres igen,
# `nginx -t` kontrollerer konfigurationen — slår noget fejl, gendannes det forrige certifikat (INGEN lockout; passer det
# gendannede par ikke sammen, bruges det selvsignerede) — og først derefter genindlæses nginx.
#
# Kopieres af install.sh til /usr/local/lib/hypervisionplc-scada/ (stien står i certbots fornyelsesopsætning).
# Til test kan kommandoer og mapper overstyres: TLSDIR, STATE, LINEAGE_ROOT, LINEAGE/RENEWED_LINEAGE, NGINX, SYSTEMCTL, OPENSSL.
set -u
umask 077
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

TLSDIR=${TLSDIR:-/etc/hypervisionplc-scada/tls}
STATE=${STATE:-/var/lib/hypervisionplc-scada-net}
LINEAGE_ROOT=${LINEAGE_ROOT:-/etc/letsencrypt/live}
LINEAGE=${RENEWED_LINEAGE:-${LINEAGE:-$LINEAGE_ROOT/hypervision-scada}}
NGINX=${NGINX:-nginx}
SYSTEMCTL=${SYSTEMCTL:-systemctl}
OPENSSL=${OPENSSL:-openssl}
CERT=$TLSDIR/fullchain.pem
KEY=$TLSDIR/privkey.pem

say() { printf '%s\n' "$*"; }
fail() { say "FEJL: $*" >&2; exit 1; }

# Kun printbare ASCII-tegn i JSON (værdierne kommer fra openssl, men citeres aldrig ukontrolleret; ingen afskårne UTF-8-tegn)
clean() { printf '%s' "$1" | tr -cd ' -~' | tr -d '"\\' | cut -c1-200; }

# Passer nøglen $1 til certifikatet $2? (samme offentlige nøgle)
pair_ok() {
    a=$($OPENSSL x509 -in "$2" -noout -pubkey 2>/dev/null | $OPENSSL sha256 2>/dev/null)
    b=$($OPENSSL pkey -in "$1" -pubout 2>/dev/null | $OPENSSL sha256 2>/dev/null)
    [ -n "$a" ] && [ "$a" = "$b" ]
}

write_info() {
    [ -f "$CERT" ] || { say "Intet certifikat at beskrive i $TLSDIR"; return 0; }
    subject=$($OPENSSL x509 -in "$CERT" -noout -subject 2>/dev/null | sed 's/^subject= *//')
    issuer=$($OPENSSL x509 -in "$CERT" -noout -issuer 2>/dev/null | sed 's/^issuer= *//')
    not_after=$($OPENSSL x509 -in "$CERT" -noout -enddate 2>/dev/null | sed 's/^notAfter=//')
    not_before=$($OPENSSL x509 -in "$CERT" -noout -startdate 2>/dev/null | sed 's/^notBefore=//')
    fp=$($OPENSSL x509 -in "$CERT" -noout -fingerprint -sha256 2>/dev/null | sed 's/^.*Fingerprint=//')
    [ -n "$not_after" ] || fail "Kan ikke læse certifikatet $CERT"
    selfsigned=false
    [ "$subject" = "$issuer" ] && selfsigned=true
    mkdir -p "$STATE" || fail "Kan ikke oprette $STATE"
    printf '{"subject":"%s","issuer":"%s","not_before":"%s","not_after":"%s","fingerprint":"%s","self_signed":%s,"updated":%s}\n' \
        "$(clean "$subject")" "$(clean "$issuer")" "$(clean "$not_before")" "$(clean "$not_after")" "$(clean "$fp")" "$selfsigned" "$(date +%s)" \
        > "$STATE/cert.json.tmp" && chmod 0644 "$STATE/cert.json.tmp" && mv "$STATE/cert.json.tmp" "$STATE/cert.json"
}

if [ "${1:-}" = "info" ]; then write_info; exit 0; fi

# ------------------------------------------------------------------ installér
case "$LINEAGE" in *..*) fail "Ugyldig certifikatsti ($LINEAGE)" ;; esac
case "$LINEAGE" in "$LINEAGE_ROOT"/*) ;; *) fail "Ugyldig certifikatsti ($LINEAGE) — kun under $LINEAGE_ROOT" ;; esac
[ -f "$LINEAGE/fullchain.pem" ] && [ -f "$LINEAGE/privkey.pem" ] || fail "fullchain.pem/privkey.pem mangler i $LINEAGE"
pair_ok "$LINEAGE/privkey.pem" "$LINEAGE/fullchain.pem" || fail "Nøglen passer ikke til certifikatet i $LINEAGE — intet er ændret"

[ -d "$TLSDIR" ] || ( umask 027; mkdir -p "$TLSDIR" ) || fail "Kan ikke oprette $TLSDIR"      # 0750 via umask

# Det forrige par gemmes: først det selvsignerede (kun første gang), så altid som .prev. Mislykkes det, ændres INTET.
rm -f "$CERT.prev" "$KEY.prev"
HAD_PREV=0
if [ -f "$CERT" ] && [ -f "$KEY" ]; then
    if [ ! -f "$CERT.selfsigned" ] && [ "$($OPENSSL x509 -in "$CERT" -noout -subject 2>/dev/null | sed 's/^subject= *//')" = \
         "$($OPENSSL x509 -in "$CERT" -noout -issuer 2>/dev/null | sed 's/^issuer= *//')" ]; then
        { cp -p "$CERT" "$CERT.selfsigned" && cp -p "$KEY" "$KEY.selfsigned" && chmod 0600 "$KEY.selfsigned"; } \
            || { rm -f "$CERT.selfsigned" "$KEY.selfsigned"; fail "Kunne ikke gemme det selvsignerede certifikat — intet er ændret"; }
    fi
    { cp -p "$CERT" "$CERT.prev" && cp -p "$KEY" "$KEY.prev" && chmod 0600 "$KEY.prev"; } \
        || { rm -f "$CERT.prev" "$KEY.prev"; fail "Kunne ikke gemme det forrige certifikat — intet er ændret"; }
    HAD_PREV=1
fi

# Gendan: det forrige par; passer det ikke sammen (eller findes det ikke), det selvsignerede. Aldrig et blandet par.
restore() {
    if [ "$HAD_PREV" = 1 ] && [ -f "$KEY.prev" ] && [ -f "$CERT.prev" ] && pair_ok "$KEY.prev" "$CERT.prev"; then
        cp -p "$KEY.prev" "$KEY.rst" && cp -p "$CERT.prev" "$CERT.rst" && mv "$KEY.rst" "$KEY" && mv "$CERT.rst" "$CERT" \
            && pair_ok "$KEY" "$CERT" && { say "Det forrige certifikat er gendannet"; return 0; }
    fi
    if [ -f "$KEY.selfsigned" ] && [ -f "$CERT.selfsigned" ] && pair_ok "$KEY.selfsigned" "$CERT.selfsigned"; then
        cp -p "$KEY.selfsigned" "$KEY.rst" && cp -p "$CERT.selfsigned" "$CERT.rst" && mv "$KEY.rst" "$KEY" && mv "$CERT.rst" "$CERT" \
            && pair_ok "$KEY" "$CERT" && { say "Det selvsignerede certifikat er gendannet"; return 0; }
    fi
    rm -f "$KEY.rst" "$CERT.rst"
    say "ADVARSEL: intet certifikatpar kunne gendannes — tjek $TLSDIR (kør: hypervision-letsencrypt status)" >&2
    return 1
}

# Nye filer ved siden af, derefter mv (nøglen først); parret kontrolleres bagefter, og enhver fejl gendanner det forrige
cp "$LINEAGE/privkey.pem" "$KEY.new" && cp "$LINEAGE/fullchain.pem" "$CERT.new" \
    || { rm -f "$KEY.new" "$CERT.new"; fail "Kunne ikke kopiere det nye certifikat — intet er ændret"; }
chmod 0600 "$KEY.new" && chmod 0644 "$CERT.new" || { rm -f "$KEY.new" "$CERT.new"; fail "Kunne ikke sætte rettigheder — intet er ændret"; }
if ! { mv "$KEY.new" "$KEY" && mv "$CERT.new" "$CERT" && pair_ok "$KEY" "$CERT"; }; then
    rm -f "$KEY.new" "$CERT.new"
    restore
    fail "Kunne ikke lægge det nye certifikat på plads"
fi

if ! $NGINX -t > /dev/null 2>&1; then
    if [ "$HAD_PREV" = 1 ]; then
        restore
        fail "nginx afviste konfigurationen med det nye certifikat — det forrige er gendannet"
    fi
    fail "nginx afviste konfigurationen (eller nginx er ikke installeret) — der var intet forrige certifikat at gendanne; kør install.sh med --with-nginx"
fi
$SYSTEMCTL reload nginx > /dev/null 2>&1 || $SYSTEMCTL restart nginx > /dev/null 2>&1 || say "ADVARSEL: nginx kunne ikke genindlæses — certifikatet bruges ved næste start"
write_info
say "Certifikatet er installeret: $($OPENSSL x509 -in "$CERT" -noout -subject -enddate 2>/dev/null | tr '\n' ' ')"
exit 0
