# SPDX-License-Identifier: AGPL-3.0-or-later
"""Indlæs testprogrammet test_ny_editor.st i ét Logic-nummer på en HypervisionPLC via dens REST API.

Brug:  PLC_USER=admin PLC_PASS=... python demo/test-ny-editor/load.py http://10.1.1.34 --logic=2
       --check          kun læs status (hvilke Logic-numre er ledige), skriv intet
       --logic=N        Logic-nummeret programmet lægges i (1-4). Er pladsen brugt af et andet program, kræves --force
       --force          overskriv det program, der ligger der

Demo-PLC'ens fire pladser bruges af varmeanlægget (demo/varme-plc). Læg testprogrammet på en anden PLC, eller stop og
erstat et af varmeprogrammerne med --force. Interval 500 ms. Adgangskoden læses fra miljøet og skrives aldrig ud.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "TestNyEditor"
INTERVAL_MS = 500


def _plc_class():
    spec = importlib.util.spec_from_file_location("varme_load", HERE.parent / "varme-plc" / "load.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Plc


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    check_only, force = "--check" in flags, "--force" in flags
    logic = next((int(f.split("=", 1)[1]) for f in flags if f.startswith("--logic=")), 0)
    if len(args) != 1 or (not check_only and logic not in (1, 2, 3, 4)):
        raise SystemExit(__doc__)
    user, password = os.environ.get("PLC_USER", ""), os.environ.get("PLC_PASS", "")
    if not user or not password:
        raise SystemExit("Sæt PLC_USER og PLC_PASS i miljøet")
    plc = _plc_class()(args[0], user, password)
    programs = {p.get("id"): p for p in plc.get("/api/logic").get("programs", [])}
    for pid in (1, 2, 3, 4):
        p = programs.get(pid, {})
        print(f"  Logic{pid}: {p.get('name') or '(tom)'} enabled={p.get('enabled')} compiled={p.get('compiled')}")
    if check_only:
        return
    used = programs.get(logic, {}).get("name") or ""
    if used and used != NAME and not force:
        raise SystemExit(f"Logic{logic} bruges af '{used}'. Vælg en anden plads, eller brug --force for at overskrive den.")
    source = (HERE / "test_ny_editor.st").read_text(encoding="utf-8")
    plc.post(f"/api/logic/{logic}/disable")
    r = plc.post(f"/api/logic/{logic}/source", {"source": source})
    if not r.get("compiled") or r.get("compile_error"):
        raise SystemExit(f"Kompileringsfejl: {r.get('compile_error') or r}")
    plc.post(f"/api/logic/{logic}/interval", {"interval_ms": INTERVAL_MS})
    plc.post(f"/api/logic/{logic}/enable")
    time.sleep(3)
    info, stats = plc.get(f"/api/logic/{logic}"), plc.get(f"/api/logic/{logic}/stats")
    ok = info.get("enabled") and info.get("compiled") and not stats.get("error_count")
    print(f"Logic{logic}: {'OK' if ok else 'FEJL'} — {len(info.get('variables') or [])} variable, "
          f"udført {stats.get('execution_count')}×, fejl {stats.get('error_count')}")
    if not ok:
        raise SystemExit("Programmet kører ikke korrekt — se PLC'ens ST-editor/Runtime Monitor")
    print(f"Testprogrammet kører i Logic{logic}. Opret tagsene som kilde logic:{logic}:<navn> (se README.md).")


if __name__ == "__main__":
    main()
