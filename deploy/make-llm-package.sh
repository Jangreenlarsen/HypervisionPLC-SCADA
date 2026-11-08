#!/bin/sh
# Byg en LLM-pakke til System › Hjælper (v3.37.0): ÉN samlet, lokal fil med llama-server (llama.cpp, MIT) og en model
# (GGUF, Apache-2.0/MIT), så serveren aldrig selv henter noget fra internettet.
#   sh deploy/make-llm-package.sh [arkitektur] [model-id]
#   sh deploy/make-llm-package.sh x86_64 qwen3.5-4b-q4_k_m     (standard)
#   sh deploy/make-llm-package.sh aarch64 ministral-3-8b-q4_k_m
# → scada-llm-<arkitektur>-<model-id>-<llama-build>.tar i projektets rod (ukomprimeret — GGUF kan ikke pakkes mindre).
# Adresser og SHA256 står i deploy/llm-models.json; alt hentet kontrolleres. Hentede filer gemmes i .llm-cache/.
set -eu
cd "$(dirname "$0")/.."
ARCH=${1:-x86_64}
MODEL=${2:-qwen3.5-4b-q4_k_m}
PY=${PY:-python}
command -v "$PY" >/dev/null 2>&1 || PY=python3
CACHE=.llm-cache
mkdir -p "$CACHE"

# Alle felter fra listen på én gang (fejler, hvis arkitektur eller model ikke findes)
eval "$("$PY" - "$ARCH" "$MODEL" <<'EOF'
import json, shlex, sys
arch, model = sys.argv[1], sys.argv[2]
c = json.load(open("deploy/llm-models.json", encoding="utf-8"))
l = c["llama"]
if arch not in ("x86_64", "aarch64"):
    sys.exit(f"Ukendt arkitektur '{arch}' (x86_64 eller aarch64)")
if model not in c["models"]:
    sys.exit(f"Ukendt model '{model}' — kendte: {', '.join(c['models'])}")
m = c["models"][model]
v = {"BUILD": l["build"], "LLAMA_URL": l[arch]["url"], "LLAMA_SHA": l[arch]["sha256"], "LLAMA_LIC": l["license_url"],
     "LLAMA_GLIBC": l[arch].get("glibc", ""),
     "M_NAME": m["name"], "M_QUANT": m["quant"], "M_LICENSE": m["license"], "M_LIC_URL": m["license_url"],
     "M_FILE": m["file"], "M_URL": m["url"], "M_SHA": m["sha256"], "M_SIZE": str(m["size"]), "M_CTX": str(m["ctx"])}
print("\n".join(f"{k}={shlex.quote(x)}" for k, x in v.items()))
EOF
)"

fetch() {   # fetch <url> <fil> <sha256>
    if [ -f "$2" ] && [ "$(sha256sum "$2" | cut -c1-64)" = "$3" ]; then echo "  (fra cache) $(basename "$2")"; return 0; fi
    echo "  henter $1"
    curl -fL --retry 3 -o "$2.part" "$1"
    got=$(sha256sum "$2.part" | cut -c1-64)
    if [ "$got" != "$3" ]; then rm -f "$2.part"; echo "FEJL: SHA256 for $(basename "$2") passer ikke ($got)" >&2; exit 1; fi
    mv -f "$2.part" "$2"
}

echo "== llama.cpp $BUILD ($ARCH)"
fetch "$LLAMA_URL" "$CACHE/llama-$BUILD-$ARCH.tar.gz" "$LLAMA_SHA"
echo "== Model $M_NAME $M_QUANT"
fetch "$M_URL" "$CACHE/$M_FILE" "$M_SHA"

OUT="scada-llm-$ARCH-$MODEL-$BUILD.tar"
STAGE=$CACHE/stage
rm -rf "$STAGE"
mkdir -p "$STAGE/scada-llm/llama" "$STAGE/scada-llm/model" "$STAGE/scada-llm/LICENSES"
# Kun selve serveren og dens biblioteker (release-tarballen har mange værktøjer, der ikke bruges). Symlinks
# (libfoo.so -> libfoo.so.0 -> libfoo.so.0.29.0) er ikke tilladt i LLM-pakken: hvert navn bliver en kopi af filen.
"$PY" - "$CACHE/llama-$BUILD-$ARCH.tar.gz" "$STAGE/scada-llm/llama" <<'EOF'
import posixpath, re, sys, tarfile
src, dst = sys.argv[1], sys.argv[2]
with tarfile.open(src, "r:gz") as tar:
    members = {m.name: m for m in tar.getmembers()}
    def resolve(m, depth=0):
        while m.issym() and depth < 10:
            m = members[posixpath.normpath(posixpath.join(posixpath.dirname(m.name), m.linkname))]
            depth += 1
        return m
    server = [m for m in members.values() if posixpath.basename(m.name) == "llama-server" and (m.isreg() or m.issym())]
    if not server:
        sys.exit("FEJL: llama-server findes ikke i llama.cpp-pakken")
    bindir = posixpath.dirname(server[0].name)
    n = 0
    for name, m in members.items():
        base = posixpath.basename(name)
        if posixpath.dirname(name) != bindir or not (base == "llama-server" or re.search(r"\.so(\.\d+)*$", base)):
            continue
        real = resolve(m)
        if not real.isreg():
            continue
        with open(f"{dst}/{base}", "wb") as out:
            out.write(tar.extractfile(real).read())
        n += 1
    print(f"  {n} filer fra {bindir}/")
EOF
cp "$CACHE/$M_FILE" "$STAGE/scada-llm/model/$M_FILE"
curl -fsSL "$LLAMA_LIC" -o "$STAGE/scada-llm/LICENSES/llama.cpp-LICENSE.txt"
curl -fsSL "$M_LIC_URL" -o "$STAGE/scada-llm/LICENSES/model-$MODEL-LICENSE.txt"
printf '%s\n' "Model: $M_NAME ($M_QUANT), licens $M_LICENSE — $M_URL" "llama.cpp $BUILD, licens MIT — $LLAMA_URL" \
    > "$STAGE/scada-llm/LICENSES/README.txt"
"$PY" - "$STAGE/scada-llm/manifest.json" <<EOF
import json, sys
json.dump({"format": "hv-llm", "format_version": 1, "arch": "$ARCH", "llama_build": "$BUILD", "ctx": int("$M_CTX"),
           "glibc": "$LLAMA_GLIBC",
           "model": {"id": "$MODEL", "name": "$M_NAME", "file": "$M_FILE", "quant": "$M_QUANT", "license": "$M_LICENSE",
                     "sha256": "$M_SHA", "size": int("$M_SIZE")}}, open(sys.argv[1], "w"), indent=1)
EOF
rm -f "$OUT"
tar --force-local -cf "$OUT" -C "$STAGE" scada-llm
rm -rf "$STAGE"
echo "LLM-pakke: $OUT ($(wc -c < "$OUT") bytes)"
sha256sum "$OUT"
