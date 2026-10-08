"""REST for ugeprogrammer (lag 2) — tekniker og admin."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..services.schedules import ScheduleService
from .auth import ENGINEER, audit

router = APIRouter(prefix="/api/schedules", dependencies=[ENGINEER])


def _svc(request: Request) -> ScheduleService:
    return request.app.state.schedule_service


async def _body(request: Request) -> Any:
    try:
        return await request.json()
    except ValueError:
        return None


@router.get("")
async def list_schedules(request: Request) -> list[dict[str, Any]]:
    return _svc(request).list()


@router.post("/preview")
async def preview(request: Request) -> dict[str, Any]:
    return _svc(request).preview(await _body(request))


@router.post("", status_code=201)
async def create(request: Request) -> dict[str, Any]:
    result = _svc(request).create(await _body(request))
    audit(request, "schedule.create", result["name"], {"tag": result["tag"]})
    return result


@router.put("/{sid}")
async def update(sid: int, request: Request) -> dict[str, Any]:
    result = _svc(request).update(sid, await _body(request))
    audit(request, "schedule.update", result["name"], {"tag": result["tag"], "enabled": result["enabled"]})
    return result


@router.delete("/{sid}", status_code=204)
async def delete(sid: int, request: Request) -> None:
    name = _svc(request).get(sid)["name"]
    _svc(request).delete(sid)
    audit(request, "schedule.delete", name)
