"""Signalvejene er fjernet (v6.0.0-b0395): gemte veje og deres symbol-opsætning (`sv~<id>`) slettes ved opstart (backup først),
symboler der brugte en vej eller et virtuelt signal røres ikke (de står i rapporten), og en ældre backup med veje kan gendannes."""

import json
import time

from app.services.migrations import remove_paths
from tests.drawing_api import api, cfg  # noqa: F401 — fixture

DATA = {"start": "kedel", "end": "rad", "ends": [], "elements": [{"element": "r1", "flows": [{"part": "all", "reverse": False}]}]}


def _old(api):
    """En vej og dens opsætning som symbol, som de lå før v6.0.0-b0395 (direkte i tabellerne)."""
    db = api.app.state.symbol_service.db
    with db._lock:
        db._conn.execute("INSERT INTO signal_paths(id, drawing_id, name, data, updated_at, updated_by) VALUES (7,?,?,?,?,?)",
                         (api.d, "Kedel → radiator", json.dumps(DATA), time.time(), "test"))
        db._conn.execute("INSERT INTO symbol_config(drawing_id, element, config, updated_at, updated_by) VALUES (?,?,?,?,?)",
                         (api.d, "sv~7", json.dumps({"op": "view", "anims": [{"part": "r1", "type": "flow", "src": "Ekstra", "params": {}}]}),
                          time.time(), "test"))
        db._conn.execute("INSERT INTO symbol_config(drawing_id, element, config, updated_at, updated_by) VALUES (?,?,?,?,?)",
                         (api.d, "rad", json.dumps({"op": "view", "anims": [{"part": "all", "type": "blink", "src": f"sym:{api.d}:sv~7:pos",
                                                                             "params": {}, "auto": True}]}), time.time(), "test"))
    db.set_meta(remove_paths.DONE_KEY, None)
    return db


class Backups:
    def __init__(self, fail=False):
        self.saved, self.fail = [], fail

    def save_to_server(self, kind, by):
        if self.fail:
            raise OSError("disk fuld")
        self.saved.append(kind)


def test_startup_removes_the_paths_and_their_setup_once_with_a_backup_first(api):
    db = _old(api)
    b = Backups()
    rep = remove_paths.migrate(db, b)
    assert b.saved == ["foer-signalvej-fjern"] and rep["paths"] == 1 and rep["setups"] == 1
    assert rep["readers"] == [{"drawing": api.d, "element": "rad"}]                  # røres ikke, men står i rapporten
    assert db.count_signal_paths() == 0 and db.get_symbol_config(api.d, "sv~7") is None
    assert db.get_symbol_config(api.d, "rad") is not None
    assert remove_paths.migrate(db, b) is None and b.saved == ["foer-signalvej-fjern"]   # én gang


def test_nothing_changes_when_the_backup_fails(api):
    db = _old(api)
    assert remove_paths.migrate(db, Backups(fail=True)) is None
    assert db.count_signal_paths() == 2 and not db.get_meta(remove_paths.DONE_KEY)


def test_the_api_has_no_signal_paths_and_no_derived_signals(api):
    assert api.get(f"/api/drawings/{api.d}/signal-paths").status_code == 404
    assert api.get(f"/api/drawings/{api.d}/signals").status_code == 404


def test_a_feedback_from_another_symbols_position_or_a_virtual_signal_is_no_longer_accepted(api):
    sel = {"op": "positions", "display": "local", "positions": [{"label": "Fra"}, {"label": "Til"}],
           "signals": [{"id": "S1", "tag": "", "virtual": True}], "planes": [{"signal": "S1", "values": [0, 1]}],
           "anims": [{"part": "all", "type": "blink", "src": "@pos", "params": {"set": [False, True]}}]}
    r = api.put(f"/api/drawings/{api.d}/symbols/rad/config", json={"config": sel})
    assert r.status_code == 400 and "kommando-tag" in r.text                         # "virtual" ignoreres
    passive = {**sel, "passive": True, "display": "remote", "signals": [{"id": "S1", "tag": "", "fb": f"sym:{api.d}:p1:pos"}]}
    r = api.put(f"/api/drawings/{api.d}/symbols/rad/config", json={"config": passive})
    assert r.status_code == 400 and "findes ikke" in r.text


def test_an_older_backup_with_paths_can_be_restored_without_them(api):
    db = _old(api)
    bk = api.get("/api/backup").json()
    assert "signal_paths" not in bk                                   # (veje eksporteres ikke mere)
    with db._lock:
        row = db._conn.execute("SELECT data FROM signal_paths").fetchone()
    bk["signal_paths"] = [{"id": 7, "drawing_id": api.d, "name": "Kedel → radiator", "data": json.loads(row[0])}]
    bk["symbol_config"].append({"drawing_id": api.d, "element": "sv~7", "config": {"op": "view", "anims": []}})
    r = api.post("/api/backup/restore", json=bk)
    assert r.status_code == 200, r.text
    assert db.count_signal_paths() == 0 and cfg(api, "rad")["anims"][0]["auto"] is False


def test_every_server_backup_kind_can_be_fetched_again(api):
    """Den automatiske backup før oprydningen (og alle andre slags) skal kunne hentes og gendannes — ikke kun gemmes."""
    from app.services.backup import _KIND_TEXT
    svc = api.app.state.backup_service
    for kind in _KIND_TEXT:
        name = svc.save_to_server(kind, "test")
        assert svc.server_backup_path(name).exists(), kind
        time.sleep(0.01)
