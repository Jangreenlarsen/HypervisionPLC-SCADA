"""Systemhelbred (lag 3): hvordan har SCADA selv og PLC'erne det? Grundlag for System › Status, og senere /metrics.

Rene funktioner til vurderingen (`assess`), så grænserne kan testes uden en kørende server; `HealthService` holder de
løbende målinger (event-loop-lag, WebSocket-klienter) og samler et samlet billede af `app.state`.
Må ikke tale med PLC'er — kun læse, hvad runtimes allerede ved.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import sqlite3
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backup_targets import expected_interval_h
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
BACKUP_GRACE_S = 600.0                        # første automatiske backup tages 5 min efter start (backup.py)
CERT_WARN_DAYS, CERT_ERROR_DAYS = 21, 7   # certifikatets levetid (Let's Encrypt fornyes ved 30 dage; gul/rød er en fornyelse, der er stoppet)

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


POWER_FRESH_S = 300.0   # <state>/power.json (deploy/power-info.sh, hvert 30. s) ældre end dette er ukendt, ikke "i orden"


def read_throttled(state_dir: Path | None, now: float | None = None) -> dict[str, list[str]] | None:
    """Pi-strømstatus: først root-hjælperens fil <state>/power.json (tjenesten må ikke åbne /dev/vcio), ellers kernens sysfs-sti (findes ikke
    på alle kerner). None = ukendt (ikke en Pi, eller filen er for gammel/ugyldig)."""
    now = time.time() if now is None else now
    if state_dir is not None:
        try:
            raw = json.loads((state_dir / "power.json").read_text(encoding="utf-8"))
            if now - float(raw["ts"]) <= POWER_FRESH_S:
                return decode_throttled(int(raw["throttled"]))
        except (OSError, ValueError, KeyError, TypeError):
            pass
    try:
        return decode_throttled(int(Path("/sys/devices/platform/soc/soc:firmware/get_throttled").read_text().strip(), 16))
    except (OSError, ValueError):
        return None


def read_host(state_dir: Path | None = None) -> dict[str, Any]:
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
    host["throttled"] = read_throttled(state_dir)
    return host


def read_tls(state_dir: Path, now: float | None = None) -> dict[str, Any] | None:
    """Metadata om det certifikat nginx bruger (skrevet af deploy/cert-deploy.sh til <state>/cert.json). Dage tilbage regnes her,
    så tallet er rigtigt, selv om filen er gammel. None hvis der ikke er en fil (ingen nginx/TLS) eller den ikke kan læses."""
    try:
        raw = json.loads((state_dir / "cert.json").read_text(encoding="utf-8"))
        expires = datetime.strptime(str(raw["not_after"]), "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc).timestamp()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    now = time.time() if now is None else now
    return {"issuer": raw.get("issuer", ""), "subject": raw.get("subject", ""), "self_signed": bool(raw.get("self_signed")),
            "fingerprint": raw.get("fingerprint", ""), "not_after_ts": expires, "days_left": int((expires - now) // 86400)}


def _problem(level: str, area: str, message: str, code: str | None = None) -> dict[str, str]:
    """`code` identificerer problemet (bruges som alarmnøgle `sys:<code>`); standard = området."""
    return {"level": level, "area": area, "message": message, "code": code or area}


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
            problems.append(_problem("error", "server", f"Serveren var optaget i {lag:.1f} s uden at svare (event-loop-lag)", "loop_lag"))
        elif lag >= LAG_WARN_S:
            problems.append(_problem("warn", "server", f"Serveren var kortvarigt optaget ({lag * 1000:.0f} ms event-loop-lag)", "loop_lag"))

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
            problems.append(_problem("warn", "host", f"Lidt hukommelse tilbage ({host['mem_available'] / 1e6:.0f} MB ledig)", "mem"))
    temp = host.get("cpu_temp_c")
    if temp is not None:
        if temp >= TEMP_ERROR_C:
            problems.append(_problem("error", "host", f"CPU'en er meget varm ({temp:.0f} °C)", "temp"))
        elif temp >= TEMP_WARN_C:
            problems.append(_problem("warn", "host", f"CPU'en er varm ({temp:.0f} °C)", "temp"))
    thr = host.get("throttled")
    if thr:
        if thr["now"]:
            problems.append(_problem("error", "host", "Strøm/varme lige nu: " + ", ".join(thr["now"]), "power"))
        elif thr["past"]:
            problems.append(_problem("warn", "host", "Siden opstart: " + ", ".join(thr["past"]), "power_past"))

    tls = d.get("tls")
    if tls:
        days = tls["days_left"]
        who = "Selvsigneret certifikat" if tls["self_signed"] else "Certifikatet"
        if days < 0:
            problems.append(_problem("error", "tls", f"{who} er udløbet (browsere afviser siden)"))
        elif days < CERT_WARN_DAYS:
            level = "error" if days < CERT_ERROR_DAYS else "warn"
            hint = "" if tls["self_signed"] else " — tjek fornyelsen: hypervision-letsencrypt status"
            problems.append(_problem(level, "tls", f"{who} udløber om {days} dage{hint}"))

    for channel, error in (d.get("notify") or {}).items():
        label = {"webhook": "webhook", "email": "e-mail"}.get(channel, channel)
        problems.append(_problem("warn", "notify", f"Notifikation via {label} kan ikke sendes: {error}", f"notify_{channel}"))

    for name, error in (d.get("backup_failing") or {}).items():
        problems.append(_problem("warn", "backup", f"Backup til '{name}' fejler: {error}", f"backup_target_{name}"))

    backup = d.get("backup", {})
    interval_h = backup.get("interval_h") or 0
    if interval_h > 0:
        age = backup.get("last_age_s")
        if age is None:
            # den første automatiske backup tages først nogle minutter efter start — ingen advarsel før da (falsk alarm)
            if d.get("uptime_s", 0) >= BACKUP_GRACE_S:
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
        values = [lag for t, lag in list(self._lag) if now - t <= window_s]
        return max(values) if values else None

    # ------------------------------------------------------------- samlet billede

    async def details(self, state: Any, lag_window_s: float = 60.0) -> dict[str, Any]:
        """Alt til System › Status og /metrics. `state` er `app.state`. Kun læsning.

        Det der ændres af event-loopet (PLC-status, alarmer, lag-målinger, tællere) læses HER på loopet; kun det
        blokerende (database, disk, filer, glob) køres i en tråd — så ingen datastruktur itereres, mens den ændres."""
        fast = self._loop_part(state, lag_window_s)
        slow = await asyncio.to_thread(self._thread_part, state)
        data = {**fast, **slow}
        data.update(assess(data))
        return data

    def _loop_part(self, state: Any, lag_window_s: float) -> dict[str, Any]:
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
                "request_count": st.get("request_count"), "throttled": st.get("throttled", 0), "last_throttled": st.get("last_throttled"),
                "partial": st.get("partial") or [], "cycles": st.get("cycles"), "errors": st.get("errors"),
                "sse": (st.get("sse") or {}).get("state"),
            })
        return {
            "now": now, "started": self.started, "uptime_s": round(now - self.started),
            "version": read_version(), "plcs": plcs,
            "loop": {"lag_last_s": round(self.lag_last, 4), "lag_max_s": self.lag_max(lag_window_s)},
            "ws_clients": self.ws_clients, "alarms": state.alarm_service.summary(None),
            "trends": self._trends(state),
            "integration": (svc.metrics() if (svc := getattr(state, "integration_service", None)) else None),
            "backup_targets": bs.metrics() if (bs := getattr(state, "backup_scheduler", None)) else None,
            "backup_failing": bs.failing() if bs else {},
            "tls_admin": ta.metrics() if (ta := getattr(state, "tls_admin", None)) else None,
            "assist": a.metrics() if (a := getattr(state, "assistant", None)) else None,
            "bindings_cache": dict(ds.cache_stats) if (ds := getattr(state, "drawing_service", None)) else None,
            # signalveje (v5.0.0): antal veje i drift, aktive/ukendte kombinationer af grene og beregningsfejl i seneste tick
            "signal_paths": dict(rt.path_stats) if (rt := getattr(state, "symbol_runtime", None)) else None,
            # opgraderingen v5.1.0 (den gamle symbolmodel fjernet): symboler, der stadig skal sættes op i guiden
            "symbol_migration": self._symbol_migration(state),
            "notify": notifier.failing() if (notifier := getattr(state, "notifier", None)) else {},
            "notifications": ({"sent": notifier.sent, "failed": notifier.failed, "dropped": notifier.dropped, "queued": len(notifier.pending)}
                              if notifier else None),
        }

    @staticmethod
    def _symbol_migration(state: Any) -> dict[str, int] | None:
        from .migrations import v51_symbols
        svc = getattr(state, "symbol_service", None)
        if svc is None:
            return None
        if v51_symbols.pending(svc.db):
            return {"pending": 1}          # opgraderingen er ikke kørt (fx backuppen fejlede) — prøves ved næste opstart
        rep = v51_symbols.report(svc.db)
        return {"converted": len(rep.get("converted", [])), "manual": len(rep.get("manual", []))} if rep else None

    def _thread_part(self, state: Any) -> dict[str, Any]:
        """Blokerende opslag (kører i en tråd)."""
        return {
            "db": self._db_probe(state.manager.db),
            "disk": self._disk(state.settings.data_dir), "host": read_host(state.settings.net_state_dir),
            "backup": self._backup(state),
            "tls": read_tls(state.settings.net_state_dir),
        }

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
        sched = getattr(state, "backup_scheduler", None)
        interval_h = expected_interval_h(sched.schedule()) if sched else state.settings.backup_hours
        return {"interval_h": interval_h, "count": len(autos),
                "last_age_s": round(time.time() - newest) if newest else None}
