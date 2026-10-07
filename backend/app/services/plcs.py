"""PLC-forbindelser: CRUD, adgangskoder (skriv-kun) og tag-forslag fra PLC'en."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from ..plc.errors import PlcError
from .errors import ServiceError
from .manager import PlcManager
from .tagsource import PLC_KEY_RE, ST_TYPE_MAP

CONNECTION_FIELDS = {"base_url", "username", "enabled", "sse_enabled", "verify_tls"}


def normalize_base_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ServiceError(400, "PLC-adresse mangler (fx http://192.168.1.100)")
    url = url.strip().rstrip("/")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ServiceError(400, f"Ugyldig PLC-adresse '{url}' — brug http://<ip>[:port] eller https://<ip>[:port]")
    if parts.path or parts.query or parts.fragment:
        raise ServiceError(400, "PLC-adressen må kun være skema, vært og port — uden sti (fx http://192.168.1.100)")
    try:
        parts.port
    except ValueError:
        raise ServiceError(400, f"Ugyldigt portnummer i '{url}'") from None
    return url


def _check_text(value: Any, field: str, *, max_len: int = 64) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceError(400, f"{field} må ikke være tomt")
    if len(value.strip()) > max_len:
        raise ServiceError(400, f"{field} må højst være {max_len} tegn")
    return value.strip()


def _check_password(value: Any) -> str:
    # Mellemrum i en adgangskode er lovlige; en helt tom/blank adgangskode er det ikke.
    if not isinstance(value, str) or not value.strip():
        raise ServiceError(400, "Adgangskoden må ikke være tom")
    return value


class PlcService:
    def __init__(self, manager: PlcManager):
        self.manager = manager
        self.db = manager.db
        self.secrets = manager.secrets

    def _public(self, plc: dict[str, Any]) -> dict[str, Any]:
        out = {k: plc[k] for k in ("key", "name", "base_url", "username", "enabled", "sse_enabled", "verify_tls")}
        out["has_password"] = self.secrets.has_plc_password(plc["key"])
        out["tag_count"] = self.db.count_tags(plc["key"])
        out["status"] = self.manager.status(plc["key"])
        return out

    def list(self) -> list[dict[str, Any]]:
        return [self._public(p) for p in self.db.list_plcs()]

    def get(self, key: str) -> dict[str, Any]:
        plc = self.db.get_plc(key)
        if plc is None:
            raise ServiceError(404, f"PLC '{key}' findes ikke")
        return self._public(plc)

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        key = data.get("key")
        if not isinstance(key, str) or not PLC_KEY_RE.match(key):
            raise ServiceError(400, "PLC-nøgle skal være små bogstaver, tal og _ og starte med et bogstav (fx plc1)")
        if self.db.get_plc(key) is not None:
            raise ServiceError(409, f"PLC '{key}' findes allerede")
        values = {
            "name": _check_text(data.get("name") or key, "Navn"),
            "base_url": normalize_base_url(data.get("base_url", "")),
            "username": _check_text(data.get("username"), "Brugernavn", max_len=31),
            "enabled": bool(data.get("enabled", True)),
            "sse_enabled": bool(data.get("sse_enabled", True)),
            "verify_tls": bool(data.get("verify_tls", True)),
        }
        password = data.get("password")
        if password is not None:
            password = _check_password(password)
        self.db.insert_plc(key, values)
        if password is not None:
            self.secrets.set_plc_password(key, password)
        await self.manager.reload_plc(key)
        return self.get(key)

    async def update(self, key: str, data: dict[str, Any]) -> dict[str, Any]:
        if self.db.get_plc(key) is None:
            raise ServiceError(404, f"PLC '{key}' findes ikke")
        changes: dict[str, Any] = {}
        if data.get("name") is not None:
            changes["name"] = _check_text(data["name"], "Navn")
        if data.get("base_url") is not None:
            changes["base_url"] = normalize_base_url(data["base_url"])
        if data.get("username") is not None:
            changes["username"] = _check_text(data["username"], "Brugernavn", max_len=31)
        for flag in ("enabled", "sse_enabled", "verify_tls"):
            if data.get(flag) is not None:
                changes[flag] = bool(data[flag])
        password = data.get("password")
        if password is not None:
            password = _check_password(password)
        self.db.update_plc(key, changes)
        if password is not None:
            self.secrets.set_plc_password(key, password)
        if password is not None or CONNECTION_FIELDS & changes.keys():
            await self.manager.reload_plc(key)
        return self.get(key)

    async def delete(self, key: str) -> None:
        if self.db.get_plc(key) is None:
            raise ServiceError(404, f"PLC '{key}' findes ikke")
        count = self.db.count_tags(key)
        if count:
            raise ServiceError(409, f"PLC '{key}' bruges af {count} tag(s) — slet eller flyt dem først")
        self.db.delete_plc(key)
        self.secrets.delete_plc_password(key)
        await self.manager.reload_plc(key)

    async def discover(self, key: str) -> dict[str, Any]:
        """Foreslå tags ud fra PLC'ens ST-variabler og GLOBAL_VAR."""
        self.get(key)
        runtime = self.manager.runtimes.get(key)
        if runtime is None:
            raise ServiceError(409, f"PLC '{key}' er ikke aktiv: {self.manager.status(key)['message']}")
        existing = {row["source"] for row in self.db.list_tags(plc=key)}
        suggestions: list[dict[str, Any]] = []
        try:
            for program in await runtime.client.logic_programs():
                pid = program.get("id")
                if not isinstance(pid, int) or not program.get("compiled"):
                    continue
                body = await runtime.client.logic_program(pid)
                for var in body.get("variables") or []:
                    _suggest(suggestions, existing, key, f"L{pid}", f"{key}:logic:{pid}:{var.get('name')}",
                             var, f"{program.get('name') or 'Logic' + str(pid)}")
            for var in await runtime.client.logic_globals():
                _suggest(suggestions, existing, key, "G", f"{key}:global:{var.get('name')}", var, "GLOBAL_VAR")
        except PlcError as exc:
            raise ServiceError(502, f"Kunne ikke hente variabler fra PLC '{key}': {exc.message}") from exc
        return {"plc": key, "suggestions": suggestions}


def _suggest(out: list[dict[str, Any]], existing: set[str], key: str, prefix: str,
             source: str, var: dict[str, Any], origin: str) -> None:
    name = var.get("name")
    if not isinstance(name, str) or not name:
        return
    datatype = ST_TYPE_MAP.get(str(var.get("type")).upper(), "auto")
    if datatype == "string":
        return  # strenge kan ikke animeres meningsfuldt endnu
    tag_name = re.sub(r"[^A-Za-z0-9_]", "_", f"{key}_{prefix}_{name}")[:64]
    out.append({
        "name": tag_name, "source": source, "datatype": datatype,
        "description": f"{origin}: {name}", "exists": source in existing,
    })
