# SPDX-License-Identifier: AGPL-3.0-or-later
"""Indlæs brøndstationen (GLOBAL_VAR + Logic2-3) på en HypervisionPLC via dens REST API. Logic1 og Logic4 røres ikke.

Brug:  PLC_USER=admin PLC_PASS=... python demo/vandvaerk/load.py http://10.1.1.34
       --check   kun læs status (hvilke pladser er ledige, hvad kører), skriv intet
       --force   overskriv Logic2-3, selvom de indeholder et andet program

Kræver PLC-firmware 7.9.68.168 eller nyere (64 globale variable, 16 timere, 2048 AST-noder; DINT/REAL uden startværdi).
GLOBAL_VAR er fælles for hele PLC'en: blokken her erstatter en eksisterende (fx varmeanlæggets). Interval 500 ms.
Adgangskoden læses fra miljøet og skrives aldrig ud.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAMS = {2: ("logic2_styring.st", "VandvaerkStyring"), 3: ("logic3_proces.st", "VandvaerkProces")}
INTERVAL_MS = 500   # fysikken regner med dt = 0,5 s x tidsfaktor


def _plc_class():
    spec = importlib.util.spec_from_file_location("varme_load", HERE.parent / "varme-plc" / "load.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Plc


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check_only, force = "--check" in sys.argv, "--force" in sys.argv
    if len(args) != 1:
        raise SystemExit(__doc__)
    user, password = os.environ.get("PLC_USER", ""), os.environ.get("PLC_PASS", "")
    if not user or not password:
        raise SystemExit("Sæt PLC_USER og PLC_PASS i miljøet")
    plc = _plc_class()(args[0], user, password)
    status = plc.get("/api/logic")
    programs = {p.get("id"): p for p in status.get("programs", [])}
    for pid in (1, 2, 3, 4):
        p = programs.get(pid, {})
        print(f"  Logic{pid}: {(p.get('name') if p.get('source_size') else None) or '(tom)'} enabled={p.get('enabled')} "
              f"compiled={p.get('compiled')} fejl={p.get('error_count')}")
    if check_only:
        return
    for pid, (_, name) in PROGRAMS.items():
        p = programs.get(pid, {})
        existing = plc.get(f"/api/logic/{pid}/source").get("source", "") if p.get("source_size") else ""
        if existing and f"PROGRAM {name}" not in existing and not force:
            raise SystemExit(f"Logic{pid} bruges af et andet program. Brug --force for at overskrive det (eller vælg en anden PLC).")
    was_enabled = {pid for pid, p in programs.items() if p.get("enabled") and pid not in PROGRAMS}

    for pid in PROGRAMS:
        plc.post(f"/api/logic/{pid}/disable")
    r = plc.post("/api/logic/globals/source", {"source": (HERE / "globals.st").read_text(encoding="utf-8")})
    if not r.get("compiled", True) or r.get("compile_error"):
        raise SystemExit(f"GLOBAL_VAR: {r.get('compile_error') or r}")
    print(f"GLOBAL_VAR: {r.get('count')} variable")
    for pid, (f, _) in PROGRAMS.items():
        r = plc.post(f"/api/logic/{pid}/source", {"source": (HERE / f).read_text(encoding="utf-8")})
        if not r.get("compiled") or r.get("compile_error"):
            raise SystemExit(f"Logic{pid} ({f}): kompileringsfejl: {r.get('compile_error') or r}")
        plc.post(f"/api/logic/{pid}/interval", {"interval_ms": INTERVAL_MS})
        print(f"Logic{pid} ({f}): kompileret, {r.get('instr_count')} instruktioner")
    for pid in PROGRAMS:
        plc.post(f"/api/logic/{pid}/enable")
    # et program uden for dette (fx Logic1) skal blive ved at køre, hvis det kørte før
    for pid in was_enabled:
        if not plc.get(f"/api/logic/{pid}").get("enabled"):
            plc.post(f"/api/logic/{pid}/enable")
            print(f"Logic{pid}: aktiveret igen")

    time.sleep(3)
    bad = False
    for pid in (1, 2, 3, 4):
        info = plc.get(f"/api/logic/{pid}")
        if not info.get("source_size"):
            continue
        stats = plc.get(f"/api/logic/{pid}/stats")
        mine = pid in PROGRAMS
        ok = info.get("enabled") and info.get("compiled") and not stats.get("error_count")
        bad |= mine and not ok
        print(f"Logic{pid}{'' if mine else ' (urørt)'}: {'OK' if ok else 'FEJL'} — {len(info.get('variables') or [])} variable, "
              f"udført {stats.get('execution_count')}×, fejl {stats.get('error_count')}, maks {stats.get('max_execution_us')} µs")
    if bad:
        raise SystemExit("Mindst ét program kører ikke korrekt — se PLC'ens ST-editor/Runtime Monitor")
    print("Brøndstationen kører (Logic2 styring, Logic3 proces). Opret tagsene som kilde logic:<nr>:<navn> (se README.md).")


if __name__ == "__main__":
    main()
