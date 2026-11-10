"""Signalveje i Tegn (lag 2, v4.2.0; v5.0.0: vejen er sit eget objekt) — se services/signal_paths/. Kun tekniker og op."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..services.bindings import _color
from ..services.errors import ServiceError
from ..services.signal_paths import MAX_ANIMS, MAX_CONDITIONS, MAX_ELEMENTS, MAX_ENDS, MAX_UI_CHARS, PATH_ANIMS, SignalPathService
from .auth import ENGINEER, audit
from .sse import sse_response

router = APIRouter(prefix="/api/drawings")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Flow(_M):
    part: str = Field(min_length=1, max_length=120)      # "all" = hele elementet, ellers delens id
    reverse: bool = False


class PartAnim(_M):
    """En animation (ud over løbelys) signalvejen lægger på en del (v4.14.0). Parametrene renses i services/signal_paths."""
    part: str = Field(min_length=1, max_length=120)
    type: Literal["fill", "stroke", "blink", "visible", "spin"]
    params: dict[str, Any] = Field(default_factory=dict)
    when: bool = True      # True: aktiv/passiv (er vejen ikke aktiv, røres delen ikke); False: viser sin fra-tilstand (fx skjult)


class PathElement(_M):
    element: str = Field(min_length=1, max_length=120)
    flows: list[Flow] = Field(default_factory=list, max_length=8)
    anims: list[PartAnim] = Field(default_factory=list, max_length=MAX_ANIMS)
    branches: list[int] = Field(default_factory=lambda: [0], max_length=MAX_ENDS)   # hvilke grene (slutpunkter) går gennem elementet


class Condition(_M):
    element: str = Field(min_length=1, max_length=120)   # symbolet på vejen betingelsen hører til
    src: str = Field(min_length=1, max_length=64)        # tag
    neg: bool = False
    cmp: Literal["", "ge", "le", "eq"] = ""
    value: float | None = None
    branches: list[int] | None = Field(default=None, max_length=MAX_ENDS)   # tom = alle grene, der går gennem elementet


class Style(_M):
    light: str = "#8fc8ea"
    speed: float = Field(default=40, ge=5, le=500)
    dash: float = Field(default=12, ge=2, le=200)

    _c = field_validator("light")(lambda cls, v: _color(v))


class Body(_M):
    name: str = Field(min_length=1, max_length=60)
    start: str = Field(min_length=1, max_length=120)
    end: str = Field(min_length=1, max_length=120)
    ends: list[str] = Field(default_factory=list, max_length=MAX_ENDS)     # flere slutpunkter: end + disse (v4.13.0)
    ui: dict[str, Any] = Field(default_factory=dict)                      # guidens valg (vejvalg, forslag) — så vejen kan rettes
    elements: list[PathElement] = Field(min_length=1, max_length=MAX_ELEMENTS)
    conditions: list[Condition] = Field(default_factory=list, max_length=MAX_CONDITIONS)
    style: Style = Field(default_factory=Style)

    @field_validator("ui")
    @classmethod
    def _ui_small(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(v, default=str)) > MAX_UI_CHARS:
            raise ValueError(f"ui må højst fylde {MAX_UI_CHARS} tegn")
        return v


class InfoBody(_M):
    elements: list[str] = Field(min_length=1, max_length=MAX_ELEMENTS)


def _svc(request: Request) -> SignalPathService:
    return request.app.state.signal_path_service


def _check(request: Request, drawing_id: str) -> None:
    """Teknikere, der er begrænset til udvalgte tegninger, kan ikke se eller ændre andres (som api/symbols.py)."""
    if not request.app.state.scope_service.can_see_drawing(request.state.user, drawing_id):
        raise ServiceError(404, f"Tegningen '{drawing_id}' findes ikke")


@router.get("/{drawing_id}/signal-paths", dependencies=[ENGINEER])
async def list_paths(drawing_id: str, request: Request) -> list[dict[str, Any]]:
    _check(request, drawing_id)
    return _svc(request).list(drawing_id)


@router.post("/{drawing_id}/signal-paths/info", dependencies=[ENGINEER])
async def info(drawing_id: str, body: InfoBody, request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    return _svc(request).info(drawing_id, body.elements,
                              request.app.state.scope_service.visible_tags(request.state.user))


@router.post("/{drawing_id}/signal-paths", status_code=201, dependencies=[ENGINEER])
async def create(drawing_id: str, body: Body, request: Request) -> dict[str, Any]:
    return _save(drawing_id, body, request, None)


@router.put("/{drawing_id}/signal-paths/{path_id}", dependencies=[ENGINEER])
async def update(drawing_id: str, path_id: int, body: Body, request: Request) -> dict[str, Any]:
    return _save(drawing_id, body, request, path_id)


def _save(drawing_id: str, body: Body, request: Request, path_id: int | None) -> dict[str, Any]:
    _check(request, drawing_id)
    try:
        result = _svc(request).save(request.state.user, drawing_id, body.model_dump(), path_id,
                                    request.app.state.scope_service.visible_tags(request.state.user))
    except ServiceError as exc:
        audit(request, "signal_path.save", f"{drawing_id}/{body.name}", {"error": exc.message[:300]})
        raise
    audit(request, "signal_path.save", f"{drawing_id}/{body.name}",
          {"id": result["id"], "elements": result["elements"], "conditions": result["conditions"]})
    return result


@router.delete("/{drawing_id}/signal-paths/{path_id}", dependencies=[ENGINEER])
async def delete(drawing_id: str, path_id: int, request: Request) -> dict[str, Any]:
    _check(request, drawing_id)
    result = _svc(request).delete(request.state.user, drawing_id, path_id)
    audit(request, "signal_path.delete", f"{drawing_id}/{path_id}", {"name": result["name"]})
    return result


class Question(_M):
    element: str = Field(min_length=1, max_length=120)
    role: Literal["valve", "threeway", "pump", "switch"] = "valve"


class SuggestBody(_M):
    text: str = Field(max_length=2000)
    questions: list[Question] = Field(min_length=1, max_length=25)


@router.post("/{drawing_id}/signal-paths/suggest", dependencies=[ENGINEER])
async def suggest(drawing_id: str, body: SuggestBody, request: Request) -> StreamingResponse:
    """"Forklar med egne ord" (v4.3.0): hjælperen udfylder betingelserne som forslag. Strømmes som server-sent events
    (`queued`, `done` med forslag, eller `error`) — modellen kan bruge minutter. Gemmer intet. Audit: kun metadata."""
    _check(request, drawing_id)
    user = request.state.user
    svc = request.app.state.signal_suggester
    prepared = await asyncio.to_thread(svc.prepare, user, drawing_id, [q.model_dump() for q in body.questions], body.text,
                                       request.app.state.scope_service.visible_tags(user))
    t0 = time.monotonic()

    def close(last: dict[str, Any]) -> None:
        if not last:
            svc.assistant.finish(user.username)   # afbrudt før start: frigiv brugeren
        audit(request, "signal_path.suggest", drawing_id, {
            "questions": len(prepared["questions"]), "filled": len(last.get("suggestions", [])),
            "ms": round((time.monotonic() - t0) * 1000), "result": last.get("type") or "afbrudt"})

    return sse_response(lambda: svc.run(user, prepared), close)
