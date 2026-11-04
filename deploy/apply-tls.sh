#!/bin/sh
# Certifikat fra System › Certifikater. Køres som ROOT af systemd (hypervisionplc-scada-tls.service, udløst af .path-enheden når
# tls.request findes) — aldrig direkte af tjenesten.
#
# Anmodningen er én linje "<id> <handling>":
#   install              installér parret i <data>/config/tls-pending/{fullchain,privkey}.pem
#   restore-prev         gendan det forrige certifikat (.prev)
#   restore-selfsigned   gendan det selvsignerede certifikat (.selfsigned)
# Selve installationen sker af cert-deploy.sh (kontrol af parret, .prev, nginx -t, gendannelse ved fejl — ingen lockout).
# Resultatet skrives til <state>/tls-apply.json: {"id","ok","message","ts"}.
#
# SIKKERHED: tjenesten (brugeren 'scada') ejer <data>/config. Derfor
#   * flyttes anmodning og par (mv) ind i rootens egen mappe (0700) før de læses, og symlinks/ikke-almindelige filer afvises;
#   * id og handling valideres med faste mønstre; filerne skal være PEM og højst 64 KB;
#   * det er cert-deploy.sh, der kontrollerer, at nøgle og certifikat passer sammen, før noget røres.
#
# Til test kan kommandoer og mapper overstyres: DATA, STATE, PRIV, TLSDIR, HOOK.
set -u
set -f
umask 077
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

DATA=${DATA:-/var/lib/hypervisionplc-scada}
W=${STATE:-/var/lib/hypervisionplc-scada-net}
PRIV=${PRIV:-/var/lib/hypervisionplc-scada-tls}
TLSDIR=${TLSDIR:-/etc/hypervisionplc-scada/tls}
HOOK=${HOOK:-/usr/local/lib/hypervisionplc-scada/cert-deploy.sh}
REQ=$DATA/config/tls.request
PENDING=$DATA/config/tls-pending
LOG=$W/tls-apply.log
MAX=65536
NOFOLLOW=""
dd if=/dev/null of=/dev/null iflag=nofollow 2>/dev/null && NOFOLLOW=iflag=nofollow   # GNU dd (Pi); uden den beskytter root-ejerskabet alene

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }
clean() { printf '%s' "$1" | tr '\n' ' ' | tr -cd ' -~' | tr -d '"\\' | cut -c1-280; }
ID=""
result() {   # $1 = true/false, $2 = besked
    printf '{"id":"%s","ok":%s,"message":"%s","ts":%s}\n' "$ID" "$1" "$(clean "$2")" "$(date +%s)" > "$W/tls-apply.json.tmp"
    chmod 0644 "$W/tls-apply.json.tmp"
    mv -f "$W/tls-apply.json.tmp" "$W/tls-apply.json"
    log "$ID: ok=$1 $(clean "$2")"
}

mkdir -p "$W" "$PRIV"
chmod 0700 "$PRIV"

[ -e "$REQ" ] || [ -L "$REQ" ] || exit 0
if [ -L "$REQ" ]; then rm -f "$REQ"; log "afvist: anmodningen var et symlink"; exit 0; fi
rm -rf "$PRIV/req" "$PRIV/pending" "$PRIV/in" "$PRIV/src"
mv -f "$REQ" "$PRIV/req" 2>/dev/null || { log "afvist: kunne ikke flytte anmodningen"; exit 0; }
if [ -L "$PRIV/req" ] || [ ! -f "$PRIV/req" ]; then rm -rf "$PRIV/req"; log "afvist: anmodningen var ikke en almindelig fil"; exit 0; fi

read -r ID ACTION REST < "$PRIV/req" || true
rm -f "$PRIV/req"
if ! printf '%s' "${ID:-}" | grep -Eqx '[0-9a-f]{8}' || [ -n "${REST:-}" ]; then
    ID=""; log "afvist: ugyldig anmodning"; exit 0
fi

# Kopiér et par (fullchain.pem + privkey.pem) fra mappen $1 til $PRIV/in efter kontrol (almindelige filer, PEM, størrelse)
take_pair() {
    mkdir "$PRIV/in" || return 1
    for f in fullchain.pem privkey.pem; do
        src=$1/$f
        if [ -L "$src" ] || [ ! -f "$src" ]; then say_err="$f mangler eller er ikke en almindelig fil"; return 1; fi
        if [ "$(stat -c %h -- "$src")" != 1 ]; then say_err="$f er et hardlink"; return 1; fi
        size=$(wc -c < "$src")
        if [ "$size" -gt "$MAX" ] || [ "$size" -eq 0 ]; then say_err="$f har en ugyldig størrelse"; return 1; fi
        dd if="$src" of="$PRIV/in/$f" bs="$MAX" count=1 $NOFOLLOW 2>/dev/null || { say_err="$f kunne ikke læses"; return 1; }
    done
    grep -q -- '-----BEGIN CERTIFICATE-----' "$PRIV/in/fullchain.pem" || { say_err="fullchain.pem er ikke et PEM-certifikat"; return 1; }
    grep -q -- '-----BEGIN .*PRIVATE KEY-----' "$PRIV/in/privkey.pem" || { say_err="privkey.pem er ikke en PEM-nøgle"; return 1; }
    return 0
}

say_err=""
case "$ACTION" in
    install)
        if [ -L "$PENDING" ] || [ ! -d "$PENDING" ]; then result false "Intet certifikat at installere"; exit 0; fi
        mv -f "$PENDING" "$PRIV/pending" 2>/dev/null || { result false "Kunne ikke overtage certifikatet"; exit 0; }
        if [ -L "$PRIV/pending" ] || [ ! -d "$PRIV/pending" ]; then rm -rf "$PRIV/pending"; result false "Ugyldig anmodning"; exit 0; fi
        # Tjenesten kan stadig holde en åben mappe-fd: fjern dens skriveret (ejer → root, 0700), før indholdet kontrolleres og læses
        if [ "$(id -u)" = 0 ]; then
            chown -R -P 0:0 "$PRIV/pending" || { rm -rf "$PRIV/pending"; result false "Kunne ikke overtage certifikatet"; exit 0; }
        fi
        chmod -R go-rwx "$PRIV/pending"
        take_pair "$PRIV/pending"; rc=$?
        rm -rf "$PRIV/pending"
        ;;
    restore-prev)
        if [ -f "$TLSDIR/fullchain.pem.prev" ] && [ -f "$TLSDIR/privkey.pem.prev" ]; then
            if mkdir "$PRIV/src" && cp "$TLSDIR/fullchain.pem.prev" "$PRIV/src/fullchain.pem" && cp "$TLSDIR/privkey.pem.prev" "$PRIV/src/privkey.pem"; then
                take_pair "$PRIV/src"; rc=$?
            else rc=1; say_err="Kunne ikke kopiere det gemte certifikat"; fi
            rm -rf "$PRIV/src"
        else rc=1; say_err="Der er intet forrige certifikat"; fi
        ;;
    restore-selfsigned)
        if [ -f "$TLSDIR/fullchain.pem.selfsigned" ] && [ -f "$TLSDIR/privkey.pem.selfsigned" ]; then
            if mkdir "$PRIV/src" && cp "$TLSDIR/fullchain.pem.selfsigned" "$PRIV/src/fullchain.pem" && cp "$TLSDIR/privkey.pem.selfsigned" "$PRIV/src/privkey.pem"; then
                take_pair "$PRIV/src"; rc=$?
            else rc=1; say_err="Kunne ikke kopiere det gemte certifikat"; fi
            rm -rf "$PRIV/src"
        else rc=1; say_err="Der er intet gemt selvsigneret certifikat"; fi
        ;;
    *)
        result false "Ukendt handling"; exit 0 ;;
esac

if [ "$rc" -ne 0 ]; then
    rm -rf "$PRIV/in"
    result false "${say_err:-Certifikatet kunne ikke overtages}"
    exit 0
fi

out=$(LINEAGE_ROOT="$PRIV" LINEAGE="$PRIV/in" RENEWED_LINEAGE="$PRIV/in" TLSDIR="$TLSDIR" STATE="$W" "$HOOK" 2>&1); rc=$?
rm -rf "$PRIV/in"
if [ "$rc" -eq 0 ]; then
    result true "$(printf '%s' "$out" | tail -n 1)"
else
    result false "$(printf '%s' "$out" | grep -E 'FEJL|ADVARSEL|gendannet' | tr '\n' ' ')"
fi
exit 0
