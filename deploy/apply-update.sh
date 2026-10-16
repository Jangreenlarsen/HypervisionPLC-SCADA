#!/bin/sh
# Installér en opdateringspakke som SCADA-tjenesten har klargjort (OTA). Køres som ROOT af systemd
# (hypervisionplc-scada-update.service, udløst af .path-enheden når apply.request findes) — aldrig direkte af tjenesten.
#
# Kopieres af install.sh til /usr/local/lib/hypervisionplc-scada/ — UDEN FOR programmappen, som installationen erstatter.
#
# Trin: læs og slet anmodningen → kopiér pakken til en root-ejet arbejdsmappe → kontrollér kontrolsummen → pak ud →
# gem forrige kode → kør install.sh --update → tjek /api/health (skal melde den nye version) → ved fejl: rul tilbage.
# Status: <data>/updates/status.json, log: <data>/updates/update.log.
set -u
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

APP=/opt/hypervisionplc-scada
DATA=/var/lib/hypervisionplc-scada
U=$DATA/updates
REQ=$U/apply.request
STATUS=$U/status.json
LOG=$U/update.log
ENVFILE=/etc/hypervisionplc-scada.env

[ -f "$REQ" ] || exit 0

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }
field() { sed -n "s/^$1=//p" "$REQ" | head -n 1; }

# Anmodningen slettes straks — ellers udløser .path-enheden os igen og igen
SHA=$(field SHA256); BY=$(field BY); TO=$(field VERSION); BUILD=$(field BUILD)
rm -f "$REQ"
FROM=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$APP/version.json" 2>/dev/null | head -n 1)
FROM=${FROM:-ukendt}
FROMB=$(sed -n 's/.*"build": *"\([^"]*\)".*/\1/p' "$APP/version.json" 2>/dev/null | head -n 1)
FROMB=${FROMB:-?}
: > "$LOG"

# Kun tegn der er sikre i JSON (beskederne er vores egne konstanter; versionerne er tjekket af tjenesten)
status() {
    printf '{"state":"%s","message":"%s","from":"%s build %s","to":"%s build %s","by":"%s","ts":%s}\n' "$1" "$2" "$FROM" "$FROMB" "${TO:-?}" "${BUILD:-?}" "${BY:-ukendt}" "$(date +%s)" > "$STATUS.tmp"
    chmod 0644 "$STATUS.tmp"
    mv "$STATUS.tmp" "$STATUS"
}

WORK=""
cleanup() { [ -n "$WORK" ] && rm -rf "$WORK"; }
trap cleanup EXIT

fail() {
    log "FEJL: $1"
    status failed "$1"
    exit 1
}

# 0 hvis tjenesten svarer på /api/health og melder den forventede version og build
health() {
    PORT=$(sed -n 's/^SCADA_PORT=//p' "$ENVFILE" 2>/dev/null | head -n 1)
    "$APP/venv/bin/python" - "${PORT:-8000}" "$1" "$2" <<'PY'
import json, sys, urllib.request
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[1]}/api/health", timeout=3) as r:
        data = json.load(r)
except Exception:
    sys.exit(1)
sys.exit(0 if data.get("status") == "ok" and data.get("version") == sys.argv[2] and data.get("build") == sys.argv[3] else 1)
PY
}

wait_health() { # forventet version, forventet build, højst så mange sekunder
    i=0
    while [ "$i" -lt "$3" ]; do
        health "$1" "$2" && return 0
        sleep 2
        i=$((i + 2))
    done
    return 1
}

rollback() {
    log "Ruller tilbage til $FROM"
    [ -d "$APP.prev/backend" ] || return 1
    systemctl stop hypervisionplc-scada 2>/dev/null
    rm -rf "$APP/backend" "$APP/frontend"
    cp -a "$APP.prev/backend" "$APP/backend"
    [ -d "$APP.prev/frontend" ] && cp -a "$APP.prev/frontend" "$APP/frontend"
    cp -a "$APP.prev/version.json" "$APP/version.json"
    systemctl restart hypervisionplc-scada
    wait_health "$FROM" "$FROMB" 60
}

log "Opdatering $FROM -> $TO build $BUILD anmodet af ${BY:-ukendt}"
status applying "Forbereder opdateringen"

case "$SHA" in *[!0-9a-f]*|"") fail "Anmodningen mangler en gyldig kontrolsum" ;; esac
[ "${#SHA}" -eq 64 ] || fail "Anmodningen mangler en gyldig kontrolsum"
[ -f "$U/staged.tar" ] || fail "Den klargjorte pakke findes ikke"

WORK=$(mktemp -d /var/tmp/hv-update.XXXXXX) || fail "Kan ikke oprette en arbejdsmappe"
cp "$U/staged.tar" "$WORK/pkg.tar" || fail "Kan ikke kopiere pakken"
GOT=$(sha256sum "$WORK/pkg.tar" | cut -d' ' -f1)
[ "$GOT" = "$SHA" ] || fail "Pakkens kontrolsum svarer ikke til den godkendte"
tar -xf "$WORK/pkg.tar" -C "$WORK" --no-same-owner --no-same-permissions >> "$LOG" 2>&1 || fail "Pakken kunne ikke pakkes ud"
[ -f "$WORK/scada/deploy/install.sh" ] || fail "Pakken mangler deploy/install.sh"
NEWV=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$WORK/scada/version.json" | head -n 1)
[ "$NEWV" = "$TO" ] || fail "Pakkens version ($NEWV) er ikke den godkendte ($TO)"

status applying "Gemmer forrige version"
rm -rf "$APP.prev"
mkdir -p "$APP.prev"
cp -a "$APP/backend" "$APP.prev/backend" || fail "Kan ikke gemme forrige version"
[ -d "$APP/frontend" ] && cp -a "$APP/frontend" "$APP.prev/frontend"
cp -a "$APP/version.json" "$APP.prev/version.json"

status applying "Installerer"
log "Kører install.sh --update"
if ! sh "$WORK/scada/deploy/install.sh" --update >> "$LOG" 2>&1; then
    log "install.sh fejlede"
    if rollback; then
        status rolled_back "Installationen fejlede - forrige version er gendannet"
    else
        status failed "Installationen fejlede, og tilbagerulningen lykkedes ikke - kontrollér serveren"
    fi
    exit 1
fi

status applying "Tjekker at den nye version svarer"
if wait_health "$TO" "$BUILD" 90; then
    log "Ny version svarer: $TO"
    rm -f "$U/staged.tar" "$U/staged.json"
    status done "Opdateret til $TO build $BUILD"
    exit 0
fi

log "Den nye version svarede ikke inden for tidsgrænsen"
if rollback; then
    status rolled_back "Den nye version svarede ikke - forrige version er gendannet"
else
    status failed "Den nye version svarede ikke, og tilbagerulningen lykkedes ikke - kontrollér serveren"
fi
exit 1
