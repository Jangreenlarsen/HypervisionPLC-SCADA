"""LLM-hjælperen (lag 2, v3.37.0): hardwareprofil, LLM-pakke, styring af LLM-tjenesten og afprøvning. Se services/assistant.py."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import platform
import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ..services.assist_tools import Context
from ..services.assistant import ARCH_ALIASES, DISK_CHECK_BYTES, MAX_PACKAGE_BYTES, WRITE_BUFFER_BYTES, AssistantService
from ..services.llm_catalog import Cancelled, LlmCatalog
from ..services.auth import CurrentUser, role_at_least
from ..services.errors import ServiceError
from .auth import ADMIN, audit, require
from .sse import sse_response

router = APIRouter(prefix="/api/assist")
log = logging.getLogger("scada.assist")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileBody(_Model):
    profile: str


class DownloadBody(_Model):
    model: str = Field(min_length=1, max_length=64)
    install: bool = True          # installér og slå til, når pakken er hentet og kontrolleret


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


def _arch() -> str:
    m = platform.machine()
    return ARCH_ALIASES.get(m.lower(), m)


def _cat(request: Request) -> LlmCatalog:
    return request.app.state.llm_catalog


@router.get("/catalog", dependencies=[ADMIN])
async def catalog(request: Request) -> dict[str, Any]:
    """Varianterne, der kan hentes fra GitHub (v4.4.0), og en evt. igangværende hentning."""
    svc, cat = _svc(request), _cat(request)
    hw = request.app.state.hw_profile.status()
    model = (svc._installed() or {}).get("model")
    installed = model.get("id") if isinstance(model, dict) else None
    return {"arch": _arch(), "profile": hw["profile"], "llm_allowed": hw["llm_allowed"], "repo": cat.repo,
            "entries": cat.entries(_arch(), hw["profile"], installed), "job": dict(cat.job)}


@router.post("/download")
async def start_download(body: DownloadBody, request: Request,
                         user: CurrentUser = Depends(require("admin"))) -> dict[str, Any]:
    """Hent en variant fra GitHub i baggrunden (fremdrift i /catalog). Klargøres som en uploadet pakke og installeres."""
    svc, cat = _svc(request), _cat(request)
    if cat.busy():
        raise ServiceError(409, "En model hentes allerede — vent, eller afbryd den")
    hw = request.app.state.hw_profile.status()
    if not hw["llm_allowed"]:
        raise ServiceError(409, "Hardwareprofilen tillader ikke hjælperen — vælg en profil med LLM ovenfor")
    entry = next((e for e in cat.entries(_arch(), hw["profile"], None) if e["id"] == body.model), None)
    if entry is None:
        raise ServiceError(404, f"Modellen '{body.model}' findes ikke til {_arch()} i listen")
    if not entry["fits"]:
        raise ServiceError(409, f"{entry['name']} passer ikke til hardwareprofilen ({hw['profile']})")
    cat.start({"state": "running", "model": entry["id"], "name": entry["name"], "by": user.username,
               "started": time.time(), "done": 0, "total": entry["size"], "part": 0, "parts": 0})
    audit(request, "assist.download", entry["id"], {"release": entry["release"], "install": body.install})

    def work() -> dict[str, Any]:
        with svc.receiving() as received:
            sha, _size = cat.download(entry["id"], _arch(), received, svc.precheck_download, svc.check_space_during_upload)
            if cat.cancelled():   # afbrudt lige efter sidste del: klargør ikke
                raise Cancelled()
            return svc.stage(user.username, received, sha, platform.machine())

    async def runner() -> None:
        try:
            info = await asyncio.to_thread(work)
            cat.job.update(state="done", finished=time.time(), sha256=info["sha256"])
            audit(request, "assist.package", entry["name"], {"sha256": info["sha256"], "size": info["size"],
                                                             "source": entry["release"]})
            if body.install and not cat.cancelled():
                try:   # pakken er hentet og klar — en fejl her vises særskilt (kan installeres med knappen)
                    svc.request("install", user.username)
                    cat.job["installing"] = True
                    audit(request, "assist.service", "install")
                except ServiceError as exc:
                    cat.job["install_error"] = exc.message
        except Cancelled:
            cat.job.update(state="cancelled", finished=time.time())
            audit(request, "assist.download", entry["id"], {"result": "afbrudt"})
        except ServiceError as exc:
            cat.job.update(state="error", error=exc.message, finished=time.time())
            audit(request, "assist.download", entry["id"], {"error": exc.message[:300]})
        except Exception:   # noqa: BLE001 — fejlen skal ses på siden, ikke forsvinde i en baggrundsopgave
            log.exception("Hentning af LLM-model fejlede")
            cat.job.update(state="error", error="Uventet fejl under hentningen — se loggen", finished=time.time())

    request.app.state.llm_download_task = asyncio.create_task(runner())   # reference, så opgaven ikke ryddes væk
    return dict(cat.job)


@router.delete("/download", dependencies=[ADMIN])
async def cancel_download(request: Request) -> dict[str, Any]:
    cat = _cat(request)
    ok = cat.cancel()
    if ok:
        audit(request, "assist.download.cancel", str(cat.job.get("model") or ""))
    return {"cancelled": ok}


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
