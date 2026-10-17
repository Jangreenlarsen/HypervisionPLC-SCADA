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
LIMIT_FIELDS = ("alarm_ll", "alarm_l", "alarm_h", "alarm_hh")  # stigende rækkefølge
ALARM_DEFAULTS = {"alarm_hh": None, "alarm_h": None, "alarm_l": None, "alarm_ll": None,
                  "alarm_deadband": 0.0, "alarm_delay_s": 0.0, "alarm_on": None,
                  "trend": False, "trend_interval_s": 10.0, "energy": None, "energy_factor": 1.0}
WRITABLE_KINDS = ("hr", "coil")


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ServiceError(400, f"{field} skal være et endeligt tal")
    return float(value)


class TagService:
    def __init__(self, manager: PlcManager):
        self.manager = manager
        self.db = manager.db
        self.on_delete: Any = None  # fx trend-historikken der skal glemme tagget
        self.schedule_usage: Any = None  # navn → ugeprogrammer der skriver til tagget
        self.symbol_usage: Any = None    # navn → symboler (tegning#element) hvis konfiguration bruger tagget
        self.on_change: Any = None  # fx trend-opsamleren der skal læse historik-indstillingerne straks

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
            raise ServiceError(400, f"min ({lo:g}) må ikke være større end max ({hi:g})")
        self._validate_alarms(data, current, out)
        if data.get("trend") is not None:
            out["trend"] = bool(data["trend"])
        if data.get("trend_interval_s") is not None:
            iv = _number(data["trend_interval_s"], "trend_interval_s")
            if not 1 <= iv <= 3600:
                raise ServiceError(400, "Trend-interval skal være 1-3600 sekunder")
            out["trend_interval_s"] = iv
        self._validate_energy(data, current, out)
        # Skrivbarhed vurderes på den ENDELIGE tilstand (ny kilde og/eller nyt flag), så reglen
        # holder ved oprettelse, opdatering og import.
        final_source = parse_source(out.get("source") or (current or {}).get("source"))  # type: ignore[arg-type]
        final_writable = out["writable"] if "writable" in out else bool((current or {}).get("writable"))
        if current is not None and not final_writable and (names := self._schedules_using(current["name"])):
            raise ServiceError(400, f"Tagget bruges i ugeprogram: {', '.join(names)} — det skal være skrivbart")
        if final_writable and final_source.kind not in WRITABLE_KINDS:
            raise ServiceError(400, f"Kun hr- og coil-tags kan være skrivbare — '{final_source}' er kun-læs "
                                    "(ir/di er input, og PLC'ens REST API kan ikke skrive ST-variabler)")
        return out

    def _validate_energy(self, data: dict[str, Any], current: dict[str, Any] | None, out: dict[str, Any]) -> None:
        """Energi kræver historik og et tal-tag — vurderet på den endelige tilstand (også når historikken
        slås fra på et energi-tag, eller kilden ændres til til/fra)."""
        if "energy" in data:
            kind = data["energy"]
            if isinstance(kind, str):
                kind = kind.strip() or None
            if kind not in (None, "counter", "power"):
                raise ServiceError(400, "energy skal være null, 'counter' (tæller) eller 'power' (effekt)")
            out["energy"] = kind
        if data.get("energy_factor") is not None:
            f = _number(data["energy_factor"], "energy_factor")
            if not 0 < f <= 1_000_000:
                raise ServiceError(400, "Omregning til kWh skal være et positivt tal (fx 1 for kWh/kW, 0,001 for Wh/W)")
            out["energy_factor"] = f

        def final(field: str) -> Any:
            return out[field] if field in out else (current or {}).get(field)

        if final("energy") is None:
            return
        if not final("trend"):
            raise ServiceError(400, "Energi kræver at historik er slået til for tagget (rapporten beregnes ud fra historikken)")
        source = parse_source(out.get("source") or (current or {}).get("source"))  # type: ignore[arg-type]
        if source.datatype == "bool":
            raise ServiceError(400, "Energi kræver et tal-tag (tæller eller effekt) — ikke et til/fra-tag")

    def _validate_alarms(self, data: dict[str, Any], current: dict[str, Any] | None, out: dict[str, Any]) -> None:
        """Alarmgrænser — vurderet på den endelige tilstand (opret, opdatér og import bruger samme vej)."""
        for field in LIMIT_FIELDS:
            if field in data:
                out[field] = None if data[field] is None else _number(data[field], field)
        if data.get("alarm_deadband") is not None:
            db = _number(data["alarm_deadband"], "alarm_deadband")
            if db < 0:
                raise ServiceError(400, "Dødbånd kan ikke være negativt")
            out["alarm_deadband"] = db
        if data.get("alarm_delay_s") is not None:
            delay = _number(data["alarm_delay_s"], "alarm_delay_s")
            if not 0 <= delay <= 3600:
                raise ServiceError(400, "Alarmforsinkelse skal være 0-3600 sekunder")
            out["alarm_delay_s"] = delay
        if "alarm_on" in data:
            on = data["alarm_on"]
            if on not in (None, "true", "false"):
                raise ServiceError(400, "alarm_on skal være null, 'true' eller 'false'")
            out["alarm_on"] = on

        def final(field: str) -> Any:
            return out[field] if field in out else (current or {}).get(field)

        limits = [(f, final(f)) for f in LIMIT_FIELDS if final(f) is not None]
        for (f1, v1), (f2, v2) in zip(limits, limits[1:]):
            if v1 > v2:
                names = {"alarm_ll": "LL", "alarm_l": "L", "alarm_h": "H", "alarm_hh": "HH"}
                raise ServiceError(400, f"Alarmgrænserne skal stige: {names[f1]} ({v1:g}) er større end {names[f2]} ({v2:g})")
        source = parse_source(out.get("source") or (current or {}).get("source"))  # type: ignore[arg-type]
        if limits and source.datatype == "bool":
            raise ServiceError(400, "HH/H/L/LL-grænser kræver et tal-tag — brug 'alarm ved til/fra' for til/fra-tags")
        if limits and final("alarm_on") is not None:
            # alarmmotoren bruger kun til/fra-alarmen, når den er sat — grænserne ville blive stille ignoreret (BUGS v0.74.0)
            raise ServiceError(400, "Et tag kan ikke have både grænser (HH/H/L/LL) og til/fra-alarm — ryd den ene (grænser til tal, til/fra-alarm til til/fra-værdier)")
        if final("alarm_on") is not None and source.datatype not in ("bool", "auto"):
            raise ServiceError(400, "'Alarm ved til/fra' kræver et til/fra-tag (coil, di eller BOOL-variabel)")

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change()

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        name = data.get("name")
        if not isinstance(name, str) or not TAG_NAME_RE.match(name):
            raise ServiceError(400, "Tag-navn skal starte med bogstav/_ og kun indeholde bogstaver, tal og _ (max 64)")
        if self.db.get_tag(name) is not None:
            raise ServiceError(409, f"Tag '{name}' findes allerede")
        values = {"description": "", "unit": "", "scale": 1.0, "offset": 0.0, "decimals": None,
                  "writable": False, "min": None, "max": None, "confirm_write": True, **ALARM_DEFAULTS}
        values.update(self._validate(data, None))
        self.db.insert_tag(name, values)
        self.manager.reload_tags()
        self._changed()
        return self.get(name)

    def update(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        current = self.db.get_tag(name)
        if current is None:
            raise ServiceError(404, f"Tag '{name}' findes ikke")
        changes = self._validate(data, current)
        self.db.update_tag(name, changes)
        self.manager.reload_tags()
        self._changed()
        return self.get(name)

    def _schedules_using(self, name: str) -> list[str]:
        return self.schedule_usage(name) if self.schedule_usage is not None else []

    def delete(self, name: str) -> None:
        if names := self._schedules_using(name):
            raise ServiceError(409, f"Tagget '{name}' bruges i ugeprogram: {', '.join(names)} — slet eller ret dem først")
        if self.symbol_usage is not None and (symbols := self.symbol_usage(name)):
            raise ServiceError(409, f"Tagget '{name}' bruges af symbol: {', '.join(symbols[:5])}"
                                    f"{' …' if len(symbols) > 5 else ''} — ret dem under Bindinger først")
        used = self.db.count_bindings_for_tag(name)
        if used:
            raise ServiceError(409, f"Tagget '{name}' bruges i {used} binding(er) i tegninger — fjern dem først")
        if not self.db.delete_tag(name):
            raise ServiceError(404, f"Tag '{name}' findes ikke")
        self.manager.reload_tags(removed=[name])
        if self.on_delete is not None:
            self.on_delete(name)

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
                          "writable": False, "min": None, "max": None, "confirm_write": True, **ALARM_DEFAULTS}
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
            self._changed()
        return {"created": created, "skipped": skipped}


def _public(tag: dict[str, Any]) -> dict[str, Any]:
    return {k: tag[k] for k in ("name", "source", "plc", "description", "unit", "scale", "offset",
                                "decimals", "writable", "min", "max", "confirm_write", *ALARM_DEFAULTS)}
