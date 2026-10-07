"""SQLite-lager (WAL). Lag 4b.

Opdateringer skriver kun de felter der faktisk ændres (CLAUDE.md regel 12: ingen
read-modify-write af hele rækker).
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plcs (
    key         TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    base_url    TEXT NOT NULL,
    username    TEXT NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    sse_enabled INTEGER NOT NULL DEFAULT 1,
    verify_tls  INTEGER NOT NULL DEFAULT 1,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tags (
    name          TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    plc           TEXT NOT NULL REFERENCES plcs(key),
    description   TEXT NOT NULL DEFAULT '',
    unit          TEXT NOT NULL DEFAULT '',
    scale         REAL NOT NULL DEFAULT 1,
    "offset"      REAL NOT NULL DEFAULT 0,
    decimals      INTEGER,
    writable      INTEGER NOT NULL DEFAULT 0,
    min           REAL,
    max           REAL,
    confirm_write INTEGER NOT NULL DEFAULT 1,
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS tags_plc ON tags(plc);
"""

PLC_FIELDS = ("name", "base_url", "username", "enabled", "sse_enabled", "verify_tls")
TAG_FIELDS = ("source", "plc", "description", "unit", "scale", "offset", "decimals",
              "writable", "min", "max", "confirm_write")
_BOOL_FIELDS = {"enabled", "sse_enabled", "verify_tls", "writable", "confirm_write"}


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(_SCHEMA)
            self._conn.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------------------------------------------------------------- hjælp

    def _query(self, sql: str, args: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [_row(r) for r in rows]

    def _execute(self, sql: str, args: tuple[Any, ...] = ()) -> int:
        with self._lock:
            return self._conn.execute(sql, args).rowcount

    # ----------------------------------------------------------------- PLC'er

    def list_plcs(self) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM plcs ORDER BY key")

    def get_plc(self, key: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM plcs WHERE key = ?", (key,))
        return rows[0] if rows else None

    def insert_plc(self, key: str, values: dict[str, Any]) -> None:
        now = time.time()
        cols = ["key", *PLC_FIELDS, "created_at", "updated_at"]
        args = (key, *(_db(f, values[f]) for f in PLC_FIELDS), now, now)
        self._execute(f"INSERT INTO plcs({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", args)

    def update_plc(self, key: str, changes: dict[str, Any]) -> bool:
        return self._update("plcs", "key", key, changes, PLC_FIELDS)

    def delete_plc(self, key: str) -> bool:
        return self._execute("DELETE FROM plcs WHERE key = ?", (key,)) > 0

    # ------------------------------------------------------------------- tags

    def list_tags(self, plc: str | None = None) -> list[dict[str, Any]]:
        if plc is None:
            return self._query("SELECT * FROM tags ORDER BY name")
        return self._query("SELECT * FROM tags WHERE plc = ? ORDER BY name", (plc,))

    def count_tags(self, plc: str) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM tags WHERE plc = ?", (plc,)).fetchone()[0])

    def get_tag(self, name: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM tags WHERE name = ?", (name,))
        return rows[0] if rows else None

    def insert_tag(self, name: str, values: dict[str, Any]) -> None:
        now = time.time()
        cols = ["name", *TAG_FIELDS, "created_at", "updated_at"]
        args = (name, *(_db(f, values.get(f)) for f in TAG_FIELDS), now, now)
        quoted = ",".join(f'"{c}"' for c in cols)
        self._execute(f"INSERT INTO tags({quoted}) VALUES ({','.join('?' * len(cols))})", args)

    def update_tag(self, name: str, changes: dict[str, Any]) -> bool:
        return self._update("tags", "name", name, changes, TAG_FIELDS)

    def delete_tag(self, name: str) -> bool:
        return self._execute("DELETE FROM tags WHERE name = ?", (name,)) > 0

    def _update(self, table: str, pk: str, key: str, changes: dict[str, Any], allowed: tuple[str, ...]) -> bool:
        fields = [f for f in changes if f in allowed]
        if not fields:
            return self._query(f"SELECT 1 FROM {table} WHERE {pk} = ?", (key,)) != []
        sets = ", ".join(f'"{f}" = ?' for f in fields)
        args = (*(_db(f, changes[f]) for f in fields), time.time(), key)
        return self._execute(f'UPDATE {table} SET {sets}, updated_at = ? WHERE {pk} = ?', args) > 0


def _db(field: str, value: Any) -> Any:
    if field in _BOOL_FIELDS and value is not None:
        return 1 if value else 0
    return value


def _row(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    for f in _BOOL_FIELDS & out.keys():
        out[f] = bool(out[f])
    return out
