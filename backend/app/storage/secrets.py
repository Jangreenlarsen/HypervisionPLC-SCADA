"""Hemmeligheder (PLC-adgangskoder) i en git-ignoreret JSON-fil — CLAUDE.md regel 6.

Værdier logges aldrig og returneres aldrig til en klient; API'et ser kun `has_password`.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path


class SecretStore:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, dict[str, str]]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Indholdet citeres bevidst ikke — filen indeholder hemmeligheder.
            raise RuntimeError(f"Kan ikke læse secrets-filen {self._path}: {type(exc).__name__}") from None
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict[str, dict[str, str]]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        if os.name == "posix":
            os.chmod(tmp, 0o600)
        os.replace(tmp, self._path)

    def get_plc_password(self, key: str) -> str | None:
        with self._lock:
            return self._load().get("plc_passwords", {}).get(key)

    def has_plc_password(self, key: str) -> bool:
        return self.get_plc_password(key) is not None

    def set_plc_password(self, key: str, password: str) -> None:
        with self._lock:
            data = self._load()
            data.setdefault("plc_passwords", {})[key] = password
            self._save(data)

    def delete_plc_password(self, key: str) -> None:
        with self._lock:
            data = self._load()
            if data.get("plc_passwords", {}).pop(key, None) is not None:
                self._save(data)
