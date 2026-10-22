"""System › Konfiguration (lag 2) — kun admin. Læsning (placering, størrelser, skrivemåling, netværksstatus) og trend-indstillinger."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from ..services import netconfig, sysconfig
from ..services.auth import CurrentUser
from .auth import ADMIN, audit, require

router = APIRouter(prefix="/api/system/config")


class TrendSettingsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retention_days: float
    flush_s: float
    energy_days: float


def _trend_view(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    trend_stats = request.app.state.trend_db.stats()
    return {
        "retention_days": settings.trend_days, "flush_s": settings.trend_flush_s, "energy_days": settings.energy_days,
        "overridden": bool(sysconfig.load_overrides(settings.data_dir)),
        "limits": {k: {"min": lo, "max": hi} for k, (lo, hi, _l) in sysconfig.TREND_LIMITS.items()},
        "tags": len(trend_stats), "samples": sum(s["samples"] for s in trend_stats.values()),
        "write": request.app.state.trend_recorder.write_stats(),
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
