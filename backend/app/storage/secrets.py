"""Hemmeligheder (PLC-adgangskoder) i en git-ignoreret JSON-fil — CLAUDE.md regel 6.

Værdier logges aldrig og returneres aldrig til en klient; API'et ser kun `has_password`.
"""

from __future__ import annotations

import hashlib
import hmac
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

    # Scrape-token til /metrics: kun SHA-256-kontrolsummen gemmes (tokenet er langt og tilfældigt, så en hurtig hash er nok),
    # og værdien kan aldrig læses tilbage.

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def has_metrics_token(self) -> bool:
        with self._lock:
            return bool(self._load().get("metrics", {}).get("token_sha256"))

    def set_metrics_token(self, token: str) -> None:
        with self._lock:
            data = self._load()
            data["metrics"] = {"token_sha256": self._digest(token)}
            self._save(data)

    def delete_metrics_token(self) -> None:
        with self._lock:
            data = self._load()
            if data.pop("metrics", None) is not None:
                self._save(data)

    def verify_metrics_token(self, candidate: str) -> bool:
        with self._lock:
            stored = self._load().get("metrics", {}).get("token_sha256")
        return bool(stored) and hmac.compare_digest(stored, self._digest(candidate))

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
