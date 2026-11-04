"""Integrationer (lag 2).

1. `/api/v1/integration/*` — stabilt, versioneret læse-API for maskiner. Godkendes KUN med en API-nøgle (`Authorization: Bearer hv_…`);
   en session (cookie) giver ikke adgang, og en nøgle kan ikke bruges andre steder. OpenAPI-beskrivelsen (kun denne del) står på
   `/api/v1/integration/openapi.json`.
2. `/api/system/integration/keys` — administration af nøgler (kun admin). Nøglen genereres i browseren; serveren returnerer aldrig værdien.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, ConfigDict, Field

from ..services.errors import ServiceError
from ..services.integration import IntegrationService, Principal
from .auth import ADMIN, audit, client_ip

router = APIRouter(prefix="/api/v1/integration", tags=["integration"])
admin_router = APIRouter(prefix="/api/system/integration")


def _svc(request: Request) -> IntegrationService:
    return request.app.state.integration_service


def principal(request: Request) -> Principal:
    """Godkend nøglen (Authorization: Bearer). Cookies og forespørgselsparametre ignoreres bevidst."""
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    key = value.strip() if scheme.lower() == "bearer" else None
    p = _svc(request).authenticate(key, client_ip(request))
    request.state.key = p
    return p


# ------------------------------------------------------------------ svar-modeller (til OpenAPI-beskrivelsen)

class Point(BaseModel):
    name: str = Field(description="Punktets navn (tag-navnet)")
    description: str | None = None
    unit: str | None = None
    type: Literal["number", "bool"]
    decimals: int | None = None
    min: float | None = None
    max: float | None = None
    history: bool = Field(description="Der gemmes historik (kan hentes med /history)")
    writable: bool = Field(description="Nøglen må skrive til punktet (altid false i denne version)")


class ValueEntry(BaseModel):
    v: Any = Field(description="Værdien (tal eller sand/falsk); null hvis den ikke kendes")
    q: str = Field(description="Kvalitet: good | comm_error | bad | unknown")
    ts: float = Field(description="Tidspunkt for værdien (Unix-sekunder, SCADA-serverens tid)")
    error: str | None = None


class ValuesResponse(BaseModel):
    time: str
    values: dict[str, ValueEntry]


class HistoryResponse(BaseModel):
    tag: str
    start: str
    end: str
    step_s: float
    unit: str | None = None
    columns: list[str] = Field(description='["time","mean","min","max"]')
    rows: list[list[Any]]


class AlarmEntry(BaseModel):
    key: str
    tag: str
    plc: str
    kind: str
    level: str
    priority: Literal["high", "medium", "low"]
    state: Literal["active_unack", "active_ack", "rtn_unack"]
    message: str
    raised_at: str
    acknowledged: bool


class InfoResponse(BaseModel):
    instance: str
    version: str
    time: str
    key: dict[str, Any]
    limits: dict[str, Any]


# ------------------------------------------------------------------ læse-API

@router.get("/info", response_model=InfoResponse, summary="Om anlægget og nøglen (til at afprøve forbindelsen)")
async def info(request: Request, p: Principal = Depends(principal)) -> dict[str, Any]:
    return _svc(request).info(p)


@router.get("/points", response_model=list[Point], summary="De punkter nøglen må se")
async def points(request: Request, p: Principal = Depends(principal)) -> list[dict[str, Any]]:
    return _svc(request).points(p)


@router.get("/values", response_model=ValuesResponse, response_model_exclude_unset=True, summary="Aktuelle værdier (fra SCADA's live-cache, aldrig direkte fra PLC'en)")
async def values(request: Request, tags: str | None = Query(default=None, description="Kommasepareret liste; udeladt = alle tilladte"),
                 p: Principal = Depends(principal)) -> dict[str, Any]:
    names = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    return _svc(request).values(p, names)


@router.get("/history", response_model=HistoryResponse, summary="Historik for ét punkt (nedsamplet)")
async def history(request: Request, tag: str, start: float | None = Query(default=None, description="Unix-sekunder; standard: 1 time før slut"),
                  end: float | None = Query(default=None, description="Unix-sekunder; standard: nu"),
                  points: int = Query(default=600, description="Ønsket antal punkter (10-2000)"), p: Principal = Depends(principal)) -> dict[str, Any]:
    svc = _svc(request)
    try:
        return await svc.history(p, tag, start, end, points)
    except ServiceError:
        svc.count_error(p)
        raise


@router.get("/alarms", response_model=list[AlarmEntry], summary="Aktive og ukvitterede alarmer inden for nøglens afgrænsning")
async def alarms(request: Request, p: Principal = Depends(principal)) -> list[dict[str, Any]]:
    return _svc(request).alarms_for(p)


_openapi_cache: dict[str, Any] = {}


@router.get("/openapi.json", include_in_schema=False)
async def openapi(request: Request) -> dict[str, Any]:
    """OpenAPI for kun denne del af serveren (importér i Postman/Node-RED osv.). Kræver ingen nøgle: den beskriver kun grænsefladen."""
    if not _openapi_cache:
        schema = get_openapi(title="HypervisionPLC SCADA — integration", version="1", routes=router.routes,
                             description="Læse-API til Node-RED, Home Assistant og andre systemer. Godkend med `Authorization: Bearer hv_…`.")
        schema.setdefault("components", {})["securitySchemes"] = {"bearerAuth": {"type": "http", "scheme": "bearer"}}
        schema["security"] = [{"bearerAuth": []}]
        _openapi_cache.update(schema)
    return _openapi_cache


# ------------------------------------------------------------------ administration af nøgler (admin)

class ScopeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    all: bool = False
    tags: list[str] = []
    prefixes: list[str] = []


class KeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    key: str
    scope: ScopeBody
    ip_allow: list[str] = []
    expires_at: float | None = None


class KeyPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    scope: ScopeBody | None = None
    ip_allow: list[str] | None = None
    expires_at: float | None = None
    disabled: bool | None = None


def _scope_text(scope: dict[str, Any]) -> str:
    return "alle tags" if scope.get("all") else f"{len(scope.get('tags', []))} tags, {len(scope.get('prefixes', []))} præfikser"


@admin_router.get("/keys", dependencies=[ADMIN])
async def list_keys(request: Request) -> list[dict[str, Any]]:
    return _svc(request).list_keys()


@admin_router.post("/keys", status_code=201, dependencies=[ADMIN])
async def create_key(body: KeyCreate, request: Request) -> dict[str, Any]:
    result = _svc(request).create(request.state.user.username, body.model_dump())
    # audit: navn, præfiks (de første tegn) og afgrænsning — aldrig nøglen
    audit(request, "integration.key.create", result["name"], {"prefix": result["prefix"], "scope": _scope_text(result["scope"]),
                                                              "ip_allow": result["ip_allow"], "expires_at": result["expires_at"]})
    return result


@admin_router.patch("/keys/{key_id}", dependencies=[ADMIN])
async def update_key(key_id: str, body: KeyPatch, request: Request) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    result = _svc(request).update(key_id, data)
    audit(request, "integration.key.update", result["name"], {"changed": sorted(data), "disabled": result["disabled"]})
    return result


@admin_router.delete("/keys/{key_id}", status_code=204, dependencies=[ADMIN])
async def delete_key(key_id: str, request: Request) -> None:
    gone = _svc(request).delete(key_id)
    audit(request, "integration.key.delete", gone["name"], {"prefix": gone["prefix"]})
