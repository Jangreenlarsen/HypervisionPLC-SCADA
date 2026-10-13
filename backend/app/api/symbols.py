"""REST for symbol-konfigurationer (lag 2). Teknik: docs/SYMBOLSTANDARD_IMPLEMENTERING.md afsnit 6."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from fastapi import Depends

from ..services.auth import CurrentUser
from ..services.errors import ServiceError
from ..services.symbol_operate import SymbolOperateService
from ..services.symbols import SymbolService, validate_config, write_plan
from ..services.svg_sanitize import describe_element
from .auth import ENGINEER, VIEWER, audit, client_ip, require

OPERATOR = require("operator")

router = APIRouter(prefix="/api/drawings")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigBody(_Model):
    config: dict[str, Any]
    pin: str | None = Field(default=None, max_length=8)   # skriv-kun; gemmes kun som hash


class OperateBody(_Model):
    position: int = Field(ge=0, le=7)
    pin: str | None = Field(default=None, max_length=8)


class EntryBody(_Model):
    value: bool | int | float


class PreviewBody(_Model):
    config: dict[str, Any]


def _svc(request: Request) -> SymbolService:
    return request.app.state.symbol_service


def _ops(request: Request) -> SymbolOperateService:
    return request.app.state.symbol_operate_service


def _check(request: Request, drawing_id: str) -> None:
    if not request.app.state.scope_service.can_see_drawing(request.state.user, drawing_id):
        raise ServiceError(404, f"Tegningen '{drawing_id}' findes ikke")


@router.get("/{drawing_id}/symbols/{element}/config", dependencies=[VIEWER])
async def get_config(drawing_id: str, element: str, request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    return _svc(request).get(drawing_id, element)


@router.put("/{drawing_id}/symbols/{element}/config", dependencies=[ENGINEER])
async def put_config(drawing_id: str, element: str, body: ConfigBody, request: Request) -> dict[str, Any]:
    result = _svc(request).put(request.state.user, drawing_id, element, body.config, body.pin)
    # Audit: konfigurationen (aldrig koden — kun at den er sat)
    audit(request, "symbol.config", f"{drawing_id}#{element}",
          {"op": result["config"]["op"], "pin_set": body.pin is not None})
    return result


@router.delete("/{drawing_id}/symbols/{element}/config", status_code=204, dependencies=[ENGINEER])
async def delete_config(drawing_id: str, element: str, request: Request) -> None:
    _svc(request).delete(drawing_id, element)
    audit(request, "symbol.config_deleted", f"{drawing_id}#{element}", {})


# ------------------------------------------------------------------ betjening (operatør)

@router.get("/{drawing_id}/symbols/{element}/plan/{position}", dependencies=[VIEWER])
async def plan(drawing_id: str, element: str, position: int, request: Request) -> dict[str, Any]:
    """De skrivninger et skift til `position` vil give lige nu (til dialogen) — skriver intet."""
    _check(request, drawing_id)
    return {"position": position, "writes": _ops(request).plan(drawing_id, element, position)}


@router.post("/{drawing_id}/symbols/{element}/operate")
async def operate(drawing_id: str, element: str, body: OperateBody, request: Request,
                  user: CurrentUser = Depends(OPERATOR)) -> dict[str, Any]:
    _check(request, drawing_id)
    return await _ops(request).operate_position(user, client_ip(request), drawing_id, element, body.position, body.pin)


@router.post("/{drawing_id}/symbols/{element}/pulse")
async def pulse(drawing_id: str, element: str, request: Request, user: CurrentUser = Depends(OPERATOR)) -> dict[str, Any]:
    _check(request, drawing_id)
    return await _ops(request).pulse(user, client_ip(request), drawing_id, element)


@router.post("/{drawing_id}/symbols/{element}/entry")
async def entry(drawing_id: str, element: str, body: EntryBody, request: Request,
                user: CurrentUser = Depends(OPERATOR)) -> dict[str, Any]:
    _check(request, drawing_id)
    return await _ops(request).entry(user, client_ip(request), drawing_id, element, body.value)


@router.post("/{drawing_id}/symbols/{element}/accept")
async def accept(drawing_id: str, element: str, request: Request, user: CurrentUser = Depends(OPERATOR)) -> dict[str, Any]:
    _check(request, drawing_id)
    return _ops(request).accept(user, client_ip(request), drawing_id, element)


# ------------------------------------------------------------------ guiden (tekniker)

@router.post("/{drawing_id}/symbols/{element}/preview", dependencies=[ENGINEER])
async def preview(drawing_id: str, element: str, body: PreviewBody, request: Request) -> dict[str, Any]:
    """Valider en konfiguration uden at gemme den, og vis skriveplanen pr. position (guidens trin 6)."""
    svc = _svc(request)
    svc.drawings._require(drawing_id)
    info = describe_element(svc.drawings.svg(drawing_id), element)
    if info is None:
        raise ServiceError(404, f"Elementet '{element}' findes ikke i den aktive version af tegningen")
    # Koden tastes i guiden og sendes først ved gem — så kræv den ikke her (PUT afviser stadig lås uden kode)
    cfg, res = validate_config(body.config, info, svc._tags(), has_pin=True)
    plans = ([{"position": k, "label": p["label"], "writes": write_plan(cfg, k)} for k, p in enumerate(cfg["positions"])]
             if cfg["op"] == "positions" and not res.count else [])
    return {"config": cfg, "steps": res.steps, "warnings": res.warnings, "errors": res.count, "plans": plans}
