"""Audit-log: hvem gjorde hvad, hvornår — skrivninger til PLC og konfigurationsændringer.

Adgangskoder og andre hemmeligheder må ALDRIG lægges i `detail` (CLAUDE.md regel 6).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..storage.db import Database

log = logging.getLogger("scada.audit")
KEEP_ROWS = 50_000
_SECRET_KEYS = {"password", "old_password", "new_password", "token", "password_hash"}


def _scrub(detail: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in detail.items():
        if k in _SECRET_KEYS:
            out[k] = "***" if v else v
        elif isinstance(v, dict):
            out[k] = _scrub(v)
        else:
            out[k] = v
    return out


class AuditService:
    def __init__(self, db: Database):
        self.db = db

    def record(self, username: str, ip: str, action: str, target: str = "", detail: dict[str, Any] | None = None,
               result: str = "ok", message: str = "") -> None:
        entry = {"ts": time.time(), "username": username, "ip": ip, "action": action, "target": target,
                 "detail": _scrub(detail or {}), "result": result, "message": message}
        try:
            self.db.insert_audit(entry, KEEP_ROWS)
        except Exception:  # audit må aldrig vælte selve handlingen — men det skal fremgå af loggen
            log.exception("Kunne ikke skrive audit-post: %s %s", action, target)
        log.info("AUDIT %s %s %s %s %s", username, action, target, result, message)

    def list(self, limit: int = 200, action: str | None = None) -> list[dict[str, Any]]:
        return self.db.list_audit(max(1, min(limit, 2000)), action)
