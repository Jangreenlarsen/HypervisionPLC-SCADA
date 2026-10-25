"""Genstart fra web (v1.8.0): SCADA-tjenesten eller hele maskinen. Tjenesten kører som en almindelig bruger og kan hverken genstarte sig
selv eller maskinen, så den lægger en anmodning (`power.request`) i `<data>/config/`; en root-hjælper (systemd .path, deploy/apply-power.sh)
udfører den. Samme mønster som netværksopsætningen (services/netconfig.py)."""

from __future__ import annotations

import json
import logging
import re
import secrets
import time
from pathlib import Path
from typing import Any

from .errors import ServiceError

log = logging.getLogger("scada.power")

ACTIONS = {"restart": "SCADA-tjenesten", "reboot": "maskinen"}
PENDING_MAX_S = 120   # som hjælperens MAX_AGE: en ældre anmodning er stale og ignoreres


class PowerService:
    def __init__(self, data_dir: Path, state_dir: Path | None = None):
        self.dir = data_dir / "config"                                          # ejes af tjenesten: anmodningen
        self.state = state_dir or Path("/var/lib/hypervisionplc-scada-net")     # ejes af root: markør og seneste handling

    @property
    def enabled(self) -> bool:
        """Hjælperen er installeret (deploy/install.sh opretter markøren)."""
        return (self.state / "power-enabled").is_file()

    def _pending(self) -> bool:
        req = self.dir / "power.request"
        try:
            return time.time() - req.stat().st_mtime < PENDING_MAX_S
        except OSError:
            return False

    def status(self) -> dict[str, Any]:
        last = None
        try:
            last = json.loads((self.state / "power.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        return {"enabled": self.enabled, "pending": self._pending(), "last": last,
                "actions": [{"id": k, "label": v} for k, v in ACTIONS.items()]}

    def request(self, action: str, actor: str) -> dict[str, Any]:
        if action not in ACTIONS:
            raise ServiceError(400, f"Ukendt handling '{action}' — vælg restart eller reboot")
        if not self.enabled:
            raise ServiceError(409, "Genstart fra web er ikke installeret på denne maskine — opdatér SCADA'en (System › Opdatering), "
                                    "eller genstart fra kommandolinjen (sudo systemctl restart hypervisionplc-scada / sudo reboot)")
        if self._pending():
            raise ServiceError(409, "En genstart er allerede bestilt — vent et øjeblik")
        by = re.sub(r"[^A-Za-z0-9._-]", "", actor)[:40] or "ukendt"
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / "power.request.tmp"
        tmp.write_text(f"action={action}\nby={by}\nid={secrets.token_hex(4)}\n", encoding="utf-8")
        tmp.replace(self.dir / "power.request")   # først nu ser hjælperen den
        log.warning("Genstart af %s bestilt af %s", ACTIONS[action], by)
        return {"requested": action, "label": ACTIONS[action]}
