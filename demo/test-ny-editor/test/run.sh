#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# PC-test af test_ny_editor.st med HypervisionPLC's egen ST-compiler og VM. Kraever g++ og PLC-repoet (PLC_REPO).
# Koeres fra SCADA-repoets rod:  bash demo/test-ny-editor/test/run.sh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DIR="$(cd "$HERE/.." && pwd)"
PLC="${PLC_REPO:-$(cd "$DIR/../../.." && pwd)/HypervisionPLC}"
[ -d "$PLC/src" ] || { echo "PLC-repoet findes ikke: $PLC (saet PLC_REPO)"; exit 2; }
OUT="$HERE/build"
mkdir -p "$OUT"
FLAGS="-std=gnu++17 -O1 -w -include stdlib.h -include stdint.h -I$PLC/test/st_host/stubs -I$PLC/include -DBOARD_ES32D26 -DBOARD_HAS_PSRAM"
OBJS=()
for f in st_lexer st_parser st_compiler st_vm st_builtins st_stateful st_builtin_timers st_builtin_counters st_builtin_edge st_builtin_latch st_builtin_signal; do
  [ "$OUT/$f.o" -nt "$PLC/src/$f.cpp" ] || g++ $FLAGS -c "$PLC/src/$f.cpp" -o "$OUT/$f.o"
  OBJS+=("$OUT/$f.o")
done
g++ $FLAGS -Dst_logic_globals_lookup=host_stub_globals_lookup -c "$PLC/test/st_host/host_stubs.cpp" -o "$OUT/host_stubs.o"
g++ $FLAGS -c "$HERE/one.cpp" -o "$OUT/one.o"
g++ -o "$OUT/one" "$OUT/one.o" "$OUT/host_stubs.o" "${OBJS[@]}"
"$OUT/one" "$DIR/test_ny_editor.st"
