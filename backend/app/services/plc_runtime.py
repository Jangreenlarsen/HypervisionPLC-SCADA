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
import collections
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from ..plc.client import PlcClient, ext_base
from ..plc.errors import PlcApiError, PlcAuthError, PlcError, PlcForbidden, PlcRateLimited
from ..plc.planner import ExtRange, ReadRange, plan_ext_reads, plan_reads
from ..plc.sse import SseListener
from .live_cache import LiveCache, LiveValue
from .tagsource import CHANNELS, ST_TYPE_MAP, TagSource, apply_scaling, decode_words

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeTag:
    name: str
    source: TagSource
    scale: float = 1.0
    offset: float = 0.0


@dataclass
class _Failure:
    """Ét kald i en cyklus, der fejlede — isoleret til de tags, kaldet dækker."""
    what: str
    exc: PlcError
    names: list[str]


# Rate-limit (429): PLC'en lever, men vil have færre kald. Så længe det varer kortere end dette, beholdes de sidste
# værdier (ingen "kommunikation tabt" og dermed ingen COMM-alarm); først derefter regnes det for en kommunikationsfejl.
RATE_LIMIT_GRACE_S = 60.0

# Efter en fejl spørger vi ikke igen med det samme om det samme (skåner en presset PLC): 2 s, 4 s … højst 20 s
COOL_STEP_S = 2.0
COOL_MAX_S = 20.0


@dataclass
class RuntimeStatus:
    state: str = "stopped"  # stopped | connecting | ok | error
    message: str = ""
    last_ok: float = 0.0
    cycles: int = 0
    errors: int = 0
    plan: list[dict[str, Any]] = field(default_factory=list)
    partial: list[dict[str, Any]] = field(default_factory=list)   # kald der fejlede i den seneste cyklus, mens resten virkede
    throttled: int = 0           # antal gange PLC'en har afvist kald pga. rate-limit (429) siden start
    last_throttled: float = 0.0  # tidspunkt (epoch) for seneste afvisning


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
        auth_retry_s: float = 60.0,
        rate_limit_grace_s: float = RATE_LIMIT_GRACE_S,
        sse_listener: SseListener | None = None,
    ):
        self.key = key
        self.client = client
        self.cache = cache
        self.fast_interval = fast_interval
        self.slow_interval = slow_interval
        self.ext_interval = ext_interval
        self.error_retry_max = error_retry_max
        self.auth_retry_s = auth_retry_s
        self.rate_limit_grace_s = rate_limit_grace_s
        self._throttled_since: float | None = None
        # (tid, kald i alt) pr. cyklus — så en afvisning kan logges med hvor mange kald vi faktisk sendte
        self._req_samples: collections.deque[tuple[float, int]] = collections.deque(maxlen=400)
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
        self._cool: dict[str, tuple[float, PlcError]] = {}      # kald → (spørg ikke før, sidste fejl)
        self._fails: dict[str, int] = {}                        # kald → antal fejl i træk
        self._timing: dict[str, list[float]] = {}               # kald → [sidste, største] svartid i sekunder
        self._wake = asyncio.Event()
        self.sse: SseListener | None = None
        if sse_enabled:
            self.sse = sse_listener or SseListener(client, self._on_sse_register, verify_tls=verify_tls,
                                                   on_ext=self._on_sse_ext)

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
            # eksterne tags → watch_all, så PLC'en også sender deres ændringer (`ext`, v0.90.0)
            self.sse.set_addresses(sse_addrs, external=bool(ext_units))
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
                if self._throttled_since is not None:
                    log.info("PLC %s: svarer igen efter rate-limit (%.0f s)", self.key, time.monotonic() - self._throttled_since)
                    self._throttled_since = None
            except asyncio.CancelledError:
                raise
            except PlcRateLimited as exc:
                self._on_throttled(exc)
                interval = max(retry, 2.0)
                retry = min(retry * 2, self.error_retry_max)
            except PlcError as exc:
                self._on_error(exc.message)
                interval = retry
                retry = min(retry * 2, self.error_retry_max)
                if isinstance(exc, PlcAuthError):
                    # Afvist login: prøv sjældnere — hvert forsøg tæller som en auth-fejl og kan udløse PLC'ens alarm for
                    # stigende login-fejl. Rettes adgangskoden i SCADA, genstartes forbindelsen alligevel straks.
                    interval = max(interval, self.auth_retry_s)
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

    def _request_rate(self, window_s: float = 60.0) -> float | None:
        """Kald pr. sekund, SCADA har sendt til PLC'en det seneste minut (None hvis for få målinger)."""
        now = time.monotonic()
        self._req_samples.append((now, self.client.request_count))
        old = next(((t, n) for t, n in self._req_samples if now - t <= window_s), None)
        if old is None or now - old[0] < 5:
            return None
        return (self.client.request_count - old[1]) / (now - old[0])

    def _on_throttled(self, exc: PlcError) -> None:
        """PLC'en afviste kald pga. rate-limit (429). Den lever: behold de sidste værdier og vent (klienten backer selv af).
        Varer det mere end `rate_limit_grace_s`, behandles det som en kommunikationsfejl (og giver COMM-alarm)."""
        now = time.monotonic()
        self.status.throttled += 1
        self.status.last_throttled = time.time()
        if self._throttled_since is None:
            self._throttled_since = now
            rate = self._request_rate()
            log.warning("PLC %s: rate-limit (429) — %s; SCADA sendte %s kald/s det seneste minut", self.key, exc.message,
                        f"{rate:.1f}" if rate is not None else "?")
        lasted = now - self._throttled_since
        if lasted >= self.rate_limit_grace_s:
            self._on_error(f"{exc.message} — PLC'en har afvist kald i {lasted:.0f} s")
            return
        if self.status.state != "error":
            self.status.message = ("PLC'en beder om færre kald (rate-limit) — SCADA venter lidt og prøver igen; "
                                   "værdierne er fra seneste vellykkede aflæsning")

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
        failures: list[_Failure] = []
        attempts = [0]
        for rng in self._plan_for(full):
            values = await self._guarded(f"{rng.kind} {rng.start}–{rng.end}", self._names_in(rng.kind, rng.start, rng.end),
                                         lambda rng=rng: self.client.read_bulk(rng.kind, rng.start, rng.count), failures, attempts)
            if values is not None:
                self._raw[rng.kind].update(values)
        logic: dict[int, dict[str, Any]] = {}
        for program_id in sorted(self._programs):
            body = await self._guarded(f"ST-program {program_id}",
                                       [t.name for t in self._tags if t.source.kind == "logic" and t.source.program == program_id],
                                       lambda p=program_id: self.client.logic_program(p), failures, attempts)
            if body is not None:
                logic[program_id] = body
        globals_: list[dict[str, Any]] | None = None
        if self._need_globals:
            globals_ = await self._guarded("GLOBAL_VAR", [t.name for t in self._tags if t.source.kind == "global"],
                                           self.client.logic_globals, failures, attempts)
        now = time.monotonic()
        if self._ext_plan and (now - self._ext_last >= self.ext_interval or self._ext_last == 0.0):
            self._ext_last = now
            await self._poll_ext(failures, attempts)
        if failures and len(failures) >= attempts[0]:
            raise failures[0].exc   # intet virkede: hele PLC'en er tabt (som før)
        failed = {n for f in failures for n in f.names}
        self._publish(logic, globals_, skip=failed)
        for f in failures:   # kun de tags, det fejlede kald dækker, mister forbindelsen — resten viser friske værdier
            self.cache.mark_comm_error(f.names, f.exc.message)
        self.status.partial = [{"what": f.what, "message": f.exc.message, "tags": len(f.names)} for f in failures]
        self.status.state = "ok"
        self.status.message = ""
        if failures:
            first = failures[0]
            more = f" (+{len(failures) - 1} andre)" if len(failures) > 1 else ""
            self.status.message = f"Delvis kommunikationsfejl: {first.what} — {first.exc.message}{more}"
            self.status.errors += 1
        self.status.last_ok = time.time()
        self.status.cycles += 1
        self._req_samples.append((time.monotonic(), self.client.request_count))

    def _names_in(self, kind: str, first: int, last: int, group: tuple | None = None) -> list[str]:
        """Tags der læser (en del af) adresseområdet — PLC'ens egne registre, eller en ekstern slaves (`group`)."""
        out = []
        for t in self._tags:
            s = t.source
            if group is not None:
                hit = s.is_external and s.ext_group == group
            else:
                hit = s.is_register and not s.is_external and s.kind == kind
            if hit and s.addr is not None and s.addr <= last and s.addr + s.words > first:
                out.append(t.name)
        return out

    async def _guarded(self, what: str, names: list[str], call: Any, failures: list[_Failure], attempts: list[int]) -> Any:
        """Kør ét kald. En fejl isoleres til kaldets tags (og kaldet hvile et øjeblik), så ét langsomt register eller én
        ST-variabel ikke tager hele PLC'en ned. Login-, rettigheds- og rate-fejl rammer alt og kastes videre.
        Returnerer None, hvis kaldet fejlede."""
        attempts[0] += 1
        until, last = self._cool.get(what, (0.0, None))
        if last is not None and time.monotonic() < until:
            failures.append(_Failure(what, last, names))
            return None
        t0 = time.monotonic()
        try:
            result = await call()
        except (PlcAuthError, PlcForbidden, PlcRateLimited):
            raise
        except PlcError as exc:
            n = self._fails.get(what, 0) + 1
            self._fails[what] = n
            self._cool[what] = (time.monotonic() + min(COOL_STEP_S * n, COOL_MAX_S), exc)
            log.warning("PLC %s: %s fejlede (%d i træk): %s", self.key, what, n, exc.message)
            failures.append(_Failure(what, exc, names))
            return None
        dt = time.monotonic() - t0
        self._fails.pop(what, None)
        self._cool.pop(what, None)
        t = self._timing.setdefault(what, [0.0, 0.0])
        t[0], t[1] = dt, max(t[1], dt)
        return result

    def slowest(self, n: int = 5) -> list[dict[str, Any]]:
        """De langsomste kald siden start (største svartid) — til fejlfinding af kommunikationsfejl."""
        top = sorted(self._timing.items(), key=lambda kv: kv[1][1], reverse=True)[:n]
        return [{"what": k, "last_s": round(v[0], 3), "max_s": round(v[1], 3)} for k, v in top]

    async def _poll_ext(self, failures: list[_Failure], attempts: list[int]) -> None:
        """Eksterne slaver. Svarer PLC'en med en fejl for ét område (fx 404 board ikke konfigureret, 409 Modbus
        Master slået fra, 502), markeres kun det områdes tags; forbindelsesfejl til PLC'en kastes videre."""
        max_age = int(self.ext_interval * 1000)
        for rng in self._ext_plan:
            src = _group_source(rng.group)

            async def call(rng: ExtRange = rng, src: TagSource = src) -> Any:
                try:
                    return await self.client.read_ext(ext_base(src), rng.kind, rng.start, rng.count, max_age_ms=max_age)
                except PlcApiError as exc:
                    return exc   # PLC'en svarede med en fejl for netop dette område: markeres nedenfor
            names = self._names_in(rng.kind, rng.start, rng.start + rng.count - 1, group=rng.group)
            items = await self._guarded(f"ekstern {':'.join(str(x) for x in rng.group[:4] if x is not None)} {rng.start}–{rng.start + rng.count - 1}",
                                        names, call, failures, attempts)
            if items is None:
                continue
            if isinstance(items, PlcApiError):
                for i in range(rng.count):
                    self._ext_raw[(rng.group, rng.start + i)] = (None, "error", items.message)
                continue
            for i, (value, state) in enumerate(items):
                key = (rng.group, rng.start + i)
                old = self._ext_raw.get(key)
                if state == "pending" and old is not None and old[1] == "ok":
                    continue  # behold sidste kendte værdi, til slaven har svaret igen
                self._ext_raw[key] = (value, state, "")

    def _on_sse_ext(self, data: dict[str, Any]) -> None:
        """En ny værdi i PLC'ens Modbus-cache (SSE `ext`, v0.90.0) — samme regler som pollingen: "pending" beholder sidst
        kendte værdi, "error" markerer tagget. Kun registre som et tag bruger; resten af cachen (ST's egne) ignoreres."""
        if data["src"] == "rtu":
            group: tuple = ("rtu", None, None, data["slave"], data["type"])
        elif 1 <= data["ch"] <= len(CHANNELS):
            group = ("mbx", data["board"], CHANNELS[data["ch"] - 1], data["slave"], data["type"])
        else:
            return
        addr = data["addr"]
        affected = [t for t in self._tags if t.source.is_external and t.source.ext_group == group
                    and t.source.addr <= addr < t.source.addr + t.source.words]  # type: ignore[operator]
        if not affected:
            return
        key = (group, addr)
        old = self._ext_raw.get(key)
        if data["status"] == "pending":
            if old is not None and old[1] == "ok":
                return  # behold sidste kendte værdi, til slaven har svaret igen
            self._ext_raw[key] = (None, "pending", "")
        elif data["status"] == "error":
            self._ext_raw[key] = (None, "error", "")
        else:
            self._ext_raw[key] = (data["value"], "ok", "")
        now = time.time()
        self.cache.update({t.name: self._ext_value(t, now) for t in affected})

    async def _on_sse_register(self, kind: str, addr: int, value: int) -> None:
        self._raw[kind][addr] = value
        # Kun PLC'ens egne registre — eksterne værdier kommer som `ext` (ovenfor), og et eksternt tag med samme
        # type/adresse (fx plc1:mbx:1:D:1:coil:0 vs. plc1:coil:0) må ikke overskrives (v0.25.1)
        affected = [t for t in self._tags if t.source.is_register and t.source.kind == kind
                    and t.source.addr == addr and t.source.words == 1]
        if affected:
            now = time.time()
            self.cache.update({t.name: self._register_value(t, now) for t in affected})

    # ------------------------------------------------------------- afkodning

    def _publish(self, logic: dict[int, dict[str, Any]], globals_: list[dict[str, Any]] | None,
                 skip: set[str] | frozenset[str] = frozenset()) -> None:
        now = time.time()
        changes: dict[str, LiveValue] = {}
        for tag in self._tags:
            if tag.name in skip:
                continue   # kaldet der dækker tagget fejlede: markeres som kommunikationsfejl af kalderen
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
