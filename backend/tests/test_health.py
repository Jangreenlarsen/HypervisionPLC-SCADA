"""Systemhelbred: vurderingen (grænser), målingerne og endpointet /api/health/details."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.health import HealthService, assess, decode_throttled

ADMIN_PW = "test-admin-pw-1"
NOW = 1_000_000.0


def _data(**kw):
    base = {"now": NOW, "plcs": [], "loop": {"lag_max_s": 0.01}, "db": {"ok": True, "latency_s": 0.001},
            "disk": {"total": 100_000_000_000, "used": 10_000_000_000, "free": 90_000_000_000},
            "host": {"mem_total": 4e9, "mem_available": 2e9, "cpu_temp_c": 50.0, "throttled": None},
            "backup": {"interval_h": 24, "last_age_s": 3600}}
    base.update(kw)
    return base


def _plc(**kw):
    base = {"name": "Kedel", "enabled": True, "state": "ok", "message": "", "partial": [], "attention": False,
            "last_throttled": None}
    base.update(kw)
    return base


def _msgs(r):
    return [(p["level"], p["area"]) for p in r["problems"]]


def test_healthy_is_ok():
    r = assess(_data(plcs=[_plc()]))
    assert r == {"level": "ok", "problems": []}


@pytest.mark.parametrize("plc, expected", [
    (_plc(state="error", message="nede"), ("error", "plc")),
    (_plc(state="stopped", attention=True, message="Ingen adgangskode"), ("error", "plc")),
    (_plc(partial=[{"what": "hr 0–9", "tags": 2, "message": "x"}]), ("warn", "plc")),
    (_plc(last_throttled=NOW - 10), ("warn", "plc")),
])
def test_plc_problems(plc, expected):
    assert expected in _msgs(assess(_data(plcs=[plc])))


def test_old_throttle_and_disabled_plc_are_ignored():
    assert assess(_data(plcs=[_plc(last_throttled=NOW - 3600)]))["level"] == "ok"
    assert assess(_data(plcs=[_plc(enabled=False, state="error", message="x")]))["level"] == "ok"
    assert assess(_data(plcs=[_plc(state="stopped", attention=False)]))["level"] == "ok"   # bevidst ikke startet


@pytest.mark.parametrize("patch, level", [
    ({"loop": {"lag_max_s": 0.3}}, "warn"), ({"loop": {"lag_max_s": 1.5}}, "error"), ({"loop": {"lag_max_s": None}}, "ok"),
    ({"disk": {"total": 100e9, "used": 92e9, "free": 8e9}}, "warn"),
    ({"disk": {"total": 100e9, "used": 97e9, "free": 3e9}}, "error"),
    ({"disk": {"total": 8e9, "used": 7.5e9, "free": 0.1e9}}, "error"),
    ({"disk": None}, "ok"),
    ({"db": {"ok": False, "error": "låst"}}, "error"), ({"db": {"ok": True, "latency_s": 0.5}}, "warn"),
    ({"host": {"cpu_temp_c": 80.0}}, "warn"), ({"host": {"cpu_temp_c": 90.0}}, "error"),
    ({"host": {"mem_total": 4e9, "mem_available": 1e8}}, "warn"),
    ({"host": {"throttled": {"now": ["undervoltage"], "past": []}}}, "error"),
    ({"host": {"throttled": {"now": [], "past": ["undervoltage"]}}}, "warn"),
    ({"host": {"cpu_temp_c": 0.0}}, "ok"),     # 0 er en gyldig temperatur (is not None)
    ({"backup": {"interval_h": 24, "last_age_s": 40 * 3600}}, "warn"),
    ({"backup": {"interval_h": 24, "last_age_s": None}}, "warn"),
    ({"backup": {"interval_h": 0, "last_age_s": None}}, "ok"),   # automatisk backup slået fra
])
def test_thresholds(patch, level):
    assert assess(_data(**patch))["level"] == level


def test_worst_level_wins_and_errors_sort_first():
    r = assess(_data(plcs=[_plc(partial=[{"what": "a", "tags": 1, "message": "m"}], name="A"),
                           _plc(state="error", message="x", name="B")]))
    assert r["level"] == "error" and r["problems"][0]["level"] == "error"


def test_decode_throttled():
    assert decode_throttled(None) is None
    assert decode_throttled(0) == {"now": [], "past": []}
    assert decode_throttled(0x50005) == {"now": ["undervoltage", "throttlet"], "past": ["undervoltage", "har været throttlet"]}


def test_lag_window():
    h = HealthService()
    h.record_lag(0.4, now=100.0)
    h.record_lag(0.01, now=150.0)
    assert h.lag_max(60, now=155.0) == 0.4
    assert h.lag_max(60, now=170.0) == 0.01     # den gamle måling er ude af vinduet
    assert h.lag_max(60, now=400.0) is None


# ------------------------------------------------------------- via API

@pytest.fixture
def api(tmp_path, mock_plc):
    s = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9, frontend_dir=tmp_path / "nope",
                 admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        yield c


def test_details_shape_and_access(api, tmp_path):
    time.sleep(1.2)   # lad event-loop-sonden og pollingen køre lidt
    r = api.get("/api/health/details")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["level"] in ("ok", "warn", "error") and isinstance(d["problems"], list)
    assert d["version"]["version"] and d["uptime_s"] >= 0
    assert d["db"]["ok"] is True and d["disk"]["total"] > 0 and d["loop"]["lag_max_s"] is not None
    (plc,) = d["plcs"]
    assert plc["key"] == "plc1" and plc["state"] in ("ok", "connecting") and "partial" in plc
    assert set(d["alarms"]) == {"active", "unacked", "high"}
    assert "password" not in str(d).lower()           # ingen hemmeligheder i svaret
    # kun tekniker og over: en viewer afvises, og uden login 401
    admin_viewer = api.post("/api/users", json={"username": "visning", "role": "viewer", "password": "Hemmelig-kode-12345"})
    assert admin_viewer.status_code == 201
    with TestClient(api.app) as v:
        assert v.get("/api/health/details").status_code == 401
        pw = v.post("/api/auth/login", json={"username": "visning", "password": "Hemmelig-kode-12345"})
        assert pw.status_code == 200
        if pw.json().get("must_change_password"):
            v.post("/api/auth/password", json={"old_password": "Hemmelig-kode-12345", "new_password": "Nyt-hemmeligt-kode-9876"})
        assert v.get("/api/health/details").status_code == 403


def test_ws_client_counter(api):
    h = api.app.state.health_service
    assert h.ws_clients == 0
    with api.websocket_connect("/ws/live") as ws:
        ws.send_json({"type": "subscribe", "tags": []})
        ws.receive_json()
        assert h.ws_clients == 1
    time.sleep(0.3)
    assert h.ws_clients == 0
