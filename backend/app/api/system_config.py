"""System › Konfiguration (lag 2) — kun admin. Trin 1: kun læsning (placering, størrelser, skrivemåling, netværksstatus)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Request

from ..services import sysconfig
from .auth import ADMIN

router = APIRouter(prefix="/api/system/config")


@router.get("", dependencies=[ADMIN])
async def get_config(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    recorder = request.app.state.trend_recorder
    trend_stats = request.app.state.trend_db.stats()
    storage, network = await asyncio.gather(asyncio.to_thread(sysconfig.storage_info, settings.data_dir),
                                            asyncio.to_thread(sysconfig.network_status))
    return {
        "storage": storage,
        "trends": {
            "retention_days": settings.trend_days, "flush_s": settings.trend_flush_s, "energy_days": settings.energy_days,
            "tags": len(trend_stats), "samples": sum(s["samples"] for s in trend_stats.values()),
            "write": recorder.write_stats(),
        },
        "network": network,
    }
