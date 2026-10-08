"""Energiberegning: perioder i dansk tid, tæller og effekt."""

from datetime import datetime

import pytest

from app.services.energy import TZ, buckets, counter_energy, default_range, label, power_energy, report


def ts(*a):
    return datetime(*a, tzinfo=TZ).timestamp()


def test_day_buckets_follow_danish_time_including_dst():
    # Sommertid slutter 25.10.2026 kl. 03 → det døgn er 25 timer
    spans = buckets("day", ts(2026, 10, 24, 12), ts(2026, 10, 26, 1))
    assert [b - a for a, b in spans] == [86400, 90000, 86400]
    assert spans[0][0] == ts(2026, 10, 24)
    assert label(datetime.fromtimestamp(spans[1][0], TZ), "day") == "25.10.2026"


def test_week_and_month_buckets():
    w = buckets("week", ts(2026, 10, 8), ts(2026, 10, 20))
    assert w[0][0] == ts(2026, 10, 5) and len(w) == 3  # mandag
    assert label(datetime.fromtimestamp(w[0][0], TZ), "week") == "Uge 41 2026"
    m = buckets("month", ts(2026, 11, 15), ts(2027, 1, 2))
    assert [label(datetime.fromtimestamp(a, TZ), "month") for a, _ in m] == ["november 2026", "december 2026", "januar 2027"]
    with pytest.raises(ValueError, match="Ukendt periode"):
        buckets("aar", 0, 1)


def test_default_range_is_n_whole_periods_including_current():
    start, end = default_range("month", ts(2026, 3, 10, 12))
    assert start == ts(2025, 4, 1) and end == ts(2026, 3, 10, 12)
    assert len(buckets("month", start, end)) == 12


def test_counter_with_reset_gap_and_baseline_before_period():
    d1 = (ts(2026, 1, 1), ts(2026, 1, 2))
    d2 = (ts(2026, 1, 2), ts(2026, 1, 3))
    samples = [(ts(2025, 12, 31, 23), 100.0),   # udgangspunkt før første døgn
               (ts(2026, 1, 1, 6), 110.0), (ts(2026, 1, 1, 7), None),  # hul
               (ts(2026, 1, 1, 9), 130.0),
               (ts(2026, 1, 2, 3), 5.0),         # tælleren nulstillet → +5
               (ts(2026, 1, 2, 4), 12.0)]
    assert counter_energy(samples, [d1, d2], now=ts(2026, 1, 5)) == [30.0, 12.0]


def test_counter_unchanged_is_zero_and_future_and_no_data_is_none():
    d1 = (ts(2026, 1, 1), ts(2026, 1, 2))
    d2 = (ts(2026, 1, 2), ts(2026, 1, 3))
    assert counter_energy([(ts(2025, 12, 31), 50.0)], [d1], now=ts(2026, 1, 5)) == [0.0]
    assert counter_energy([], [d1], now=ts(2026, 1, 5)) == [None]
    assert counter_energy([(ts(2025, 12, 31), 50.0)], [d1, d2], now=ts(2026, 1, 1, 12)) == [0.0, None]


def test_power_integration_hold_and_gaps():
    d = (ts(2026, 1, 1), ts(2026, 1, 2))
    t0 = ts(2026, 1, 1, 10)
    # 2 kW i 5 min, så hul (None) i 5 min, så 1 kW holdt højst 10 min (MAX_HOLD) → 2*5/60 + 1*10/60
    samples = [(t0, 2.0), (t0 + 300, None), (t0 + 600, 1.0)]
    assert power_energy(samples, [d], now=ts(2026, 1, 3)) == [pytest.approx(2 * 5 / 60 + 1 * 10 / 60)]
    # Værdien holdes ikke ud over "nu"
    assert power_energy([(t0, 6.0)], [d], now=t0 + 60) == [pytest.approx(6 / 60)]
    # Effekt der krydser en periodegrænse fordeles
    mid = ts(2026, 1, 2)
    d2 = (mid, ts(2026, 1, 3))
    got = power_energy([(mid - 120, 3.0), (mid + 120, 3.0)], [d, d2], now=ts(2026, 1, 5))
    assert got == [pytest.approx(3 * 2 / 60), pytest.approx(3 * (2 + 10) / 60)]


def test_report_applies_factor_and_totals():
    spans_start, spans_end = ts(2026, 1, 1), ts(2026, 1, 3)
    data = {"Maaler": [(ts(2025, 12, 31), 1000.0), (ts(2026, 1, 1, 12), 3000.0), (ts(2026, 1, 2, 12), 4000.0)]}
    tags = [{"name": "Maaler", "energy": "counter", "energy_factor": 0.001, "description": "Elmåler (Wh)"}]
    r = report(tags, "day", spans_start, spans_end, ts(2026, 1, 5), lambda n, a, b: data[n])
    assert r["series"]["Maaler"] == [2.0, 1.0] and r["totals"]["Maaler"] == 3.0 and r["unit"] == "kWh"
    assert [b["label"] for b in r["buckets"]] == ["01.01.2026", "02.01.2026"]
    assert r["meta"]["Maaler"] == {"description": "Elmåler (Wh)", "kind": "counter"}
