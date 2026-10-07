"""REST API'et med rigtig lifespan (DB + secrets + runtimes) mod mock-PLC'en."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9, frontend_dir=tmp_path / "nope")


@pytest.fixture
def api(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def _plc(mock_url, **kw):
    body = {"key": "plc1", "name": "Testanlæg", "base_url": mock_url, "username": "scada",
            "password": "scada123", "sse_enabled": False}
    body.update(kw)
    return body


def _wait(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


def test_health(api):
    body = api.get("/api/health").json()
    assert body["status"] == "ok" and "version" in body


def test_password_is_write_only(api, settings, mock_plc):
    r = api.post("/api/plcs", json=_plc(mock_plc.url))
    assert r.status_code == 201, r.text
    assert "password" not in r.json() and "scada123" not in r.text
    assert r.json()["has_password"] is True
    assert "scada123" not in api.get("/api/plcs").text
    assert json.loads(settings.secrets_path.read_text())["plc_passwords"]["plc1"] == "scada123"


def test_blank_password_and_url_rejected(api, mock_plc):
    for bad in ("", "   "):
        r = api.post("/api/plcs", json=_plc(mock_plc.url, password=bad))
        assert r.status_code == 400 and r.json()["error"] == "Adgangskoden må ikke være tom"
    r = api.post("/api/plcs", json=_plc("http://10.0.0.1/api"))
    assert r.status_code == 400 and "uden sti" in r.json()["error"]
    r = api.post("/api/plcs", json=_plc("ftp://10.0.0.1"))
    assert r.status_code == 400


def test_validation_error_is_a_string(api):
    r = api.post("/api/plcs", json={"key": "plc1", "ukendt": 1})
    assert r.status_code == 422
    assert isinstance(r.json()["error"], str) and "base_url: mangler" in r.json()["error"]


def test_tags_live_values_and_integrity(api, mock_plc):
    mock_plc.state.hr[10] = 500
    assert api.post("/api/plcs", json=_plc(mock_plc.url)).status_code == 201
    r = api.post("/api/tags", json={"name": "Niveau", "source": "plc1:hr:10", "scale": 0.1, "unit": "%"})
    assert r.status_code == 201, r.text

    # Ugyldig kilde, ukendt PLC, min>max — samme regler ved opret og opdatering
    r = api.post("/api/tags", json={"name": "X", "source": "plc1:hr:999"})
    assert r.status_code == 400 and "uden for hr" in r.json()["error"]
    r = api.post("/api/tags", json={"name": "Y", "source": "plc9:hr:1"})
    assert r.status_code == 400 and "plc9" in r.json()["error"]
    r = api.post("/api/tags", json={"name": "Z", "source": "plc1:hr:1", "min": 10, "max": 0})
    assert r.status_code == 400
    r = api.patch("/api/tags/Niveau", json={"min": 50})
    assert r.status_code == 200 and r.json()["min"] == 50
    r = api.patch("/api/tags/Niveau", json={"max": 0})  # 0 er en lovlig grænse, men < min
    assert r.status_code == 400 and "min" in r.json()["error"]
    r = api.patch("/api/tags/Niveau", json={"source": "plc1:ir:400"})
    assert r.status_code == 400

    values = _wait(lambda: (v := api.get("/api/live?tags=Niveau").json()["values"])["Niveau"]["quality"] == "good" and v)
    assert values["Niveau"]["value"] == pytest.approx(50.0)

    status = api.get("/api/plcs/plc1").json()["status"]
    assert status["state"] == "ok" and status["requests_per_cycle"] == 1

    # PLC med tags kan ikke slettes
    r = api.delete("/api/plcs/plc1")
    assert r.status_code == 409 and "1 tag" in r.json()["error"]
    assert api.delete("/api/tags/Niveau").status_code == 204
    assert api.delete("/api/plcs/plc1").status_code == 204


def test_wrong_plc_password_visible_in_status(api, mock_plc):
    api.post("/api/plcs", json=_plc(mock_plc.url, password="forkert"))
    api.post("/api/tags", json={"name": "A", "source": "plc1:hr:1"})
    status = _wait(lambda: (s := api.get("/api/plcs/plc1").json()["status"])["state"] == "error" and s)
    assert "Login afvist af PLC" in status["message"]
    live = api.get("/api/live?tags=A").json()["values"]["A"]
    assert live["quality"] == "comm_error" and "Login afvist" in live["error"]


def test_discover_and_import(api, mock_plc):
    api.post("/api/plcs", json=_plc(mock_plc.url))
    body = api.get("/api/plcs/plc1/discover").json()
    names = {s["name"]: s for s in body["suggestions"]}
    assert names["plc1_L1_Niveau"]["source"] == "plc1:logic:1:Niveau"
    assert names["plc1_G_Mode"]["source"] == "plc1:global:Mode"
    r = api.post("/api/tags/import", json={"tags": [
        {"name": "plc1_L1_Niveau", "source": "plc1:logic:1:Niveau"},
        {"name": "Ugyldig", "source": "plc1:hr:9999"},
    ]})
    assert r.json()["created"] == ["plc1_L1_Niveau"]
    assert r.json()["skipped"][0]["name"] == "Ugyldig"
    again = api.get("/api/plcs/plc1/discover").json()["suggestions"]
    assert next(s for s in again if s["name"] == "plc1_L1_Niveau")["exists"] is True


def test_discover_inactive_plc(api, mock_plc):
    api.post("/api/plcs", json=_plc(mock_plc.url, enabled=False))
    r = api.get("/api/plcs/plc1/discover")
    assert r.status_code == 409 and "deaktiveret" in r.json()["error"]
