"""Signalveje i Tegn (lag 2, v4.2.0) — se services/signal_paths.py. Kun tekniker og op (ændrer symbolopsætninger)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..services.bindings import _color
from ..services.errors import ServiceError
from ..services.signal_paths import MAX_CONDITIONS, MAX_ELEMENTS, SignalPathService
from .auth import ENGINEER, audit

router = APIRouter(prefix="/api/drawings")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Flow(_M):
    part: str = Field(min_length=1, max_length=120)      # "all" = hele elementet, ellers delens id
    reverse: bool = False


class PathElement(_M):
    element: str = Field(min_length=1, max_length=120)
    flows: list[Flow] = Field(default_factory=list, max_length=8)


class Condition(_M):
    element: str = Field(min_length=1, max_length=120)   # symbolet på vejen betingelsen hører til
    src: str = Field(min_length=1, max_length=64)        # tag
    neg: bool = False
    cmp: Literal["", "ge", "le", "eq"] = ""
    value: float | None = None


class Style(_M):
    light: str = "#8fc8ea"
    speed: float = Field(default=40, ge=5, le=500)
    dash: float = Field(default=12, ge=2, le=200)

    _c = field_validator("light")(lambda cls, v: _color(v))


class Body(_M):
    name: str = Field(min_length=1, max_length=60)
    start: str = Field(min_length=1, max_length=120)
    end: str = Field(min_length=1, max_length=120)
    elements: list[PathElement] = Field(min_length=1, max_length=MAX_ELEMENTS)
    conditions: list[Condition] = Field(default_factory=list, max_length=MAX_CONDITIONS)
    style: Style = Field(default_factory=Style)
    replace: bool = False                                 # erstat løbelys, der allerede ligger på rørene


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
    return _svc(request).info(drawing_id, body.elements,
                              request.app.state.scope_service.visible_tags(request.state.user))


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
    audit(request, "signal_path.save", f"{drawing_id}/{body.name}",
          {"id": result["id"], "elements": len(body.elements), "conditions": len(body.conditions),
           "changed": result["changed"][:50], "replaced": len(result["conflicts_replaced"])})
    return result


@router.delete("/{drawing_id}/signal-paths/{path_id}", dependencies=[ENGINEER])
async def delete(drawing_id: str, path_id: int, request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    result = _svc(request).delete(request.state.user, drawing_id, path_id)
    audit(request, "signal_path.delete", f"{drawing_id}/{path_id}", {"changed": result["changed"][:50]})
    return result
