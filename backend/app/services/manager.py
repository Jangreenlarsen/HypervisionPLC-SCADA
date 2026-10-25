"""Holder én PlcRuntime pr. aktiv PLC og fodrer dem med tags fra databasen.

Fase 1: alle tags på aktive PLC'er polles. Fase 2 indsnævrer til de tags, der vises
i åbne tegninger (+ alarm-tags).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

import httpx

from ..config import Settings
from ..plc.client import PlcClient
from ..storage.db import Database
from ..storage.secrets import SecretStore
from .live_cache import LiveCache, LiveValue
from .plc_runtime import PlcRuntime, RuntimeTag
from .tagsource import TagSourceError, parse_source

log = logging.getLogger(__name__)

TransportFactory = Callable[[str], "httpx.AsyncBaseTransport | None"]


class PlcManager:
    def __init__(
        self,
        db: Database,
        secrets: SecretStore,
        cache: LiveCache,
        settings: Settings,
        transport_factory: TransportFactory | None = None,
    ):
        self.db = db
        self.secrets = secrets
        self.cache = cache
        self.settings = settings
        self._transport_factory = transport_factory
        self.runtimes: dict[str, PlcRuntime] = {}
        self._not_started: dict[str, str] = {}

    async def start_all(self) -> None:
        for plc in self.db.list_plcs():
            await self.reload_plc(plc["key"])

    async def stop_all(self) -> None:
        for key in list(self.runtimes):
            await self._stop(key)

    async def reload_plc(self, key: str) -> None:
        """Genstart runtime efter en ændring af forbindelsesindstillinger (eller sletning)."""
        await self._stop(key)
        plc = self.db.get_plc(key)
        if plc is None:
            self._not_started.pop(key, None)
            return
        if not plc["enabled"]:
            self._not_started[key] = "PLC'en er deaktiveret"
            return
        password = self.secrets.get_plc_password(key)
        if password is None:
            self._not_started[key] = "Ingen adgangskode sat for PLC-brugeren"
            return
        if not self.settings.start_runtimes:
            self._not_started[key] = "Runtimes er slået fra i denne instans"
            return
        transport = self._transport_factory(key) if self._transport_factory else None
        client = PlcClient(
            plc["base_url"], plc["username"], password,
            rate=self.settings.plc_rate, burst=max(1, int(self.settings.plc_rate)),
            timeout=self.settings.plc_timeout_s, verify_tls=plc["verify_tls"], name=key, transport=transport,
        )
        runtime = PlcRuntime(
            key, client, self.cache,
            sse_enabled=plc["sse_enabled"], verify_tls=plc["verify_tls"],
            fast_interval=self.settings.poll_fast_s, slow_interval=self.settings.poll_slow_s,
            ext_interval=self.settings.poll_ext_s,
        )
        runtime.set_tags(self._runtime_tags(key, self._suspended()))
        self._not_started.pop(key, None)
        self.runtimes[key] = runtime
        runtime.start()
        log.info("Startede runtime for PLC %s (%s)", key, plc["base_url"])

    # Tags kun deaktiverede tegninger bruger (v1.6.0): sættes af main.py til `drawing_activity.suspended_tags`
    suspended_tags: Any = None

    def reload_tags(self, removed: list[str] | None = None) -> None:
        if removed:
            self.cache.remove(removed)
        suspended = self._suspended()
        for key, runtime in self.runtimes.items():
            runtime.set_tags(self._runtime_tags(key, suspended))
        if suspended:
            now = time.time()
            self.cache.update({n: LiveValue(quality="unknown", ts=now, error="Pollas ikke — kun deaktiverede tegninger bruger tagget")
                               for n in suspended})

    def _suspended(self) -> set[str]:
        if self.suspended_tags is None:
            return set()
        try:
            return set(self.suspended_tags())
        except Exception:
            log.exception("Kunne ikke afgøre hvilke tags der er suspenderet — alle tags pollas")
            return set()

    def _runtime_tags(self, key: str, suspended: set[str] | frozenset[str] = frozenset()) -> list[RuntimeTag]:
        tags = []
        for row in self.db.list_tags(plc=key):
            if row["name"] in suspended:
                continue
            try:
                source = parse_source(row["source"])
            except TagSourceError as exc:
                # Kan kun ske ved manuel redigering af databasen — valideres ellers ved oprettelse.
                log.error("Tag %s har ugyldig kilde i databasen: %s", row["name"], exc)
                continue
            tags.append(RuntimeTag(row["name"], source, row["scale"], row["offset"]))
        return tags

    async def _stop(self, key: str) -> None:
        runtime = self.runtimes.pop(key, None)
        if runtime is not None:
            await runtime.stop()
            log.info("Stoppede runtime for PLC %s", key)

    def status(self, key: str) -> dict[str, Any]:
        runtime = self.runtimes.get(key)
        if runtime is None:
            return {"state": "stopped", "message": self._not_started.get(key, "Ikke startet")}
        st = runtime.status
        sse = runtime.sse.status if runtime.sse is not None else None
        return {
            "state": st.state,
            "message": st.message,
            "last_ok": st.last_ok or None,
            "cycles": st.cycles,
            "errors": st.errors,
            "requests_per_cycle": runtime.requests_per_cycle,
            "request_count": runtime.client.request_count,
            "plan": st.plan,
            "partial": st.partial,
            "slowest": runtime.slowest(),
            "sse": ({"state": sse.state, "message": sse.message, "events": sse.events,
                     "external": bool(sse.extra.get("external")), "ext_events": runtime.sse.ext_events,  # type: ignore[union-attr]
                     "ext_by_src": dict(runtime.sse.ext_by_src),  # type: ignore[union-attr]
                     "covered": sum(len(v) for v in runtime.sse.covered.values())}  # type: ignore[union-attr]
                    if sse else {"state": "off_in_scada"}),
        }
