"""Alarmer: betingelser, tilstandsmaskine, kvittering, persistens, adgang og backup."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.alarms import tag_conditions

ADMIN_PW = "test-admin-pw-1"


def _tag(**kw):
    base = {"name": "T", "plc": "plc1", "unit": "°C", "description": "Temp", "alarm_hh": None, "alarm_h": None,
            "alarm_l": None, "alarm_ll": None, "alarm_deadband": 0.0, "alarm_delay_s": 0.0, "alarm_on": None}
    base.update(kw)
    return base


def _levels(conds):
    return {c.kind: c.level for c in conds}


# ------------------------------------------------------------- ren logik

def test_no_alarm_config_returns_none():
    assert tag_conditions(_tag(), 50, {}) is None


def test_high_low_levels():
    t = _tag(alarm_hh=90, alarm_h=80, alarm_l=10, alarm_ll=0)
    assert _levels(tag_conditions(t, 50, {})) == {}
    assert _levels(tag_conditions(t, 80, {})) == {"high": "H"}
    assert _levels(tag_conditions(t, 95, {})) == {"high": "HH"}
    assert _levels(tag_conditions(t, 10, {})) == {"low": "L"}
    assert _levels(tag_conditions(t, -1, {})) == {"low": "LL"}  # 0 er en gyldig grænse


def test_deadband_hysteresis():
    t = _tag(alarm_h=80, alarm_deadband=2)
    assert _levels(tag_conditions(t, 79, {})) == {}                    # ikke aktiv: under grænsen
    assert _levels(tag_conditions(t, 79, {"high": "H"})) == {"high": "H"}  # aktiv: bliver til < 78
    assert _levels(tag_conditions(t, 77.9, {"high": "H"})) == {}
    hh = _tag(alarm_hh=90, alarm_h=80, alarm_deadband=2)
    assert _levels(tag_conditions(hh, 89, {"high": "HH"})) == {"high": "HH"}
    assert _levels(tag_conditions(hh, 87.9, {"high": "HH"})) == {"high": "H"}  # nedgraderes


def test_bool_alarm():
    t = _tag(alarm_on="true", description="Motorfejl")
    assert _levels(tag_conditions(t, True, {})) == {"state": "ON"}
    assert _levels(tag_conditions(t, False, {})) == {}
    assert _levels(tag_conditions(_tag(alarm_on="false"), False, {})) == {"state": "ON"}
    assert tag_conditions(_tag(alarm_h=1), "tekst", {}) == []


# ------------------------------------------------------------- via API

def _wait(predicate, timeout=6.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


def _settings(tmp_path, **kw):
    return Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9, frontend_dir=tmp_path / "nope",
                    admin_password=ADMIN_PW, backup_hours=0, alarm_tick_s=0.1, alarm_comm_delay_s=0.3, **kw)


@pytest.fixture
def api(tmp_path, mock_plc):
    with TestClient(create_app(_settings(tmp_path))) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        assert c.post("/api/tags", json={"name": "Temp", "source": "plc1:hr:5", "scale": 0.1, "unit": "°C",
                                         "description": "Kedeltemperatur", "alarm_hh": 90, "alarm_h": 80,
                                         "alarm_deadband": 1}).status_code == 201
        assert c.post("/api/tags", json={"name": "Fejl", "source": "plc1:coil:4", "alarm_on": "true",
                                         "description": "Motorfejl"}).status_code == 201
        _wait(lambda: c.get("/api/live?tags=Temp").json()["values"]["Temp"]["quality"] == "good")
        yield c


def _active(c):
    return {a["key"]: a for a in c.get("/api/alarms").json()["active"]}


def test_raise_ack_clear_cycle(api, mock_plc):
    mock_plc.state.hr[5] = 850  # 85,0 °C → H
    a = _wait(lambda: _active(api).get("tag:Temp:high"))
    assert a["level"] == "H" and a["state"] == "active_unack" and a["priority"] == "medium"
    assert "Kedeltemperatur for høj (H): 85.0 °C" in a["message"]
    assert api.get("/api/alarms").json()["summary"] == {"active": 1, "unacked": 1, "high": 0}

    assert api.post("/api/alarms/ack", json={"keys": ["tag:Temp:high"]}).json() == {"acked": 1}
    a = _active(api)["tag:Temp:high"]
    assert a["state"] == "active_ack" and a["acked_by"] == "admin"

    mock_plc.state.hr[5] = 795  # 79,5 — inden for dødbåndet (H − 1) → stadig aktiv
    time.sleep(0.6)
    assert "tag:Temp:high" in _active(api)
    mock_plc.state.hr[5] = 780  # 78,0 → ophører; kvitteret → væk
    _wait(lambda: "tag:Temp:high" not in _active(api))
    events = [(e["event"], e["level"]) for e in api.get("/api/alarms/history").json() if e["key"] == "tag:Temp:high"]
    assert events == [("clear", "H"), ("ack", "H"), ("raise", "H")]


def test_return_unacked_then_ack_removes(api, mock_plc):
    mock_plc.state.coils[4] = True
    _wait(lambda: _active(api).get("tag:Fejl:state"))
    mock_plc.state.coils[4] = False
    a = _wait(lambda: (x := _active(api).get("tag:Fejl:state")) and x["state"] == "rtn_unack" and x)
    assert a["priority"] == "high"
    assert api.get("/api/alarms").json()["summary"]["unacked"] == 1
    api.post("/api/alarms/ack", json={"keys": None})  # kvittér alle synlige
    assert _active(api) == {}


def test_escalation_requires_new_ack(api, mock_plc):
    mock_plc.state.hr[5] = 850
    _wait(lambda: _active(api).get("tag:Temp:high"))
    api.post("/api/alarms/ack", json={"keys": None})
    mock_plc.state.hr[5] = 950  # → HH
    a = _wait(lambda: (x := _active(api).get("tag:Temp:high")) and x["level"] == "HH" and x)
    assert a["state"] == "active_unack" and a["priority"] == "high"


def test_delay(api, mock_plc):
    api.patch("/api/tags/Fejl", json={"alarm_delay_s": 1.0})
    mock_plc.state.coils[4] = True
    time.sleep(0.5)
    assert "tag:Fejl:state" not in _active(api)
    _wait(lambda: "tag:Fejl:state" in _active(api), timeout=3)
    # kortvarig betingelse udløser ikke
    api.post("/api/alarms/ack", json={"keys": None})
    mock_plc.state.coils[4] = False
    _wait(lambda: _active(api) == {})


def test_comm_alarm_and_frozen_tag_alarms(api, mock_plc):
    mock_plc.state.hr[5] = 850
    _wait(lambda: _active(api).get("tag:Temp:high"))
    mock_plc.state.users["scada"] = "andet"
    mock_plc.state.revoke_all_sessions()
    comm = _wait(lambda: _active(api).get("plc:plc1:comm"))
    assert comm["level"] == "COMM" and "kommunikation tabt" in comm["message"]
    assert "tag:Temp:high" in _active(api)  # tag-alarmen ryddes ikke af en kommunikationsfejl


def test_alarms_survive_restart(tmp_path, mock_plc):
    s = _settings(tmp_path)
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        c.post("/api/tags", json={"name": "Fejl", "source": "plc1:coil:4", "alarm_on": "true"})
        mock_plc.state.coils[4] = True
        _wait(lambda: _active(c).get("tag:Fejl:state"))
        mock_plc.state.coils[4] = False
        _wait(lambda: _active(c)["tag:Fejl:state"]["state"] == "rtn_unack")
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        assert _active(c)["tag:Fejl:state"]["state"] == "rtn_unack"  # ukvitteret alarm overlevede genstart


@pytest.mark.parametrize("body, message", [
    ({"name": "X", "source": "plc1:hr:1", "alarm_h": 10, "alarm_hh": 5}, "skal stige"),
    ({"name": "X", "source": "plc1:hr:1", "alarm_l": 10, "alarm_h": 5}, "skal stige"),
    ({"name": "X", "source": "plc1:coil:1", "alarm_h": 1}, "tal-tag"),
    ({"name": "X", "source": "plc1:hr:1", "alarm_on": "true"}, "til/fra-tag"),
    ({"name": "X", "source": "plc1:hr:1", "alarm_on": "ja"}, "alarm_on"),
    ({"name": "X", "source": "plc1:hr:1", "alarm_h": 1, "alarm_deadband": -1}, "negativt"),
    ({"name": "X", "source": "plc1:hr:1", "alarm_h": 1, "alarm_delay_s": 4000}, "0-3600"),
    # "auto"-tag (PLC-logik): både grænser og til/fra-alarm — grænserne ville blive ignoreret (BUGS v0.74.0)
    ({"name": "X", "source": "plc1:logic:1:Niveau", "alarm_h": 90, "alarm_hh": 100, "alarm_on": "true"}, "både grænser"),
])
def test_alarm_validation(api, body, message):
    r = api.post("/api/tags", json=body)
    assert r.status_code == 400 and message in r.json()["error"], r.text


def test_alarm_validation_on_update(api):
    r = api.patch("/api/tags/Temp", json={"alarm_h": 95})  # H > eksisterende HH 90
    assert r.status_code == 400 and "skal stige" in r.json()["error"]
    r = api.patch("/api/tags/Temp", json={"source": "plc1:coil:1"})  # grænser på et til/fra-tag
    assert r.status_code == 400


def test_scoped_user_sees_only_own_alarms_and_viewer_cannot_ack(api, mock_plc):
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><text id="Fejl">-</text></svg>'
    did = api.post("/api/drawings", json={"name": "Motor", "svg": svg}).json()["drawing"]["id"]
    r = api.post("/api/users", json={"username": "vagt", "role": "viewer", "password": "Hemmelig-123", "drawings": [did]})
    assert r.status_code == 201, r.text
    mock_plc.state.hr[5] = 850
    mock_plc.state.coils[4] = True
    _wait(lambda: len(_active(api)) == 2)
    assert api.post("/api/auth/login", json={"username": "vagt", "password": "Hemmelig-123"}).status_code == 200
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert set(_active(api)) == {"tag:Fejl:state"}
    assert all(e["tag"] == "Fejl" for e in api.get("/api/alarms/history").json())
    r = api.post("/api/alarms/ack", json={"keys": None})
    assert r.status_code == 403


def test_websocket_pushes_alarms(api, mock_plc):
    cookie = {"cookie": f"scada_session={api.cookies.get('scada_session')}"}
    with api.websocket_connect("/ws/live", headers=cookie) as ws:
        first = ws.receive_json()
        assert first["type"] == "alarms" and first["active"] == []
        mock_plc.state.coils[4] = True
        while True:
            msg = ws.receive_json()
            if msg["type"] == "alarms" and msg["active"]:
                assert msg["active"][0]["key"] == "tag:Fejl:state" and msg["summary"]["unacked"] == 1
                break


def test_alarm_limits_in_backup(api):
    backup = api.get("/api/backup").json()
    temp = next(t for t in backup["tags"] if t["name"] == "Temp")
    assert temp["alarm_hh"] == 90 and temp["alarm_h"] == 80 and temp["alarm_deadband"] == 1
    temp["alarm_h"] = 95  # ugyldig rækkefølge → hele restore afvises
    r = api.post("/api/backup/restore", json=backup)
    assert r.status_code == 400 and "stige" in r.json()["error"]
    temp["alarm_h"] = 70
    assert api.post("/api/backup/restore", json=backup).status_code == 200
    assert api.get("/api/tags/Temp").json()["alarm_h"] == 70


def test_switching_between_limits_and_on_off_alarm(api):
    """Skift mellem grænser og til/fra-alarm på et "auto"-tag: tilladt, når den anden ryddes i samme gem."""
    assert api.post("/api/tags", json={"name": "Auto", "source": "plc1:logic:1:Niveau", "alarm_h": 90}).status_code == 201
    r = api.patch("/api/tags/Auto", json={"alarm_on": "true"})
    assert r.status_code == 400 and "både grænser" in r.json()["error"]
    r = api.patch("/api/tags/Auto", json={"alarm_on": "true", "alarm_h": None})
    assert r.status_code == 200, r.text



# ------------------------------------------------- kommunikationsalarmer (delvis fejl, ikke startet)

def test_comm_problems_variants():
    from app.services.alarms import AlarmService as A
    plc = {"key": "plc1", "name": "Kedel"}
    assert A._comm_problems(plc, {"state": "ok", "message": "", "partial": []}) == []
    assert A._comm_problems(plc, {"state": "stopped", "message": "Ikke startet", "attention": False}) == []
    k, m = A._comm_problems(plc, {"state": "stopped", "message": "Ingen adgangskode sat", "attention": True})[0]
    assert k == "plc:plc1:comm" and "ikke startet" in m
    k, m = A._comm_problems(plc, {"state": "error", "message": "nede"})[0]
    assert k == "plc:plc1:comm" and "kommunikation tabt" in m
    (k, m), = A._comm_problems(plc, {"state": "ok", "partial": [{"what": "ST-program 1", "message": "timeout", "tags": 3},
                                                                {"what": "hr 0–9", "message": "x", "tags": 1}]})
    assert k == "plc:plc1:partial" and "ST-program 1 svarer ikke (3 tag)" in m and "(+1 andre)" in m


def test_partial_failure_raises_comm_alarm_and_clears(api, mock_plc, monkeypatch):
    """Et fejlende ST-program giver en kommunikationsalarm (tidligere kun hele-PLC'en-tabt), og den ophører igen."""
    import app.services.plc_runtime as mod
    from app.plc.errors import PlcUnreachable
    monkeypatch.setattr(mod, "COOL_STEP_S", 0.05)
    api.post("/api/tags", json={"name": "ST", "source": "plc1:logic:1:Niveau"})
    rt = api.app.state.manager.runtimes["plc1"]
    real, broken = rt.client.logic_program, {"on": True}

    async def flaky(program_id):
        if broken["on"]:
            raise PlcUnreachable("svarede ikke (test)")
        return await real(program_id)

    rt.client.logic_program = flaky  # type: ignore[method-assign]
    api.app.state.alarm_service.comm_delay_s = 0.0
    a = _wait(lambda: _active(api).get("plc:plc1:partial"))
    assert a["level"] == "COMM" and "ST-program 1 svarer ikke" in a["message"]
    broken["on"] = False
    _wait(lambda: "plc:plc1:partial" not in _active(api) or
          _active(api)["plc:plc1:partial"]["state"] == "rtn_unack")


def test_plc_without_password_raises_comm_alarm(api, mock_plc):
    """En aktiv PLC uden adgangskode starter aldrig — det skal give en alarm, ikke tavshed."""
    r = api.post("/api/plcs", json={"key": "plc2", "base_url": mock_plc.url, "username": "scada", "sse_enabled": False})
    assert r.status_code == 201, r.text
    api.app.state.alarm_service.comm_delay_s = 0.0
    a = _wait(lambda: _active(api).get("plc:plc2:comm"))
    assert a["level"] == "COMM" and "ikke startet" in a["message"] and "adgangskode" in a["message"]


def test_partial_alarm_cleared_when_plc_disabled(api, mock_plc, monkeypatch):
    import app.services.plc_runtime as mod
    from app.plc.errors import PlcUnreachable
    monkeypatch.setattr(mod, "COOL_STEP_S", 0.05)
    api.post("/api/tags", json={"name": "ST", "source": "plc1:logic:1:Niveau"})

    async def broken(program_id):
        raise PlcUnreachable("svarede ikke (test)")

    api.app.state.manager.runtimes["plc1"].client.logic_program = broken  # type: ignore[method-assign]
    api.app.state.alarm_service.comm_delay_s = 0.0
    _wait(lambda: _active(api).get("plc:plc1:partial"))
    assert api.patch("/api/plcs/plc1", json={"enabled": False}).status_code == 200
    _wait(lambda: "plc:plc1:partial" not in _active(api) or _active(api)["plc:plc1:partial"]["state"] == "rtn_unack")
