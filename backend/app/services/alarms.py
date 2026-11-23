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

Udsættelse (shelving, ISA-18.2): en operatør kan udsætte en aktiv alarm i 5 min – 24 timer med begrundelse. Alarmen
fjernes fra de aktive, og betingelsen springes over, til tiden er gået eller den genindsættes (tabellen alarm_shelf, så
udsættelsen overlever genstart). Alt skrives i alarmhistorikken og auditeres. Kommunikations- og systemalarmer kan ikke
udsættes. Stiger alvoren på en udsat alarm (H → HH, L → LL), ophæves udsættelsen automatisk og alarmen rejses som ny og
ukvitteret; uændret eller lavere alvor forbliver udsat. evaluate/ack/shelve/unshelve kører under samme lås, så en udsættelse aldrig overlapper et tick.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..storage.db import Database
from .errors import ServiceError
from .live_cache import LiveValue
from .manager import PlcManager
from .schedule_engine import TZ

log = logging.getLogger(__name__)

PRIORITY = {"HH": "high", "LL": "high", "ON": "high", "COMM": "high", "H": "medium", "L": "medium"}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
SEVERITY = {"H": 1, "HH": 2, "L": 1, "LL": 2}
KEEP_EVENTS = 50_000
HISTORY_MAX = 2000                                    # grænsen for historikvisningen; CSV-eksporten må op til KEEP_EVENTS
EVENT_TYPES = ("raise", "clear", "ack", "change", "shelve", "unshelve")   # hændelsestyperne i alarm_events (se _event)
PRIORITIES = ("high", "medium", "low")
PRIORITY_TEXT = {"high": "Høj", "medium": "Medium", "low": "Lav"}
SHELVE_MIN, SHELVE_MAX = 5, 1440                      # udsættelsens varighed i minutter (5 min – 24 timer)
REASON_MIN, REASON_MAX = 3, 200                       # begrundelsens længde i tegn
UNSHELVABLE_KINDS = ("comm", "sys")                   # kommunikations- og systemalarmer kan aldrig udsættes (Condition.kind)


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
    prio = tag.get("alarm_priority") or None  # valgfri fast prioritet (v6.18.0); ellers efter niveauet
    out: list[Condition] = []

    if on is not None:
        if isinstance(value, (bool, int, float)) and bool(value) == (on == "true"):
            out.append(Condition(f"tag:{name}:state", name, plc, "state", "ON", value,
                                 f"{label}: {'aktiv' if on == 'true' else 'ikke aktiv'}", delay, prio))
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
                                 f"{label} {word} ({lvl}): {_fmt(value, unit)} — grænse {_fmt(limits[lvl], unit)}", delay, prio))
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
        # Lyttere på alarmhændelser (row, hændelse, tid) — fx notifikation. En fejl i en lytter må aldrig vælte alarmmotoren.
        self.listeners: list[Any] = []
        self._published: set[str] = set()   # alarm:<tag>:active|unack i live-cachen (v0.74.0)
        # Serialiserer tilstandsskift. Alt kører i dag på event-loopet, men låsen gør rækkefølgen uafhængig af det.
        self._lock = threading.RLock()

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

    @staticmethod
    def _comm_problems(plc: dict[str, Any], st: dict[str, Any]) -> list[tuple[str, str]]:
        """Kommunikationsproblemer for en aktiv PLC → [(alarmnøgle, tekst)]: hele PLC'en tabt, aldrig startet
        (mangler adgangskode), eller delvist (ét bulk-område / ST-program / ekstern slave svarer ikke — tagsene
        er `comm_error`, men PLC'en er ellers oppe)."""
        key, name = plc["key"], plc["name"]
        if st["state"] == "error":
            return [(f"plc:{key}:comm", f"PLC {name}: kommunikation tabt — {st['message']}")]
        if st["state"] == "stopped" and st.get("attention"):
            return [(f"plc:{key}:comm", f"PLC {name}: ikke startet — {st['message']}")]
        partial = st.get("partial") or []
        if not partial:
            return []
        first = partial[0]
        more = f" (+{len(partial) - 1} andre)" if len(partial) > 1 else ""
        # én alarm pr. PLC (ikke pr. kald): stabil nøgle, også når tags ændrer opdelingen i områder
        return [(f"plc:{key}:partial",
                 f"PLC {name}: {first['what']} svarer ikke ({first['tags']} tag) — {first['message']}{more}")]

    def evaluate(self, now: float | None = None) -> None:
        with self._lock:
            self._evaluate(time.time() if now is None else now)

    def _evaluate(self, now: float) -> None:
        changed = self._expire_shelf(now)
        shelf = {r["key"]: r for r in self.db.list_alarm_shelf()}   # læses fra databasen: en rettelse dér gælder straks
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

        seen: set[str] = set()
        for plc in self.db.list_plcs():
            if not plc["enabled"]:
                continue
            st = self.manager.status(plc["key"])
            for key, message in self._comm_problems(plc, st):
                seen.add(key)
                since = self._comm_since.setdefault(key, now)
                if now - since >= self.comm_delay_s:
                    desired[key] = Condition(key, "", plc["key"], "comm", "COMM", None, message)
        for key in [k for k in self._comm_since if k not in seen]:
            del self._comm_since[key]

        for provider in self.providers:
            try:
                conds, frozen_extra = provider(now)
            except Exception:
                log.exception("Fejl i alarmkilde")
                continue
            for c in conds:
                desired[c.key] = c
            frozen |= frozen_extra

        for key, s in shelf.items():
            cond = desired.get(key)
            why = self._shelf_breakthrough(s, cond) if cond is not None else None
            if cond is not None and why is not None:
                # Eskalering (niveau H → HH, L → LL, eller en højere prioritet på tagget) bryder igennem: udsættelsen
                # ophæves, og betingelsen rejses som en ny, ukvitteret alarm (med den almindelige forsinkelse).
                # Uændret eller lavere alvor/prioritet forbliver udsat.
                self.db.delete_alarm_shelf(key)
                self._event({**s, "level": cond.level, "priority": cond.prio, "value": cond.value,
                             "message": f"Udsættelsen ophævet: {why}"}, "unshelve", now)
                log.warning("ALARM udsættelse ophævet ved eskalering plc=%s tag=%s key=%s %s/%s -> %s/%s",
                            s["plc"], s["tag"], key, s["level"], s["priority"], cond.level, cond.prio)
                changed = True
                continue
            # udsatte alarme rejses ikke og begynder ikke at tælle forsinkelse
            desired.pop(key, None)
            self._pending.pop(key, None)
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
                if existing["level"] == cond.level and existing["priority"] != cond.prio and cond.kind in ("high", "low", "state"):
                    # tagets prioritet er ændret mens alarmen er aktiv: opdatér kun prioriteten (ingen ny kvittering/hændelse)
                    existing["priority"] = cond.prio
                    self.db.upsert_alarm_state(existing)
                    changed = True
                elif existing["level"] != cond.level or existing["priority"] != cond.prio:
                    changed |= self._relevel(existing, cond, now)
                continue
            since = self._pending.setdefault(key, now)
            if now - since >= cond.delay_s:
                self._pending.pop(key, None)
                changed |= self._raise(cond, now)
        if changed:
            self._changed()
        self.publish(now)

    @staticmethod
    def _shelf_breakthrough(s: dict[str, Any], cond: Condition) -> str | None:
        """Årsagen (tekst til historikken) hvis betingelsen er værre end da alarmen blev udsat, ellers None."""
        if SEVERITY.get(cond.level, 0) > SEVERITY.get(s["level"], 0):
            return f"alarmen er steget til {cond.level}"
        if PRIORITY_ORDER.get(cond.prio, 9) < PRIORITY_ORDER.get(s["priority"], 9):
            return f"prioriteten er steget til {PRIORITY_TEXT.get(cond.prio, cond.prio)}"
        return None

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

    def _event(self, row: dict[str, Any], event: str, now: float, username: str = "",
               listener_row: dict[str, Any] | None = None) -> None:
        """Skriv hændelsen i historikken og giv den til lytterne. `listener_row`: rækken lytterne får, hvis den skal være
        en anden end historikkens (en udsættelse: lytterne må ikke se operatørens begrundelse)."""
        self.db.insert_alarm_event({"ts": now, "key": row["key"], "tag": row["tag"], "plc": row["plc"],
                                    "level": row["level"], "priority": row["priority"], "event": event,
                                    "value": row.get("value"), "username": username, "message": row["message"]},
                                   KEEP_EVENTS)
        for listener in self.listeners:
            try:
                listener(listener_row or row, event, now)
            except Exception:
                log.exception("Fejl i alarm-lytter")

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

    def forget(self, tags: set[str], plc: str | None = None, moved_to: str | None = None) -> int:
        """En PLC er fjernet (v3.34.0): tagsenes alarmer — og PLC'ens egne kommunikationsalarmer — fjernes fra tilstanden
        i hukommelsen og databasen (ellers skrev næste evaluate dem tilbage som "rtn_unack"). `moved_to`: tagsene er
        flyttet til en anden PLC — deres alarmer bevares og peger på den nye PLC. Hændelseshistorikken røres ikke, bortset fra at en fjernet udsættelse får en `unshelve`-hændelse
        (en flyttet udsættelse følger tagget uden hændelse). → antal fjernede alarmer."""
        with self._lock:
            return self._forget(tags, plc, moved_to)

    def _forget(self, tags: set[str], plc: str | None, moved_to: str | None) -> int:
        removed_shelf = False
        now = time.time()
        for s in self.db.list_alarm_shelf():   # udsættelser følger tagget (flyttet, uden hændelse) eller fjernes med det (med hændelse)
            if s["tag"] in tags and moved_to:
                self.db.upsert_alarm_shelf({**s, "plc": moved_to})
            elif s["tag"] in tags or (plc and not s["tag"] and s["plc"] == plc):
                self.db.delete_alarm_shelf(s["key"])
                what = "PLC slettet" if plc else "tag slettet"
                self._event({**s, "value": None, "message": f"Udsættelsen fjernet: {what}"}, "unshelve", now)
                log.warning("ALARM udsættelse fjernet (%s) plc=%s tag=%s key=%s", what, s["plc"], s["tag"], s["key"])
                removed_shelf = True
        gone = 0
        for key, row in list(self.state.items()):
            tag = row.get("tag") or ""
            if tag in tags and moved_to:
                row["plc"] = moved_to
                self.db.upsert_alarm_state(row)
            elif tag in tags or (plc and not tag and row.get("plc") == plc):
                self.state.pop(key, None)
                self._pending.pop(key, None)
                self.db.delete_alarm_state(key)
                gone += 1
        if removed_shelf:
            self._changed()
        self.publish()
        return gone

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
        with self._lock:
            return self._ack(keys, username, visible)

    def _ack(self, keys: list[str], username: str, visible: set[str] | None) -> int:
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

    # --------------------------------------------------------- udsættelse

    @staticmethod
    def _local(ts: float) -> str:
        return datetime.fromtimestamp(ts, TZ).strftime("%d.%m.%Y %H:%M")

    def _expire_shelf(self, now: float) -> bool:
        """Udløbne udsættelser slettes (hændelsen `unshelve`); alarmen vurderes derefter som en ny betingelse."""
        gone = False
        for s in self.db.list_alarm_shelf():
            if s["until_ts"] > now:
                continue
            self.db.delete_alarm_shelf(s["key"])
            self._event({**s, "value": None, "message": "Udsættelsen udløb"}, "unshelve", now)
            log.warning("ALARM udsættelse udløbet plc=%s tag=%s key=%s", s["plc"], s["tag"], s["key"])
            gone = True
        return gone

    def _shelf_visible(self, rows: list[dict[str, Any]], visible_tags: set[str] | None) -> list[dict[str, Any]]:
        if visible_tags is None:
            return rows
        plcs = {t["plc"] for t in self.db.list_tags() if t["name"] in visible_tags}
        return [r for r in rows if (r["tag"] and r["tag"] in visible_tags) or (not r["tag"] and r["plc"] in plcs)]

    def visible_shelf_keys(self, visible_tags: set[str] | None) -> set[str] | None:
        """Nøglerne på de udsatte alarme brugeren må se (None = alle) — afgrænsningen for `unshelve`."""
        if visible_tags is None:
            return None
        return {r["key"] for r in self._shelf_visible(self.db.list_alarm_shelf(), visible_tags)}

    @staticmethod
    def _clean_reason(reason: Any) -> str:
        """Begrundelsen normaliseret: kontroltegn (Unicode Cc: linjeskift, tabulator …) og formattegn (Cf: usynlige, retningsstyrende)
        afvises, øvrigt whitespace (også nbsp) bliver ét mellemrum, og kanterne trimmes. Længden tælles i kodepunkter."""
        if not isinstance(reason, str):
            raise ServiceError(400, f"Begrundelsen skal være en tekst på {REASON_MIN}-{REASON_MAX} tegn.")
        if any(unicodedata.category(ch) in ("Cc", "Cf") for ch in reason):
            raise ServiceError(400, "Begrundelsen må ikke indeholde kontroltegn, linjeskift eller usynlige tegn.")
        text = " ".join(reason.split())
        if not REASON_MIN <= len(text) <= REASON_MAX:
            raise ServiceError(400, f"Begrundelsen skal være på {REASON_MIN}-{REASON_MAX} tegn.")
        return text

    def shelve(self, key: str, minutes: Any, reason: Any, username: str, allowed_keys: set[str] | None) -> dict[str, Any]:
        """Udsæt en aktiv alarm. → udsættelsesrækken. Fejl: 400 (ugyldig varighed/begrundelse, kommunikations-/systemalarm,
        ophørt alarm), 404 (ukendt eller fremmed alarm), 409 (allerede udsat). `allowed_keys` skal indeholde både brugerens
        synlige aktive alarmer og synlige udsatte (så en dobbeltudsættelse giver 409 og ikke 404)."""
        if isinstance(minutes, bool) or not isinstance(minutes, int) or not SHELVE_MIN <= minutes <= SHELVE_MAX:
            raise ServiceError(400, f"Varigheden skal være et helt antal minutter mellem {SHELVE_MIN} og {SHELVE_MAX}.")
        text = self._clean_reason(reason)
        with self._lock:
            if allowed_keys is not None and key not in allowed_keys:
                raise ServiceError(404, "Alarmen findes ikke")   # samme svar for ukendt og fremmed: intet lækker
            existing = next((s for s in self.db.list_alarm_shelf() if s["key"] == key), None)
            if existing is not None:   # (en udsat alarm er ikke længere i alarm_state, så det tjekkes først)
                raise ServiceError(409, f"Alarmen er allerede udsat til {self._local(existing['until_ts'])}")
            row = self.state.get(key)
            if row is None:
                raise ServiceError(404, "Alarmen findes ikke")
            if row["kind"] in UNSHELVABLE_KINDS:
                raise ServiceError(400, "Kommunikations- og systemalarmer kan ikke udsættes")
            if row["state"] not in ("active_unack", "active_ack"):
                raise ServiceError(400, "Alarmen er ophørt — kvittér den i stedet for at udsætte den")
            now = time.time()
            until = now + minutes * 60
            shelf = {"key": key, "tag": row["tag"], "plc": row["plc"], "level": row["level"], "priority": row["priority"],
                     "message": row["message"], "shelved_by": username, "shelved_at": now, "until_ts": until, "reason": text}
            self.db.upsert_alarm_shelf(shelf)
            self.state.pop(key, None)
            self._pending.pop(key, None)
            self.db.delete_alarm_state(key)
            self._event({**row, "message": f"Udsat til {self._local(until)} af {username}: {text} ({row['message']})"},
                        "shelve", now, username, listener_row=row)
            log.warning("ALARM udsat bruger=%s plc=%s tag=%s key=%s varighed=%d min", username, row["plc"], row["tag"], key, minutes)
            self._changed()
            self.publish(now)
            return shelf

    def unshelve(self, key: str, username: str, allowed_keys: set[str] | None) -> dict[str, Any]:
        """Genindsæt en udsat alarm. → den slettede række. 404 hvis den ikke er udsat eller brugeren ikke må se den."""
        with self._lock:
            shelf = next((s for s in self.db.list_alarm_shelf() if s["key"] == key), None)
            if shelf is None or (allowed_keys is not None and key not in allowed_keys):
                raise ServiceError(404, "Alarmen findes ikke")
            now = time.time()
            self.db.delete_alarm_shelf(key)
            self._event({**shelf, "value": None, "message": f"Genindsat af {username}"}, "unshelve", now, username)
            log.warning("ALARM genindsat bruger=%s plc=%s tag=%s key=%s", username, shelf["plc"], shelf["tag"], key)
            self._changed()
            return shelf

    def shelved(self, visible_tags: set[str] | None) -> list[dict[str, Any]]:
        """Udsatte alarmer (de brugeren må se), sorteret efter udløb. `remaining_s`: resttid på serverens ur."""
        now = time.time()
        rows = self._shelf_visible(self.db.list_alarm_shelf(), visible_tags)
        return [{**r, "remaining_s": max(0.0, r["until_ts"] - now)} for r in sorted(rows, key=lambda r: r["until_ts"])]

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
        rows = sorted(rows, key=lambda a: (order[a["state"]], PRIORITY_ORDER.get(a["priority"], 9), -a["raised_at"]))
        return [self._with_rationale(a) for a in rows]

    def _with_rationale(self, a: dict[str, Any]) -> dict[str, Any]:
        """Konsekvens/handling/svartid slås op live fra tagget (ikke gemt i alarm_state), så en rettelse slår igennem straks.
        Kun tag-alarmer; kommunikations-/system-/symbolalarmer får None."""
        out = dict(a)
        tag = self.db.get_tag(a["tag"]) if a.get("kind") in ("state", "high", "low") and a.get("tag") else None
        out["consequence"] = (tag or {}).get("alarm_consequence")
        out["action"] = (tag or {}).get("alarm_action")
        out["response_min"] = (tag or {}).get("alarm_response_min")
        return out

    def summary(self, visible_tags: set[str] | None) -> dict[str, int]:
        rows = self.active(visible_tags)
        return {"active": sum(a["state"] != "rtn_unack" for a in rows),
                "unacked": sum(a["state"] in ("active_unack", "rtn_unack") for a in rows),
                "high": sum(a["priority"] == "high" and a["state"] != "rtn_unack" for a in rows),
                "shelved": len(self._shelf_visible(self.db.list_alarm_shelf(), visible_tags))}

    def history(self, limit: int, visible_tags: set[str] | None, flt: dict[str, Any] | None = None,
                cap: int = HISTORY_MAX) -> list[dict[str, Any]]:
        """Hændelser, nyeste først. `flt`: q, ts_from, ts_to, event, priority, system (se Database.list_alarm_events).
        Adgangen pr. tegning gælder ovenpå filtrene og afgøres i SQL, så grænsen tæller kun synlige hændelser."""
        scope = None
        if visible_tags is not None:
            scope = (set(visible_tags), {t["plc"] for t in self.db.list_tags() if t["name"] in visible_tags})
        return self.db.list_alarm_events(max(1, min(limit, cap)), scope=scope, **(flt or {}))
