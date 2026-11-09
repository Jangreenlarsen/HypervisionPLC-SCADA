"""Signalveje: grænser og kontrol af en signalvejs `data` (fra en backup). Del af services/signal_paths (v4.15.1)."""

from __future__ import annotations

import json
from typing import Any

from ..symbols import MAX_LOGIC, MAX_LOGIC_INPUTS

MAX_CONDITIONS = MAX_LOGIC_INPUTS + (MAX_LOGIC - 1) * (MAX_LOGIC_INPUTS - 1)   # 4 + 7·3 = 25 (8 blokke i kæde)
MAX_ELEMENTS = 200
MAX_ENDS = 4          # slutpunkter (grene) pr. signalvej (v4.13.0)
MAX_ANIMS = 16        # ekstra animationer pr. element (v4.14.0)
# Animationer en signalvej kan lægge på delene (v4.14.0): løbelys kommer fra `flows` (rør), de øvrige fra `anims`. "Gennemsigtighed"
# (opacity) kræver et tal-tag og kan derfor ikke styres af en logikblok — brug Synlig.
PATH_ANIMS = ("flow", "fill", "stroke", "blink", "visible", "spin")
MAX_UI_CHARS = 8000   # guidens valg (vejvalg m.m.) gemmes sammen med vejen — samme grænse i API og backup


def valid_data(d: Any) -> str | None:
    """Kontrol af en signalvejs `data` (fra en backup): → fejltekst eller None."""
    if not isinstance(d, dict):
        return "data skal være et objekt"
    for k in ("start", "end", "owner", "final"):
        if not isinstance(d.get(k, ""), str):
            return f"{k} skal være tekst"
    if not isinstance(d.get("blocks", []), list) or not all(isinstance(b, str) for b in d.get("blocks", [])):
        return "blocks skal være en liste af blok-id'er"
    if not isinstance(d.get("created", []), list) or not all(isinstance(b, str) for b in d.get("created", [])):
        return "created skal være en liste af element-id'er"
    els = d.get("elements", [])
    if not isinstance(els, list):
        return "elements skal være en liste"
    for e in els:
        if not isinstance(e, dict) or not isinstance(e.get("element"), str) or not isinstance(e.get("flows", []), list):
            return "hvert element skal have element og flows"
        if not all(isinstance(f, dict) and isinstance(f.get("part"), str) for f in e.get("flows", [])):
            return "hver flow skal have en del (part)"
        an = e.get("anims", [])
        if not isinstance(an, list) or not all(isinstance(a, dict) and isinstance(a.get("part"), str) and a.get("type") in PATH_ANIMS
                                               and isinstance(a.get("params", {}), dict) for a in an):
            return "anims skal være en liste af {part, type, params}"
    if not isinstance(d.get("conditions", []), list) or not isinstance(d.get("style", {}), dict):
        return "conditions skal være en liste og style et objekt"
    ends = d.get("ends", [])
    if not isinstance(ends, list) or len(ends) > MAX_ENDS or not all(isinstance(x, str) for x in ends):
        return f"ends skal være en liste af højst {MAX_ENDS} element-id'er"
    for e in els:
        br = e.get("branches", [0])
        if not isinstance(br, list) or not all(isinstance(b, int) and not isinstance(b, bool) and 0 <= b < MAX_ENDS for b in br):
            return "branches skal være en liste af gren-numre"
        if not isinstance(e.get("block", ""), str):
            return "block skal være tekst"
    if not isinstance(d.get("ui", {}), dict) or len(json.dumps(d.get("ui", {}), default=str)) > MAX_UI_CHARS:
        return "ui skal være et lille objekt"
    blocks = set(d.get("blocks", []))
    for e in els:
        if e.get("block", "") not in blocks | {""}:
            return "block skal være tom eller en af vejens blokke"
    for c in d.get("conditions", []):
        br = c.get("branches") if isinstance(c, dict) else None
        if br is not None and (not isinstance(br, list) or not all(isinstance(b, int) and not isinstance(b, bool) and 0 <= b < MAX_ENDS for b in br)):
            return "conditions[].branches skal være en liste af gren-numre"
    return None
