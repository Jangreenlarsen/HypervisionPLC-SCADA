"""Navngivne symbolgrupper (v0.130.0): et udvalg af elementer på en tegning, gemt under et navn. Samme element må være med i
flere grupper. Gruppen ændrer ikke tegningen eller elementernes opsætning — den samler dem til at markere og vælge."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from ..storage.db import Database
from .errors import ServiceError

log = logging.getLogger("scada.symbol_groups")

GROUP_KINDS = ("function", "selection")   # funktion (fx "Fyr uden akku-tank") / frit udvalg
MAX_GROUP_NAME = 60
MAX_GROUP_MEMBERS = 500
MAX_GROUPS = 200


def clean_members(members: list[str]) -> list[str]:
    """Rækkefølgen bevares; dubletter fjernes."""
    out = list(dict.fromkeys(m.strip() for m in members if m and m.strip()))
    if any(len(m) > 120 for m in out):
        raise ServiceError(400, "Et elements id er for langt (højst 120 tegn)")
    if len(out) > MAX_GROUP_MEMBERS:
        raise ServiceError(400, f"En gruppe kan højst have {MAX_GROUP_MEMBERS} elementer")
    return out


class SymbolGroupService:
    def __init__(self, db: Database):
        self.db = db

    def list(self, drawing_id: str) -> list[dict[str, Any]]:
        return self.db.list_symbol_groups(drawing_id)

    def _check_name(self, name: str, kind: str) -> str:
        name = name.strip()
        if not name:
            raise ServiceError(400, "Gruppen skal have et navn")
        if len(name) > MAX_GROUP_NAME:
            raise ServiceError(400, f"Gruppens navn må højst være {MAX_GROUP_NAME} tegn")
        if kind not in GROUP_KINDS:
            raise ServiceError(400, "Ukendt art — vælg 'function' eller 'selection'")
        return name

    def save(self, user: str, drawing_id: str, group_id: int | None, name: str, kind: str,
             members: list[str] | None) -> dict[str, Any]:
        name = self._check_name(name, kind)
        clean = clean_members(members) if members is not None else None
        if group_id is None and len(self.db.list_symbol_groups(drawing_id)) >= MAX_GROUPS:
            raise ServiceError(400, f"Der kan højst være {MAX_GROUPS} grupper pr. tegning")
        try:
            gid = self.db.save_symbol_group(drawing_id, group_id, name, kind, clean, user)
        except sqlite3.IntegrityError:
            raise ServiceError(409, f"Der findes allerede en gruppe med navnet '{name}' på tegningen") from None
        if gid is None:
            raise ServiceError(404, "Gruppen findes ikke")
        log.info("Symbolgruppe gemt: tegning=%s gruppe=%s (%s) medlemmer=%s bruger=%s", drawing_id, name, kind,
                 len(clean) if clean is not None else "uændret", user)
        return self.db.get_symbol_group(drawing_id, gid)  # type: ignore[return-value]

    def delete(self, user: str, drawing_id: str, group_id: int) -> str:
        group = self.db.get_symbol_group(drawing_id, group_id)
        if group is None:
            raise ServiceError(404, "Gruppen findes ikke")
        self.db.delete_symbol_group(drawing_id, group_id)
        log.info("Symbolgruppe slettet: tegning=%s gruppe=%s bruger=%s", drawing_id, group["name"], user)
        return group["name"]
