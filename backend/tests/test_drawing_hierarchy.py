"""Tegningshierarki (ISA-101, v6.22.0): forælder sættes/ryddes i backend med regler (selv, cirkel, dybde), følger
backup/gendannelse, nulstilles ved sletning, og skjules for begrænsede brugere når forælderen er utilgængelig."""

import json
import threading

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.drawing_tree import (MAX_DEPTH, ancestors, check_parent, clean_parent, descendants, height,
                                       sanitize_parents)
from app.storage.db import SCHEMA_VERSION, Database

ADMIN_PW = "test-admin-pw-1"
SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect id="R" width="1" height="1"/></svg>'


@pytest.fixture
def api(tmp_path):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        assert c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW}).status_code == 200
        yield c


def mk(c, name):
    r = c.post("/api/drawings", json={"name": name, "svg": SVG})
    assert r.status_code == 201, r.text
    return r.json()["drawing"]["id"]


def parents(c):
    return {d["id"]: d["parent_id"] for d in c.get("/api/drawings").json()}


def put(c, did, parent):
    return c.put(f"/api/drawings/{did}/parent", json={"parent_id": parent})


def chain(c, n):
    """a1 (rod) <- a2 <- ... <- an"""
    ids = [mk(c, f"Niv {i}") for i in range(1, n + 1)]
    for i in range(1, n):
        assert put(c, ids[i], ids[i - 1]).status_code == 200
    return ids


# --------------------------------------------------------------------------- rene regler

def test_schema_version_and_column(tmp_path):
    assert SCHEMA_VERSION == 22
    db = Database(tmp_path / "x.db")
    assert "parent_id" in {r[1] for r in db._conn.execute("PRAGMA table_info(drawings)")}


def test_old_database_is_migrated(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE drawings (id TEXT PRIMARY KEY, name TEXT NOT NULL, active_version INTEGER NOT NULL, "
                "created_at REAL NOT NULL, updated_at REAL NOT NULL, disabled INTEGER NOT NULL DEFAULT 0)")
    con.execute("INSERT INTO drawings VALUES ('a','A',1,0,0,0)")
    con.commit()
    con.close()
    db = Database(path)
    assert db.get_drawing("a")["parent_id"] is None


def test_clean_parent():
    assert clean_parent(None) is None and clean_parent("") is None and clean_parent("   ") is None
    assert clean_parent(" a ") == "a"


def test_tree_helpers_survive_cycles():
    p = {"a": "b", "b": "c", "c": "a", "d": "ukendt"}
    assert set(ancestors(p, "a")) == {"b", "c"}                 # stopper i stedet for at hænge
    assert descendants(p, "a") == {"b", "c"}
    assert height(p, "a") >= 1
    assert ancestors(p, "d") == []                              # ukendt forælder afkorter


def test_check_parent_rules():
    p = {"a": None, "b": "a", "c": "b", "d": "c", "x": None}
    n = {k: k.upper() for k in p}
    assert check_parent(p, n, "x", None) is None
    assert "sin egen" in check_parent(p, n, "a", "a")
    assert "findes ikke" in check_parent(p, n, "a", "nej")
    assert "cirkel" in check_parent(p, n, "a", "c")
    assert "4 niveauer" in check_parent(p, n, "x", "d")         # d er niveau 4 → x ville blive 5
    assert check_parent(p, n, "x", "c") is None                 # niveau 4: ok


def test_sanitize_parents_clears_invalid():
    raw = {"a": None, "b": "a", "c": "ukendt", "d": "d", "e": "f", "f": "e", "g": "  ", "h": 5}
    out, dropped = sanitize_parents(raw, {k: k for k in raw})
    assert out["b"] == "a" and out["c"] is None and out["d"] is None and out["g"] is None and out["h"] is None
    assert (out["e"], out["f"]) in {("f", None), (None, "e")}   # én af cirklens kanter overlever, aldrig begge
    assert len(dropped) >= 3


# ---------------------------------------------------------------------------- API

def test_set_and_clear_parent(api):
    a, b = mk(api, "Anlaeg"), mk(api, "Omraade")
    assert parents(api) == {a: None, b: None}                   # liste leverer parent_id (null som standard)
    r = put(api, b, a)
    assert r.status_code == 200 and r.json()["parent_id"] == a
    assert parents(api)[b] == a
    assert api.get(f"/api/drawings/{b}").json()["parent_id"] == a
    assert put(api, b, None).json()["parent_id"] is None        # ryd
    put(api, b, a)
    assert put(api, b, "   ").json()["parent_id"] is None      # whitespace = ingen
    put(api, b, a)
    assert put(api, b, "").json()["parent_id"] is None          # tom streng = ingen


def test_rules_are_enforced_with_specific_danish_errors(api):
    a, b, c = mk(api, "A"), mk(api, "B"), mk(api, "C")
    put(api, b, a)
    put(api, c, b)
    r = put(api, a, a)
    assert r.status_code == 400 and "egen overordnede" in r.json()["error"]
    r = put(api, b, "findes-ikke")
    assert r.status_code == 400 and "findes ikke" in r.json()["error"]
    r = put(api, a, c)                                          # a under sin egen efterkommer
    assert r.status_code == 400 and "cirkel" in r.json()["error"]
    assert put(api, "findes-ikke", a).status_code == 404
    assert parents(api) == {a: None, b: a, c: b}                # intet ændret af de afviste kald


def test_depth_four_ok_five_rejected_also_for_subtree(api):
    ids = chain(api, 4)                                         # niveau 1-4: ok
    assert [parents(api)[i] for i in ids] == [None, ids[0], ids[1], ids[2]]
    extra = mk(api, "For dyb")
    r = put(api, extra, ids[3])
    assert r.status_code == 400 and "4 niveauer" in r.json()["error"]
    # undertræet tæller med: en rod med 2 niveauer under sig må ikke hænges under niveau 3
    top = mk(api, "Top2")
    mid = mk(api, "Mid2")
    put(api, mid, top)                                          # top2 <- mid2 (2 niveauer)
    r = put(api, top, ids[2])                                   # ville blive niveau 4 + 5
    assert r.status_code == 400 and "4 niveauer" in r.json()["error"]
    assert put(api, top, ids[1]).status_code == 200             # niveau 3 + 4: ok
    assert MAX_DEPTH == 4


def test_viewer_cannot_change_parent(api):
    a, b = mk(api, "A"), mk(api, "B")
    api.post("/api/users", json={"username": "kigger", "role": "viewer", "password": "Hemmelig-123"})
    api.post("/api/auth/login", json={"username": "kigger", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert put(api, b, a).status_code == 403
    assert parents(api)[b] is None


def test_parent_change_is_audited(api):
    a, b, c = mk(api, "A"), mk(api, "B"), mk(api, "C")
    put(api, c, a)
    put(api, c, b)
    put(api, c, None)
    rows = [e for e in api.get("/api/audit").json() if e["action"] == "drawing.parent"]
    changes = [(e["detail"]["old"], e["detail"]["new"]) for e in rows if e["target"] == c]
    assert len(changes) == 3 and set(changes) == {(None, a), (a, b), (b, None)}


def test_delete_clears_children_in_same_transaction(api):
    a, b, c = mk(api, "A"), mk(api, "B"), mk(api, "C")
    put(api, b, a)
    put(api, c, a)
    assert api.get(f"/api/drawings/{a}/usage").json()["children"] == ["B", "C"]
    assert api.delete(f"/api/drawings/{a}").status_code == 204
    assert parents(api) == {b: None, c: None}                   # børnene findes stadig, uden forælder


def test_disable_does_not_touch_hierarchy(api):
    a, b = mk(api, "A"), mk(api, "B")
    put(api, b, a)
    assert api.patch(f"/api/drawings/{a}", json={"disabled": True}).status_code == 200
    assert parents(api)[b] == a


def test_scoped_user_gets_null_for_hidden_parent(api):
    a, b, c = mk(api, "A"), mk(api, "B"), mk(api, "C")
    put(api, b, a)
    put(api, c, b)
    r = api.post("/api/users", json={"username": "op_b", "role": "operator", "password": "Hemmelig-123", "drawings": [b, c]})
    assert r.status_code == 201, r.text
    api.post("/api/auth/login", json={"username": "op_b", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    listed = {d["id"]: d["parent_id"] for d in api.get("/api/drawings").json()}
    assert listed == {b: None, c: b}                            # a er skjult → b får null; c's forælder b er tilladt
    assert api.get(f"/api/drawings/{b}").json()["parent_id"] is None
    assert "A" not in json.dumps(api.get("/api/drawings").json()).replace("Hemmelig", "")


# ---------------------------------------------------------------------- backup/gendannelse

def _backup(c):
    return c.get("/api/backup").json()


def _restore(c, backup):
    return c.post("/api/backup/restore", content=json.dumps(backup), headers={"content-type": "application/json"})


def test_backup_roundtrip_keeps_hierarchy(api):
    a, b, c = mk(api, "A"), mk(api, "B"), mk(api, "C")
    put(api, b, a)
    put(api, c, b)
    backup = _backup(api)
    assert {d["id"]: d["parent_id"] for d in backup["drawings"]} == {a: None, b: a, c: b}
    for d in api.get("/api/drawings").json():
        api.delete(f"/api/drawings/{d['id']}")
    r = _restore(api, backup)
    assert r.status_code == 200, r.text
    assert parents(api) == {a: None, b: a, c: b}


def test_restore_clears_invalid_parents_without_failing(api):
    ids = chain(api, 4)
    x = mk(api, "Fri")
    backup = _backup(api)
    for d in backup["drawings"]:
        if d["id"] == x:
            d["parent_id"] = "findes-ikke"                      # ukendt forælder
        if d["id"] == ids[0]:
            d["parent_id"] = ids[3]                             # cirkel
    r = _restore(api, backup)
    assert r.status_code == 200, r.text
    got = parents(api)
    assert got[x] is None
    assert got[ids[0]] is None or got[ids[3]] is None           # aldrig hele cirklen
    # selv, dybde 5 og forkert type
    backup = _backup(api)
    for d in backup["drawings"]:                                # en gyldig kæde på 4 niveauer: niv-4 <- niv-1 <- niv-2 <- niv-3
        d["parent_id"] = {ids[0]: ids[3], ids[1]: ids[0], ids[2]: ids[1]}.get(d["id"])
    extra = {**backup["drawings"][0], "id": "zekstra", "name": "Ekstra", "parent_id": ids[2]}   # niveau 5
    backup["drawings"].append(extra)
    backup["drawings"].append({**extra, "id": "zekstra2", "name": "Ekstra 2", "parent_id": 17})   # forkert type
    backup["drawings"][0]["parent_id"] = backup["drawings"][0]["id"]      # sig selv
    assert _restore(api, backup).status_code == 200
    got = parents(api)
    assert got["zekstra"] is None and got["zekstra2"] is None and got[x] is None
    assert got[ids[2]] == ids[1]                                          # den gyldige del bevares
    assert all(v is None or v in got for v in got.values())     # ingen peger på en tegning der ikke findes


def test_old_backup_without_parent_id_restores(api):
    a = mk(api, "A")
    backup = _backup(api)
    for d in backup["drawings"]:
        d.pop("parent_id", None)
    assert _restore(api, backup).status_code == 200
    assert parents(api) == {a: None}


# ------------------------------------------------------------------------ samtidighed

def test_concurrent_parent_changes_never_create_a_cycle(tmp_path):
    """Valideringen og skrivningen ligger i ÉN transaktion: A under B og B under A samtidigt må aldrig begge lykkes."""
    from app.services.drawings import DrawingService
    from app.services.errors import ServiceError
    from app.services.live_cache import LiveCache
    from app.storage.files import DrawingFiles

    for round_no in range(15):
        db = Database(tmp_path / f"c{round_no}.db")
        for n in ("a", "b", "c"):
            db.add_drawing_version(n, n.upper(), {"size": 1, "width": 1, "height": 1}, True)
        svc = DrawingService(db, DrawingFiles(tmp_path / f"f{round_no}"), LiveCache())
        results = []
        barrier = threading.Barrier(3)

        def go(child, parent):
            barrier.wait()
            try:
                svc.set_parent(child, parent)
                results.append(True)
            except ServiceError:
                results.append(False)

        ts = [threading.Thread(target=go, args=args) for args in (("a", "b"), ("b", "a"), ("c", "a"))]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        got = {d["id"]: d["parent_id"] for d in db.list_drawings()}
        assert not (got["a"] == "b" and got["b"] == "a"), got
        assert sum(1 for v in (got["a"], got["b"]) if v is not None) <= 1
        db.close()


# ------------------------------------------------- begrænset bruger: intet må afsløre skjulte tegninger (rettelse efter review)
# Teknikere/admin kan i dag aldrig begrænses (SCOPABLE_ROLES), så endpoints for teknikere afprøves som forsvar i dybden:
# omfanget (ScopeService.drawing_ids) tvinges til et sæt, mens den indloggede er admin.

def restrict(api, monkeypatch, allowed):
    monkeypatch.setattr(api.app.state.scope_service, "drawing_ids", lambda user: set(allowed))


def hidden_text(did):
    return f"Tegningen '{did}' findes ikke"


def goto(c, source, target):
    r = c.put(f"/api/drawings/{source}/bindings/R", json={"bindings": [{"anim": "click:goto", "params": {"drawing": target}}]})
    assert r.status_code == 200, r.text


def scoped_login(api, role, drawings=None):
    r = api.post("/api/users", json={"username": f"u_{role}", "role": role, "password": "Hemmelig-123", "drawings": drawings})
    assert r.status_code == 201, r.text
    api.post("/api/auth/login", json={"username": f"u_{role}", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})


def test_patch_response_hides_hidden_parent(api, monkeypatch):
    a, b, c = mk(api, "A"), mk(api, "B"), mk(api, "C")
    put(api, b, a)
    put(api, c, b)
    assert api.patch(f"/api/drawings/{b}", json={"name": "B2"}).json()["parent_id"] == a      # ubegrænset: uændret
    restrict(api, monkeypatch, {b, c})
    for body in ({"name": "B3"}, {"active_version": 1}, {"disabled": False}):
        r = api.patch(f"/api/drawings/{b}", json=body)
        assert r.status_code == 200 and r.json()["parent_id"] is None, body
    assert api.patch(f"/api/drawings/{c}", json={"name": "C2"}).json()["parent_id"] == b     # tilladt forælder vises


def test_restricted_cannot_patch_or_delete_hidden_drawing(api, monkeypatch):
    a, b = mk(api, "A"), mk(api, "B")
    restrict(api, monkeypatch, {b})
    r = api.patch(f"/api/drawings/{a}", json={"name": "Hacket"})
    assert r.status_code == 404 and r.json()["error"] == hidden_text(a)
    unknown = api.patch("/api/drawings/findes-ikke", json={"name": "x"})                      # ukendt: samme svar
    assert unknown.status_code == 404 and unknown.json()["error"] == hidden_text("findes-ikke")
    assert api.delete(f"/api/drawings/{a}").status_code == 404
    assert api.get(f"/api/drawings/{a}/usage").status_code == 404
    assert api.post(f"/api/drawings/{a}/versions", json={"svg": SVG}).status_code == 404
    monkeypatch.undo()
    assert [d["name"] for d in api.get("/api/drawings").json() if d["id"] == a] == ["A"]      # intet ændret/slettet
    assert api.delete(f"/api/drawings/{a}").status_code == 204                                # ubegrænset: som før


def test_add_version_response_hides_hidden_parent(api, monkeypatch):
    a, b = mk(api, "A"), mk(api, "B")
    put(api, b, a)
    restrict(api, monkeypatch, {b})
    r = api.post(f"/api/drawings/{b}/versions", json={"svg": SVG})
    assert r.status_code == 201 and r.json()["drawing"]["parent_id"] is None


def test_usage_filters_hidden_drawings_and_users(api, monkeypatch):
    a, b, c, d = mk(api, "A"), mk(api, "B"), mk(api, "C"), mk(api, "D")
    put(api, b, a)          # b: synlig, c og d: skjulte — alle børn af a
    put(api, c, a)
    put(api, d, a)
    goto(api, b, a)
    goto(api, c, a)
    r = api.post("/api/users", json={"username": "begr", "role": "viewer", "password": "Hemmelig-123", "drawings": [a, b]})
    assert r.status_code == 201, r.text
    full = api.get(f"/api/drawings/{a}/usage").json()                                         # ubegrænset: alt som før
    assert full["children"] == ["B", "C", "D"] and full["goto_from"] == ["B", "C"] and full["users"] == ["begr"]
    restrict(api, monkeypatch, {a, b})
    u = api.get(f"/api/drawings/{a}/usage").json()
    assert u["children"] == ["B"] and u["goto_from"] == ["B"] and u["users"] == []
    assert u["bindings"] == full["bindings"] and u["versions"] == full["versions"]


def test_put_parent_hidden_cases_look_like_unknown(api, monkeypatch):
    a, b, c = mk(api, "A"), mk(api, "B"), mk(api, "C")
    restrict(api, monkeypatch, {b, c})
    hid = put(api, b, a)                                         # skjult forælder
    assert hid.status_code == 404 and hid.json()["error"] == hidden_text(a)
    unk = put(api, b, "findes-ikke")                             # ukendt forælder: SAMME slags svar
    assert unk.status_code == 404 and unk.json()["error"] == hidden_text("findes-ikke")
    assert put(api, a, b).status_code == 404                     # skjult barn
    assert put(api, a, None).json()["error"] == hidden_text(a)
    assert put(api, b, c).status_code == 200                     # tilladt -> tilladt
    monkeypatch.undo()
    assert parents(api)[a] is None and parents(api)[b] == c


def test_depth_error_is_neutral_for_restricted_user(api, monkeypatch):
    ids = chain(api, 3)
    x, y = mk(api, "X"), mk(api, "Y")
    put(api, y, x)                                               # x har et undertræ på 2 niveauer
    full = put(api, x, ids[2])
    assert full.status_code == 400 and "ville give 5" in full.json()["error"]
    restrict(api, monkeypatch, {x, ids[2]})
    r = put(api, x, ids[2])
    assert r.status_code == 400 and "4 niveauer" in r.json()["error"]
    assert "ville give" not in r.json()["error"] and "5" not in r.json()["error"]


def test_put_same_parent_is_a_noop(api):
    a, b = mk(api, "A"), mk(api, "B")
    put(api, b, a)

    def stamp(did):
        return [d for d in api.get("/api/drawings").json() if d["id"] == did][0]["updated_at"]

    before_a, before_b = stamp(a), stamp(b)
    n_audit = len([e for e in api.get("/api/audit").json() if e["action"] == "drawing.parent"])
    assert put(api, b, a).status_code == 200
    assert put(api, a, None).status_code == 200                  # ingen -> ingen
    assert stamp(a) == before_a and stamp(b) == before_b
    assert len([e for e in api.get("/api/audit").json() if e["action"] == "drawing.parent"]) == n_audit


@pytest.mark.parametrize("role", ["viewer", "operator"])
def test_put_parent_rejected_for_low_roles(api, role):
    a, b = mk(api, "A"), mk(api, "B")
    scoped_login(api, role)
    assert put(api, b, a).status_code == 403
    assert api.get(f"/api/drawings/{b}/usage").status_code == 403
    assert api.patch(f"/api/drawings/{b}", json={"name": "x"}).status_code == 403
    assert api.delete(f"/api/drawings/{b}").status_code == 403
    assert parents(api)[b] is None


def test_scoped_operator_never_sees_hidden_parent(api):
    a, b = mk(api, "A"), mk(api, "B")
    put(api, b, a)
    scoped_login(api, "operator", [b])
    assert put(api, b, None).status_code == 403                  # rollen afviser; forælderen røbes aldrig
    assert api.get(f"/api/drawings/{b}").json()["parent_id"] is None
    assert [d["id"] for d in api.get("/api/drawings").json()] == [b]


# ------------------------------------------------------------------ transaktion og log

def test_set_drawing_parent_rolls_back_on_any_error(tmp_path):
    db = Database(tmp_path / "t.db")
    for n in ("a", "b"):
        db.add_drawing_version(n, n.upper(), {"size": 1, "width": 1, "height": 1}, True)

    def boom(parents, names):
        raise RuntimeError("fejl midt i transaktionen")

    with pytest.raises(RuntimeError):
        db.set_drawing_parent("b", "a", boom)
    assert not db._conn.in_transaction
    with pytest.raises(KeyError):
        db.set_drawing_parent("findes-ikke", "a", lambda p, n: None)
    assert not db._conn.in_transaction
    assert db.set_drawing_parent("b", "a", lambda p, n: None) == (None, None)      # næste BEGIN IMMEDIATE virker
    assert db.get_drawing("b")["parent_id"] == "a"
    assert db.set_drawing_parent("b", "a", lambda p, n: pytest.fail("ingen kontrol ved uændret forælder")) == ("a", None)
    db.close()


def test_restore_log_lines_escape_backup_values():
    out, dropped = sanitize_parents({"a": "x\nFALSK LOGLINJE " + "y" * 500}, {"a": "A"})
    assert out["a"] is None and len(dropped) == 1
    assert "\n" not in dropped[0] and len(dropped[0]) < 400
