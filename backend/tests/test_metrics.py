"""Prometheus: tekstformatet, scrape-tokenet (kun Bearer; skriv-kun, kun kontrolsum gemt) og at intet følsomt lækker."""

import re
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.metrics import render

ADMIN_PW = "test-admin-pw-1"
TOKEN = "scrape-token-lang-og-tilfaeldig-123"


def _details(**kw):
    base = {"version": {"version": "3.16.0", "build": "0310"}, "uptime_s": 120, "level": "warn",
            "problems": [{"level": "warn", "area": "plc", "message": "x"}],
            "loop": {"lag_last_s": 0.001, "lag_max_s": 0.05}, "db": {"ok": True, "latency_s": 0.0004},
            "ws_clients": 2, "alarms": {"active": 3, "unacked": 1, "high": 0},
            "plcs": [{"key": 'pl"c1', "enabled": True, "state": "ok", "partial": [{"what": "a"}], "last_ok_age_s": 0.5,
                      "request_rate": 2.5, "request_count": 100, "throttled": 0, "cycles": 10, "errors": 1},
                     {"key": "off", "enabled": False, "state": "stopped"}],
            "trends": {"rows": 5, "flushes": 1, "db_bytes": 1000}, "backup": {"last_age_s": None, "count": 0},
            "disk": {"free": 5, "total": 10},
            "host": {"mem_available": 1, "mem_total": 2, "load": [0.5, 0.4, 0.3], "cpu_temp_c": 0.0, "throttled": None}}
    base.update(kw)
    return base


def test_render_format():
    text = render(_details(), auth_failures=4)
    assert text.endswith("\n")
    assert 'scada_build_info{version="3.16.0",build="0310"} 1' in text
    assert "# TYPE scada_plc_requests_total counter" in text and "# HELP scada_up " in text
    assert 'scada_plc_up{plc="pl\\"c1"} 1' in text                 # label-escape af "
    assert 'scada_plc_partial_failures{plc="pl\\"c1"} 1' in text
    assert 'plc="off"' not in text                                   # deaktiverede PLC'er udelades
    assert "scada_host_cpu_temp_celsius 0.0" in text                 # 0 er en gyldig værdi
    assert "scada_host_throttled" not in text                        # ikke en Pi → udeladt, ikke "None"
    assert "scada_last_backup_age_seconds" not in text               # ingen backup endnu → udeladt
    assert "scada_health_level 1" in text and 'scada_health_problems{level="warn"} 1' in text
    assert "scada_metrics_auth_failures_total 4" in text
    assert "None" not in text and "nan" not in text.lower()
    # hver linje er enten kommentar eller `navn{labels} tal`
    pat = re.compile(r'^(# (HELP|TYPE) \S+ .+|[a-z_0-9]+(\{[^}]*\})? -?\d+(\.\d+)?(e-?\d+)?)$')
    for line in text.strip().split("\n"):
        assert pat.match(line), line


def test_render_drops_nan_and_inf():
    text = render(_details(loop={"lag_last_s": float("nan"), "lag_max_s": float("inf")}))
    assert "scada_event_loop_lag" not in text


# ------------------------------------------------------------- via API

@pytest.fixture
def api(tmp_path, mock_plc):
    s = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9, frontend_dir=tmp_path / "nope",
                 admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        c.tmp = tmp_path
        yield c


def _anon(api):
    return TestClient(api.app)


def test_disabled_until_token_set(api):
    r = _anon(api).get("/metrics")
    assert r.status_code == 404 and "ikke slået til" in r.json()["error"]
    assert api.get("/api/system/metrics").json()["enabled"] is False


def test_token_flow_and_secrecy(api):
    assert api.put("/api/system/metrics", json={"token": "for-kort"}).status_code == 422
    r = api.put("/api/system/metrics", json={"token": TOKEN})
    assert r.status_code == 200 and r.json() == {"enabled": True} and TOKEN not in r.text
    assert TOKEN not in api.get("/api/system/metrics").text
    secrets_file = (api.tmp / "secrets.json").read_text(encoding="utf-8")
    assert TOKEN not in secrets_file and "token_sha256" in secrets_file        # kun kontrolsum på disk
    audit = api.get("/api/audit?limit=50").text
    assert "system.metrics.token" in audit and TOKEN not in audit

    anon = _anon(api)
    time.sleep(0.5)
    for headers in ({}, {"Authorization": "Bearer forkert-token-forkert-token"}, {"Authorization": f"Basic {TOKEN}"}):
        r = anon.get("/metrics", headers=headers)
        assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer", headers
    assert anon.get(f"/metrics?token={TOKEN}").status_code == 401              # ikke via URL (havner i logs)
    assert api.get("/metrics").status_code == 401                              # en admin-session alene giver ikke adgang

    r = anon.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain; version=0.0.4")
    body = r.text
    assert 'scada_plc_up{plc="plc1"}' in body and "scada_event_loop_lag_max_seconds" in body
    assert "scada_metrics_auth_failures_total 5" in body                       # de fem afviste forsøg tælles
    # intet følsomt: ingen adgangskoder, tokenværdi, brugernavne eller tag-/tegningsnavne
    for secret in (TOKEN, "scada123", ADMIN_PW, "admin"):
        assert secret not in body


def test_token_endpoints_admin_only_and_removal(api):
    api.put("/api/system/metrics", json={"token": TOKEN})
    api.post("/api/users", json={"username": "tek", "role": "engineer", "password": "Hemmelig-kode-12345"})
    eng = TestClient(api.app)
    eng.post("/api/auth/login", json={"username": "tek", "password": "Hemmelig-kode-12345"})
    eng.post("/api/auth/password", json={"old_password": "Hemmelig-kode-12345", "new_password": "Nyt-hemmeligt-kode-9876"})
    assert eng.get("/api/system/metrics").status_code == 403
    assert eng.put("/api/system/metrics", json={"token": "x" * 30}).status_code == 403
    assert eng.delete("/api/system/metrics").status_code == 403
    assert api.delete("/api/system/metrics").json() == {"enabled": False}
    assert _anon(api).get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 404   # slået fra igen


def test_token_must_be_url_safe(api):
    for bad in ("med mellemrum i tokenet 1234567", "aeoe-æøå-ikke-ascii-tegn-123456", "linje\nskift-1234567890123456"):
        assert api.put("/api/system/metrics", json={"token": bad}).status_code == 422, bad
    assert api.put("/api/system/metrics", json={"token": "Ab-_.~09" * 4}).status_code == 200


def test_failure_log_table_is_bounded(api):
    import app.api.metrics as m
    api.put("/api/system/metrics", json={"token": TOKEN})
    st = api.app.state
    st.metrics_last_log = {f"10.0.{i // 250}.{i % 250}": time.monotonic() - 3600 for i in range(m._MAX_LOG_IPS + 5)}
    _anon(api).get("/metrics", headers={"Authorization": "Bearer forkert-token-forkert-token"})
    assert len(st.metrics_last_log) < 10        # gamle poster ryddet; kun den nye er tilbage
