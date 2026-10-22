"""System › Konfiguration (lag 2) — kun admin. Læsning (placering, størrelser, skrivemåling, netværksstatus) og trend-indstillinger."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from ..services import sysconfig
from .auth import ADMIN, audit

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
