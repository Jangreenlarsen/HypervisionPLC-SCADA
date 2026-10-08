"""Betjening (skriv til PLC) og audit-log (lag 2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from ..services.auth import CurrentUser
from ..services.operate import OperateService
from .auth import ENGINEER, client_ip, require

router = APIRouter(prefix="/api")
OPERATOR = require("operator")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WriteBody(_Model):
    value: bool | int | float


class PulseBody(_Model):
    ms: int = Field(default=500, ge=100, le=10_000)


def _svc(request: Request) -> OperateService:
    return request.app.state.operate_service


def _operable(request: Request, user: CurrentUser) -> set[str] | None:
    return request.app.state.scope_service.operable_tags(user)


@router.post("/tags/{name}/write")
async def write_tag(name: str, body: WriteBody, request: Request, user: CurrentUser = Depends(OPERATOR)) -> dict[str, Any]:
    return await _svc(request).write(user, client_ip(request), name, body.value, allowed=_operable(request, user))


@router.post("/tags/{name}/toggle")
async def toggle_tag(name: str, request: Request, user: CurrentUser = Depends(OPERATOR)) -> dict[str, Any]:
    return await _svc(request).toggle(user, client_ip(request), name, allowed=_operable(request, user))


@router.post("/tags/{name}/pulse")
async def pulse_tag(name: str, body: PulseBody, request: Request, user: CurrentUser = Depends(OPERATOR)) -> dict[str, Any]:
    return await _svc(request).pulse(user, client_ip(request), name, body.ms, allowed=_operable(request, user))


@router.get("/audit", dependencies=[ENGINEER])
async def audit_log(request: Request, limit: int = 200, action: str | None = None) -> list[dict[str, Any]]:
    return request.app.state.audit_service.list(limit, action)
