"""Ugeprogrammer (lag 3): validering, opbevaring og afvikling.

Afvikling: hvert TICK_S sekund beregnes den ønskede værdi for hvert aktivt program. Ændrer den sig
(et skift, eller programmet er nyt/ændret), skrives den — men kun hvis PLC'en ikke allerede har den.
Mellem to skift røres tagget ikke, så en operatør kan overstyre manuelt indtil næste skift. Fejler en
skrivning (fx PLC nede), prøves igen efter RETRY_S, og fejlen vises på programmet.
Skrivning sker gennem OperateService: samme regler (skrivbar, min/max), tilbagelæsning og audit-log
(afsender "ugeprogram:<navn>").
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import date, datetime, timedelta
from typing import Any

from .auth import CurrentUser
from .errors import ServiceError
from .schedule_engine import DAY_NAMES, TZ, changes, desired, parse_hhmm, program_from, week_segments
from .tagsource import TagSourceError, parse_source

log = logging.getLogger(__name__)
TICK_S = 15.0
RETRY_S = 60.0
MAX_ENTRIES = 50
MAX_EXCEPTIONS = 100


def _is_bool_tag(tag: dict[str, Any]) -> bool:
    try:
        s = parse_source(tag["source"])
    except TagSourceError:
        return False
    return s.kind == "coil" or s.datatype == "bool"


def _value(v: Any, tag: dict[str, Any], where: str) -> float:
    if _is_bool_tag(tag):
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if v in (0, 1):
            return float(v)
        raise ServiceError(400, f"{where}: '{tag['name']}' er et til/fra-tag — værdien skal være Til eller Fra")
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ServiceError(400, f"{where}: værdien skal være et tal")
    # 0 er en gyldig grænse — derfor `is not None`
    if tag.get("min") is not None and v < tag["min"]:
        raise ServiceError(400, f"{where}: {v:g} er under tagets minimum {tag['min']:g}")
    if tag.get("max") is not None and v > tag["max"]:
        raise ServiceError(400, f"{where}: {v:g} er over tagets maksimum {tag['max']:g}")
    return float(v)


def validate_schedule(data: Any, tags: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Normalisér et ugeprogram. Bruges af API'et og ved restore af en backup (samme regler)."""
    if not isinstance(data, dict):
        raise ServiceError(400, "Ugeprogrammet skal være et objekt")
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 60:
        raise ServiceError(400, "Navn skal udfyldes (højst 60 tegn)")
    tag = tags.get(str(data.get("tag") or ""))
    if tag is None:
        raise ServiceError(400, f"Tagget '{data.get('tag')}' findes ikke")
    if not tag.get("writable"):
        raise ServiceError(400, f"Tagget '{tag['name']}' er ikke skrivbart — markér det skrivbart under Tags")
    entries_in = data.get("entries") or []
    exceptions_in = data.get("exceptions") or []
    if not isinstance(entries_in, list) or len(entries_in) > MAX_ENTRIES:
        raise ServiceError(400, f"Højst {MAX_ENTRIES} perioder")
    if not isinstance(exceptions_in, list) or len(exceptions_in) > MAX_EXCEPTIONS:
        raise ServiceError(400, f"Højst {MAX_EXCEPTIONS} undtagelser")
    entries = []
    for i, e in enumerate(entries_in, 1):
        where = f"Periode {i}"
        if not isinstance(e, dict):
            raise ServiceError(400, f"{where}: ugyldig")
        days = e.get("days")
        if not isinstance(days, list) or not days or any(isinstance(d, bool) or d not in range(1, 8) for d in days):
            raise ServiceError(400, f"{where}: vælg mindst én ugedag")
        try:
            start, end = parse_hhmm(str(e.get("start"))), parse_hhmm(str(e.get("end")))
        except ValueError as exc:
            raise ServiceError(400, f"{where}: {exc}") from None
        if start == end or start == 1440:
            raise ServiceError(400, f"{where}: start og slut skal være forskellige (brug 00:00-24:00 for hele døgnet)")
        entries.append({"days": sorted(set(days)), "start": e["start"], "end": e["end"], "value": _value(e.get("value"), tag, where)})
    exceptions = []
    for i, x in enumerate(exceptions_in, 1):
        where = f"Undtagelse {i}"
        if not isinstance(x, dict):
            raise ServiceError(400, f"{where}: ugyldig")
        try:
            d0, d1 = date.fromisoformat(str(x.get("date_from"))), date.fromisoformat(str(x.get("date_to")))
        except ValueError:
            raise ServiceError(400, f"{where}: datoer skal være ÅÅÅÅ-MM-DD") from None
        if d0 > d1:
            raise ServiceError(400, f"{where}: fra-dato er efter til-dato")
        value = None if x.get("value") is None else _value(x["value"], tag, where)
        exceptions.append({"date_from": d0.isoformat(), "date_to": d1.isoformat(), "value": value,
                           "note": str(x.get("note") or "")[:60]})
    default = data.get("default_value")
    default = None if default is None else _value(default, tag, "Standardværdi")
    if not entries and default is None and not exceptions:
        raise ServiceError(400, "Tilføj mindst én periode eller en standardværdi")
    return {"name": name, "tag": tag["name"], "enabled": bool(data.get("enabled", True)), "default_value": default,
            "entries": entries, "exceptions": exceptions}


class ScheduleService:
    def __init__(self, db: Any, operate: Any, manager: Any):
        self.db = db
        self.operate = operate
        self.manager = manager
        self._state: dict[int, dict[str, Any]] = {}  # id → {target, done, error, last_write, retry_at}
        self._wake = asyncio.Event()
        self.actor_prefix = "ugeprogram:"
        self.paused = False  # kun til tests: baggrundsløkken springer gennemløb over

    def _tags(self) -> dict[str, dict[str, Any]]:
        return {t["name"]: t for t in self.db.list_tags()}

    # ------------------------------------------------------------------ CRUD

    def list(self) -> list[dict[str, Any]]:
        now = datetime.now(TZ)
        return [self._public(s, now) for s in self.db.list_schedules()]

    def get(self, sid: int) -> dict[str, Any]:
        s = self.db.get_schedule(sid)
        if s is None:
            raise ServiceError(404, f"Ugeprogram {sid} findes ikke")
        return self._public(s, datetime.now(TZ))

    def create(self, data: Any) -> dict[str, Any]:
        clean = validate_schedule(data, self._tags())
        if self.db.get_schedule_by_name(clean["name"]):
            raise ServiceError(409, f"Der findes allerede et ugeprogram med navnet '{clean['name']}'")
        sid = self.db.insert_schedule(clean)
        self._changed(sid)
        return self.get(sid)

    def update(self, sid: int, data: Any) -> dict[str, Any]:
        if self.db.get_schedule(sid) is None:
            raise ServiceError(404, f"Ugeprogram {sid} findes ikke")
        clean = validate_schedule(data, self._tags())
        other = self.db.get_schedule_by_name(clean["name"])
        if other and other["id"] != sid:
            raise ServiceError(409, f"Der findes allerede et ugeprogram med navnet '{clean['name']}'")
        self.db.update_schedule(sid, clean)
        self._changed(sid)
        return self.get(sid)

    def delete(self, sid: int) -> None:
        if not self.db.delete_schedule(sid):
            raise ServiceError(404, f"Ugeprogram {sid} findes ikke")
        self._state.pop(sid, None)

    def preview(self, data: Any) -> dict[str, Any]:
        """Ugeoversigt og kommende skift for et (evt. ikke gemt) program — samme beregning som afviklingen."""
        clean = validate_schedule({**(data if isinstance(data, dict) else {}), "name": "preview"}, self._tags())
        return self._timeline(clean, datetime.now(TZ))

    def usage(self, tag: str) -> list[str]:
        """Navne på ugeprogrammer der skriver til tagget (tag-servicen bruger det til at blokere sletning m.m.)."""
        return [s["name"] for s in self.db.list_schedules() if s["tag"] == tag]

    def _changed(self, sid: int) -> None:
        self._state.pop(sid, None)  # beregnes og anvendes på ny ved næste gennemløb
        self._wake.set()

    # ------------------------------------------------------------------ visning

    def _timeline(self, s: dict[str, Any], now: datetime) -> dict[str, Any]:
        p = program_from(s)
        monday = now.date() - timedelta(days=now.weekday())
        upcoming = changes(p, now, 7)
        return {
            "now_value": desired(p, now),
            "next_changes": [{"at": t.timestamp(), "value": v} for t, v in upcoming[1:11]],
            "week": [{"day": DAY_NAMES[i], "date": (monday + timedelta(days=i)).isoformat(), "segments": segs}
                     for i, segs in enumerate(week_segments(p, monday))],
        }

    def _public(self, s: dict[str, Any], now: datetime) -> dict[str, Any]:
        st = self._state.get(s["id"], {})
        return {**s, **self._timeline(s, now),
                "status": {"target": st.get("target"), "applied": st.get("done", False), "error": st.get("error", ""),
                           "last_write": st.get("last_write")}}

    # ------------------------------------------------------------------ afvikling

    async def tick(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        dt = datetime.fromtimestamp(now, TZ)
        tags = self._tags()
        for s in self.db.list_schedules():
            if not s["enabled"]:
                self._state.pop(s["id"], None)
                continue
            target = desired(program_from(s), dt)
            st = self._state.setdefault(s["id"], {})
            if target is None:
                st.update(target=None, done=True, error="")
                continue
            if st.get("target") != target:
                st.update(target=target, done=False, error="", retry_at=0.0)
            if st.get("done") or now < st.get("retry_at", 0.0):
                continue
            tag = tags.get(s["tag"])
            if tag is None:
                st.update(error=f"Tagget '{s['tag']}' findes ikke længere", retry_at=now + RETRY_S)
                continue
            is_bool = _is_bool_tag(tag)
            live = self.manager.cache.get(s["tag"])
            if live.quality == "good" and live.value is not None and (
                    bool(live.value) == bool(target) if is_bool else math.isclose(float(live.value), target, abs_tol=1e-6)):
                st.update(done=True, error="")  # PLC'en har allerede værdien — skriv ikke
                continue
            actor = CurrentUser(username=self.actor_prefix + s["name"], role="admin", must_change_password=False,
                                token_hash="")
            try:
                await self.operate.write(actor, "ugeprogram", s["tag"], bool(target) if is_bool else target,
                                         action="schedule")
                st.update(done=True, error="", last_write=now)
                log.info("Ugeprogram %s: %s = %s", s["name"], s["tag"], target)
            except ServiceError as exc:
                st.update(error=exc.message, retry_at=now + RETRY_S)
                log.warning("Ugeprogram %s kunne ikke skrive %s: %s", s["name"], s["tag"], exc.message)

    async def run(self) -> None:
        while True:
            try:
                if not self.paused:
                    await self.tick()
            except Exception:
                log.exception("Ugeprogrammer: gennemløb fejlede")
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=TICK_S)
            except asyncio.TimeoutError:
                pass
