"""Systemhelbred (lag 2): `GET /api/health/details` — kun læsning, tekniker/admin. `/api/health` (minimal, bruges af
OTA-rollback og versionstjekket) ligger i routes.py."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Request

from .auth import ENGINEER

router = APIRouter(prefix="/api/health")


@router.get("/details", dependencies=[ENGINEER])
async def details(request: Request) -> dict[str, Any]:
    # databasetjek og diskopslag er blokerende → ud af event-loopet, så målingen ikke selv skaber lag
    return await asyncio.to_thread(request.app.state.health_service.details, request.app.state)
