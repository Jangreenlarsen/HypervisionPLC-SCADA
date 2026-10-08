"""REST for tegninger og bindinger (lag 2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from ..services.drawings import DrawingService
from ..services.errors import ServiceError
from ..services.scope import ScopeService
from .auth import ENGINEER, VIEWER, audit

router = APIRouter(prefix="/api/drawings")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DrawingCreate(_Model):
    name: str
    svg: str
    comment: str = Field(default="", max_length=200)


class VersionCreate(_Model):
    svg: str
    comment: str = Field(default="", max_length=200)
    activate: bool = True


class DrawingUpdate(_Model):
    name: str | None = None
    active_version: int | None = None


class ElementBindings(_Model):
    bindings: list[dict[str, Any]] = Field(max_length=10)


def _svc(request: Request) -> DrawingService:
    return request.app.state.drawing_service


def _scope(request: Request) -> ScopeService:
    return request.app.state.scope_service


def _check(request: Request, drawing_id: str) -> None:
    """Tegninger uden for brugerens adgang 'findes ikke' (afslør ikke at de eksisterer)."""
    if not _scope(request).can_see_drawing(request.state.user, drawing_id):
        raise ServiceError(404, f"Tegningen '{drawing_id}' findes ikke")


@router.get("", dependencies=[VIEWER])
async def list_drawings(request: Request) -> list[dict[str, Any]]:
    allowed = _scope(request).drawing_ids(request.state.user)
    return [d for d in _svc(request).list() if allowed is None or d["id"] in allowed]


@router.post("", status_code=201, dependencies=[ENGINEER])
async def create_drawing(body: DrawingCreate, request: Request) -> dict[str, Any]:
    result = _svc(request).create(body.name, body.svg, body.comment)
    audit(request, "drawing.create", result["drawing"]["id"], {"name": body.name, "report": result["report"]})
    return result


@router.get("/{drawing_id}", dependencies=[VIEWER])
async def get_drawing(drawing_id: str, request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    return _svc(request).get(drawing_id)


@router.patch("/{drawing_id}", dependencies=[ENGINEER])
async def update_drawing(drawing_id: str, body: DrawingUpdate, request: Request) -> dict[str, Any]:
    svc = _svc(request)
    if body.name is not None:
        svc.rename(drawing_id, body.name)
    if body.active_version is not None:
        svc.activate(drawing_id, body.active_version)
    audit(request, "drawing.update", drawing_id, body.model_dump(exclude_unset=True))
    return svc.get(drawing_id)


@router.delete("/{drawing_id}", status_code=204, dependencies=[ENGINEER])
async def delete_drawing(drawing_id: str, request: Request) -> None:
    _svc(request).delete(drawing_id)
    audit(request, "drawing.delete", drawing_id)


@router.post("/{drawing_id}/versions", status_code=201, dependencies=[ENGINEER])
async def add_version(drawing_id: str, body: VersionCreate, request: Request) -> dict[str, Any]:
    result = _svc(request).add_version(drawing_id, body.svg, body.comment, body.activate)
    audit(request, "drawing.version", drawing_id, {"version": result["version"], "report": result["report"]})
    return result


@router.get("/{drawing_id}/svg", dependencies=[VIEWER])
async def get_svg(drawing_id: str, request: Request, version: int | None = None) -> Response:
    _check(request, drawing_id)
    svg = _svc(request).svg(drawing_id, version)
    # Saneret SVG serveres med CSP, så den heller ikke kan køre script hvis den åbnes direkte.
    return Response(svg, media_type="image/svg+xml",
                    headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:",
                             "X-Content-Type-Options": "nosniff"})


@router.get("/{drawing_id}/view", dependencies=[VIEWER])
async def view(drawing_id: str, request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    return _svc(request).view(drawing_id, _scope(request).drawing_ids(request.state.user))


@router.get("/{drawing_id}/bindings", dependencies=[VIEWER])
async def list_bindings(drawing_id: str, request: Request) -> list[dict[str, Any]]:
    _check(request, drawing_id)
    return _svc(request).bindings(drawing_id)


@router.put("/{drawing_id}/bindings/{element}", dependencies=[ENGINEER])
async def set_bindings(drawing_id: str, element: str, body: ElementBindings, request: Request) -> list[dict[str, Any]]:
    result = _svc(request).set_element_bindings(drawing_id, element, body.bindings)
    audit(request, "binding.set", f"{drawing_id}#{element}", {"bindings": result})
    return result
