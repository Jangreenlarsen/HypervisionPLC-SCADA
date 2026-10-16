#!/bin/sh
# Byg en opdateringspakke (til OTA under System › Opdatering, eller scp + install.sh) af det der er COMMITTET:
#   sh deploy/make-package.sh            → scada-<version>-b<build>.tar i projektets rod
# git archive giver LF-linjeskift uanset arbejdsmappen; frontend bygges først og lægges med som frontend/dist.
set -eu
cd "$(dirname "$0")/.."
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "Advarsel: der er ucommittede ændringer — pakken indeholder kun det der er committet (+ en frisk frontend-build)." >&2
fi
(cd frontend && npm run build)
VERSION=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' version.json)
BUILD=$(sed -n 's/.*"build": *"\([^"]*\)".*/\1/p' version.json)
OUT="scada-$VERSION-b$BUILD.tar"
git archive --format=tar --prefix=scada/ HEAD > "$OUT"
tar --force-local -rf "$OUT" --transform 's,^,scada/,' frontend/dist
echo "Pakke: $OUT ($(wc -c < "$OUT") bytes)"
command -v sha256sum >/dev/null && sha256sum "$OUT" || true
