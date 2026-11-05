"""REST for egne symboler og bibliotekets opdeling (lag 2). Se services/library.py."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from ..services.auth import role_at_least
from ..services.errors import ServiceError
from ..services.library import MAX_HINT, MAX_LABEL, LibraryService
from .auth import ENGINEER, VIEWER, audit

router = APIRouter(prefix="/api/library")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Box(_Model):
    x: float
    y: float
    w: float
    h: float


class ExportBody(_Model):
    drawing_id: str = Field(min_length=1, max_length=120)
    element: str = Field(min_length=1, max_length=120)
    version: int | None = Field(default=None, ge=1)
    box: Box
    label: str = Field(min_length=1, max_length=MAX_LABEL + 20)
    hint: str = Field(default="", max_length=MAX_HINT + 50)
    section: str = Field(default="", max_length=24)
    keep_tags: bool = False
    replace: bool = False


class UpdateBody(_Model):
    label: str | None = Field(default=None, max_length=MAX_LABEL + 20)
    hint: str | None = Field(default=None, max_length=MAX_HINT + 50)


class LayoutBody(_Model):
    layout: dict[str, Any]
    rev: int = Field(ge=0)   # påkrævet: ændringen afvises, hvis en anden har gemt imens


def _svc(request: Request) -> LibraryService:
    return request.app.state.library_service


@router.get("", dependencies=[VIEWER])
async def get_library(request: Request) -> dict[str, Any]:
    """Egne symboler (grafik + standardopsætning) og opdelingen af hele biblioteket."""
    return _svc(request).list(with_presets=role_at_least(request.state.user.role, "engineer"))


@router.post("/symbols", status_code=201, dependencies=[ENGINEER])
async def export_symbol(body: ExportBody, request: Request) -> dict[str, Any]:
    """Gem et objekt/en gruppe fra en tegning som et (nyt eller ny version af et) bibliotekssymbol."""
    if not request.app.state.scope_service.can_see_drawing(request.state.user, body.drawing_id):
        raise ServiceError(404, f"Tegningen '{body.drawing_id}' findes ikke")
    result = _svc(request).export_from_drawing(
        request.state.user, body.drawing_id, body.element, body.box.model_dump(), body.label, body.hint, body.section,
        body.keep_tags, body.replace, body.version)
    audit(request, "library.save", result["type"],
          {"label": result["label"], "version": result["version"], "from": f"{body.drawing_id}#{body.element}",
           "preset": result["preset"] is not None, "keep_tags": body.keep_tags})
    return result


@router.patch("/symbols/{sym_type}", dependencies=[ENGINEER])
async def update_symbol(sym_type: str, body: UpdateBody, request: Request) -> dict[str, Any]:
    result = _svc(request).update(request.state.user, sym_type, body.label, body.hint)
    audit(request, "library.update", sym_type, {"label": result["label"]})
    return result


@router.delete("/symbols/{sym_type}", dependencies=[ENGINEER])
async def delete_symbol(sym_type: str, request: Request) -> dict[str, Any]:
    """Slet et eget symbol. Tegninger, der bruger det, beholder deres kopi (svaret siger hvilke)."""
    result = _svc(request).delete(request.state.user, sym_type)
    audit(request, "library.delete", sym_type, {"label": result["label"], "used_in": result["used_in"][:50]})
    return result


@router.put("/layout", dependencies=[ENGINEER])
async def put_layout(body: LayoutBody, request: Request) -> dict[str, Any]:
    """Gem hele opdelingen (egne sektioner, rækkefølge og placeringer). `rev` = den revision, ændringen bygger på."""
    result = _svc(request).set_layout(request.state.user, body.layout, body.rev)
    audit(request, "library.layout", "", {"sections": len(result["sections"]), "items": len(result["items"])})
    return result
