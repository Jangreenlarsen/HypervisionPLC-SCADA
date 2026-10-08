"""Betjening: skriv til PLC'en fra Overview (setpunkt, toggle, puls).

Regler:
- Kun tags markeret skrivbare, og kun hr/coil-kilder (valideret ved oprettelse/opdatering).
- Operatøren arbejder i tekniske enheder; værdien omregnes til rå PLC-værdi ved invers
  skalering: rå = (værdi - offset) / scale. Heltalstyper afrundes og tjekkes mod typens grænser.
- min/max på tagget håndhæves her (backend), ikke kun i dialogen.
- Efter skrivning læses værdien tilbage. Er den anderledes (fx et ST-program med output-
  binding overskriver registret), returneres en advarsel i stedet for at påstå succes.
- Puls nulstilles af serveren, så en lukket browser ikke efterlader en udgang tændt.
- Alle forsøg — også de afviste — registreres i audit-loggen.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

from ..plc.errors import PlcApiError, PlcAuthError, PlcError, PlcForbidden, PlcRateLimited, PlcUnreachable
from .audit import AuditService
from .auth import CurrentUser
from .errors import ServiceError
from .manager import PlcManager
from .tagsource import TagSource, apply_scaling, decode_words, parse_source

INT_RANGES = {"uint": (0, 65535), "int": (-32768, 32767), "dint": (-2**31, 2**31 - 1), "dword": (0, 2**32 - 1)}


def _plc_error(exc: PlcError, what: str) -> ServiceError:
    if isinstance(exc, PlcUnreachable):
        return ServiceError(503, f"{what}: PLC'en svarer ikke — {exc.message}")
    if isinstance(exc, PlcRateLimited):
        return ServiceError(429, f"{what}: PLC'en er overbelastet — prøv igen om lidt")
    if isinstance(exc, (PlcAuthError, PlcForbidden)):
        return ServiceError(502, f"{what}: SCADA-brugeren på PLC'en må ikke skrive — {exc.message} "
                                 "(kræver privilegiet write på PLC'en)")
    if isinstance(exc, PlcApiError):
        return ServiceError(409, f"{what}: PLC'en afviste — {exc.message}")
    return ServiceError(502, f"{what}: {exc.message}")


def to_raw(value: Any, source: TagSource, scale: float, offset: float) -> tuple[int | float | bool, Any]:
    """Teknisk værdi → (rå værdi, faktisk teknisk værdi efter afrunding)."""
    if source.kind == "coil" or source.datatype == "bool":
        if isinstance(value, bool):
            return value, value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value), bool(value)
        raise ServiceError(400, "Værdien skal være til eller fra (true/false)")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ServiceError(400, "Værdien skal være et tal")
    raw = (value - offset) / scale
    if source.datatype == "real":
        return raw, value
    lo, hi = INT_RANGES[source.datatype]
    raw_int = round(raw)
    if not lo <= raw_int <= hi:
        raise ServiceError(400, f"Værdien {value} giver rå værdien {raw_int}, som er uden for {source.datatype} ({lo}…{hi})")
    return raw_int, apply_scaling(raw_int, scale, offset)


class OperateService:
    def __init__(self, manager: PlcManager, audit: AuditService):
        self.manager = manager
        self.db = manager.db
        self.audit = audit
        self._locks: dict[str, asyncio.Lock] = {}

    def _prepare(self, tag_name: str) -> tuple[dict[str, Any], TagSource, Any]:
        tag = self.db.get_tag(tag_name)
        if tag is None:
            raise ServiceError(404, f"Tagget '{tag_name}' findes ikke")
        if not tag["writable"]:
            raise ServiceError(403, f"Tagget '{tag_name}' er ikke skrivbart")
        source = parse_source(tag["source"])
        if source.kind not in ("hr", "coil"):
            raise ServiceError(403, f"Tagget '{tag_name}' kan ikke skrives ({source.kind} er kun-læs)")
        runtime = self.manager.runtimes.get(source.plc)
        if runtime is None:
            raise ServiceError(409, f"PLC '{source.plc}' er ikke aktiv: {self.manager.status(source.plc)['message']}")
        return tag, source, runtime

    async def _write_raw(self, runtime: Any, source: TagSource, raw: Any) -> None:
        if source.kind == "coil":
            await runtime.client.write_coil(source.addr, bool(raw))
        else:
            await runtime.client.write_hr(source.addr, raw, source.datatype)

    async def _readback(self, runtime: Any, source: TagSource, tag: dict[str, Any]) -> Any:
        words = await runtime.client.read_bulk(source.kind, source.addr, source.words)
        value = decode_words([words[a] for a in range(source.addr, source.addr + source.words)], source.datatype)
        return apply_scaling(value, tag["scale"], tag["offset"])

    @staticmethod
    def _same(a: Any, b: Any) -> bool:
        if isinstance(a, bool) or isinstance(b, bool):
            return bool(a) == bool(b)
        return math.isclose(float(a), float(b), rel_tol=1e-4, abs_tol=1e-6)

    def _log(self, actor: CurrentUser, ip: str, action: str, tag: str, detail: dict[str, Any],
             error: ServiceError | None = None, warning: str = "") -> None:
        self.audit.record(actor.username, ip, action, tag, detail,
                          "error" if error else ("warning" if warning else "ok"),
                          error.message if error else warning)

    async def write(self, actor: CurrentUser, ip: str, tag_name: str, value: Any, action: str = "write") -> dict[str, Any]:
        detail: dict[str, Any] = {"requested": value}
        try:
            tag, source, runtime = self._prepare(tag_name)
            detail["source"] = str(source)
            detail["old"] = self.manager.cache.get(tag_name).value
            if source.kind != "coil" and not isinstance(value, bool) and isinstance(value, (int, float)):
                # min/max: 0 er en gyldig grænse — derfor `is not None`, ikke truthiness.
                if tag["min"] is not None and value < tag["min"]:
                    raise ServiceError(400, f"Værdien {value} er under minimum {tag['min']}")
                if tag["max"] is not None and value > tag["max"]:
                    raise ServiceError(400, f"Værdien {value} er over maksimum {tag['max']}")
            raw, actual = to_raw(value, source, tag["scale"], tag["offset"])
            detail.update(raw=raw, written=actual)
            async with self._locks.setdefault(tag_name, asyncio.Lock()):
                try:
                    await self._write_raw(runtime, source, raw)
                    readback = await self._readback(runtime, source, tag)
                except PlcError as exc:
                    raise _plc_error(exc, "Skrivning fejlede") from exc
            runtime.poke()
        except ServiceError as exc:
            self._log(actor, ip, action, tag_name, detail, error=exc)
            raise
        detail["readback"] = readback
        warning = ""
        if not self._same(readback, actual):
            warning = (f"PLC'en viser {readback} efter skrivning af {actual} — værdien er sandsynligvis "
                       "overskrevet af PLC'ens eget program (fx en ST-binding)")
        self._log(actor, ip, action, tag_name, detail, warning=warning)
        return {"tag": tag_name, "written": actual, "readback": readback, "matches": not warning, "warning": warning}

    async def toggle(self, actor: CurrentUser, ip: str, tag_name: str) -> dict[str, Any]:
        current = self.manager.cache.get(tag_name)
        if current.quality != "good" or current.value is None:
            exc = ServiceError(409, f"Kan ikke skifte '{tag_name}': den aktuelle værdi er ukendt ({current.quality})")
            self._log(actor, ip, "toggle", tag_name, {}, error=exc)
            raise exc
        on = bool(current.value)
        result = await self.write(actor, ip, tag_name, (not on) if isinstance(current.value, bool) else (0 if on else 1),
                                  action="toggle")
        return {**result, "from": current.value}

    async def pulse(self, actor: CurrentUser, ip: str, tag_name: str, ms: int) -> dict[str, Any]:
        if not 100 <= ms <= 10_000:
            raise ServiceError(400, "Pulslængde skal være 100-10000 ms")
        detail: dict[str, Any] = {"ms": ms}
        try:
            tag, source, runtime = self._prepare(tag_name)
            if source.datatype == "real":
                raise ServiceError(400, "Puls kræver et til/fra-tag (coil eller heltals-register)")
            on_raw: Any = True if source.kind == "coil" else 1
            off_raw: Any = False if source.kind == "coil" else 0
            async with self._locks.setdefault(tag_name, asyncio.Lock()):
                try:
                    await self._write_raw(runtime, source, on_raw)
                except PlcError as exc:
                    raise _plc_error(exc, "Puls kunne ikke startes") from exc
                try:
                    await asyncio.sleep(ms / 1000)
                finally:
                    # Nulstil ALTID — også hvis requesten afbrydes undervejs.
                    try:
                        await self._write_raw(runtime, source, off_raw)
                    except PlcError as exc:
                        raise _plc_error(exc, "ADVARSEL: pulsen blev sat men IKKE nulstillet") from exc
            runtime.poke()
        except ServiceError as exc:
            self._log(actor, ip, "pulse", tag_name, detail, error=exc)
            raise
        self._log(actor, ip, "pulse", tag_name, detail)
        return {"tag": tag_name, "ms": ms}
