"""OTA-opdatering (lag 2) — kun admin. Selve installationen udføres af en privilegeret hjælper (deploy/apply-update.sh)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from ..services.auth import CurrentUser
from ..services.errors import ServiceError
from ..services.github_releases import GitHubReleases
from ..services.updates import MAX_PACKAGE_BYTES, UpdateService
from .auth import ADMIN, audit, require

router = APIRouter(prefix="/api/system/update")


class ApplyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sha256: str = Field(min_length=64, max_length=64)
    reinstall: bool = False


def _svc(request: Request) -> UpdateService:
    return request.app.state.update_service


@router.get("", dependencies=[ADMIN])
async def status(request: Request) -> dict[str, Any]:
    return _svc(request).status()


@router.post("/upload")
async def upload(request: Request, user: CurrentUser = Depends(require("admin"))) -> dict[str, Any]:
    """Modtag og kontrollér en pakke (streames til disk). Installerer ikke noget — det kræver en særskilt bekræftelse."""
    svc = _svc(request)
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > MAX_PACKAGE_BYTES:
        raise ServiceError(413, f"Pakken er for stor (max {MAX_PACKAGE_BYTES // 1024 // 1024} MB)")
    size = 0
    with svc.receiving() as incoming:
        with incoming.open("wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_PACKAGE_BYTES:
                    raise ServiceError(413, f"Pakken er for stor (max {MAX_PACKAGE_BYTES // 1024 // 1024} MB)")
                f.write(chunk)
        try:
            info = await asyncio.to_thread(svc.stage, user.username, incoming)
        except ServiceError as exc:
            request.app.state.audit_service.record(user.username, request.client.host if request.client else "",
                                                   "system.update.upload", "", {"size": size}, "error", exc.message[:500])
            raise
    audit(request, "system.update.upload", info["version"], {"version": info["version"], "build": info["build"],
                                                              "sha256": info["sha256"], "size": info["size"], "relation": info["relation"]})
    return info


@router.post("/apply")
async def apply(body: ApplyBody, request: Request, user: CurrentUser = Depends(require("admin"))) -> dict[str, Any]:
    try:
        result = await asyncio.to_thread(_svc(request).apply, body.sha256.lower(), user.username, body.reinstall)
    except ServiceError as exc:
        request.app.state.audit_service.record(user.username, request.client.host if request.client else "",
                                               "system.update.apply", "", {}, "error", exc.message[:500])
        raise
    audit(request, "system.update.apply", result["version"], result)
    return result


@router.delete("/staged", status_code=204, dependencies=[ADMIN])
async def discard(request: Request) -> None:
    _svc(request).discard()
    audit(request, "system.update.discard", "", {})


class GitHubBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)   # pakken admin så under "Søg" — der klargøres ikke andet


def _gh(request: Request) -> GitHubReleases:
    return request.app.state.github_releases


@router.get("/github", dependencies=[ADMIN])
async def github_latest(request: Request) -> dict[str, Any]:
    """Den nyeste udgivelse på GitHub og om den er nyere end den installerede."""
    return await asyncio.to_thread(_gh(request).latest)


@router.post("/github/download")
async def github_download(body: GitHubBody, request: Request, user: CurrentUser = Depends(require("admin"))) -> dict[str, Any]:
    """Hent den nyeste udgivelse og klargør den som en uploadet pakke. Installerer ikke noget."""
    svc = _svc(request)
    with svc.receiving() as incoming:
        try:
            await asyncio.to_thread(_gh(request).download, incoming, body.name)
            info = await asyncio.to_thread(svc.stage, user.username, incoming)
        except ServiceError as exc:
            request.app.state.audit_service.record(user.username, request.client.host if request.client else "",
                                                   "system.update.github", body.name, {"name": body.name}, "error", exc.message[:500])
            raise
    audit(request, "system.update.github", info["version"], {"version": info["version"], "build": info["build"], "name": body.name,
                                                              "sha256": info["sha256"], "size": info["size"], "relation": info["relation"]})
    return info
