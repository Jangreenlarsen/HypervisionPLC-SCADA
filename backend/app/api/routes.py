"""REST-endpoints (lag 2). Ingen forretningslogik — alt delegeres til service-laget."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..config import read_version
from .auth import ADMIN, ENGINEER, VIEWER, audit
from ..services.errors import ServiceError
from ..services.plcs import PlcService
from ..services.tags import TagService

router = APIRouter(prefix="/api")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlcCreate(_Model):
    key: str
    name: str | None = None
    base_url: str
    username: str
    password: str | None = Field(default=None, description="Skriv-kun; returneres aldrig")
    enabled: bool = True
    sse_enabled: bool = True
    verify_tls: bool = True


class PlcUpdate(_Model):
    name: str | None = None
    base_url: str | None = None
    username: str | None = None
    password: str | None = None
    enabled: bool | None = None
    sse_enabled: bool | None = None
    verify_tls: bool | None = None


class TagCreate(_Model):
    trend: bool | None = None
    trend_interval_s: float | None = None
    energy: str | None = None
    energy_factor: float | None = None
    alarm_hh: float | None = None
    alarm_h: float | None = None
    alarm_l: float | None = None
    alarm_ll: float | None = None
    alarm_deadband: float | None = None
    alarm_delay_s: float | None = None
    alarm_on: str | None = None
    name: str
    source: str
    description: str | None = None
    unit: str | None = None
    scale: float | None = None
    offset: float | None = None
    decimals: int | None = None
    writable: bool | None = None
    min: float | None = None
    max: float | None = None
    confirm_write: bool | None = None


class TagUpdate(_Model):
    trend: bool | None = None
    trend_interval_s: float | None = None
    energy: str | None = None
    energy_factor: float | None = None
    alarm_hh: float | None = None
    alarm_h: float | None = None
    alarm_l: float | None = None
    alarm_ll: float | None = None
    alarm_deadband: float | None = None
    alarm_delay_s: float | None = None
    alarm_on: str | None = None
    source: str | None = None
    description: str | None = None
    unit: str | None = None
    scale: float | None = None
    offset: float | None = None
    decimals: int | None = None
    writable: bool | None = None
    min: float | None = None
    max: float | None = None
    confirm_write: bool | None = None


class TagImport(_Model):
    tags: list[dict[str, Any]]


def _plcs(request: Request) -> PlcService:
    return request.app.state.plc_service


def _tags(request: Request) -> TagService:
    return request.app.state.tag_service


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    return {"status": "ok", **read_version(), "source_url": request.app.state.settings.source_url}


@router.get("/plcs", dependencies=[ENGINEER])
async def list_plcs(request: Request) -> list[dict[str, Any]]:
    return _plcs(request).list()


@router.post("/plcs", status_code=201, dependencies=[ADMIN])
async def create_plc(body: PlcCreate, request: Request) -> dict[str, Any]:
    data = body.model_dump()
    result = await _plcs(request).create(data)
    audit(request, "plc.create", body.key, data)
    return result


@router.get("/plcs/{key}", dependencies=[ENGINEER])
async def get_plc(key: str, request: Request) -> dict[str, Any]:
    return _plcs(request).get(key)


@router.patch("/plcs/{key}", dependencies=[ADMIN])
async def update_plc(key: str, body: PlcUpdate, request: Request) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    result = await _plcs(request).update(key, data)
    audit(request, "plc.update", key, data)
    return result


@router.delete("/plcs/{key}", status_code=204, dependencies=[ADMIN])
async def delete_plc(key: str, request: Request) -> None:
    await _plcs(request).delete(key)
    audit(request, "plc.delete", key)


@router.get("/plcs/{key}/discover", dependencies=[ENGINEER])
async def discover_plc(key: str, request: Request) -> dict[str, Any]:
    return await _plcs(request).discover(key)


@router.get("/tags", dependencies=[VIEWER])
async def list_tags(request: Request, plc: str | None = None) -> list[dict[str, Any]]:
    visible = request.app.state.scope_service.visible_tags(request.state.user)
    return [t for t in _tags(request).list(plc=plc) if visible is None or t["name"] in visible]


@router.post("/tags", status_code=201, dependencies=[ENGINEER])
async def create_tag(body: TagCreate, request: Request) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    result = _tags(request).create(data)
    audit(request, "tag.create", body.name, data)
    return result


@router.post("/tags/import", dependencies=[ENGINEER])
async def import_tags(body: TagImport, request: Request) -> dict[str, Any]:
    result = _tags(request).import_many(body.tags)
    if result["created"]:
        audit(request, "tag.import", "", {"created": result["created"]})
    return result


@router.get("/tags/{name}", dependencies=[VIEWER])
async def get_tag(name: str, request: Request) -> dict[str, Any]:
    visible = request.app.state.scope_service.visible_tags(request.state.user)
    if visible is not None and name not in visible:
        raise ServiceError(404, f"Tag '{name}' findes ikke")
    return _tags(request).get(name)


@router.patch("/tags/{name}", dependencies=[ENGINEER])
async def update_tag(name: str, body: TagUpdate, request: Request) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    result = _tags(request).update(name, data)
    audit(request, "tag.update", name, data)
    return result


@router.delete("/tags/{name}", status_code=204, dependencies=[ENGINEER])
async def delete_tag(name: str, request: Request) -> None:
    _tags(request).delete(name)
    audit(request, "tag.delete", name)


@router.get("/live", dependencies=[VIEWER])
async def live_values(request: Request, tags: str | None = Query(default=None, description="Kommasepareret liste")) -> dict[str, Any]:
    names = [t.strip() for t in tags.split(",") if t.strip()] if tags else [t["name"] for t in _tags(request).list()]
    visible = request.app.state.scope_service.visible_tags(request.state.user)
    if visible is not None:
        names = [n for n in names if n in visible]
    return {"values": request.app.state.cache.snapshot(names)}
