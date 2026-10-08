"""Ugeprogrammer mod mock-PLC'en: validering, beskyttede tags, skrivning ved skift, overstyring, fejl og backup."""

import json
import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.schedule_engine import TZ

ADMIN_PW = "test-admin-pw-1"
HVERDAG = [1, 2, 3, 4, 5]


def _wait(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


def at(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=TZ).timestamp()


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        c.app.state.schedule_service.paused = True  # testen styrer tiden selv via tick(now)
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        for tag in [
            {"name": "Setpunkt", "source": "plc1:hr:5", "scale": 0.1, "unit": "°C", "writable": True, "min": 5, "max": 30},
            {"name": "Pumpe", "source": "plc1:coil:3", "writable": True},
            {"name": "Kun_laes", "source": "plc1:hr:6"},
        ]:
            assert c.post("/api/tags", json=tag).status_code == 201, tag
        _wait(lambda: c.get("/api/live?tags=Setpunkt,Pumpe").json()["values"]["Pumpe"]["quality"] == "good")
        yield c


def _tick(api, ts):
    api.portal.call(api.app.state.schedule_service.tick, ts)


def _live(api, tag):
    return api.get(f"/api/live?tags={tag}").json()["values"][tag]["value"]


PROGRAM = {"name": "Komfort", "tag": "Setpunkt", "default_value": 17,
           "entries": [{"days": HVERDAG, "start": "06:00", "end": "22:00", "value": 21}]}


@pytest.mark.parametrize("change, message", [
    ({"tag": "Kun_laes"}, "ikke skrivbart"),
    ({"tag": "Findes_ikke"}, "findes ikke"),
    ({"default_value": 40}, "over tagets maksimum"),
    ({"entries": [{"days": [], "start": "06:00", "end": "22:00", "value": 21}]}, "mindst én ugedag"),
    ({"entries": [{"days": [1], "start": "6:00", "end": "22:00", "value": 21}]}, "klokkeslæt"),
    ({"entries": [{"days": [1], "start": "06:00", "end": "06:00", "value": 21}]}, "forskellige"),
    ({"exceptions": [{"date_from": "2026-12-24", "date_to": "2026-12-20", "value": 15}]}, "efter til-dato"),
    ({"name": " "}, "Navn"),
])
def test_validation(api, change, message):
    r = api.post("/api/schedules", json={**PROGRAM, **change})
    assert r.status_code == 400 and message in r.json()["error"], r.text


def test_bool_tag_values_and_duplicate_name(api):
    r = api.post("/api/schedules", json={"name": "Pumpe nat", "tag": "Pumpe", "default_value": False,
                                         "entries": [{"days": [1, 2, 3, 4, 5, 6, 7], "start": "22:00", "end": "06:00", "value": True}]})
    assert r.status_code == 201, r.text
    assert r.json()["entries"][0]["value"] == 1.0 and r.json()["default_value"] == 0.0
    bad = api.post("/api/schedules", json={"name": "x", "tag": "Pumpe", "default_value": 5})
    assert bad.status_code == 400 and "Til eller Fra" in bad.json()["error"]
    assert api.post("/api/schedules", json={**PROGRAM, "name": "Pumpe nat"}).status_code == 409


def test_tag_in_use_is_protected(api):
    assert api.post("/api/schedules", json=PROGRAM).status_code == 201
    r = api.delete("/api/tags/Setpunkt")
    assert r.status_code == 409 and "ugeprogram" in r.json()["error"]
    r = api.patch("/api/tags/Setpunkt", json={"writable": False})
    assert r.status_code == 400 and "ugeprogram" in r.json()["error"]


def test_writes_on_transition_and_manual_override_holds(api, mock_plc):
    sid = api.post("/api/schedules", json=PROGRAM).json()["id"]
    _tick(api, at(2026, 10, 5, 5))                 # mandag nat → standard 17
    _wait(lambda: _live(api, "Setpunkt") == 17.0)
    _tick(api, at(2026, 10, 5, 6, 1))              # skift → 21
    _wait(lambda: _live(api, "Setpunkt") == 21.0)
    mock_plc.state.hr[5] = 195                     # operatør sætter 19,5 manuelt
    _wait(lambda: _live(api, "Setpunkt") == 19.5)
    _tick(api, at(2026, 10, 5, 12))                # samme periode → overstyringen holder
    time.sleep(0.4)
    assert _live(api, "Setpunkt") == 19.5
    _tick(api, at(2026, 10, 5, 22, 1))             # næste skift → 17
    _wait(lambda: _live(api, "Setpunkt") == 17.0)
    entries = [e for e in api.get("/api/audit").json() if e["action"] == "schedule"]
    assert entries and entries[0]["username"] == "ugeprogram:Komfort"
    status = next(s for s in api.get("/api/schedules").json() if s["id"] == sid)["status"]
    assert status["applied"] is True and status["error"] == "" and status["target"] == 17.0


def test_no_write_when_plc_already_has_value(api, mock_plc):
    mock_plc.state.hr[5] = 210
    _wait(lambda: _live(api, "Setpunkt") == 21.0)
    api.post("/api/schedules", json=PROGRAM)
    _tick(api, at(2026, 10, 5, 8))
    assert not [e for e in api.get("/api/audit").json() if e["action"] == "schedule"]


def test_plc_error_is_shown_and_retried(api, mock_plc):
    sid = api.post("/api/schedules", json=PROGRAM).json()["id"]
    mock_plc.state.reject_writes = "PLC i safe mode"
    _tick(api, at(2026, 10, 5, 8))
    status = next(s for s in api.get("/api/schedules").json() if s["id"] == sid)["status"]
    assert status["applied"] is False and "safe mode" in status["error"]
    mock_plc.state.reject_writes = ""
    _tick(api, at(2026, 10, 5, 8, 0) + 30)        # før RETRY_S → ikke igen endnu
    assert _live(api, "Setpunkt") != 21.0
    _tick(api, at(2026, 10, 5, 8, 0) + 61)        # efter RETRY_S → skrives
    _wait(lambda: _live(api, "Setpunkt") == 21.0)


def test_disabled_program_does_nothing_and_preview(api):
    p = api.post("/api/schedules", json={**PROGRAM, "enabled": False}).json()
    _tick(api, at(2026, 10, 5, 8))
    assert not [e for e in api.get("/api/audit").json() if e["action"] == "schedule"]
    assert len(p["week"]) == 7 and p["week"][0]["day"] == "man"
    prev = api.post("/api/schedules/preview", json=PROGRAM).json()
    assert prev["now_value"] in (17.0, 21.0) and prev["next_changes"]
    assert api.post("/api/schedules/preview", json={**PROGRAM, "tag": "Kun_laes"}).status_code == 400


def test_engineer_only(api):
    api.post("/api/users", json={"username": "op", "role": "operator", "password": "Hemmelig-123"})
    api.post("/api/auth/login", json={"username": "op", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert api.get("/api/schedules").status_code == 403


def test_backup_roundtrip_and_invalid_schedule_in_backup(api):
    api.post("/api/schedules", json=PROGRAM)
    backup = api.get("/api/backup").json()
    assert [s["name"] for s in backup["schedules"]] == ["Komfort"]
    sid = api.get("/api/schedules").json()[0]["id"]
    api.delete(f"/api/schedules/{sid}")
    r = api.post("/api/backup/restore", content=json.dumps(backup), headers={"content-type": "application/json"})
    assert r.status_code == 200 and r.json()["schedules"] == 1
    assert [s["name"] for s in api.get("/api/schedules").json()] == ["Komfort"]
    backup["schedules"][0]["tag"] = "Kun_laes"
    r = api.post("/api/backup/restore", content=json.dumps(backup), headers={"content-type": "application/json"})
    assert r.status_code == 400 and "Ugeprogram #1" in r.json()["error"] and "skrivbart" in r.json()["error"]
