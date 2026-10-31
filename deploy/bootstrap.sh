#!/bin/sh
# Installér HypervisionPLC SCADA på en ny Raspberry Pi OS / Debian direkte fra GitHub (v3.13.0).
#
#   curl -fsSL https://raw.githubusercontent.com/Jangreenlarsen/HypervisionPLC-SCADA/main/deploy/bootstrap.sh | sudo sh
#
# Som standard sættes nginx med TLS op foran SCADA med Pi'ens hostnavn og IP (SCADA selv lytter kun på 127.0.0.1),
# så siden kan nås på https://<pi-ens-ip>. Valg sendes videre til deploy/install.sh:
#   ... | sudo sh -s -- --with-nginx scada.local 192.168.1.50      (andet hostnavn/IP i certifikatet)
#   ... | sudo sh -s -- --with-mock-plc                            (+ mock-PLC til test)
#   ... | sudo sh -s -- --local-only                               (ingen nginx — kun adgang fra Pi'en selv)
#
# Miljøvariabler (skrives FØR sh, efter sudo: ... | sudo SCADA_VERSION=v3.13.0 sh):
#   SCADA_VERSION=v3.13.0   en bestemt udgivelse i stedet for den nyeste
#   SCADA_REPO=ejer/repo     et andet GitHub-repo (standard Jangreenlarsen/HypervisionPLC-SCADA)
#   DRY_RUN=1                hent og kontrollér pakken, men installér ikke (kræver ikke root)
#
# Scriptet henter udgivelsens pakke (scada-<version>-b<build>.tar — den samme som OTA-opdateringen bruger) og dens
# kontrolsum fra GitHub Releases, kontrollerer den, pakker ud og kører deploy/install.sh. Der skal ikke bygges noget
# på Pi'en (frontend er færdigbygget i pakken). Senere opdateringer sker fra web-siden under System › Opdatering.
set -eu

REPO=${SCADA_REPO:-Jangreenlarsen/HypervisionPLC-SCADA}
TAG=${SCADA_VERSION:-}
DRY=${DRY_RUN:-0}
DATA=/var/lib/hypervisionplc-scada

say() { printf '== %s\n' "$*"; }
fail() { printf 'FEJL: %s\n' "$*" >&2; exit 1; }

if [ "$DRY" != 1 ] && [ "$(id -u)" -ne 0 ]; then
    fail "skal køres som root — brug: curl -fsSL …/bootstrap.sh | sudo sh"
fi

need() { command -v "$1" >/dev/null 2>&1; }
if ! need curl || ! need sha256sum || ! need tar; then
    [ "$DRY" = 1 ] && fail "curl, sha256sum og tar skal være installeret"
    say "Installerer curl og tar"
    apt-get update -qq
    apt-get install -y -qq curl ca-certificates tar coreutils >/dev/null
fi

if [ -n "$TAG" ]; then API="https://api.github.com/repos/$REPO/releases/tags/$TAG"
else API="https://api.github.com/repos/$REPO/releases/latest"; fi
say "Finder udgivelsen (${TAG:-nyeste}) i $REPO"
JSON=$(curl -fsSL -H 'Accept: application/vnd.github+json' "$API") \
    || fail "kunne ikke hente udgivelsen fra $API (findes den? er der internet?)"

# adresserne på pakken og dens kontrolsum (uden jq: grep i GitHubs JSON)
url_of() { printf '%s\n' "$JSON" | grep -o "\"browser_download_url\": *\"[^\"]*$1\"" | head -n 1 | sed 's/.*"\(https[^"]*\)"$/\1/'; }
TAR_URL=$(url_of '\.tar')
SUM_URL=$(url_of '\.tar\.sha256')
[ -n "$TAR_URL" ] || fail "udgivelsen har ingen scada-*.tar"
[ -n "$SUM_URL" ] || fail "udgivelsen har ingen kontrolsum (scada-*.tar.sha256)"
NAME=$(basename "$TAR_URL")

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT INT TERM
say "Henter $NAME"
curl -fL --retry 3 --progress-bar -o "$WORK/$NAME" "$TAR_URL" || fail "kunne ikke hente $TAR_URL"
curl -fsSL --retry 3 -o "$WORK/$NAME.sha256" "$SUM_URL" || fail "kunne ikke hente $SUM_URL"
say "Kontrollerer kontrolsummen"
(cd "$WORK" && sha256sum -c "$NAME.sha256") || fail "kontrolsummen passer ikke — pakken er beskadiget eller ændret"

tar -xf "$WORK/$NAME" -C "$WORK" || fail "pakken kunne ikke pakkes ud"
[ -f "$WORK/scada/deploy/install.sh" ] && [ -f "$WORK/scada/frontend/dist/index.html" ] \
    || fail "pakken mangler deploy/install.sh eller den byggede frontend"

if [ "$DRY" = 1 ]; then
    say "DRY_RUN: $NAME er hentet og kontrolleret — version $(tr -d '\n ' < "$WORK/scada/version.json"). Intet installeret."
    exit 0
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
# nginx som standard: uden den kan SCADA kun nås fra Pi'en selv
NGINX=1
for a in "$@"; do case "$a" in --with-nginx|--local-only) NGINX=0 ;; esac; done
LOCAL=0
for a in "$@"; do [ "$a" = --local-only ] && LOCAL=1; done
if [ "$LOCAL" = 1 ]; then
    # --local-only er bootstraps eget valg og sendes ikke videre
    for a in "$@"; do shift; [ "$a" = --local-only ] || set -- "$@" "$a"; done
fi
if [ "$NGINX" = 1 ]; then
    [ -n "$IP" ] || fail "kunne ikke finde Pi'ens IP-adresse — angiv den: … | sudo sh -s -- --with-nginx <hostnavn> <ip>"
    set -- "$@" --with-nginx "$(hostname)" "$IP"
fi

say "Installerer"
sh "$WORK/scada/deploy/install.sh" "$@"

echo
if [ "$LOCAL" = 1 ]; then
    say "SCADA kører kun lokalt: http://127.0.0.1:8000 (fra Pi'en selv)"
else
    say "SCADA kører. Åbn https://${IP:-<pi-ens-ip>} (selvsigneret certifikat — godkend advarslen i browseren)"
fi
if [ -f "$DATA/initial-admin-password.txt" ]; then
    echo "   Første login: bruger 'admin', engangsadgangskode: $(cat "$DATA/initial-admin-password.txt")"
    echo "   (skal skiftes ved første login; filen ligger i $DATA/initial-admin-password.txt)"
fi
echo "   Opdateringer: hent den nyeste scada-*.tar under Releases på GitHub og upload den under System › Opdatering."
