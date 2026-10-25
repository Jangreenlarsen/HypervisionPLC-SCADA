"""Deaktiverede tegninger (v1.6.0): offline — ingen betjening, tags kun de bruger pollas ikke, alarmer holdes i live, backup bevarer det."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"
SVG_A = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
         '<text id="Niveau_A">-</text><rect id="Knap_A" width="1" height="1"/></svg>')
SVG_B = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
         '<text id="Niveau_B">-</text><rect id="Knap_B" width="1" height="1"/></svg>')


def _wait(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


@pytest.fixture
def setup(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        for t in [{"name": "Niveau_A", "source": "plc1:hr:1"},          # kun tegning A
                  {"name": "Niveau_B", "source": "plc1:hr:2"},          # kun tegning B
                  {"name": "Faelles", "source": "plc1:hr:3"},            # begge
                  {"name": "Alarm_A", "source": "plc1:hr:4"},           # kun A, men har alarm
                  {"name": "Motor_A", "source": "plc1:coil:1", "writable": True}]:
            assert c.post("/api/tags", json=t).status_code == 201
        assert c.patch("/api/tags/Alarm_A", json={"alarm_h": 90}).status_code == 200
        a = c.post("/api/drawings", json={"name": "Anlæg A", "svg": SVG_A}).json()["drawing"]["id"]
        b = c.post("/api/drawings", json={"name": "Anlæg B", "svg": SVG_B}).json()["drawing"]["id"]
        # nye versioner med ét tekst-element pr. tag og en knap, så hvert tag er brugt af tegningen
        for did, tags in ((a, ["Niveau_A", "Faelles", "Alarm_A"]), (b, ["Niveau_B", "Faelles"])):
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                   + "".join(f'<text id="t_{n}">-</text>' for n in tags) + '<rect id="Knap" width="1" height="1"/></svg>')
            assert c.post(f"/api/drawings/{did}/versions", json={"svg": svg, "activate": True}).status_code == 201
            for n in tags:
                assert c.put(f"/api/drawings/{did}/bindings/t_{n}", json={"bindings": [{"tag": n, "anim": "text"}]}).status_code == 200
        assert c.put(f"/api/drawings/{a}/bindings/Knap", json={"bindings": [{"tag": "Motor_A", "anim": "click:toggle"}]}).status_code == 200
        c.a, c.b = a, b
        r = c.post("/api/users", json={"username": "op", "role": "operator", "password": "Hemmelig-123"})
        assert r.status_code == 201
        yield c


def polled(c):
    return {t.name for t in c.app.state.manager.runtimes["plc1"]._tags}


def as_user(c, name, pw="Hemmelig-123"):
    c.post("/api/auth/login", json={"username": name, "password": pw})
    c.post("/api/auth/password", json={"old_password": pw, "new_password": pw + "-ny"})
    c.post("/api/auth/login", json={"username": name, "password": pw + "-ny"})


def test_disable_and_enable_roundtrip_with_flags(setup):
    c = setup
    assert [d["disabled"] for d in c.get("/api/drawings").json()] == [False, False]
    r = c.patch(f"/api/drawings/{c.a}", json={"disabled": True})
    assert r.status_code == 200 and r.json()["disabled"] is True
    assert {d["id"]: d["disabled"] for d in c.get("/api/drawings").json()} == {c.a: True, c.b: False}
    assert c.get(f"/api/drawings/{c.a}/view").json()["disabled"] is True
    assert c.get(f"/api/drawings/{c.b}/view").json()["disabled"] is False
    assert c.patch(f"/api/drawings/{c.a}", json={"disabled": False}).json()["disabled"] is False
    assert c.patch("/api/drawings/findes-ikke", json={"disabled": True}).status_code == 404


def test_only_exclusive_tags_without_other_needs_stop_polling(setup):
    c = setup
    _wait(lambda: {"Niveau_A", "Niveau_B", "Faelles", "Alarm_A", "Motor_A"} <= polled(c))
    c.patch(f"/api/drawings/{c.a}", json={"disabled": True})
    now = polled(c)
    assert "Niveau_A" not in now                      # kun tegning A (deaktiveret) bruger det
    assert "Motor_A" not in now                       # også kun A
    assert {"Niveau_B", "Faelles", "Alarm_A"} <= now   # B bruger det / alarmer slås aldrig fra
    live = c.app.state.cache.get("Niveau_A")
    assert live.quality == "unknown" and "deaktiverede" in (live.error or "")
    c.patch(f"/api/drawings/{c.a}", json={"disabled": False})
    assert "Niveau_A" in polled(c)
    _wait(lambda: c.app.state.cache.get("Niveau_A").quality == "good")


def test_operator_cannot_operate_a_disabled_drawing(setup):
    c = setup
    admin_pw = ADMIN_PW
    as_user(c, "op")
    assert c.post("/api/tags/Motor_A/toggle").status_code == 200
    c.post("/api/auth/login", json={"username": "admin", "password": admin_pw})
    c.patch(f"/api/drawings/{c.a}", json={"disabled": True})
    c.post("/api/auth/login", json={"username": "op", "password": "Hemmelig-123-ny"})
    r = c.post("/api/tags/Motor_A/toggle")
    assert r.status_code == 403, r.text
    # og operatøren kan ikke selv aktivere den
    assert c.patch(f"/api/drawings/{c.a}", json={"disabled": False}).status_code == 403
    c.post("/api/auth/login", json={"username": "admin", "password": admin_pw})
    c.patch(f"/api/drawings/{c.a}", json={"disabled": False})
    c.post("/api/auth/login", json={"username": "op", "password": "Hemmelig-123-ny"})
    assert c.post("/api/tags/Motor_A/toggle").status_code == 200


def test_disabled_flag_survives_backup_roundtrip(setup):
    c = setup
    c.patch(f"/api/drawings/{c.a}", json={"disabled": True})
    backup = c.get("/api/backup").json()
    assert {d["id"]: d["disabled"] for d in backup["drawings"]} == {c.a: True, c.b: False}
    c.patch(f"/api/drawings/{c.a}", json={"disabled": False})
    assert c.post("/api/backup/restore", json=backup).status_code == 200
    assert {d["id"]: d["disabled"] for d in c.get("/api/drawings").json()} == {c.a: True, c.b: False}
