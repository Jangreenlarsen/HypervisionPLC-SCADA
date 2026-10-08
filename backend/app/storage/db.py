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

SCHEMA_VERSION = 6

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
CREATE TABLE IF NOT EXISTS audit (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL NOT NULL,
    username  TEXT NOT NULL,
    ip        TEXT NOT NULL DEFAULT '',
    action    TEXT NOT NULL,
    target    TEXT NOT NULL DEFAULT '',
    detail    TEXT NOT NULL DEFAULT '{}',
    result    TEXT NOT NULL,
    message   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS audit_ts ON audit(ts);
CREATE TABLE IF NOT EXISTS alarm_state (
    key         TEXT PRIMARY KEY,
    tag         TEXT NOT NULL DEFAULT '',
    plc         TEXT NOT NULL DEFAULT '',
    kind        TEXT NOT NULL,
    level       TEXT NOT NULL,
    priority    TEXT NOT NULL,
    state       TEXT NOT NULL,
    raised_at   REAL NOT NULL,
    value       TEXT NOT NULL DEFAULT 'null',
    message     TEXT NOT NULL DEFAULT '',
    acked_by    TEXT,
    acked_at    REAL
);
CREATE TABLE IF NOT EXISTS alarm_events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL NOT NULL,
    key       TEXT NOT NULL,
    tag       TEXT NOT NULL DEFAULT '',
    plc       TEXT NOT NULL DEFAULT '',
    level     TEXT NOT NULL,
    priority  TEXT NOT NULL,
    event     TEXT NOT NULL,
    value     TEXT NOT NULL DEFAULT 'null',
    username  TEXT NOT NULL DEFAULT '',
    message   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS alarm_events_ts ON alarm_events(ts);
CREATE TABLE IF NOT EXISTS user_drawings (
    username    TEXT NOT NULL,
    drawing_id  TEXT NOT NULL,
    PRIMARY KEY (username, drawing_id)
);
"""

PLC_FIELDS = ("name", "base_url", "username", "enabled", "sse_enabled", "verify_tls")
# Alarmgrænser pr. tag (NULL = ingen). alarm_on: NULL | 'true' | 'false' for til/fra-tags.
ALARM_COLUMNS = {
    "alarm_hh": "REAL", "alarm_h": "REAL", "alarm_l": "REAL", "alarm_ll": "REAL",
    "alarm_deadband": "REAL NOT NULL DEFAULT 0", "alarm_delay_s": "REAL NOT NULL DEFAULT 0", "alarm_on": "TEXT",
}
ALARM_FIELDS = tuple(ALARM_COLUMNS)
TAG_FIELDS = ("source", "plc", "description", "unit", "scale", "offset", "decimals",
              "writable", "min", "max", "confirm_write") + ALARM_FIELDS
_BOOL_FIELDS = {"enabled", "sse_enabled", "verify_tls", "writable", "confirm_write", "disabled", "must_change_password",
                "scoped"}
USER_FIELDS = ("password_hash", "role", "disabled", "must_change_password", "scoped")


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
            self._migrate()
            self._conn.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
            )

    def _migrate(self) -> None:
        """Tilføj kolonner til eksisterende databaser (CREATE TABLE IF NOT EXISTS ændrer ikke gamle tabeller)."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(users)").fetchall()}
        if "scoped" not in cols:
            # 0 = adgang til alle tegninger (som før) — eksisterende brugere bevarer deres adgang
            self._conn.execute("ALTER TABLE users ADD COLUMN scoped INTEGER NOT NULL DEFAULT 0")
        tag_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(tags)").fetchall()}
        for col, ddl in ALARM_COLUMNS.items():
            if col not in tag_cols:
                self._conn.execute(f"ALTER TABLE tags ADD COLUMN {col} {ddl}")
        self._conn.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'", (str(SCHEMA_VERSION),))

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
        defaults = {"alarm_deadband": 0.0, "alarm_delay_s": 0.0}
        args = (name, *(_db(f, values.get(f, defaults.get(f))) for f in TAG_FIELDS), now, now)
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

    # ------------------------------------------------------------- alarmer

    def list_alarm_states(self) -> list[dict[str, Any]]:
        rows = self._query("SELECT * FROM alarm_state ORDER BY raised_at DESC")
        for r in rows:
            r["value"] = json.loads(r["value"])
        return rows

    def upsert_alarm_state(self, row: dict[str, Any]) -> None:
        self._execute(
            "INSERT INTO alarm_state(key, tag, plc, kind, level, priority, state, raised_at, value, message, acked_by, "
            "acked_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET tag=excluded.tag, "
            "plc=excluded.plc, kind=excluded.kind, level=excluded.level, priority=excluded.priority, "
            "state=excluded.state, raised_at=excluded.raised_at, value=excluded.value, message=excluded.message, "
            "acked_by=excluded.acked_by, acked_at=excluded.acked_at",
            (row["key"], row["tag"], row["plc"], row["kind"], row["level"], row["priority"], row["state"],
             row["raised_at"], json.dumps(row["value"], default=str), row["message"], row.get("acked_by"),
             row.get("acked_at")))

    def delete_alarm_state(self, key: str) -> None:
        self._execute("DELETE FROM alarm_state WHERE key = ?", (key,))

    def insert_alarm_event(self, entry: dict[str, Any], keep: int) -> None:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO alarm_events(ts, key, tag, plc, level, priority, event, value, username, message) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (entry["ts"], entry["key"], entry["tag"], entry["plc"], entry["level"], entry["priority"],
                 entry["event"], json.dumps(entry.get("value"), default=str), entry.get("username", ""),
                 entry.get("message", "")))
            if cur.lastrowid and cur.lastrowid % 500 == 0:
                self._conn.execute("DELETE FROM alarm_events WHERE id <= ?", (cur.lastrowid - keep,))

    def list_alarm_events(self, limit: int) -> list[dict[str, Any]]:
        rows = self._query("SELECT * FROM alarm_events ORDER BY id DESC LIMIT ?", (limit,))
        for r in rows:
            r["value"] = json.loads(r["value"])
        return rows

    # ------------------------------------------------- adgang pr. tegning

    def get_user_drawings(self, username: str) -> list[str]:
        rows = self._query("SELECT drawing_id FROM user_drawings WHERE username = ? ORDER BY drawing_id", (username,))
        return [r["drawing_id"] for r in rows]

    def set_user_drawings(self, username: str, drawing_ids: list[str]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                cur.execute("DELETE FROM user_drawings WHERE username = ?", (username,))
                for did in drawing_ids:
                    cur.execute("INSERT INTO user_drawings(username, drawing_id) VALUES (?, ?)", (username, did))
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise

    def delete_drawing_scope(self, drawing_id: str) -> None:
        self._execute("DELETE FROM user_drawings WHERE drawing_id = ?", (drawing_id,))

    def delete_user_scope(self, username: str) -> None:
        self._execute("DELETE FROM user_drawings WHERE username = ?", (username,))

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

    # ------------------------------------------------------------------ audit

    def insert_audit(self, entry: dict[str, Any], keep: int) -> None:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO audit(ts, username, ip, action, target, detail, result, message) VALUES (?,?,?,?,?,?,?,?)",
                (entry["ts"], entry["username"], entry.get("ip", ""), entry["action"], entry.get("target", ""),
                 json.dumps(entry.get("detail", {}), ensure_ascii=False, default=str), entry["result"],
                 entry.get("message", "")),
            )
            if cur.lastrowid and cur.lastrowid % 500 == 0:  # oprydning engang imellem, ikke ved hver skrivning
                self._conn.execute("DELETE FROM audit WHERE id <= ?", (cur.lastrowid - keep,))

    def list_audit(self, limit: int, action_prefix: str | None = None) -> list[dict[str, Any]]:
        if action_prefix:
            rows = self._query("SELECT * FROM audit WHERE action LIKE ? ORDER BY id DESC LIMIT ?",
                               (action_prefix.replace("%", "") + "%", limit))
        else:
            rows = self._query("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,))
        for r in rows:
            r["detail"] = json.loads(r["detail"])
        return rows

    # ------------------------------------------------------- backup/restore

    def export_project(self) -> dict[str, Any]:
        """Hele projektet (uden brugere, sessioner og audit) — til backup."""
        return {
            "plcs": self._query("SELECT key, name, base_url, username, enabled, sse_enabled, verify_tls FROM plcs ORDER BY key"),
            "tags": self._query('SELECT name, source, description, unit, scale, "offset", decimals, writable, min, max, '
                                "confirm_write, " + ", ".join(ALARM_FIELDS) + " FROM tags ORDER BY name"),
            "drawings": self._query("SELECT id, name, active_version FROM drawings ORDER BY id"),
            "versions": self._query("SELECT drawing_id, version, comment, size, width, height, created_at "
                                    "FROM drawing_versions ORDER BY drawing_id, version"),
            "bindings": self.list_all_bindings(),
        }

    def list_all_bindings(self) -> list[dict[str, Any]]:
        rows = self._query("SELECT drawing_id, element, position, tag, anim, params FROM bindings "
                           "ORDER BY drawing_id, element, position")
        for r in rows:
            r["params"] = json.loads(r["params"])
        return rows

    def replace_project(self, data: dict[str, Any]) -> None:
        """Erstat PLC'er, tags, tegninger og bindinger i ÉN transaktion (alt eller intet).
        Brugere, sessioner og audit røres ikke."""
        now = time.time()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                for table in ("bindings", "drawing_versions", "drawings", "tags", "plcs"):
                    cur.execute(f"DELETE FROM {table}")
                for p in data["plcs"]:
                    cur.execute(
                        "INSERT INTO plcs(key, name, base_url, username, enabled, sse_enabled, verify_tls, created_at, "
                        "updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (p["key"], p["name"], p["base_url"], p["username"], _db("enabled", p["enabled"]),
                         _db("sse_enabled", p["sse_enabled"]), _db("verify_tls", p["verify_tls"]), now, now))
                for t in data["tags"]:
                    cur.execute(
                        'INSERT INTO tags(name, source, plc, description, unit, scale, "offset", decimals, writable, '
                        "min, max, confirm_write, " + ", ".join(ALARM_FIELDS) + ", created_at, updated_at) "
                        "VALUES (" + ",".join("?" * (14 + len(ALARM_FIELDS))) + ")",
                        (t["name"], t["source"], t["plc"], t["description"], t["unit"], t["scale"], t["offset"],
                         t["decimals"], _db("writable", t["writable"]), t["min"], t["max"],
                         _db("confirm_write", t["confirm_write"]),
                         *(t.get(f, 0.0 if f in ("alarm_deadband", "alarm_delay_s") else None) for f in ALARM_FIELDS),
                         now, now))
                for d in data["drawings"]:
                    cur.execute("INSERT INTO drawings(id, name, active_version, created_at, updated_at) VALUES (?,?,?,?,?)",
                                (d["id"], d["name"], d["active_version"], now, now))
                for v in data["versions"]:
                    cur.execute(
                        "INSERT INTO drawing_versions(drawing_id, version, comment, size, width, height, created_at) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (v["drawing_id"], v["version"], v["comment"], v["size"], v["width"], v["height"],
                         v.get("created_at") or now))
                for b in data["bindings"]:
                    cur.execute("INSERT INTO bindings(drawing_id, element, position, tag, anim, params) VALUES (?,?,?,?,?,?)",
                                (b["drawing_id"], b["element"], b["position"], b["tag"], b["anim"],
                                 json.dumps(b["params"])))
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise

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
