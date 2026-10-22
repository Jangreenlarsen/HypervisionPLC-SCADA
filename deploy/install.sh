#!/bin/sh
# Installér/opdatér HypervisionPLC SCADA på Debian / Raspberry Pi OS. Køres som root
# fra roden af en udpakket kopi af repoet:
#   sh deploy/install.sh [--with-mock-plc] [--with-nginx <hostnavn> [ip]] [--update]
# --update: bruges af OTA-opdateringen — springer apt og pip-opgradering over (virker uden internet når alt er installeret).
# --with-nginx: nginx med TLS foran SCADA (selvsigneret certifikat hvis intet findes) og Secure-cookie.
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
UPDATE=0
NGINX_HOST=""
NGINX_IP=""
while [ $# -gt 0 ]; do
    case "$1" in
        --with-mock-plc) WITH_MOCK=1 ;;
        --update) UPDATE=1 ;;
        --with-nginx) NGINX_HOST=${2:?--with-nginx kræver et hostnavn}; shift
                      case "${2:-}" in --*|"") ;; *) NGINX_IP=$2; shift ;; esac ;;
        *) echo "Ukendt parameter: $1" >&2; exit 2 ;;
    esac
    shift
done

if [ "$(id -u)" -ne 0 ]; then
    echo "Skal køres som root" >&2
    exit 1
fi

echo "== Pakker"
if [ "$UPDATE" -eq 1 ] && python3 -c 'import venv, ensurepip' 2>/dev/null; then
    echo "(--update: apt springes over)"
else
    apt-get update -qq
    apt-get install -y -qq python3 python3-venv >/dev/null
fi

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
[ "$UPDATE" -eq 1 ] || "$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q --disable-pip-version-check -r "$APP/backend/requirements.txt"

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

if [ -n "$NGINX_HOST" ]; then
    echo "== nginx + TLS ($NGINX_HOST${NGINX_IP:+, $NGINX_IP})"
    apt-get install -y -qq nginx openssl >/dev/null
    sh "$SRC/deploy/tls-selfsigned.sh" "$NGINX_HOST" "$NGINX_IP"
    install -m 0644 "$SRC/deploy/nginx-hypervisionplc-scada.conf" /etc/nginx/sites-available/hypervisionplc-scada
    ln -sf /etc/nginx/sites-available/hypervisionplc-scada /etc/nginx/sites-enabled/hypervisionplc-scada
    rm -f /etc/nginx/sites-enabled/default
    nginx -t
    systemctl enable -q nginx
    systemctl reload nginx 2>/dev/null || systemctl restart nginx
    # Bag TLS må session-cookien kun sendes over HTTPS
    if grep -q '^SCADA_COOKIE_SECURE=' "$ENVFILE"; then
        sed -i 's/^SCADA_COOKIE_SECURE=.*/SCADA_COOKIE_SECURE=true/' "$ENVFILE"
    else
        echo "SCADA_COOKIE_SECURE=true" >> "$ENVFILE"
    fi
fi

echo "== OTA-opdatering"
# Hjælperen ligger UDEN FOR $APP (den erstattes ved hver installation) og udskiftes ved at lægge en ny fil ved siden af
install -d -m 0755 /usr/local/lib/hypervisionplc-scada
install -m 0755 "$SRC/deploy/apply-update.sh" /usr/local/lib/hypervisionplc-scada/apply-update.sh.new
mv /usr/local/lib/hypervisionplc-scada/apply-update.sh.new /usr/local/lib/hypervisionplc-scada/apply-update.sh
install -m 0644 "$SRC/deploy/hypervisionplc-scada-update.service" "$SRC/deploy/hypervisionplc-scada-update.path" /etc/systemd/system/
install -d -o scada -g scada -m 0750 "$DATA/updates"
: > "$DATA/updates/enabled"

echo "== Netværksopsætning via web (System › Konfiguration)"
install -m 0755 "$SRC/deploy/apply-config.sh" /usr/local/lib/hypervisionplc-scada/apply-config.sh.new
mv /usr/local/lib/hypervisionplc-scada/apply-config.sh.new /usr/local/lib/hypervisionplc-scada/apply-config.sh
install -m 0644 "$SRC/deploy/hypervisionplc-scada-config.service" "$SRC/deploy/hypervisionplc-scada-config.path" /etc/systemd/system/
install -d -o scada -g scada -m 0750 "$DATA/config"
# Status og log ejes af ROOT (tjenesten kun læser) — så kan tjenesten ikke narre root-hjælperen med symlinks i sin egen mappe
install -d -o root -g root -m 0755 /var/lib/hypervisionplc-scada-net
# Kun hvis NetworkManager findes (Raspberry Pi OS Bookworm) — ellers er netværk ikke ændrbart fra web
if command -v nmcli >/dev/null 2>&1; then : > /var/lib/hypervisionplc-scada-net/enabled; else rm -f /var/lib/hypervisionplc-scada-net/enabled; fi

echo "== systemd"
install -m 0644 "$SRC/deploy/hypervisionplc-scada.service" /etc/systemd/system/
if [ "$WITH_MOCK" -eq 1 ]; then
    install -m 0644 "$SRC/deploy/hypervisionplc-mock-plc.service" /etc/systemd/system/
fi
systemctl daemon-reload
systemctl enable -q hypervisionplc-scada
systemctl restart hypervisionplc-scada
systemctl enable -q hypervisionplc-scada-update.path
systemctl restart hypervisionplc-scada-update.path
systemctl enable -q hypervisionplc-scada-config.path
systemctl restart hypervisionplc-scada-config.path
if [ "$WITH_MOCK" -eq 1 ]; then
    systemctl enable -q hypervisionplc-mock-plc
    systemctl restart hypervisionplc-mock-plc
elif systemctl is-active --quiet hypervisionplc-mock-plc 2>/dev/null; then
    systemctl restart hypervisionplc-mock-plc   # kører fra den kode der lige er erstattet
fi

sleep 2
systemctl --no-pager --lines=5 status hypervisionplc-scada || true
echo "== Færdig. Version: $(cat "$APP/version.json" | tr -d '\n ')"
