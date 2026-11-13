"""Ind/ud og veje pr. symboltype til flowberegningen (v6.1.0): standarderne for de indbyggede symboler + de rettede definitioner
(services/symbol_flow.py, gemt pr. symboltype), som går forud for standarderne.

Standarderne er de samme som i frontend (lib/symbolFlow.ts, FLOW_DEFAULTS) — hold dem i takt. Punkterne er brøkdele [x, y] af
symbolets egen boks; et punkt på et symbol i tegningen (fra en gemt forbindelse, nøglen "x,y") hører til den nærmeste definition
inden for MATCH_TOL.

**Retning:** en vej mellem to punkter kan løbe fra et punkt med rollen *ind* eller *begge* til et punkt med rollen *ud* eller
*begge*. En pumpe og en kontraventil (IND/UD) giver derfor kun flow ind → ud; en 3-vejsventil (alle *begge*) giver AB ↔ A og AB ↔ B.
"""

from __future__ import annotations

import math
from typing import Any

MATCH_TOL = 0.2


def _in_out(y: float) -> list[dict[str, Any]]:
    return [{"x": 0, "y": y, "name": "IND", "role": "in"}, {"x": 1, "y": y, "name": "UD", "role": "out"}]


# Tilstande (v6.6.0, Jan): tilstand 1 = A igennem AB (B blokeret), tilstand 2 = B igennem AB (A blokeret)
THREE_WAY_STATES: list[dict[str, Any]] = [{"name": "A → AB", "open": ["AB>A"]}, {"name": "B → AB", "open": ["AB>B"]}]

DEFAULTS: dict[str, dict[str, Any]] = {
    "pumpe": {"ports": _in_out(0.5), "kind": "pump"},
    "kontraventil": {"ports": _in_out(0.67)},
    "trevejs_motorventil": {"ports": [
        {"x": 0.07, "y": 0.46, "name": "A", "role": "both", "part": "port_a"},
        {"x": 0.46, "y": 0.08, "name": "B", "role": "both", "part": "port_b"},
        {"x": 0.84, "y": 0.46, "name": "AB", "role": "both", "common": True, "part": "port_ab"}], "states": THREE_WAY_STATES},
    "trevejs_motorventil_ab": {"ports": [
        {"x": 0.07, "y": 0.5, "name": "A", "role": "both", "part": "port_a"},
        {"x": 0.85, "y": 0.5, "name": "B", "role": "both", "part": "port_b"},
        {"x": 0.46, "y": 0.86, "name": "AB", "role": "both", "common": True, "part": "port_ab"}], "states": THREE_WAY_STATES},
    "trevejsventil": {"ports": [
        {"x": 0, "y": 0.44, "name": "A", "role": "both"}, {"x": 1, "y": 0.44, "name": "B", "role": "both"},
        {"x": 0.5, "y": 1, "name": "AB", "role": "both", "common": True}], "states": THREE_WAY_STATES},
    # 4-vejsventil (v6.6.0, Jan): tilstand 1 = A igennem B (C og D blokeret), tilstand 2 = C igennem D (A og B blokeret)
    "firevejsventil": {"ports": [
        {"x": 0, "y": 0.5, "name": "A", "role": "both", "part": "port_a"},
        {"x": 1, "y": 0.5, "name": "B", "role": "both", "part": "port_b"},
        {"x": 0.5, "y": 0, "name": "C", "role": "both", "part": "port_c"},
        {"x": 0.5, "y": 1, "name": "D", "role": "both", "part": "port_d"}],
        "ways": [["A", "B"], ["C", "D"]],
        "states": [{"name": "A → B", "open": ["A>B"]}, {"name": "C → D", "open": ["C>D"]}]},
}

# Symboltyper, der er rørstykker (hører under "forbindelser") — samme liste som scada-core.js og signalpath/graph.ts
PIPE_SYMBOL_TYPES = frozenset({"roer_l", "roer_v", "boejning45", "boejning90", "t_stykke", "kryds", "reduktion", "flange",
                               "ledning_l", "ledning_v", "forbindelse", "klemme"})
# Typer, der som standard er en pumpe (kan ændres pr. symbol i guiden)
PUMP_TYPES = frozenset({"pumpe"})


def merged(custom: dict[str, dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {**DEFAULTS, **(custom or {})}


# Medie → enheden, flowet vises i (v6.3.0) — kun visning; beregningen regner i "enheder" uanset medie
UNITS = {"water": "l/min", "air": "m³/h", "electric": "A", "other": ""}


def kind_of(defs: dict[str, dict[str, Any]], sym_type: str) -> str:
    """Typens rolle: pump | piece | consumer. Rørstykker er de indbyggede + typer med rollen rørstykke (v6.3.0)."""
    d = defs.get(sym_type) or {}
    if d.get("kind") in ("pump", "piece", "consumer"):
        return d["kind"]
    return "piece" if sym_type in PIPE_SYMBOL_TYPES else "pump" if sym_type in PUMP_TYPES else "consumer"


def piece_types(defs: dict[str, dict[str, Any]]) -> frozenset[str]:
    """Alle rørstykke-typer: de indbyggede (medmindre en profil siger noget andet) + typer med rollen rørstykke."""
    return frozenset({t for t in PIPE_SYMBOL_TYPES if kind_of(defs, t) == "piece"} |
                     {t for t, d in defs.items() if d.get("kind") == "piece"})


def unit_of(defs: dict[str, dict[str, Any]], sym_type: str) -> str:
    return UNITS.get(str((defs.get(sym_type) or {}).get("medium") or "water"), "")


def ways_of(d: dict[str, Any] | None) -> list[tuple[str, str]]:
    """Vejene gennem symbolet: de angivne, ellers hver fælles port parret med hver ikke-fælles; uden fælles port alle par."""
    if not d:
        return []
    if d.get("ways"):
        return [(str(a), str(b)) for a, b in d["ways"]]
    names = [p["name"] for p in d.get("ports", [])]
    common = [p["name"] for p in d.get("ports", []) if p.get("common")]
    if common:
        return [(c, r) for c in common for r in names if r not in common]
    return [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]


def way_key(a: str, b: str) -> str:
    return f"{a}>{b}"


def directions(d: dict[str, Any], a: str, b: str) -> tuple[bool, bool]:
    """(a → b tilladt, b → a tilladt) ud fra punkternes roller."""
    role = {p["name"]: p.get("role", "both") for p in d.get("ports", [])}
    ra, rb = role.get(a, "both"), role.get(b, "both")
    return (ra in ("in", "both") and rb in ("out", "both"), rb in ("in", "both") and ra in ("out", "both"))


def parse_frac(key: str) -> tuple[float, float] | None:
    try:
        x, y = (float(v) for v in key.split(","))
    except ValueError:
        return None
    return (x, y) if math.isfinite(x) and math.isfinite(y) else None


def match_ports(d: dict[str, Any] | None, keys: list[str]) -> dict[str, str]:
    """{forbindelsesnøgle ("x,y") → punktets navn}: den nærmeste definition inden for MATCH_TOL, hver højst én gang."""
    if not d:
        return {}
    pairs: list[tuple[float, str, int]] = []
    for key in keys:
        f = parse_frac(key)
        if f is None:
            continue
        for k, p in enumerate(d.get("ports", [])):
            pairs.append((math.hypot(f[0] - p["x"], f[1] - p["y"]), key, k))
    pairs.sort()
    out: dict[str, str] = {}
    taken: set[int] = set()
    for dist, key, k in pairs:
        if dist > MATCH_TOL or key in out or k in taken:
            continue
        out[key] = d["ports"][k]["name"]
        taken.add(k)
    return out
