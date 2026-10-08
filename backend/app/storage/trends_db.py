"""Trend-historik i en separat SQLite-fil (holder hoveddatabase og backups små). Lag 4b.

samples: (tag_id, ts, value) — value NULL markerer et hul (ingen gyldig værdi).
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trend_tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS samples (
    tag_id INTEGER NOT NULL,
    ts     REAL NOT NULL,
    value  REAL,
    PRIMARY KEY (tag_id, ts)
) WITHOUT ROWID;
"""


class TrendDatabase:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        self._ids: dict[str, int] = {}
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")  # skåner SD-kortet; WAL gør det sikkert nok
            self._conn.executescript(_SCHEMA)
            for row in self._conn.execute("SELECT id, name FROM trend_tags"):
                self._ids[row[1]] = row[0]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _id(self, name: str, create: bool) -> int | None:
        if name in self._ids:
            return self._ids[name]
        if not create:
            return None
        cur = self._conn.execute("INSERT OR IGNORE INTO trend_tags(name) VALUES (?)", (name,))
        tid = cur.lastrowid if cur.rowcount else self._conn.execute(
            "SELECT id FROM trend_tags WHERE name = ?", (name,)).fetchone()[0]
        self._ids[name] = int(tid)
        return int(tid)

    def insert_many(self, rows: list[tuple[str, float, float | None]]) -> None:
        """Én transaktion pr. batch (få, store skrivninger i stedet for mange små)."""
        if not rows:
            return
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                self._conn.executemany(
                    "INSERT OR REPLACE INTO samples(tag_id, ts, value) VALUES (?, ?, ?)",
                    [(self._id(name, True), ts, value) for name, ts, value in rows])
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def series(self, name: str, start: float, end: float, step: float) -> list[list[Any]]:
        """Nedsamplet serie: [[t, gennemsnit, min, max], ...] — én række pr. tidsspand med data.
        Et spand med kun huller giver [t, None, None, None]. Første punkt er sidste værdi før `start`."""
        with self._lock:
            tid = self._id(name, False)
            if tid is None:
                return []
            before = self._conn.execute(
                "SELECT ts, value FROM samples WHERE tag_id = ? AND ts < ? ORDER BY ts DESC LIMIT 1",
                (tid, start)).fetchone()
            rows = self._conn.execute(
                "SELECT CAST((ts - ?) / ? AS INTEGER) AS b, AVG(value), MIN(value), MAX(value), MIN(ts) "
                "FROM samples WHERE tag_id = ? AND ts >= ? AND ts <= ? GROUP BY b ORDER BY b",
                (start, step, tid, start, end)).fetchall()
        out: list[list[Any]] = []
        if before is not None:
            out.append([start, before[1], before[1], before[1]])
        for b, avg, lo, hi, _first in rows:
            out.append([min(start + (b + 0.5) * step, end), avg, lo, hi])  # midt i tidsspandet
        return out

    def raw(self, names: list[str], start: float, end: float, limit: int) -> Iterator[tuple[str, float, float | None]]:
        with self._lock:
            ids = {self._ids[n]: n for n in names if n in self._ids}
            if not ids:
                return iter(())
            marks = ",".join("?" * len(ids))
            rows = self._conn.execute(
                f"SELECT tag_id, ts, value FROM samples WHERE tag_id IN ({marks}) AND ts >= ? AND ts <= ? "
                f"ORDER BY ts LIMIT ?", (*ids, start, end, limit)).fetchall()
        return ((ids[t], ts, v) for t, ts, v in rows)

    def stats(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT t.name, COUNT(*), MIN(s.ts), MAX(s.ts) FROM samples s JOIN trend_tags t ON t.id = s.tag_id "
                "GROUP BY s.tag_id").fetchall()
        return {r[0]: {"samples": r[1], "oldest": r[2], "newest": r[3]} for r in rows}

    def purge_before(self, cutoff: float) -> int:
        with self._lock:
            return self._conn.execute("DELETE FROM samples WHERE ts < ?", (cutoff,)).rowcount

    def forget(self, name: str) -> None:
        with self._lock:
            tid = self._ids.pop(name, None)
            if tid is not None:
                self._conn.execute("DELETE FROM samples WHERE tag_id = ?", (tid,))
                self._conn.execute("DELETE FROM trend_tags WHERE id = ?", (tid,))

    def size_bytes(self) -> int:
        total = 0
        for suffix in ("", "-wal"):
            p = Path(str(self.path) + suffix)
            if p.exists():
                total += p.stat().st_size
        return total
