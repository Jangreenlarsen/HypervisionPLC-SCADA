#!/bin/sh
# Genstart SCADA-tjenesten eller hele maskinen efter anmodning fra System › Konfiguration. Køres som ROOT af systemd
# (hypervisionplc-scada-power.service, udløst af .path-enheden når power.request findes) — aldrig direkte af tjenesten.
#
# Kopieres af install.sh til /usr/local/lib/hypervisionplc-scada/ — UDEN FOR programmappen, som en opdatering erstatter.
#
# SIKKERHED: Tjenesten (brugeren 'scada') ejer <data>/config og kan lægge hvad som helst dér, også symlinks. Derfor
#   * anmodningen flyttes (mv) ind i rootens egen mappe $W før den læses, og et symlink afvises;
#   * kun to handlinger kendes (restart, reboot) — alt andet i filen ignoreres, og ingen værdi når et shell;
#   * en anmodning ældre end 2 minutter afvises (en gammel fil må aldrig genstarte maskinen efter en opstart);
#   * anmodningen fjernes FØR handlingen, så en genstart aldrig udløser sig selv igen.
#
# Til test kan kommandoer og mapper overstyres: SYSTEMCTL, DATA, STATE, DELAY, SYNC.
set -u
set -f
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

SYSTEMCTL=${SYSTEMCTL:-systemctl}
SYNC=${SYNC:-sync}
DATA=${DATA:-/var/lib/hypervisionplc-scada}
W=${STATE:-/var/lib/hypervisionplc-scada-net}
DELAY=${DELAY:-3}          # sekunder: lad web-svaret nå frem til browseren, før tjenesten/maskinen stoppes
MAX_AGE=120
REQ=$DATA/config/power.request
WORK=$W/power.work
LOG=$W/power.log
STATUS=$W/power.json

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

[ -e "$REQ" ] || [ -L "$REQ" ] || exit 0
if [ -L "$REQ" ]; then
    rm -f "$REQ"; log "afvist: anmodningen var et symlink"; exit 0
fi
rm -f "$WORK"
mv -f "$REQ" "$WORK" 2>/dev/null || { log "afvist: kunne ikke flytte anmodningen"; exit 0; }
if [ -L "$WORK" ] || [ ! -f "$WORK" ]; then
    rm -f "$WORK"; log "afvist: anmodningen var ikke en almindelig fil"; exit 0
fi

now=$(date +%s)
mtime=$(stat -c %Y "$WORK" 2>/dev/null || echo 0)
action=$(sed -n 's/^action=//p' "$WORK" | head -n 1 | tr -cd 'a-z')
by=$(sed -n 's/^by=//p' "$WORK" | head -n 1 | tr -cd 'A-Za-z0-9._-' | cut -c1-40)
[ -n "$by" ] || by=ukendt
rm -f "$WORK"

if [ $((now - mtime)) -gt "$MAX_AGE" ]; then
    log "afvist: anmodningen fra $by var for gammel"; exit 0
fi
case "$action" in
    restart|reboot) ;;
    *) log "afvist: ukendt handling fra $by"; exit 0 ;;
esac

log "$action anmodet af $by"
printf '{"action":"%s","by":"%s","ts":%s}\n' "$action" "$by" "$now" > "$STATUS.tmp"
chmod 0644 "$STATUS.tmp"
mv -f "$STATUS.tmp" "$STATUS"

sleep "$DELAY"
case "$action" in
    restart) $SYSTEMCTL restart hypervisionplc-scada ;;
    reboot)  $SYNC; $SYSTEMCTL reboot ;;
esac
