"""Tags: CRUD og import. Samme validering bruges ved oprettelse, opdatering og import."""

from __future__ import annotations

import math
import re
from typing import Any

from .errors import ServiceError
from .manager import PlcManager
from .tagsource import TagSourceError, parse_source

TAG_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_TEXT_FIELDS = {"description": 200, "unit": 16}
WRITABLE_KINDS = ("hr", "coil")


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ServiceError(400, f"{field} skal være et endeligt tal")
    return float(value)


class TagService:
    def __init__(self, manager: PlcManager):
        self.manager = manager
        self.db = manager.db

    def list(self, plc: str | None = None) -> list[dict[str, Any]]:
        return [_public(t) for t in self.db.list_tags(plc=plc)]

    def get(self, name: str) -> dict[str, Any]:
        tag = self.db.get_tag(name)
        if tag is None:
            raise ServiceError(404, f"Tag '{name}' findes ikke")
        return _public(tag)

    def _validate(self, data: dict[str, Any], current: dict[str, Any] | None) -> dict[str, Any]:
        """Returnér de felter der skal skrives. `current` er None ved oprettelse."""
        out: dict[str, Any] = {}
        if current is None or data.get("source") is not None:
            try:
                source = parse_source(data.get("source"))  # type: ignore[arg-type]
            except TagSourceError as exc:
                raise ServiceError(400, str(exc)) from None
            if self.db.get_plc(source.plc) is None:
                raise ServiceError(400, f"Kilden peger på PLC '{source.plc}', som ikke findes")
            out["source"] = str(source)
            out["plc"] = source.plc
        for field, max_len in _TEXT_FIELDS.items():
            if data.get(field) is not None:
                text = str(data[field]).strip()
                if len(text) > max_len:
                    raise ServiceError(400, f"{field} må højst være {max_len} tegn")
                out[field] = text
        for field in ("scale", "offset"):
            if data.get(field) is not None:
                out[field] = _number(data[field], field)
        if out.get("scale") == 0:
            raise ServiceError(400, "scale må ikke være 0")
        if data.get("decimals") is not None:
            dec = data["decimals"]
            if isinstance(dec, bool) or not isinstance(dec, int) or not 0 <= dec <= 6:
                raise ServiceError(400, "decimals skal være et heltal 0-6")
            out["decimals"] = dec
        for flag in ("writable", "confirm_write"):
            if data.get(flag) is not None:
                out[flag] = bool(data[flag])
        # min/max: None betyder "ingen grænse" og er lovligt; 0 er en gyldig grænse.
        for field in ("min", "max"):
            if field in data:
                out[field] = None if data[field] is None else _number(data[field], field)
        lo = out["min"] if "min" in out else (current or {}).get("min")
        hi = out["max"] if "max" in out else (current or {}).get("max")
        if lo is not None and hi is not None and lo > hi:
            raise ServiceError(400, f"min ({lo}) må ikke være større end max ({hi})")
        # Skrivbarhed vurderes på den ENDELIGE tilstand (ny kilde og/eller nyt flag), så reglen
        # holder ved oprettelse, opdatering og import.
        final_source = parse_source(out.get("source") or (current or {}).get("source"))  # type: ignore[arg-type]
        final_writable = out["writable"] if "writable" in out else bool((current or {}).get("writable"))
        if final_writable and final_source.kind not in WRITABLE_KINDS:
            raise ServiceError(400, f"Kun hr- og coil-tags kan være skrivbare — '{final_source}' er kun-læs "
                                    "(ir/di er input, og PLC'ens REST API kan ikke skrive ST-variabler)")
        return out

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        name = data.get("name")
        if not isinstance(name, str) or not TAG_NAME_RE.match(name):
            raise ServiceError(400, "Tag-navn skal starte med bogstav/_ og kun indeholde bogstaver, tal og _ (max 64)")
        if self.db.get_tag(name) is not None:
            raise ServiceError(409, f"Tag '{name}' findes allerede")
        values = {"description": "", "unit": "", "scale": 1.0, "offset": 0.0, "decimals": None,
                  "writable": False, "min": None, "max": None, "confirm_write": True}
        values.update(self._validate(data, None))
        self.db.insert_tag(name, values)
        self.manager.reload_tags()
        return self.get(name)

    def update(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        current = self.db.get_tag(name)
        if current is None:
            raise ServiceError(404, f"Tag '{name}' findes ikke")
        changes = self._validate(data, current)
        self.db.update_tag(name, changes)
        self.manager.reload_tags()
        return self.get(name)

    def delete(self, name: str) -> None:
        used = self.db.count_bindings_for_tag(name)
        if used:
            raise ServiceError(409, f"Tagget '{name}' bruges i {used} binding(er) i tegninger — fjern dem først")
        if not self.db.delete_tag(name):
            raise ServiceError(404, f"Tag '{name}' findes ikke")
        self.manager.reload_tags(removed=[name])

    def import_many(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Opret flere tags; ét ugyldigt tag stopper ikke resten."""
        created: list[str] = []
        skipped: list[dict[str, str]] = []
        for item in items:
            name = item.get("name") if isinstance(item, dict) else None
            try:
                if not isinstance(item, dict):
                    raise ServiceError(400, "Hvert element skal være et objekt")
                values = {"description": "", "unit": "", "scale": 1.0, "offset": 0.0, "decimals": None,
                          "writable": False, "min": None, "max": None, "confirm_write": True}
                if not isinstance(name, str) or not TAG_NAME_RE.match(name):
                    raise ServiceError(400, "Ugyldigt tag-navn")
                if self.db.get_tag(name) is not None:
                    raise ServiceError(409, "Findes allerede")
                values.update(self._validate(item, None))
                self.db.insert_tag(name, values)
                created.append(name)
            except ServiceError as exc:
                skipped.append({"name": str(name), "reason": exc.message})
        if created:
            self.manager.reload_tags()
        return {"created": created, "skipped": skipped}


def _public(tag: dict[str, Any]) -> dict[str, Any]:
    return {k: tag[k] for k in ("name", "source", "plc", "description", "unit", "scale", "offset",
                                "decimals", "writable", "min", "max", "confirm_write")}
