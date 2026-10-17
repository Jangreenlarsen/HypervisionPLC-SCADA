"""Alarmer (ISA-18.2, forenklet).

Betingelser:
- Tal-tags: højalarm (H/HH) og lavalarm (L/LL) — én alarm pr. retning, der kan skifte niveau.
  Dødbånd (hysterese) på udgangen: en H-alarm ophører først når værdien er under H − dødbånd.
- Til/fra-tags: alarm når værdien er sand (`alarm_on='true'`) eller falsk (`'false'`).
- PLC-kommunikation: alarm når en PLC har været i fejl i mere end `comm_delay_s`.
- Forsinkelse (`alarm_delay_s`): betingelsen skal holde så længe før alarmen udløses.

Tilstande: active_unack → (kvittering) active_ack → (ophør) væk
           active_unack → (ophør) rtn_unack → (kvittering) væk
Eskalering (H → HH) gør alarmen ukvitteret igen. Tags uden gyldig værdi (PLC nede) bevarer
deres tilstand — en kommunikationsfejl må ikke "rydde" en alarm.

Aktive alarmer gemmes i databasen (overlever genstart); alle hændelser i historikken.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from ..storage.db import Database
from .live_cache import LiveValue
from .manager import PlcManager

log = logging.getLogger(__name__)

PRIORITY = {"HH": "high", "LL": "high", "ON": "high", "COMM": "high", "H": "medium", "L": "medium"}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
SEVERITY = {"H": 1, "HH": 2, "L": 1, "LL": 2}
KEEP_EVENTS = 50_000


@dataclass
class Condition:
    key: str
    tag: str
    plc: str
    kind: str  # high | low | state | comm
    level: str
    value: Any
    message: str
    delay_s: float = 0.0
    priority: str | None = None  # fast prioritet (fx symbolets valgte alarmniveau); ellers efter niveauet

    @property
    def prio(self) -> str:
        return self.priority or PRIORITY[self.level]


def _fmt(value: Any, unit: str) -> str:
    if isinstance(value, float):
        value = round(value, 3)
    return f"{value}{' ' + unit if unit else ''}"


def tag_conditions(tag: dict[str, Any], value: Any, current: dict[str, str]) -> list[Condition] | None:
    """Ønskede alarmer for ét tag ud fra værdien. `current`: {retning: aktivt niveau} for hysterese.
    Returnerer None hvis tagget ikke har alarmer."""
    name, plc, unit = tag["name"], tag["plc"], tag["unit"]
    label = tag["description"] or name
    limits = {lvl: tag[f"alarm_{lvl.lower()}"] for lvl in ("HH", "H", "L", "LL")}
    on = tag["alarm_on"]
    if all(v is None for v in limits.values()) and on is None:
        return None
    delay = float(tag["alarm_delay_s"] or 0)
    db = float(tag["alarm_deadband"] or 0)
    out: list[Condition] = []

    if on is not None:
        if isinstance(value, (bool, int, float)) and bool(value) == (on == "true"):
            out.append(Condition(f"tag:{name}:state", name, plc, "state", "ON", value,
                                 f"{label}: {'aktiv' if on == 'true' else 'ikke aktiv'}", delay))
        return out

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return out
    v = float(value)

    def level_for(direction: str) -> str | None:
        cur = current.get(direction)
        order = ("HH", "H") if direction == "high" else ("LL", "L")
        for lvl in order:
            t = limits[lvl]
            if t is None:
                continue
            if direction == "high":
                hit = v >= t or (cur is not None and SEVERITY.get(cur, 0) >= SEVERITY[lvl] and v > t - db)
            else:
                hit = v <= t or (cur is not None and SEVERITY.get(cur, 0) >= SEVERITY[lvl] and v < t + db)
            if hit:
                return lvl
        return None

    for direction in ("high", "low"):
        lvl = level_for(direction)
        if lvl is not None:
            word = "for høj" if direction == "high" else "for lav"
            out.append(Condition(f"tag:{name}:{direction}", name, plc, direction, lvl, value,
                                 f"{label} {word} ({lvl}): {_fmt(value, unit)} — grænse {_fmt(limits[lvl], unit)}", delay))
    return out


class AlarmService:
    def __init__(self, manager: PlcManager, db: Database, *, tick_s: float = 1.0, comm_delay_s: float = 10.0):
        self.manager = manager
        self.db = db
        self.tick_s = tick_s
        self.comm_delay_s = comm_delay_s
        self.state: dict[str, dict[str, Any]] = {a["key"]: a for a in db.list_alarm_states()}
        self._pending: dict[str, float] = {}
        self._comm_since: dict[str, float] = {}
        self._subscribers: set[asyncio.Queue[int]] = set()
        self._version = 0
        # Ekstra kilder til alarmer (fx symbolernes afvigelse): now → (betingelser, "frosne" tags hvis alarmer ikke må
        # ryddes fordi værdien er ukendt — en kommunikationsfejl må aldrig rydde en alarm)
        self.providers: list[Any] = []
        self._published: set[str] = set()   # alarm:<tag>:active|unack i live-cachen (v0.74.0)

    # ------------------------------------------------------------ abonnenter

    def subscribe(self) -> asyncio.Queue[int]:
        q: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[int]) -> None:
        self._subscribers.discard(q)

    def _changed(self) -> None:
        self._version += 1
        for q in list(self._subscribers):
            if q.empty():
                q.put_nowait(self._version)

    # ------------------------------------------------------------- motor

    async def run(self) -> None:
        queue = self.manager.cache.subscribe()
        try:
            while True:
                try:
                    await asyncio.wait_for(queue.get(), timeout=self.tick_s)
                    while not queue.empty():  # saml en byge af ændringer til én evaluering
                        queue.get_nowait()
                except asyncio.TimeoutError:
                    pass
                try:
                    self.evaluate()
                except Exception:
                    log.exception("Fejl i alarmevaluering")
        finally:
            self.manager.cache.unsubscribe(queue)

    def evaluate(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        desired: dict[str, Condition] = {}
        frozen: set[str] = set()  # tags uden gyldig værdi — rør ikke deres alarmer

        for tag in self.db.list_tags():
            live = self.manager.cache.get(tag["name"])
            current = {a["kind"]: a["level"] for a in self.state.values()
                       if a["tag"] == tag["name"] and a["state"] != "rtn_unack" and a["kind"] in ("high", "low")}
            if live.quality != "good":
                frozen.add(tag["name"])
                continue
            conds = tag_conditions(tag, live.value, current)
            for c in conds or []:
                desired[c.key] = c

        for plc in self.db.list_plcs():
            st = self.manager.status(plc["key"])
            if plc["enabled"] and st["state"] == "error":
                since = self._comm_since.setdefault(plc["key"], now)
                if now - since >= self.comm_delay_s:
                    desired[f"plc:{plc['key']}:comm"] = Condition(
                        f"plc:{plc['key']}:comm", "", plc["key"], "comm", "COMM", None,
                        f"PLC {plc['name']}: kommunikation tabt — {st['message']}")
            else:
                self._comm_since.pop(plc["key"], None)

        for provider in self.providers:
            try:
                conds, frozen_extra = provider(now)
            except Exception:
                log.exception("Fejl i alarmkilde")
                continue
            for c in conds:
                desired[c.key] = c
            frozen |= frozen_extra

        changed = False
        keys = set(self.state) | set(desired) | set(self._pending)
        for key in keys:
            existing = self.state.get(key)
            if existing and existing["tag"] in frozen:
                continue
            cond = desired.get(key)
            active = existing is not None and existing["state"] in ("active_unack", "active_ack")
            if cond is None:
                self._pending.pop(key, None)
                if active:
                    changed |= self._clear(existing, now)
                continue
            if active:
                self._pending.pop(key, None)
                if existing["level"] != cond.level or existing["priority"] != cond.prio:
                    changed |= self._relevel(existing, cond, now)
                continue
            since = self._pending.setdefault(key, now)
            if now - since >= cond.delay_s:
                self._pending.pop(key, None)
                changed |= self._raise(cond, now)
        if changed:
            self._changed()
        self.publish(now)

    def publish(self, now: float | None = None) -> None:
        """Alarmtilstanden pr. tag som live-værdier, så animationer kan styres af den (symbolguidens kilde "alarm på et
        tag", v0.74.0): `alarm:<tag>:active` (en alarm er aktiv) og `alarm:<tag>:unack` (en alarm er ukvitteret — også
        efter den er ophørt). Udgives for alle tags med alarmopsætning; cachen sender kun ændringer videre."""
        now = time.time() if now is None else now
        names = {t["name"] for t in self.db.list_tags()
                 if t["alarm_on"] is not None or any(t[f"alarm_{k}"] is not None for k in ("hh", "h", "l", "ll"))}
        active = {a["tag"] for a in self.state.values() if a["tag"] and a["state"] in ("active_unack", "active_ack")}
        unack = {a["tag"] for a in self.state.values() if a["tag"] and a["state"] in ("active_unack", "rtn_unack")}
        updates: dict[str, LiveValue] = {}
        for name in names | active | unack:
            updates[f"alarm:{name}:active"] = LiveValue(value=name in active, quality="good", ts=now)
            updates[f"alarm:{name}:unack"] = LiveValue(value=name in unack, quality="good", ts=now)
        stale = self._published - set(updates)
        if stale:
            self.manager.cache.remove(sorted(stale))
        self._published = set(updates)
        if updates:
            self.manager.cache.update(updates)

    # ------------------------------------------------------ tilstandsskift

    def _event(self, row: dict[str, Any], event: str, now: float, username: str = "") -> None:
        self.db.insert_alarm_event({"ts": now, "key": row["key"], "tag": row["tag"], "plc": row["plc"],
                                    "level": row["level"], "priority": row["priority"], "event": event,
                                    "value": row.get("value"), "username": username, "message": row["message"]},
                                   KEEP_EVENTS)

    def _raise(self, c: Condition, now: float) -> bool:
        row = {"key": c.key, "tag": c.tag, "plc": c.plc, "kind": c.kind, "level": c.level,
               "priority": c.prio, "state": "active_unack", "raised_at": now, "value": c.value,
               "message": c.message, "acked_by": None, "acked_at": None}
        self.state[c.key] = row
        self.db.upsert_alarm_state(row)
        self._event(row, "raise", now)
        log.warning("ALARM %s %s", c.level, c.message)
        return True

    def _relevel(self, row: dict[str, Any], c: Condition, now: float) -> bool:
        worse = (SEVERITY.get(c.level, 0) > SEVERITY.get(row["level"], 0)
                 or PRIORITY_ORDER.get(c.prio, 9) < PRIORITY_ORDER.get(row["priority"], 9))
        row.update(level=c.level, priority=c.prio, value=c.value, message=c.message)
        if worse:  # eskalering kræver ny kvittering
            row.update(state="active_unack", raised_at=now, acked_by=None, acked_at=None)
        self.db.upsert_alarm_state(row)
        self._event(row, "raise" if worse else "change", now)
        return True

    def _clear(self, row: dict[str, Any], now: float) -> bool:
        self._event(row, "clear", now)
        if row["state"] == "active_unack":
            row["state"] = "rtn_unack"
            self.db.upsert_alarm_state(row)
        else:
            self.state.pop(row["key"], None)
            self.db.delete_alarm_state(row["key"])
        return True

    def ack(self, keys: list[str], username: str, visible: set[str] | None) -> int:
        now = time.time()
        count = 0
        for key in keys:
            row = self.state.get(key)
            if row is None or (visible is not None and key not in visible):
                continue
            if row["state"] == "active_unack":
                row.update(state="active_ack", acked_by=username, acked_at=now)
                self.db.upsert_alarm_state(row)
            elif row["state"] == "rtn_unack":
                self.state.pop(key, None)
                self.db.delete_alarm_state(key)
            else:
                continue
            self._event(row, "ack", now, username)
            count += 1
        if count:
            self._changed()
            self.publish(now)
        return count

    # ------------------------------------------------------------- visning

    def visible_keys(self, visible_tags: set[str] | None) -> set[str] | None:
        if visible_tags is None:
            return None
        plcs = {t["plc"] for t in self.db.list_tags() if t["name"] in visible_tags}
        return {k for k, a in self.state.items()
                if (a["tag"] and a["tag"] in visible_tags) or (not a["tag"] and a["plc"] in plcs)}

    def active(self, visible_tags: set[str] | None) -> list[dict[str, Any]]:
        keys = self.visible_keys(visible_tags)
        rows = [a for k, a in self.state.items() if keys is None or k in keys]
        order = {"active_unack": 0, "rtn_unack": 1, "active_ack": 2}
        return sorted(rows, key=lambda a: (order[a["state"]], PRIORITY_ORDER.get(a["priority"], 9), -a["raised_at"]))

    def summary(self, visible_tags: set[str] | None) -> dict[str, int]:
        rows = self.active(visible_tags)
        return {"active": sum(a["state"] != "rtn_unack" for a in rows),
                "unacked": sum(a["state"] in ("active_unack", "rtn_unack") for a in rows),
                "high": sum(a["priority"] == "high" and a["state"] != "rtn_unack" for a in rows)}

    def history(self, limit: int, visible_tags: set[str] | None) -> list[dict[str, Any]]:
        rows = self.db.list_alarm_events(max(1, min(limit, 2000)) if visible_tags is None else 2000)
        if visible_tags is not None:
            plcs = {t["plc"] for t in self.db.list_tags() if t["name"] in visible_tags}
            rows = [r for r in rows if (r["tag"] and r["tag"] in visible_tags) or (not r["tag"] and r["plc"] in plcs)]
        return rows[:limit]
