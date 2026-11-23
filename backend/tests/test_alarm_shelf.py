"""Udsæt alarm (shelving, v6.19.0): validering, scope, rolle, hændelser, audit, udløb, genstart, summary og metrics."""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.errors import ServiceError
from app.services.metrics import render
from tests.test_alarms import ADMIN_PW, _active, _settings, _wait, api  # noqa: F401

KEY = "tag:Fejl:state"


def _raise(api, mock_plc):
    mock_plc.state.coils[4] = True
    return _wait(lambda: _active(api).get(KEY))


def _shelve(c, key=KEY, minutes=60, reason="Sensor mistænkes defekt"):
    return c.post("/api/alarms/shelve", json={"key": key, "minutes": minutes, "reason": reason})


def _shelved(c):
    r = c.get("/api/alarms/shelved")
    assert r.status_code == 200, r.text
    return r.json()


def _events(c, key=KEY):
    return [(e["event"], e["username"], e["message"]) for e in c.get("/api/alarms/history").json() if e["key"] == key]


# ------------------------------------------------------------------ validering

@pytest.mark.parametrize("minutes", [0, 4, 1441, -5, 5.5, "60", None, True, [60]])
def test_invalid_minutes_is_400(api, mock_plc, minutes):
    _raise(api, mock_plc)
    r = _shelve(api, minutes=minutes)
    assert r.status_code == 400 and "minutter" in r.json()["error"], r.text
    assert KEY in _active(api) and _shelved(api) == []


@pytest.mark.parametrize("minutes", [5, 1440])
def test_minutes_boundaries_accepted(api, mock_plc, minutes):
    _raise(api, mock_plc)
    r = _shelve(api, minutes=minutes)
    assert r.status_code == 200, r.text
    assert abs((r.json()["until_ts"] - r.json()["shelved_at"]) - minutes * 60) < 1


@pytest.mark.parametrize("reason", ["", "   ", "ab", "  ab  ", "x" * 201, None, 5])
def test_invalid_reason_is_400(api, mock_plc, reason):
    _raise(api, mock_plc)
    r = _shelve(api, reason=reason)
    assert r.status_code == 400 and "Begrundelsen" in r.json()["error"], r.text
    assert KEY in _active(api)


def test_reason_is_trimmed_and_limits_inclusive(api, mock_plc):
    _raise(api, mock_plc)
    r = _shelve(api, reason="  abc  ")
    assert r.status_code == 200 and r.json()["reason"] == "abc"
    api.post("/api/alarms/unshelve", json={"key": KEY})
    _raise(api, mock_plc)
    assert _shelve(api, reason="x" * 200).status_code == 200


@pytest.mark.parametrize("reason", ["abc\ndef", "abc\tdef", "abc\x00def", "abc\x07", "ab​c", "‮abc", "abc⁠", "abc\r"])
def test_control_and_format_characters_in_reason_are_rejected(api, mock_plc, reason):
    _raise(api, mock_plc)
    r = _shelve(api, reason=reason)
    assert r.status_code == 400 and "kontroltegn" in r.json()["error"], r.text
    assert KEY in _active(api) and _shelved(api) == []


def test_reason_whitespace_is_collapsed_and_length_counts_code_points(api, mock_plc):
    _raise(api, mock_plc)
    r = _shelve(api, reason="  Sensor   mistænkes  defekt  ")
    assert r.status_code == 200 and r.json()["reason"] == "Sensor mistænkes defekt"
    api.post("/api/alarms/unshelve", json={"key": KEY})
    _raise(api, mock_plc)
    assert _shelve(api, reason="a" + " " * 50 + "bc").json()["reason"] == "a bc"   # kollapset længde 4 tæller
    api.post("/api/alarms/unshelve", json={"key": KEY})
    _raise(api, mock_plc)
    assert _shelve(api, reason="😀" * 200).status_code == 200                       # 200 kodepunkter (400 UTF-16-enheder)
    api.post("/api/alarms/unshelve", json={"key": KEY})
    _raise(api, mock_plc)
    r = _shelve(api, reason="😀" * 201)
    assert r.status_code == 400 and "Begrundelsen" in r.json()["error"]
    assert _shelve(api, reason="a" + " " * 5 + "b").status_code == 200                # kollapset til "a b" = 3 tegn: nok


def test_unknown_key_is_404_and_extra_field_rejected(api):
    r = _shelve(api, key="tag:Findes:ikke")
    assert r.status_code == 404 and r.json()["error"] == "Alarmen findes ikke"
    assert api.post("/api/alarms/shelve", json={"key": KEY, "minutes": 60, "reason": "abc", "x": 1}).status_code == 422
    assert api.post("/api/alarms/unshelve", json={"key": "tag:Findes:ikke"}).status_code == 404


def test_comm_alarm_cannot_be_shelved(api, mock_plc):
    mock_plc.state.users["scada"] = "andet"
    mock_plc.state.revoke_all_sessions()
    _wait(lambda: _active(api).get("plc:plc1:comm"))
    r = _shelve(api, key="plc:plc1:comm")
    assert r.status_code == 400 and r.json()["error"] == "Kommunikations- og systemalarmer kan ikke udsættes"
    assert "plc:plc1:comm" in _active(api)


def test_system_alarm_cannot_be_shelved(api):
    svc = api.app.state.alarm_service
    row = {"key": "sys:test", "tag": "", "plc": "", "kind": "sys", "level": "SYS", "priority": "high", "state": "active_unack",
           "raised_at": time.time(), "value": None, "message": "System: test", "acked_by": None, "acked_at": None}
    with svc._lock:   # under tick-låsen, så evaluate ikke rydder den kunstige række undervejs (servicen kaldes direkte: HTTP ville vente på låsen)
        svc.state["sys:test"] = row
        try:
            with pytest.raises(ServiceError) as exc:
                svc.shelve("sys:test", 60, "Test af begrundelse", "admin", None)
        finally:
            svc.state.pop("sys:test", None)
    assert exc.value.status == 400 and "systemalarmer" in exc.value.message
    assert _shelved(api) == []


def test_ended_alarm_cannot_be_shelved(api, mock_plc):
    _raise(api, mock_plc)
    mock_plc.state.coils[4] = False
    _wait(lambda: _active(api)[KEY]["state"] == "rtn_unack")
    r = _shelve(api)
    assert r.status_code == 400 and "ophørt" in r.json()["error"]


def test_already_shelved_is_409_with_end_time(api, mock_plc):
    _raise(api, mock_plc)
    assert _shelve(api).status_code == 200
    r = _shelve(api, minutes=30)
    assert r.status_code == 409 and "allerede udsat til" in r.json()["error"], r.text
    assert len(_shelved(api)) == 1


# ------------------------------------------------------------ virkning og spor

def test_shelve_hides_alarm_logs_event_and_audit(api, mock_plc):
    _raise(api, mock_plc)
    r = _shelve(api, minutes=15, reason="Afventer service")
    assert r.status_code == 200, r.text
    row = r.json()
    assert row["key"] == KEY and row["shelved_by"] == "admin" and row["tag"] == "Fejl" and row["plc"] == "plc1"
    assert KEY not in _active(api)
    assert api.get("/api/alarms").json()["summary"]["shelved"] == 1
    (event, user, message), = [e for e in _events(api) if e[0] == "shelve"]
    assert user == "admin" and "Afventer service" in message and "Udsat til" in message
    audit = [a for a in api.get("/api/audit?limit=50").json() if a["action"] == "alarm.shelve"]
    assert len(audit) == 1
    d = audit[0]["detail"]
    assert d["key"] == KEY and d["minutes"] == 15 and d["reason"] == "Afventer service" and d["until"] == row["until_ts"]
    assert "Fejl" in _shelved(api)[0]["tag"] and _shelved(api)[0]["remaining_s"] > 800


def test_failed_shelve_is_not_audited(api, mock_plc):
    _raise(api, mock_plc)
    _shelve(api, minutes=1)
    _shelve(api, key="tag:Findes:ikke")
    assert not [a for a in api.get("/api/audit?limit=50").json() if a["action"].startswith("alarm.shelve")]


def test_no_new_alarm_while_shelved_even_if_condition_holds(api, mock_plc):
    _raise(api, mock_plc)
    assert _shelve(api).status_code == 200
    time.sleep(1.0)
    assert mock_plc.state.coils[4] is True
    assert KEY not in _active(api)
    assert len([e for e in _events(api) if e[0] == "raise"]) == 1   # ingen ny "raise"


def test_shelved_alarm_with_delay_does_not_start_pending(api, mock_plc):
    api.patch("/api/tags/Fejl", json={"alarm_delay_s": 0.5})
    _raise(api, mock_plc)
    assert _shelve(api).status_code == 200
    time.sleep(1.2)
    assert KEY not in _active(api)
    assert KEY not in api.app.state.alarm_service._pending


def test_unshelve_raises_again_when_condition_holds(api, mock_plc):
    _raise(api, mock_plc)
    _shelve(api)
    r = api.post("/api/alarms/unshelve", json={"key": KEY})
    assert r.status_code == 200, r.text
    assert _shelved(api) == []
    a = _wait(lambda: _active(api).get(KEY))
    assert a["state"] == "active_unack"
    assert any(e[0] == "unshelve" and e[1] == "admin" and e[2] == "Genindsat af admin" for e in _events(api))
    assert [a["action"] for a in api.get("/api/audit?limit=50").json()].count("alarm.unshelve") == 1
    assert api.post("/api/alarms/unshelve", json={"key": KEY}).status_code == 404   # er ikke længere udsat


def test_unshelve_without_condition_leaves_no_alarm(api, mock_plc):
    _raise(api, mock_plc)
    _shelve(api)
    mock_plc.state.coils[4] = False
    time.sleep(0.5)
    assert api.post("/api/alarms/unshelve", json={"key": KEY}).status_code == 200
    time.sleep(0.6)
    assert KEY not in _active(api)


def test_expiry_raises_alarm_again_if_condition_holds(api, mock_plc):
    _raise(api, mock_plc)
    _shelve(api)
    svc = api.app.state.alarm_service
    svc.db._execute("UPDATE alarm_shelf SET until_ts = ?", (time.time() - 5,))
    a = _wait(lambda: _active(api).get(KEY))
    assert a["state"] == "active_unack" and _shelved(api) == []
    ev = [e for e in _events(api) if e[0] == "unshelve"]
    assert ev == [("unshelve", "", "Udsættelsen udløb")]


def test_expiry_without_condition_just_clears_shelf(api, mock_plc):
    _raise(api, mock_plc)
    _shelve(api)
    mock_plc.state.coils[4] = False
    svc = api.app.state.alarm_service
    svc.db._execute("UPDATE alarm_shelf SET until_ts = ?", (time.time() - 5,))
    _wait(lambda: _shelved(api) == [])
    time.sleep(0.5)
    assert KEY not in _active(api)


def test_delete_tag_removes_shelf_with_event(api, mock_plc):
    _raise(api, mock_plc)
    _shelve(api)
    assert api.delete("/api/tags/Fejl").status_code == 204
    assert _shelved(api) == [] and api.get("/api/alarms").json()["summary"]["shelved"] == 0
    assert api.app.state.alarm_service.db.list_alarm_shelf() == []
    assert [e for e in _events(api) if e[0] == "unshelve"] == [("unshelve", "", "Udsættelsen fjernet: tag slettet")]
    assert KEY not in _active(api)


def test_deleted_and_recreated_tag_is_not_hidden(api, mock_plc):
    _raise(api, mock_plc)
    _shelve(api)
    assert api.delete("/api/tags/Fejl").status_code == 204
    assert api.post("/api/tags", json={"name": "Fejl", "source": "plc1:coil:4", "alarm_on": "true",
                                       "description": "Motorfejl"}).status_code == 201
    a = _wait(lambda: _active(api).get(KEY))          # coil 4 er stadig sand: den nye alarm rejses, ikke skjult af den gamle udsættelse
    assert a["state"] == "active_unack" and _shelved(api) == []


def test_expiry_for_orphan_shelf_just_expires(api):
    svc = api.app.state.alarm_service
    svc.db.upsert_alarm_shelf({"key": "tag:Væk:state", "tag": "Væk", "plc": "plc1", "level": "ON", "priority": "high",
                               "message": "Væk: aktiv", "shelved_by": "admin", "shelved_at": time.time() - 100,
                               "until_ts": time.time() - 5, "reason": "gammel"})
    _wait(lambda: _shelved(api) == [])
    assert "tag:Væk:state" not in _active(api)
    assert _events(api, "tag:Væk:state") == [("unshelve", "", "Udsættelsen udløb")]


def test_forget_with_moved_to_moves_shelf_without_event(api, mock_plc):
    _raise(api, mock_plc)
    _shelve(api)
    svc = api.app.state.alarm_service
    svc.forget({"Fejl"}, plc="plc1", moved_to="plc2")
    assert [(r["key"], r["plc"]) for r in _shelved(api)] == [(KEY, "plc2")]
    assert _events(api) and not [e for e in _events(api) if e[0] == "unshelve"]
    time.sleep(0.5)
    assert KEY not in _active(api)                    # er stadig udsat


def test_plc_removal_removes_shelf_with_event(api, mock_plc):
    _raise(api, mock_plc)
    _shelve(api)
    r = api.post("/api/plcs/plc1/remove", json={"mode": "all", "confirm": "plc1"})
    assert r.status_code == 200, r.text
    assert _shelved(api) == [] and api.get("/api/alarms").json()["summary"]["shelved"] == 0
    assert [e for e in _events(api) if e[0] == "unshelve"] == [("unshelve", "", "Udsættelsen fjernet: PLC slettet")]


def test_expiry_while_server_is_down_unshelves_and_raises_at_first_tick(tmp_path, mock_plc):
    s = _settings(tmp_path)
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        c.post("/api/tags", json={"name": "Fejl", "source": "plc1:coil:4", "alarm_on": "true"})
        mock_plc.state.coils[4] = True
        _wait(lambda: _active(c).get(KEY))
        assert _shelve(c, minutes=5).status_code == 200
    import sqlite3
    con = sqlite3.connect(str(s.db_path))             # serveren er nede: tiden løber ud
    con.execute("UPDATE alarm_shelf SET until_ts = ?", (time.time() - 60,))
    con.commit()
    con.close()
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        a = _wait(lambda: _active(c).get(KEY))
        assert a["state"] == "active_unack" and _shelved(c) == []
        assert sorted(e[0] for e in _events(c)) == ["raise", "raise", "shelve", "unshelve"]
        assert [e for e in _events(c) if e[0] == "unshelve"] == [("unshelve", "", "Udsættelsen udløb")]


def test_shelf_survives_restart(tmp_path, mock_plc):
    s = _settings(tmp_path)
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        c.post("/api/tags", json={"name": "Fejl", "source": "plc1:coil:4", "alarm_on": "true"})
        mock_plc.state.coils[4] = True
        _wait(lambda: _active(c).get(KEY))
        assert _shelve(c).status_code == 200
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        time.sleep(1.0)
        assert [r["key"] for r in _shelved(c)] == [KEY]
        assert KEY not in _active(c)
        assert c.get("/api/alarms").json()["summary"]["shelved"] == 1


# ------------------------------------------------------------ rettigheder og scope

def _scoped_user(api, role):
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><text id="Fejl">-</text></svg>'
    did = api.post("/api/drawings", json={"name": "Motor", "svg": svg}).json()["drawing"]["id"]
    r = api.post("/api/users", json={"username": "vagt", "role": role, "password": "Hemmelig-123", "drawings": [did]})
    assert r.status_code == 201, r.text


def _login_as(c, username, password):
    assert c.post("/api/auth/login", json={"username": username, "password": password}).status_code == 200
    c.post("/api/auth/password", json={"old_password": password, "new_password": password + "-ny"})


def test_viewer_cannot_shelve_or_unshelve_but_can_read(api, mock_plc):
    _raise(api, mock_plc)
    _shelve(api)
    assert api.post("/api/users", json={"username": "se", "role": "viewer", "password": "Hemmelig-123"}).status_code == 201
    api.post("/api/auth/logout")
    _login_as(api, "se", "Hemmelig-123")
    assert _shelve(api).status_code == 403
    assert api.post("/api/alarms/unshelve", json={"key": KEY}).status_code == 403
    assert [r["key"] for r in _shelved(api)] == [KEY]
    assert api.get("/api/alarms").json()["summary"]["shelved"] == 1


def test_scoped_operator_cannot_touch_foreign_alarms(api, mock_plc):
    _scoped_user(api, "operator")
    mock_plc.state.hr[5] = 850
    mock_plc.state.coils[4] = True
    _wait(lambda: len(_active(api)) == 2)
    assert _shelve(api, key="tag:Temp:high").status_code == 200       # admin udsætter fremmed alarm (for vagt)
    api.post("/api/auth/logout")
    _login_as(api, "vagt", "Hemmelig-123")
    assert set(_active(api)) == {KEY}
    assert _shelved(api) == [] and api.get("/api/alarms").json()["summary"]["shelved"] == 0
    r = api.post("/api/alarms/unshelve", json={"key": "tag:Temp:high"})
    assert r.status_code == 404 and r.json()["error"] == "Alarmen findes ikke"
    r = _shelve(api, key="tag:Temp:high")           # samme svar som for en ukendt nøgle (ingen lækage)
    assert r.status_code == 404 and r.json()["error"] == "Alarmen findes ikke"
    # egen alarm kan udsættes og genindsættes
    assert _shelve(api).status_code == 200
    assert [r["key"] for r in _shelved(api)] == [KEY]
    assert api.post("/api/alarms/unshelve", json={"key": KEY}).status_code == 200
    # den fremmede er stadig udsat
    svc = api.app.state.alarm_service
    assert [r["key"] for r in svc.shelved(None)] == ["tag:Temp:high"]


def test_scoped_viewer_sees_only_own_shelved_in_list_and_summary(api, mock_plc):
    _scoped_user(api, "viewer")
    mock_plc.state.hr[5] = 850
    mock_plc.state.coils[4] = True
    _wait(lambda: len(_active(api)) == 2)
    assert _shelve(api, key="tag:Temp:high").status_code == 200      # fremmed for vagt
    api.post("/api/auth/logout")
    _login_as(api, "vagt", "Hemmelig-123")
    assert _shelved(api) == [] and api.get("/api/alarms").json()["summary"]["shelved"] == 0
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    assert _shelve(api).status_code == 200                            # egen for vagt
    api.post("/api/auth/logout")
    assert api.post("/api/auth/login", json={"username": "vagt", "password": "Hemmelig-123-ny"}).status_code == 200
    assert [r["key"] for r in _shelved(api)] == [KEY]
    assert api.get("/api/alarms").json()["summary"]["shelved"] == 1


# --------------------------------------------------------------- integrations-SSE

def test_integration_stream_gets_clear_on_shelve_and_raise_again_on_unshelve(api, mock_plc):
    from app.services.integration import Principal
    isvc = api.app.state.integration_service
    s = isvc.open_stream(Principal("k_t", "test", {"all": True, "tags": [], "prefixes": []}), "1.1.1.1")
    try:
        def drain():
            out = []
            while not s.alarm_q.empty():
                out.append(s.alarm_q.get_nowait())
            return out

        _raise(api, mock_plc)
        _wait(lambda: s.alarm_q.qsize() >= 1)
        assert [e["event"] for e in drain()] == ["raise"]
        assert _shelve(api, reason="Hemmelig begrundelse").status_code == 200
        got = drain()
        assert [e["event"] for e in got] == ["clear"] and got[0]["alarm"]["key"] == KEY
        assert "Hemmelig begrundelse" not in str(got) and "Udsat" not in str(got)   # klienten ser alarmens egen tekst, ikke begrundelsen
        assert got[0]["alarm"]["message"] == "Motorfejl: aktiv"
        assert api.post("/api/alarms/unshelve", json={"key": KEY}).status_code == 200
        _wait(lambda: s.alarm_q.qsize() >= 1)
        assert [e["event"] for e in drain()] == ["raise"]                 # genindsat og betingelsen holder: ny raise
    finally:
        isvc.close_stream(s)


# --------------------------------------------------------------- summary, metrics, historik

def test_summary_shelved_counts_and_sorted_by_until(api, mock_plc):
    mock_plc.state.hr[5] = 850
    mock_plc.state.coils[4] = True
    _wait(lambda: len(_active(api)) == 2)
    assert _shelve(api, key="tag:Temp:high", minutes=120).status_code == 200
    assert _shelve(api, minutes=10).status_code == 200
    assert api.get("/api/alarms").json()["summary"] == {"active": 0, "unacked": 0, "high": 0, "shelved": 2}
    assert [r["key"] for r in _shelved(api)] == [KEY, "tag:Temp:high"]


def test_metrics_gauge_for_shelved():
    text = render({"alarms": {"active": 1, "unacked": 0, "high": 0, "shelved": 3}})
    assert "scada_alarms_shelved 3" in text
    assert "scada_alarms_shelved 0" in render({"alarms": {"shelved": 0}})   # 0 er en gyldig værdi


def test_health_details_carries_shelved(api, mock_plc):
    _raise(api, mock_plc)
    _shelve(api)
    r = api.get("/api/health/details")
    assert r.status_code == 200 and r.json()["alarms"]["shelved"] == 1


def test_history_filters_on_shelve_and_unshelve(api, mock_plc):
    _raise(api, mock_plc)
    _shelve(api)
    api.post("/api/alarms/unshelve", json={"key": KEY})
    sh = api.get("/api/alarms/history", params={"event": "shelve"}).json()
    un = api.get("/api/alarms/history", params={"event": "unshelve"}).json()
    assert [e["event"] for e in sh] == ["shelve"] and [e["event"] for e in un] == ["unshelve"]
    csv = api.get("/api/alarms/history/export", params={"event": "shelve"}).text
    assert "Udsat" in csv
    csv = api.get("/api/alarms/history/export", params={"event": "unshelve"}).text
    assert "Genindsat" in csv
    assert api.get("/api/alarms/history", params={"event": "bogus"}).status_code == 400


# ------------------------------------------------------------ eskalering bryder igennem

def _escalation_events(c, key):
    return [e for e in _events(c, key) if e[0] == "unshelve"]


def test_escalation_h_to_hh_breaks_through_shelf(api, mock_plc):
    key = "tag:Temp:high"
    mock_plc.state.hr[5] = 850
    _wait(lambda: _active(api).get(key))
    assert _shelve(api, key=key).status_code == 200
    assert api.get("/api/alarms").json()["summary"]["shelved"] == 1
    mock_plc.state.hr[5] = 950   # HH
    a = _wait(lambda: _active(api).get(key))
    assert a["level"] == "HH" and a["state"] == "active_unack"
    assert _shelved(api) == []
    summary = api.get("/api/alarms").json()["summary"]
    assert summary["shelved"] == 0 and "scada_alarms_shelved 0" in render({"alarms": summary})
    assert _escalation_events(api, key) == [("unshelve", "", "Udsættelsen ophævet: alarmen er steget til HH")]


def test_escalation_l_to_ll_breaks_through_shelf(api, mock_plc):
    key = "tag:Niv:low"
    mock_plc.state.hr[6] = 250
    assert api.post("/api/tags", json={"name": "Niv", "source": "plc1:hr:6", "scale": 0.1, "unit": "m",
                                       "alarm_l": 20, "alarm_ll": 10}).status_code == 201
    _wait(lambda: api.get("/api/live?tags=Niv").json()["values"]["Niv"]["quality"] == "good")
    mock_plc.state.hr[6] = 150   # L
    _wait(lambda: _active(api).get(key))
    assert _shelve(api, key=key).status_code == 200
    mock_plc.state.hr[6] = 50    # LL
    a = _wait(lambda: _active(api).get(key))
    assert a["level"] == "LL" and a["state"] == "active_unack" and _shelved(api) == []
    assert _escalation_events(api, key) == [("unshelve", "", "Udsættelsen ophævet: alarmen er steget til LL")]


def test_unchanged_level_stays_shelved(api, mock_plc):
    key = "tag:Temp:high"
    mock_plc.state.hr[5] = 850
    _wait(lambda: _active(api).get(key))
    assert _shelve(api, key=key).status_code == 200
    mock_plc.state.hr[5] = 860   # stadig H
    time.sleep(1.0)
    assert key not in _active(api) and [r["key"] for r in _shelved(api)] == [key]
    assert _escalation_events(api, key) == []


def test_lower_severity_stays_shelved(api, mock_plc):
    key = "tag:Temp:high"
    mock_plc.state.hr[5] = 950   # HH
    _wait(lambda: (_active(api).get(key) or {}).get("level") == "HH")
    assert _shelve(api, key=key).status_code == 200
    mock_plc.state.hr[5] = 850   # falder til H
    time.sleep(1.0)
    assert key not in _active(api) and [r["key"] for r in _shelved(api)] == [key]
    assert _escalation_events(api, key) == []


def test_on_off_alarm_never_breaks_through(api, mock_plc):
    _raise(api, mock_plc)
    assert _shelve(api).status_code == 200
    time.sleep(1.0)
    assert KEY not in _active(api) and [r["key"] for r in _shelved(api)] == [KEY]


def test_escalation_with_alarm_delay_unshelves_at_once_and_raises_after_delay(api, mock_plc):
    key = "tag:Temp:high"
    assert api.patch("/api/tags/Temp", json={"alarm_delay_s": 0.5}).status_code == 200
    mock_plc.state.hr[5] = 850
    _wait(lambda: _active(api).get(key))              # H, efter forsinkelsen
    assert _shelve(api, key=key).status_code == 200
    mock_plc.state.hr[5] = 950                        # HH
    _wait(lambda: _shelved(api) == [])                # udsættelsen ophæves straks
    assert _escalation_events(api, key) == [("unshelve", "", "Udsættelsen ophævet: alarmen er steget til HH")]
    a = _wait(lambda: _active(api).get(key))          # og alarmen rejses efter forsinkelsen
    assert a["level"] == "HH" and a["state"] == "active_unack"
    assert [e[0] for e in _events(api, key)].count("raise") == 2


# ------------------------------------------- eskalering via prioritet

def _set_priority(api, value):
    assert api.patch("/api/tags/Fejl", json={"alarm_priority": value}).status_code == 200


def test_priority_increase_breaks_through_shelf(api, mock_plc):
    _set_priority(api, "low")
    _raise(api, mock_plc)
    assert _shelve(api).status_code == 200
    assert _shelved(api)[0]["priority"] == "low"
    _set_priority(api, "high")
    a = _wait(lambda: _active(api).get(KEY))
    assert a["priority"] == "high" and a["state"] == "active_unack" and _shelved(api) == []
    assert _escalation_events(api, KEY) == [("unshelve", "", "Udsættelsen ophævet: prioriteten er steget til Høj")]
    assert api.get("/api/alarms").json()["summary"]["shelved"] == 0


def test_priority_low_to_medium_names_medium(api, mock_plc):
    _set_priority(api, "low")
    _raise(api, mock_plc)
    _shelve(api)
    _set_priority(api, "medium")
    _wait(lambda: _active(api).get(KEY))
    assert _escalation_events(api, KEY) == [("unshelve", "", "Udsættelsen ophævet: prioriteten er steget til Medium")]


def test_lower_or_unchanged_priority_stays_shelved(api, mock_plc):
    _set_priority(api, "medium")
    _raise(api, mock_plc)
    assert _shelve(api).status_code == 200
    _set_priority(api, "low")                         # lavere
    time.sleep(1.0)
    assert KEY not in _active(api) and [r["key"] for r in _shelved(api)] == [KEY]
    _set_priority(api, "low")                         # uændret
    time.sleep(0.6)
    assert KEY not in _active(api) and [r["key"] for r in _shelved(api)] == [KEY]
    assert _escalation_events(api, KEY) == []
