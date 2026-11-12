"""Signalveje i Tegn (lag 2, v4.2.0; v5.0.0: vejen er sit eget objekt; v6.0.0: kun en definition) — se services/signal_paths/. Kun tekniker og op."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..services.errors import ServiceError
from ..services.signal_paths import MAX_ELEMENTS, MAX_ENDS, MAX_UI_CHARS, SignalPathService
from .auth import ENGINEER, audit

router = APIRouter(prefix="/api/drawings")


class _M(BaseModel):
    # (ældre klienter sendte også `conditions`, `style` og `anims`: de ignoreres — hvornår vejen er aktiv og hvordan den ser ud er
    #  ikke en del af vejen, men af vejens symbol-opsætning, v6.0.0)
    model_config = ConfigDict(extra="ignore")


class Flow(_M):
    part: str = Field(min_length=1, max_length=120)      # "all" = hele elementet, ellers delens id
    reverse: bool = False


class PathElement(_M):
    element: str = Field(min_length=1, max_length=120)
    flows: list[Flow] = Field(default_factory=list, max_length=8)
    branches: list[int] = Field(default_factory=lambda: [0], max_length=MAX_ENDS)   # hvilke grene (slutpunkter) går gennem elementet


class Body(_M):
    name: str = Field(min_length=1, max_length=60)
    start: str = Field(min_length=1, max_length=120)
    end: str = Field(min_length=1, max_length=120)
    ends: list[str] = Field(default_factory=list, max_length=MAX_ENDS)     # flere slutpunkter: end + disse (v4.13.0)
    ui: dict[str, Any] = Field(default_factory=dict)                      # guidens valg (vejvalg) — så vejen kan rettes
    elements: list[PathElement] = Field(min_length=1, max_length=MAX_ELEMENTS)

    @field_validator("ui")
    @classmethod
    def _ui_small(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(v, default=str)) > MAX_UI_CHARS:
            raise ValueError(f"ui må højst fylde {MAX_UI_CHARS} tegn")
        return v


class InfoBody(_M):
    elements: list[str] = Field(min_length=1, max_length=MAX_ELEMENTS)


def _svc(request: Request) -> SignalPathService:
    return request.app.state.signal_path_service


def _check(request: Request, drawing_id: str) -> None:
    """Teknikere, der er begrænset til udvalgte tegninger, kan ikke se eller ændre andres (som api/symbols.py)."""
    if not request.app.state.scope_service.can_see_drawing(request.state.user, drawing_id):
        raise ServiceError(404, f"Tegningen '{drawing_id}' findes ikke")


@router.get("/{drawing_id}/signal-paths", dependencies=[ENGINEER])
async def list_paths(drawing_id: str, request: Request) -> list[dict[str, Any]]:
    _check(request, drawing_id)
    return _svc(request).list(drawing_id)


@router.post("/{drawing_id}/signal-paths/info", dependencies=[ENGINEER])
async def info(drawing_id: str, body: InfoBody, request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    return _svc(request).info(drawing_id, body.elements)


@router.post("/{drawing_id}/signal-paths", status_code=201, dependencies=[ENGINEER])
async def create(drawing_id: str, body: Body, request: Request) -> dict[str, Any]:
    return _save(drawing_id, body, request, None)


@router.put("/{drawing_id}/signal-paths/{path_id}", dependencies=[ENGINEER])
async def update(drawing_id: str, path_id: int, body: Body, request: Request) -> dict[str, Any]:
    return _save(drawing_id, body, request, path_id)


def _save(drawing_id: str, body: Body, request: Request, path_id: int | None) -> dict[str, Any]:
    _check(request, drawing_id)
    try:
        result = _svc(request).save(request.state.user, drawing_id, body.model_dump(), path_id)
    except ServiceError as exc:
        audit(request, "signal_path.save", f"{drawing_id}/{body.name}", {"error": exc.message[:300]})
        raise
    audit(request, "signal_path.save", f"{drawing_id}/{body.name}", {"id": result["id"], "elements": result["elements"]})
    return result


@router.delete("/{drawing_id}/signal-paths/{path_id}", dependencies=[ENGINEER])
async def delete(drawing_id: str, path_id: int, request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    result = _svc(request).delete(request.state.user, drawing_id, path_id)
    audit(request, "signal_path.delete", f"{drawing_id}/{path_id}", {"name": result["name"]})
    return result
