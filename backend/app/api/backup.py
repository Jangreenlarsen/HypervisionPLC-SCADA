"""Backup/restore (lag 2) — kun admin."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response

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
    return FileResponse(path, media_type="application/json", filename=name)
