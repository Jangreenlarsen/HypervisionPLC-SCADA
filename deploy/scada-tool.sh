#!/bin/sh
# scada-tool — værktøjskassen til vedligeholdelse af serveren (status, diagnose, log, start/stop, opdatering, backup, brugere).
# Installeres af install.sh som /usr/local/sbin/scada-tool. Virker uden at web-siden kører. Se `scada-tool --help`.
#
#   scada-tool status | check | logs | start | stop | restart | update … | backup … | user … | config | maint …
#
# Kræver root (su -c … eller sudo). Alt der ændrer noget, spørger først (eller kræv --yes) og logges i systemloggen.
set -eu
# Rod-værktøj: faste stier og en fast PATH (ikke den kaldende brugers — su -c uden "-" beholder den), ingen arvede Python-variabler
PATH=/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin
export PATH
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP
ENVFILE=/etc/hypervisionplc-scada.env
APP=/opt/hypervisionplc-scada
export ENVFILE
case "${1:-}" in
    ""|-h|--help|help) ;;
    *) [ "$(id -u)" -eq 0 ] || { echo "scada-tool skal køres som root (su -c 'scada-tool …' eller sudo)." >&2; exit 1; } ;;
esac
if [ -r "$ENVFILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENVFILE"
    set +a
fi
cd "$APP/backend"
exec "$APP/venv/bin/python" -E -m app.tool "$@"
