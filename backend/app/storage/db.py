"""SQLite-lager (WAL). Lag 4b.

Opdateringer skriver kun de felter der faktisk ændres (CLAUDE.md regel 12: ingen
read-modify-write af hele rækker).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 3

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
CREATE TABLE IF NOT EXISTS drawings (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    active_version INTEGER NOT NULL,
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS drawing_versions (
    drawing_id  TEXT NOT NULL REFERENCES drawings(id) ON DELETE CASCADE,
    version     INTEGER NOT NULL,
    comment     TEXT NOT NULL DEFAULT '',
    size        INTEGER NOT NULL,
    width       REAL,
    height      REAL,
    created_at  REAL NOT NULL,
    PRIMARY KEY (drawing_id, version)
);
CREATE TABLE IF NOT EXISTS bindings (
    drawing_id  TEXT NOT NULL REFERENCES drawings(id) ON DELETE CASCADE,
    element     TEXT NOT NULL,
    position    INTEGER NOT NULL,
    tag         TEXT NOT NULL,
    anim        TEXT NOT NULL,
    params      TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (drawing_id, element, position)
);
CREATE TABLE IF NOT EXISTS users (
    username             TEXT PRIMARY KEY,
    password_hash        TEXT NOT NULL,
    role                 TEXT NOT NULL,
    disabled             INTEGER NOT NULL DEFAULT 0,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at           REAL NOT NULL,
    updated_at           REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    username    TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    created_at  REAL NOT NULL,
    expires_at  REAL NOT NULL,
    ip          TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(username);
"""

PLC_FIELDS = ("name", "base_url", "username", "enabled", "sse_enabled", "verify_tls")
TAG_FIELDS = ("source", "plc", "description", "unit", "scale", "offset", "decimals",
              "writable", "min", "max", "confirm_write")
_BOOL_FIELDS = {"enabled", "sse_enabled", "verify_tls", "writable", "confirm_write", "disabled", "must_change_password"}
USER_FIELDS = ("password_hash", "role", "disabled", "must_change_password")


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

    # -------------------------------------------------------------- tegninger

    def list_drawings(self) -> list[dict[str, Any]]:
        return self._query(
            "SELECT d.*, (SELECT COUNT(*) FROM drawing_versions v WHERE v.drawing_id = d.id) AS version_count "
            "FROM drawings d ORDER BY d.name"
        )

    def get_drawing(self, drawing_id: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM drawings WHERE id = ?", (drawing_id,))
        return rows[0] if rows else None

    def list_versions(self, drawing_id: str) -> list[dict[str, Any]]:
        return self._query(
            "SELECT * FROM drawing_versions WHERE drawing_id = ? ORDER BY version DESC", (drawing_id,)
        )

    def add_drawing_version(self, drawing_id: str, name: str | None, meta: dict[str, Any], activate: bool) -> int:
        """Opret tegning (hvis `name` er givet og den ikke findes) + ny version, atomisk."""
        now = time.time()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                if name is not None:
                    cur.execute(
                        "INSERT INTO drawings(id, name, active_version, created_at, updated_at) VALUES (?,?,?,?,?)",
                        (drawing_id, name, 1, now, now),
                    )
                row = cur.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 FROM drawing_versions WHERE drawing_id = ?", (drawing_id,)
                ).fetchone()
                version = int(row[0])
                cur.execute(
                    "INSERT INTO drawing_versions(drawing_id, version, comment, size, width, height, created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (drawing_id, version, meta.get("comment", ""), meta["size"], meta.get("width"),
                     meta.get("height"), now),
                )
                if activate:
                    cur.execute("UPDATE drawings SET active_version = ?, updated_at = ? WHERE id = ?",
                                (version, now, drawing_id))
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise
        return version

    def set_active_version(self, drawing_id: str, version: int) -> bool:
        return self._execute("UPDATE drawings SET active_version = ?, updated_at = ? WHERE id = ?",
                             (version, time.time(), drawing_id)) > 0

    def rename_drawing(self, drawing_id: str, name: str) -> bool:
        return self._execute("UPDATE drawings SET name = ?, updated_at = ? WHERE id = ?",
                             (name, time.time(), drawing_id)) > 0

    def delete_drawing(self, drawing_id: str) -> bool:
        return self._execute("DELETE FROM drawings WHERE id = ?", (drawing_id,)) > 0

    # -------------------------------------------------------------- bindinger

    def list_bindings(self, drawing_id: str) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT element, position, tag, anim, params FROM bindings WHERE drawing_id = ? "
            "ORDER BY element, position", (drawing_id,)
        )
        for r in rows:
            r["params"] = json.loads(r["params"])
        return rows

    def set_element_bindings(self, drawing_id: str, element: str, items: list[dict[str, Any]]) -> None:
        """Erstat bindingerne for ÉT element (andre elementer røres ikke)."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                cur.execute("DELETE FROM bindings WHERE drawing_id = ? AND element = ?", (drawing_id, element))
                for pos, item in enumerate(items):
                    cur.execute(
                        "INSERT INTO bindings(drawing_id, element, position, tag, anim, params) VALUES (?,?,?,?,?,?)",
                        (drawing_id, element, pos, item["tag"], item["anim"], json.dumps(item.get("params", {}))),
                    )
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise

    def count_bindings_for_tag(self, tag: str) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM bindings WHERE tag = ?", (tag,)).fetchone()[0])

    # ------------------------------------------------------------- brugere

    def list_users(self) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM users ORDER BY username")

    def get_user(self, username: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM users WHERE username = ?", (username,))
        return rows[0] if rows else None

    def count_users(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def insert_user(self, username: str, values: dict[str, Any]) -> None:
        now = time.time()
        self._execute(
            "INSERT INTO users(username, password_hash, role, disabled, must_change_password, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (username, values["password_hash"], values["role"], _db("disabled", values.get("disabled", False)),
             _db("must_change_password", values.get("must_change_password", False)), now, now),
        )

    def update_user_guarded(self, username: str, changes: dict[str, Any], keep_admin: bool) -> str:
        """Opdatér en bruger atomisk. Med keep_admin afvises ændringen hvis den ville efterlade
        nul aktive administratorer (tjek og skriv i samme transaktion — ingen race mellem to admins).
        Returnerer 'ok', 'missing' eller 'last_admin'."""
        fields = [f for f in changes if f in USER_FIELDS]
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                if cur.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone() is None:
                    cur.execute("ROLLBACK")
                    return "missing"
                if fields:
                    sets = ", ".join(f"{f} = ?" for f in fields)
                    cur.execute(f"UPDATE users SET {sets}, updated_at = ? WHERE username = ?",
                                (*(_db(f, changes[f]) for f in fields), time.time(), username))
                if keep_admin and _active_admins(cur) == 0:
                    cur.execute("ROLLBACK")
                    return "last_admin"
                cur.execute("COMMIT")
                return "ok"
            except Exception:
                cur.execute("ROLLBACK")
                raise

    def delete_user_guarded(self, username: str) -> str:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                if cur.execute("DELETE FROM users WHERE username = ?", (username,)).rowcount == 0:
                    cur.execute("ROLLBACK")
                    return "missing"
                if _active_admins(cur) == 0:
                    cur.execute("ROLLBACK")
                    return "last_admin"
                cur.execute("DELETE FROM sessions WHERE username = ?", (username,))
                cur.execute("COMMIT")
                return "ok"
            except Exception:
                cur.execute("ROLLBACK")
                raise

    # ------------------------------------------------------------ sessioner

    def insert_session(self, token_hash: str, username: str, expires_at: float, ip: str) -> None:
        self._execute("INSERT INTO sessions(token_hash, username, created_at, expires_at, ip) VALUES (?,?,?,?,?)",
                      (token_hash, username, time.time(), expires_at, ip))

    def get_session(self, token_hash: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM sessions WHERE token_hash = ?", (token_hash,))
        return rows[0] if rows else None

    def touch_session(self, token_hash: str, expires_at: float) -> None:
        self._execute("UPDATE sessions SET expires_at = ? WHERE token_hash = ?", (expires_at, token_hash))

    def delete_session(self, token_hash: str) -> None:
        self._execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    def delete_user_sessions(self, username: str, except_hash: str | None = None) -> None:
        self._execute("DELETE FROM sessions WHERE username = ? AND token_hash != ?", (username, except_hash or ""))

    def purge_expired_sessions(self, now: float) -> None:
        self._execute("DELETE FROM sessions WHERE expires_at < ?", (now,))

    def _update(self, table: str, pk: str, key: str, changes: dict[str, Any], allowed: tuple[str, ...]) -> bool:
        fields = [f for f in changes if f in allowed]
        if not fields:
            return self._query(f"SELECT 1 FROM {table} WHERE {pk} = ?", (key,)) != []
        sets = ", ".join(f'"{f}" = ?' for f in fields)
        args = (*(_db(f, changes[f]) for f in fields), time.time(), key)
        return self._execute(f'UPDATE {table} SET {sets}, updated_at = ? WHERE {pk} = ?', args) > 0


def _active_admins(cur: sqlite3.Cursor) -> int:
    return int(cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND disabled = 0").fetchone()[0])


def _db(field: str, value: Any) -> Any:
    if field in _BOOL_FIELDS and value is not None:
        return 1 if value else 0
    return value


def _row(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    for f in _BOOL_FIELDS & out.keys():
        out[f] = bool(out[f])
    return out
