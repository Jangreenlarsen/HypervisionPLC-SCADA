#!/bin/sh
# Installér/opdatér HypervisionPLC SCADA på Debian / Raspberry Pi OS. Køres som root
# fra roden af en udpakket kopi af repoet:
#   sh deploy/install.sh [--with-mock-plc] [--with-nginx <hostnavn> [ip]] [--update] [--hw <profil>]
# --hw: hardwareprofil (pi4, lille, pi5, vm-8, vm-16, vm-32) — afgør om LLM-hjælperen kan slås til. Uden: foreslås ud fra maskinen
#       og kan rettes under System › Hjælper.
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
HW=""
while [ $# -gt 0 ]; do
    case "$1" in
        --with-mock-plc) WITH_MOCK=1 ;;
        --update) UPDATE=1 ;;
        --with-nginx) NGINX_HOST=${2:?--with-nginx kræver et hostnavn}; shift
                      case "${2:-}" in --*|"") ;; *) NGINX_IP=$2; shift ;; esac ;;
        --hw) HW=${2:?--hw kræver en profil (pi4, lille, pi5, vm-8, vm-16, vm-32)}; shift
              case "$HW" in pi4|lille|pi5|vm-8|vm-16|vm-32) ;; *) echo "Ukendt hardwareprofil: $HW" >&2; exit 2 ;; esac ;;
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
    apt-get install -y -qq python3 python3-venv libgomp1 >/dev/null   # libgomp1: OpenMP til LLM-hjælperen (llama-server)
fi

# LLM-hjælperens llama-server kræver OpenMP (libgomp1). Ved OTA (--update) kun hvis den mangler, og uden at fejle offline
if [ "$UPDATE" -eq 1 ] && ! dpkg -s libgomp1 >/dev/null 2>&1; then
    apt-get install -y -qq libgomp1 >/dev/null 2>&1 || echo "BEMÆRK: libgomp1 mangler — LLM-hjælperen kræver 'sudo apt install libgomp1'" >&2
fi

echo "== Bruger og mapper"
id scada >/dev/null 2>&1 || useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin scada
install -d -o scada -g scada -m 0750 "$DATA"

echo "== Kode"
rm -rf "$APP.new"
mkdir -p "$APP.new"
cp -r "$SRC/backend" "$SRC/version.json" "$SRC/LICENSE" "$APP.new/"
[ -d "$SRC/frontend/dist" ] && mkdir -p "$APP.new/frontend" && cp -r "$SRC/frontend/dist" "$APP.new/frontend/"
# Manualens markdown: hjælperens viden (services/assist_knowledge.py) — selve manualen i UI'et ligger i dist
[ -d "$SRC/frontend/src/manual" ] && mkdir -p "$APP.new/frontend" && cp -r "$SRC/frontend/src/manual" "$APP.new/frontend/"
# LLM-kataloget (System › Hjælper: varianter og deres GitHub-udgivelser, services/llm_catalog.py)
[ -f "$SRC/deploy/llm-models.json" ] && cp "$SRC/deploy/llm-models.json" "$APP.new/"
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

echo "== Vedligeholdelse ved fuld disk (scada-maint)"
install -m 0755 "$SRC/deploy/scada-maint.sh" /usr/local/sbin/scada-maint
echo "== Værktøjskasse (scada-tool)"
install -m 0755 "$SRC/deploy/scada-tool.sh" /usr/local/sbin/scada-tool

echo "== Netværksopsætning via web (System › Konfiguration)"
install -m 0755 "$SRC/deploy/apply-config.sh" /usr/local/lib/hypervisionplc-scada/apply-config.sh.new
mv /usr/local/lib/hypervisionplc-scada/apply-config.sh.new /usr/local/lib/hypervisionplc-scada/apply-config.sh
install -m 0755 "$SRC/deploy/net-watchdog.sh" /usr/local/lib/hypervisionplc-scada/net-watchdog.sh.new
mv /usr/local/lib/hypervisionplc-scada/net-watchdog.sh.new /usr/local/lib/hypervisionplc-scada/net-watchdog.sh
install -m 0644 "$SRC/deploy/hypervisionplc-scada-config.service" "$SRC/deploy/hypervisionplc-scada-config.path" \
    "$SRC/deploy/hypervisionplc-scada-netwatch.service" "$SRC/deploy/hypervisionplc-scada-netwatch.timer" /etc/systemd/system/
install -d -o scada -g scada -m 0750 "$DATA/config"
# Status og log ejes af ROOT (tjenesten kun læser) — så kan tjenesten ikke narre root-hjælperen med symlinks i sin egen mappe
install -d -o root -g root -m 0755 /var/lib/hypervisionplc-scada-net
# Genstart af SCADA-tjenesten / maskinen fra web (System › Konfiguration › Genstart): samme mønster som netværk — anmodning i <data>/config, root-hjælper
install -m 0755 "$SRC/deploy/apply-power.sh" /usr/local/lib/hypervisionplc-scada/apply-power.sh.new
mv /usr/local/lib/hypervisionplc-scada/apply-power.sh.new /usr/local/lib/hypervisionplc-scada/apply-power.sh
install -m 0644 "$SRC/deploy/hypervisionplc-scada-power.service" "$SRC/deploy/hypervisionplc-scada-power.path" /etc/systemd/system/
: > /var/lib/hypervisionplc-scada-net/power-enabled
# NFS-shares til backup (System › Backup › Destinationer): samme mønster — ønsket liste i <data>/config, root-hjælper monterer under /mnt/hv-backup
install -m 0755 "$SRC/deploy/apply-backup-mounts.sh" /usr/local/lib/hypervisionplc-scada/apply-backup-mounts.sh.new
mv /usr/local/lib/hypervisionplc-scada/apply-backup-mounts.sh.new /usr/local/lib/hypervisionplc-scada/apply-backup-mounts.sh
install -m 0644 "$SRC/deploy/hypervisionplc-scada-backupmount.service" "$SRC/deploy/hypervisionplc-scada-backupmount.path" /etc/systemd/system/
command -v mount.nfs >/dev/null 2>&1 || { [ "$UPDATE" -eq 1 ] && echo "BEMÆRK: nfs-common mangler — NFS-backup virker først efter 'sudo apt install nfs-common'" >&2 || apt-get install -y -qq nfs-common >/dev/null || true; }
# Hvilket netværkssystem kører maskinen, og er der en brugbar DHCP-klient? (NetworkManager eller ifupdown; ingen af dem → netværk kan ikke ændres fra web)
# net-detect.sh skriver capabilities + markørfiler, og køres igen af DHCP-vagtens timer, så en senere "apt install dhcpcd-base" slår igennem af sig selv.
install -m 0755 "$SRC/deploy/net-detect.sh" /usr/local/lib/hypervisionplc-scada/net-detect.sh
/usr/local/lib/hypervisionplc-scada/net-detect.sh || true
# Strøm-/varmestatus (Raspberry Pi) til System › Status og alarmer — tjenesten må ikke selv åbne /dev/vcio
install -m 0755 "$SRC/deploy/power-info.sh" /usr/local/lib/hypervisionplc-scada/power-info.sh
/usr/local/lib/hypervisionplc-scada/power-info.sh || true
NETBACKEND=$(sed -n 's/^backend=//p' /var/lib/hypervisionplc-scada-net/capabilities 2>/dev/null | head -n 1)
[ "$NETBACKEND" = none ] && echo "ADVARSEL: hverken NetworkManager eller ifupdown findes — netværk kan ikke ændres fra web" >&2
# WiFi-strømbesparelse slås fra: på en server giver den forsinkelser og udfald (målt på en Pi: "Power save: on" som standard).
# NetworkManager: gælder ved næste WiFi-forbindelse; her slås den også fra straks (best effort, kun trådløse kort).
if [ "$NETBACKEND" = nm ]; then
    install -d -m 0755 /etc/NetworkManager/conf.d
    printf '[connection]\n# Sat af HypervisionPLC SCADA: ingen WiFi-strømbesparelse (2 = fra)\nwifi.powersave = 2\n' \
        > /etc/NetworkManager/conf.d/90-hypervisionplc-wifi-powersave.conf
    for w in /sys/class/net/*/wireless; do
        [ -d "$w" ] || continue
        iw dev "$(basename "$(dirname "$w")")" set power_save off 2>/dev/null || true
    done
fi

echo "== Let's Encrypt (certbot + deSEC): hypervision-letsencrypt"
# Hooken ligger på en fast sti (certbots fornyelsesopsætning peger på den); styringsscriptet er til en admin på maskinen.
install -m 0755 "$SRC/deploy/cert-deploy.sh" /usr/local/lib/hypervisionplc-scada/cert-deploy.sh
# Certifikat fra en reverse proxy (v4.11.0): forced command for proxyens nøgle i root's authorized_keys (se scriptet)
install -m 0755 "$SRC/deploy/cert-receive.sh" /usr/local/lib/hypervisionplc-scada/cert-receive.sh
install -m 0755 "$SRC/deploy/desec-acme-hook.sh" /usr/local/lib/hypervisionplc-scada/desec-acme-hook.sh
install -m 0755 "$SRC/deploy/tls-letsencrypt.sh" /usr/local/sbin/hypervision-letsencrypt
install -d -m 0755 /var/lib/hypervisionplc-scada-acme       # webroot til Let's Encrypt HTTP-01 (læses af nginx)
# nginx-opsætningen følger pakken (fx acme-location til HTTP-01): kun hvis SCADA's nginx-site findes. Den gamle gemmes med
# tidsstempel; nginx -t afviser → den gamle tilbage. Er filen tilpasset lokalt, skrives "# hypervisionplc: lokal" i den — så røres den ikke.
NGX=/etc/nginx/sites-available/hypervisionplc-scada
if [ -f "$NGX" ] && ! cmp -s "$SRC/deploy/nginx-hypervisionplc-scada.conf" "$NGX"; then
    if grep -q '^# hypervisionplc: lokal' "$NGX"; then
        echo "BEMÆRK: $NGX er markeret som lokal og opdateres ikke (Let's Encrypt HTTP-01 kræver acme-location fra deploy/nginx-hypervisionplc-scada.conf)" >&2
    else
        BK="$NGX.$(date +%Y%m%d-%H%M%S).bak"
        cp -p "$NGX" "$BK"
        install -m 0644 "$SRC/deploy/nginx-hypervisionplc-scada.conf" "$NGX"
        if nginx -t >/dev/null 2>&1; then
            systemctl reload nginx 2>/dev/null || true
            echo "nginx-opsætningen er opdateret (den forrige er gemt som $BK)"
        else
            cp -p "$BK" "$NGX"; echo "ADVARSEL: ny nginx-opsætning afvist af nginx -t — den gamle beholdes" >&2
        fi
    fi
fi
/usr/local/lib/hypervisionplc-scada/cert-deploy.sh info || true    # certifikatets metadata til System › Status (ingen nginx = intet at beskrive)
# System › Certifikater: root-hjælper installerer/gendanner certifikatet efter anmodning i <data>/config (bruger cert-deploy.sh)
install -m 0755 "$SRC/deploy/apply-tls.sh" /usr/local/lib/hypervisionplc-scada/apply-tls.sh.new
mv /usr/local/lib/hypervisionplc-scada/apply-tls.sh.new /usr/local/lib/hypervisionplc-scada/apply-tls.sh
install -d -m 0700 /var/lib/hypervisionplc-scada-tls
install -m 0644 "$SRC/deploy/hypervisionplc-scada-tls.service" "$SRC/deploy/hypervisionplc-scada-tls.path" /etc/systemd/system/
install -m 0755 "$SRC/deploy/apply-letsencrypt.sh" /usr/local/lib/hypervisionplc-scada/apply-letsencrypt.sh.new
mv /usr/local/lib/hypervisionplc-scada/apply-letsencrypt.sh.new /usr/local/lib/hypervisionplc-scada/apply-letsencrypt.sh
install -m 0644 "$SRC/deploy/hypervisionplc-scada-le.service" "$SRC/deploy/hypervisionplc-scada-le.path" /etc/systemd/system/

echo "== LLM-hjælper (System › Hjælper) — valgfri; selve tjenesten startes først, når en LLM-pakke er installeret og slået til"
id scada-llm >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin scada-llm
install -d -o scada -g scada -m 0750 "$DATA/llm"
install -m 0755 "$SRC/deploy/apply-llm.sh" /usr/local/lib/hypervisionplc-scada/apply-llm.sh.new
mv /usr/local/lib/hypervisionplc-scada/apply-llm.sh.new /usr/local/lib/hypervisionplc-scada/apply-llm.sh
install -m 0644 "$SRC/deploy/hypervisionplc-scada-llm.service" "$SRC/deploy/hypervisionplc-scada-llm-apply.service"     "$SRC/deploy/hypervisionplc-scada-llm-apply.path" /etc/systemd/system/
: > /var/lib/hypervisionplc-scada-net/llm-enabled
if [ -n "$HW" ]; then
    printf '{"profile": "%s", "by": "install.sh"}
' "$HW" > "$DATA/config/hw.json"
    chown scada:scada "$DATA/config/hw.json"
    echo "Hardwareprofil: $HW"
fi

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
systemctl enable -q hypervisionplc-scada-power.path
systemctl enable -q hypervisionplc-scada-llm-apply.path
systemctl restart hypervisionplc-scada-llm-apply.path
systemctl try-restart hypervisionplc-scada-llm.service 2>/dev/null || true   # kun hvis hjælperen er slået til
systemctl enable -q hypervisionplc-scada-backupmount.path
systemctl restart hypervisionplc-scada-power.path
systemctl restart hypervisionplc-scada-backupmount.path
systemctl enable -q hypervisionplc-scada-tls.path
systemctl restart hypervisionplc-scada-tls.path
systemctl enable -q hypervisionplc-scada-le.path
systemctl restart hypervisionplc-scada-le.path
systemctl enable -q hypervisionplc-scada-netwatch.timer; systemctl restart hypervisionplc-scada-netwatch.timer   # kører også net-detect.sh (hold capabilities opdateret)
if [ "$WITH_MOCK" -eq 1 ]; then
    systemctl enable -q hypervisionplc-mock-plc
    systemctl restart hypervisionplc-mock-plc
elif systemctl is-active --quiet hypervisionplc-mock-plc 2>/dev/null; then
    systemctl restart hypervisionplc-mock-plc   # kører fra den kode der lige er erstattet
fi

sleep 2
systemctl --no-pager --lines=5 status hypervisionplc-scada || true
echo "== Færdig. Version: $(cat "$APP/version.json" | tr -d '\n ')"
