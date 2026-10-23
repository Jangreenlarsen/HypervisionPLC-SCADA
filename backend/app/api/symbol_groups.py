"""REST for navngivne symbolgrupper (lag 2). Se services/symbol_groups.py."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..services.errors import ServiceError
from ..services.symbol_groups import GROUP_KINDS, MAX_GROUP_MEMBERS, MAX_GROUP_NAME, SymbolGroupService
from .auth import ENGINEER, VIEWER, audit

router = APIRouter(prefix="/api/drawings")


class MembersBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    add: list[str] = Field(default_factory=list, max_length=MAX_GROUP_MEMBERS)
    remove: list[str] = Field(default_factory=list, max_length=MAX_GROUP_MEMBERS)


class MoveMemberBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    old: str = Field(min_length=1, max_length=120)
    new: str = Field(min_length=1, max_length=120)


class OrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[int] = Field(max_length=200)


class AnimsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    anims: list[dict[str, Any]] = Field(max_length=12)   # tom liste fjerner gruppens animationer på elementet


class AnimsAllBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    anims: list[dict[str, Any]] = Field(min_length=1, max_length=12)
    mode: str = Field(default="add", pattern="^(add|replace)$")
    skip_invalid: bool = True


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


@router.post("/{drawing_id}/groups/order", dependencies=[ENGINEER])
async def reorder_groups(drawing_id: str, body: OrderBody, request: Request) -> list[dict[str, Any]]:
    """Gruppernes rækkefølge — afgør hvem der vinder, når flere grupper har samme slags animation på samme del."""
    _check(request, drawing_id)
    groups = _svc(request).reorder(request.state.user.username, drawing_id, body.ids)
    audit(request, "symbol_group.order", drawing_id, {"ids": body.ids})
    return groups


@router.post("/{drawing_id}/groups/{group_id}/members", dependencies=[ENGINEER])
async def change_members(drawing_id: str, group_id: int, body: MembersBody, request: Request) -> dict[str, Any]:
    """Tilføj/fjern enkelte medlemmer uden at overskrive en kollegas ændringer."""
    _check(request, drawing_id)
    group = _svc(request).change_members(request.state.user.username, drawing_id, group_id, body.add, body.remove)
    audit(request, "symbol_group.members", f"{drawing_id}#{group['name']}", {"add": len(body.add), "remove": len(body.remove)})
    return group


@router.post("/{drawing_id}/groups/{group_id}/members/move", dependencies=[ENGINEER])
async def move_member(drawing_id: str, group_id: int, body: MoveMemberBody, request: Request) -> dict[str, Any]:
    """Flyt et forsvundet medlem (og dets gruppe-animationer) til det element, der har fået dets plads."""
    _check(request, drawing_id)
    group = _svc(request).move_member(request.state.user.username, drawing_id, group_id, body.old, body.new)
    audit(request, "symbol_group.move", f"{drawing_id}#{group['name']}", {"old": body.old, "new": body.new})
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


@router.post("/{drawing_id}/groups/{group_id}/anims", dependencies=[ENGINEER])
async def put_anims_all(drawing_id: str, group_id: int, body: AnimsAllBody, request: Request) -> dict[str, Any]:
    """Samme animationer (på "Hele symbolet") til alle gruppens medlemmer — tilføjet eller erstattet."""
    _check(request, drawing_id)
    result = _svc(request).put_anims_all(request.state.user.username, drawing_id, group_id, body.anims, body.mode, body.skip_invalid)
    audit(request, "symbol_group.anims_all", f"{drawing_id}#{group_id}",
          {"mode": body.mode, "anims": len(body.anims), "applied": result["applied"], "skipped": result["skipped"]})
    return result


@router.get("/{drawing_id}/groups/{group_id}/anims", dependencies=[VIEWER])
async def get_anims(drawing_id: str, group_id: int, request: Request) -> dict[str, list[dict[str, Any]]]:
    """Gruppens egne animationer pr. medlem: {element: [animation, …]}."""
    _check(request, drawing_id)
    return _svc(request).get_anims(drawing_id, group_id)


@router.put("/{drawing_id}/groups/{group_id}/anims/{element}", dependencies=[ENGINEER])
async def put_anims(drawing_id: str, group_id: int, element: str, body: AnimsBody, request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    result = _svc(request).put_anims(request.state.user.username, drawing_id, group_id, element, body.anims)
    audit(request, "symbol_group.anims", f"{drawing_id}#{element}", {"group": group_id, "anims": len(result["anims"])})
    return {"element": element, **result}


@router.get("/{drawing_id}/symbols/{element}/group-anims", dependencies=[VIEWER])
async def group_anims_on(drawing_id: str, element: str, request: Request) -> list[dict[str, Any]]:
    """Animationer som grupper har lagt på elementet — så symbolguiden kan vise, hvad der ikke er symbolets egne."""
    _check(request, drawing_id)
    return _svc(request).anims_on(drawing_id, element)
