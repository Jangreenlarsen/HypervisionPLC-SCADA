"""Ugeprogram-beregning: perioder, over midnat, prioritet, undtagelser og sommertid."""

from datetime import date, datetime

import pytest

from app.services.schedule_engine import TZ, changes, desired, parse_hhmm, program_from, week_segments

HVERDAG = [1, 2, 3, 4, 5]


def at(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=TZ)


def prog(entries, default=17.0, exceptions=()):
    return program_from({"entries": entries, "exceptions": list(exceptions), "default_value": default})


def test_weekday_comfort_and_default():
    p = prog([{"days": HVERDAG, "start": "06:00", "end": "22:00", "value": 21}])
    assert desired(p, at(2026, 10, 5, 5, 59)) == 17  # mandag før start
    assert desired(p, at(2026, 10, 5, 6, 0)) == 21   # start er med
    assert desired(p, at(2026, 10, 5, 22, 0)) == 17  # slut er ikke med
    assert desired(p, at(2026, 10, 10, 12)) == 17    # lørdag


def test_overnight_belongs_to_start_day():
    p = prog([{"days": [5], "start": "22:00", "end": "06:00", "value": 1}], default=0)  # fredag nat
    assert desired(p, at(2026, 10, 9, 23)) == 1    # fredag 23
    assert desired(p, at(2026, 10, 10, 5, 59)) == 1  # lørdag morgen
    assert desired(p, at(2026, 10, 10, 6)) == 0
    assert desired(p, at(2026, 10, 9, 5)) == 0     # fredag morgen (torsdag er ikke valgt)


def test_later_entry_wins_and_24h():
    p = prog([{"days": [1, 2, 3, 4, 5, 6, 7], "start": "00:00", "end": "24:00", "value": 19},
              {"days": [1], "start": "08:00", "end": "09:00", "value": 23}])
    assert desired(p, at(2026, 10, 5, 8, 30)) == 23 and desired(p, at(2026, 10, 5, 23, 59)) == 19


def test_exception_overrides_week_plan():
    p = prog([{"days": HVERDAG, "start": "06:00", "end": "22:00", "value": 21}],
             exceptions=[{"date_from": "2026-10-12", "date_to": "2026-10-16", "value": 15},
                         {"date_from": "2026-10-19", "date_to": "2026-10-19", "value": None}])
    assert desired(p, at(2026, 10, 14, 12)) == 15   # ferie
    assert desired(p, at(2026, 10, 19, 12)) == 17   # undtagelse uden værdi = standard
    assert desired(p, at(2026, 10, 20, 12)) == 21


def test_no_default_means_no_wish():
    p = prog([{"days": HVERDAG, "start": "06:00", "end": "22:00", "value": 1}], default=None)
    assert desired(p, at(2026, 10, 5, 3)) is None


def test_changes_lists_transitions_in_local_time_across_dst():
    # Sommertid slutter søndag 25.10.2026 — 06:00 skal stadig være 06:00 lokal tid
    p = prog([{"days": [1, 2, 3, 4, 5, 6, 7], "start": "06:00", "end": "22:00", "value": 21}])
    ch = changes(p, at(2026, 10, 24, 12), days=2)
    assert [(t.astimezone(TZ).strftime("%d %H:%M"), v) for t, v in ch] == [
        ("24 12:00", 21), ("24 22:00", 17), ("25 06:00", 21), ("25 22:00", 17), ("26 06:00", 21)]
    assert ch[2][0].utcoffset().total_seconds() == 3600  # vintertid efter skiftet


def test_week_segments_for_display():
    p = prog([{"days": HVERDAG, "start": "06:00", "end": "22:00", "value": 21}])
    week = week_segments(p, date(2026, 10, 5))
    assert week[0] == [{"from": 0, "to": 360, "value": 17}, {"from": 360, "to": 1320, "value": 21},
                       {"from": 1320, "to": 1440, "value": 17}]
    assert week[5] == [{"from": 0, "to": 1440, "value": 17}]


def test_parse_hhmm():
    assert parse_hhmm("00:00") == 0 and parse_hhmm("24:00") == 1440 and parse_hhmm("23:59") == 1439
    for bad in ("24:01", "7:00", "12:60", ""):
        with pytest.raises(ValueError, match="klokkeslæt"):
            parse_hhmm(bad)
