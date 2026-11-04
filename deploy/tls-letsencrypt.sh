#!/bin/sh
# Let's Encrypt-certifikat til nginx via certbot + deSEC (DNS-01) — styres af en admin på Pi'en. Køres som ROOT.
#
#   hypervision-letsencrypt install                       installér certbot (apt) og aktivér automatisk fornyelse
#   hypervision-letsencrypt set-token                     gem deSEC-tokenet (læses fra stdin, vises/logges aldrig)
#   hypervision-letsencrypt set-target <zone> [navn]      deSEC-zonen og navnet, `_acme-challenge.<hostnavn>`-CNAME'en peger på
#                                                         (<navn>.<zone>; standard-navn: scada-acme)
#   hypervision-letsencrypt issue <hostnavn> <e-mail> [--method dns|http] [--dry-run] [--force]
#                                                         --dry-run: hele forløbet mod Let's Encrypts STAGING, intet gemmes
#   hypervision-letsencrypt status                        certifikatet nginx bruger nu + certbots oversigt
#   hypervision-letsencrypt renew-test                    `certbot renew --dry-run`
#
# Navnet skal have en CNAME `_acme-challenge.<hostnavn>` → `<navn>.<zone>` (se docs/TLS_LETSENCRYPT.md). TXT-posten skrives af
# desec-acme-hook.sh direkte i zonen (certbots deSEC-plugin i Debian følger ikke CNAME'er, derfor en hook).
# Fornyelse sker af Debians certbot.timer; deploy-hooken (cert-deploy.sh) lægger certifikatet på nginx' sti og genindlæser nginx.
# Slår udstedelsen fejl, bliver det nuværende certifikat liggende — ingen lockout.
#
# Kopieres af install.sh til /usr/local/sbin/hypervision-letsencrypt. Til test kan kommandoer og mapper overstyres:
# CERTBOT, APT_GET, SYSTEMCTL, LE_CONF, HOOK, AUTH_HOOK, TLSDIR.
set -u
umask 077
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

CERTBOT=${CERTBOT:-certbot}
APT_GET=${APT_GET:-apt-get}
SYSTEMCTL=${SYSTEMCTL:-systemctl}
CONF=${LE_CONF:-/etc/hypervisionplc-scada/letsencrypt}
INI=$CONF/desec.ini
TARGET=$CONF/target.conf
TLSDIR=${TLSDIR:-/etc/hypervisionplc-scada/tls}
LIB=/usr/local/lib/hypervisionplc-scada
HOOK=${HOOK:-$LIB/cert-deploy.sh}
AUTH_HOOK=${AUTH_HOOK:-$LIB/desec-acme-hook.sh}
CERTNAME=hypervision-scada
WEBROOT=${WEBROOT:-/var/lib/hypervisionplc-scada-acme}     # HTTP-01: nginx' port 80 serverer /.well-known/acme-challenge/ herfra

say() { printf '%s\n' "$*"; }
fail() { say "FEJL: $*" >&2; exit 1; }
one_line() { [ "$(printf '%s\n' "$1" | wc -l)" -eq 1 ]; }   # grep tester linje for linje, så flere linjer afvises særskilt
is_host() { one_line "$1" && printf '%s' "$1" | grep -Eq '^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$'; }

# Mappen med tokenet: kun root (umask 077 ved oprettelse; chmod for en mappe, der fandtes i forvejen)
ensure_conf() {
    ( umask 077; mkdir -p "$CONF" ) || fail "Kan ikke oprette $CONF"
    chmod 0700 "$CONF" 2>/dev/null || true
}

cmd=${1:-}
[ $# -gt 0 ] && shift

case "$cmd" in
install)
    $APT_GET install -y certbot curl || fail "apt kunne ikke installere certbot (er der internet?)"
    ensure_conf
    $SYSTEMCTL enable --now certbot.timer > /dev/null 2>&1 || say "ADVARSEL: certbot.timer kunne ikke aktiveres — fornyelse sker ikke automatisk"
    say "certbot er installeret. Næste: set-token, set-target <zone>, derefter issue <hostnavn> <e-mail> --dry-run"
    ;;
set-token)
    if [ -t 0 ]; then
        trap 'stty echo 2>/dev/null' EXIT INT TERM      # Ctrl-C må ikke efterlade terminalen uden echo
        printf 'deSEC-token: ' >&2; stty -echo 2>/dev/null
    fi
    IFS= read -r TOKEN
    [ -t 0 ] && { stty echo 2>/dev/null; printf '\n' >&2; }
    TOKEN=${TOKEN%"$(printf '\015')"}     # et token indsat fra Windows kan ende på CR
    one_line "$TOKEN" && printf '%s' "$TOKEN" | grep -Eq '^[A-Za-z0-9_-]{20,100}$' || fail "Tokenet ser ikke rigtigt ud (20-100 tegn: bogstaver, tal, _ og -)"
    ensure_conf
    printf 'dns_desec_token = %s\n' "$TOKEN" > "$INI.tmp" && chmod 0600 "$INI.tmp" && mv "$INI.tmp" "$INI" || fail "Kunne ikke gemme tokenet"
    say "Tokenet er gemt i $INI (kun root kan læse det)."
    ;;
set-target)
    ZONE=${1:-}; SUB=${2:-scada-acme}
    is_host "$ZONE" || fail "Ugyldig zone (fx mitnavn.dedyn.io)"
    one_line "$SUB" && printf '%s' "$SUB" | grep -Eq '^[a-z0-9]([a-z0-9-]{0,60}[a-z0-9])?$' || fail "Ugyldigt navn (ét led, fx scada-acme)"
    ensure_conf
    printf 'DESEC_ZONE=%s\nDESEC_SUB=%s\n' "$ZONE" "$SUB" > "$TARGET.tmp" && chmod 0600 "$TARGET.tmp" && mv "$TARGET.tmp" "$TARGET" || fail "Kunne ikke gemme"
    say "Gemt. CNAME-posten hos one.com skal pege på: $SUB.$ZONE"
    ;;
issue)
    HOST=${1:-}; EMAIL=${2:-}
    [ $# -ge 2 ] && shift 2
    DRY=0; FORCE=0; METHOD=dns
    while [ $# -gt 0 ]; do
        case "$1" in
            --dry-run) DRY=1 ;;
            --force) FORCE=1 ;;
            --method) shift; METHOD=${1:-}; case "$METHOD" in dns|http) ;; *) fail "Ukendt metode (dns eller http)" ;; esac ;;
            *) fail "Ukendt valg: $1" ;;
        esac
        shift
    done
    is_host "$HOST" || fail "Ugyldigt hostnavn (fx scada.laces.dk)"
    one_line "$EMAIL" && printf '%s' "$EMAIL" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9._+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' || fail "Ugyldig e-mailadresse"
    if [ "$METHOD" = dns ]; then
        [ -f "$INI" ] || fail "Intet deSEC-token — kør først: hypervision-letsencrypt set-token"
        [ -f "$TARGET" ] || fail "Ingen deSEC-zone — kør først: hypervision-letsencrypt set-target <zone>"
        [ -x "$AUTH_HOOK" ] || fail "DNS-hooken mangler eller er ikke kørbar ($AUTH_HOOK) — installér pakken igen"
    else
        [ -d "$WEBROOT" ] || fail "Webroot $WEBROOT mangler — installér pakken igen"
    fi
    [ -x "$HOOK" ] || fail "Hooken mangler eller er ikke kørbar ($HOOK) — installér pakken igen"
    if [ "$DRY" = 0 ] && [ ! -f "$TLSDIR/fullchain.pem" ]; then
        fail "nginx/TLS er ikke sat op (ingen $TLSDIR/fullchain.pem) — kør install.sh med --with-nginx <hostnavn> <ip> først"
    fi
    if [ "$METHOD" = dns ]; then
        set -- certonly --non-interactive --agree-tos --no-eff-email -m "$EMAIL" \
            --manual --preferred-challenges dns --manual-auth-hook "$AUTH_HOOK auth" --manual-cleanup-hook "$AUTH_HOOK cleanup" \
            --cert-name "$CERTNAME" -d "$HOST" --deploy-hook "$HOOK"
    else
        set -- certonly --non-interactive --agree-tos --no-eff-email -m "$EMAIL" \
            --webroot -w "$WEBROOT" --cert-name "$CERTNAME" -d "$HOST" --deploy-hook "$HOOK"
    fi
    [ "$DRY" = 1 ] && set -- "$@" --dry-run
    [ "$FORCE" = 1 ] && set -- "$@" --force-renewal
    if [ "$DRY" = 1 ]; then say "== Prøveudstedelse mod Let's Encrypts STAGING (intet gemmes, nginx røres ikke)"; else say "== Udsteder certifikat til $HOST"; fi
    $CERTBOT "$@" || fail "certbot fejlede. Se /var/log/letsencrypt/letsencrypt.log. Det nuværende certifikat er urørt, medmindre hooken nåede at installere et nyt — kør: hypervision-letsencrypt status"
    if [ "$DRY" = 1 ]; then say "Prøven lykkedes. Kør nu det samme uden --dry-run."; else sh "$HOOK" info; say "Færdig. Tjek System › Status i SCADA-siden."; fi
    ;;
status)
    sh "$HOOK" info
    $CERTBOT certificates 2>&1 || true
    ;;
renew-test)
    $CERTBOT renew --dry-run
    ;;
*)
    say "Brug: hypervision-letsencrypt install | set-token | set-target <zone> [navn] | issue <hostnavn> <e-mail> [--dry-run] [--force] | status | renew-test" >&2
    exit 2
    ;;
esac
