"""REST for navngivne symbolgrupper (lag 2). Se services/symbol_groups.py."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..services.errors import ServiceError
from ..services.symbol_groups import GROUP_KINDS, MAX_GROUP_MEMBERS, MAX_GROUP_NAME, SymbolGroupService
from .auth import ENGINEER, VIEWER, audit

router = APIRouter(prefix="/api/drawings")


class GroupBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=MAX_GROUP_NAME)
    kind: str = Field(default="selection", pattern="^(" + "|".join(GROUP_KINDS) + ")$")
    members: list[str] | None = Field(default=None, max_length=MAX_GROUP_MEMBERS)   # None = uændret (ved ret)


def _svc(request: Request) -> SymbolGroupService:
    return request.app.state.symbol_group_service


def _check(request: Request, drawing_id: str) -> None:
    if not request.app.state.scope_service.can_see_drawing(request.state.user, drawing_id):
        raise ServiceError(404, f"Tegningen '{drawing_id}' findes ikke")
    if request.app.state.drawing_service.db.get_drawing(drawing_id) is None:
        raise ServiceError(404, f"Tegningen '{drawing_id}' findes ikke")


@router.get("/{drawing_id}/groups", dependencies=[VIEWER])
async def list_groups(drawing_id: str, request: Request) -> list[dict[str, Any]]:
    _check(request, drawing_id)
    return _svc(request).list(drawing_id)


@router.post("/{drawing_id}/groups", status_code=201, dependencies=[ENGINEER])
async def create_group(drawing_id: str, body: GroupBody, request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    group = _svc(request).save(request.state.user.username, drawing_id, None, body.name, body.kind, body.members or [])
    audit(request, "symbol_group.create", f"{drawing_id}#{group['name']}", {"kind": group["kind"], "members": len(group["members"])})
    return group


@router.put("/{drawing_id}/groups/{group_id}", dependencies=[ENGINEER])
async def update_group(drawing_id: str, group_id: int, body: GroupBody, request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    group = _svc(request).save(request.state.user.username, drawing_id, group_id, body.name, body.kind, body.members)
    audit(request, "symbol_group.update", f"{drawing_id}#{group['name']}", {"kind": group["kind"], "members": len(group["members"])})
    return group


@router.delete("/{drawing_id}/groups/{group_id}", status_code=204, dependencies=[ENGINEER])
async def delete_group(drawing_id: str, group_id: int, request: Request) -> Response:
    _check(request, drawing_id)
    name = _svc(request).delete(request.state.user.username, drawing_id, group_id)
    audit(request, "symbol_group.delete", f"{drawing_id}#{name}")
    return Response(status_code=204)
