"""Konsistenskontrol af alle tegninger på en SCADA-server — KUN LÆSNING (v6.9.2, analysen 2026-11-13).

Kører de samme beregninger som Overview og simulatoren (simulate skriver intet til PLC'en) og melder pr. tegning:
gamle symbolopsætninger, standardgruppens løbelys, bindinger til elementer der ikke findes, tags der mangler,
om forbindelserne er bundet, og flowberegningens beskeder. Bruges efter hver deploy, så en ændring ses på de rigtige
tegninger og ikke kun på testdata.

    SCADA_USER=<bruger> SCADA_PASS=<adgangskode> python deploy/audit_drawings.py https://scada.laces.dk

Adgangskoden gives kun som miljøvariabel (CLAUDE.md regel 3).
"""
from __future__ import annotations

import collections
import os
import re
import sys

import httpx

INTERNAL = ("@", "sym:", "flow:", "flowp:", "flowlvl:", "alarm:", "path:")


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    c = httpx.Client(base_url=base, timeout=60)
    r = c.post("/api/auth/login", json={"username": os.environ["SCADA_USER"], "password": os.environ["SCADA_PASS"]})
    if r.status_code != 200:
        print(f"Login fejlede: {r.status_code}")
        return 2
    tags = {t["name"] for t in c.get("/api/tags").json()}
    problems = 0
    for d in c.get("/api/drawings").json():
        did = d["id"]
        v = c.get(f"/api/drawings/{did}/view").json()
        ids = set(re.findall(r'\bid="([^"]+)"', v["svg"]))
        orph = c.get(f"/api/drawings/{did}/symbols-orphaned").json()
        notes = c.post(f"/api/drawings/{did}/simulate", json={"values": {}, "positions": {}}).json().get("notes", [])
        used = {k for b in v["bindings"] for k in (b.get("tag"), (b.get("params") or {}).get("dir_tag"))
                if k and not k.startswith(INTERNAL)}
        missing_tags = sorted(used - tags)
        no_element = sorted({b["element"] for b in v["bindings"] if b["element"] not in ids})
        group = dict(collections.Counter(b["anim"] for b in v["bindings"] if b.get("source") == "conn-group"))
        linked = "data-hv-links" in v["svg"]
        flags = []
        if orph:
            flags.append(f"{len(orph)} gamle opsætninger")
        if group and not linked:
            flags.append("standardgruppe uden bundne forbindelser")
        if no_element:
            flags.append(f"bindinger uden element: {', '.join(no_element[:5])}")
        if missing_tags:
            flags.append(f"manglende tags: {', '.join(missing_tags[:5])}")
        flags += [f"flow: {n}" for n in notes]
        problems += bool(flags)
        print(f"{'!!' if flags else 'ok'} {did}: bindinger={len(v['bindings'])} standardgruppe={group} bundet={linked}"
              + (f"\n     - " + "\n     - ".join(flags) if flags else ""))
    print(f"\n{problems} tegning(er) med noget at se på.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
