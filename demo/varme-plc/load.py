# SPDX-License-Identifier: AGPL-3.0-or-later
"""Indlæs demo-varmeanlægget (GLOBAL_VAR + Logic1-4) på en HypervisionPLC via dens REST API.

Brug:  PLC_USER=admin PLC_PASS=... python demo/varme-plc/load.py http://10.1.1.40
       (--check = kun læs status, skriv intet)

Rækkefølge: log ind (Bearer) → tjek kildepuljen → stop Logic1-4 → GLOBAL_VAR → kilde pr. program
→ interval 500 ms → start → kontrollér at alt er kompileret og kører. Kun Python-standardbiblioteket.
Adgangskoden læses fra miljøet og skrives aldrig ud.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAMS = {1: "logic1_styring.st", 2: "logic2_kilder.st", 3: "logic3_tank_hus.st", 4: "logic4_system.st"}
INTERVAL_MS = 500   # fysikken i programmerne regner med dt = 0,5 s × tidsfaktor


class Plc:
    def __init__(self, base: str, user: str, password: str) -> None:
        self.base = base.rstrip("/")
        self.token = ""
        basic = base64.b64encode(f"{user}:{password}".encode()).decode()
        body = self._req("POST", "/api/login", None, {"Authorization": f"Basic {basic}"})
        self.token = body.get("token", "")
        if not self.token:
            raise SystemExit("Login gav intet token — tjek PLC_USER/PLC_PASS")

    def _req(self, method: str, path: str, data: dict | None = None, headers: dict | None = None) -> dict:
        h = {"Content-Type": "application/json", **(headers or {})}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        raw = json.dumps(data).encode() if data is not None else (b"" if method == "POST" else None)
        req = urllib.request.Request(self.base + path, data=raw, method=method, headers=h)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    txt = r.read().decode() or "{}"
                    return json.loads(txt)
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 3:   # PLC'ens rate-limiter: vent og prøv igen
                    time.sleep(1.5)
                    continue
                msg = e.read().decode(errors="replace")
                raise SystemExit(f"{method} {path} → HTTP {e.code}: {msg}")
            except urllib.error.URLError as e:
                raise SystemExit(f"{method} {path} → kan ikke nå PLC'en: {e.reason}")
        raise SystemExit(f"{method} {path} → for mange forsøg")

    def get(self, path: str) -> dict:
        return self._req("GET", path)

    def post(self, path: str, data: dict | None = None) -> dict:
        return self._req("POST", path, data)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # Windows-konsol
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check_only = "--check" in sys.argv
    if len(args) != 1:
        raise SystemExit(__doc__)
    user, password = os.environ.get("PLC_USER", ""), os.environ.get("PLC_PASS", "")
    if not user or not password:
        raise SystemExit("Sæt PLC_USER og PLC_PASS i miljøet")
    plc = Plc(args[0], user, password)

    sources = {pid: (HERE / f).read_text(encoding="utf-8") for pid, f in PROGRAMS.items()}
    globals_src = (HERE / "globals.st").read_text(encoding="utf-8")
    total = sum(len(s.encode()) for s in sources.values())
    status = plc.get("/api/logic")
    pool_total = status.get("pool_total") or (status.get("resources") or {}).get("pool_total")
    print(f"PLC {args[0]}: kildepulje {pool_total} bytes, demoen bruger {total} bytes")
    if pool_total and total > int(pool_total):
        raise SystemExit("Kildepuljen er for lille (PLC'en har ingen PSRAM?) — demoen kræver ca. 20 KB")
    if check_only:
        for p in status.get("programs", []):
            print(f"  Logic{p.get('id')}: {p.get('name')} enabled={p.get('enabled')} compiled={p.get('compiled')} "
                  f"interval={p.get('interval_ms')} fejl={p.get('error_count')}")
        return

    for pid in PROGRAMS:
        plc.post(f"/api/logic/{pid}/disable")
    r = plc.post("/api/logic/globals/source", {"source": globals_src})
    if not r.get("compiled", True) or r.get("compile_error"):
        raise SystemExit(f"GLOBAL_VAR: {r.get('compile_error') or r}")
    print(f"GLOBAL_VAR: {r.get('count')} variable")
    for pid, f in PROGRAMS.items():
        r = plc.post(f"/api/logic/{pid}/source", {"source": sources[pid]})
        if not r.get("compiled") or r.get("compile_error"):
            raise SystemExit(f"Logic{pid} ({f}): kompileringsfejl: {r.get('compile_error') or r}")
        plc.post(f"/api/logic/{pid}/interval", {"interval_ms": INTERVAL_MS})
        print(f"Logic{pid} ({f}): kompileret, {r.get('instr_count')} instruktioner")
    for pid in PROGRAMS:
        plc.post(f"/api/logic/{pid}/enable")

    time.sleep(3)
    bad = False
    for pid in PROGRAMS:
        info = plc.get(f"/api/logic/{pid}")
        stats = plc.get(f"/api/logic/{pid}/stats")
        ok = info.get("enabled") and info.get("compiled") and not stats.get("error_count")
        bad |= not ok
        print(f"Logic{pid}: {'OK' if ok else 'FEJL'} — {len(info.get('variables') or [])} variable, "
              f"udført {stats.get('execution_count')}×, fejl {stats.get('error_count')}, "
              f"maks {stats.get('max_execution_us')} µs")
    if bad:
        raise SystemExit("Mindst ét program kører ikke korrekt — se PLC'ens ST-editor/Runtime Monitor")
    print("Demo-varmeanlægget kører.")


if __name__ == "__main__":
    main()
