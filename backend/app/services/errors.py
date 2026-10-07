from __future__ import annotations


class ServiceError(Exception):
    """Fejl som API-laget oversætter til `{"error": message}` med `status`."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message
