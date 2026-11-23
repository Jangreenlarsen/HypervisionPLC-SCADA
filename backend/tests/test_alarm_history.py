"""Alarmhistorik: søgning, filtre, system, adgang pr. tegning og CSV-eksport."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient  # noqa: F401  (fixturen `api` kommer fra test_alarms)

from app.services.schedule_engine import TZ
from tests.test_alarms import ADMIN_PW, api  # noqa: F401


def _ts(text: str) -> float:
    return datetime.fromisoformat(text).replace(tzinfo=TZ).timestamp()


def _add(api, ts, key, tag, plc, level, priority, event, message, value=None, username=""):
    api.app.state.alarm_service.db.insert_alarm_event(
        {"ts": _ts(ts), "key": key, "tag": tag, "plc": plc, "level": level, "priority": priority, "event": event,
         "value": value, "username": username, "message": message}, 50_000)


@pytest.fixture
def seeded(api):
    _add(api, "2026-11-01T10:00:00", "tag:Temp:high", "Temp", "plc1", "H", "medium", "raise", "Kedeltemperatur for høj", 85.5)
    _add(api, "2026-11-02T12:00:00", "tag:Temp:high", "Temp", "plc1", "H", "medium", "ack", "Kedeltemperatur for høj", 85.5, "jan")
    _add(api, "2026-11-03T08:30:00", "tag:Fejl:state", "Fejl", "plc1", "ON", "high", "raise", "Motorfejl ÆØ", True)
    _add(api, "2026-11-04T09:00:00", "tag:Fejl:state", "Fejl", "plc1", "ON", "high", "clear", "Motorfejl ÆØ", False)
    _add(api, "2026-11-05T09:00:00", "plc:plc1:comm", "", "plc1", "COMM", "high", "raise", "plc1: kommunikation tabt")
    _add(api, "2026-11-06T09:00:00", "sym:ukendt:x:alarm", "", "", "AFV", "low", "raise", "Symbolafvigelse")
    return api


def _h(c, **params):
    r = c.get("/api/alarms/history", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _msgs(rows):
    return sorted(r["message"] for r in rows)


def test_no_filter_returns_all_newest_first(seeded):
    rows = _h(seeded)
    assert len(rows) == 6 and rows[0]["message"] == "Symbolafvigelse"


def test_q_matches_tag_plc_message_case_insensitive_and_blank_is_nofilter(seeded):
    assert len(_h(seeded, q="temp")) == 2                     # tag
    assert len(_h(seeded, q="PLC1")) == 5                     # plc + besked (case-insensitive)
    assert len(_h(seeded, q="kommunikation")) == 1            # besked
    assert len(_h(seeded, q="motorfejl æø")) == 2             # ikke-ASCII
    assert len(_h(seeded, q="   ")) == 6 and len(_h(seeded, q="")) == 6


def test_q_wildcards_are_literal(seeded):
    assert _h(seeded, q="%") == [] and _h(seeded, q="_") == []


def test_date_range_inclusive_and_date_only_covers_whole_day(seeded):
    assert len(_h(seeded, **{"from": "2026-11-03", "to": "2026-11-04"})) == 2
    assert len(_h(seeded, **{"to": "2026-11-01"})) == 1       # hele dagen den 1.
    assert len(_h(seeded, **{"from": "2026-11-05"})) == 2
    assert len(_h(seeded, **{"from": "2026-11-03T08:30:00", "to": "2026-11-03T08:30:00"})) == 1   # begge inklusive
    assert len(_h(seeded, **{"from": "2026-11-03T08:30:01", "to": "2026-11-03T09:00:00"})) == 0


def test_event_and_priority(seeded):
    assert len(_h(seeded, event="raise")) == 4
    assert len(_h(seeded, event="ack")) == 1 and len(_h(seeded, event="clear")) == 1
    assert len(_h(seeded, priority="high")) == 3 and len(_h(seeded, priority="low")) == 1


def test_combined_filters(seeded):
    rows = _h(seeded, q="motorfejl", event="raise", priority="high", **{"from": "2026-11-01", "to": "2026-11-03"})
    assert [r["event"] for r in rows] == ["raise"] and rows[0]["tag"] == "Fejl"
    assert _h(seeded, q="temp", priority="high") == []


@pytest.mark.parametrize("params, text", [
    ({"from": "i går"}, "Ugyldig 'from'"),
    ({"to": "2026-13-45"}, "Ugyldig 'to'"),
    ({"from": "2026-11-05", "to": "2026-11-01"}, "efter"),
    ({"event": "slet"}, "Ukendt hændelse"),
    ({"priority": "kritisk"}, "Ukendt prioritet"),
])
def test_invalid_values_give_400_in_danish(seeded, params, text):
    for url in ("/api/alarms/history", "/api/alarms/history/export"):
        r = seeded.get(url, params=params)
        assert r.status_code == 400 and text in r.json()["error"], r.text


def test_limit_is_clamped(seeded):
    assert len(_h(seeded, limit=2)) == 2
    assert len(_h(seeded, limit=0)) == 1 and len(_h(seeded, limit=-5)) == 1
    assert len(_h(seeded, limit=99999)) == 6


def _drawing(api, name, tag):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><text id="{tag}">-</text></svg>'
    r = api.post("/api/drawings", json={"name": name, "svg": svg})
    assert r.status_code in (200, 201), r.text
    return r.json()["drawing"]["id"]


def test_system_filter(seeded):
    motor, kedel = _drawing(seeded, "Motor", "Fejl"), _drawing(seeded, "Kedel", "Temp")
    assert _msgs(_h(seeded, system=motor)) == sorted(["Motorfejl ÆØ", "Motorfejl ÆØ", "plc1: kommunikation tabt"])
    assert len(_h(seeded, system=kedel)) == 3                  # 2 tag-hændelser + PLC-forbindelse
    # symbolalarm på en tegning, der ikke findes, hører ikke til noget system
    assert "Symbolafvigelse" not in _msgs(_h(seeded, system=motor))
    assert _msgs(_h(seeded, system="-")) == sorted(["plc1: kommunikation tabt", "Symbolafvigelse"])
    _add(seeded, "2026-11-07T09:00:00", f"sym:{motor}:x:alarm", "", "", "AFV", "low", "raise", "Symbol på motor")
    assert "Symbol på motor" in _msgs(_h(seeded, system=motor))
    assert "Symbol på motor" not in _msgs(_h(seeded, system=kedel))
    assert "Symbol på motor" not in _msgs(_h(seeded, system="-"))
    assert len(_h(seeded, system=motor, event="clear")) == 1   # kombineret med andre filtre


def _scoped_client(api, mock_plc):
    did = _drawing(api, "Motor", "Fejl")
    r = api.post("/api/users", json={"username": "vagt", "role": "viewer", "password": "Hemmelig-123", "drawings": [did]})
    assert r.status_code == 201, r.text
    from app.config import Settings  # noqa: F401
    assert api.post("/api/auth/login", json={"username": "vagt", "password": "Hemmelig-123"}).status_code == 200
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})


def test_scoped_user_only_gets_own_events_in_list_and_export(seeded, mock_plc):
    _scoped_client(seeded, mock_plc)
    rows = _h(seeded)
    assert rows and {r["tag"] for r in rows} <= {"Fejl", ""} and "Temp" not in {r["tag"] for r in rows}
    assert not any(r["message"].startswith("Kedel") for r in rows)
    assert len(_h(seeded, q="temp")) == 0                      # filtre gælder ovenpå adgangen
    assert len(_h(seeded, q="motorfejl")) == 2
    csv_text = seeded.get("/api/alarms/history/export").content.decode("utf-8")
    assert "Kedeltemperatur" not in csv_text and "Motorfejl" in csv_text


def test_export_csv_format_and_content(seeded):
    r = seeded.get("/api/alarms/history/export", params={"event": "raise"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv") and "utf-8" in r.headers["content-type"]
    assert r.headers["content-disposition"].startswith('attachment; filename="alarmer-') and ".csv" in r.headers["content-disposition"]
    text = r.content.decode("utf-8")
    assert text.startswith("﻿")
    lines = text.lstrip("﻿").strip().splitlines()
    assert lines[0] == "Tid;Tag;PLC;Type;Prioritet;Hændelse;Værdi;Bruger;Besked"
    assert len(lines) == 1 + 4
    by_msg = {ln.split(";")[8]: ln.split(";") for ln in lines[1:]}
    kedel = by_msg["Kedeltemperatur for høj"]
    assert kedel[0] == "2026-11-01T10:00:00.000+01:00" and kedel[1] == "Temp" and kedel[5] == "Opstået" and kedel[6] == "85,5"
    comm = by_msg["plc1: kommunikation tabt"]
    assert comm[1] == "" and comm[6] == "" and comm[7] == ""   # tomme celler for tag, værdi og bruger
    rows = [ln.split(";") for ln in seeded.get("/api/alarms/history/export", params={"event": "ack"}).content.decode("utf-8").strip().splitlines()]
    assert rows[1][7] == "jan"


def test_export_has_no_2000_limit_and_respects_filters(seeded):
    db = seeded.app.state.alarm_service.db
    with db._lock:
        db._conn.execute("BEGIN")
        for i in range(2100):
            db._conn.execute("INSERT INTO alarm_events(ts, key, tag, plc, level, priority, event, value, username, message) "
                             "VALUES (?, 'k', 'Bulk', 'plc1', 'H', 'low', 'raise', 'null', '', 'bulk')", (_ts("2026-11-10T00:00:00") + i,))
        db._conn.execute("COMMIT")
    assert len(_h(seeded, limit=99999)) == 2000
    lines = seeded.get("/api/alarms/history/export", params={"q": "bulk"}).content.decode("utf-8").strip().splitlines()
    assert len(lines) == 1 + 2100
    lines = seeded.get("/api/alarms/history/export", params={"q": "temp"}).content.decode("utf-8").strip().splitlines()
    assert len(lines) == 1 + 2


def test_viewer_can_export(seeded):
    seeded.post("/api/users", json={"username": "se", "role": "viewer", "password": "Hemmelig-123"})
    seeded.post("/api/auth/login", json={"username": "se", "password": "Hemmelig-123"})
    seeded.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert seeded.get("/api/alarms/history/export").status_code == 200
    seeded.post("/api/auth/logout")
    assert seeded.get("/api/alarms/history/export").status_code == 401


def test_csv_cells_that_look_like_formulas_are_neutralised(seeded):
    _add(seeded, "2026-11-08T09:00:00", "k", "=1+1", "plc1", "H", "low", "raise", "@SUM(A1)", -5.5, "-jan")
    text = seeded.get("/api/alarms/history/export", params={"q": "1+1"}).content.decode("utf-8")
    cells = text.lstrip("﻿").strip().splitlines()[1].split(";")
    assert cells[1] == "'=1+1" and cells[8] == "'@SUM(A1)" and cells[7] == "'-jan"
    assert cells[6] == "-5,5"                                  # tal (også negative) er uændrede


def test_date_only_to_covers_whole_day_also_on_dst_days(seeded):
    # 2026-10-25 har 25 timer (tilbage til normaltid), 2026-03-29 har 23 timer (frem til sommertid)
    for ts, msg in [("2026-10-25T23:30:00", "sen25"), ("2026-10-26T00:30:00", "tidlig26"),
                    ("2026-03-29T23:30:00", "sen29"), ("2026-03-30T00:30:00", "tidlig30")]:
        _add(seeded, ts, "k", "Dst", "plc1", "H", "low", "raise", msg)
    assert _msgs(_h(seeded, **{"from": "2026-10-25", "to": "2026-10-25"})) == ["sen25"]
    assert _msgs(_h(seeded, **{"from": "2026-03-29", "to": "2026-03-29"})) == ["sen29"]


def test_unknown_system_gives_400_also_for_scoped_user(seeded, mock_plc):
    kedel = _drawing(seeded, "Kedel", "Temp")
    r = seeded.get("/api/alarms/history", params={"system": "findes-ikke"})
    assert r.status_code == 400 and "Ukendt system" in r.text
    _scoped_client(seeded, mock_plc)
    for path in ("/api/alarms/history", "/api/alarms/history/export"):
        assert seeded.get(path, params={"system": kedel}).status_code == 400   # fremmed tegning
    rows = _h(seeded, system="-")                                              # uden system: stadig kun egne
    assert not any(r["message"].startswith("Kedel") for r in rows)
