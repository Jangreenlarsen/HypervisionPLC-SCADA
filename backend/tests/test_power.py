"""Genstart fra web (v1.8.0): anmodning til root-hjælperen, kun admin, kun når hjælperen er installeret, ingen dobbelt-bestilling."""

import os
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"


@pytest.fixture
def api(tmp_path):
    state = tmp_path / "net-state"
    state.mkdir()
    settings = Settings(data_dir=tmp_path / "data", net_state_dir=state, frontend_dir=tmp_path / "nope",
                        admin_password=ADMIN_PW, backup_hours=0, start_runtimes=False)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.state, c.req = state, tmp_path / "data" / "config" / "power.request"
        yield c


def test_not_installed_gives_a_clear_409_and_writes_nothing(api):
    assert api.get("/api/system/power").json()["enabled"] is False
    r = api.post("/api/system/power", json={"action": "reboot"})
    assert r.status_code == 409 and "ikke installeret" in r.json()["error"]
    assert not api.req.exists()


def test_request_is_written_for_the_helper_and_audited(api):
    (api.state / "power-enabled").write_text("")
    r = api.post("/api/system/power", json={"action": "reboot"})
    assert r.status_code == 200 and r.json() == {"requested": "reboot", "label": "maskinen"}
    text = api.req.read_text(encoding="utf-8")
    assert text.startswith("action=reboot\nby=admin\nid=") and not (api.req.parent / "power.request.tmp").exists()
    assert api.get("/api/system/power").json()["pending"] is True
    audited = [e for e in api.get("/api/audit?limit=20").json() if e["action"] == "system.power"]
    assert audited and audited[0]["target"] == "reboot"
    # en ny bestilling imens den første venter, afvises
    assert api.post("/api/system/power", json={"action": "restart"}).status_code == 409


def test_stale_request_does_not_block_and_last_action_is_shown(api):
    (api.state / "power-enabled").write_text("")
    api.post("/api/system/power", json={"action": "restart"})
    old = time.time() - 600
    os.utime(api.req, (old, old))                     # helperen er aldrig kørt: filen er stale
    assert api.get("/api/system/power").json()["pending"] is False
    assert api.post("/api/system/power", json={"action": "restart"}).status_code == 200
    (api.state / "power.json").write_text('{"action":"reboot","by":"jan","ts":1}')
    assert api.get("/api/system/power").json()["last"]["by"] == "jan"


def test_validation_and_admin_only(api):
    (api.state / "power-enabled").write_text("")
    assert api.post("/api/system/power", json={"action": "poweroff"}).status_code == 422
    assert api.post("/api/system/power", json={}).status_code == 422
    assert api.post("/api/users", json={"username": "eng", "role": "engineer", "password": "Hemmelig-123"}).status_code == 201
    with TestClient(api.app) as e:
        e.post("/api/auth/login", json={"username": "eng", "password": "Hemmelig-123"})
        e.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
        e.post("/api/auth/login", json={"username": "eng", "password": "Hemmelig-123-ny"})
        assert e.post("/api/system/power", json={"action": "reboot"}).status_code == 403
        assert e.get("/api/system/power").status_code == 403
    assert not api.req.exists()
