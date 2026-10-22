#!/bin/sh
# scada-maint — vedligeholdelse ved fuld disk (ryd logfiler, gamle backups og historik). Installeres af install.sh som
# /usr/local/sbin/scada-maint. Virker uden at web-siden kører. Se `scada-maint --help` og manualen (System › Konfiguration).
#
#   scada-maint status                       størrelser og ledig plads
#   scada-maint emergency [--yes]            trin for trin, til der er plads nok
#   scada-maint logs | backups | trends | history | trends-reset   (se --help for hver)
#
# TØRKØRSEL som standard — intet ændres uden --yes. Kræver root for at udføre (su -c ... eller sudo).
set -eu
ENVFILE=${ENVFILE:-/etc/hypervisionplc-scada.env}
APP=${APP:-/opt/hypervisionplc-scada}
if [ -r "$ENVFILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENVFILE"
    set +a
fi
cd "$APP/backend"
exec "$APP/venv/bin/python" -m app.maint "$@"
