"""Alarmer (lag 2): aktiv liste, kvittering og historik — filtreret efter brugerens adgang pr. tegning."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from ..services.alarms import AlarmService
from ..services.bindings import binding_tags
from ..services.auth import CurrentUser
from .auth import audit, require

router = APIRouter(prefix="/api/alarms")


class AckBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keys: list[str] | None = Field(default=None, description="null = alle synlige")


def _svc(request: Request) -> AlarmService:
    return request.app.state.alarm_service


def _visible(request: Request, user: CurrentUser) -> set[str] | None:
    return request.app.state.scope_service.visible_tags(user)


@router.get("")
async def active(request: Request, user: CurrentUser = Depends(require("viewer"))) -> dict[str, Any]:
    vis = _visible(request, user)
    return {"summary": _svc(request).summary(vis), "active": _svc(request).active(vis)}


@router.post("/ack")
async def ack(body: AckBody, request: Request, user: CurrentUser = Depends(require("operator"))) -> dict[str, Any]:
    svc = _svc(request)
    vis = _visible(request, user)
    keys = body.keys if body.keys is not None else [a["key"] for a in svc.active(vis)]
    count = svc.ack(keys, user.username, svc.visible_keys(vis))
    if count:
        audit(request, "alarm.ack", "", {"count": count, "keys": keys[:50]})
    return {"acked": count}


@router.get("/history")
async def history(request: Request, limit: int = 300, user: CurrentUser = Depends(require("viewer"))) -> list[dict[str, Any]]:
    return _svc(request).history(limit, _visible(request, user))


@router.get("/systems")
async def systems(request: Request, user: CurrentUser = Depends(require("viewer"))) -> list[dict[str, Any]]:
    """Systemerne (tegningerne) og de tags, de bruger — så Alarmer kan filtrere pr. system. Kun brugerens egne tegninger og tags."""
    state = request.app.state
    allowed = state.scope_service.drawing_ids(user)
    vis = _visible(request, user)
    out: list[dict[str, Any]] = []
    for d in state.drawing_service.list():
        did = d["id"]
        if d.get("disabled") or (allowed is not None and did not in allowed):
            continue
        names = {t for b in state.drawing_service.effective_bindings(did) for t in binding_tags(b)} | state.symbol_service.tags_for_drawing(did)
        out.append({"id": did, "name": d["name"], "tags": sorted(n for n in names if vis is None or n in vis)})
    return out
