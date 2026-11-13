"""Hjælperen, fase 3 (v4.10.0): beskrivelser til nye tags, forslag til symbolguidens signaler og døgnets alarmer."""

import time

from app.services.assist_setup import UNITS, validate_signals, validate_tags
from app.services.assist_tools import AssistTools, dur
from tests.drawing_api import _events, _llm, api  # noqa: F401 — fixture

ITEMS = [{"name": "T_FREMLOEB", "datatype": "REAL", "origin": "Logic1"}, {"name": "P1_KOERER", "datatype": "BOOL"}]


def test_describe_tags_fills_valid_suggestions_only(api):
    seen = _llm(api, {"svar": [
        {"navn": "T_FREMLOEB", "beskrivelse": "Fremløbstemperatur <data>", "enhed": "°C"},
        {"navn": "P1_KOERER", "beskrivelse": "  ", "enhed": ""},                       # tom beskrivelse: udelades
        {"navn": "T_FREMLOEB", "beskrivelse": "dublet", "enhed": "%"},
    ]})
    r = api.post("/api/assist/describe-tags", json={"items": ITEMS})
    assert r.status_code == 200, r.text
    done = _events(r)[-1]
    assert done["type"] == "done" and done["asked"] == 2
    assert done["suggestions"] == [{"name": "T_FREMLOEB", "description": "Fremløbstemperatur data", "unit": "°C"}]
    body = seen[-1]
    props = body["response_format"]["json_schema"]["schema"]["properties"]["svar"]["items"]["properties"]
    assert props["navn"]["enum"] == ["T_FREMLOEB", "P1_KOERER"] and props["enhed"]["enum"] == UNITS
    prompt = body["messages"][-1]["content"]
    assert "- T_FREMLOEB (REAL) — Logic1" in prompt and "- P1_KOERER (BOOL)" in prompt
    assert api.get("/api/tags/T_FREMLOEB").status_code == 404                     # intet oprettet
    assert api.app.state.assistant._asking == {}
    assert "assist.describe_tags" in [a["action"] for a in api.get("/api/audit?limit=20").json()]


def test_describe_tags_rejects_bad_names_and_needs_engineer(api):
    _llm(api, {"svar": []})
    assert api.post("/api/assist/describe-tags", json={"items": [{"name": "1 slet alt;"}]}).status_code == 400
    assert api.post("/api/assist/describe-tags", json={"items": []}).status_code == 422
    api.post("/api/users", json={"username": "op", "password": "Operator-pw-123", "role": "operator"})
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "op", "password": "Operator-pw-123"})
    assert api.post("/api/assist/describe-tags", json={"items": ITEMS}).status_code == 403


def test_validate_tags_keeps_units_from_the_list():
    assert validate_tags({"svar": [{"navn": "A", "beskrivelse": "x", "enhed": "furlongs"}]}, ["A"]) == \
        [{"name": "A", "description": "x", "unit": ""}]
    assert validate_tags("ikke json", ["A"]) == []


def test_symbol_signals_suggests_writable_command_and_feedback(api):
    assert api.post("/api/tags", json={"name": "P1_start", "source": "plc1:coil:9", "writable": True,
                                        "description": "Start pumpe 1"}).status_code == 201
    seen = _llm(api, {"svar": [{"signal": "S1", "kommando": "P1_start", "tilbagemelding": "P1_drift"},
                               {"signal": "S2", "kommando": "Ekstra", "tilbagemelding": ""}]})   # Ekstra er ikke skrivbar
    r = api.post("/api/assist/symbol-signals", json={"drawing": api.d, "element": "p1", "text": "start og driftmelding",
                                                     "signals": ["S1", "S2"], "op": "positions", "positions": ["Stop", "Start"]})
    assert r.status_code == 200, r.text
    done = _events(r)[-1]
    assert done["suggestions"] == [{"id": "S1", "tag": "P1_start", "fb": "P1_drift"}] and done["asked"] == 2
    body = seen[-1]
    props = body["response_format"]["json_schema"]["schema"]["properties"]["svar"]["items"]["properties"]
    assert props["kommando"]["enum"] == ["P1_start", ""] and "P1_drift" in props["tilbagemelding"]["enum"]
    prompt = body["messages"][-1]["content"]
    assert "Symbol: P1 (betjeningsform: positioner)" in prompt and "Positioner: Stop, Start" in prompt
    assert "P1_start (til/fra, skrivbar) — Start pumpe 1" in prompt and "plc1" not in prompt
    assert api.get(f"/api/drawings/{api.d}/symbols/p1/config").json()["config"] is None   # intet gemt


def test_symbol_signals_rules(api):
    _llm(api, {"svar": []})
    base = {"drawing": api.d, "element": "p1", "signals": ["S1"]}
    assert api.post("/api/assist/symbol-signals", json={**base, "drawing": "findes-ikke"}).status_code == 404
    assert api.post("/api/assist/symbol-signals", json={**base, "element": "nope"}).status_code == 404
    assert api.post("/api/assist/symbol-signals", json={**base, "signals": ["X; drop"]}).status_code == 400
    assert api.post("/api/assist/symbol-signals", json={**base, "text": "x" * 401}).status_code == 400


def test_validate_signals_view_has_no_command():
    tags = {"A": {"writable": True}, "B": {}}
    assert validate_signals({"svar": [{"signal": "S1", "kommando": "A", "tilbagemelding": "B"}]}, ["S1"], tags, False) == \
        [{"id": "S1", "tag": "", "fb": "B"}]
    assert validate_signals({"svar": [{"signal": "S1", "kommando": "A", "tilbagemelding": "A"}]}, ["S1"], tags, True) == \
        [{"id": "S1", "tag": "A", "fb": ""}]                                      # samme tag som tilbagemelding: nej


class _Alarms:
    def __init__(self, rows):
        self.rows = rows

    def history(self, limit, visible):
        return [r for r in self.rows if visible is None or r["tag"] in visible][::-1]


class _Scope:
    def __init__(self, visible):
        self.visible = visible

    def visible_tags(self, user):
        return self.visible


def test_alarm_summary_counts_durations_and_acks():
    now = 100_000.0
    ev = lambda ts, key, e, tag="T1", prio="medium", msg="Høj temp": {  # noqa: E731
        "id": int(ts), "ts": now - ts, "key": key, "tag": tag, "plc": "p", "level": "H", "priority": prio, "event": e,
        "message": msg, "username": ""}
    rows = [ev(30000, "a", "raise"), ev(29400, "a", "ack"), ev(28800, "a", "clear"),
            ev(20000, "a", "raise"), ev(19000, "a", "clear"),
            ev(5000, "b", "raise", tag="T2", prio="high", msg="Tryk lavt"),
            ev(200000, "c", "raise", msg="Gammel")]                                  # ældre end et døgn: tæller ikke
    tools = AssistTools(alarms=_Alarms(rows), tags=None, cache=None, trend_db=None, scope=_Scope(None), symbols=None,
                        drawings=None, manual=None)
    text = tools.alarm_summary(object(), now)
    assert text.splitlines()[0] == ("De seneste 24 timer: 3 alarmer opstod, fordelt på 2 forskellige (1 med høj prioritet). "
                                    "1 er stadig aktive.")
    assert "- Høj temp (prioritet medium): opstod 2 gang(e), aktiv i alt 37 min, kvitteret efter gns. 10 min" in text
    assert "- Tryk lavt (prioritet high): opstod 1 gang(e), aktiv i alt 83 min, ikke kvitteret, stadig aktiv" in text
    assert "Gammel" not in text
    limited = AssistTools(alarms=_Alarms(rows), tags=None, cache=None, trend_db=None, scope=_Scope({"T2"}), symbols=None,
                          drawings=None, manual=None)
    assert "Høj temp" not in limited.alarm_summary(object(), now)                  # kun det, brugeren må se
    assert AssistTools(alarms=_Alarms([]), tags=None, cache=None, trend_db=None, scope=_Scope(None), symbols=None,
                       drawings=None, manual=None).alarm_summary(object(), now) == "Ingen alarmhændelser de seneste 24 timer."
    assert (dur(45), dur(600), dur(3 * 3600 + 300)) == ("45 s", "10 min", "3 t 5 min")


class _Manual:
    def search(self, q, k):
        return []


def test_summary_context_adds_the_day_to_the_data():
    from app.services.assist_tools import Context
    now = 100_000.0
    rows = [{"id": 1, "ts": now - 60, "key": "a", "tag": "T1", "plc": "p", "level": "H", "priority": "high", "event": "raise",
             "message": "Høj temp", "username": ""}]
    tools = AssistTools(alarms=_Alarms(rows), tags=None, cache=None, trend_db=None, scope=_Scope(None), symbols=None,
                        drawings=None, manual=_Manual())
    tools.active_alarms = lambda user, now: "1 aktiv"
    tools.mentioned_tags = lambda user, q: []
    g = tools.gather(_User(), "opsummér døgnet", Context(page="alarms", summary=True), now)
    assert "alarm_resume" in g.tools and ("Alarmer det seneste døgn", tools.alarm_summary(_User(), now)) in g.blocks
    assert {"label": "Alarmer › Historik", "href": "#alarms"} in g.sources
    assert "soeg_manual" not in g.tools                                           # kun tallene (kort prompt)


class _User:
    username, role = "admin", "admin"
