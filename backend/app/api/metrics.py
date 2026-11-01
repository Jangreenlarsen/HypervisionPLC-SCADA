"""Prometheus (lag 2): `GET /metrics` med scrape-token (Bearer) og admin-endpoints til at sætte/fjerne tokenet.

Tokenet er skriv-kun: serveren gemmer kun en SHA-256-kontrolsum i secrets-filen og returnerer aldrig værdien (kun *om*
et token er sat). En session (cookie) giver IKKE adgang til /metrics — kun tokenet gør, så en scraper ikke kræver login.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from ..services import metrics
from .auth import ADMIN, audit, client_ip

log = logging.getLogger(__name__)

router = APIRouter()
admin_router = APIRouter(prefix="/api/system/metrics")

MIN_TOKEN_LENGTH = 24
_LOG_EVERY_S = 60.0
_MAX_LOG_IPS = 1000


class TokenBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # URL-sikre tegn: et token med mellemrum ville kunne gemmes, men aldrig matche (Authorization-headeren trimmes)
    token: str = Field(min_length=MIN_TOKEN_LENGTH, max_length=200, pattern=r"^[A-Za-z0-9_\-.~]+$")


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


@router.get("/metrics")
async def get_metrics(request: Request) -> Response:
    state = request.app.state
    secrets = state.secrets
    if not secrets.has_metrics_token():
        return JSONResponse({"error": "Metrics er ikke slået til — en admin sætter et scrape-token under System › Status"},
                            status_code=404)
    token = _bearer(request)
    if token is None or not secrets.verify_metrics_token(token):
        state.metrics_auth_failures += 1
        ip = client_ip(request)
        now = time.monotonic()
        if now - state.metrics_last_log.get(ip, -_LOG_EVERY_S) >= _LOG_EVERY_S:   # ikke en logpost pr. scrape
            state.metrics_last_log[ip] = now
            if len(state.metrics_last_log) > _MAX_LOG_IPS:   # ingen ubegrænset vækst (fx mange IPv6-adresser)
                cutoff = now - _LOG_EVERY_S
                state.metrics_last_log = {k: t for k, t in state.metrics_last_log.items() if t > cutoff}
            log.warning("Afvist /metrics fra %s: %s token", ip, "forkert" if token else "manglende")
        return JSONResponse({"error": "Forkert eller manglende token (Authorization: Bearer …)"}, status_code=401,
                            headers={"WWW-Authenticate": "Bearer"})
    details = await state.health_service.details(state)
    return Response(metrics.render(details, state.metrics_auth_failures), media_type=metrics.CONTENT_TYPE)


@admin_router.get("", dependencies=[ADMIN])
async def status(request: Request) -> dict[str, Any]:
    return {"enabled": request.app.state.secrets.has_metrics_token(), "min_length": MIN_TOKEN_LENGTH,
            "auth_failures": request.app.state.metrics_auth_failures}


@admin_router.put("", dependencies=[ADMIN])
async def set_token(body: TokenBody, request: Request) -> dict[str, Any]:
    request.app.state.secrets.set_metrics_token(body.token)
    audit(request, "system.metrics.token", "", {"enabled": True})   # værdien logges aldrig
    return {"enabled": True}


@admin_router.delete("", dependencies=[ADMIN])
async def delete_token(request: Request) -> dict[str, Any]:
    request.app.state.secrets.delete_metrics_token()
    audit(request, "system.metrics.token", "", {"enabled": False})
    return {"enabled": False}
