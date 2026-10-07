"""REST for tegninger og bindinger (lag 2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from ..services.drawings import DrawingService

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


@router.get("")
async def list_drawings(request: Request) -> list[dict[str, Any]]:
    return _svc(request).list()


@router.post("", status_code=201)
async def create_drawing(body: DrawingCreate, request: Request) -> dict[str, Any]:
    return _svc(request).create(body.name, body.svg, body.comment)


@router.get("/{drawing_id}")
async def get_drawing(drawing_id: str, request: Request) -> dict[str, Any]:
    return _svc(request).get(drawing_id)


@router.patch("/{drawing_id}")
async def update_drawing(drawing_id: str, body: DrawingUpdate, request: Request) -> dict[str, Any]:
    svc = _svc(request)
    if body.name is not None:
        svc.rename(drawing_id, body.name)
    if body.active_version is not None:
        svc.activate(drawing_id, body.active_version)
    return svc.get(drawing_id)


@router.delete("/{drawing_id}", status_code=204)
async def delete_drawing(drawing_id: str, request: Request) -> None:
    _svc(request).delete(drawing_id)


@router.post("/{drawing_id}/versions", status_code=201)
async def add_version(drawing_id: str, body: VersionCreate, request: Request) -> dict[str, Any]:
    return _svc(request).add_version(drawing_id, body.svg, body.comment, body.activate)


@router.get("/{drawing_id}/svg")
async def get_svg(drawing_id: str, request: Request, version: int | None = None) -> Response:
    svg = _svc(request).svg(drawing_id, version)
    # Saneret SVG serveres med CSP, så den heller ikke kan køre script hvis den åbnes direkte.
    return Response(svg, media_type="image/svg+xml",
                    headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:",
                             "X-Content-Type-Options": "nosniff"})


@router.get("/{drawing_id}/view")
async def view(drawing_id: str, request: Request) -> dict[str, Any]:
    return _svc(request).view(drawing_id)


@router.get("/{drawing_id}/bindings")
async def list_bindings(drawing_id: str, request: Request) -> list[dict[str, Any]]:
    return _svc(request).bindings(drawing_id)


@router.put("/{drawing_id}/bindings/{element}")
async def set_bindings(drawing_id: str, element: str, body: ElementBindings, request: Request) -> list[dict[str, Any]]:
    return _svc(request).set_element_bindings(drawing_id, element, body.bindings)
