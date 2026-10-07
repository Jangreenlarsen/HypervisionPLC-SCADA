"""Konfiguration fra miljøvariabler (evt. via .env-fil indlæst af systemd/EnvironmentFile)."""

from __future__ import annotations

import ipaddress
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

log = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"Miljøvariablen {name} skal være et tal, ikke '{raw}'") from None


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("SCADA_DATA_DIR", REPO_ROOT / "data")))
    host: str = field(default_factory=lambda: os.environ.get("SCADA_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("SCADA_PORT", "8000")))
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO").upper())
    plc_rate: float = field(default_factory=lambda: _env_float("SCADA_PLC_RATE", 5.0))
    poll_fast_s: float = field(default_factory=lambda: _env_float("SCADA_POLL_FAST_S", 0.5))
    poll_slow_s: float = field(default_factory=lambda: _env_float("SCADA_POLL_SLOW_S", 2.0))
    plc_timeout_s: float = field(default_factory=lambda: _env_float("SCADA_PLC_TIMEOUT_S", 5.0))
    frontend_dir: Path = field(default_factory=lambda: Path(os.environ.get("SCADA_FRONTEND_DIR", REPO_ROOT / "frontend" / "dist")))
    # AGPL §13: brugere over netværket skal tilbydes kildekoden — peg på jeres egen fork ved ændringer.
    source_url: str = field(default_factory=lambda: os.environ.get(
        "SCADA_SOURCE_URL", "https://github.com/Jangreenlarsen/HypervisionPLC-SCADA"))
    start_runtimes: bool = True

    def __post_init__(self) -> None:
        if self.plc_rate <= 0 or self.plc_rate > 9:
            raise ValueError("SCADA_PLC_RATE skal være mellem 0 og 9 req/s (PLC'ens grænse er 10 pr. IP)")
        if self.poll_fast_s <= 0 or self.poll_slow_s <= 0:
            raise ValueError("Poll-intervaller skal være > 0")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "scada.db"

    @property
    def secrets_path(self) -> Path:
        return self.data_dir / "secrets.json"

    def warn_insecure(self) -> list[str]:
        """Usikre indstillinger skal være synlige ved opstart (CLAUDE.md regel 12)."""
        warnings = []
        try:
            loopback = ipaddress.ip_address(self.host).is_loopback
        except ValueError:
            loopback = self.host == "localhost"
        if not loopback:
            warnings.append(
                f"SCADA_HOST={self.host}: serveren lytter på netværket, men bruger-login er endnu "
                "ikke implementeret (fase 5) — alle på netværket kan ændre PLC- og tag-konfiguration."
            )
        return warnings


def read_version() -> dict[str, str]:
    path = REPO_ROOT / "version.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"version": str(data["version"]), "build": str(data["build"])}
    except (OSError, ValueError, KeyError) as exc:
        log.warning("Kan ikke læse %s: %s", path, exc)
        return {"version": "ukendt", "build": "ukendt"}
