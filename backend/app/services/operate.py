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
import logging
import math
import struct
import time
from typing import Any

from ..plc.client import ext_base
from ..plc.errors import PlcApiError, PlcAuthError, PlcError, PlcForbidden, PlcRateLimited, PlcUnreachable
from .audit import AuditService
from .auth import CurrentUser
from .errors import ServiceError
from .manager import PlcManager
from .tagsource import ST_TYPE_MAP, TagSource, apply_scaling, decode_words, parse_source

log = logging.getLogger(__name__)

# Hvileværdien efter en puls (SLUK) skrives med genforsøg i så lang tid, før udgangen meldes som ikke nulstillet
REST_RETRY_S = 10.0

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
    if source.kind in ("logic", "global"):
        # ST-variabel: typen kendes af PLC'en, som konverterer og tjekker området (FEAT-503)
        if isinstance(value, bool):
            return value, value
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ServiceError(400, "Værdien skal være et tal eller til/fra")
        raw = (value - offset) / scale
        if float(raw).is_integer():
            return int(raw), apply_scaling(int(raw), scale, offset)
        return raw, value
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
        self._via: dict[str, str] = {}   # kilde → register der blev skrevet i stedet for en input-bundet ST-variabel
        # Tags hvis hvileværdi efter en puls IKKE kunne skrives (udgangen kan stå tændt) → (plc, besked). Giver en alarm,
        # indtil tagget skrives med succes igen.
        self.stuck: dict[str, tuple[str, str]] = {}

    def _prepare(self, tag_name: str, allowed: set[str] | None = None) -> tuple[dict[str, Any], TagSource, Any]:
        if allowed is not None and tag_name not in allowed:
            raise ServiceError(403, f"Du har ikke adgang til at betjene '{tag_name}' — det kræver en klik-handling "
                                    "i en tegning du har adgang til")
        tag = self.db.get_tag(tag_name)
        if tag is None:
            raise ServiceError(404, f"Tagget '{tag_name}' findes ikke")
        if not tag["writable"]:
            raise ServiceError(403, f"Tagget '{tag_name}' er ikke skrivbart")
        source = parse_source(tag["source"])
        if source.kind not in ("hr", "coil", "logic", "global"):
            raise ServiceError(403, f"Tagget '{tag_name}' kan ikke skrives ({source.kind} er kun-læs)")
        runtime = self.manager.runtimes.get(source.plc)
        if runtime is None:
            raise ServiceError(409, f"PLC '{source.plc}' er ikke aktiv: {self.manager.status(source.plc)['message']}")
        return tag, source, runtime

    async def _write_raw(self, runtime: Any, source: TagSource, raw: Any, urgent: bool = False) -> str:
        """→ "ok" når skrivningen er bekræftet; for eksterne slaver evt. "timeout"/"queued" (ikke bekræftet).
        `urgent`: sikkerhedsskrivning (hvileværdi efter puls) — afvises ikke af klientens lokale rate-limit-pause."""
        if source.is_external:
            # Med `wait`: PLC'en svarer når slaven har bekræftet, fejlet eller ikke nået at svare
            return await runtime.client.write_ext(ext_base(source), source.kind, source.addr, raw, source.datatype,
                                                  urgent=urgent)
        if source.kind == "logic":
            try:
                await runtime.client.write_logic_var(source.program, source.var, raw, urgent=urgent)
            except PlcApiError as exc:
                # PLC'en afviser en variabel, der er bundet som INPUT fra et register (den ville blive overskrevet hver cyklus).
                # Så skriver vi i stedet det register, variablen læser fra — det er det, bindingen er til for.
                if exc.status != 409 or "bound as input" not in exc.message.lower():
                    raise
                self._via[str(source)] = await self._write_via_input_binding(runtime, source, raw, urgent)
            return "ok"
        if source.kind == "global":
            await runtime.client.write_global(source.var, raw, urgent=urgent)
            return "ok"
        if source.kind == "coil":
            await runtime.client.write_coil(source.addr, bool(raw), urgent=urgent)
            return "ok"
        await runtime.client.write_hr(source.addr, raw, source.datatype, urgent=urgent)
        return "ok"

    async def _write_rest(self, runtime: Any, source: TagSource, tag_name: str, raw: Any) -> None:
        """Skriv hvileværdien efter en puls (SLUK) — med genforsøg i op til REST_RETRY_S, så en enkelt timeout eller en
        kort rate-limit-pause ikke efterlader en udgang tændt (kodeanalyse 26.10.2026, F4). Lykkes det ikke: tagget
        markeres som "ikke nulstillet" (alarm), og den sidste fejl kastes. En ekstern slave, der ikke når at bekræfte
        ("timeout"/"queued"), prøves også igen — at skrive samme værdi igen er harmløst."""
        deadline = time.monotonic() + REST_RETRY_S
        delay, attempts = 0.25, 0
        last: PlcError | None = None
        while True:
            attempts += 1
            try:
                result = await self._write_raw(runtime, source, raw, urgent=True)
                if result == "ok":
                    if attempts > 1:
                        log.warning("Hvileværdien for %s blev skrevet efter %d forsøg", tag_name, attempts)
                    self.stuck.pop(tag_name, None)
                    return
                last = PlcUnreachable(f"slaven bekræftede ikke skrivningen ({result})")
            except PlcError as exc:
                last = exc
            if time.monotonic() + delay > deadline:
                break
            await asyncio.sleep(delay)
            delay = min(delay * 2, 2.0)
        assert last is not None
        message = f"{tag_name} kunne ikke sættes tilbage til hvileværdien efter en puls ({attempts} forsøg): {last.message}"
        self.stuck[tag_name] = (source.plc, message)
        log.error("%s — udgangen kan stå tændt", message)
        raise last

    def alarm_conditions(self, now: float) -> tuple[list[Any], set[str]]:
        """Alarmkilde: udgange der ikke kunne nulstilles efter en puls (kontrollér udgangen på anlægget)."""
        from .alarms import Condition
        conds = [Condition(f"tag:{name}:pulse_stuck", name, plc, "state", "ON", None,
                           f"{message} — kontrollér udgangen", priority="high")
                 for name, (plc, message) in self.stuck.items()]
        return conds, set()

    async def _write_via_input_binding(self, runtime: Any, source: TagSource, raw: Any, urgent: bool = False) -> str:
        """Skriv det register, som ST-variablen er bundet til som INPUT (HR eller coil). → "HR 18" (til audit og besked).
        32-bit-typer skrives som to registre, lav ord først (som PLC'ens input-binding læser dem)."""
        items = await runtime.client.bindings(urgent=urgent)
        mine = [b for b in items if b.get("direction") == "input" and b.get("program") == source.program
                and b.get("name") == source.var]
        if not mine:
            raise ServiceError(409, f"PLC'en siger, at '{source.var}' er bundet som input, men bindingen kunne ikke findes — "
                                    "kontrollér bindingen på PLC'en")
        b = mine[0]
        rtype, addr, vtype = str(b.get("register_type")), int(b.get("register_addr", -1)), str(b.get("type", "INT")).upper()
        if rtype == "DI":
            raise ServiceError(409, f"'{source.var}' er bundet som input fra et digitalt input (DI {addr}) — det kan kun læses, "
                                    "ikke skrives")
        if rtype == "Coil":
            await runtime.client.write_coil(addr, bool(raw), urgent=urgent)
            return f"coil {addr}"
        if vtype == "BOOL":
            words = [1 if raw else 0]
        elif vtype == "INT":
            words = [int(raw) & 0xFFFF]
        elif vtype in ("DINT", "DWORD", "TIME"):
            v = int(raw) & 0xFFFFFFFF
            words = [v & 0xFFFF, v >> 16]
        elif vtype == "REAL":
            bits = struct.unpack("<I", struct.pack("<f", float(raw)))[0]
            words = [bits & 0xFFFF, bits >> 16]
        else:
            raise ServiceError(409, f"'{source.var}' ({vtype}) kan ikke skrives via sit input-register")
        for i, w in enumerate(words):
            await runtime.client.write_hr(addr + i, w, "uint", urgent=urgent)
        return f"HR {addr}" + (f"–{addr + len(words) - 1}" if len(words) > 1 else "")

    async def _readback(self, runtime: Any, source: TagSource, tag: dict[str, Any]) -> Any:
        if source.kind in ("logic", "global"):
            if source.kind == "logic":
                variables = (await runtime.client.logic_program(source.program)).get("variables") or []
            else:
                variables = await runtime.client.logic_globals()
            var = next((v for v in variables if isinstance(v, dict) and v.get("name") == source.var), None)
            if var is None or var.get("value") is None:
                return None
            value = var["value"]
            if ST_TYPE_MAP.get(str(var.get("type")).upper()) == "bool" and isinstance(value, (int, bool)):
                return bool(value)
            return apply_scaling(value, tag["scale"], tag["offset"])
        if source.is_external:
            items = await runtime.client.read_ext(ext_base(source), source.kind, source.addr, source.words,
                                                  max_age_ms=0, wait_ms=1000)
            if any(state != "ok" or v is None for v, state in items):
                return None  # skrevet og bekræftet af slaven, men kunne ikke læses tilbage
            ext_words = [int(bool(v)) if isinstance(v, bool) else int(v) for v, _ in items]
            return apply_scaling(decode_words(ext_words, source.datatype), tag["scale"], tag["offset"])
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

    @staticmethod
    def _check_limits(tag: dict[str, Any], source: TagSource, value: Any) -> None:
        if source.kind != "coil" and not isinstance(value, bool) and isinstance(value, (int, float)):
            # min/max: 0 er en gyldig grænse — derfor `is not None`, ikke truthiness.
            if tag["min"] is not None and value < tag["min"]:
                raise ServiceError(400, f"Værdien {value:g} er under minimum {tag['min']:g}")
            if tag["max"] is not None and value > tag["max"]:
                raise ServiceError(400, f"Værdien {value:g} er over maksimum {tag['max']:g}")

    async def write(self, actor: CurrentUser, ip: str, tag_name: str, value: Any, action: str = "write",
                    allowed: set[str] | None = None, allowed_values: set[float] | None = None,
                    toggle: bool = False) -> dict[str, Any]:
        """Skriv `value` — eller med `toggle=True` det modsatte af den værdi PLC'en har NU. Ved toggle læses
        værdien frisk fra PLC'en under tag-låsen, så samtidige tryk giver til→fra og aldrig "til" to gange
        (BUGS v0.27.0 #2), og en forældet cache-værdi aldrig bruges."""
        detail: dict[str, Any] = {"requested": "toggle" if toggle else value}
        try:
            tag, source, runtime = self._prepare(tag_name, allowed)
            # Operatør med kun en omskifter: kun dens positioner (ikke vilkårlige værdier via API'et)
            if not toggle and allowed_values is not None and not (
                    isinstance(value, (int, float)) and float(value) in allowed_values):
                shown = ", ".join(f"{v:g}" for v in sorted(allowed_values)) or "ingen"
                raise ServiceError(403, f"Værdien {value} er ikke en af omskifterens positioner ({shown})")
            detail["source"] = str(source)
            detail["old"] = self.manager.cache.get(tag_name).value
            if not toggle:
                self._check_limits(tag, source, value)
                raw, actual = to_raw(value, source, tag["scale"], tag["offset"])
                detail.update(raw=raw, written=actual)
            async with self._locks.setdefault(tag_name, asyncio.Lock()):
                if toggle:
                    try:
                        current = await self._readback(runtime, source, tag)
                    except PlcError as exc:
                        raise _plc_error(exc, f"Kan ikke skifte '{tag_name}': den aktuelle værdi kunne ikke læses") from exc
                    if current is None:
                        raise ServiceError(409, f"Kan ikke skifte '{tag_name}': den aktuelle værdi er ukendt")
                    detail["old"] = current
                    value = (not current) if isinstance(current, bool) else (0 if current else 1)
                    self._check_limits(tag, source, value)
                    raw, actual = to_raw(value, source, tag["scale"], tag["offset"])
                    detail.update(raw=raw, written=actual)
                try:
                    confirmed = await self._write_raw(runtime, source, raw)
                    self.stuck.pop(tag_name, None)   # skrevet med succes: en evt. "ikke nulstillet"-alarm er forældet
                    via = self._via.pop(str(source), None)
                    readback = await self._readback(runtime, source, tag)
                    if via:   # variablen får værdien fra registret ved næste ST-cyklus — giv den et øjeblik
                        detail["via_register"] = via
                        for _ in range(6):
                            if readback is not None and self._same(readback, actual):
                                break
                            await asyncio.sleep(0.25)
                            readback = await self._readback(runtime, source, tag)
                except PlcError as exc:
                    raise _plc_error(exc, "Skrivning fejlede") from exc
            runtime.poke()
        except ServiceError as exc:
            self._log(actor, ip, action, tag_name, detail, error=exc)
            raise
        detail["readback"] = readback
        if confirmed != "ok":
            detail["slave_result"] = confirmed  # ikke bekræftet af slaven — tilbagelæsningen afgør
        warning = ""
        if readback is None and confirmed != "ok":
            exc = ServiceError(502, f"Skrivningen til {source.device} blev ikke bekræftet og værdien kunne ikke læses "
                                    "tilbage — kontrollér værdien")
            self._log(actor, ip, action, tag_name, detail, error=exc)
            raise exc
        if readback is None:
            warning = f"Skrevet og bekræftet af {source.device}, men værdien kunne ikke læses tilbage endnu"
        elif not self._same(readback, actual):
            warning = (f"PLC'en viser {readback} efter skrivning af {actual} — værdien er sandsynligvis "
                       "overskrevet af PLC'ens eget program (fx en ST-binding)")
        self._log(actor, ip, action, tag_name, detail, warning=warning)
        result = {"tag": tag_name, "written": actual, "readback": readback, "matches": not warning, "warning": warning}
        if toggle:
            result["from"] = detail["old"]  # værdien PLC'en havde lige før skiftet (læst under låsen)
        return result

    # ------------------------------------------------- byggesten til symboler (symbol_operate.py)

    async def write_value(self, tag_name: str, value: Any) -> Any:
        """Skriv én værdi uden tilbagelæsning og uden audit (symbolets betjening logger hele skiftet samlet).
        Samme omregning, min/max og tag-lås som `write`. → den skrevne tekniske værdi. Kaster ServiceError."""
        tag, source, runtime = self._prepare(tag_name)
        self._check_limits(tag, source, value)
        raw, actual = to_raw(value, source, tag["scale"], tag["offset"])
        async with self._locks.setdefault(tag_name, asyncio.Lock()):
            try:
                await self._write_raw(runtime, source, raw)
                self.stuck.pop(tag_name, None)
            except PlcError as exc:
                raise _plc_error(exc, f"Skrivning til {tag_name} fejlede") from exc
        runtime.poke()
        return actual

    async def pulse_value(self, tag_name: str, value: Any, rest: Any, ms: int) -> None:
        """Puls på et register: værdi → vent `ms` → hvileværdi. Hvileværdien skrives ALTID — også hvis kaldet
        afbrydes, og også ved timeout på første skrivning (udfaldet er da ukendt, jf. `pulse`)."""
        tag, source, runtime = self._prepare(tag_name)
        self._check_limits(tag, source, value)
        self._check_limits(tag, source, rest)
        raw, _ = to_raw(value, source, tag["scale"], tag["offset"])
        rest_raw, _ = to_raw(rest, source, tag["scale"], tag["offset"])
        async with self._locks.setdefault(tag_name, asyncio.Lock()):
            first_error: PlcError | None = None
            try:
                await self._write_raw(runtime, source, raw)
            except PlcUnreachable as exc:
                first_error = exc
            except PlcError as exc:
                raise _plc_error(exc, f"Puls på {tag_name} kunne ikke startes") from exc
            try:
                if first_error is None:
                    await asyncio.sleep(ms / 1000)
            finally:
                try:
                    await self._write_rest(runtime, source, tag_name, rest_raw)
                except PlcError as exc:
                    raise _plc_error(exc, f"ADVARSEL: {tag_name} blev ikke sat tilbage til hvileværdien") from exc
            if first_error is not None:
                raise _plc_error(first_error, f"Puls på {tag_name} kunne ikke bekræftes (hvileværdien er skrevet)")
        runtime.poke()

    async def toggle(self, actor: CurrentUser, ip: str, tag_name: str, allowed: set[str] | None = None) -> dict[str, Any]:
        if allowed is not None and tag_name not in allowed:
            exc = ServiceError(403, f"Du har ikke adgang til at betjene '{tag_name}'")
            self._log(actor, ip, "toggle", tag_name, {}, error=exc)
            raise exc
        return await self.write(actor, ip, tag_name, None, action="toggle", allowed=allowed, toggle=True)

    async def pulse(self, actor: CurrentUser, ip: str, tag_name: str, ms: int,
                    allowed: set[str] | None = None) -> dict[str, Any]:
        if not 100 <= ms <= 10_000:
            raise ServiceError(400, "Pulslængde skal være 100-10000 ms")
        detail: dict[str, Any] = {"ms": ms}
        try:
            tag, source, runtime = self._prepare(tag_name, allowed)
            if source.datatype == "real":
                raise ServiceError(400, "Puls kræver et til/fra-tag (coil eller heltals-register)")
            on_raw: Any = True if source.kind == "coil" else 1
            off_raw: Any = False if source.kind == "coil" else 0
            async with self._locks.setdefault(tag_name, asyncio.Lock()):
                try:
                    await self._write_raw(runtime, source, on_raw)
                except PlcUnreachable as exc:
                    # Timeout/forbindelsesfejl: PLC'en kan have udført TÆND — kun svaret gik tabt. Send derfor
                    # SLUK alligevel, så en udgang aldrig efterlades tændt (BUGS v0.27.0 #1).
                    detail["on_result"] = "ukendt (timeout)"
                    try:
                        await self._write_rest(runtime, source, tag_name, off_raw)
                    except PlcError as off_exc:
                        raise _plc_error(off_exc, "ADVARSEL: pulsen kunne ikke bekræftes, og udgangen kunne ikke "
                                                  "sættes til fra — kontrollér udgangen") from off_exc
                    raise _plc_error(exc, "Puls kunne ikke bekræftes (udgangen er sat til fra for en sikkerheds "
                                          "skyld)") from exc
                except PlcError as exc:
                    # PLC'en svarede og afviste: TÆND er ikke udført, så der er intet at nulstille
                    raise _plc_error(exc, "Puls kunne ikke startes") from exc
                try:
                    await asyncio.sleep(ms / 1000)
                finally:
                    # Nulstil ALTID — også hvis requesten afbrydes undervejs — og prøv igen ved fejl (F4).
                    try:
                        await self._write_rest(runtime, source, tag_name, off_raw)
                    except PlcError as exc:
                        raise _plc_error(exc, "ADVARSEL: pulsen blev sat men IKKE nulstillet") from exc
            runtime.poke()
        except ServiceError as exc:
            self._log(actor, ip, "pulse", tag_name, detail, error=exc)
            raise
        self._log(actor, ip, "pulse", tag_name, detail)
        return {"tag": tag_name, "ms": ms}
