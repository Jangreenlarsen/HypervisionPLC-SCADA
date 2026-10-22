"""System › Konfiguration (lag 2) — kun admin. Læsning (placering, størrelser, skrivemåling, netværksstatus) og trend-indstillinger."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from ..services import netconfig, sysconfig
from ..services.errors import ServiceError
from ..services.auth import CurrentUser
from .auth import ADMIN, audit, require

router = APIRouter(prefix="/api/system/config")


class TrendSettingsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retention_days: float
    flush_s: float
    energy_days: float


class StorageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trend_dir: str


_move_lock = asyncio.Lock()


def _trend_storage(request: Request) -> dict[str, Any]:
    db = request.app.state.trend_db
    return {"path": str(db.path), "configured": sysconfig.load_trend_dir(request.app.state.settings.data_dir),
            "warning": request.app.state.trend_storage_warning, "roots": [r.as_posix() for r in sysconfig.TREND_DIR_ROOTS]}


def _trend_view(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    trend_stats = request.app.state.trend_db.stats()
    return {
        "retention_days": settings.trend_days, "flush_s": settings.trend_flush_s, "energy_days": settings.energy_days,
        "overridden": bool(sysconfig.load_overrides(settings.data_dir)),
        "limits": {k: {"min": lo, "max": hi} for k, (lo, hi, _l) in sysconfig.TREND_LIMITS.items()},
        "tags": len(trend_stats), "samples": sum(s["samples"] for s in trend_stats.values()),
        "write": request.app.state.trend_recorder.write_stats(), "storage": _trend_storage(request),
    }


@router.get("", dependencies=[ADMIN])
async def get_config(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    storage, network = await asyncio.gather(asyncio.to_thread(sysconfig.storage_info, settings.data_dir),
                                            asyncio.to_thread(sysconfig.network_status))
    return {
        "storage": storage,
        "trends": _trend_view(request),
        "network": network,
        "network_config": _net(request).status(),
    }


@router.put("/trends", dependencies=[ADMIN])
async def put_trends(body: TrendSettingsBody, request: Request) -> dict[str, Any]:
    """Opbevaring, skriveinterval og energi-opbevaring. Gemmes og gælder straks (ingen genstart)."""
    values = sysconfig.validate_trend_settings(body.model_dump())
    settings = request.app.state.settings
    recorder = request.app.state.trend_recorder
    old = {"retention_days": settings.trend_days, "flush_s": settings.trend_flush_s, "energy_days": settings.energy_days}
    await asyncio.to_thread(sysconfig.save_trend_settings, settings.data_dir, values)
    settings.trend_days, settings.trend_flush_s, settings.energy_days = (
        values["retention_days"], values["flush_s"], values["energy_days"])
    recorder.retention_days, recorder.flush_s, recorder.energy_days = (
        values["retention_days"], values["flush_s"], values["energy_days"])
    audit(request, "system.config.trends", "", {"old": old, "new": values})
    return _trend_view(request)


# ---------------------------------------------------------------- netværk
class NetworkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interface: str
    mode: str
    ip: str = ""
    prefix: int = 0
    gateway: str = ""
    dns: list[str] = []
    hostname: str = ""


def _net(request: Request) -> netconfig.NetworkService:
    return request.app.state.network_service


@router.get("/network", dependencies=[ADMIN])
async def get_network(request: Request) -> dict[str, Any]:
    return _net(request).status()


@router.put("/network")
async def put_network(body: NetworkBody, request: Request, user: CurrentUser = Depends(require("admin"))) -> dict[str, Any]:
    """Valider og anmod om en netværksændring. Hjælperen anvender den og venter på bekræftelse (ellers gendannes den gamle)."""
    status = await asyncio.to_thread(sysconfig.network_status)
    names = [n["name"] for n in status["interfaces"]] if status["available"] else None
    cfg = netconfig.validate_network(body.model_dump(), names)
    result = _net(request).request_apply(cfg, user.username)
    audit(request, "system.config.network", cfg["interface"], {"new": cfg})
    return result


@router.post("/network/confirm", dependencies=[ADMIN])
async def confirm_network(request: Request) -> dict[str, Any]:
    result = _net(request).confirm()
    audit(request, "system.config.network.confirm", "", {})
    return result


@router.post("/network/revert", dependencies=[ADMIN])
async def revert_network(request: Request) -> dict[str, Any]:
    result = _net(request).revert()
    audit(request, "system.config.network.revert", "", {})
    return result


@router.put("/storage", dependencies=[ADMIN])
async def put_storage(body: StorageBody, request: Request) -> dict[str, Any]:
    """Flyt trend-databasen til en anden disk (eller tilbage til datamappen). Kører online; den gamle fil bevares som `.moved`."""
    settings = request.app.state.settings
    db = request.app.state.trend_db
    if _move_lock.locked():
        raise ServiceError(409, "En flytning er allerede i gang")
    async with _move_lock:
        target = sysconfig.validate_trend_dir(body.trend_dir, settings.data_dir, db.path)
        old = str(db.path)
        try:
            moved = await asyncio.to_thread(db.relocate, target)
        except (OSError, FileExistsError) as exc:
            raise ServiceError(500, f"Flytningen mislykkedes — databasen er uændret: {exc}") from exc
        stored = "" if target.parent.resolve() == settings.data_dir.resolve() else str(target.parent)
        await asyncio.to_thread(sysconfig.save_section, settings.data_dir, "storage", {"trend_dir": stored})
        request.app.state.trend_storage_warning = ""
        audit(request, "system.config.storage", "trends.db", {"from": old, "to": str(target), "kept_as": str(moved)})
        return _trend_view(request)
