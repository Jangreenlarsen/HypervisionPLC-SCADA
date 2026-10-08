"""Lytter på PLC'ens SSE-strøm (`GET :<sse_port>/api/events`).

SSE er et supplement til polling, ikke en forudsætning (docs/HYPERVISIONPLC_ANALYSE.md):
- højst 3 SSE-klienter pr. PLC (delt med PLC'ens eget dashboard) → 503 er normalt,
- strømmen er altid ukrypteret,
- watch-list max 32 adresser pr. type (ellers `subscribe=all`); HR/IR kun 0-159, coils/DI 0-255
  (sse_events.cpp: sse_parse_addr_list(..., 159/255)),
- PLC'en URL-afkoder IKKE query-strengen: kommaer skal sendes ukodede, ellers læses kun den
  første adresse (SCADA BUGS v0.7.0).

"Dækning": en adresse regnes kun som leveret af SSE, når PLC'ens `connected`-hændelse bekræfter
at den overvåger præcis det antal adresser vi bad om. Alt andet polles hurtigt.
"""

from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import quote
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit

import httpx

from .client import PlcClient
from .errors import PlcError

log = logging.getLogger(__name__)

SSE_MAX_WATCH = 32
SSE_ADDR_MAX = {"hr": 159, "ir": 159, "coil": 255, "di": 255}
_WATCH_PARAM = {"hr": "hr", "ir": "ir", "coil": "coils", "di": "di"}


@dataclass
class SseEvent:
    event: str
    data: Any


class SseParser:
    """Inkrementel parser af text/event-stream. Fodres med linjer, returnerer færdige events."""

    def __init__(self) -> None:
        self._event = "message"
        self._data: list[str] = []

    def feed_line(self, line: str) -> SseEvent | None:
        line = line.rstrip("\r")
        if line == "":
            if not self._data:
                self._event = "message"
                return None
            raw = "\n".join(self._data)
            event = self._event
            self._event, self._data = "message", []
            try:
                data: Any = json.loads(raw)
            except ValueError:
                data = raw
            return SseEvent(event, data)
        if line.startswith(":"):
            return None  # kommentar/keepalive
        name, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if name == "event":
            self._event = value
        elif name == "data":
            self._data.append(value)
        return None


def build_watch(addresses: dict[str, set[int]]) -> tuple[dict[str, str], bool]:
    """Byg query-parametre. Returnerer (params, watch_all)."""
    eligible = {k: sorted(a for a in addrs if 0 <= a <= SSE_ADDR_MAX[k]) for k, addrs in addresses.items()}
    if any(len(v) > SSE_MAX_WATCH for v in eligible.values()):
        return {"subscribe": "all"}, True
    params = {"subscribe": "registers,system"}
    for kind, addrs in eligible.items():
        if addrs:
            params[_WATCH_PARAM[kind]] = ",".join(str(a) for a in addrs)
    return params, False


def build_query(params: dict[str, str]) -> str:
    """Query-streng med ukodede kommaer — PLC'en afkoder ikke %2C (se modulets docstring)."""
    return "&".join(f"{k}={quote(str(v), safe=',')}" for k, v in params.items())


# PLC'ens navne i `connected.watching` (den rigtige PLC skriver "coils"; vi accepterer begge)
_WATCHING_KEYS = {"hr": ("hr",), "ir": ("ir",), "coil": ("coils", "coil"), "di": ("di",)}


@dataclass
class SseState:
    state: str = "off"  # off | connecting | connected | full | disabled_on_plc | error
    message: str = ""
    last_event_monotonic: float = 0.0
    events: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


RegisterCallback = Callable[[str, int, int], Awaitable[None] | None]


class SseListener:
    """Holder én SSE-forbindelse åben og genforbinder ved fejl."""

    def __init__(
        self,
        client: PlcClient,
        on_register: RegisterCallback,
        *,
        verify_tls: bool = True,
        heartbeat_timeout_s: float = 45.0,
        retry_s: float = 5.0,
        full_retry_s: float = 30.0,
    ):
        self._client = client
        self._on_register = on_register
        self._verify = verify_tls
        self._heartbeat_timeout = heartbeat_timeout_s
        self._retry_s = retry_s
        self._full_retry_s = full_retry_s
        self._addresses: dict[str, set[int]] = {}
        self._addresses_changed = asyncio.Event()
        self.status = SseState()
        self._requested: dict[str, set[int]] = {}
        self._watch_all = False
        self.covered: dict[str, set[int]] = {}

    def set_addresses(self, addresses: dict[str, set[int]]) -> None:
        if addresses != self._addresses:
            self._addresses = {k: set(v) for k, v in addresses.items()}
            self._addresses_changed.set()

    def healthy(self, now: float) -> bool:
        return self.status.state == "connected" and now - self.status.last_event_monotonic < self._heartbeat_timeout

    def covers(self, kind: str, addr: int) -> bool:
        """Leverer SSE ændringer for denne adresse (bekræftet af PLC'en)?"""
        return self.status.state == "connected" and addr in self.covered.get(kind, ())

    def _on_connected(self, data: Any) -> None:
        watching = data.get("watching") if isinstance(data, dict) else None
        covered: dict[str, set[int]] = {}
        short: list[str] = []
        for kind, wanted in self._requested.items():
            if not wanted:
                continue
            if self._watch_all:
                covered[kind] = set(wanted)
                continue
            got = None
            if isinstance(watching, dict):
                for key in _WATCHING_KEYS[kind]:
                    if isinstance(watching.get(key), int):
                        got = watching[key]
                        break
            if got == len(wanted):
                covered[kind] = set(wanted)
            else:
                short.append(f"{kind}: {got if got is not None else '?'} af {len(wanted)}")
        self.covered = covered
        if short:
            msg = "PLC'en overvåger færre adresser end ønsket (" + ", ".join(short) + ") — de polles i stedet"
            log.warning("SSE %s: %s", self._client.name, msg)
            self.status.message = msg

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            if not any(self._addresses.values()):
                self.status = SseState(state="off", message="Ingen adresser at overvåge")
                self._addresses_changed.clear()
                await self._addresses_changed.wait()
                continue
            delay = self._retry_s
            try:
                delay = await self._connect_once(loop)
            except asyncio.CancelledError:
                raise
            except PlcError as exc:
                self.status = SseState(state="error", message=exc.message)
            except (httpx.HTTPError, OSError) as exc:
                self.status = SseState(state="error", message=f"SSE-forbindelse afbrudt: {exc}")
            except Exception as exc:  # sidste værn: listeneren må aldrig dø stille
                log.exception("Uventet fejl i SSE-lytter for %s", self._client.name)
                self.status = SseState(state="error", message=f"Uventet fejl: {exc}")
            self._addresses_changed.clear()
            try:
                await asyncio.wait_for(self._addresses_changed.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    async def _connect_once(self, loop: asyncio.AbstractEventLoop) -> float:
        """Én forbindelse. Returnerer ventetid før næste forsøg."""
        self.status = SseState(state="connecting")
        info = await self._client.sse_status()
        if not info.get("sse_enabled", False):
            self.status = SseState(state="disabled_on_plc", message="SSE er slået fra på PLC'en — kører på polling")
            return self._full_retry_s
        port = info.get("sse_port")
        token = info.get("sse_token")
        if not isinstance(port, int) or not isinstance(token, str) or not token:
            self.status = SseState(state="error", message="PLC'en returnerede ingen SSE-port/-token")
            return self._full_retry_s

        host = urlsplit(self._client.base_url).hostname
        params, watch_all = build_watch(self._addresses)
        self._watch_all = watch_all
        self._requested = {k: {a for a in v if 0 <= a <= SSE_ADDR_MAX[k]} for k, v in self._addresses.items()}
        self.covered = {}
        params["token"] = token
        # PLC'ens SSE er altid plain HTTP (SECURITY_INDEX #13); query bygges selv (ukodede kommaer).
        url = f"http://{host}:{port}/api/events?{build_query(params)}"
        timeout = httpx.Timeout(10.0, read=self._heartbeat_timeout)
        parser = SseParser()
        async with httpx.AsyncClient(timeout=timeout) as http:
            async with http.stream("GET", url) as resp:
                if resp.status_code == 503:
                    self.status = SseState(state="full", message="PLC'ens SSE-pladser er optaget — kører på polling")
                    return self._full_retry_s
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="replace")[:200]
                    self.status = SseState(state="error", message=f"SSE afvist (HTTP {resp.status_code}): {body}")
                    return self._retry_s
                self.status = SseState(state="connected", last_event_monotonic=loop.time(),
                                       extra={"watch_all": watch_all})
                self._addresses_changed.clear()
                async for line in resp.aiter_lines():
                    if self._addresses_changed.is_set():
                        return 0.0  # ny watch-list → genforbind straks
                    self.status.last_event_monotonic = loop.time()
                    event = parser.feed_line(line)
                    if event is None:
                        continue
                    if event.event.startswith("HTTP/"):
                        # PLC BUG-483: en rå statuslinje midt i strømmen = pladsen var ikke reelt fri
                        self.status = SseState(state="full", message="PLC'ens SSE-pladser er optaget")
                        return self._full_retry_s
                    self.status.events += 1
                    if event.event == "connected":
                        self._on_connected(event.data)
                    elif event.event == "register" and isinstance(event.data, dict):
                        await self._dispatch(event.data)
        self.covered = {}
        self.status = SseState(state="error", message="SSE-strømmen blev lukket af PLC'en")
        return self._retry_s

    async def _dispatch(self, data: dict[str, Any]) -> None:
        kind, addr, value = data.get("type"), data.get("addr"), data.get("value")
        if kind not in SSE_ADDR_MAX or not isinstance(addr, int) or not isinstance(value, (int, bool)):
            return
        result = self._on_register(kind, addr, int(value))
        if asyncio.iscoroutine(result):
            await result
