"""Signalveje: grænser og kontrol af en signalvejs `data` (gemt objekt og backup). Del af services/signal_paths.

Fra v6.0.0 **definerer** en signalvej kun, hvad den består af — hvornår den er aktiv, og hvordan den ser ud, hører til vejens symbol-
opsætning (`sv~<id>`, symbol-guidens 6 trin). `data`:

    {start, end, ends: [..],                       # start og slutpunkter (grenene: end, ends[0], …)
     elements: [{element, branches: [b],          # elementerne på vejen og de grene, der går igennem dem
                 flows: [{part, reverse}]}],      # delene, flowet løber igennem, og retningen (reverse) — til "Tilføj løbelys langs vejen"
     ui: {…}}                                     # guidens valg (vejvalg), så vejen kan rettes

Ældre veje (v4.2–v5.12) har også `conditions`, `style` og `elements[].anims`: de kendes stadig i en gemt vej/backup (de ignoreres), og
`strip_legacy` fjerner dem (opgraderingen til v6.0.0).
"""

from __future__ import annotations

import json
import re
from typing import Any

MAX_ELEMENTS = 200
MAX_ENDS = 4          # slutpunkter (grene) pr. signalvej (v4.13.0)
MAX_UI_CHARS = 8000   # guidens valg (vejvalg m.m.) gemmes sammen med vejen — samme grænse i API og backup
_ID = re.compile(r"^[^\s<>\"']{1,120}$")


def _branches(v: Any) -> bool:
    return isinstance(v, list) and 0 < len(v) <= MAX_ENDS and all(
        isinstance(b, int) and not isinstance(b, bool) and 0 <= b < MAX_ENDS for b in v)


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
    if not isinstance(d.get("ui", {}), dict) or len(json.dumps(d.get("ui", {}), default=str)) > MAX_UI_CHARS:
        return "ui skal være et lille objekt"
    return None


def strip_legacy(d: dict[str, Any]) -> dict[str, Any]:
    """Vejens definition uden det, der hørte til før v6.0.0 (betingelser, udseende, egne animationer, markører)."""
    return {"start": d["start"], "end": d["end"], "ends": list(d.get("ends") or []),
            "elements": [{"element": e["element"], "branches": list(e.get("branches") or [0]), "flows": list(e.get("flows") or [])}
                         for e in d.get("elements", [])],
            "ui": d.get("ui") or {}}


def is_legacy(d: dict[str, Any]) -> bool:
    """Har vejen noget fra før v6.0.0 (betingelser, udseende, animationer, markør)?"""
    return bool(d.get("conditions") or d.get("style") or d.get("materialized") or any("anims" in e for e in d.get("elements", [])))
