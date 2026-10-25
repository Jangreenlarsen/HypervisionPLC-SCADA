"""Genstart fra web (lag 2) — kun admin. Se services/power.py."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from .auth import ADMIN, audit

router = APIRouter(prefix="/api/system/power")


class PowerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["restart", "reboot"]


@router.get("", dependencies=[ADMIN])
async def power_status(request: Request) -> dict[str, Any]:
    return request.app.state.power_service.status()


@router.post("", dependencies=[ADMIN])
async def power_request(body: PowerBody, request: Request) -> dict[str, Any]:
    result = request.app.state.power_service.request(body.action, request.state.user.username)
    audit(request, "system.power", body.action, {"label": result["label"]})
    return result
