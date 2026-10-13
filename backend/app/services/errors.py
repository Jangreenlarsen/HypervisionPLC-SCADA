from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    """Fejl som API-laget oversætter til `{"error": message, **extra}` med `status`.
    `extra`: valgfrie ekstra felter til frontend (fx fejl pr. trin i symbol-guiden) — `error` er altid den læsbare tekst."""

    def __init__(self, status: int, message: str, extra: dict[str, Any] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra or {}
