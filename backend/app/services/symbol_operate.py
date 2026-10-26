"""Symbolstandard fase 3: betjening af symboler (lag 3).

Teknik: docs/SYMBOLSTANDARD_IMPLEMENTERING.md afsnit 5.3–5.4. Reference: prototypens `operate`, `operatePulse`,
`operateEntry`, `accept`, `needsPin`, `blockedMsg`.

Regler for alle kald:
- rolle ≥ operator og tegningen i brugerens adgang (API-laget);
- symbolet er konfigureret med den rette betjeningsform og findes i den aktive tegningsversion;
- fejl/låst-tagget er ikke Til (og er kendt); kommando-tagsene har gyldige værdier (ingen komm.fejl);
- én betjening ad gangen pr. symbol (ellers 409).

Positionsskift skriver signalerne efter skriveplanen (break-before-make). Fejler en skrivning, stopper planen —
der rulles ikke tilbage, fordi et automatisk tilbageskift kan være farligere end at stå stille; svaret siger præcis
hvad der er skrevet. Pulssignaler skriver altid deres hvileværdi (også hvis browseren lukkes).
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import threading
import time
from typing import Any

from .audit import AuditService
from .auth import CurrentUser, verify_password
from .errors import ServiceError
from .operate import OperateService
from .symbol_runtime import SymbolRuntime
from .symbols import needs_pin, write_plan

log = logging.getLogger(__name__)

PIN_TRIES = 3          # forkerte koder pr. bruger, før brugeren spærres
SYMBOL_TRIES = 10      # forkerte koder for symbolet i alt (alle brugere), før symbolet spærres
# Spærretider, der stiger ved gentagne spærringer (kodeanalyse 2, G3 — før altid 60 s, så en firecifret kode kunne
# gennemprøves på ~2 døgn). Nulstilles ved rigtig kode, eller når en tekniker sætter/fjerner koden.
PIN_LOCK_STEPS = (60.0, 300.0, 900.0, 3600.0)
PIN_LOCK_S = PIN_LOCK_STEPS[0]


def _fmt_wait(seconds: float) -> str:
    s = max(1, math.ceil(seconds))
    return f"{s} s" if s < 120 else f"{math.ceil(s / 60)} min"


class SymbolOperateService:
    def __init__(self, operate: OperateService, runtime: SymbolRuntime, audit: AuditService):
        self.operate = operate
        self.runtime = runtime
        self.db = operate.db
        self.cache = operate.manager.cache
        self.audit = audit
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}
        # Nøglelås pr. symbol: {"sym": {count, level, until}, "users": {navn: {count, level, until}}}. Gemt i databasen
        # (setting pinlock.<tegning>.<element>), så en genstart ikke nulstiller spærringen (G3). PIN tjekkes i en tråd.
        self._pin_guard = threading.Lock()
        self._background: set[asyncio.Task[Any]] = set()

    # ------------------------------------------------------------- fælles tjek

    def _config(self, drawing_id: str, element: str, op: str) -> dict[str, Any]:
        if self.runtime.drawings.is_disabled(drawing_id):
            raise ServiceError(409, "Tegningen er deaktiveret — den er offline og kan ikke betjenes")
        row = self.db.get_symbol_config(drawing_id, element)
        if row is None:
            raise ServiceError(404, f"'{element}' er ikke et konfigureret symbol")
        cfg = row["config"]
        if cfg.get("op") != op:
            what = {"positions": "positioner", "pulse": "trykknap", "entry": "setpunkt", "view": "kun visning"}
            raise ServiceError(409, f"Symbolet er sat op som {what.get(cfg.get('op'), cfg.get('op'))} — ikke {what[op]}")
        if self.runtime.symbols.get((drawing_id, element)) is None:
            self.runtime.reload()
            if self.runtime.symbols.get((drawing_id, element)) is None:
                raise ServiceError(409, f"'{element}' findes ikke i den aktive version af tegningen")
        return cfg

    def _blocked(self, cfg: dict[str, Any]) -> None:
        """Prototypens `blockedMsg`: fejl/låst-tag aktivt eller ukendt, eller komm.fejl på kommando-tags."""
        fault = cfg.get("fault")
        if fault:
            lv = self.cache.get(fault)
            if lv.quality != "good" or lv.value is None:
                raise ServiceError(409, f"Betjening er blokeret — {fault} (fejl/låst) er ukendt")
            if bool(lv.value):
                raise ServiceError(409, f"Betjening er blokeret — {fault} er aktiv")
        for s in cfg.get("signals", []):
            if s.get("tag") and self.cache.get(s["tag"]).quality != "good":
                raise ServiceError(503, f"Ingen forbindelse til {s['tag']} — intet er skrevet")

    def _lock(self, key: tuple[str, str]) -> asyncio.Lock:
        lock = self._locks.setdefault(key, asyncio.Lock())
        if lock.locked():
            raise ServiceError(409, "Symbolet betjenes allerede — prøv igen om et øjeblik")
        return lock

    def _record(self, actor: CurrentUser, ip: str, action: str, key: tuple[str, str], detail: dict[str, Any],
                error: ServiceError | None = None) -> None:
        self.audit.record(actor.username, ip, action, f"{key[0]}#{key[1]}", detail,
                          "error" if error else "ok", error.message if error else "")

    # ------------------------------------------------------------- nøglelås

    @staticmethod
    def _pin_key(key: tuple[str, str]) -> str:
        return f"pinlock.{key[0]}.{key[1]}"

    def _pin_state(self, key: tuple[str, str]) -> dict[str, Any]:
        try:
            state = json.loads(self.db.get_setting(self._pin_key(key)) or "{}")
        except ValueError:
            state = {}
        if not isinstance(state, dict):
            state = {}
        state.setdefault("sym", {})
        state.setdefault("users", {})
        return state

    def reset_pin_fails(self, drawing_id: str, element: str) -> None:
        """Ny eller fjernet kode: spærringer og fejltællere for symbolet gælder ikke længere."""
        with self._pin_guard:
            self.db.set_setting(self._pin_key((drawing_id, element)), None)

    @staticmethod
    def _bump(entry: dict[str, Any], limit: int, now: float) -> float:
        """Tæl en fejl; ved `limit` spærres med stigende tid. → spærretid i sekunder (0 = ikke spærret nu)."""
        entry["count"] = int(entry.get("count", 0)) + 1
        if entry["count"] < limit:
            return 0.0
        level = int(entry.get("level", 0))
        lock_s = PIN_LOCK_STEPS[min(level, len(PIN_LOCK_STEPS) - 1)]
        entry.update(count=0, level=level + 1, until=now + lock_s)
        return lock_s

    def _check_pin(self, actor: CurrentUser, ip: str, key: tuple[str, str], pin: str | None, label: str) -> None:
        now = time.time()
        with self._pin_guard:
            state = self._pin_state(key)
        user_until = float(state["users"].get(actor.username, {}).get("until", 0))
        sym_until = float(state["sym"].get("until", 0))
        until = max(user_until, sym_until)
        if until > now:
            who = "symbolet (for mange forkerte koder i alt)" if sym_until >= user_until else "dig"
            raise ServiceError(429, f"For mange forkerte koder — betjening er spærret for {who} i {_fmt_wait(until - now)}")
        stored = self.db.get_symbol_pin_hash(*key)
        if stored is None:
            raise ServiceError(409, f"{label} er låst, og der er ingen kode — en tekniker skal sætte en kode")
        if not pin:
            raise ServiceError(403, f"{label} er låst — indtast koden")
        if not verify_password(pin, stored):
            with self._pin_guard:
                state = self._pin_state(key)          # læs igen: en anden bruger kan have fejlet imens
                mine = state["users"].setdefault(actor.username, {})
                user_lock = self._bump(mine, PIN_TRIES, now)
                sym_lock = self._bump(state["sym"], SYMBOL_TRIES, now)
                attempts = mine.get("count", 0)
                self.db.set_setting(self._pin_key(key), json.dumps(state))
            lock_s = max(user_lock, sym_lock)
            if lock_s:
                self._record(actor, ip, "symbol.pin_failed", key, {"locked_s": lock_s, "symbol_locked": bool(sym_lock)})
                log.warning("PIN for %s/%s: spærret i %.0f s efter forkerte koder (sidst: %s)", key[0], key[1], lock_s,
                            actor.username)
                raise ServiceError(429, f"Forkert kode — betjening af symbolet er spærret i {_fmt_wait(lock_s)}")
            self._record(actor, ip, "symbol.pin_failed", key, {"attempts": attempts})
            raise ServiceError(403, f"Forkert kode ({attempts} af {PIN_TRIES} forsøg)")
        with self._pin_guard:
            self.db.set_setting(self._pin_key(key), None)   # rigtig kode: alle tællere og niveauer nulstilles
        self._record(actor, ip, "symbol.unlock", key, {"position": label})

    # ------------------------------------------------------------- betjening

    def plan(self, drawing_id: str, element: str, position: int) -> list[dict[str, Any]]:
        cfg = self._config(drawing_id, element, "positions")
        if not 0 <= position < len(cfg["positions"]):
            raise ServiceError(400, f"Positionen findes ikke (0–{len(cfg['positions']) - 1})")
        return write_plan(cfg, position, lambda t: self.cache.get(t).value if self.cache.get(t).quality == "good" else None)

    async def operate_position(self, actor: CurrentUser, ip: str, drawing_id: str, element: str, position: int,
                               pin: str | None = None) -> dict[str, Any]:
        key = (drawing_id, element)
        detail: dict[str, Any] = {"to": position}
        try:
            cfg = self._config(drawing_id, element, "positions")
            labels = [p["label"] for p in cfg["positions"]]
            if not 0 <= position < len(labels):
                raise ServiceError(400, f"Positionen findes ikke (0–{len(labels) - 1})")
            st = self.runtime.state(drawing_id, element)
            shown = st.pos if st else None
            detail.update(position=labels[position], **({"from": labels[shown]} if shown is not None else {}))
            if needs_pin(cfg, shown, position):
                locked = (cfg.get("lock") or {}).get("positions") or []
                target_locked = position < len(locked) and locked[position]
                label = f'"{labels[position]}"' if target_locked or shown is None else f'"{labels[shown]}"'
                detail["pin"] = True
                await asyncio.to_thread(self._check_pin, actor, ip, key, pin, label)   # scrypt i en tråd (G1)
            self._blocked(cfg)
            lock = self._lock(key)
        except ServiceError as exc:
            self._record(actor, ip, "symbol.operate", key, detail, exc)
            raise
        async with lock:
            plan = write_plan(cfg, position, lambda t: self.cache.get(t).value)
            done: list[dict[str, Any]] = []
            uncertain: list[str] = []   # intet svar (timeout): PLC'en kan have udført skrivningen
            try:
                for w in (x for x in plan if not x["pulse"]):
                    try:
                        written = await self.operate.write_value(w["tag"], w["value"])
                    except ServiceError as exc:
                        if exc.status == 503:
                            uncertain.append(w["tag"])
                        raise
                    done.append({"tag": w["tag"], "value": written})
                pulses = [w for w in plan if w["pulse"]]
                if pulses:
                    # Pulserne kører som selvstændige opgaver: hvileværdien skrives også hvis requesten afbrydes
                    tasks = [asyncio.ensure_future(self.operate.pulse_value(w["tag"], w["value"], w["rest"], int(w["ms"])))
                             for w in pulses]
                    for t in tasks:
                        self._background.add(t)
                        t.add_done_callback(self._background.discard)
                    results = await asyncio.shield(asyncio.gather(*tasks, return_exceptions=True))
                    for w, res in zip(pulses, results):
                        if isinstance(res, ServiceError):
                            if res.status == 503:
                                uncertain.append(w["tag"])
                            raise res
                        if isinstance(res, BaseException):
                            raise ServiceError(502, f"Puls på {w['tag']}: {res}")
                        done.append({"tag": w["tag"], "value": w["value"], "pulse_ms": w["ms"], "rest": w["rest"]})
            except ServiceError as exc:
                missing = [w["tag"] for w in plan if w["tag"] not in {d["tag"] for d in done} | set(uncertain)]
                detail.update(writes=done, uncertain=uncertain, not_written=missing)
                msg = (f"{exc.message}. Skrevet: {', '.join(d['tag'] for d in done) or 'intet'}; "
                       + (f"usikkert (intet svar fra PLC'en): {', '.join(uncertain)}; " if uncertain else "")
                       + f"ikke skrevet: {', '.join(missing) or 'intet'}. Kontrollér symbolet.")
                err = ServiceError(exc.status, msg, {"writes": done, "uncertain": uncertain, "not_written": missing})
                self._record(actor, ip, "symbol.operate", key, detail, err)
                log.warning("Symbol %s#%s: skift til %s stoppet efter %d skrivning(er): %s", drawing_id, element,
                            labels[position], len(done), exc.message)
                raise err from exc
            self.runtime.set_chosen(key, position, actor.username)
            self.runtime.evaluate()
        detail["writes"] = done
        self._record(actor, ip, "symbol.operate", key, detail)
        log.info("Symbol %s#%s: %s valgt af %s (%d skrivning(er))", drawing_id, element, labels[position],
                 actor.username, len(done))
        st = self.runtime.state(drawing_id, element)
        return {"element": element, "position": position, "label": labels[position], "writes": done,
                "state": st.state if st else "unknown"}

    async def pulse(self, actor: CurrentUser, ip: str, drawing_id: str, element: str) -> dict[str, Any]:
        key = (drawing_id, element)
        try:
            cfg = self._config(drawing_id, element, "pulse")
            self._blocked(cfg)
            lock = self._lock(key)
        except ServiceError as exc:
            self._record(actor, ip, "symbol.pulse", key, {}, exc)
            raise
        async with lock:
            tag = cfg["signals"][0]["tag"]
            result = await self.operate.pulse(actor, ip, tag, int(cfg.get("pulse_ms", 500)))
        return {"element": element, **result}

    async def entry(self, actor: CurrentUser, ip: str, drawing_id: str, element: str, value: Any) -> dict[str, Any]:
        key = (drawing_id, element)
        try:
            cfg = self._config(drawing_id, element, "entry")
            self._blocked(cfg)
            lock = self._lock(key)
        except ServiceError as exc:
            self._record(actor, ip, "symbol.entry", key, {"requested": value}, exc)
            raise
        async with lock:
            result = await self.operate.write(actor, ip, cfg["signals"][0]["tag"], value, action="symbol.entry")
        return {"element": element, **result}

    def accept(self, actor: CurrentUser, ip: str, drawing_id: str, element: str) -> dict[str, Any]:
        """Kvittér en afvigelse ved at acceptere PLC'ens position (der skrives intet til PLC'en)."""
        key = (drawing_id, element)
        cfg = self._config(drawing_id, element, "positions")
        st = self.runtime.state(drawing_id, element)
        if st is None or st.state != "mismatch" or st.remote is None:
            exc = ServiceError(409, "Der er ingen afvigelse at acceptere")
            self._record(actor, ip, "symbol.accept", key, {}, exc)
            raise exc
        labels = [p["label"] for p in cfg["positions"]]
        self.runtime.set_chosen(key, st.remote, f"accepteret af {actor.username}",
                                time.time() - float(cfg.get("validate_s", 5)))
        self.runtime.evaluate()
        self._record(actor, ip, "symbol.accept", key, {"from": labels[st.pos] if st.pos is not None else None,
                                                       "accepted": labels[st.remote]})
        return {"element": element, "position": st.remote, "label": labels[st.remote]}
