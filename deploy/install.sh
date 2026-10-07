#!/bin/sh
# Installér/opdatér HypervisionPLC SCADA på Debian / Raspberry Pi OS. Køres som root
# fra roden af en udpakket kopi af repoet:  sh deploy/install.sh [--with-mock-plc]
#
# - kode:  /opt/hypervisionplc-scada (erstattes ved hver installation)
# - data:  /var/lib/hypervisionplc-scada (bevares: database + secrets.json)
# - konfig: /etc/hypervisionplc-scada.env (oprettes kun hvis den ikke findes)
set -eu
export PATH="/usr/local/sbin:/usr/sbin:/sbin:$PATH"

APP=/opt/hypervisionplc-scada
DATA=/var/lib/hypervisionplc-scada
ENVFILE=/etc/hypervisionplc-scada.env
SRC=$(cd "$(dirname "$0")/.." && pwd)
WITH_MOCK=0
[ "${1:-}" = "--with-mock-plc" ] && WITH_MOCK=1

if [ "$(id -u)" -ne 0 ]; then
    echo "Skal køres som root" >&2
    exit 1
fi

echo "== Pakker"
apt-get update -qq
apt-get install -y -qq python3 python3-venv >/dev/null

echo "== Bruger og mapper"
id scada >/dev/null 2>&1 || useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin scada
install -d -o scada -g scada -m 0750 "$DATA"

echo "== Kode"
rm -rf "$APP.new"
mkdir -p "$APP.new"
cp -r "$SRC/backend" "$SRC/version.json" "$SRC/LICENSE" "$APP.new/"
[ -d "$SRC/frontend/dist" ] && mkdir -p "$APP.new/frontend" && cp -r "$SRC/frontend/dist" "$APP.new/frontend/"
rm -rf "$APP.new/backend/.venv" "$APP.new/backend/tests" "$APP.new/backend/.pytest_cache"
find "$APP.new" -name __pycache__ -type d -prune -exec rm -rf {} +
if [ -d "$APP/venv" ]; then mv "$APP/venv" "$APP.new/venv"; fi
rm -rf "$APP"
mv "$APP.new" "$APP"
chown -R root:root "$APP"

echo "== Python-miljø"
[ -d "$APP/venv" ] || python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q -r "$APP/backend/requirements.txt"

echo "== Konfiguration"
if [ ! -f "$ENVFILE" ]; then
    cat > "$ENVFILE" <<EOF
# HypervisionPLC SCADA — se backend/app/config.py
SCADA_DATA_DIR=$DATA
SCADA_HOST=127.0.0.1
SCADA_PORT=8000
LOG_LEVEL=INFO
EOF
    chmod 0640 "$ENVFILE"
    chown root:scada "$ENVFILE"
fi

echo "== systemd"
install -m 0644 "$SRC/deploy/hypervisionplc-scada.service" /etc/systemd/system/
if [ "$WITH_MOCK" -eq 1 ]; then
    install -m 0644 "$SRC/deploy/hypervisionplc-mock-plc.service" /etc/systemd/system/
fi
systemctl daemon-reload
systemctl enable -q hypervisionplc-scada
systemctl restart hypervisionplc-scada
if [ "$WITH_MOCK" -eq 1 ]; then
    systemctl enable -q hypervisionplc-mock-plc
    systemctl restart hypervisionplc-mock-plc
fi

sleep 2
systemctl --no-pager --lines=5 status hypervisionplc-scada || true
echo "== Færdig. Version: $(cat "$APP/version.json" | tr -d '\n ')"
