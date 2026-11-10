"""Signalveje: grænser og kontrol af en signalvejs `data` (gemt objekt og backup). Del af services/signal_paths (v5.0.0).

En signalvej er sit eget objekt (v5.0.0): intet skrives i symbolernes opsætning. `data`:

    {start, end, ends: [..],                       # start og slutpunkter (grenene: end, ends[0], …)
     elements: [{element, branches: [b],          # elementerne på vejen og de grene, der går igennem dem
                 flows: [{part, reverse}],        # løbelys på delene (rør, bøjninger, T-stykkets ben)
                 anims: [{part, type, params, when}]}],   # øvrige animationer (farve, blink, synlig, roterer)
     conditions: [{element, src, neg, cmp, value, branches: [b]}],   # hvornår en gren er aktiv (OG inden for grenen)
     style: {light, speed, dash}, ui: {…}}        # løbelysets udseende og guidens valg
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

MAX_CONDITIONS = 64   # pr. signalvej (alle grene); ingen logikblokke, så ingen grænse fra et ejer-symbol (v5.0.0)
MAX_ELEMENTS = 200
MAX_ENDS = 4          # slutpunkter (grene) pr. signalvej (v4.13.0)
MAX_ANIMS = 16        # ekstra animationer pr. element (v4.14.0)
# Animationer en signalvej kan lægge på delene: løbelys kommer fra `flows` (rør), de øvrige fra `anims`. Gennemsigtighed kræver
# et tal-tag og kan derfor ikke styres af vejen — brug Synlig.
PATH_ANIMS = ("flow", "fill", "stroke", "blink", "visible", "spin")
MAX_UI_CHARS = 8000   # guidens valg (vejvalg m.m.) gemmes sammen med vejen — samme grænse i API og backup
CMPS = ("", "ge", "le", "eq")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_ID = re.compile(r"^[^\s<>\"']{1,120}$")


def _branches(v: Any) -> bool:
    return isinstance(v, list) and 0 < len(v) <= MAX_ENDS and all(
        isinstance(b, int) and not isinstance(b, bool) and 0 <= b < MAX_ENDS for b in v)


def clean_params(kind: str, params: Any) -> dict[str, Any] | None:
    """Parametrene for en animation, som Overview forstår dem (samme som symbolernes egne) — None = ugyldige."""
    p = params if isinstance(params, dict) else {}
    if kind in ("fill", "stroke"):
        on = p.get("on")
        return {"on": on} if isinstance(on, str) and _COLOR.match(on) else None
    if kind == "blink":
        speed = p.get("speed", "normal")
        return {"speed": speed} if speed in ("slow", "normal", "fast") else None
    return {}      # visible, spin: ingen parametre


def valid_data(d: Any) -> str | None:
    """Kontrol af en signalvejs `data` (fra API'et efter normalisering, eller en backup): → fejltekst eller None."""
    if not isinstance(d, dict):
        return "data skal være et objekt"
    if "owner" in d or "blocks" in d:
        return "signalvejen har det gamle format (før v5.0.0)"
    for k in ("start", "end"):
        if not isinstance(d.get(k), str) or not _ID.match(d[k]):
            return f"{k} skal være et element-id"
    ends = d.get("ends", [])
    if not isinstance(ends, list) or len(ends) > MAX_ENDS or not all(isinstance(x, str) and _ID.match(x) for x in ends):
        return f"ends skal være en liste af højst {MAX_ENDS} element-id'er"
    nb = len(dict.fromkeys([d["end"], *ends]))
    els = d.get("elements")
    if not isinstance(els, list) or not els or len(els) > MAX_ELEMENTS:
        return f"elements skal være en liste med 1–{MAX_ELEMENTS} elementer"
    for e in els:
        if not isinstance(e, dict) or not isinstance(e.get("element"), str) or not _ID.match(e["element"]):
            return "hvert element skal have et element-id"
        if not _branches(e.get("branches")) or max(e["branches"]) >= nb:
            return "branches skal være en liste af gren-numre"
        flows = e.get("flows", [])
        if not isinstance(flows, list) or len(flows) > 8 or not all(
                isinstance(f, dict) and isinstance(f.get("part"), str) and _ID.match(f["part"]) and isinstance(f.get("reverse", False), bool)
                for f in flows):
            return "flows skal være en liste af {part, reverse}"
        anims = e.get("anims", [])
        if not isinstance(anims, list) or len(anims) > MAX_ANIMS:
            return f"anims skal være en liste med højst {MAX_ANIMS}"
        for a in anims:
            if (not isinstance(a, dict) or not isinstance(a.get("part"), str) or not _ID.match(a["part"])
                    or a.get("type") not in PATH_ANIMS[1:] or clean_params(a["type"], a.get("params")) is None
                    or not isinstance(a.get("when", True), bool)):
                return "anims skal være en liste af {part, type, params, when}"
    conds = d.get("conditions", [])
    if not isinstance(conds, list) or len(conds) > MAX_CONDITIONS:
        return f"conditions skal være en liste med højst {MAX_CONDITIONS}"
    for c in conds:
        if (not isinstance(c, dict) or not isinstance(c.get("src"), str) or not c["src"] or c["src"].startswith("@")
                or c.get("cmp", "") not in CMPS or not isinstance(c.get("neg", False), bool)
                or not _branches(c.get("branches")) or max(c["branches"]) >= nb):
            return "hver betingelse skal have et tag, en sammenligning og gyldige grene"
        v = c.get("value")
        if c.get("cmp") and (not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)):
            return "en sammenligning kræver en grænseværdi"
    style = d.get("style", {})
    if not isinstance(style, dict) or not isinstance(style.get("light", "#8fc8ea"), str) or not _COLOR.match(style.get("light", "#8fc8ea")):
        return "style.light skal være en farve (#rrggbb)"
    for k, lo, hi in (("speed", 5, 500), ("dash", 2, 200)):
        v = style.get(k, lo)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
            return f"style.{k} skal være mellem {lo} og {hi}"
    if not isinstance(d.get("ui", {}), dict) or len(json.dumps(d.get("ui", {}), default=str)) > MAX_UI_CHARS:
        return "ui skal være et lille objekt"
    return None
