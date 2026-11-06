#!/bin/sh
# LLM-hjælperen (v3.37.0): installér en LLM-pakke, start/stop tjenesten eller fjern den — efter anmodning fra
# System › Hjælper. Køres som ROOT af systemd (hypervisionplc-scada-llm-apply.service, udløst af .path-enheden når
# <data>/llm/llm.request findes) — aldrig direkte af SCADA-tjenesten.
#
# Kopieres af install.sh til /usr/local/lib/hypervisionplc-scada/ — UDEN FOR programmappen, som en opdatering erstatter.
#
# SIKKERHED: SCADA-tjenesten (brugeren 'scada') ejer <data>/llm og kan lægge hvad som helst dér, også symlinks. Derfor
#   * anmodningen FLYTTES ind i rootens egen mappe $W, før den læses (symlinks og andet end filer afvises);
#   * tar-listen kontrolleres før udpakning: kun filer og mapper under scada-llm/, ingen absolutte stier eller '..';
#   * modelfilens SHA256 kontrolleres mod manifestet; kun kendte handlinger; tal (tråde, MB) valideres som tal;
#   * pakken KOPIERES til en root-ejet fil (SHA256 af præcis de skrevne bytes) — scada kan ikke ændre kopien;
#   * efter udpakning: kun almindelige filer og mapper, ingen hardlinks;
#   * en anmodning ældre end 30 minutter ignoreres (ryddelighed, ikke en sikkerhedskontrol: mtime styres af scada).
# Tjenesten (hypervisionplc-scada-llm.service) kører som brugeren 'scada-llm' med lav prioritet og hukommelsesloft.
#
# Til test kan kommandoer og mapper overstyres: SYSTEMCTL, DATA, STATE, OPT, ETC, UNITDIR, PY.
set -u
set -f
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

SYSTEMCTL=${SYSTEMCTL:-systemctl}
PY=${PY:-python3}
DATA=${DATA:-/var/lib/hypervisionplc-scada}
W=${STATE:-/var/lib/hypervisionplc-scada-net}
OPT=${OPT:-/opt/hypervisionplc-scada-llm}
ETC=${ETC:-/etc}
UNITDIR=${UNITDIR:-/etc/systemd/system}
UNIT=hypervisionplc-scada-llm.service
PORT=${LLM_PORT:-8091}
MAX_AGE=1800
REQ=$DATA/llm/llm.request
WORK=$W/llm.work
PKG=$W/llm.incoming.tar
LOG=$W/llm.log
STATUS=$W/llm.json

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

# status <state> <message> — llm.json læses af SCADA'en (System › Hjælper); manifestets model bevares fra installationen
status() {
    model="{}"; build=""
    [ -f "$OPT/current/manifest.json" ] && model=$("$PY" -c 'import json,sys; m=json.load(open(sys.argv[1])); print(json.dumps(m["model"]))' "$OPT/current/manifest.json" 2>/dev/null || echo "{}") \
        && build=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["llama_build"])' "$OPT/current/manifest.json" 2>/dev/null || echo "")
    [ -f "$OPT/current/manifest.json" ] || model="null"
    msg=$(printf '%s' "$2" | tr -d '"\\' | tr '\n' ' ' | cut -c1-300)
    printf '{"state":"%s","message":"%s","action":"%s","by":"%s","ts":%s,"model":%s,"llama_build":"%s"}\n' \
        "$1" "$msg" "$action" "$by" "$(date +%s)" "$model" "$build" > "$STATUS.tmp"
    chmod 0644 "$STATUS.tmp"
    mv -f "$STATUS.tmp" "$STATUS"
}

fail() { log "fejl ($action fra $by): $1"; status error "$1"; rm -f "$PKG"; exit 0; }

[ -e "$REQ" ] || [ -L "$REQ" ] || exit 0
mkdir -p "$W"
if [ -L "$REQ" ]; then
    rm -f "$REQ"; log "afvist: anmodningen var et symlink"; exit 0
fi
rm -rf "$WORK"
mv -f "$REQ" "$WORK" 2>/dev/null || { log "afvist: kunne ikke flytte anmodningen"; exit 0; }
if [ -L "$WORK" ] || [ ! -f "$WORK" ]; then
    rm -rf "$WORK"; log "afvist: anmodningen var ikke en almindelig fil"; exit 0
fi

now=$(date +%s)
mtime=$(stat -c %Y "$WORK" 2>/dev/null || echo 0)
field() { sed -n "s/^$1=//p" "$WORK" | head -n 1; }
action=$(field action | tr -cd 'a-z')
by=$(field by | tr -cd 'A-Za-z0-9._-' | cut -c1-40)
sha=$(field sha256 | tr -cd '0-9a-f')
threads=$(field threads | tr -cd '0-9')
mem_mb=$(field mem_mb | tr -cd '0-9')
[ -n "$by" ] || by=ukendt
rm -f "$WORK"

if [ $((now - mtime)) -gt "$MAX_AGE" ]; then
    log "afvist: anmodningen fra $by var for gammel"; exit 0
fi
case "$action" in
    install|start|stop|remove) ;;
    *) log "afvist: ukendt handling fra $by"; exit 0 ;;
esac
log "$action anmodet af $by"

# Tråde og hukommelse fra hardwareprofilen: altid tal i et fornuftigt interval
limits() {
    case "$threads" in ''|*[!0-9]*) threads=2 ;; esac
    [ "$threads" -ge 1 ] && [ "$threads" -le 64 ] || threads=2
    case "$mem_mb" in ''|*[!0-9]*) mem_mb=4500 ;; esac
    [ "$mem_mb" -ge 1000 ] && [ "$mem_mb" -le 200000 ] || mem_mb=4500
    ctx=$("$PY" -c 'import json,sys; c=int(json.load(open(sys.argv[1])).get("ctx",8192)); print(c if 512<=c<=131072 else 8192)' "$OPT/current/manifest.json" 2>/dev/null || echo 8192)
    mfile=$("$PY" -c 'import json,re,sys; f=json.load(open(sys.argv[1]))["model"]["file"]; assert re.fullmatch(r"[A-Za-z0-9._-]{1,120}\.gguf", f); print(f)' "$OPT/current/manifest.json" 2>/dev/null) \
        || fail "manifestet for den installerede model kan ikke læses"
    printf 'LLM_MODEL=%s\nLLM_THREADS=%s\nLLM_CTX=%s\nLLM_PORT=%s\n' "$OPT/current/model/$mfile" "$threads" "$ctx" "$PORT" > "$ETC/hypervisionplc-scada-llm.env.tmp"
    chmod 0644 "$ETC/hypervisionplc-scada-llm.env.tmp"
    mv -f "$ETC/hypervisionplc-scada-llm.env.tmp" "$ETC/hypervisionplc-scada-llm.env"
    mkdir -p "$UNITDIR/$UNIT.d"
    printf '[Service]\n# Fra hardwareprofilen (System › Hjælper)\nMemoryMax=%sM\n' "$mem_mb" > "$UNITDIR/$UNIT.d/limits.conf"
    $SYSTEMCTL daemon-reload
}

# Systembiblioteker, som llama-server kræver (fx libgomp1/OpenMP — install.sh installerer det): en klar besked i stedet
# for en tjeneste, der bare genstarter igen og igen
deps() {
    missing=$(LD_LIBRARY_PATH="$OPT/current/llama" ldd "$OPT/current/llama/llama-server" 2>/dev/null | awk '/not found/ { print $1 }' | tr '
' ' ')
    [ -z "$missing" ] || fail "systembiblioteker mangler: $missing— installér dem (fx sudo apt install libgomp1) og tryk Slå til igen"
}

start() {
    command -v ldd >/dev/null 2>&1 && [ -z "${SKIP_DEPS:-}" ] && deps
    limits
    $SYSTEMCTL enable "$UNIT" >/dev/null 2>&1
    $SYSTEMCTL restart "$UNIT" || fail "tjenesten kunne ikke startes (se journalctl -u $UNIT)"
    status running "kører med $threads tråde og højst $mem_mb MB"
    log "startet ($threads tråde, $mem_mb MB)"
}

stop() {
    $SYSTEMCTL disable --now "$UNIT" >/dev/null 2>&1 || true
}

case "$action" in
stop)
    stop; status stopped "slået fra — bruger ingen CPU eller RAM"; log "stoppet"; exit 0 ;;
remove)
    stop
    rm -rf "$OPT"
    rm -f "$ETC/hypervisionplc-scada-llm.env" "$UNITDIR/$UNIT.d/limits.conf"
    status removed "fjernet"; log "fjernet"; exit 0 ;;
start)
    [ -f "$OPT/current/manifest.json" ] || fail "ingen LLM-pakke er installeret"
    start; exit 0 ;;
esac

# ---- install
[ ${#sha} -eq 64 ] || fail "anmodningen mangler pakkens SHA256"
SRCPKG=$DATA/llm/incoming.tar
if [ -L "$SRCPKG" ] || [ ! -f "$SRCPKG" ]; then fail "LLM-pakken mangler eller er ikke en almindelig fil"; fi
# Plads: rootens kopi + udpakket + den gamle installation, indtil den nye virker (ca. 3x pakken)
size=$(stat -c %s "$SRCPKG" 2>/dev/null || echo 0)
mkdir -p "$OPT"
need_kb=$((size / 1024 * 2 + 1048576))
free_kb=$(df -Pk "$OPT" 2>/dev/null | awk 'NR==2 { print $4 }')
case "$free_kb" in ''|*[!0-9]*) free_kb=0 ;; esac
[ "$free_kb" -ge "$need_kb" ] || fail "for lidt diskplads til installationen (kræver ca. $((need_kb / 1048576 + 1)) GB fri ud over pakken)"
status installing "kontrollerer LLM-pakken"
# Pakken ejes af scada (også efter en flytning: samme inode, og scada kan stadig skrive i den). Derfor laver root sin EGEN
# kopi og beregner SHA256 af præcis de bytes, der skrives i kopien — alt videre arbejde sker kun på kopien.
# Først flyttes navnet ind i rootens mappe (så kan det ikke byttes ud med et symlink), dér tjekkes det, og så kopieres der.
SRC2=$W/llm.src.tar
rm -f "$PKG" "$SRC2"
mv -f "$SRCPKG" "$SRC2" || fail "LLM-pakken kunne ikke flyttes"
rm -f "$DATA/llm/staged.json"
if [ -L "$SRC2" ] || [ ! -f "$SRC2" ]; then rm -f "$SRC2"; fail "LLM-pakken er ikke en almindelig fil"; fi
got=$( (umask 077; cat "$SRC2" | tee "$PKG" | sha256sum) | cut -c1-64 )
rm -f "$SRC2"
if [ -L "$PKG" ] || [ ! -f "$PKG" ]; then fail "LLM-pakken kunne ikke kopieres"; fi
[ "$got" = "$sha" ] || fail "LLM-pakkens SHA256 passer ikke (ændret efter upload?)"

# Kun filer og mapper under scada-llm/ — ingen absolutte stier, ingen '..', ingen links eller enheder
# Listerne SKAL kunne læses — en fejlet listning må aldrig se ud som "intet usikkert fundet"
LIST=$W/llm.list
tar --force-local -tvf "$PKG" > "$LIST" 2>/dev/null && [ -s "$LIST" ] || fail "LLM-pakken kan ikke læses som tar"
bad=$(awk '{ t=substr($1,1,1); if (t!="-" && t!="d") { print "type:" $0; exit } }' "$LIST")
[ -z "$bad" ] || fail "LLM-pakken indeholder andet end filer og mapper"
tar --force-local -tf "$PKG" > "$LIST" 2>/dev/null && [ -s "$LIST" ] || fail "LLM-pakken kan ikke læses som tar"
bad=$(awk '!/^scada-llm(\/|$)/ || /(^|\/)\.\.(\/|$)/ || /^\// { print; exit }' "$LIST")
rm -f "$LIST"
[ -z "$bad" ] || fail "LLM-pakken indeholder en usikker sti"

TMP=$OPT/.installing
rm -rf "$TMP"
mkdir -p "$TMP"
tar --force-local -xf "$PKG" -C "$TMP" --no-same-owner --no-same-permissions || { rm -rf "$TMP"; fail "LLM-pakken kunne ikke pakkes ud"; }
rm -f "$PKG"
# Efter udpakning: KUN almindelige filer og mapper, ingen hardlinks (dobbelttjek af listen ovenfor)
odd=$(find "$TMP" \( ! -type f ! -type d \) -print -quit 2>/dev/null; find "$TMP" -type f -links +1 -print -quit 2>/dev/null)
[ -z "$odd" ] || { rm -rf "$TMP"; fail "LLM-pakken indeholdt links eller specialfiler"; }
M=$TMP/scada-llm/manifest.json
info=$("$PY" - "$M" <<'EOF'
import json, re, sys
m = json.load(open(sys.argv[1]))
mo = m["model"]
assert m.get("format") == "hv-llm" and int(m["format_version"]) == 1
assert re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,60}", mo["id"]) and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,60}", m["llama_build"])
assert re.fullmatch(r"[A-Za-z0-9._-]{1,120}\.gguf", mo["file"]) and re.fullmatch(r"[0-9a-f]{64}", mo["sha256"])
print(f'{m["llama_build"]}-{mo["id"]} {mo["file"]} {mo["sha256"]}')
EOF
) || { rm -rf "$TMP"; fail "manifest.json i LLM-pakken er ugyldigt"; }
id=$(echo "$info" | cut -d' ' -f1)
mfile=$(echo "$info" | cut -d' ' -f2)
msha=$(echo "$info" | cut -d' ' -f3)
status installing "kontrollerer modelfilen"
got=$(sha256sum < "$TMP/scada-llm/model/$mfile" 2>/dev/null | cut -c1-64)
[ "$got" = "$msha" ] || { rm -rf "$TMP"; fail "modelfilens SHA256 passer ikke med manifestet"; }
[ -f "$TMP/scada-llm/llama/llama-server" ] || { rm -rf "$TMP"; fail "llama-server mangler i pakken"; }

stop
rm -rf "${OPT:?}/$id"
mv "$TMP/scada-llm" "$OPT/$id" || { rm -rf "$TMP"; fail "installationen kunne ikke flyttes på plads"; }
rm -rf "$TMP"
chown -R root:root "$OPT/$id"
find "$OPT/$id" -type d -exec chmod 0755 {} +
find "$OPT/$id" -type f -exec chmod 0644 {} +
chmod 0755 "$OPT/$id/llama/llama-server"
find "$OPT/$id/llama" -maxdepth 1 -type f -name 'llama-*' -exec chmod 0755 {} +
rm -rf "$OPT/current.new"
ln -sfn "$OPT/$id" "$OPT/current.new" 2>/dev/null || cp -R "$OPT/$id" "$OPT/current.new"   # kopi kun hvor symlinks mangler (test på Windows)
rm -rf "$OPT/current" 2>/dev/null; mv -f "$OPT/current.new" "$OPT/current"
# Ældre installationer fylder GB — kun den aktuelle bevares
set +f
for d in "$OPT"/*; do
    [ -d "$d" ] && [ ! -L "$d" ] && [ "$d" != "$OPT/$id" ] && [ "$d" != "$OPT/current" ] && rm -rf "$d"
done
set -f
log "installeret: $id"
start
exit 0
