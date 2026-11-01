"""Systemhelbred (lag 3): hvordan har SCADA selv og PLC'erne det? Grundlag for System › Status, og senere /metrics.

Rene funktioner til vurderingen (`assess`), så grænserne kan testes uden en kørende server; `HealthService` holder de
løbende målinger (event-loop-lag, WebSocket-klienter) og samler et samlet billede af `app.state`.
Må ikke tale med PLC'er — kun læse, hvad runtimes allerede ved.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import sqlite3
import time
from collections import deque
from pathlib import Path
from typing import Any

from ..config import read_version

log = logging.getLogger(__name__)

LEVELS = ("ok", "warn", "error")

# Grænser for gul/rød. Samlet ét sted, så de er lette at finde og ændre.
LAG_WARN_S, LAG_ERROR_S = 0.25, 1.0          # event-loop-lag (maks. seneste minut)
DISK_WARN_FRAC, DISK_ERROR_FRAC = 0.10, 0.05
DISK_WARN_BYTES, DISK_ERROR_BYTES = 1_000_000_000, 200_000_000
MEM_WARN_FRAC = 0.10
TEMP_WARN_C, TEMP_ERROR_C = 75.0, 85.0
BACKUP_WARN_FACTOR = 1.5                      # ældre end 1,5 × backup-intervallet
DB_WARN_S = 0.2
THROTTLE_RECENT_S = 300.0

# Raspberry Pi `get_throttled`: bit 0 undervoltage, 1 frekvens begrænset, 2 throttlet, 3 blød temperaturgrænse;
# bit 16-19 er det samme "har været" siden opstart.
THROTTLE_NOW = {0: "undervoltage", 1: "frekvensen er begrænset", 2: "throttlet", 3: "blød temperaturgrænse"}
THROTTLE_PAST = {16: "undervoltage", 17: "frekvensen har været begrænset", 18: "har været throttlet",
                 19: "har ramt blød temperaturgrænse"}


def decode_throttled(value: int | None) -> dict[str, list[str]] | None:
    if value is None:
        return None
    return {"now": [t for b, t in THROTTLE_NOW.items() if value >> b & 1],
            "past": [t for b, t in THROTTLE_PAST.items() if value >> b & 1]}


def read_host() -> dict[str, Any]:
    """Hukommelse, belastning, CPU-temperatur og Pi-throttling. Det der ikke findes (fx på Windows) er None."""
    host: dict[str, Any] = {"mem_total": None, "mem_available": None, "load": None, "cpu_temp_c": None, "throttled": None}
    try:
        info: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            if key in ("MemTotal", "MemAvailable"):
                info[key] = int(rest.split()[0]) * 1024
        host["mem_total"], host["mem_available"] = info.get("MemTotal"), info.get("MemAvailable")
    except (OSError, ValueError):
        pass
    try:
        host["load"] = [float(x) for x in Path("/proc/loadavg").read_text().split()[:3]]
    except (OSError, ValueError):
        pass
    try:
        host["cpu_temp_c"] = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()) / 1000.0
    except (OSError, ValueError):
        pass
    try:
        raw = Path("/sys/devices/platform/soc/soc:firmware/get_throttled").read_text().strip()
        host["throttled"] = decode_throttled(int(raw, 16))
    except (OSError, ValueError):
        pass
    return host


def _problem(level: str, area: str, message: str) -> dict[str, str]:
    return {"level": level, "area": area, "message": message}


def assess(d: dict[str, Any]) -> dict[str, Any]:
    """Ud fra målingerne: samlet niveau (ok/warn/error) og en liste af problemer med dansk tekst."""
    problems: list[dict[str, str]] = []
    now = d.get("now", time.time())

    for plc in d.get("plcs", []):
        name = plc["name"]
        if not plc["enabled"]:
            continue
        if plc["state"] == "error":
            problems.append(_problem("error", "plc", f"PLC {name}: kommunikation tabt — {plc['message']}"))
        elif plc["state"] == "stopped" and plc.get("attention"):
            problems.append(_problem("error", "plc", f"PLC {name}: ikke startet — {plc['message']}"))
        else:
            for p in plc.get("partial") or []:
                problems.append(_problem("warn", "plc", f"PLC {name}: {p['what']} svarer ikke ({p['tags']} tag) — {p['message']}"))
            lt = plc.get("last_throttled")
            if lt is not None and now - lt < THROTTLE_RECENT_S:
                problems.append(_problem("warn", "plc", f"PLC {name}: har bedt om færre kald (rate-limit) for nylig"))

    lag = d.get("loop", {}).get("lag_max_s")
    if lag is not None:
        if lag >= LAG_ERROR_S:
            problems.append(_problem("error", "server", f"Serveren var optaget i {lag:.1f} s uden at svare (event-loop-lag)"))
        elif lag >= LAG_WARN_S:
            problems.append(_problem("warn", "server", f"Serveren var kortvarigt optaget ({lag * 1000:.0f} ms event-loop-lag)"))

    db_s = d.get("db", {}).get("latency_s")
    if d.get("db", {}).get("ok") is False:
        problems.append(_problem("error", "database", f"Databasen svarer ikke: {d['db'].get('error', '')}"))
    elif db_s is not None and db_s >= DB_WARN_S:
        problems.append(_problem("warn", "database", f"Databasen er langsom ({db_s * 1000:.0f} ms)"))

    disk = d.get("disk")
    if disk:
        frac = disk["free"] / disk["total"] if disk["total"] else 1.0
        free_gb = disk["free"] / 1e9
        if frac < DISK_ERROR_FRAC or disk["free"] < DISK_ERROR_BYTES:
            problems.append(_problem("error", "disk", f"Næsten fuld disk: {free_gb:.2f} GB ledig ({frac * 100:.0f} %)"))
        elif frac < DISK_WARN_FRAC or disk["free"] < DISK_WARN_BYTES:
            problems.append(_problem("warn", "disk", f"Lav ledig plads: {free_gb:.2f} GB ({frac * 100:.0f} %)"))

    host = d.get("host", {})
    if host.get("mem_total") and host.get("mem_available") is not None:
        if host["mem_available"] / host["mem_total"] < MEM_WARN_FRAC:
            problems.append(_problem("warn", "host", f"Lidt hukommelse tilbage ({host['mem_available'] / 1e6:.0f} MB ledig)"))
    temp = host.get("cpu_temp_c")
    if temp is not None:
        if temp >= TEMP_ERROR_C:
            problems.append(_problem("error", "host", f"CPU'en er meget varm ({temp:.0f} °C)"))
        elif temp >= TEMP_WARN_C:
            problems.append(_problem("warn", "host", f"CPU'en er varm ({temp:.0f} °C)"))
    thr = host.get("throttled")
    if thr:
        if thr["now"]:
            problems.append(_problem("error", "host", "Strøm/varme lige nu: " + ", ".join(thr["now"])))
        elif thr["past"]:
            problems.append(_problem("warn", "host", "Siden opstart: " + ", ".join(thr["past"])))

    backup = d.get("backup", {})
    interval_h = backup.get("interval_h") or 0
    if interval_h > 0:
        age = backup.get("last_age_s")
        if age is None:
            problems.append(_problem("warn", "backup", "Der er endnu ikke taget nogen automatisk backup"))
        elif age > interval_h * 3600 * BACKUP_WARN_FACTOR:
            problems.append(_problem("warn", "backup", f"Seneste backup er {age / 3600:.0f} timer gammel"))

    level = "ok"
    for p in problems:
        if LEVELS.index(p["level"]) > LEVELS.index(level):
            level = p["level"]
    problems.sort(key=lambda p: -LEVELS.index(p["level"]))
    return {"level": level, "problems": problems}


class HealthService:
    def __init__(self) -> None:
        self.started = time.time()
        self.ws_clients = 0
        self._lag: deque[tuple[float, float]] = deque(maxlen=240)   # (tid, lag i s) — ca. 2 min ved 0,5 s
        self.lag_last = 0.0

    # ------------------------------------------------------------- løbende målinger

    async def run_lag_probe(self, interval: float = 0.5) -> None:
        """Måler hvor meget en simpel `sleep` overskrider sin tid: det er tiden event-loopet var optaget af andet."""
        last = time.monotonic()
        while True:
            await asyncio.sleep(interval)
            now = time.monotonic()
            self.record_lag(max(0.0, now - last - interval), now)
            last = now

    def record_lag(self, lag: float, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self.lag_last = lag
        self._lag.append((now, lag))

    def lag_max(self, window_s: float = 60.0, now: float | None = None) -> float | None:
        now = time.monotonic() if now is None else now
        values = [lag for t, lag in self._lag if now - t <= window_s]
        return max(values) if values else None

    # ------------------------------------------------------------- samlet billede

    def details(self, state: Any) -> dict[str, Any]:
        """Alt til System › Status. `state` er `app.state`. Kun læsning."""
        settings = state.settings
        now = time.time()
        plcs = []
        for plc in state.manager.db.list_plcs():
            st = state.manager.status(plc["key"])
            last_ok = st.get("last_ok")
            plcs.append({
                "key": plc["key"], "name": plc["name"], "enabled": bool(plc["enabled"]),
                "state": st["state"], "message": st["message"], "attention": bool(st.get("attention")),
                "last_ok_age_s": round(now - last_ok, 1) if last_ok else None,
                "request_rate": st.get("request_rate"), "requests_per_cycle": st.get("requests_per_cycle"),
                "throttled": st.get("throttled", 0), "last_throttled": st.get("last_throttled"),
                "partial": st.get("partial") or [], "cycles": st.get("cycles"), "errors": st.get("errors"),
                "sse": (st.get("sse") or {}).get("state"),
            })
        alarms = state.alarm_service.summary(None)
        data: dict[str, Any] = {
            "now": now, "started": self.started, "uptime_s": round(now - self.started),
            "version": read_version(), "plcs": plcs,
            "loop": {"lag_last_s": round(self.lag_last, 4), "lag_max_s": self.lag_max()},
            "ws_clients": self.ws_clients, "alarms": alarms,
            "db": self._db_probe(state.manager.db),
            "disk": self._disk(settings.data_dir), "host": read_host(),
            "trends": self._trends(state),
            "backup": self._backup(state),
        }
        data.update(assess(data))
        return data

    @staticmethod
    def _db_probe(db: Any) -> dict[str, Any]:
        t0 = time.monotonic()
        try:
            db._query("SELECT 1")
        except (sqlite3.Error, OSError) as exc:
            log.warning("Databasetjek fejlede: %s", exc)
            return {"ok": False, "error": str(exc), "latency_s": None}
        return {"ok": True, "latency_s": round(time.monotonic() - t0, 4)}

    @staticmethod
    def _disk(data_dir: Path) -> dict[str, int] | None:
        try:
            du = shutil.disk_usage(data_dir)
        except OSError:
            return None
        return {"total": du.total, "used": du.used, "free": du.free}

    @staticmethod
    def _trends(state: Any) -> dict[str, Any]:
        rec = state.trend_recorder.write_stats()
        try:
            size = state.trend_db.path.stat().st_size
        except OSError:
            size = None
        return {"db_bytes": size, "rows": rec["rows"], "flushes": rec["flushes"], "rows_per_day": rec["rows_per_day"]}

    @staticmethod
    def _backup(state: Any) -> dict[str, Any]:
        autos = [b for b in state.backup_service.list_server_backups() if b["kind"] == "auto"]
        newest = max((b["created"] for b in autos), default=None)
        return {"interval_h": state.settings.backup_hours, "count": len(autos),
                "last_age_s": round(time.time() - newest) if newest else None}
