"""System-konfiguration (kun læsning): hvor data ligger, hvor meget de fylder/skrives, og netværksstatus.

Læser kun — ændringer (netværk, flytning af datamappen) kommer i senere trin via en privilegeret hjælper (se PLAN.md).
Netværksstatus hentes med `ip -j` (iproute2, findes på Raspberry Pi OS); mangler det (fx under Windows-udvikling), meldes
`available: false` i stedet for en fejl.
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import socket
import subprocess
import threading
from pathlib import Path
from typing import Any

from .errors import ServiceError

log = logging.getLogger(__name__)

IP_TIMEOUT_S = 3.0


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _tree_size(path: Path) -> int:
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                total += _size(p)
    except OSError:
        pass
    return total


def storage_info(data_dir: Path) -> dict[str, Any]:
    """Datamappens placering, de enkelte filers størrelse og ledig plads på disken."""
    files = []
    for name in ("scada.db", "scada.db-wal", "trends.db", "trends.db-wal"):
        p = data_dir / name
        if p.exists():
            files.append({"name": name, "size": _size(p)})
    folders = [{"name": n, "size": _tree_size(data_dir / n)} for n in ("drawings", "backups", "updates") if (data_dir / n).is_dir()]
    try:
        du = shutil.disk_usage(data_dir)
        disk: dict[str, int] | None = {"total": du.total, "used": du.used, "free": du.free}
    except OSError:
        disk = None
    return {"path": str(data_dir), "files": files, "folders": folders, "disk": disk}


def parse_ip_addr(text: str) -> list[dict[str, Any]]:
    """`ip -j addr` → netkort (uden loopback) med MAC, link og IPv4-adresser."""
    out = []
    for link in json.loads(text):
        name = link.get("ifname", "")
        if name == "lo" or "LOOPBACK" in (link.get("flags") or []):
            continue
        addrs = [{"ip": a["local"], "prefix": a.get("prefixlen")}
                 for a in link.get("addr_info", []) if a.get("family") == "inet" and a.get("local")]
        out.append({"name": name, "mac": link.get("address") or "", "state": (link.get("operstate") or "").lower(),
                    "addresses": addrs})
    return out


def parse_default_route(text: str) -> str:
    """`ip -j route` → gateway for standardruten ('' hvis ingen)."""
    for r in json.loads(text):
        if r.get("dst") == "default" and r.get("gateway"):
            return str(r["gateway"])
    return ""


def parse_resolv(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "nameserver":
            out.append(parts[1])
    return out


def _ip(*args: str) -> str:
    return subprocess.run(["ip", "-j", *args], capture_output=True, text=True, timeout=IP_TIMEOUT_S, check=True).stdout


def network_status() -> dict[str, Any]:
    status: dict[str, Any] = {"available": False, "hostname": socket.gethostname(), "interfaces": [], "gateway": "",
                              "dns": [], "error": ""}
    try:
        status["interfaces"] = parse_ip_addr(_ip("-4", "addr"))
        status["gateway"] = parse_default_route(_ip("-4", "route"))
        status["available"] = True
    except FileNotFoundError:
        status["error"] = "Netværksværktøjet 'ip' findes ikke på denne maskine"
    except (subprocess.SubprocessError, ValueError, KeyError, OSError) as exc:
        log.warning("Netværksstatus kunne ikke læses: %s", exc)
        status["error"] = f"Netværksstatus kunne ikke læses: {exc}"
    try:
        status["dns"] = parse_resolv(Path("/etc/resolv.conf").read_text(encoding="utf-8"))
    except OSError:
        pass
    return status


# ---------------------------------------------------------------- trend-indstillinger (overstyrer miljøvariablerne)
# Gemmes i <data>/config/settings.json; miljøvariablerne (SCADA_TREND_DAYS …) er standarden, når intet er gemt.
TREND_LIMITS: dict[str, tuple[float, float, str]] = {
    "retention_days": (1.0, 365.0, "Opbevaring"),
    "flush_s": (1.0, 300.0, "Skriveinterval"),
    "energy_days": (30.0, 3650.0, "Opbevaring af energi"),
}
_SETTINGS_ATTR = {"retention_days": "trend_days", "flush_s": "trend_flush_s", "energy_days": "energy_days"}
_write_lock = threading.Lock()


def _settings_path(data_dir: Path) -> Path:
    return data_dir / "config" / "settings.json"


def load_overrides(data_dir: Path) -> dict[str, float]:
    """De gemte overstyringer (kun kendte, gyldige felter — en ødelagt fil ignoreres med en advarsel)."""
    path = _settings_path(data_dir)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        log.warning("Konfigurationsfilen %s kunne ikke læses (ignoreres): %s", path, exc)
        return {}
    trends = raw.get("trends") if isinstance(raw, dict) else None
    out: dict[str, float] = {}
    for key, (lo, hi, _label) in TREND_LIMITS.items():
        v = trends.get(key) if isinstance(trends, dict) else None
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo <= v <= hi:
            out[key] = float(v)
    return out


def apply_overrides(settings: Any) -> dict[str, float]:
    """Læg de gemte overstyringer ind i Settings (ved opstart)."""
    ov = load_overrides(settings.data_dir)
    for key, value in ov.items():
        setattr(settings, _SETTINGS_ATTR[key], value)
    return ov


def validate_trend_settings(values: dict[str, Any]) -> dict[str, float]:
    """Kontrollér alle tre felter. Afviser med en specifik besked (400)."""
    out: dict[str, float] = {}
    for key, (lo, hi, label) in TREND_LIMITS.items():
        v = values.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ServiceError(400, f"{label}: skriv et tal")
        if not lo <= v <= hi:
            raise ServiceError(400, f"{label}: skal være mellem {lo:g} og {hi:g}")
        out[key] = float(v)
    if out["energy_days"] < out["retention_days"]:
        raise ServiceError(400, "Opbevaring af energi må ikke være kortere end opbevaring af anden historik")
    return out


def save_trend_settings(data_dir: Path, values: dict[str, float]) -> None:
    save_section(data_dir, "trends", values)


def save_section(data_dir: Path, section: str, values: dict[str, Any]) -> None:
    """Skriv ét afsnit i filen; resten bevares. Atomisk (midlertidig fil + omdøbning), så en strømafbrydelse ikke giver en halv fil."""
    path = _settings_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(doc, dict):
                doc = {}
        except (OSError, ValueError):
            doc = {}
        doc[section] = values   # de øvrige afsnit i filen bevares
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        os.replace(tmp, path)


# ---------------------------------------------------------------- placering af trend-databasen
# Kun montérbare diske (USB-SSD) under /mnt eller /media er tilladt: servicen må kun skrive dér (se deploy/*.service), og et
# vilkårligt sted i filsystemet ville kunne ramme systemfiler. Mappen skal ejes af brugeren 'scada' (oprettes én gang som root).
TREND_DIR_ROOTS = (Path("/mnt"), Path("/media"))
TREND_DB_NAME = "trends.db"


def load_trend_dir(data_dir: Path) -> str:
    """Den gemte placering ('' = datamappen)."""
    try:
        raw = json.loads(_settings_path(data_dir).read_text(encoding="utf-8"))
        v = raw.get("storage", {}).get("trend_dir") if isinstance(raw, dict) else None
        return v if isinstance(v, str) else ""
    except (OSError, ValueError, AttributeError):
        return ""


def _writable(directory: Path) -> bool:
    probe = directory / f".skriv-test-{os.getpid()}"
    try:
        probe.write_bytes(b"x")
        probe.unlink()
        return True
    except OSError:
        return False


def resolve_trend_db_path(data_dir: Path) -> tuple[Path, str]:
    """Opstart: hvor ligger databasen? Er den gemte disk ikke til stede/skrivbar, bruges datamappen (tom historik) og
    der returneres en advarsel — SCADA'en starter altid; historikken på den manglende disk er urørt."""
    configured = load_trend_dir(data_dir)
    if not configured:
        return data_dir / TREND_DB_NAME, ""
    target = Path(configured)
    if target.is_dir() and _writable(target):
        return target / TREND_DB_NAME, ""
    log.error("Trend-databasens placering %s mangler eller er ikke skrivbar — bruger datamappen", configured)
    return data_dir / TREND_DB_NAME, (f"Trend-databasens disk ({configured}) mangler eller er ikke skrivbar — historikken er "
                                       f"urørt dér, men der bruges midlertidigt en tom database i datamappen")


def validate_trend_dir(raw: Any, data_dir: Path, current_db: Path, roots: tuple[Path, ...] = TREND_DIR_ROOTS,
                       require_other_device: bool = True) -> Path:
    """Kontrollér en ny placering og returnér målfilen. Afviser med en specifik besked (400). '' = tilbage til datamappen."""
    if not isinstance(raw, str):
        raise ServiceError(400, "Mappe: skriv en sti, fx /mnt/ssd/scada")
    text = raw.strip()
    if "\x00" in text:
        raise ServiceError(400, "Mappe: ugyldig sti")
    if text == "":
        directory = data_dir
    else:
        if not Path(text).is_absolute():
            raise ServiceError(400, "Mappe: skriv en fuld sti, der starter med /  (fx /mnt/ssd/scada)")
        directory = Path(text).resolve()
        if not any(directory == r or r in directory.parents for r in (p.resolve() for p in roots)):
            raise ServiceError(400, "Mappe: skal ligge under /mnt eller /media (monteringspunkt for en USB-disk)")
    if not directory.is_dir():
        raise ServiceError(400, f"Mappe: {directory} findes ikke — monter disken og opret mappen først")
    if not _writable(directory):
        raise ServiceError(400, f"Mappe: {directory} er ikke skrivbar for SCADA-tjenesten. Kør én gang på maskinen: "
                                f"sudo install -d -o scada -g scada -m 0750 {directory}")
    target = directory / TREND_DB_NAME
    if target.resolve() == current_db.resolve():
        raise ServiceError(400, "Mappe: databasen ligger allerede dér")
    if target.exists():
        raise ServiceError(409, f"Mappe: der ligger allerede en {TREND_DB_NAME} i {directory} — omdøb eller fjern den først")
    if text and require_other_device and directory.stat().st_dev == current_db.parent.stat().st_dev:
        raise ServiceError(400, "Mappe: ligger på samme disk som den nuværende database — vælg en anden disk (USB-SSD)")
    needed = int(sum(p.stat().st_size for p in (current_db, Path(str(current_db) + "-wal")) if p.exists()) * 1.3) + 50 * 1024 * 1024
    free = shutil.disk_usage(directory).free
    if free < needed:
        raise ServiceError(400, f"Mappe: for lidt ledig plads ({free // 1024 // 1024} MB; der skal bruges ca. {needed // 1024 // 1024} MB)")
    return target
