"""Oversæt fejl til ét fast format: `{"error": "<læsbar tekst>"}`.

FastAPI/pydantic kaster valideringsfejl som en LISTE af objekter, ikke en streng
(CLAUDE.md regel 12) — den form flades her ud til én læsbar tekst.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..services.errors import ServiceError

log = logging.getLogger(__name__)


def format_validation_errors(errors: list[Any]) -> str:
    parts = []
    for err in errors:
        if not isinstance(err, dict):
            parts.append(str(err))
            continue
        loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
        msg = err.get("msg", "ugyldig værdi")
        if err.get("type") == "extra_forbidden":
            msg = "ukendt felt"
        elif err.get("type") == "missing":
            msg = "mangler"
        parts.append(f"{'.'.join(loc)}: {msg}" if loc else str(msg))
    return "Ugyldigt input — " + "; ".join(parts) if parts else "Ugyldigt input"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def _service(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse({"error": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"error": format_validation_errors(list(exc.errors()))}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse({"error": detail}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Uventet fejl ved %s %s", request.method, request.url.path)
        return JSONResponse({"error": f"Intern serverfejl: {type(exc).__name__}"}, status_code=500)
