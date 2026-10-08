"""Runtime for én PLC: poll-løkke + valgfri SSE-lytter → live-cache.

- Poll-plan bygges ud fra de tags der hører til PLC'en.
- SSE sund → resync-poll hvert `slow_interval` (default 2 s); ellers `fast_interval` (0,5 s).
- Klientens rate-budget (≤ 5 req/s) er et hårdt loft: er planen større, bliver cyklussen
  bare længere.
- 32-bit-tags opdateres kun via polling (begge ord i samme kald). SSE-hændelser for
  enkeltregistre kunne ellers give et kortvarigt "halvt" tal.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from ..plc.client import PlcClient
from ..plc.errors import PlcError, PlcRateLimited
from ..plc.planner import ReadRange, plan_reads
from ..plc.sse import SseListener
from .live_cache import LiveCache, LiveValue
from .tagsource import ST_TYPE_MAP, TagSource, apply_scaling, decode_words

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeTag:
    name: str
    source: TagSource
    scale: float = 1.0
    offset: float = 0.0


@dataclass
class RuntimeStatus:
    state: str = "stopped"  # stopped | connecting | ok | error
    message: str = ""
    last_ok: float = 0.0
    cycles: int = 0
    errors: int = 0
    plan: list[dict[str, Any]] = field(default_factory=list)


class PlcRuntime:
    def __init__(
        self,
        key: str,
        client: PlcClient,
        cache: LiveCache,
        *,
        sse_enabled: bool = True,
        verify_tls: bool = True,
        fast_interval: float = 0.5,
        slow_interval: float = 2.0,
        error_retry_max: float = 10.0,
        sse_listener: SseListener | None = None,
    ):
        self.key = key
        self.client = client
        self.cache = cache
        self.fast_interval = fast_interval
        self.slow_interval = slow_interval
        self.error_retry_max = error_retry_max
        self.status = RuntimeStatus()
        self._tags: list[RuntimeTag] = []
        self._plan: list[ReadRange] = []
        self._programs: set[int] = set()
        self._need_globals = False
        self._raw: dict[str, dict[int, int]] = {"hr": {}, "ir": {}, "coil": {}, "di": {}}
        self._tasks: list[asyncio.Task[None]] = []
        self._wake = asyncio.Event()
        self.sse: SseListener | None = None
        if sse_enabled:
            self.sse = sse_listener or SseListener(client, self._on_sse_register, verify_tls=verify_tls)

    # ----------------------------------------------------------- livscyklus

    def start(self) -> None:
        if self._tasks:
            return
        self.status = RuntimeStatus(state="connecting")
        self._tasks.append(asyncio.create_task(self._poll_loop(), name=f"poll-{self.key}"))
        if self.sse is not None:
            self._tasks.append(asyncio.create_task(self.sse.run(), name=f"sse-{self.key}"))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                log.exception("Task for PLC %s endte med fejl ved stop", self.key)
        self._tasks.clear()
        await self.client.logout()
        await self.client.close()
        self.status.state = "stopped"

    # --------------------------------------------------------------- tags

    def set_tags(self, tags: list[RuntimeTag]) -> None:
        self._tags = [t for t in tags if t.source.plc == self.key]
        units: dict[str, set[tuple[int, int]]] = {}
        sse_addrs: dict[str, set[int]] = {}
        programs: set[int] = set()
        need_globals = False
        for tag in self._tags:
            src = tag.source
            if src.is_register:
                units.setdefault(src.kind, set()).add(src.unit())
                if src.words == 1:
                    sse_addrs.setdefault(src.kind, set()).add(src.addr)  # type: ignore[arg-type]
            elif src.kind == "logic":
                programs.add(src.program)  # type: ignore[arg-type]
            elif src.kind == "global":
                need_globals = True
        self._plan = plan_reads(units)
        self._programs = programs
        self._need_globals = need_globals
        self.status.plan = [{"kind": r.kind, "start": r.start, "count": r.count} for r in self._plan]
        if self.sse is not None:
            self.sse.set_addresses(sse_addrs)
        self._wake.set()

    def poke(self) -> None:
        """Poll straks (fx efter en skrivning), så Overview viser den nye værdi hurtigt."""
        self._wake.set()

    @property
    def requests_per_cycle(self) -> int:
        return len(self._plan) + len(self._programs) + (1 if self._need_globals else 0)

    # --------------------------------------------------------------- poll

    async def _poll_loop(self) -> None:
        retry = 1.0
        while True:
            interval = self.fast_interval
            if not self._tags:
                self.status.state = "ok" if self.status.cycles else "connecting"
                self.status.message = "Ingen tags for denne PLC"
                self._wake.clear()
                await self._wake.wait()
                continue
            try:
                await self.poll_once()
                retry = 1.0
                loop_time = asyncio.get_running_loop().time()
                if self.sse is not None and self.sse.healthy(loop_time):
                    interval = self.slow_interval
            except asyncio.CancelledError:
                raise
            except PlcError as exc:
                self._on_error(exc.message)
                interval = retry
                retry = min(retry * 2, self.error_retry_max)
                if isinstance(exc, PlcRateLimited):
                    interval = max(interval, 2.0)
            except Exception as exc:  # sidste værn: løkken må ikke dø stille
                log.exception("Uventet fejl i poll-løkke for %s", self.key)
                self._on_error(f"Intern fejl: {exc}")
                interval = retry
                retry = min(retry * 2, self.error_retry_max)
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    def _on_error(self, message: str) -> None:
        if self.status.state != "error" or self.status.message != message:
            log.warning("PLC %s: %s", self.key, message)
        self.status.state = "error"
        self.status.message = message
        self.status.errors += 1
        self.cache.mark_comm_error([t.name for t in self._tags], message)

    async def poll_once(self) -> None:
        """Én fuld cyklus. Kaster PlcError ved kommunikationsfejl."""
        for rng in self._plan:
            values = await self.client.read_bulk(rng.kind, rng.start, rng.count)
            self._raw[rng.kind].update(values)
        logic: dict[int, dict[str, Any]] = {}
        for program_id in sorted(self._programs):
            logic[program_id] = await self.client.logic_program(program_id)
        globals_: list[dict[str, Any]] | None = None
        if self._need_globals:
            globals_ = await self.client.logic_globals()
        self._publish(logic, globals_)
        self.status.state = "ok"
        self.status.message = ""
        self.status.last_ok = time.time()
        self.status.cycles += 1

    async def _on_sse_register(self, kind: str, addr: int, value: int) -> None:
        self._raw[kind][addr] = value
        affected = [t for t in self._tags if t.source.kind == kind and t.source.addr == addr and t.source.words == 1]
        if affected:
            now = time.time()
            self.cache.update({t.name: self._register_value(t, now) for t in affected})

    # ------------------------------------------------------------- afkodning

    def _publish(self, logic: dict[int, dict[str, Any]], globals_: list[dict[str, Any]] | None) -> None:
        now = time.time()
        changes: dict[str, LiveValue] = {}
        for tag in self._tags:
            src = tag.source
            if src.is_register:
                changes[tag.name] = self._register_value(tag, now)
            elif src.kind == "logic":
                changes[tag.name] = _variable_value(
                    tag, now, logic.get(src.program or 0, {}), f"ST-program {src.program}"
                )
            elif src.kind == "global":
                changes[tag.name] = _variable_value(tag, now, {"variables": globals_ or [], "compiled": True}, "GLOBAL_VAR")
        self.cache.update(changes)

    def _register_value(self, tag: RuntimeTag, now: float) -> LiveValue:
        src = tag.source
        raw = self._raw[src.kind]
        words = [raw.get(a) for a in range(src.addr, src.addr + src.words)]  # type: ignore[arg-type]
        if any(w is None for w in words):
            return LiveValue(quality="unknown", ts=now, error="Ingen værdi læst endnu")
        value = decode_words(words, src.datatype)  # type: ignore[arg-type]
        return LiveValue(value=apply_scaling(value, tag.scale, tag.offset), quality="good", ts=now)


def _variable_value(tag: RuntimeTag, now: float, body: dict[str, Any], where: str) -> LiveValue:
    if body.get("compiled") is False:
        return LiveValue(quality="bad", ts=now, error=f"{where} er ikke kompileret på PLC'en")
    for var in body.get("variables") or []:
        if isinstance(var, dict) and var.get("name") == tag.source.var:
            value = var.get("value")
            if ST_TYPE_MAP.get(str(var.get("type")).upper()) == "bool" and isinstance(value, (int, bool)):
                value = bool(value)
            return LiveValue(value=apply_scaling(value, tag.scale, tag.offset), quality="good", ts=now)
    return LiveValue(quality="bad", ts=now, error=f"Variablen '{tag.source.var}' findes ikke i {where}")
