"""SQLite-lager (WAL). Lag 4b.

Opdateringer skriver kun de felter der faktisk ændres (CLAUDE.md regel 12: ingen
read-modify-write af hele rækker).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SCHEMA_VERSION = 14   # 14: tags.priority (FEATURE_TAG_PRIORITET)

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
    updated_at     REAL NOT NULL,
    disabled       INTEGER NOT NULL DEFAULT 0
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
CREATE TABLE IF NOT EXISTS schedules (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    tag           TEXT NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 1,
    default_value REAL,
    entries       TEXT NOT NULL DEFAULT '[]',
    exceptions    TEXT NOT NULL DEFAULT '[]',
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS symbol_meta (
    drawing_id  TEXT NOT NULL REFERENCES drawings(id) ON DELETE CASCADE,
    element     TEXT NOT NULL,
    description TEXT NOT NULL,
    PRIMARY KEY (drawing_id, element)
);
-- Symbolstandard (docs/SYMBOLSTANDARD_IMPLEMENTERING.md afsnit 3): én konfiguration pr. symbol,
-- PIN-hash adskilt (kommer aldrig i svar eller backup) og den lokale tilstand (sidst valgte position).
CREATE TABLE IF NOT EXISTS symbol_config (
    drawing_id  TEXT NOT NULL REFERENCES drawings(id) ON DELETE CASCADE,
    element     TEXT NOT NULL,
    config      TEXT NOT NULL,
    updated_at  REAL NOT NULL,
    updated_by  TEXT NOT NULL,
    PRIMARY KEY (drawing_id, element)
);
CREATE TABLE IF NOT EXISTS symbol_pins (
    drawing_id  TEXT NOT NULL REFERENCES drawings(id) ON DELETE CASCADE,
    element     TEXT NOT NULL,
    pin_hash    TEXT NOT NULL,
    set_by      TEXT NOT NULL,
    set_at      REAL NOT NULL,
    PRIMARY KEY (drawing_id, element)
);
CREATE TABLE IF NOT EXISTS symbol_state (
    drawing_id  TEXT NOT NULL REFERENCES drawings(id) ON DELETE CASCADE,
    element     TEXT NOT NULL,
    chosen      INTEGER,
    chosen_at   REAL NOT NULL,
    chosen_by   TEXT NOT NULL,
    PRIMARY KEY (drawing_id, element)
);
-- Navngivne symbolgrupper (v0.130.0): et udvalg af elementer på en tegning; samme element må være i flere grupper.
CREATE TABLE IF NOT EXISTS symbol_groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    drawing_id  TEXT NOT NULL REFERENCES drawings(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL,
    sort        INTEGER NOT NULL DEFAULT 0,
    updated_at  REAL NOT NULL,
    updated_by  TEXT NOT NULL,
    UNIQUE (drawing_id, name)
);
CREATE TABLE IF NOT EXISTS symbol_group_members (
    group_id    INTEGER NOT NULL REFERENCES symbol_groups(id) ON DELETE CASCADE,
    element     TEXT NOT NULL,
    sort        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (group_id, element)
);
-- Animationer ejet af en gruppe (v0.131.0): pr. gruppe og medlem en liste af animationer (samme form som symbolets egne)
CREATE TABLE IF NOT EXISTS symbol_group_anims (
    group_id    INTEGER NOT NULL REFERENCES symbol_groups(id) ON DELETE CASCADE,
    element     TEXT NOT NULL,
    anims       TEXT NOT NULL,
    updated_at  REAL NOT NULL,
    updated_by  TEXT NOT NULL,
    PRIMARY KEY (group_id, element)
);
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
# Trend-historik pr. tag: slået fra som standard; minimumsinterval mellem gemte værdier.
TREND_COLUMNS = {"trend": "INTEGER NOT NULL DEFAULT 0", "trend_interval_s": "REAL NOT NULL DEFAULT 10"}
TREND_FIELDS = tuple(TREND_COLUMNS)
# Energi pr. tag: None | 'counter' (tæller) | 'power' (effekt); faktor omregner til kWh.
ENERGY_COLUMNS = {"energy": "TEXT", "energy_factor": "REAL NOT NULL DEFAULT 1"}
ENERGY_FIELDS = tuple(ENERGY_COLUMNS)
# Prioritet pr. tag (v2.0.0): "high" = eksterne tags læses med prio=high i PLC'ens Modbus-kø
PRIORITY_COLUMNS = {"priority": "TEXT NOT NULL DEFAULT 'normal'"}
PRIORITY_FIELDS = tuple(PRIORITY_COLUMNS)
TAG_FIELDS = ("source", "plc", "description", "unit", "scale", "offset", "decimals",
              "writable", "min", "max", "confirm_write") + ALARM_FIELDS + TREND_FIELDS + ENERGY_FIELDS + PRIORITY_FIELDS
_BOOL_FIELDS = {"enabled", "sse_enabled", "verify_tls", "writable", "confirm_write", "disabled", "must_change_password",
                "scoped", "trend"}
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
        drawing_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(drawings)").fetchall()}
        if "disabled" not in drawing_cols:
            # v1.6.0: en deaktiveret tegning er offline (ingen live-data, ingen betjening). 0 = aktiv som før.
            self._conn.execute("ALTER TABLE drawings ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0")
        tag_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(tags)").fetchall()}
        for col, ddl in {**ALARM_COLUMNS, **TREND_COLUMNS, **ENERGY_COLUMNS, **PRIORITY_COLUMNS}.items():
            if col not in tag_cols:
                self._conn.execute(f"ALTER TABLE tags ADD COLUMN {col} {ddl}")
        # Brugernavne er unikke uanset store/små bogstaver. Findes der allerede dubletter, springes indekset over
        # (de eksisterende konti røres ikke) — oprettelse tjekkes under alle omstændigheder i `get_user_ci`.
        try:
            self._conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username_ci ON users(lower(username))")
        except sqlite3.IntegrityError:
            log.warning("Brugernavne med forskellig store/små bogstaver findes allerede — unikt indeks springes over")
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
        defaults = {"alarm_deadband": 0.0, "alarm_delay_s": 0.0, "trend": False, "trend_interval_s": 10.0,
                    "energy_factor": 1.0, "priority": "normal"}
        args = (name, *(_db(f, values.get(f, defaults.get(f))) for f in TAG_FIELDS), now, now)
        quoted = ",".join(f'"{c}"' for c in cols)
        self._execute(f"INSERT INTO tags({quoted}) VALUES ({','.join('?' * len(cols))})", args)

    def update_tag(self, name: str, changes: dict[str, Any]) -> bool:
        return self._update("tags", "name", name, changes, TAG_FIELDS)

    def delete_tag(self, name: str) -> bool:
        return self._execute("DELETE FROM tags WHERE name = ?", (name,)) > 0

    # -------------------------------------------------------------- tegninger

    # ------------------------------------------------------------- indstillinger

    def get_setting(self, key: str) -> str | None:
        rows = self._query("SELECT value FROM meta WHERE key = ?", (f"setting.{key}",))
        return rows[0]["value"] if rows else None

    def set_setting(self, key: str, value: str | None) -> None:
        """Sæt (eller fjern med None) én indstilling — én række, så samtidige ændringer af andre nøgler ikke røres."""
        with self._lock:
            if value is None:
                self._conn.execute("DELETE FROM meta WHERE key = ?", (f"setting.{key}",))
            else:
                self._conn.execute("INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                                   (f"setting.{key}", value))
            self._conn.commit()

    # ------------------------------------------------------- gemte trend-visninger (v1.16.0)

    @staticmethod
    def _trendview_key(name: str) -> str:
        return f"trendview.{name.strip().casefold()}"

    # Tilslutningspunkter pr. bibliotekssymbol (symbol-editoren): meta-nøgle symbolports.<type> → JSON [[fx, fy], …]
    def list_symbol_ports(self) -> dict[str, list[list[float]]]:
        out: dict[str, list[list[float]]] = {}
        for r in self._query("SELECT key, value FROM meta WHERE key LIKE 'symbolports.%' ORDER BY key"):
            try:
                ports = json.loads(r["value"])
            except ValueError:
                continue   # beskadiget række — symbolet bruger de automatiske punkter
            if isinstance(ports, list) and all(isinstance(p, list) and len(p) == 2 for p in ports):
                out[r["key"][len("symbolports."):]] = ports
        return out

    def set_symbol_ports(self, sym_type: str, ports: list[list[float]] | None) -> bool:
        """Gem (ports) eller slet (None). → om der var noget (ved gem altid True)."""
        key = f"symbolports.{sym_type}"
        if ports is None:
            return self._execute("DELETE FROM meta WHERE key = ?", (key,)) > 0
        self._execute("INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                      (key, json.dumps(ports)))
        return True

    def list_trend_views(self) -> list[dict[str, Any]]:
        out = []
        for r in self._query("SELECT value FROM meta WHERE key LIKE 'setting.trendview.%'"):
            try:
                out.append(json.loads(r["value"]))
            except ValueError:
                continue   # beskadiget række — springes over
        return sorted(out, key=lambda v: str(v.get("name", "")).casefold())

    def set_trend_view(self, name: str, view: dict[str, Any] | None) -> bool:
        """Gem (view) eller slet (None) én visning. → om der var noget at slette (ved gem altid True)."""
        key = self._trendview_key(name)
        if view is None:
            had = self.get_setting(key) is not None
            self.set_setting(key, None)
            return had
        self.set_setting(key, json.dumps(view, ensure_ascii=False))
        return True

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

    def set_drawing_disabled(self, drawing_id: str, disabled: bool) -> bool:
        return self._execute("UPDATE drawings SET disabled = ?, updated_at = ? WHERE id = ?",
                             (1 if disabled else 0, time.time(), drawing_id)) > 0

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

    def set_symbol_bindings(self, drawing_id: str, per_element: dict[str, list[dict[str, Any]]]) -> None:
        """Erstat bindingerne for flere elementer (et symbols dele) i ÉN transaktion — alt eller intet."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                for element, items in per_element.items():
                    cur.execute("DELETE FROM bindings WHERE drawing_id = ? AND element = ?", (drawing_id, element))
                    for pos, item in enumerate(items):
                        cur.execute(
                            "INSERT INTO bindings(drawing_id, element, position, tag, anim, params) VALUES (?,?,?,?,?,?)",
                            (drawing_id, element, pos, item["tag"], item["anim"], json.dumps(item.get("params", {}))))
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise

    # ------------------------------------------------- symbolers forklaring (pr. tegning + element)

    def list_symbol_meta(self, drawing_id: str) -> dict[str, str]:
        return {r["element"]: r["description"]
                for r in self._query("SELECT element, description FROM symbol_meta WHERE drawing_id = ?", (drawing_id,))}

    def list_all_symbol_meta(self) -> list[dict[str, Any]]:
        return self._query("SELECT drawing_id, element, description FROM symbol_meta ORDER BY drawing_id, element")

    def set_symbol_description(self, drawing_id: str, element: str, description: str) -> None:
        """Tom tekst fjerner forklaringen. Én række pr. element — andre elementer røres ikke."""
        if not description:
            self._execute("DELETE FROM symbol_meta WHERE drawing_id = ? AND element = ?", (drawing_id, element))
        else:
            self._execute("INSERT INTO symbol_meta(drawing_id, element, description) VALUES (?,?,?) "
                          "ON CONFLICT(drawing_id, element) DO UPDATE SET description = excluded.description",
                          (drawing_id, element, description))

    # ------------------------------------------------------------ symbolgrupper

    def list_symbol_groups(self, drawing_id: str | None = None) -> list[dict[str, Any]]:
        """Grupper med deres medlemmer (i rækkefølge) — for én tegning, eller alle (til backup)."""
        where, args = ("WHERE g.drawing_id = ?", (drawing_id,)) if drawing_id is not None else ("", ())
        groups = self._query(f"SELECT g.id, g.drawing_id, g.name, g.kind, g.sort FROM symbol_groups g {where} "
                             "ORDER BY g.drawing_id, CASE g.kind WHEN 'function' THEN 0 ELSE 1 END, g.sort, g.id", args)
        members = self._query("SELECT m.group_id, m.element FROM symbol_group_members m "
                              f"JOIN symbol_groups g ON g.id = m.group_id {where} ORDER BY m.group_id, m.sort", args)
        by_group: dict[int, list[str]] = {}
        for m in members:
            by_group.setdefault(m["group_id"], []).append(m["element"])
        return [{**g, "members": by_group.get(g["id"], [])} for g in groups]

    def get_symbol_group(self, drawing_id: str, group_id: int) -> dict[str, Any] | None:
        return next((g for g in self.list_symbol_groups(drawing_id) if g["id"] == group_id), None)

    def save_symbol_group(self, drawing_id: str, group_id: int | None, name: str, kind: str,
                          members: list[str] | None, user: str) -> int | None:
        """Opret (group_id None) eller ret én gruppe i ÉN transaktion. members None = medlemmerne røres ikke.
        Returnerer id, eller None hvis gruppen ikke findes. Kaster sqlite3.IntegrityError ved dublet-navn."""
        now = time.time()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                if group_id is None:
                    nxt = cur.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM symbol_groups WHERE drawing_id = ?",
                                      (drawing_id,)).fetchone()[0]
                    group_id = cur.execute("INSERT INTO symbol_groups(drawing_id, name, kind, sort, updated_at, updated_by) "
                                           "VALUES (?,?,?,?,?,?)", (drawing_id, name, kind, nxt, now, user)).lastrowid
                else:
                    n = cur.execute("UPDATE symbol_groups SET name = ?, kind = ?, updated_at = ?, updated_by = ? "
                                    "WHERE id = ? AND drawing_id = ?", (name, kind, now, user, group_id, drawing_id)).rowcount
                    if not n:
                        cur.execute("ROLLBACK")
                        return None
                if members is not None:
                    cur.execute("DELETE FROM symbol_group_members WHERE group_id = ?", (group_id,))
                    cur.executemany("INSERT INTO symbol_group_members(group_id, element, sort) VALUES (?,?,?)",
                                    [(group_id, el, i) for i, el in enumerate(members)])
                    cur.execute("DELETE FROM symbol_group_anims WHERE group_id = ? AND element NOT IN "
                                "(SELECT element FROM symbol_group_members WHERE group_id = ?)", (group_id, group_id))
                cur.execute("COMMIT")
                return group_id
            except Exception:
                cur.execute("ROLLBACK")
                raise

    def change_group_members(self, drawing_id: str, group_id: int, add: list[str], remove: list[str], user: str) -> bool:
        """Tilføj/fjern enkelte medlemmer i ÉN transaktion — rører ikke de andre (ingen overskrivning af en kollegas ændringer).
        Fjernede medlemmers animationer fjernes med. False hvis gruppen ikke findes."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                if cur.execute("SELECT 1 FROM symbol_groups WHERE id = ? AND drawing_id = ?", (group_id, drawing_id)).fetchone() is None:
                    cur.execute("ROLLBACK")
                    return False
                nxt = cur.execute("SELECT COALESCE(MAX(sort), -1) + 1 FROM symbol_group_members WHERE group_id = ?", (group_id,)).fetchone()[0]
                for el in add:
                    if el in remove:
                        continue
                    n = cur.execute("INSERT OR IGNORE INTO symbol_group_members(group_id, element, sort) VALUES (?,?,?)",
                                    (group_id, el, nxt)).rowcount
                    nxt += n
                for el in remove:
                    cur.execute("DELETE FROM symbol_group_members WHERE group_id = ? AND element = ?", (group_id, el))
                    cur.execute("DELETE FROM symbol_group_anims WHERE group_id = ? AND element = ?", (group_id, el))
                cur.execute("UPDATE symbol_groups SET updated_at = ?, updated_by = ? WHERE id = ?", (time.time(), user, group_id))
                cur.execute("COMMIT")
                return True
            except Exception:
                cur.execute("ROLLBACK")
                raise

    def rename_element_in_groups(self, drawing_id: str, old: str, new: str, group_id: int | None = None,
                                 valid_parts: set[str] | None = None) -> dict[str, Any]:
        """Flyt et elements medlemskab (og dets gruppe-animationer) fra et id til et andet — fx når et symbol har fået nyt id.
        Delene følger id-mønstret `<gammelt>_<del>` → `<nyt>_<del>`; er `valid_parts` givet, droppes animationer på dele der ikke
        findes på målet. Er `new` allerede medlem af gruppen, fjernes `old` og dets animationer (nye id'ets bevares).
        Returnerer {groups, dropped: [dele], discarded: antal animationer kasseret ved sammenfald}."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                sql = ("SELECT m.group_id FROM symbol_group_members m JOIN symbol_groups g ON g.id = m.group_id "
                       "WHERE g.drawing_id = ? AND m.element = ?")
                args: list[Any] = [drawing_id, old]
                if group_id is not None:
                    sql += " AND g.id = ?"
                    args.append(group_id)
                moved, dropped, discarded = 0, [], 0
                for (gid,) in cur.execute(sql, args).fetchall():
                    row = cur.execute("SELECT anims FROM symbol_group_anims WHERE group_id = ? AND element = ?", (gid, old)).fetchone()
                    old_anims: list[dict[str, Any]] = json.loads(row[0]) if row else []
                    if cur.execute("SELECT 1 FROM symbol_group_members WHERE group_id = ? AND element = ?", (gid, new)).fetchone():
                        cur.execute("DELETE FROM symbol_group_members WHERE group_id = ? AND element = ?", (gid, old))
                        cur.execute("DELETE FROM symbol_group_anims WHERE group_id = ? AND element = ?", (gid, old))
                        discarded += len(old_anims)
                    else:
                        cur.execute("UPDATE symbol_group_members SET element = ? WHERE group_id = ? AND element = ?", (new, gid, old))
                        kept: list[dict[str, Any]] = []
                        for a in old_anims:
                            part = a.get("part", "all")
                            if part != "all":
                                part = new + part[len(old):] if part.startswith(old + "_") else part
                                if valid_parts is not None and part not in valid_parts:
                                    dropped.append(a.get("part", ""))
                                    continue
                            kept.append({**a, "part": part})
                        cur.execute("DELETE FROM symbol_group_anims WHERE group_id = ? AND element = ?", (gid, old))
                        if kept:
                            cur.execute("INSERT INTO symbol_group_anims(group_id, element, anims, updated_at, updated_by) VALUES (?,?,?,?,?)",
                                        (gid, new, json.dumps(kept, ensure_ascii=False), time.time(), "flyt"))
                    moved += 1
                cur.execute("COMMIT")
                return {"groups": moved, "dropped": list(dict.fromkeys(dropped)), "discarded": discarded}
            except Exception:
                cur.execute("ROLLBACK")
                raise

    def reorder_symbol_groups(self, drawing_id: str, ids: list[int]) -> bool:
        """Gruppernes rækkefølge (afgør hvem der vinder ved overlap). `ids` skal være præcis tegningens grupper."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                have = {r[0] for r in cur.execute("SELECT id FROM symbol_groups WHERE drawing_id = ?", (drawing_id,)).fetchall()}
                if set(ids) != have or len(ids) != len(have):
                    cur.execute("ROLLBACK")
                    return False
                for i, gid in enumerate(ids):
                    cur.execute("UPDATE symbol_groups SET sort = ? WHERE id = ?", (i, gid))
                cur.execute("COMMIT")
                return True
            except Exception:
                cur.execute("ROLLBACK")
                raise

    def list_group_anims(self, drawing_id: str | None = None, group_id: int | None = None) -> list[dict[str, Any]]:
        """Gruppe-animationer i gruppens rækkefølge: [{group_id, group_name, drawing_id, element, anims}]."""
        where, args = [], []
        if drawing_id is not None:
            where.append("g.drawing_id = ?"); args.append(drawing_id)
        if group_id is not None:
            where.append("g.id = ?"); args.append(group_id)
        rows = self._query("SELECT a.group_id, g.name AS group_name, g.drawing_id, a.element, a.anims FROM symbol_group_anims a "
                           "JOIN symbol_groups g ON g.id = a.group_id "
                           + ("WHERE " + " AND ".join(where) + " " if where else "")
                           + "ORDER BY g.drawing_id, CASE g.kind WHEN 'function' THEN 0 ELSE 1 END, g.sort, g.id, a.element", tuple(args))
        return [{**r, "anims": json.loads(r["anims"])} for r in rows]

    def set_group_anims(self, group_id: int, element: str, anims: list[dict[str, Any]], user: str) -> bool:
        """Tom liste fjerner rækken. Én række pr. (gruppe, element) — andre røres ikke. Skrivningen sker kun, hvis elementet
        STADIG er medlem (tjekket i selve skrivningen — en kollega kan have fjernet det imens); ellers False og intet skrives."""
        if not anims:
            self._execute("DELETE FROM symbol_group_anims WHERE group_id = ? AND element = ?", (group_id, element))
            return True
        return self._execute(
            "INSERT INTO symbol_group_anims(group_id, element, anims, updated_at, updated_by) "
            "SELECT ?,?,?,?,? WHERE EXISTS (SELECT 1 FROM symbol_group_members WHERE group_id = ? AND element = ?) "
            "ON CONFLICT(group_id, element) DO UPDATE SET anims = excluded.anims, updated_at = excluded.updated_at, "
            "updated_by = excluded.updated_by",
            (group_id, element, json.dumps(anims, ensure_ascii=False), time.time(), user, group_id, element)) > 0

    def delete_symbol_group(self, drawing_id: str, group_id: int) -> bool:
        return self._execute("DELETE FROM symbol_groups WHERE id = ? AND drawing_id = ?", (group_id, drawing_id)) > 0

    # ------------------------------------------------------------ symbolstandard

    def get_symbol_config(self, drawing_id: str, element: str) -> dict[str, Any] | None:
        rows = self._query("SELECT config, updated_at, updated_by FROM symbol_config WHERE drawing_id = ? AND element = ?",
                           (drawing_id, element))
        if not rows:
            return None
        return {**rows[0], "config": json.loads(rows[0]["config"])}

    def list_symbol_configs(self, drawing_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT drawing_id, element, config, updated_at, updated_by FROM symbol_config"
        rows = (self._query(sql + " WHERE drawing_id = ? ORDER BY element", (drawing_id,)) if drawing_id is not None
                else self._query(sql + " ORDER BY drawing_id, element"))
        for r in rows:
            r["config"] = json.loads(r["config"])
        return rows

    def set_symbol_config(self, drawing_id: str, element: str, config: dict[str, Any], username: str) -> None:
        self._execute("INSERT INTO symbol_config(drawing_id, element, config, updated_at, updated_by) VALUES (?,?,?,?,?) "
                      "ON CONFLICT(drawing_id, element) DO UPDATE SET config = excluded.config, "
                      "updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                      (drawing_id, element, json.dumps(config, ensure_ascii=False), time.time(), username))

    def delete_symbol_config(self, drawing_id: str, element: str) -> bool:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                n = cur.execute("DELETE FROM symbol_config WHERE drawing_id = ? AND element = ?",
                                (drawing_id, element)).rowcount
                cur.execute("DELETE FROM symbol_pins WHERE drawing_id = ? AND element = ?", (drawing_id, element))
                cur.execute("DELETE FROM symbol_state WHERE drawing_id = ? AND element = ?", (drawing_id, element))
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise
        return n > 0

    def get_symbol_pin_hash(self, drawing_id: str, element: str) -> str | None:
        rows = self._query("SELECT pin_hash FROM symbol_pins WHERE drawing_id = ? AND element = ?", (drawing_id, element))
        return rows[0]["pin_hash"] if rows else None

    def set_symbol_pin_hash(self, drawing_id: str, element: str, pin_hash: str, username: str) -> None:
        self._execute("INSERT INTO symbol_pins(drawing_id, element, pin_hash, set_by, set_at) VALUES (?,?,?,?,?) "
                      "ON CONFLICT(drawing_id, element) DO UPDATE SET pin_hash = excluded.pin_hash, "
                      "set_by = excluded.set_by, set_at = excluded.set_at",
                      (drawing_id, element, pin_hash, username, time.time()))

    def delete_symbol_pin(self, drawing_id: str, element: str) -> bool:
        return self._execute("DELETE FROM symbol_pins WHERE drawing_id = ? AND element = ?", (drawing_id, element)) > 0

    def symbol_pin_keys(self) -> set[tuple[str, str]]:
        return {(r["drawing_id"], r["element"]) for r in self._query("SELECT drawing_id, element FROM symbol_pins")}

    def get_symbol_state(self, drawing_id: str, element: str) -> dict[str, Any] | None:
        rows = self._query("SELECT chosen, chosen_at, chosen_by FROM symbol_state WHERE drawing_id = ? AND element = ?",
                           (drawing_id, element))
        return rows[0] if rows else None

    def list_symbol_states(self) -> list[dict[str, Any]]:
        return self._query("SELECT drawing_id, element, chosen, chosen_at, chosen_by FROM symbol_state")

    def set_symbol_state(self, drawing_id: str, element: str, chosen: int | None, chosen_at: float, chosen_by: str) -> None:
        self._execute("INSERT INTO symbol_state(drawing_id, element, chosen, chosen_at, chosen_by) VALUES (?,?,?,?,?) "
                      "ON CONFLICT(drawing_id, element) DO UPDATE SET chosen = excluded.chosen, "
                      "chosen_at = excluded.chosen_at, chosen_by = excluded.chosen_by",
                      (drawing_id, element, chosen, chosen_at, chosen_by))

    def drawings_using_tag(self, tag: str) -> list[tuple[str, int]]:
        """[(tegningens navn, antal bindinger)] der bruger tagget (også som løbelysets retnings-tag) — til beskeden ved sletning."""
        return [(r["name"], r["n"]) for r in self._query(
            "SELECT d.name AS name, COUNT(*) AS n FROM bindings b JOIN drawings d ON d.id = b.drawing_id "
            "WHERE b.tag = ? OR (b.anim = 'flow' AND json_extract(b.params, '$.dir_tag') = ?) GROUP BY d.id ORDER BY d.name", (tag, tag))]

    def binding_places(self, tag: str) -> list[str]:
        """["Tegning: element", …] for bindinger der bruger tagget — så beskeden ved sletning siger præcis hvor (B3)."""
        return [f"{r['name']}: {r['element']}" for r in self._query(
            "SELECT d.name AS name, b.element AS element FROM bindings b JOIN drawings d ON d.id = b.drawing_id "
            "WHERE b.tag = ? OR (b.anim = 'flow' AND json_extract(b.params, '$.dir_tag') = ?) "
            "GROUP BY d.id, b.element ORDER BY d.name, b.element", (tag, tag))]

    def count_bindings_for_tag(self, tag: str) -> int:
        with self._lock:
            # Også løbelys der bruger tagget som retnings-tag (params.dir_tag)
            return int(self._conn.execute(
                "SELECT COUNT(*) FROM bindings WHERE tag = ? OR (anim = 'flow' AND json_extract(params, '$.dir_tag') = ?)",
                (tag, tag)).fetchone()[0])

    # ------------------------------------------------------------- brugere

    def list_users(self) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM users ORDER BY username")

    def get_user_ci(self, username: str) -> dict[str, Any] | None:
        """Som get_user, men uden hensyn til store/små bogstaver (til tjek af dubletter ved oprettelse)."""
        rows = self._query("SELECT * FROM users WHERE lower(username) = lower(?)", (username,))
        return rows[0] if rows else None

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

    def users_with_drawing(self, drawing_id: str) -> list[str]:
        """Brugere der er begrænset til udvalgte tegninger og har denne iblandt."""
        return [r["username"] for r in self._query(
            "SELECT username FROM user_drawings WHERE drawing_id = ? ORDER BY username", (drawing_id,))]

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
                                "confirm_write, " + ", ".join(ALARM_FIELDS + TREND_FIELDS + ENERGY_FIELDS + PRIORITY_FIELDS) + " FROM tags ORDER BY name"),
            "drawings": self._query("SELECT id, name, active_version, disabled FROM drawings ORDER BY id"),
            "versions": self._query("SELECT drawing_id, version, comment, size, width, height, created_at "
                                    "FROM drawing_versions ORDER BY drawing_id, version"),
            "bindings": self.list_all_bindings(),
            "symbol_meta": self.list_all_symbol_meta(),
            # Symbol-konfigurationer — men aldrig PIN-hashes eller driftstilstand (symbol_pins/symbol_state)
            "symbol_config": [{"drawing_id": r["drawing_id"], "element": r["element"], "config": r["config"]}
                              for r in self.list_symbol_configs()],
            "symbol_groups": self._export_groups(),
            "trend_views": self.list_trend_views(),
            "symbol_ports": self.list_symbol_ports(),
            "settings": {"start_drawing": self.get_setting("start_drawing")},
            "schedules": [{k: s[k] for k in ("name", "tag", "enabled", "default_value", "entries", "exceptions")}
                          for s in self.list_schedules()],
        }

    # -------------------------------------------------------------- ugeprogrammer

    def _schedule_row(self, r: dict[str, Any]) -> dict[str, Any]:
        return {**r, "enabled": bool(r["enabled"]), "entries": json.loads(r["entries"]),
                "exceptions": json.loads(r["exceptions"])}

    def list_schedules(self) -> list[dict[str, Any]]:
        return [self._schedule_row(r) for r in self._query("SELECT * FROM schedules ORDER BY name")]

    def get_schedule(self, sid: int) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM schedules WHERE id = ?", (sid,))
        return self._schedule_row(rows[0]) if rows else None

    def get_schedule_by_name(self, name: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM schedules WHERE name = ?", (name,))
        return self._schedule_row(rows[0]) if rows else None

    def insert_schedule(self, s: dict[str, Any]) -> int:
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO schedules(name, tag, enabled, default_value, entries, exceptions, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (s["name"], s["tag"], int(s["enabled"]), s["default_value"], json.dumps(s["entries"]),
                 json.dumps(s["exceptions"]), now, now))
            self._conn.commit()
            return int(cur.lastrowid)

    def update_schedule(self, sid: int, s: dict[str, Any]) -> None:
        self._execute("UPDATE schedules SET name = ?, tag = ?, enabled = ?, default_value = ?, entries = ?, "
                      "exceptions = ?, updated_at = ? WHERE id = ?",
                      (s["name"], s["tag"], int(s["enabled"]), s["default_value"], json.dumps(s["entries"]),
                       json.dumps(s["exceptions"]), time.time(), sid))

    def delete_schedule(self, sid: int) -> bool:
        return self._execute("DELETE FROM schedules WHERE id = ?", (sid,)) > 0

    def list_energy_tags(self) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM tags WHERE energy IS NOT NULL ORDER BY name")

    def list_trend_tags(self) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM tags WHERE trend = 1 ORDER BY name")

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
                # B5 (funktionsanalyse): PIN-koder er ikke i backuppen, men forsvinder med tegningerne (CASCADE) — gem dem
                # og læg dem tilbage for symboler der stadig findes efter gendannelsen.
                pins = cur.execute("SELECT drawing_id, element, pin_hash, set_by, set_at FROM symbol_pins").fetchall()
                for table in ("schedules", "symbol_meta", "bindings", "drawing_versions", "drawings", "tags", "plcs"):
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
                        "min, max, confirm_write, " + ", ".join(ALARM_FIELDS + TREND_FIELDS + ENERGY_FIELDS + PRIORITY_FIELDS) + ", created_at, updated_at) "
                        "VALUES (" + ",".join("?" * (14 + len(ALARM_FIELDS) + len(TREND_FIELDS) + len(ENERGY_FIELDS) + len(PRIORITY_FIELDS))) + ")",
                        (t["name"], t["source"], t["plc"], t["description"], t["unit"], t["scale"], t["offset"],
                         t["decimals"], _db("writable", t["writable"]), t["min"], t["max"],
                         _db("confirm_write", t["confirm_write"]),
                         *(t.get(f, 0.0 if f in ("alarm_deadband", "alarm_delay_s") else None) for f in ALARM_FIELDS),
                         _db("trend", t.get("trend", False)), t.get("trend_interval_s", 10.0),
                         t.get("energy"), t.get("energy_factor", 1.0), t.get("priority") or "normal",
                         now, now))
                for d in data["drawings"]:
                    cur.execute("INSERT INTO drawings(id, name, active_version, created_at, updated_at, disabled) VALUES (?,?,?,?,?,?)",
                                (d["id"], d["name"], d["active_version"], now, now, 1 if d.get("disabled") else 0))
                for s in data.get("schedules", []):
                    cur.execute(
                        "INSERT INTO schedules(name, tag, enabled, default_value, entries, exceptions, created_at, updated_at) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (s["name"], s["tag"], int(s["enabled"]), s["default_value"], json.dumps(s["entries"]),
                         json.dumps(s["exceptions"]), now, now))
                # Start-tegningen følger projektet (samme transaktion — kan ikke pege på en tegning der ikke findes)
                cur.execute("DELETE FROM meta WHERE key = 'setting.start_drawing'")
                cur.execute("DELETE FROM meta WHERE key LIKE 'setting.trendview.%'")
                cur.execute("DELETE FROM meta WHERE key LIKE 'symbolports.%'")
                for sym_type, ports in (data.get("symbol_ports") or {}).items():
                    cur.execute("INSERT INTO meta(key, value) VALUES (?, ?)", (f"symbolports.{sym_type}", json.dumps(ports)))
                for v in data.get("trend_views", []):
                    cur.execute("INSERT INTO meta(key, value) VALUES (?, ?)",
                                (f"setting.{self._trendview_key(v['name'])}", json.dumps(v, ensure_ascii=False)))
                start = (data.get("settings") or {}).get("start_drawing")
                if start:
                    cur.execute("INSERT INTO meta(key, value) VALUES ('setting.start_drawing', ?)", (start,))
                for v in data["versions"]:
                    cur.execute(
                        "INSERT INTO drawing_versions(drawing_id, version, comment, size, width, height, created_at) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (v["drawing_id"], v["version"], v["comment"], v["size"], v["width"], v["height"],
                         v.get("created_at") or now))
                for m in data.get("symbol_meta", []):
                    cur.execute("INSERT INTO symbol_meta(drawing_id, element, description) VALUES (?,?,?)",
                                (m["drawing_id"], m["element"], m["description"]))
                # Tegningerne er slettet ovenfor → symbol_config/-pins/-state er væk via ON DELETE CASCADE.
                # Konfigurationerne lægges ind igen; koder kun for symboler der fandtes før (samme server).
                for c in data.get("symbol_config", []):
                    cur.execute("INSERT INTO symbol_config(drawing_id, element, config, updated_at, updated_by) "
                                "VALUES (?,?,?,?,?)",
                                (c["drawing_id"], c["element"], json.dumps(c["config"], ensure_ascii=False), now, "restore"))
                restored = {(c["drawing_id"], c["element"]) for c in data.get("symbol_config", [])}
                cur.executemany("INSERT INTO symbol_pins(drawing_id, element, pin_hash, set_by, set_at) VALUES (?,?,?,?,?)",
                                [tuple(p) for p in pins if (p[0], p[1]) in restored])
                for i, g in enumerate(data.get("symbol_groups", [])):
                    gid = cur.execute("INSERT INTO symbol_groups(drawing_id, name, kind, sort, updated_at, updated_by) "
                                      "VALUES (?,?,?,?,?,?)", (g["drawing_id"], g["name"], g["kind"], i, now, "restore")).lastrowid
                    cur.executemany("INSERT INTO symbol_group_members(group_id, element, sort) VALUES (?,?,?)",
                                    [(gid, el, j) for j, el in enumerate(g["members"])])
                    for el, anims in (g.get("anims") or {}).items():
                        cur.execute("INSERT INTO symbol_group_anims(group_id, element, anims, updated_at, updated_by) "
                                    "VALUES (?,?,?,?,?)", (gid, el, json.dumps(anims, ensure_ascii=False), now, "restore"))
                for b in data["bindings"]:
                    cur.execute("INSERT INTO bindings(drawing_id, element, position, tag, anim, params) VALUES (?,?,?,?,?,?)",
                                (b["drawing_id"], b["element"], b["position"], b["tag"], b["anim"],
                                 json.dumps(b["params"])))
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise

    def _export_groups(self) -> list[dict[str, Any]]:
        anims: dict[int, dict[str, list[dict[str, Any]]]] = {}
        for a in self.list_group_anims():
            anims.setdefault(a["group_id"], {})[a["element"]] = a["anims"]
        return [{**{k: g[k] for k in ("drawing_id", "name", "kind", "members")}, "anims": anims.get(g["id"], {})}
                for g in self.list_symbol_groups()]

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
