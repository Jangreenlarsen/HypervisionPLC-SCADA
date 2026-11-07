#!/bin/sh
# Udgiv en LLM-pakke som GitHub release (v4.4.0), så administratoren kan vælge den under System › Hjælper:
#   sh deploy/publish-llm-release.sh x86_64 qwen3.5-4b-q4_k_m
# Bygger pakken (make-llm-package.sh, hvis den ikke findes), deler den i dele på 1900 MiB (GitHub tillader højst 2 GiB pr.
# fil) og lægger delene + scada-llm-….tar.sha256 i udgivelsen `llm-<model>-<llama-build>`.
# Udgivelsen er en PRERELEASE og aldrig "latest": SCADA-opdateringerne (/releases/latest) må ikke forveksle den med en
# SCADA-pakke. Findes udgivelsen allerede (fx med den anden arkitektur), lægges filerne blot til (--clobber).
# Husk derefter at tilføje arkitekturen til "published" for modellen i deploy/llm-models.json.
set -eu
cd "$(dirname "$0")/.."
ARCH=${1:?arkitektur (x86_64 eller aarch64)}
MODEL=${2:?model-id fra deploy/llm-models.json}
PY=${PY:-python}
command -v "$PY" >/dev/null 2>&1 || PY=python3
command -v gh >/dev/null 2>&1 || { echo "Fejl: GitHub CLI (gh) mangler" >&2; exit 1; }
eval "$("$PY" - "$MODEL" <<'EOF'
import json, shlex, sys
c = json.load(open("deploy/llm-models.json", encoding="utf-8"))
m = c["models"].get(sys.argv[1]) or sys.exit(f"Ukendt model '{sys.argv[1]}'")
for k, v in {"BUILD": c["llama"]["build"], "NAME": m["name"], "VARIANT": m.get("variant", ""), "LICENSE": m["license"],
             "ABOUT": m.get("about", "")}.items():
    print(f"{k}={shlex.quote(str(v))}")
EOF
)"
PKG="scada-llm-$ARCH-$MODEL-$BUILD.tar"
TAG="llm-$MODEL-$BUILD"
[ -f "$PKG" ] || sh deploy/make-llm-package.sh "$ARCH" "$MODEL"
OUT=".llm-cache/release-$ARCH-$MODEL"
rm -rf "$OUT"
mkdir -p "$OUT"
echo "Deler $PKG ($(wc -c < "$PKG") bytes) …"
split -b 1900M -d -a 2 --numeric-suffixes=1 "$PKG" "$OUT/$PKG.part"
SHA=$(sha256sum < "$PKG" | cut -d' ' -f1)
printf '%s  %s\n' "$SHA" "$PKG" > "$OUT/$PKG.sha256"
NOTES="LLM-pakke til HypervisionPLC SCADA › System › Hjælper (LLM): **$NAME** ($VARIANT).

$ABOUT

- llama.cpp $BUILD (MIT) + $NAME ($LICENSE) — licenserne ligger i pakken (LICENSES/).
- Hentes og installeres fra SCADA'en (System › Hjælper › Vælg model). Delene (.partNN) sættes sammen og kontrolleres
  med $PKG.sha256 (SHA256 $SHA).
- Manuelt (lukket net): \`cat $PKG.part* > $PKG\` og upload filen under System › Hjælper."
if gh release view "$TAG" >/dev/null 2>&1; then
    # Gamle dele af SAMME pakke fjernes først (en ny pakke med færre dele må ikke efterlade fx .part03)
    for a in $(gh release view "$TAG" --json assets --jq '.assets[].name' | grep "^$PKG\.part"); do
        gh release delete-asset "$TAG" "$a" --yes
    done
    gh release upload "$TAG" "$OUT"/* --clobber
    gh release edit "$TAG" --notes "$NOTES"
else
    gh release create "$TAG" "$OUT"/* --prerelease --latest=false --title "LLM-pakke: $NAME" --notes "$NOTES"
fi
echo "Udgivet: $TAG ($ARCH) — SHA256 $SHA"
echo "Lås den fast i deploy/llm-models.json: \"published\": {\"$ARCH\": \"$SHA\"}"
rm -rf "$OUT"
