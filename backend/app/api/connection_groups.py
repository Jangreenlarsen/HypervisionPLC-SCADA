"""REST for forbindelsesgrupper (v6.1.0) og flowberegningens status. Se services/connection_groups.py og flow_calc.py."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response

from ..services.connection_groups import ConnectionGroupService
from .auth import ENGINEER, audit

router = APIRouter(prefix="/api/drawings")


def _svc(request: Request) -> ConnectionGroupService:
    return request.app.state.connection_group_service


@router.get("/{drawing_id}/connection-groups", dependencies=[ENGINEER])
async def list_groups(drawing_id: str, request: Request) -> dict[str, Any]:
    out = _svc(request).list(drawing_id)
    rt = getattr(request.app.state, "symbol_runtime", None)
    st = rt.flow.status() if rt is not None else {}
    out["flow"] = {"unbound": drawing_id in (st.get("unbound") or []), "notes": (st.get("notes") or {}).get(drawing_id, []),
                   "stats": (st.get("per_drawing") or {}).get(drawing_id)}
    return out


@router.post("/{drawing_id}/connection-groups", status_code=201, dependencies=[ENGINEER])
async def create_group(drawing_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
    g = _svc(request).create(request.state.user, drawing_id, body)
    audit(request, "connection_group.create", drawing_id, {"id": g["id"], "name": g["name"], "members": len(g["members"])})
    return g


@router.put("/{drawing_id}/connection-groups/default", dependencies=[ENGINEER])
async def set_default(drawing_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
    out = _svc(request).set_default(request.state.user, drawing_id, body)
    audit(request, "connection_group.default", drawing_id, {"anims": [a["type"] for a in out["anims"]]})
    return out


@router.put("/{drawing_id}/connection-groups/{gid}", dependencies=[ENGINEER])
async def update_group(drawing_id: str, gid: int, body: dict[str, Any], request: Request) -> dict[str, Any]:
    g = _svc(request).update(request.state.user, drawing_id, gid, body)
    audit(request, "connection_group.update", drawing_id, {"id": gid, "name": g["name"], "members": len(g["members"])})
    return g


@router.delete("/{drawing_id}/connection-groups/{gid}", status_code=204, dependencies=[ENGINEER])
async def delete_group(drawing_id: str, gid: int, request: Request) -> Response:
    _svc(request).delete(drawing_id, gid)
    audit(request, "connection_group.delete", drawing_id, {"id": gid})
    return Response(status_code=204)
