"""Alarmrationalisering (v6.20.0, B6): konsekvens, handling og svartid pr. tag-alarm."""

import pytest

from tests.test_alarm_shelf import _login_as, _scoped_user  # noqa: F401
from tests.test_alarms import ADMIN_PW, _active, _wait, api  # noqa: F401


def _patch(api, **kw):
    return api.patch("/api/tags/Temp", json=kw)


@pytest.mark.parametrize("field", ["alarm_consequence", "alarm_action"])
def test_text_fields_normalised(api, field):
    r = _patch(api, **{field: "  Kedlen   går   i  trip  "})
    assert r.status_code == 200, r.text
    assert r.json()[field] == "Kedlen går i trip"
    for empty in ("", "   ", None):
        assert _patch(api, **{field: empty}).json()[field] is None
    assert _patch(api, **{field: "x" * 200}).status_code == 200
    r = _patch(api, **{field: "x" * 201})
    assert r.status_code == 400 and "200" in r.json()["error"]
    assert _patch(api, **{field: "æ" * 200}).status_code == 200      # kodepunkter, ikke bytes
    assert _patch(api, **{field: "æ" * 201}).status_code == 400


@pytest.mark.parametrize("value", ["a\nb", "a\tb", "a\x00b", "a​b", "a‮b", "a\rb"])
def test_text_fields_reject_control_chars(api, value):
    for field in ("alarm_consequence", "alarm_action"):
        r = _patch(api, **{field: value})
        assert r.status_code == 400 and "kontroltegn" in r.json()["error"], r.text
    assert api.get("/api/tags/Temp").json()["alarm_consequence"] is None


@pytest.mark.parametrize("value", [5, True, ["a"]])
def test_text_fields_reject_non_strings(api, value):
    r = _patch(api, alarm_consequence=value)
    assert r.status_code in (400, 422), r.text


@pytest.mark.parametrize("value", [0, 1, 1440])
def test_response_min_valid(api, value):
    r = _patch(api, alarm_response_min=value)
    assert r.status_code == 200 and r.json()["alarm_response_min"] == value   # 0 er gyldigt
    assert api.get("/api/tags/Temp").json()["alarm_response_min"] == value


@pytest.mark.parametrize("value", [-1, 1441, True, False, "5", 5.5, 5.0, [5]])
def test_response_min_invalid(api, value):
    assert _patch(api, alarm_response_min=10).status_code == 200
    r = _patch(api, alarm_response_min=value)
    assert r.status_code in (400, 422), r.text
    if r.status_code == 400:
        assert "Svartid" in r.json()["error"]
    assert api.get("/api/tags/Temp").json()["alarm_response_min"] == 10   # uændret


def test_response_min_null_clears_and_omitted_keeps(api):
    _patch(api, alarm_response_min=0, alarm_action="Tjek pumpen")
    assert _patch(api, alarm_h=79).json()["alarm_response_min"] == 0          # andre rettelser rører den ikke
    assert api.get("/api/tags/Temp").json()["alarm_action"] == "Tjek pumpen"
    assert _patch(api, alarm_response_min=None).json()["alarm_response_min"] is None


def test_create_with_rationale_and_default_none(api):
    r = api.post("/api/tags", json={"name": "Ny", "source": "plc1:hr:7", "alarm_h": 5, "alarm_action": " Ring vagten ",
                                    "alarm_response_min": 15})
    assert r.status_code == 201, r.text
    assert (r.json()["alarm_action"], r.json()["alarm_response_min"], r.json()["alarm_consequence"]) == ("Ring vagten", 15, None)
    assert api.post("/api/tags", json={"name": "Ny2", "source": "plc1:hr:8", "alarm_response_min": 2000}).status_code == 400
    tags = {t["name"]: t for t in api.get("/api/tags").json()["tags"]} if isinstance(api.get("/api/tags").json(), dict) \
        else {t["name"]: t for t in api.get("/api/tags").json()}
    assert tags["Ny"]["alarm_response_min"] == 15 and tags["Temp"]["alarm_response_min"] is None


def test_active_list_live_lookup(api, mock_plc):
    _patch(api, alarm_consequence="Kedlen stopper", alarm_action="Åbn ventil V2", alarm_response_min=0)
    mock_plc.state.hr[5] = 850
    a = _wait(lambda: _active(api).get("tag:Temp:high"))
    assert (a["consequence"], a["action"], a["response_min"]) == ("Kedlen stopper", "Åbn ventil V2", 0)
    api.post("/api/alarms/ack", json={"keys": ["tag:Temp:high"]})
    # ændring slår igennem uden ny alarm
    before = len(api.get("/api/alarms/history").json())
    _patch(api, alarm_action="Ring til vagten", alarm_response_min=None)
    a = _active(api)["tag:Temp:high"]
    assert a["action"] == "Ring til vagten" and a["response_min"] is None and a["state"] == "active_ack"
    assert len(api.get("/api/alarms/history").json()) == before


def test_active_list_none_for_non_tag_alarms(api, mock_plc):
    svc = api.app.state.alarm_service
    row = {"key": "plc:plc1:comm", "tag": None, "plc": "plc1", "kind": "comm", "level": "COMM", "priority": "high",
           "state": "active_unack", "raised_at": 1.0, "value": None, "message": "x", "acked_by": None, "acked_at": None}
    out = svc._with_rationale(row)
    assert (out["consequence"], out["action"], out["response_min"]) == (None, None, None)
    assert "consequence" not in row                       # kopi, ikke gemt i alarm_state
    mock_plc.state.coils[4] = True
    a = _wait(lambda: _active(api).get("tag:Fejl:state"))
    assert (a["consequence"], a["action"], a["response_min"]) == (None, None, None)


def test_rationale_in_backup_roundtrip(api):
    _patch(api, alarm_consequence="Kedlen stopper", alarm_action="Åbn V2", alarm_response_min=30)
    backup = api.get("/api/backup").json()
    t = next(x for x in backup["tags"] if x["name"] == "Temp")
    assert (t["alarm_consequence"], t["alarm_action"], t["alarm_response_min"]) == ("Kedlen stopper", "Åbn V2", 30)
    _patch(api, alarm_consequence=None, alarm_action=None, alarm_response_min=None)
    assert api.post("/api/backup/restore", json=backup).status_code == 200
    got = api.get("/api/tags/Temp").json()
    assert (got["alarm_consequence"], got["alarm_action"], got["alarm_response_min"]) == ("Kedlen stopper", "Åbn V2", 30)


@pytest.mark.parametrize("field,value", [("alarm_response_min", 1441), ("alarm_response_min", True), ("alarm_response_min", "5"),
                                         ("alarm_action", "a\nb"), ("alarm_consequence", "x" * 201), ("alarm_action", 5)])
def test_backup_restore_rejects_invalid_rationale(api, field, value):
    backup = api.get("/api/backup").json()
    next(x for x in backup["tags"] if x["name"] == "Temp")[field] = value
    r = api.post("/api/backup/restore", json=backup)
    assert r.status_code == 400 and "alarm" in r.json()["error"].lower(), r.text


def test_old_backup_without_fields_restores_as_none(api):
    backup = api.get("/api/backup").json()
    for t in backup["tags"]:
        for k in ("alarm_consequence", "alarm_action", "alarm_response_min"):
            t.pop(k, None)
    assert api.post("/api/backup/restore", json=backup).status_code == 200
    assert api.get("/api/tags/Temp").json()["alarm_response_min"] is None


def test_scoped_user_sees_only_own_alarms_with_rationale(api, mock_plc):
    _scoped_user(api, "viewer")
    _patch(api, alarm_action="Kun admin-synlig alarm")
    api.patch("/api/tags/Fejl", json={"alarm_action": "Stop motor"})
    mock_plc.state.hr[5] = 850
    mock_plc.state.coils[4] = True
    _wait(lambda: len(_active(api)) == 2)
    api.post("/api/auth/logout")
    _login_as(api, "vagt", "Hemmelig-123")
    act = _active(api)
    assert set(act) == {"tag:Fejl:state"} and act["tag:Fejl:state"]["action"] == "Stop motor"


def test_assist_alarm_text_includes_rationale(api, mock_plc):
    from app.services.assist_tools import AssistTools
    _patch(api, alarm_consequence="Kedlen stopper", alarm_action="Åbn V2", alarm_response_min=10)
    mock_plc.state.hr[5] = 850
    _wait(lambda: _active(api).get("tag:Temp:high"))
    svc = api.app.state.alarm_service
    tools = AssistTools.__new__(AssistTools)
    tools.alarms = svc
    tools._visible = lambda user: None
    text, tag, _ = tools.alarm(None, "tag:Temp:high", 1e10)
    assert "Konsekvens: Kedlen stopper" in text and "Foreskrevet handling: Åbn V2" in text and "Svartid: 10 min" in text
    assert tag == "Temp"
