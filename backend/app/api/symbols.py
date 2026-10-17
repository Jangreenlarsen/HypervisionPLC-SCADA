"""REST for symbol-konfigurationer (lag 2). Teknik: docs/SYMBOLSTANDARD_IMPLEMENTERING.md afsnit 6."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from fastapi import Depends

from ..services.auth import CurrentUser
from ..services.errors import ServiceError
from ..services.symbol_convert import convert_all, suggest
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


class CopyBody(_Model):
    targets: list[str] = Field(min_length=1, max_length=500)
    overwrite: bool = False


class PreviewBody(_Model):
    config: dict[str, Any]


def _svc(request: Request) -> SymbolService:
    return request.app.state.symbol_service


def _ops(request: Request) -> SymbolOperateService:
    return request.app.state.symbol_operate_service


def _check(request: Request, drawing_id: str) -> None:
    if not request.app.state.scope_service.can_see_drawing(request.state.user, drawing_id):
        raise ServiceError(404, f"Tegningen '{drawing_id}' findes ikke")


@router.get("/{drawing_id}/symbols", dependencies=[ENGINEER])
async def list_symbols(drawing_id: str, request: Request) -> list[dict[str, Any]]:
    """Symbolerne i tegningen (bibliotekstype eller navn) og om de har en opsætning."""
    return _svc(request).list_symbols(drawing_id)


@router.post("/{drawing_id}/symbols/{element}/copy", dependencies=[ENGINEER])
async def copy_config(drawing_id: str, element: str, body: CopyBody, request: Request) -> dict[str, Any]:
    """Kopiér symbolets gemte opsætning (tag og animationer) til andre symboler — hver kopi valideres for sig."""
    result = _svc(request).copy_to(request.state.user, drawing_id, element, body.targets, body.overwrite)
    audit(request, "symbol.copy", f"{drawing_id}#{element}",
          {"ok": result["ok"], "skipped": result["skipped"], "error": result["error"],
           "targets": [r["element"] for r in result["results"] if r["status"] == "ok"][:100]})
    return result


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
    if body.pin is not None:
        _ops(request).reset_pin_fails(drawing_id, element)
        audit(request, "symbol.pin_set", f"{drawing_id}#{element}", {})
    return result


class PinBody(_Model):
    pin: str = Field(max_length=8)


@router.put("/{drawing_id}/symbols/{element}/pin", dependencies=[ENGINEER])
async def set_pin(drawing_id: str, element: str, body: PinBody, request: Request) -> dict[str, Any]:
    """Sæt/skift koden (skriv-kun). Svaret siger kun at en kode er sat — aldrig koden (CLAUDE.md regel 6)."""
    result = _svc(request).set_pin(request.state.user, drawing_id, element, body.pin)
    _ops(request).reset_pin_fails(drawing_id, element)
    audit(request, "symbol.pin_set", f"{drawing_id}#{element}", {})
    return result


@router.delete("/{drawing_id}/symbols/{element}/pin", dependencies=[ENGINEER])
async def clear_pin(drawing_id: str, element: str, request: Request) -> dict[str, Any]:
    result = _svc(request).clear_pin(request.state.user, drawing_id, element)
    _ops(request).reset_pin_fails(drawing_id, element)
    audit(request, "symbol.pin_cleared", f"{drawing_id}#{element}", {})
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
    others = {k: v for k, v in svc.configs(drawing_id).items() if k != element}
    cfg, res = validate_config(body.config, info, svc._tags(), has_pin=True, element_id=element, others=others)
    plans = ([{"position": k, "label": p["label"], "writes": write_plan(cfg, k)} for k, p in enumerate(cfg["positions"])]
             if cfg["op"] == "positions" and not res.count else [])
    return {"config": cfg, "steps": res.steps, "warnings": res.warnings, "errors": res.count, "plans": plans}


@router.get("/{drawing_id}/symbols/{element}/suggest", dependencies=[ENGINEER])
async def suggest_config(drawing_id: str, element: str, request: Request) -> dict[str, Any]:
    """Forslag til en konfiguration ud fra symbolets bindinger i dag (Konvertér) — gemmes ikke."""
    svc = _svc(request)
    svc.drawings._require(drawing_id)
    return suggest(svc.drawings, drawing_id, element)


class ConvertAllBody(_Model):
    apply: bool = False                       # False = tør-kørsel (standard): intet gemmes
    drawings: list[str] | None = None         # None = alle tegninger


@router.post("/convert-symbols", dependencies=[ENGINEER])
async def convert_symbols(body: ConvertAllBody, request: Request) -> dict[str, Any]:
    """Konvertér alle (symbolstandarden afsnit 11.2): rapport pr. symbol; gemmer kun når `apply` er sat."""
    svc = _svc(request)
    ids = body.drawings if body.drawings is not None else [d["id"] for d in svc.drawings.list()]
    for d in ids:
        svc.drawings._require(d)
    result = convert_all(svc, request.state.user, ids, body.apply)
    if body.apply:
        audit(request, "symbol.convert_all", ",".join(ids)[:200], result["counts"])
    return result
