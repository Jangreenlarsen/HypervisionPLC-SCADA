#!/bin/sh
# Find ud af hvilket netværkssystem maskinen bruger og om der er en brugbar DHCP-klient. Skriver <state>/capabilities og markørfilerne
# (enabled / no-backend), som System › Konfiguration læser. Køres som ROOT:
#   * af install.sh (ved installation/opdatering), og
#   * af DHCP-vagtens timer (hvert 30. sekund, ExecStartPre) — så en senere `apt install dhcpcd-base` slår igennem af sig selv,
#     uden at nogen skal køre install.sh igen.
#
# NetworkManager (Raspberry Pi OS) → 'nm'. ifupdown (/etc/network/interfaces, Debian/Ubuntu-servere og VM'er) → 'ifupdown'.
# DHCP: NetworkManager har sin egen klient. Med ifupdown kræves dhcpcd (prøver uden ende og giver adresserne en levetid, som
# DHCP-vagten kan se); dhclient kører med -1 (én gang) og udhcpc giver ingen levetid — begge ville få vagten til at tage fejl.
#
# Til test: NETDETECT_PATH (søgesti for kommandoer), IFFILE, STATE.
set -u
export PATH="${NETDETECT_PATH:-/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin}"
W=${STATE:-/var/lib/hypervisionplc-scada-net}
IFFILE=${IFFILE:-/etc/network/interfaces}

mkdir -p "$W" || exit 1
chmod 0755 "$W"

BACKEND=none
if command -v nmcli >/dev/null 2>&1 && systemctl is-active --quiet NetworkManager 2>/dev/null; then
    BACKEND=nm
elif [ -f "$IFFILE" ] && command -v ifup >/dev/null 2>&1 && command -v ifdown >/dev/null 2>&1; then
    BACKEND=ifupdown
fi
DHCP=0
if [ "$BACKEND" = nm ]; then DHCP=1; elif [ "$BACKEND" = ifupdown ] && command -v dhcpcd >/dev/null 2>&1; then DHCP=1; fi

NEW=$(printf 'backend=%s\ndhcp=%s\n' "$BACKEND" "$DHCP")
if [ "$(cat "$W/capabilities" 2>/dev/null)" != "$NEW" ]; then
    printf '%s\n' "$NEW" > "$W/capabilities.tmp" && chmod 0644 "$W/capabilities.tmp" && mv "$W/capabilities.tmp" "$W/capabilities"
fi
if [ "$BACKEND" != none ]; then
    [ -e "$W/enabled" ] || : > "$W/enabled"
    rm -f "$W/no-backend" "$W/no-nmcli"
else
    rm -f "$W/enabled"
    [ -e "$W/no-backend" ] || : > "$W/no-backend"
fi
echo "Netværkssystem: $BACKEND (DHCP-klient: $DHCP)"
exit 0
