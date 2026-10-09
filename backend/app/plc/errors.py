"""Typede fejl fra PLC-klient-laget.

Service-laget ser kun disse — aldrig rå httpx-exceptions (ARCHITECTURE.md, lag 4a).
`message` er altid en læsbar tekst; kommer fejlen fra PLC'en, er det PLC'ens egen tekst.
"""

from __future__ import annotations

from typing import Any


class PlcError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.message = message
        self.status = status


class PlcAuthError(PlcError):
    """Login afvist (forkert brugernavn/adgangskode) eller intet token i svaret."""


class PlcForbidden(PlcError):
    """403 — brugeren på PLC'en mangler rolle/privilegie."""


class PlcRateLimited(PlcError):
    """429 — PLC'ens rate-limiter har afvist kaldet."""


class PlcUnreachable(PlcError):
    """Netværksfejl/timeout — PLC'en svarer ikke."""


class PlcApiError(PlcError):
    """Alle øvrige fejlsvar fra PLC'en (400/404/409/500 ... og uventede statusser)."""


def extract_error_message(status: int, body: Any, text: str) -> str:
    """Find den mest specifikke fejltekst i et PLC-svar.

    PLC'en svarer normalt `{"error": "...", "status": N}`, men vi må ikke antage det:
    tom body, ikke-JSON (fx en proxy-fejlside) og andre JSON-former skal også give
    en meningsfuld tekst.
    """
    if isinstance(body, dict):
        for key in ("error", "message", "detail"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(body, dict) and isinstance(body.get("result"), str):  # /api/ext-svar uden "error"
        return f"slaven svarede '{body['result']}'"
    if isinstance(body, list) and body:
        parts = [str(item.get("msg", item)) if isinstance(item, dict) else str(item) for item in body]
        return "; ".join(parts)[:300]
    if text and text.strip():
        return text.strip()[:300]
    return f"HTTP {status} fra PLC"
