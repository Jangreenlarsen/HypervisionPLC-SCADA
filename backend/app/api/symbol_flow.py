"""REST for ind/ud, navne og veje pr. symboltype (v4.13.0). Se services/symbol_flow.py."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict

from ..services.symbol_flow import SymbolFlowService
from .auth import ENGINEER, audit

router = APIRouter(prefix="/api/symbol-flow")


class FlowBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ports: list[dict[str, Any]]
    ways: list[list[str]] = []


def _svc(request: Request) -> SymbolFlowService:
    return request.app.state.symbol_flow_service


@router.get("", dependencies=[ENGINEER])
async def list_flow(request: Request) -> dict[str, Any]:
    """{symboltype: {ports, ways}} — kun de rettede; øvrige symboler bruger standarderne i frontend."""
    return _svc(request).list()


@router.put("/{sym_type}", dependencies=[ENGINEER])
async def set_flow(sym_type: str, body: FlowBody, request: Request) -> dict[str, Any]:
    clean = _svc(request).set(sym_type, body.model_dump())
    audit(request, "symbol_flow.set", sym_type, {"ports": len(clean["ports"]), "ways": len(clean.get("ways", []))})
    return {"type": sym_type, **clean}


@router.delete("/{sym_type}", status_code=204, dependencies=[ENGINEER])
async def reset_flow(sym_type: str, request: Request) -> Response:
    if _svc(request).reset(sym_type):
        audit(request, "symbol_flow.reset", sym_type, {})
    return Response(status_code=204)
