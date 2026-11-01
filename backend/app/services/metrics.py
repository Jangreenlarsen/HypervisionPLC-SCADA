"""Prometheus-eksponering (lag 3): `render()` laver tekstformatet (0.0.4) ud fra `HealthService.details()`.

Håndskrevet (ingen afhængighed). Indeholder KUN systemtal og PLC-nøgler som label — aldrig tag-værdier, tag- eller
tegningsnavne, brugere eller hemmeligheder. Adgang styres af `api/metrics.py` (scrape-token).
"""

from __future__ import annotations

import math
from typing import Any

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
LEVEL_VALUE = {"ok": 0, "warn": 1, "error": 2}


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _num(value: Any) -> str | None:
    """Tal → tekst; bool → 0/1; None/NaN/uendelig/ikke-tal → None (målingen udelades i stedet for at give ugyldig tekst)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return repr(value) if isinstance(value, float) else str(value)
    return None


class _Exposition:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def metric(self, name: str, kind: str, help_: str, samples: list[tuple[dict[str, str], Any]]) -> None:
        rows = []
        for labels, value in samples:
            text = _num(value)
            if text is None:
                continue
            label = "{" + ",".join(f'{k}="{_escape(str(v))}"' for k, v in labels.items()) + "}" if labels else ""
            rows.append(f"{name}{label} {text}")
        if not rows:
            return   # en måling uden værdier (fx CPU-temperatur på en VM) udelades helt
        self.lines += [f"# HELP {name} {help_}", f"# TYPE {name} {kind}", *rows]

    def gauge(self, name: str, help_: str, value: Any, labels: dict[str, str] | None = None) -> None:
        self.metric(name, "gauge", help_, [(labels or {}, value)])

    def counter(self, name: str, help_: str, value: Any, labels: dict[str, str] | None = None) -> None:
        self.metric(name, "counter", help_, [(labels or {}, value)])

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def render(d: dict[str, Any], auth_failures: int = 0) -> str:
    x = _Exposition()
    v = d.get("version", {})
    x.gauge("scada_build_info", "Installeret version (værdien er altid 1)", 1,
            {"version": str(v.get("version", "")), "build": str(v.get("build", ""))})
    x.gauge("scada_up", "SCADA-serveren svarer", 1)
    x.gauge("scada_uptime_seconds", "Sekunder siden serveren startede", d.get("uptime_s"))
    x.gauge("scada_health_level", "Samlet helbred: 0 ok, 1 opmærksomhed, 2 fejl", LEVEL_VALUE.get(d.get("level", "ok")))
    x.metric("scada_health_problems", "gauge", "Antal aktuelle problemer pr. niveau",
             [({"level": lv}, sum(1 for p in d.get("problems", []) if p["level"] == lv)) for lv in ("warn", "error")])

    loop = d.get("loop", {})
    x.gauge("scada_event_loop_lag_seconds", "Event-loop-lag lige nu (tid serveren var optaget uden at kunne svare)", loop.get("lag_last_s"))
    x.gauge("scada_event_loop_lag_max_seconds", "Største event-loop-lag seneste minut", loop.get("lag_max_s"))
    db = d.get("db", {})
    x.gauge("scada_db_up", "Databasen svarer", db.get("ok"))
    x.gauge("scada_db_latency_seconds", "Svartid for en simpel databaseforespørgsel", db.get("latency_s"))
    x.gauge("scada_ws_clients", "Åbne live-forbindelser (WebSocket)", d.get("ws_clients"))
    alarms = d.get("alarms", {})
    x.gauge("scada_alarms_active", "Aktive alarmer", alarms.get("active"))
    x.gauge("scada_alarms_unacked", "Ukvitterede alarmer", alarms.get("unacked"))
    x.gauge("scada_alarms_high", "Aktive alarmer med høj prioritet", alarms.get("high"))

    plcs = [p for p in d.get("plcs", []) if p.get("enabled")]
    per = lambda field: [({"plc": p["key"]}, p.get(field)) for p in plcs]  # noqa: E731
    x.metric("scada_plc_up", "gauge", "PLC'en svarer (1) eller er tabt/ikke startet (0)",
             [({"plc": p["key"]}, p["state"] == "ok") for p in plcs])
    x.metric("scada_plc_partial_failures", "gauge", "Antal kald/områder der fejler, mens PLC'en ellers svarer",
             [({"plc": p["key"]}, len(p.get("partial") or [])) for p in plcs])
    x.metric("scada_plc_last_ok_age_seconds", "gauge", "Sekunder siden PLC'en sidst svarede", per("last_ok_age_s"))
    x.metric("scada_plc_request_rate", "gauge", "Kald pr. sekund SCADA sender til PLC'en (seneste minut; loft 5)", per("request_rate"))
    x.metric("scada_plc_requests_total", "counter", "Kald sendt til PLC'en siden start", per("request_count"))
    x.metric("scada_plc_rate_limited_total", "counter", "Gange PLC'en har afvist kald (429) siden start", per("throttled"))
    x.metric("scada_plc_poll_cycles_total", "counter", "Gennemførte poll-runder siden start", per("cycles"))
    x.metric("scada_plc_poll_errors_total", "counter", "Poll-runder med fejl siden start", per("errors"))

    t = d.get("trends", {})
    x.counter("scada_trend_rows_written_total", "Trend-rækker skrevet siden start", t.get("rows"))
    x.counter("scada_trend_flushes_total", "Trend-skrivninger til disk siden start", t.get("flushes"))
    x.gauge("scada_trend_db_bytes", "Trend-databasens størrelse", t.get("db_bytes"))
    b = d.get("backup", {})
    x.gauge("scada_last_backup_age_seconds", "Sekunder siden seneste automatiske backup", b.get("last_age_s"))
    x.gauge("scada_backups_stored", "Gemte automatiske backups", b.get("count"))

    disk = d.get("disk") or {}
    x.gauge("scada_disk_free_bytes", "Ledig plads på datadisken", disk.get("free"))
    x.gauge("scada_disk_total_bytes", "Datadiskens størrelse", disk.get("total"))
    h = d.get("host", {})
    x.gauge("scada_host_mem_available_bytes", "Ledig hukommelse", h.get("mem_available"))
    x.gauge("scada_host_mem_total_bytes", "Hukommelse i alt", h.get("mem_total"))
    x.gauge("scada_host_load1", "Belastning (1 minut)", (h.get("load") or [None])[0])
    x.gauge("scada_host_cpu_temp_celsius", "CPU-temperatur", h.get("cpu_temp_c"))
    thr = h.get("throttled")
    x.gauge("scada_host_throttled", "Raspberry Pi er undervolted/throttlet lige nu", None if thr is None else bool(thr["now"]))
    x.gauge("scada_host_throttled_since_boot", "Raspberry Pi har været undervolted/throttlet siden opstart",
            None if thr is None else bool(thr["past"]))

    x.counter("scada_metrics_auth_failures_total", "Afviste forsøg på at hente /metrics (forkert eller manglende token)", auth_failures)
    return x.text()
