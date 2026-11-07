"""LLM-hjælperen (lag 2, v3.37.0): hardwareprofil, LLM-pakke, styring af LLM-tjenesten og afprøvning. Se services/assistant.py."""

from __future__ import annotations

import asyncio
import hashlib
import platform
import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ..services.assist_tools import Context
from ..services.assistant import DISK_CHECK_BYTES, MAX_PACKAGE_BYTES, WRITE_BUFFER_BYTES, AssistantService
from ..services.auth import CurrentUser, role_at_least
from ..services.errors import ServiceError
from .auth import ADMIN, audit, require
from .sse import sse_response

router = APIRouter(prefix="/api/assist")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileBody(_Model):
    profile: str


class ActionBody(_Model):
    action: Literal["install", "start", "stop", "remove"]


class AskContext(_Model):
    page: str = Field("", max_length=40)
    drawing: str | None = Field(None, max_length=80)
    alarm: str | None = Field(None, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=10)


class Turn(_Model):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class AskBody(_Model):
    question: str = Field(max_length=2000)
    context: AskContext = Field(default_factory=AskContext)
    history: list[Turn] = Field(default_factory=list, max_length=20)


def _svc(request: Request) -> AssistantService:
    return request.app.state.assistant


@router.get("/available")
async def available(request: Request, user: CurrentUser = Depends(require("viewer"))) -> dict[str, Any]:
    """Til alle roller: må hjælper-funktionerne vises? (ingen detaljer om maskinen). `can_ask`: operatør og op."""
    st = await _svc(request).status()
    return {"available": st["available"], "busy": st["busy"], "waiting": st["waiting"],
            "can_ask": role_at_least(user.role, "operator")}


@router.post("/ask")
async def ask(body: AskBody, request: Request, user: CurrentUser = Depends(require("operator"))) -> StreamingResponse:
    """Spørg hjælperen (operatør og op). Svaret strømmes som server-sent events: `sources`, `queued`, `delta`…, `done` eller
    `error`. Audit logger kun metadata (side, værktøjer, svartid, tokens) — aldrig spørgsmål eller svar."""
    svc = _svc(request)
    c = body.context
    ctx = Context(page=c.page, drawing=c.drawing, alarm=c.alarm, tags=[t[:80] for t in c.tags])
    prepared = await asyncio.to_thread(svc.prepare, user, body.question, ctx, [t.model_dump() for t in body.history])
    t0 = time.monotonic()

    def close(last: dict[str, Any]) -> None:
        svc.finish(user.username)
        audit(request, "assist.ask", c.page or "", {
            "tools": prepared["tools"], "data_chars": prepared["data_chars"], "ms": round((time.monotonic() - t0) * 1000),
            "tokens_in": last.get("tokens_in"), "tokens_out": last.get("tokens_out"),
            "result": "ok" if last.get("type") == "done" else ("error" if last else "afbrudt")})

    return sse_response(lambda: svc.answer(user, prepared), close)


@router.get("/status", dependencies=[ADMIN])
async def status(request: Request) -> dict[str, Any]:
    return await _svc(request).status()


@router.put("/profile")
async def set_profile(body: ProfileBody, request: Request, user: CurrentUser = Depends(require("admin"))) -> dict[str, Any]:
    result = request.app.state.hw_profile.set_profile(body.profile, user.username)
    audit(request, "assist.profile", body.profile, {"llm_allowed": result["llm_allowed"]})
    return result


@router.post("/package")
async def upload_package(request: Request, user: CurrentUser = Depends(require("admin"))) -> dict[str, Any]:
    """Modtag en LLM-pakke (streames til disk, SHA256 beregnes undervejs). Installerer ikke — det er en særskilt handling."""
    svc = _svc(request)
    length = request.headers.get("content-length")
    limit = f"max {MAX_PACKAGE_BYTES // 1024 ** 3} GB"
    if length is not None and length.isdigit() and int(length) > MAX_PACKAGE_BYTES:
        raise ServiceError(413, f"LLM-pakken er for stor ({limit})")
    # Før der modtages noget: profil og plads (pakken må aldrig fylde disken, som databasen også ligger på)
    svc.precheck(int(length) if length and length.isdigit() else None)
    size = 0
    digest = hashlib.sha256()
    buf: list[bytes] = []
    buffered = 0
    next_check = DISK_CHECK_BYTES

    def flush(f: Any, chunks: list[bytes]) -> None:   # i en tråd: skrivning og SHA256 må ikke blokere event-loopet
        for c in chunks:
            digest.update(c)
            f.write(c)

    try:
        with svc.receiving() as received:
            with received.open("wb") as f:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_PACKAGE_BYTES:
                        raise ServiceError(413, f"LLM-pakken er for stor ({limit})")
                    buf.append(chunk)
                    buffered += len(chunk)
                    if buffered >= WRITE_BUFFER_BYTES:
                        await asyncio.to_thread(flush, f, buf)
                        buf, buffered = [], 0
                    if size >= next_check:
                        next_check += DISK_CHECK_BYTES
                        svc.check_space_during_upload()
                if buf:
                    await asyncio.to_thread(flush, f, buf)
            info = await asyncio.to_thread(svc.stage, user.username, received, digest.hexdigest(), platform.machine())
    except ServiceError as exc:
        audit(request, "assist.package", "", {"size": size, "error": exc.message[:300]})
        raise
    man = info["manifest"]
    audit(request, "assist.package", man["model"]["name"], {"sha256": info["sha256"], "size": info["size"],
                                                            "llama": man["llama_build"], "model": man["model"]["id"]})
    return info


@router.delete("/package", status_code=204, dependencies=[ADMIN])
async def discard_package(request: Request) -> None:
    _svc(request).discard()


@router.post("/service")
async def service_action(body: ActionBody, request: Request, user: CurrentUser = Depends(require("admin"))) -> dict[str, Any]:
    try:
        result = _svc(request).request(body.action, user.username)
    except ServiceError as exc:
        audit(request, "assist.service", body.action, {"error": exc.message[:300]})
        raise
    audit(request, "assist.service", body.action)
    return result


@router.post("/test", dependencies=[ADMIN])
async def selftest(request: Request) -> dict[str, Any]:
    """Lille afprøvning af modellen med svartid og hastighed (vises under System › Hjælper)."""
    result = await _svc(request).selftest()
    audit(request, "assist.test", result.get("model") or "", {k: result[k] for k in ("ms", "tokens_out", "tokens_per_s")})
    return result
