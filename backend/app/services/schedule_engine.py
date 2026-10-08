"""Ugeprogrammer — ren beregning (ingen I/O): hvilken værdi ønskes nu, og hvornår skifter den.

- Tider er lokal dansk vægur-tid (SCADA_TZ): 06:00 er 06:00 året rundt, også omkring sommertid.
- En periode "22:00–06:00" går over midnat og hører til startdagen.
- Overlapper perioder, vinder den der står senest i listen.
- En undtagelse (fx ferie) gælder hele datoer [fra, til] og erstatter ugeplanen; value None = standardværdien.
- Uden for perioder gælder standardværdien; er den None, ønskes ingen bestemt værdi (programmet skriver ikke).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("SCADA_TZ", "Europe/Copenhagen"))
DAY_NAMES = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]
_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$|^24:00$")


@dataclass(frozen=True)
class Entry:
    days: frozenset[int]  # 1 = mandag … 7 = søndag
    start: int            # minutter efter midnat
    end: int              # minutter efter midnat (1440 = 24:00); end < start = over midnat
    value: float


@dataclass(frozen=True)
class Exception_:
    date_from: date
    date_to: date
    value: float | None


@dataclass(frozen=True)
class Program:
    entries: tuple[Entry, ...]
    exceptions: tuple[Exception_, ...]
    default: float | None


def parse_hhmm(text: str) -> int:
    m = _HHMM.match(text or "")
    if not m:
        raise ValueError(f"Ugyldigt klokkeslæt '{text}' — brug TT:MM (00:00-24:00)")
    return 1440 if text == "24:00" else int(m.group(1)) * 60 + int(m.group(2))


def fmt_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def program_from(data: dict[str, Any]) -> Program:
    """Fra validerede data (som gemt) til et Program."""
    return Program(
        entries=tuple(Entry(frozenset(e["days"]), parse_hhmm(e["start"]), parse_hhmm(e["end"]), float(e["value"]))
                      for e in data.get("entries", [])),
        exceptions=tuple(Exception_(date.fromisoformat(x["date_from"]), date.fromisoformat(x["date_to"]),
                                    None if x.get("value") is None else float(x["value"]))
                         for x in data.get("exceptions", [])),
        default=None if data.get("default_value") is None else float(data["default_value"]),
    )


def _active(e: Entry, d: date, minute: int) -> bool:
    wd = d.isoweekday()
    if e.start < e.end:
        return wd in e.days and e.start <= minute < e.end
    # Over midnat: fra start på startdagen til slut næste dag
    prev = 7 if wd == 1 else wd - 1
    return (wd in e.days and minute >= e.start) or (prev in e.days and minute < e.end)


def desired(p: Program, now: datetime) -> float | None:
    local = now.astimezone(TZ)
    d, minute = local.date(), local.hour * 60 + local.minute
    for x in reversed(p.exceptions):
        if x.date_from <= d <= x.date_to:
            return p.default if x.value is None else x.value
    for e in reversed(p.entries):
        if _active(e, d, minute):
            return e.value
    return p.default


def changes(p: Program, start: datetime, days: int = 7) -> list[tuple[datetime, float | None]]:
    """Skift i [start, start + days): (tidspunkt, ny værdi). Første element er værdien ved `start`."""
    local = start.astimezone(TZ)
    candidates: set[datetime] = set()
    for i in range(days + 1):
        d = local.date() + timedelta(days=i)
        candidates.add(datetime.combine(d, time(0, 0), TZ))
        for e in p.entries:
            for m in (e.start, e.end):
                if m < 1440:
                    candidates.add(datetime.combine(d, time(m // 60, m % 60), TZ))
    end = local + timedelta(days=days)
    out: list[tuple[datetime, float | None]] = [(local, desired(p, local))]
    for t in sorted(c for c in candidates if local < c < end):
        v = desired(p, t)
        if v != out[-1][1]:
            out.append((t, v))
    return out


def week_segments(p: Program, monday: date) -> list[list[dict[str, Any]]]:
    """Ugeoversigt til visning: pr. dag (man–søn) en liste af {from, to, value} i minutter."""
    out = []
    for i in range(7):
        d = monday + timedelta(days=i)
        start = datetime.combine(d, time(0, 0), TZ)
        segs: list[dict[str, Any]] = []
        for t, v in changes(p, start, 1):
            m = t.astimezone(TZ).hour * 60 + t.astimezone(TZ).minute if t.astimezone(TZ).date() == d else 1440
            if segs:
                segs[-1]["to"] = m
            segs.append({"from": m, "to": 1440, "value": v})
        out.append([s for s in segs if s["to"] > s["from"]])
    return out
