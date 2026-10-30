"""REST for tilslutningspunkter pr. bibliotekssymbol (lag 2). Se services/symbol_ports.py."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..services.symbol_ports import MAX_PORTS, SymbolPortService
from .auth import ENGINEER, audit

router = APIRouter(prefix="/api/symbol-ports")


class PortsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ports: list[list[float]] = Field(min_length=1, max_length=MAX_PORTS)


def _svc(request: Request) -> SymbolPortService:
    return request.app.state.symbol_port_service


@router.get("", dependencies=[ENGINEER])
async def list_ports(request: Request) -> dict[str, Any]:
    """{symboltype: [[fx, fy], …]} — kun de rettede; øvrige symboler bruger de automatiske punkter."""
    return _svc(request).list()


@router.put("/{sym_type}", dependencies=[ENGINEER])
async def set_ports(sym_type: str, body: PortsBody, request: Request) -> dict[str, Any]:
    ports = _svc(request).set(sym_type, body.ports)
    audit(request, "symbol_ports.set", sym_type, {"ports": len(ports)})
    return {"type": sym_type, "ports": ports}


@router.delete("/{sym_type}", status_code=204, dependencies=[ENGINEER])
async def reset_ports(sym_type: str, request: Request) -> Response:
    if _svc(request).reset(sym_type):
        audit(request, "symbol_ports.reset", sym_type, {})
    return Response(status_code=204)
