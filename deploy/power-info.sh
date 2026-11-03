#!/bin/sh
# Raspberry Pi: skriv strøm-/varmestatus (vcgencmd get_throttled) til <state>/power.json, så SCADA-tjenesten kan vise og alarmere om
# lav spænding. Køres som ROOT af DHCP-vagtens timer (hvert 30. sekund, ExecStartPre) og af install.sh.
#
# Hvorfor en hjælper: tjenesten (brugeren 'scada') må ikke åbne /dev/vcio, og kernens sysfs-sti til samme oplysning findes ikke på alle
# kerner (målt på en Pi 3B+ med kerne 6.18: stien mangler). Filen er root-ejet (0644); tjenesten læser kun.
# Ikke en Pi (ingen vcgencmd): intet at skrive, og en gammel fil fjernes.
#
# Til test kan kommandoer og mapper overstyres: VCGENCMD, STATE.
set -u
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin:/opt/vc/bin"

STATE=${STATE:-/var/lib/hypervisionplc-scada-net}
VCGENCMD=${VCGENCMD:-vcgencmd}

if ! command -v "$VCGENCMD" > /dev/null 2>&1; then rm -f "$STATE/power.json"; exit 0; fi
out=$($VCGENCMD get_throttled 2> /dev/null) || exit 0
hex=$(printf '%s' "$out" | sed -n 's/^throttled=0x\([0-9A-Fa-f]\{1,8\}\)$/\1/p')
[ -n "$hex" ] || exit 0

mkdir -p "$STATE" || exit 1
printf '{"throttled":%s,"ts":%s}\n' "$((0x$hex))" "$(date +%s)" > "$STATE/power.json.tmp" \
    && chmod 0644 "$STATE/power.json.tmp" && mv "$STATE/power.json.tmp" "$STATE/power.json"
exit 0
