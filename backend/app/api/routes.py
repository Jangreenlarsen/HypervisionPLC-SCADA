"""REST-endpoints (lag 2). Ingen forretningslogik — alt delegeres til service-laget."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..config import read_version
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
async def health() -> dict[str, Any]:
    return {"status": "ok", **read_version()}


@router.get("/plcs")
async def list_plcs(request: Request) -> list[dict[str, Any]]:
    return _plcs(request).list()


@router.post("/plcs", status_code=201)
async def create_plc(body: PlcCreate, request: Request) -> dict[str, Any]:
    return await _plcs(request).create(body.model_dump())


@router.get("/plcs/{key}")
async def get_plc(key: str, request: Request) -> dict[str, Any]:
    return _plcs(request).get(key)


@router.patch("/plcs/{key}")
async def update_plc(key: str, body: PlcUpdate, request: Request) -> dict[str, Any]:
    return await _plcs(request).update(key, body.model_dump(exclude_unset=True))


@router.delete("/plcs/{key}", status_code=204)
async def delete_plc(key: str, request: Request) -> None:
    await _plcs(request).delete(key)


@router.get("/plcs/{key}/discover")
async def discover_plc(key: str, request: Request) -> dict[str, Any]:
    return await _plcs(request).discover(key)


@router.get("/tags")
async def list_tags(request: Request, plc: str | None = None) -> list[dict[str, Any]]:
    return _tags(request).list(plc=plc)


@router.post("/tags", status_code=201)
async def create_tag(body: TagCreate, request: Request) -> dict[str, Any]:
    return _tags(request).create(body.model_dump(exclude_unset=True))


@router.post("/tags/import")
async def import_tags(body: TagImport, request: Request) -> dict[str, Any]:
    return _tags(request).import_many(body.tags)


@router.get("/tags/{name}")
async def get_tag(name: str, request: Request) -> dict[str, Any]:
    return _tags(request).get(name)


@router.patch("/tags/{name}")
async def update_tag(name: str, body: TagUpdate, request: Request) -> dict[str, Any]:
    return _tags(request).update(name, body.model_dump(exclude_unset=True))


@router.delete("/tags/{name}", status_code=204)
async def delete_tag(name: str, request: Request) -> None:
    _tags(request).delete(name)


@router.get("/live")
async def live_values(request: Request, tags: str | None = Query(default=None, description="Kommasepareret liste")) -> dict[str, Any]:
    names = [t.strip() for t in tags.split(",") if t.strip()] if tags else [t["name"] for t in _tags(request).list()]
    return {"values": request.app.state.cache.snapshot(names)}
