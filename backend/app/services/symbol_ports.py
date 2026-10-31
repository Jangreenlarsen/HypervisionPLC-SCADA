"""Tilslutningspunkter pr. bibliotekssymbol (symbol-editoren, v2.16.0).

Rør i Tegn sættes fast i et symbols tilslutningspunkter. Som standard findes punkterne automatisk (rørender og kantmidter);
her kan en tekniker rette dem for en symboltype. Punkterne er brøkdele af symbolets egen boks ([fx, fy], 0..1).

Ændringen gælder kun symboler, der indsættes EFTER den — Tegn bygger punkterne ind i symbolet ved indsættelse
(data-hv-ports), så symboler, der allerede står i en tegning, beholder deres punkter.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any

from ..storage.db import Database
from .errors import ServiceError

log = logging.getLogger("scada.symbol_ports")

TYPE_RE = re.compile(r"^[a-z0-9_]{1,40}$")
MAX_PORTS = 32
MAX_TYPES = 500   # loft over antal symboltyper med rettede punkter (biblioteket har langt færre)


def clean_type(sym_type: Any) -> str:
    if not isinstance(sym_type, str) or not TYPE_RE.match(sym_type):
        raise ServiceError(400, "Ugyldig symboltype (små bogstaver, tal og _ — højst 40 tegn)")
    return sym_type


def clean_ports(ports: Any) -> list[list[float]]:
    """Punkterne afrundet til 4 decimaler, uden dubletter (rækkefølgen bevares). Fejl → ServiceError(400)."""
    if not isinstance(ports, list) or not ports:
        raise ServiceError(400, "Angiv mindst ét tilslutningspunkt — eller nulstil til de automatiske")
    if len(ports) > MAX_PORTS:
        raise ServiceError(400, f"Højst {MAX_PORTS} tilslutningspunkter pr. symbol")
    out: list[list[float]] = []
    for i, p in enumerate(ports):
        ok = isinstance(p, (list, tuple)) and len(p) == 2 and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in p)
        if not ok or not all(0 <= v <= 1 for v in p):
            raise ServiceError(400, f"Punkt {i + 1}: skal være [x, y] mellem 0 og 1 (brøkdel af symbolets boks)")
        q = [round(float(p[0]), 4), round(float(p[1]), 4)]
        if q not in out:
            out.append(q)
    return out


class SymbolPortService:
    def __init__(self, db: Database):
        self.db = db

    def list(self) -> dict[str, list[list[float]]]:
        return self.db.list_symbol_ports()

    def set(self, sym_type: str, ports: Any) -> list[list[float]]:
        t = clean_type(sym_type)
        clean = clean_ports(ports)
        existing = self.db.list_symbol_ports()
        if t not in existing and len(existing) >= MAX_TYPES:
            raise ServiceError(400, f"Højst {MAX_TYPES} symboler kan have rettede tilslutningspunkter")
        self.db.set_symbol_ports(t, clean)
        log.info("Tilslutningspunkter for %s gemt (%d)", t, len(clean))
        return clean

    def reset(self, sym_type: str) -> bool:
        t = clean_type(sym_type)
        had = self.db.set_symbol_ports(t, None)
        if had:
            log.info("Tilslutningspunkter for %s nulstillet til automatiske", t)
        return had
