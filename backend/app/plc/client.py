"""HTTP-klient mod én HypervisionPLC.

Det ENESTE sted i SCADA-serveren der taler REST med en PLC (ARCHITECTURE.md, lag 4a).

Designvalg fra docs/HYPERVISIONPLC_ANALYSE.md:
- Én vedvarende keep-alive-forbindelse og serielle kald (HTTPS-serveren har kun 2
  sockets og er heap-følsom ved bursts).
- Ét Bearer-token genbruges; re-login kun ved 401 (PLC'en har 8 session-pladser delt
  med alle brugere — gentagne logins ville smide andre ud).
- Uversioneret `/api/...` (PLC BUG-485: `/api/v1` mangler bl.a. `/api/login`).
- Rate-budget pr. PLC + backoff ved 429.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from .errors import (
    PlcApiError,
    PlcAuthError,
    PlcError,
    PlcForbidden,
    PlcRateLimited,
    PlcUnreachable,
    extract_error_message,
)
from .ratelimit import TokenBucket

log = logging.getLogger(__name__)

# Bulk-grænser fra PLC'ens api_handlers.cpp
BULK_MAX = {"hr": 200, "ir": 200, "coil": 256, "di": 256}
_BULK_PATH = {"hr": "hr", "ir": "ir", "coil": "coils", "di": "di"}
_BULK_KEY = {"hr": "registers", "ir": "registers", "coil": "coils", "di": "inputs"}

BACKOFF_START_S = 1.0
BACKOFF_MAX_S = 30.0


class PlcClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        rate: float = 5.0,
        burst: int = 5,
        timeout: float = 5.0,
        verify_tls: bool = True,
        name: str = "plc",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.name = name
        self._username = username
        self._password = password
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            verify=verify_tls,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            transport=transport,
        )
        self._bucket = TokenBucket(rate, burst)
        self._lock = asyncio.Lock()
        self._token: str | None = None
        self._backoff_s = 0.0
        self._backoff_until = 0.0
        self.request_count = 0

    # ------------------------------------------------------------------ basis

    async def close(self) -> None:
        await self._http.aclose()

    async def logout(self) -> None:
        """Frigiv session-pladsen på PLC'en. Fejl ignoreres bevidst: logout er
        best-effort ved nedlukning, og PLC'en lader alligevel tokenet udløbe efter 30 min."""
        async with self._lock:
            if self._token is None:
                return
            try:
                await self._send("POST", "/api/logout")
            except PlcError as exc:
                log.debug("logout mod %s fejlede: %s", self.name, exc.message)
            self._token = None

    @property
    def has_session(self) -> bool:
        return self._token is not None

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        accept: tuple[int, ...] = (),
    ) -> Any:
        """Udfør et autentificeret kald og returnér den parsede JSON-body. Statuskoder i `accept`
        returnerer også body'en (fx /api/ext-skrivning, hvor 502/504 bærer slavens resultat)."""
        async with self._lock:
            if self._token is None:
                await self._login_locked()
            resp = await self._send(method, path, json=json, params=params)
            if resp.status_code == 401:
                # Token udløbet/revokeret (fx efter en ACL-ændring på PLC'en): ét nyt login.
                log.info("PLC %s afviste token (401) — logger ind igen", self.name)
                self._token = None
                await self._login_locked()
                resp = await self._send(method, path, json=json, params=params)
            if resp.status_code in accept:
                body, _ = _parse(resp)
                if isinstance(body, dict):
                    return body
            return self._handle(resp)

    async def _login_locked(self) -> None:
        resp = await self._send("POST", "/api/login", auth=(self._username, self._password), use_token=False)
        if resp.status_code == 401:
            body, text = _parse(resp)
            raise PlcAuthError(
                "Login afvist af PLC: " + extract_error_message(401, body, text), status=401
            )
        body = self._handle(resp)
        token = body.get("token") if isinstance(body, dict) else None
        if not isinstance(token, str) or not token.strip():
            raise PlcAuthError(
                "PLC'en returnerede intet session-token ved login (kræver firmware med POST /api/login)"
            )
        self._token = token.strip()
        log.info("Logget ind på PLC %s som %s", self.name, self._username)

    async def _send(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        auth: tuple[str, str] | None = None,
        use_token: bool = True,
    ) -> httpx.Response:
        wait = self._backoff_until - time.monotonic()
        if wait > 0:
            raise PlcRateLimited(f"PLC'en har bedt os vente (429) — prøver igen om {wait:.0f} s", status=429)
        await self._bucket.acquire()
        headers = {}
        if use_token and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            self.request_count += 1
            return await self._http.request(method, path, json=json, params=params, auth=auth, headers=headers)
        except httpx.TimeoutException as exc:
            raise PlcUnreachable(f"PLC'en svarede ikke inden for tidsgrænsen ({self.base_url})") from exc
        except httpx.HTTPError as exc:
            raise PlcUnreachable(f"Kan ikke forbinde til PLC ({self.base_url}): {exc}") from exc

    def _handle(self, resp: httpx.Response) -> Any:
        body, text = _parse(resp)
        status = resp.status_code
        if 200 <= status < 300:
            self._backoff_s = 0.0
            if body is None:
                raise PlcApiError(f"Ugyldigt JSON-svar fra PLC (HTTP {status})", status=status)
            return body
        message = extract_error_message(status, body, text)
        if status == 429:
            self._backoff_s = BACKOFF_START_S if self._backoff_s == 0 else min(self._backoff_s * 2, BACKOFF_MAX_S)
            self._backoff_until = time.monotonic() + self._backoff_s
            raise PlcRateLimited(f"PLC'en afviste kaldet (rate-limit): {message}", status=429)
        if status == 401:
            raise PlcAuthError(f"PLC'en afviste login: {message}", status=401)
        if status == 403:
            raise PlcForbidden(f"PLC-brugeren mangler rettighed: {message}", status=403)
        raise PlcApiError(message, status=status)

    # ---------------------------------------------------------- PLC-endpoints

    async def read_bulk(self, kind: str, start: int, count: int) -> dict[int, int]:
        """Bulk-læs et sammenhængende område. Returnerer {adresse: værdi} (bool som 0/1)."""
        if kind not in BULK_MAX:
            raise ValueError(f"ukendt registertype: {kind}")
        if not 1 <= count <= BULK_MAX[kind]:
            raise ValueError(f"count for {kind} skal være 1-{BULK_MAX[kind]}")
        body = await self.request(
            "GET", f"/api/registers/{_BULK_PATH[kind]}", params={"start": start, "count": count}
        )
        items = body.get(_BULK_KEY[kind]) if isinstance(body, dict) else None
        if not isinstance(items, list):
            raise PlcApiError(f"Uventet svar fra PLC på bulk-læsning af {kind}: mangler '{_BULK_KEY[kind]}'")
        result: dict[int, int] = {}
        for item in items:
            if not isinstance(item, dict) or "addr" not in item or "value" not in item:
                continue
            value = item["value"]
            result[int(item["addr"])] = int(bool(value)) if isinstance(value, bool) else int(value)
        return result

    async def read_ext(self, base: str, kind: str, start: int, count: int, *, max_age_ms: int | None = None,
                       wait_ms: int | None = None) -> list[tuple[Any, str]]:
        """Læs `count` (1-16) værdier fra en ekstern slave via /api/ext → [(værdi, status), ...].
        status: ok | pending (ingen værdi endnu) | error. Værdien er None når der ikke er en gyldig værdi."""
        if not 1 <= count <= EXT_MAX:
            raise ValueError(f"count skal være 1-{EXT_MAX}")
        params: dict[str, Any] = {"count": count}
        if max_age_ms is not None:
            params["max_age"] = max(0, int(max_age_ms))
        if wait_ms is not None:
            params["wait"] = max(0, min(2000, int(wait_ms)))
        body = await self.request("GET", f"{base}/{_EXT_TYPE[kind]}/{start}", params=params)
        if not isinstance(body, dict):
            raise PlcApiError("Uventet svar fra PLC på /api/ext")
        if count > 1 and isinstance(body.get("values"), list):
            values = body["values"]
            states = body.get("states") if isinstance(body.get("states"), list) else ["ok"] * len(values)
        else:
            values, states = [body.get("value")], [body.get("status", "ok")]
        if len(values) < count or len(states) < len(values):
            raise PlcApiError(f"Uventet svar fra PLC på /api/ext: {len(values)} værdier, forventede {count}")
        return [(values[i], str(states[i])) for i in range(count)]

    async def write_ext(self, base: str, kind: str, addr: int, value: Any, datatype: str = "uint",
                        wait_ms: int = 1500) -> str:
        """Skriv én værdi (hr) eller coil til en ekstern slave og vent på slavens svar.
        → "ok" (bekræftet), "timeout" (ikke bekræftet i tide — skrivningen KAN være udført, læs tilbage)
        eller "queued" (kan ikke bekræftes). Slavens "error" kastes som PlcApiError."""
        payload: dict[str, Any] = {"value": bool(value)} if kind == "coil" else {"value": value, "type": datatype}
        body = await self.request("POST", f"{base}/{_EXT_TYPE[kind]}/{addr}", params={"wait": wait_ms}, json=payload,
                                  accept=(502, 504))
        result = body.get("result") if isinstance(body, dict) else None
        if result in ("ok", "queued", "timeout"):
            return str(result)
        if result == "error":
            raise PlcApiError("Slaven svarede med en fejl på skrivningen (fx ugyldig adresse eller skrivebeskyttet)", status=502)
        raise PlcApiError(f"Uventet svar fra PLC på skrivning til ekstern slave: {body}", status=502)

    async def logic_program(self, program_id: int) -> dict[str, Any]:
        body = await self.request("GET", f"/api/logic/{program_id}")
        if not isinstance(body, dict):
            raise PlcApiError(f"Uventet svar fra PLC for ST-program {program_id}")
        return body

    async def logic_programs(self) -> list[dict[str, Any]]:
        body = await self.request("GET", "/api/logic")
        programs = body.get("programs") if isinstance(body, dict) else None
        return programs if isinstance(programs, list) else []

    async def logic_globals(self) -> list[dict[str, Any]]:
        body = await self.request("GET", "/api/logic/globals")
        items = body.get("globals") if isinstance(body, dict) else None
        return items if isinstance(items, list) else []

    async def write_hr(self, addr: int, value: int | float, datatype: str = "uint") -> Any:
        return await self.request("POST", f"/api/registers/hr/{addr}", json={"value": value, "type": datatype})

    async def write_coil(self, addr: int, value: bool) -> Any:
        return await self.request("POST", f"/api/registers/coils/{addr}", json={"value": bool(value)})

    async def sse_status(self) -> dict[str, Any]:
        body = await self.request("GET", "/api/events/status")
        if not isinstance(body, dict):
            raise PlcApiError("Uventet svar fra PLC på /api/events/status")
        return body


EXT_MAX = 16  # højst 16 registre pr. /api/ext-kald
_EXT_TYPE = {"hr": "hr", "ir": "ir", "coil": "coils", "di": "di"}


def ext_base(source: Any) -> str:
    """URL-præfiks for en ekstern kilde (uden type og adresse)."""
    if source.bus == "rtu":
        return f"/api/ext/rtu/{source.slave}"
    if source.bus == "mbx":
        return f"/api/ext/mbx/{source.board}/{source.channel}/{source.slave}"
    raise ValueError("ikke en ekstern kilde")


def _parse(resp: httpx.Response) -> tuple[Any, str]:
    text = resp.text
    try:
        return resp.json(), text
    except ValueError:
        return None, text
