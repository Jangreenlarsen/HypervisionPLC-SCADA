"""Runtime for én PLC: poll-løkke + valgfri SSE-lytter → live-cache.

- Poll-plan bygges ud fra de tags der hører til PLC'en.
- Hver `fast_interval` (0,5 s) polles alt, som SSE IKKE leverer: ST-variabler, GLOBAL_VAR,
  32-bit-registre og adresser PLC'en ikke har bekræftet i sin watch-list.
- Adresser SSE leverer, får kun en kontrol-poll hvert `slow_interval` (2 s). Er SSE nede,
  polles alt hurtigt.
- Klientens rate-budget (≤ 5 req/s) er et hårdt loft: er planen større, bliver cyklussen
  bare længere.
- 32-bit-tags opdateres kun via polling (begge ord i samme kald). SSE-hændelser for
  enkeltregistre kunne ellers give et kortvarigt "halvt" tal.
- Eksterne slaver (/api/ext, RS485 og expansion boards) polles hvert `ext_interval` (2 s) uden
  `wait`, så PLC'ens webserver ikke blokeres; `max_age` = intervallet. Første læsning af en ny
  adresse giver "pending" (ingen værdi endnu). En slave der ikke svarer (eller et board der ikke er
  konfigureret) markerer KUN sine egne tags som fejl — ikke hele PLC'en.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from ..plc.client import PlcClient, ext_base
from ..plc.errors import PlcApiError, PlcError, PlcRateLimited
from ..plc.planner import ExtRange, ReadRange, plan_ext_reads, plan_reads
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
        ext_interval: float = 2.0,
        error_retry_max: float = 10.0,
        sse_listener: SseListener | None = None,
    ):
        self.key = key
        self.client = client
        self.cache = cache
        self.fast_interval = fast_interval
        self.slow_interval = slow_interval
        self.ext_interval = ext_interval
        self.error_retry_max = error_retry_max
        self.status = RuntimeStatus()
        self._tags: list[RuntimeTag] = []
        self._plan: list[ReadRange] = []
        self._units: dict[str, set[tuple[int, int]]] = {}
        self._last_full = 0.0
        self._programs: set[int] = set()
        self._need_globals = False
        self._raw: dict[str, dict[int, int]] = {"hr": {}, "ir": {}, "coil": {}, "di": {}}
        self._ext_plan: list[ExtRange] = []
        self._ext_last = 0.0
        # (gruppe, adresse) → (værdi, status, fejltekst); status ok | pending | error
        self._ext_raw: dict[tuple[tuple, int], tuple[Any, str, str]] = {}
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
        ext_units: dict[tuple, set[tuple[int, int]]] = {}
        for tag in self._tags:
            src = tag.source
            if src.is_external:
                ext_units.setdefault(src.ext_group, set()).add(src.unit())
            elif src.is_register:
                units.setdefault(src.kind, set()).add(src.unit())
                if src.words == 1:
                    sse_addrs.setdefault(src.kind, set()).add(src.addr)  # type: ignore[arg-type]
            elif src.kind == "logic":
                programs.add(src.program)  # type: ignore[arg-type]
            elif src.kind == "global":
                need_globals = True
        self._units = units
        self._plan = plan_reads(units)
        self._last_full = 0.0
        self._programs = programs
        self._need_globals = need_globals
        self._ext_plan = plan_ext_reads(ext_units)
        self._ext_last = 0.0
        self.status.plan = ([{"kind": r.kind, "start": r.start, "count": r.count} for r in self._plan] +
                            [{"kind": r.kind, "start": r.start, "count": r.count, "ext": ":".join(
                                str(x) for x in r.group[:4] if x is not None)} for r in self._ext_plan])
        if self.sse is not None:
            self.sse.set_addresses(sse_addrs)
        self._wake.set()

    def poke(self) -> None:
        """Poll straks (fx efter en skrivning), så Overview viser den nye værdi hurtigt."""
        self._wake.set()

    @property
    def requests_per_cycle(self) -> int:
        return len(self._plan) + len(self._programs) + (1 if self._need_globals else 0) + len(self._ext_plan)

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
                now = asyncio.get_running_loop().time()
                sse_ok = self.sse is not None and self.sse.healthy(now)
                full = not sse_ok or now - self._last_full >= self.slow_interval
                await self.poll_once(full=full)
                if full:
                    self._last_full = now
                retry = 1.0
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

    def _plan_for(self, full: bool) -> list[ReadRange]:
        if full or self.sse is None:
            return self._plan
        sse = self.sse
        uncovered = {kind: {u for u in units if not (u[0] == u[1] and sse.covers(kind, u[0]))}
                     for kind, units in self._units.items()}
        return plan_reads(uncovered)

    async def poll_once(self, full: bool = True) -> None:
        """Én cyklus (`full=False`: kun det SSE ikke leverer). Kaster PlcError ved kommunikationsfejl."""
        for rng in self._plan_for(full):
            values = await self.client.read_bulk(rng.kind, rng.start, rng.count)
            self._raw[rng.kind].update(values)
        logic: dict[int, dict[str, Any]] = {}
        for program_id in sorted(self._programs):
            logic[program_id] = await self.client.logic_program(program_id)
        globals_: list[dict[str, Any]] | None = None
        if self._need_globals:
            globals_ = await self.client.logic_globals()
        now = time.monotonic()
        if self._ext_plan and (now - self._ext_last >= self.ext_interval or self._ext_last == 0.0):
            self._ext_last = now
            await self._poll_ext()
        self._publish(logic, globals_)
        self.status.state = "ok"
        self.status.message = ""
        self.status.last_ok = time.time()
        self.status.cycles += 1

    async def _poll_ext(self) -> None:
        """Eksterne slaver. Svarer PLC'en med en fejl for ét område (fx 404 board ikke konfigureret, 409 Modbus
        Master slået fra, 502), markeres kun det områdes tags; forbindelsesfejl til PLC'en kastes videre."""
        max_age = int(self.ext_interval * 1000)
        for rng in self._ext_plan:
            src = _group_source(rng.group)
            try:
                items = await self.client.read_ext(ext_base(src), rng.kind, rng.start, rng.count, max_age_ms=max_age)
            except PlcApiError as exc:
                for i in range(rng.count):
                    self._ext_raw[(rng.group, rng.start + i)] = (None, "error", exc.message)
                continue
            for i, (value, state) in enumerate(items):
                key = (rng.group, rng.start + i)
                old = self._ext_raw.get(key)
                if state == "pending" and old is not None and old[1] == "ok":
                    continue  # behold sidste kendte værdi, til slaven har svaret igen
                self._ext_raw[key] = (value, state, "")

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
            if src.is_external:
                changes[tag.name] = self._ext_value(tag, now)
            elif src.is_register:
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


    def _ext_value(self, tag: RuntimeTag, now: float) -> LiveValue:
        src = tag.source
        entries = [self._ext_raw.get((src.ext_group, a)) for a in range(src.addr, src.addr + src.words)]  # type: ignore[arg-type]
        if any(e is None for e in entries):
            return LiveValue(quality="unknown", ts=now, error="Ingen værdi læst endnu")
        for value, state, message in entries:  # type: ignore[misc]
            if state == "error":
                return LiveValue(quality="bad", ts=now, error=message or f"{src.device} svarer ikke")
            if state == "pending" or value is None:
                return LiveValue(quality="unknown", ts=now, error=f"Venter på første svar fra {src.device}")
        words = [int(bool(v)) if isinstance(v, bool) else int(v) for v, _, _ in entries]  # type: ignore[misc]
        value = decode_words(words, src.datatype)  # type: ignore[arg-type]
        return LiveValue(value=apply_scaling(value, tag.scale, tag.offset), quality="good", ts=now)


def _group_source(group: tuple) -> TagSource:
    bus, board, channel, slave, kind = group
    return TagSource(plc="", kind=kind, datatype="uint", bus=bus, board=board, channel=channel, slave=slave)


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
