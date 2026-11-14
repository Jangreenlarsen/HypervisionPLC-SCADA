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

import html
import json
from pathlib import Path

import httpx

SHARED = Path(__file__).resolve().parents[1] / "shared" / "flow_defaults.json"
INTERNAL = ("@", "sym:", "flow:", "flowp:", "flowlvl:", "alarm:", "path:")


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    c = httpx.Client(base_url=base, timeout=60)
    r = c.post("/api/auth/login", json={"username": os.environ["SCADA_USER"], "password": os.environ["SCADA_PASS"]})
    if r.status_code != 200:
        print(f"Login fejlede: {r.status_code}")
        return 2
    tags = {t["name"] for t in c.get("/api/tags").json()}
    # typernes punkter: standarderne + serverens egne (Ind/ud og veje) — til kontrollen af forældede forbindelser (v6.9.3)
    defs = json.loads(SHARED.read_text(encoding="utf-8"))["flow_defaults"]
    defs.update(c.get("/api/symbol-flow").json() or {})
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
        stale = []
        # (v6.9.3) en gemt forbindelse — på symbolet selv eller på røret, der peger på det — til et punkt, symbolet ikke har
        pts_of: dict[str, list[tuple[float, float]]] = {}
        for m in re.finditer(r"<[^>]*\bdata-hv-type=\"([^\"]+)\"[^>]*>", v["svg"]):
            tag = m.group(0)
            el_id = re.search(r'\bid="([^"]+)"', tag)
            fixed = re.search(r'\bdata-hv-ports="([^"]*)"', tag)
            pts = ([tuple(map(float, x.split(",")[:2])) for x in fixed.group(1).split(";") if x.count(",") >= 1] if fixed else
                   [(q["x"], q["y"]) for q in (defs.get(m.group(1)) or {}).get("ports", [])])
            if el_id and pts:
                pts_of[el_id.group(1)] = pts

        def off(el: str, key: str) -> bool:
            try:
                kx, ky = (float(x) for x in key.split(","))
            except ValueError:
                return False            # "s", "e", "~", "#n": rørender og andet — ikke et brøkpunkt
            return el in pts_of and min(abs(kx - x) + abs(ky - y) for x, y in pts_of[el]) > 0.08

        # (v6.11.3) rørenes ender: data-hv-from/-to — en gemt forbindelse til et andet element end det, enden sidder i, er forældet
        ends: dict[tuple[str, str], str] = {}
        for m in re.finditer(r"<[^>]*\bdata-hv-pipe=[^>]*>", v["svg"]):
            tag = m.group(0)
            el_id = re.search(r'\bid="([^"]+)"', tag)
            for key, attr in (("s", "data-hv-from"), ("e", "data-hv-to")):
                ref = re.search(rf'\b{attr}="([^"@]+)', tag)
                if el_id and ref and ref.group(1) in ids:
                    ends[(el_id.group(1), key)] = ref.group(1)

        for m in re.finditer(r'<[^>]*\bid="([^"]+)"[^>]*\bdata-hv-links="([^"]*)"|<[^>]*\bdata-hv-links="([^"]*)"[^>]*\bid="([^"]+)"', v["svg"]):
            own, text = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
            for part in html.unescape(text).split(";"):
                if ">" not in part or ":" not in part:
                    continue
                key, rest = part.split(">", 1)
                to, to_key = rest.rsplit(":", 1)
                if off(own, key):
                    stale.append(f"{own}:{key}")
                if off(to, to_key):
                    stale.append(f"{own}→{to}:{to_key}")
                ra, rb = ends.get((own, key)), ends.get((to, to_key))
                if not (ra and ra == rb) and ((ra and ra != to) or (rb and rb != own)):
                    stale.append(f"{own}:{key}→{to} (røret sidder i noget andet)")
        # (v6.12.1) to ens symboler præcis oven på hinanden (samme type og placering) — rørene deles mellem dem
        placed: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
        for m in re.finditer(r"<g\b[^>]*\bdata-hv-type=\"([^\"]+)\"[^>]*>", v["svg"]):
            el_id, tf = re.search(r'\bid="([^"]+)"', m.group(0)), re.search(r'\btransform="([^"]+)"', m.group(0))
            if el_id and tf:
                placed[(m.group(1), tf.group(1))].append(el_id.group(1))
        stacked = [" og ".join(ids) for ids in placed.values() if len(ids) > 1]
        flags = []
        if stacked:
            flags.append(f"symboler oven på hinanden: {', '.join(stacked[:5])}")
        if orph:
            flags.append(f"{len(orph)} gamle opsætninger")
        if group and not linked:
            flags.append("standardgruppe uden bundne forbindelser")
        if no_element:
            flags.append(f"bindinger uden element: {', '.join(no_element[:5])}")
        if stale:
            flags.append(f"forældede forbindelser (tryk Bind forbindelser i Tegn): {', '.join(stale[:5])}")
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
