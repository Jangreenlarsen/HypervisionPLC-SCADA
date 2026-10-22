"""Trend-historik i en separat SQLite-fil (holder hoveddatabase og backups små). Lag 4b.

samples: (tag_id, ts, value) — value NULL markerer et hul (ingen gyldig værdi).
"""

from __future__ import annotations

import os
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

    def relocate(self, new_path: Path) -> Path:
        """Flyt databasen til en anden fil/disk mens den kører: konsistent kopi (SQLites backup-API) under låsen, kontrol af
        kopien (quick_check + samme antal rækker), derefter skiftes forbindelsen. Den gamle fil omdøbes til `<navn>.moved`
        (og returneres), så intet slettes. Fejler noget, er den gamle database uændret i brug."""
        new_path = Path(new_path)
        if new_path.exists():
            raise FileExistsError(f"{new_path} findes allerede")
        tmp = new_path.with_name(new_path.name + ".tmp")
        for suffix in ("", "-wal", "-shm"):
            Path(str(tmp) + suffix).unlink(missing_ok=True)
        with self._lock:
            try:
                dest = sqlite3.connect(str(tmp))
                try:
                    self._conn.backup(dest)
                finally:
                    dest.close()
                check = sqlite3.connect(str(tmp))
                try:
                    if check.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise OSError("Kontrol af kopien fejlede (quick_check)")
                    copied = check.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
                finally:
                    check.close()
                original = self._conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
                if copied != original:
                    raise OSError(f"Kopien har {copied} rækker, originalen {original}")
                os.replace(tmp, new_path)
                conn = sqlite3.connect(str(new_path), check_same_thread=False, isolation_level=None)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.executescript(_SCHEMA)
            except Exception:
                for suffix in ("", "-wal", "-shm"):
                    Path(str(tmp) + suffix).unlink(missing_ok=True)
                raise
            old, old_path = self._conn, self.path
            self._conn, self.path = conn, new_path
            self._ids = {row[1]: row[0] for row in conn.execute("SELECT id, name FROM trend_tags")}
            old.close()
        moved = old_path.with_name(old_path.name + ".moved")
        moved.unlink(missing_ok=True)
        os.replace(old_path, moved)
        for suffix in ("-wal", "-shm"):
            Path(str(old_path) + suffix).unlink(missing_ok=True)
        return moved

    def snapshot(self, dest: Path) -> None:
        """Konsistent kopi via SQLites backup-API på en SEPARAT forbindelse (WAL: læsning blokerer ikke
        opsamlingen). Kan køres i en baggrundstråd."""
        dest.unlink(missing_ok=True)
        src = sqlite3.connect(str(self.path), timeout=30)
        target = sqlite3.connect(str(dest))
        try:
            src.backup(target, pages=4096)
        finally:
            target.close()
            src.close()

    @staticmethod
    def check_file(path: Path) -> dict[str, int]:
        """Er filen en trend-historik? → {tags, samples}. ValueError med dansk tekst ellers."""
        try:
            con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        except sqlite3.Error:
            raise ValueError("Filen kan ikke åbnes som database") from None
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if not {"trend_tags", "samples"} <= tables:
                raise ValueError("Filen er ikke en trend-historik fra HypervisionPLC SCADA")
            cols = {r[1] for r in con.execute("PRAGMA table_info(samples)")}
            if not {"tag_id", "ts", "value"} <= cols:
                raise ValueError("Filen er ikke en trend-historik fra HypervisionPLC SCADA")
            if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Databasen i filen er beskadiget")
            return {"tags": con.execute("SELECT COUNT(*) FROM trend_tags").fetchone()[0],
                    "samples": con.execute("SELECT COUNT(*) FROM samples").fetchone()[0]}
        except sqlite3.DatabaseError:
            raise ValueError("Filen er ikke en gyldig SQLite-database") from None
        finally:
            con.close()

    def merge_from(self, src: Path) -> dict[str, int]:
        """Flet en anden trend-historik ind: tags matches på navn, og eksisterende (tag, tidspunkt) bevares —
        intet overskrives. Flettes tag for tag, så opsamlingen kun venter kort ad gangen."""
        info = self.check_file(src)
        added = 0
        with self._lock:
            self._conn.execute("ATTACH DATABASE ? AS src", (str(src),))
        try:
            with self._lock:
                names = [r[0] for r in self._conn.execute("SELECT name FROM src.trend_tags")]
            for name in names:
                with self._lock:
                    self._conn.execute("BEGIN")
                    try:
                        self._conn.execute("INSERT OR IGNORE INTO trend_tags(name) VALUES (?)", (name,))
                        cur = self._conn.execute(
                            "INSERT OR IGNORE INTO samples(tag_id, ts, value) "
                            "SELECT (SELECT id FROM trend_tags WHERE name = ?), s.ts, s.value "
                            "FROM src.samples s JOIN src.trend_tags st ON st.id = s.tag_id WHERE st.name = ?",
                            (name, name))
                        added += max(0, cur.rowcount)
                        self._conn.execute("COMMIT")
                    except Exception:
                        self._conn.execute("ROLLBACK")
                        raise
        finally:
            with self._lock:
                self._conn.execute("DETACH DATABASE src")
                self._ids = {row[1]: row[0] for row in self._conn.execute("SELECT id, name FROM trend_tags")}
        return {"tags": len(names), "samples_in_file": info["samples"], "samples_added": added}

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

    def purge_before(self, cutoff: float, keep: dict[str, float] | None = None) -> int:
        """Slet værdier ældre end `cutoff` — undtagen tags i `keep` ({navn: egen cutoff}, fx energi-tags)."""
        keep = keep or {}
        with self._lock:
            ids = {self._ids[n]: c for n, c in keep.items() if n in self._ids}
            if not ids:
                return self._conn.execute("DELETE FROM samples WHERE ts < ?", (cutoff,)).rowcount
            marks = ",".join("?" * len(ids))
            n = self._conn.execute(f"DELETE FROM samples WHERE ts < ? AND tag_id NOT IN ({marks})",
                                   (cutoff, *ids)).rowcount
            for tid, c in ids.items():
                n += self._conn.execute("DELETE FROM samples WHERE tag_id = ? AND ts < ?", (tid, c)).rowcount
            return n

    def samples_with_prev(self, name: str, start: float, end: float) -> list[tuple[float, float | None]]:
        """Alle værdier i [start, end] plus den sidste gyldige værdi før `start` (udgangspunkt for tællere)."""
        with self._lock:
            tid = self._ids.get(name)
            if tid is None:
                return []
            prev = self._conn.execute("SELECT ts, value FROM samples WHERE tag_id = ? AND ts < ? AND value IS NOT NULL "
                                      "ORDER BY ts DESC LIMIT 1", (tid, start)).fetchall()
            rows = self._conn.execute("SELECT ts, value FROM samples WHERE tag_id = ? AND ts >= ? AND ts <= ? ORDER BY ts",
                                      (tid, start, end)).fetchall()
        return [(r[0], r[1]) for r in prev + rows]

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
