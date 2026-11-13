"""REST for simulatoren (v6.5.0, services/simulator.py): tegningens variabler, beregning med indskudte værdier og scenarier.
Kun teknikere. Skriver aldrig til PLC'en."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Request, Response

from ..services.errors import ServiceError
from ..services.simulator import SimulatorService, clean_positions, clean_values
from .auth import ENGINEER, audit

log = logging.getLogger("scada.simulator")
router = APIRouter(prefix="/api/drawings")
_busy = asyncio.Semaphore(2)          # en Pi skal ikke regne mange simuleringer på én gang


def _svc(request: Request) -> SimulatorService:
    return request.app.state.simulator_service


def _check(request: Request, drawing_id: str) -> None:
    """Tegninger uden for brugerens adgang 'findes ikke'."""
    if not request.app.state.scope_service.can_see_drawing(request.state.user, drawing_id):
        raise ServiceError(404, f"Tegningen '{drawing_id}' findes ikke")


@router.get("/{drawing_id}/simulator", dependencies=[ENGINEER])
async def variables(drawing_id: str, request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    return await asyncio.to_thread(_svc(request).variables, drawing_id)      # en stor tegning må ikke blokere event-løkken


@router.post("/{drawing_id}/simulate", dependencies=[ENGINEER])
async def simulate(drawing_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    values = clean_values(body.get("values") or {})
    positions = clean_positions(body.get("positions") or {})
    if _busy.locked():                    # køer ikke: siden spørger igen om lidt
        raise ServiceError(429, "Simulatoren er optaget — prøver igen om lidt")
    svc = _svc(request)
    async with _busy:
        try:
            return await asyncio.to_thread(svc.simulate, drawing_id, values, positions)
        except ServiceError:
            raise
        except Exception:
            svc.stats["errors"] += 1
            log.exception("Simuleringen fejlede for %s", drawing_id)
            raise ServiceError(400, "Tegningen kunne ikke simuleres") from None


@router.get("/{drawing_id}/sim-scenarios", dependencies=[ENGINEER])
async def list_scenarios(drawing_id: str, request: Request) -> list[dict[str, Any]]:
    _check(request, drawing_id)
    return _svc(request).scenarios(drawing_id)


@router.post("/{drawing_id}/sim-scenarios", status_code=201, dependencies=[ENGINEER])
async def create_scenario(drawing_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    s = _svc(request).save_scenario(request.state.user, drawing_id, None, body)
    audit(request, "sim_scenario.create", drawing_id, {"id": s["id"], "name": s["name"]})
    return s


@router.put("/{drawing_id}/sim-scenarios/{sid}", dependencies=[ENGINEER])
async def update_scenario(drawing_id: str, sid: int, body: dict[str, Any], request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    s = _svc(request).save_scenario(request.state.user, drawing_id, sid, body)
    audit(request, "sim_scenario.update", drawing_id, {"id": sid, "name": s["name"]})
    return s


@router.delete("/{drawing_id}/sim-scenarios/{sid}", status_code=204, dependencies=[ENGINEER])
async def delete_scenario(drawing_id: str, sid: int, request: Request) -> Response:
    _check(request, drawing_id)
    _svc(request).delete_scenario(drawing_id, sid)
    audit(request, "sim_scenario.delete", drawing_id, {"id": sid})
    return Response(status_code=204)
