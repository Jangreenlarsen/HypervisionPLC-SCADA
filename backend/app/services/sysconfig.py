"""System-konfiguration (kun læsning): hvor data ligger, hvor meget de fylder/skrives, og netværksstatus.

Læser kun — ændringer (netværk, flytning af datamappen) kommer i senere trin via en privilegeret hjælper (se PLAN.md).
Netværksstatus hentes med `ip -j` (iproute2, findes på Raspberry Pi OS); mangler det (fx under Windows-udvikling), meldes
`available: false` i stedet for en fejl.
"""

from __future__ import annotations

import json
import logging
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

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
