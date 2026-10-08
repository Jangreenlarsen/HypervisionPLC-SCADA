"""Trend-optager: gemmer historik for tags med `trend` slået til.

Regler (skåner disken på en Raspberry Pi):
- En værdi gemmes når den ændrer sig — højst én gang pr. `trend_interval_s`. En ændring inden for
  intervallet huskes og gemmes når intervallet er gået (den seneste værdi går ikke tabt).
- Til/fra-skift gemmes altid med det samme.
- "Jeg lever"-værdi hvert `keepalive_s` sekund, så grafen ikke ser ud til at stoppe.
- Ingen gyldig værdi (PLC nede) gemmes som et hul (NULL), så grafen ikke tegner en falsk linje.
- Skrives samlet (én transaktion) hvert `flush_s` sekund; data ældre end `retention_days` slettes.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from ..storage.trends_db import TrendDatabase
from .live_cache import LiveValue
from .manager import PlcManager

log = logging.getLogger(__name__)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return None


class TrendRecorder:
    def __init__(self, manager: PlcManager, tdb: TrendDatabase, *, flush_s: float = 5.0,
                 keepalive_s: float = 300.0, retention_days: float = 30.0, energy_days: float = 400.0):
        self.manager = manager
        self.tdb = tdb
        self.flush_s = flush_s
        self.keepalive_s = keepalive_s
        self.retention_days = retention_days
        self.energy_days = energy_days
        self._last: dict[str, tuple[float, float | None]] = {}
        self._pending: dict[str, tuple[float, float | None]] = {}
        self._buffer: list[tuple[str, float, float | None]] = []
        self._config: dict[str, tuple[float, bool]] = {}  # navn → (interval, er til/fra)
        self._last_purge = 0.0

    def _refresh_config(self) -> None:
        from .tagsource import TagSourceError, parse_source

        cfg = {}
        for t in self.manager.db.list_trend_tags():
            try:
                is_bool = parse_source(t["source"]).datatype == "bool"
            except TagSourceError:
                is_bool = False
            cfg[t["name"]] = (float(t["trend_interval_s"]), is_bool)
        self._config = cfg

    def offer(self, name: str, live: LiveValue) -> None:
        cfg = self._config.get(name)
        if cfg is None:
            return
        interval, is_bool = cfg
        value = _number(live.value) if live.quality == "good" else None
        if live.quality == "good" and value is None:
            return  # strenge o.l. kan ikke vises som graf
        ts = live.ts or time.time()
        last = self._last.get(name)
        bool_change = (is_bool or isinstance(live.value, bool)) and last is not None and value != last[1]
        if last is None or (value is None) != (last[1] is None) or bool_change:
            self._store(name, ts, value)
        elif value != last[1]:
            if ts - last[0] >= interval:
                self._store(name, ts, value)
            else:
                self._pending[name] = (ts, value)

    def forget(self, name: str) -> int:
        """Slet al historik for tagget — også værdier der endnu ikke er skrevet (ellers dukker de op igen).
        Returnerer antal slettede samples."""
        self._buffer = [r for r in self._buffer if r[0] != name]
        self._last.pop(name, None)
        self._pending.pop(name, None)
        before = self.tdb.stats().get(name, {}).get("samples", 0)
        self.tdb.forget(name)
        return before

    def _store(self, name: str, ts: float, value: float | None) -> None:
        self._buffer.append((name, ts, value))
        self._last[name] = (ts, value)
        self._pending.pop(name, None)

    def flush(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        self._refresh_config()
        for name, (ts, value) in list(self._pending.items()):
            interval = self._config.get(name, (10.0, False))[0]
            if now - self._last.get(name, (0.0, None))[0] >= interval:
                self._store(name, ts, value)  # gemmes med det tidspunkt værdien blev målt
        for name in self._config:
            last = self._last.get(name)
            live = self.manager.cache.get(name)
            if live.quality == "good" and (last is None or now - last[0] >= self.keepalive_s):
                value = _number(live.value)
                if value is not None:
                    self._store(name, now, value)
        rows, self._buffer = self._buffer, []
        self.tdb.insert_many(rows)
        if now - self._last_purge >= 3600:
            self._last_purge = now
            energy_cut = now - max(self.energy_days, self.retention_days) * 86400
            keep = {t["name"]: energy_cut for t in self.manager.db.list_energy_tags()}
            removed = self.tdb.purge_before(now - self.retention_days * 86400, keep)
            if removed:
                log.info("Trend: slettede %d samples ældre end %g dage", removed, self.retention_days)
        return len(rows)

    async def run(self) -> None:
        queue = self.manager.cache.subscribe(maxsize=2000)
        self._refresh_config()
        next_flush = time.monotonic() + self.flush_s
        try:
            while True:
                timeout = max(0.0, next_flush - time.monotonic())
                try:
                    delta = await asyncio.wait_for(queue.get(), timeout=timeout)
                    for name in delta:
                        self.offer(name, self.manager.cache.get(name))
                except asyncio.TimeoutError:
                    pass
                if time.monotonic() >= next_flush:
                    next_flush = time.monotonic() + self.flush_s
                    try:
                        self.flush()
                    except Exception:
                        log.exception("Trend: kunne ikke gemme samples")
        finally:
            self.manager.cache.unsubscribe(queue)
            try:
                self.flush()  # gem det sidste ved nedlukning
            except Exception:
                log.exception("Trend: kunne ikke gemme ved nedlukning")
