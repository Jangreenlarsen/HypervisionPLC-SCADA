"""Backup/restore (lag 2) — kun admin."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask

from ..services.auth import CurrentUser
from ..services.backup import MAX_RESTORE_BYTES, BackupService
from ..services.errors import ServiceError
from .auth import ADMIN, audit, require

router = APIRouter(prefix="/api/backup")


def _svc(request: Request) -> BackupService:
    return request.app.state.backup_service


@router.get("")
async def download(request: Request, user: CurrentUser = Depends(require("admin"))) -> Response:
    data = _svc(request).export(user.username)
    audit(request, "backup.download", "", {"plcs": len(data["plcs"]), "tags": len(data["tags"]),
                                            "drawings": len(data["drawings"])})
    name = f"scada-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    return Response(json.dumps(data, ensure_ascii=False, indent=1), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/restore")
async def restore(request: Request, user: CurrentUser = Depends(require("admin"))) -> dict[str, Any]:
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > MAX_RESTORE_BYTES:
        raise ServiceError(413, f"Backup-filen er for stor (max {MAX_RESTORE_BYTES // 1024 // 1024} MB)")
    raw = await request.body()
    if len(raw) > MAX_RESTORE_BYTES:
        raise ServiceError(413, f"Backup-filen er for stor (max {MAX_RESTORE_BYTES // 1024 // 1024} MB)")
    try:
        backup = json.loads(raw)
    except ValueError:
        raise ServiceError(400, "Filen er ikke gyldig JSON") from None
    try:
        result = await _svc(request).restore(backup, user.username)
    except ServiceError as exc:
        request.app.state.audit_service.record(user.username, request.client.host if request.client else "",
                                               "backup.restore", "", {}, "error", exc.message[:500])
        raise
    audit(request, "backup.restore", "", result)
    return result


@router.get("/files", dependencies=[ADMIN])
async def list_files(request: Request) -> list[dict[str, Any]]:
    return _svc(request).list_server_backups()


@router.get("/files/{name}", dependencies=[ADMIN])
async def download_file(name: str, request: Request) -> FileResponse:
    path = _svc(request).server_backup_path(name)
    media = "application/gzip" if name.endswith(".gz") else "application/json"
    return FileResponse(path, media_type=media, filename=name)


# ------------------------------------------------------------------ trend-historik

MAX_TREND_UPLOAD_BYTES = 1024 * 1024 * 1024


def _tmp_path(request: Request, suffix: str) -> Path:
    tmp_dir = request.app.state.settings.data_dir / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    return tmp_dir / f"{uuid.uuid4().hex}{suffix}"


@router.get("/trends")
async def download_trends(request: Request, user: CurrentUser = Depends(require("admin"))) -> FileResponse:
    """Øjebliksbillede af hele trend-historikken (.db.gz) — tages uden at stoppe opsamlingen."""
    path = _tmp_path(request, ".db.gz")
    try:
        await asyncio.to_thread(_svc(request).write_trend_snapshot, path)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    audit(request, "backup.trends.download", "", {"size": path.stat().st_size})
    name = f"scada-historik-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db.gz"
    return FileResponse(path, media_type="application/gzip", filename=name,
                        background=BackgroundTask(path.unlink, missing_ok=True))


@router.post("/trends/merge")
async def merge_trends(request: Request, user: CurrentUser = Depends(require("admin"))) -> dict[str, Any]:
    """Indlæs en historik-fil og flet den ind (eksisterende værdier bevares). Streames til disk."""
    path = _tmp_path(request, ".upload")
    size = 0
    try:
        with path.open("wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_TREND_UPLOAD_BYTES:
                    raise ServiceError(413, f"Filen er for stor (max {MAX_TREND_UPLOAD_BYTES // 1024 // 1024} MB)")
                f.write(chunk)
        if size == 0:
            raise ServiceError(400, "Ingen fil modtaget")
        try:
            result = await asyncio.to_thread(_svc(request).merge_trends, path)
        except ServiceError as exc:
            request.app.state.audit_service.record(user.username, request.client.host if request.client else "",
                                                   "backup.trends.merge", "", {"size": size}, "error", exc.message[:500])
            raise
        audit(request, "backup.trends.merge", "", {"size": size, **result})
        return result
    finally:
        path.unlink(missing_ok=True)
