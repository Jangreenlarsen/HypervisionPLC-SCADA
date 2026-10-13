"""REST for symbol-konfigurationer (lag 2). Teknik: docs/SYMBOLSTANDARD_IMPLEMENTERING.md afsnit 6."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from ..services.errors import ServiceError
from ..services.symbols import SymbolService
from .auth import ENGINEER, VIEWER, audit

router = APIRouter(prefix="/api/drawings")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigBody(_Model):
    config: dict[str, Any]
    pin: str | None = Field(default=None, max_length=8)   # skriv-kun; gemmes kun som hash


def _svc(request: Request) -> SymbolService:
    return request.app.state.symbol_service


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
