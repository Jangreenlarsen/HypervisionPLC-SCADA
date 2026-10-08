"""Energirapporter ud fra trend-historikken (lag 3).

Et tag kan markeres som energi:
- `counter` (tæller, fx kWh-måler): forbruget i en periode = summen af stigninger. Falder tælleren
  (nulstilling/udskiftning), regnes den nye værdi som stigning fra 0.
- `power` (effekt, fx W/kW): integreres over tiden (værdien holdes til næste måling). Huller (ingen
  gyldig værdi) og data ældre end MAX_HOLD tæller som 0 — aldrig som den sidste værdi.

`energy_factor` omregner til kWh: tæller i Wh → 0,001; effekt i W → 0,001; effekt i kW eller tæller i kWh → 1.
Perioderne følger dansk tid (sommertid inkl.).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Copenhagen")
PERIODS = ("day", "week", "month")
DEFAULT_COUNT = {"day": 14, "week": 12, "month": 12}
MAX_BUCKETS = 400
# En effekt-værdi holdes højst så længe uden ny måling (opsamleren gemmer mindst hvert 5. min).
MAX_HOLD_S = 600.0
MONTHS = ["januar", "februar", "marts", "april", "maj", "juni", "juli", "august", "september", "oktober",
          "november", "december"]


def _floor(dt: datetime, period: str) -> datetime:
    dt = dt.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        dt -= timedelta(days=dt.weekday())  # mandag
    elif period == "month":
        dt = dt.replace(day=1)
    return dt


def _next(dt: datetime, period: str) -> datetime:
    """Næste periodestart — beregnet i lokal kalender og omsat igen, så sommertid håndteres."""
    if period == "day":
        n = dt.replace(tzinfo=None) + timedelta(days=1)
    elif period == "week":
        n = dt.replace(tzinfo=None) + timedelta(days=7)
    else:
        n = dt.replace(tzinfo=None, year=dt.year + (dt.month == 12), month=dt.month % 12 + 1)
    return n.replace(tzinfo=TZ)


def label(start: datetime, period: str) -> str:
    start = start.astimezone(TZ)
    if period == "day":
        return start.strftime("%d.%m.%Y")
    if period == "week":
        year, week, _ = start.isocalendar()
        return f"Uge {week} {year}"
    return f"{MONTHS[start.month - 1]} {start.year}"


def buckets(period: str, start: float, end: float) -> list[tuple[float, float]]:
    """Perioder [start, slut) der dækker [start, end] — justeret til hele dage/uger/måneder i dansk tid."""
    if period not in PERIODS:
        raise ValueError(f"Ukendt periode '{period}' (brug {', '.join(PERIODS)})")
    cur = _floor(datetime.fromtimestamp(start, TZ), period)
    out: list[tuple[float, float]] = []
    while cur.timestamp() < end:
        nxt = _next(cur, period)
        out.append((cur.timestamp(), nxt.timestamp()))
        if len(out) > MAX_BUCKETS:
            raise ValueError(f"For mange perioder (max {MAX_BUCKETS}) — vælg en kortere periode eller større enhed")
        cur = nxt
    return out


def default_range(period: str, now: float) -> tuple[float, float]:
    """De seneste N hele perioder inkl. den igangværende."""
    cur = _floor(datetime.fromtimestamp(now, TZ), period)
    for _ in range(DEFAULT_COUNT[period] - 1):
        prev = cur.replace(tzinfo=None)
        if period == "day":
            prev -= timedelta(days=1)
        elif period == "week":
            prev -= timedelta(days=7)
        else:
            prev = prev.replace(year=prev.year - (prev.month == 1), month=(prev.month - 2) % 12 + 1)
        cur = prev.replace(tzinfo=TZ)
    return cur.timestamp(), now


def counter_energy(samples: list[tuple[float, float | None]], spans: list[tuple[float, float]],
                   now: float) -> list[float | None]:
    """Stigning i hver periode. `samples` sorteret efter tid; den sidste værdi før perioden er udgangspunktet.
    None = ingen tællerværdi før/i perioden, eller perioden ligger i fremtiden. Uændret tæller = 0."""
    out: list[float | None] = []
    for b0, b1 in spans:
        if b0 >= now:
            out.append(None)
            continue
        last: float | None = None
        total = 0.0
        any_value = False
        for ts, v in samples:
            if v is None:
                continue  # hul: tælleren fortsætter fra sidste kendte værdi
            if ts > b1:
                break
            any_value = True
            if ts > b0 and last is not None:
                d = v - last
                total += d if d >= 0 else v  # fald = nulstilling → tæller op fra 0
            last = v
        out.append(round(total, 6) if any_value else None)
    return out


def power_energy(samples: list[tuple[float, float | None]], spans: list[tuple[float, float]], now: float) -> list[float | None]:
    """∫ effekt dt (i timer) for hver periode — værdien holdes til næste måling, højst MAX_HOLD_S og aldrig efter `now`."""
    segs: list[tuple[float, float, float]] = []  # (fra, til, effekt)
    for i, (ts, v) in enumerate(samples):
        nxt = samples[i + 1][0] if i + 1 < len(samples) else now
        stop = min(nxt, ts + MAX_HOLD_S, now)
        if v is not None and stop > ts:
            segs.append((ts, stop, v))
    out: list[float | None] = []
    for b0, b1 in spans:
        if b0 >= now:
            out.append(None)  # fremtiden
            continue
        total = 0.0
        covered = False
        for s0, s1, v in segs:
            lo, hi = max(s0, b0), min(s1, b1)
            if hi > lo:
                total += v * (hi - lo) / 3600.0
                covered = True
        out.append(round(total, 6) if covered else None)
    return out


def energy_series(kind: str, factor: float, samples: Iterable[tuple[float, float | None]],
                  spans: list[tuple[float, float]], now: float) -> list[float | None]:
    data = sorted(samples)
    raw = counter_energy(data, spans, now) if kind == "counter" else power_energy(data, spans, now)
    return [None if v is None else round(v * factor, 4) for v in raw]


def report(tags: list[dict[str, Any]], period: str, start: float, end: float, now: float,
           samples_for: Any) -> dict[str, Any]:
    """`tags`: [{name, energy, energy_factor, description}], `samples_for(name, start, end)` → [(ts, value)]."""
    spans = buckets(period, start, end)
    series: dict[str, list[float | None]] = {}
    totals: dict[str, float] = {}
    for t in tags:
        data = samples_for(t["name"], spans[0][0] if spans else start, spans[-1][1] if spans else end)
        series[t["name"]] = energy_series(t["energy"], float(t["energy_factor"]), data, spans, now)
        totals[t["name"]] = round(sum(v for v in series[t["name"]] if v is not None), 4)
    return {
        "period": period,
        "buckets": [{"start": a, "end": b, "label": label(datetime.fromtimestamp(a, TZ), period),
                     "current": a <= now < b} for a, b in spans],
        "series": series,
        "totals": totals,
        "meta": {t["name"]: {"description": t.get("description") or "", "kind": t["energy"]} for t in tags},
        "unit": "kWh",
    }
