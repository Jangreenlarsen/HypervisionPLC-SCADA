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

    tls = d.get("tls") or {}
    x.gauge("scada_tls_cert_expiry_seconds", "Sekunder til nginx' certifikat udløber (negativ = udløbet)",
            None if "not_after_ts" not in tls else tls["not_after_ts"] - d.get("now", 0))
    x.gauge("scada_tls_cert_self_signed", "Certifikatet er selvsigneret (1) eller fra en udsteder (0)", tls.get("self_signed"))
    ig = d.get("integration") or {}
    x.gauge("scada_integration_keys", "Antal API-nøgler til integrationer", ig.get("keys"))
    pk = ig.get("per_key") or {}
    x.metric("scada_integration_requests_total", "counter", "Godkendte kald pr. API-nøgle siden start", [({"key": k}, v["requests"]) for k, v in pk.items()])
    x.metric("scada_integration_errors_total", "counter", "Kald med fejl (4xx) pr. API-nøgle", [({"key": k}, v["errors"]) for k, v in pk.items()])
    x.metric("scada_integration_rate_limited_total", "counter", "Kald afvist af hastighedsgrænsen pr. API-nøgle", [({"key": k}, v["rate_limited"]) for k, v in pk.items()])
    x.gauge("scada_integration_streams", "Åbne SSE-strømme til integrationer", ig.get("streams"))
    x.metric("scada_integration_stream_events_total", "counter", "Hændelser sendt på SSE-strømme pr. API-nøgle", [({"key": k}, v.get("stream_events")) for k, v in pk.items()])
    x.counter("scada_integration_auth_failures_total", "Afviste integrationskald (forkert/manglende/udløbet nøgle, forbudt IP)", ig.get("auth_failures"))
    n = d.get("notifications") or {}
    x.metric("scada_notifications_sent_total", "counter", "Afsendte notifikationer siden start pr. kanal",
             [({"channel": c}, v) for c, v in (n.get("sent") or {}).items()])
    x.metric("scada_notifications_failed_total", "counter", "Notifikationer der ikke kunne sendes (efter forsøg igen) pr. kanal",
             [({"channel": c}, v) for c, v in (n.get("failed") or {}).items()])
    x.counter("scada_notifications_dropped_total", "Notifikationer kasseret, fordi køen var fuld", n.get("dropped"))
    ta = d.get("tls_admin") or {}
    x.metric("scada_tls_operations_total", "counter", "Certifikat-handlinger fra System › Certifikater pr. handling og resultat",
             [({"action": k.split("|")[0], "result": k.split("|")[1]}, v) for k, v in (ta.get("ops") or {}).items()])
    bk = d.get("backup_targets") or {}
    x.metric("scada_backup_runs_total", "counter", "Backup-kørsler siden start pr. resultat (ok/partial/error)",
             [({"result": r}, v) for r, v in (bk.get("runs") or {}).items()])
    x.metric("scada_backup_upload_total", "counter", "Afsendelser til backup-destinationer pr. destination og resultat",
             [({"target": t, "result": r}, v) for t, rv in (bk.get("uploads") or {}).items() for r, v in rv.items()])
    x.metric("scada_backup_last_success_timestamp_seconds", "gauge", "Seneste vellykkede afsendelse pr. backup-destination (Unix-tid)",
             [({"target": t}, v) for t, v in (bk.get("last_success") or {}).items()])
    x.metric("scada_backup_target_failing", "gauge", "Backup-destinationen er fejlet flere gange i træk (1)",
             [({"target": t}, v) for t, v in (bk.get("failing") or {}).items()])
    asst = d.get("assist") or {}
    if asst:
        x.counter("scada_assist_asks_total", "Spørgsmål til LLM-hjælperen (hjælper-panelet) siden start", asst.get("asks"))
        x.counter("scada_assist_requests_total", "Kald til LLM-hjælperen siden start", asst.get("requests"))
        x.counter("scada_assist_errors_total", "Fejlede kald til LLM-hjælperen siden start", asst.get("errors"))
        x.gauge("scada_assist_busy", "LLM-hjælperen arbejder lige nu (1)", asst.get("busy"))
        x.gauge("scada_assist_waiting", "Kald der venter på LLM-hjælperen", asst.get("waiting"))
        x.gauge("scada_assist_last_seconds", "Svartid for seneste kald til LLM-hjælperen", (asst.get("last_ms") or 0) / 1000)
    x.gauge("scada_notification_queue", "Notifikationer der venter på at blive sendt", n.get("queued"))
    x.counter("scada_metrics_auth_failures_total", "Afviste forsøg på at hente /metrics (forkert eller manglende token)", auth_failures)
    return x.text()
