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
    # Eksterne slaver (RS485/expansion boards via /api/ext): bussen er langsom og PLC'ens cache lille
    poll_ext_s: float = field(default_factory=lambda: _env_float("SCADA_POLL_EXT_S", 2.0))
    plc_timeout_s: float = field(default_factory=lambda: _env_float("SCADA_PLC_TIMEOUT_S", 5.0))
    frontend_dir: Path = field(default_factory=lambda: Path(os.environ.get("SCADA_FRONTEND_DIR", REPO_ROOT / "frontend" / "dist")))
    # AGPL §13: brugere over netværket skal tilbydes kildekoden — peg på jeres egen fork ved ændringer.
    source_url: str = field(default_factory=lambda: os.environ.get(
        "SCADA_SOURCE_URL", "https://github.com/Jangreenlarsen/HypervisionPLC-SCADA"))
    # Sæt til true når serveren kører bag TLS (nginx) — så sendes session-cookien kun over HTTPS.
    cookie_secure: bool = field(default_factory=lambda: os.environ.get("SCADA_COOKIE_SECURE", "").lower() in ("1", "true", "yes"))
    session_hours: float = field(default_factory=lambda: _env_float("SCADA_SESSION_HOURS", 8.0))
    # Åbne /ws/live-forbindelser gentjekker sessionen så ofte: logout, deaktivering, rolle- og tegningsadgang slår
    # igennem inden for så mange sekunder (en åben skærm tæller som brug og forlænger sessionen som et kald).
    ws_revalidate_s: float = field(default_factory=lambda: _env_float("SCADA_WS_REVALIDATE_S", 10.0))
    # Kun ved første opstart (ingen brugere): adgangskode til 'admin'. Ellers genereres en engangsadgangskode.
    admin_password: str | None = field(default_factory=lambda: os.environ.get("SCADA_ADMIN_PASSWORD") or None)
    # Automatisk backup på serveren hvert N. time (0 = fra); de seneste `backup_keep` gemmes.
    backup_hours: float = field(default_factory=lambda: _env_float("SCADA_BACKUP_HOURS", 24.0))
    backup_keep: int = field(default_factory=lambda: int(os.environ.get("SCADA_BACKUP_KEEP", "7")))
    # Antal automatiske øjebliksbilleder af trend-historikken der gemmes (0 = ingen)
    trend_backup_keep: int = field(default_factory=lambda: int(os.environ.get("SCADA_TREND_BACKUP_KEEP", "2")))
    alarm_tick_s: float = field(default_factory=lambda: _env_float("SCADA_ALARM_TICK_S", 1.0))
    # Symbolernes position/tilstand genberegnes ved hver live-ændring og mindst så ofte (valideringstid, Venter → Afvigelse)
    symbol_tick_s: float = field(default_factory=lambda: _env_float("SCADA_SYMBOL_TICK_S", 0.5))
    # En PLC skal have været utilgængelig så længe før kommunikationsalarmen udløses
    alarm_comm_delay_s: float = field(default_factory=lambda: _env_float("SCADA_ALARM_COMM_DELAY_S", 10.0))
    trend_days: float = field(default_factory=lambda: _env_float("SCADA_TREND_DAYS", 30.0))
    trend_flush_s: float = field(default_factory=lambda: _env_float("SCADA_TREND_FLUSH_S", 5.0))
    # Energi-tags gemmes længere end anden historik, så måneds-/årsrapporter er mulige.
    energy_days: float = field(default_factory=lambda: _env_float("SCADA_ENERGY_DAYS", 400.0))
    # Root-ejet mappe med status/log for netværksændringer (deploy/apply-config.sh); tjenesten kun læser den
    net_state_dir: Path = field(default_factory=lambda: Path(os.environ.get("SCADA_NET_STATE_DIR", "/var/lib/hypervisionplc-scada-net")))
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
        if not loopback and not self.cookie_secure:
            warnings.append(
                f"SCADA_HOST={self.host}: serveren lytter på netværket uden TLS — login og session-cookies "
                "sendes ukrypteret. Kør bag nginx med TLS og sæt SCADA_COOKIE_SECURE=true."
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
