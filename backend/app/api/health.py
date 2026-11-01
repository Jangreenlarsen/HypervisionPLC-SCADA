"""Systemhelbred (lag 2): `GET /api/health/details` — kun læsning, tekniker/admin. `/api/health` (minimal, bruges af
OTA-rollback og versionstjekket) ligger i routes.py."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from .auth import ENGINEER

router = APIRouter(prefix="/api/health")


@router.get("/details", dependencies=[ENGINEER])
async def details(request: Request) -> dict[str, Any]:
    # blokerende opslag køres i en tråd inde i details(); resten læses på event-loopet (trådsikkert)
    return await request.app.state.health_service.details(request.app.state)
