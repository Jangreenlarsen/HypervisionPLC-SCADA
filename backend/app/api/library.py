"""REST for egne symboler og bibliotekets opdeling (lag 2). Se services/library.py."""

from __future__ import annotations

from typing import Any, Literal, TypeVar

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..services.auth import role_at_least
from ..services.errors import ServiceError
from ..services.library import MAX_HINT, MAX_IMPORT_BYTES, MAX_IMPORT_FILES, MAX_LABEL, LibraryService, import_fragment
from ..services.svg_sanitize import MAX_SVG_BYTES
from .auth import ENGINEER, VIEWER, audit

router = APIRouter(prefix="/api/library")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


_M = TypeVar("_M", bound=BaseModel)


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


class ImportFile(_Model):
    name: str = Field(default="", max_length=200)
    svg: str = Field(min_length=1, max_length=MAX_SVG_BYTES)
    label: str | None = Field(default=None, max_length=MAX_LABEL + 20)


Conflict = Literal["version", "rename", "skip"]


class ImportBody(_Model):
    files: list[ImportFile] = Field(min_length=1, max_length=MAX_IMPORT_FILES)
    section: str = Field(default="", max_length=60)
    on_conflict: Conflict = "rename"


class PackageBody(_Model):
    package: dict[str, Any]
    on_conflict: Conflict = "rename"


MAX_REQUEST = MAX_IMPORT_BYTES + 2 * 1024 * 1024   # filerne + JSON-indpakning


async def _body(request: Request, model: type[_M]) -> _M:
    """Læs og validér en (stor) JSON-krop med loft over størrelsen — også når Content-Length mangler."""
    length = request.headers.get("content-length")
    too_big = f"Importen er for stor (højst {MAX_IMPORT_BYTES // (1024 * 1024)} MB i alt)"
    if length is not None and length.isdigit() and int(length) > MAX_REQUEST:
        raise ServiceError(413, too_big)
    raw = bytearray()
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > MAX_REQUEST:
            raise ServiceError(413, too_big)
    try:
        return model.model_validate_json(bytes(raw))
    except ValidationError as exc:
        e = exc.errors()[0]
        raise ServiceError(400, f"Ugyldig anmodning: {'.'.join(str(p) for p in e['loc'])}: {e['msg']}") from None


def _audit_results(request: Request, action: str, results: list[dict[str, Any]]) -> None:
    for r in results:
        if r["status"] in ("created", "version", "renamed"):
            audit(request, action, r["type"], {"label": r["label"], "version": r["version"], "file": r.get("file", "")})


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    count = {k: sum(1 for r in results if r["status"] == k) for k in ("created", "version", "renamed", "skipped", "error")}
    return {"results": results, "count": count}


@router.post("/import", dependencies=[ENGINEER])
async def import_svg(request: Request) -> dict[str, Any]:
    """Importér SVG-filer som egne symboler (én fil = ét symbol). Svaret har resultatet pr. fil."""
    body = await _body(request, ImportBody)
    # rensning og parsning af op til 10 MB SVG må ikke blokere event-loopet (live-data, WebSocket)
    results = await run_in_threadpool(_svc(request).import_files, request.state.user, [f.model_dump() for f in body.files],
                                      body.section, body.on_conflict)
    _audit_results(request, "library.import", results)
    return _summary(results)


class FragmentBody(_Model):
    svg: str = Field(min_length=1, max_length=MAX_SVG_BYTES)


@router.post("/fragment", dependencies=[ENGINEER])
async def svg_fragment(request: Request) -> dict[str, Any]:
    """Rens en SVG-fil til indsættelse i en tegning i Tegn (v3.32.0): ét `<g>` flyttet til (0,0), id'er som dele og
    defs som `def_*`. Intet gemmes — tegningen renses igen, når den gemmes."""
    body = await _body(request, FragmentBody)
    fragment, parts, warnings = await run_in_threadpool(import_fragment, body.svg, None)
    return {"svg": fragment, "parts": parts, "warnings": warnings}


@router.get("/package", dependencies=[ENGINEER])
async def export_package(request: Request, types: str = "") -> dict[str, Any]:
    """Bibliotekspakke med egne symboler (alle, eller kommaseparerede typer) — til en anden SCADA-installation."""
    wanted = [t for t in types.split(",") if t] or None
    pkg = _svc(request).export_package(wanted)
    audit(request, "library.package.export", "", {"symbols": len(pkg["symbols"])})
    return pkg


@router.post("/package", dependencies=[ENGINEER])
async def import_package(request: Request) -> dict[str, Any]:
    body = await _body(request, PackageBody)
    results = await run_in_threadpool(_svc(request).import_package, request.state.user, body.package, body.on_conflict)
    _audit_results(request, "library.package.import", results)
    return _summary(results)


@router.put("/layout", dependencies=[ENGINEER])
async def put_layout(body: LayoutBody, request: Request) -> dict[str, Any]:
    """Gem hele opdelingen (egne sektioner, rækkefølge og placeringer). `rev` = den revision, ændringen bygger på."""
    result = _svc(request).set_layout(request.state.user, body.layout, body.rev)
    audit(request, "library.layout", "", {"sections": len(result["sections"]), "items": len(result["items"])})
    return result
