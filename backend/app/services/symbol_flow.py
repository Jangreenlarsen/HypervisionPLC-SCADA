"""Ind/ud, navne og veje på VVS-symboler (v4.13.0, PLAN.md › Signalveje 2).

Hvert tilslutningspunkt på en symboltype kan have et navn (A, B, AB …), en rolle (ind, ud, begge) og være "fælles". Et symbol har
desuden en liste af veje — de forbindelser, det kan lave (AB → A, AB → B). Bruges kun af signalveje (retning fra en pumpe,
vejvalg på en 3-vejsventil). Standarderne for de indbyggede symboler ligger i frontend (lib/symbolFlow.ts); her gemmes de
RETTEDE definitioner pr. symboltype, som går forud for dem.

Punkterne er brøkdele [x, y] af symbolets egen boks (som symbol_ports). Gemmes i `meta` (nøgle `symbolflow.<type>`) og følger med
i backup og gendannelse.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any

from ..storage.db import Database
from .errors import ServiceError
from .symbol_ports import MAX_TYPES, clean_type

log = logging.getLogger("scada.symbol_flow")

NAME_RE = re.compile(r"^[A-Za-z0-9_+-]{1,12}$")
PART_RE = re.compile(r"^[a-z0-9_]{1,40}$")
ROLES = ("in", "out", "both")
# Flow-profilen pr. symboltype (v6.3.0, PLAN.md › Flow-model runde 2): rollen i flowberegningen, mediet (til visning) og
# standarderne, når et symbol ikke har sin egen flow-opsætning i guiden. Gælder alle symboltyper — også elektriske komponenter
# (en strømforsyning er en kilde, ledninger og klemmer er rørstykker).
KINDS = ("consumer", "pump", "piece")
MEDIA = ("water", "air", "electric", "other")
MAX_PORTS = 12
MAX_WAYS = 24
MAX_STATES = 12
STATE_NAME_RE = re.compile(r"^[^\x00-\x1f]{1,30}\Z")


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 1


def clean_def(raw: Any) -> dict[str, Any]:
    """Kontrol og normalisering af en definition ({ports, ways}). Fejl → ServiceError(400) med en forståelig tekst."""
    if not isinstance(raw, dict):
        raise ServiceError(400, "Definitionen skal være et objekt med ports (og evt. ways)")
    ports_in = raw.get("ports")
    kind = raw.get("kind", "consumer") or "consumer"
    if kind not in KINDS:
        raise ServiceError(400, "Rollen skal være forbruger, pumpe/kilde eller rørstykke")
    medium = raw.get("medium", "water") or "water"
    if medium not in MEDIA:
        raise ServiceError(400, "Mediet skal være vand, luft, el eller andet")
    cap = raw.get("capacity")
    if cap is not None and not (isinstance(cap, int) and not isinstance(cap, bool) and 0 <= cap <= 65535):
        raise ServiceError(400, "Standard-kapaciteten skal være et helt tal mellem 0 og 65535")
    restrict = raw.get("restrict")
    if restrict is not None and not _num(restrict):
        raise ServiceError(400, "Standard-restriktionen skal være et tal mellem 0 og 1")
    profile = raw.get("kind") is not None or medium != "water" or cap is not None or restrict is not None
    if ports_in in (None, []) and profile:
        ports_in = []
    elif not isinstance(ports_in, list) or not ports_in:
        raise ServiceError(400, "Angiv mindst ét punkt")
    if len(ports_in) > MAX_PORTS:
        raise ServiceError(400, f"Højst {MAX_PORTS} punkter pr. symbol")
    ports: list[dict[str, Any]] = []
    names: set[str] = set()
    for i, p in enumerate(ports_in, 1):
        if not isinstance(p, dict) or not _num(p.get("x")) or not _num(p.get("y")):
            raise ServiceError(400, f"Punkt {i}: x og y skal være tal mellem 0 og 1 (brøkdel af symbolets boks)")
        name = p.get("name")
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise ServiceError(400, f"Punkt {i}: navnet må kun have bogstaver, tal og _ + - (højst 12 tegn)")
        if name in names:
            raise ServiceError(400, f"Navnet '{name}' er brugt to gange")
        names.add(name)
        role = p.get("role", "both")
        if role not in ROLES:
            raise ServiceError(400, f"Punkt '{name}': rollen skal være ind, ud eller begge")
        out: dict[str, Any] = {"x": round(float(p["x"]), 4), "y": round(float(p["y"]), 4), "name": name, "role": role}
        if p.get("common"):
            out["common"] = True
        part = p.get("part")
        if part not in (None, ""):
            if not isinstance(part, str) or not PART_RE.match(part):
                raise ServiceError(400, f"Punkt '{name}': delen skal være et id (små bogstaver, tal og _)")
            out["part"] = part
        ports.append(out)
    ways_in = raw.get("ways", [])
    if not isinstance(ways_in, list) or len(ways_in) > MAX_WAYS:
        raise ServiceError(400, f"ways skal være en liste (højst {MAX_WAYS} veje)")
    ways: list[list[str]] = []
    for w in ways_in:
        if not (isinstance(w, (list, tuple)) and len(w) == 2 and all(isinstance(x, str) for x in w)):
            raise ServiceError(400, "En vej skal være to punktnavne")
        a, b = w
        if a not in names or b not in names or a == b:
            raise ServiceError(400, f"Vejen {a} → {b} bruger et ukendt punkt")
        if [a, b] not in ways and [b, a] not in ways:
            ways.append([a, b])
    result: dict[str, Any] = {"ports": ports}
    if ways:
        result["ways"] = ways
    # Tilstande (v6.6.0, Jan): navngivne tilstande med de veje, der er åbne — fx "A → AB" = A igennem AB, B blokeret
    states_in = raw.get("states") or []
    if not isinstance(states_in, list) or len(states_in) > MAX_STATES:
        raise ServiceError(400, f"Tilstandene skal være en liste (højst {MAX_STATES})")
    if states_in:
        from .flow_defs import way_key, ways_of
        known = {frozenset(w): way_key(*w) for w in ways_of({"ports": ports, **({"ways": ways} if ways else {})})}
        states: list[dict[str, Any]] = []
        seen: set[str] = set()
        for i, st in enumerate(states_in, 1):
            if not isinstance(st, dict):
                raise ServiceError(400, f"Tilstand {i}: skal være et objekt med navn og åbne veje")
            name = " ".join(str(st.get("name") or "").split())
            if not STATE_NAME_RE.match(name):
                raise ServiceError(400, f"Tilstand {i}: giv den et navn (højst 30 tegn)")
            if name.casefold() in seen:
                raise ServiceError(400, f"Tilstanden '{name}' findes to gange")
            seen.add(name.casefold())
            opens = st.get("open") or []
            if not isinstance(opens, list) or not all(isinstance(w, str) for w in opens):
                raise ServiceError(400, f"Tilstanden '{name}': de åbne veje skal være en liste (fx \"AB>A\")")
            keys: list[str] = []
            for w in opens:
                a, _, b = w.partition(">")
                k = known.get(frozenset((a, b)))
                if k is None:
                    raise ServiceError(400, f"Tilstanden '{name}': vejen '{w}' findes ikke på symbolet")
                if k not in keys:
                    keys.append(k)
            states.append({"name": name, "open": keys})
        result["states"] = states
    if kind != "consumer" or raw.get("kind") == "consumer":   # en udtrykkelig forbruger (fx en indbygget pumpe-type)
        result["kind"] = kind
    if medium != "water":
        result["medium"] = medium
    if cap is not None:
        result["capacity"] = cap
    if restrict is not None:
        result["restrict"] = round(float(restrict), 3)
    return result


class SymbolFlowService:
    def __init__(self, db: Database):
        self.db = db

    def list(self) -> dict[str, dict[str, Any]]:
        return self.db.list_symbol_flow()

    def set(self, sym_type: str, raw: Any) -> dict[str, Any]:
        t = clean_type(sym_type)
        clean = clean_def(raw)
        existing = self.db.list_symbol_flow()
        if t not in existing and len(existing) >= MAX_TYPES:
            raise ServiceError(400, f"Højst {MAX_TYPES} symboler kan have rettede ind/ud-definitioner")
        self.db.set_symbol_flow(t, clean)
        log.info("Ind/ud-definition for %s gemt (%d punkter, %d veje, rolle %s, medie %s)", t, len(clean["ports"]), len(clean.get("ways", [])),
                 clean.get("kind", "consumer"), clean.get("medium", "water"))
        return clean

    def reset(self, sym_type: str) -> bool:
        t = clean_type(sym_type)
        had = self.db.set_symbol_flow(t, None)
        if had:
            log.info("Ind/ud-definition for %s nulstillet til standarden", t)
        return had
