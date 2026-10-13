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
import logging
import time
from typing import Any

from .audit import AuditService
from .auth import CurrentUser, verify_password
from .errors import ServiceError
from .operate import OperateService
from .symbol_runtime import SymbolRuntime
from .symbols import needs_pin, write_plan

log = logging.getLogger(__name__)

PIN_TRIES = 3
PIN_LOCK_S = 60.0


class SymbolOperateService:
    def __init__(self, operate: OperateService, runtime: SymbolRuntime, audit: AuditService):
        self.operate = operate
        self.runtime = runtime
        self.db = operate.db
        self.cache = operate.manager.cache
        self.audit = audit
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}
        # Nøglelås: forkerte koder pr. (symbol, bruger) → (antal, spærret til). Kun i hukommelsen (nulstilles ved
        # genstart — samme som login-låsningen).
        self._pin_fails: dict[tuple[str, str, str], tuple[int, float]] = {}
        self._background: set[asyncio.Task[Any]] = set()

    # ------------------------------------------------------------- fælles tjek

    def _config(self, drawing_id: str, element: str, op: str) -> dict[str, Any]:
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

    def _check_pin(self, actor: CurrentUser, ip: str, key: tuple[str, str], pin: str | None, label: str) -> None:
        fail_key = (key[0], key[1], actor.username)
        count, until = self._pin_fails.get(fail_key, (0, 0.0))
        now = time.time()
        if until > now:
            raise ServiceError(429, f"For mange forkerte koder — prøv igen om {int(until - now) + 1} s")
        stored = self.db.get_symbol_pin_hash(*key)
        if stored is None:
            raise ServiceError(409, f"{label} er låst, og der er ingen kode — en tekniker skal sætte en kode")
        if not pin:
            raise ServiceError(403, f"{label} er låst — indtast koden")
        if not verify_password(pin, stored):
            count += 1
            if count >= PIN_TRIES:
                self._pin_fails[fail_key] = (0, now + PIN_LOCK_S)
                self._record(actor, ip, "symbol.pin_failed", key, {"attempts": count, "locked_s": PIN_LOCK_S})
                raise ServiceError(429, f"Forkert kode {PIN_TRIES} gange — betjening af symbolet er spærret i "
                                        f"{int(PIN_LOCK_S)} s")
            self._pin_fails[fail_key] = (count, 0.0)
            self._record(actor, ip, "symbol.pin_failed", key, {"attempts": count})
            raise ServiceError(403, f"Forkert kode ({count} af {PIN_TRIES} forsøg)")
        self._pin_fails.pop(fail_key, None)
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
                self._check_pin(actor, ip, key, pin, label)
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
