#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# PC-test af demo-varmeanlaeggets ST-programmer med HypervisionPLC's egen
# ST-compiler og VM. Kraever g++ og PLC-repoet (PLC_REPO, standard ../HypervisionPLC).
# Koeres fra SCADA-repoets rod:  bash demo/varme-plc/test/run.sh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DEMO="$(cd "$HERE/.." && pwd)"
PLC="${PLC_REPO:-$(cd "$DEMO/../../.." && pwd)/HypervisionPLC}"
[ -d "$PLC/src" ] || { echo "PLC-repoet findes ikke: $PLC (saet PLC_REPO)"; exit 2; }
OUT="$HERE/build"
mkdir -p "$OUT"
FLAGS="-std=gnu++17 -O1 -w -include stdlib.h -include stdint.h -I$PLC/test/st_host/stubs -I$PLC/include -DBOARD_ES32D26 -DBOARD_HAS_PSRAM"
OBJS=()
for f in st_lexer st_parser st_compiler st_vm st_builtins st_stateful st_builtin_timers st_builtin_counters st_builtin_edge st_builtin_latch st_builtin_signal; do
  [ "$OUT/$f.o" -nt "$PLC/src/$f.cpp" ] || g++ $FLAGS -c "$PLC/src/$f.cpp" -o "$OUT/$f.o"
  OBJS+=("$OUT/$f.o")
done
# host_stubs' tomme GLOBAL_VAR-opslag omdoebes; sim_test.cpp har det rigtige
g++ $FLAGS -Dst_logic_globals_lookup=host_stub_globals_lookup -c "$PLC/test/st_host/host_stubs.cpp" -o "$OUT/host_stubs.o"
g++ $FLAGS -c "$HERE/sim_test.cpp" -o "$OUT/sim_test.o"
g++ -o "$OUT/sim_test" "$OUT/sim_test.o" "$OUT/host_stubs.o" "${OBJS[@]}"
"$OUT/sim_test" "$DEMO"
