"""System › Certifikater (lag 2) — kun admin. Private nøgler og adgangskoder sendes kun IND (aldrig ud) og står aldrig i auditloggen."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ..services.errors import ServiceError
from ..services.tls_admin import MAX_UPLOAD, TlsAdmin
from .auth import ADMIN, audit

router = APIRouter(prefix="/api/system/tls", dependencies=[ADMIN])


def _svc(request: Request) -> TlsAdmin:
    return request.app.state.tls_admin


async def _json(request: Request) -> dict[str, Any]:
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > MAX_UPLOAD * 3:
        raise ServiceError(413, f"Anmodningen er for stor (højst {MAX_UPLOAD // 1024} KB pr. fil)")
    raw = await request.body()
    if len(raw) > MAX_UPLOAD * 3:                      # to filer + base64/JSON-indpakning
        raise ServiceError(413, f"Anmodningen er for stor (højst {MAX_UPLOAD // 1024} KB pr. fil)")
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        raise ServiceError(400, "Forventede JSON") from None
    if not isinstance(body, dict):
        raise ServiceError(400, "Forventede et JSON-objekt")
    return body


def _str(body: dict[str, Any], key: str) -> str | None:
    v = body.get(key)
    return v if isinstance(v, str) and v else None


def _audit_ok(request: Request, action: str, result: dict[str, Any]) -> None:
    cert = result.get("cert") or {}
    audit(request, action, cert.get("cn", ""), {"fingerprint": cert.get("fingerprint", ""), "not_after": cert.get("not_after")})


@router.get("")
async def status(request: Request) -> dict[str, Any]:
    return await asyncio.to_thread(_svc(request).status)


@router.get("/cert.pem")
async def cert_pem(request: Request) -> Response:
    data = await asyncio.to_thread(_svc(request).cert_pem)
    return Response(data, media_type="application/x-pem-file", headers={"Content-Disposition": 'attachment; filename="scada-cert.pem"'})


@router.post("/selfsigned")
async def selfsigned(request: Request) -> dict[str, Any]:
    result = await asyncio.to_thread(_svc(request).create_self_signed, await _json(request))
    _audit_ok(request, "tls.selfsigned", result)
    return result


@router.post("/csr")
async def csr(request: Request) -> dict[str, Any]:
    result = await asyncio.to_thread(_svc(request).create_csr, await _json(request))
    audit(request, "tls.csr", result.get("subject", ""), {"sans": result.get("sans", [])})
    return result


@router.delete("/csr")
async def cancel_csr(request: Request) -> dict[str, Any]:
    await asyncio.to_thread(_svc(request).cancel_csr)
    audit(request, "tls.csr.cancel", "", {})
    return {"ok": True}


@router.post("/signed")
async def signed(request: Request) -> dict[str, Any]:
    cert = _str(await _json(request), "cert")
    if not cert:
        raise ServiceError(400, "Indsæt eller vælg det signerede certifikat")
    result = await asyncio.to_thread(_svc(request).install_signed, cert.encode())
    _audit_ok(request, "tls.signed", result)
    return result


@router.post("/import")
async def import_(request: Request) -> dict[str, Any]:
    body = await _json(request)
    svc = _svc(request)
    if body.get("format") == "pkcs12":
        try:
            data = base64.b64decode(_str(body, "p12") or "", validate=True)
        except (binascii.Error, ValueError):
            raise ServiceError(400, "PKCS#12-filen kunne ikke læses") from None
        result = await asyncio.to_thread(svc.import_pkcs12, data, _str(body, "password"))
    elif body.get("format") == "pem":
        cert, key = _str(body, "cert"), _str(body, "key")
        if not cert or not key:
            raise ServiceError(400, "Både certifikat og privat nøgle skal angives")
        result = await asyncio.to_thread(svc.import_pem, cert.encode(), key.encode(), _str(body, "password"))
    else:
        raise ServiceError(400, "Format skal være 'pkcs12' eller 'pem'")
    _audit_ok(request, f"tls.import.{body['format']}", result)
    return result


@router.post("/restore")
async def restore(request: Request) -> dict[str, Any]:
    which = str((await _json(request)).get("which", ""))
    result = await asyncio.to_thread(_svc(request).restore, which)
    _audit_ok(request, f"tls.restore.{which}", result)
    return result
