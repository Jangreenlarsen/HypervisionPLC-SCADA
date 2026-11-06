"""Fjern en PLC (v3.34.0): flyt tagsene til en anden PLC, eller fjern PLC'en med alle tags og henvisninger."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect id="Lampe" width="10" height="10"/>'
       '<rect id="Kasse" width="10" height="10"/><g id="P1" data-hv-type="pumpe" data-hv-name="Pumpe 1">'
       '<circle id="P1_hjul" cx="5" cy="5" r="3"/></g><path id="Roer" d="M0 0H50"/></svg>')
TAGS = [
    {"name": "Drift", "source": "plc1:di:1"},
    {"name": "Start", "source": "plc1:coil:1", "writable": True},
    {"name": "Temp", "source": "plc1:ir:3", "trend": True},
    {"name": "Andet", "source": "plc2:hr:9"},
]


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0,
                        start_runtimes=False)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        for key in ("plc1", "plc2"):
            assert c.post("/api/plcs", json={"key": key, "base_url": mock_plc.url, "username": "scada", "password": "scada123",
                                             "sse_enabled": False}).status_code == 201
        for t in TAGS:
            assert c.post("/api/tags", json=t).status_code == 201, t
        c.did = c.post("/api/drawings", json={"name": "Anlæg", "svg": SVG}).json()["drawing"]["id"]
        assert c.put(f"/api/drawings/{c.did}/bindings/Lampe", json={"bindings": [
            {"tag": "Drift", "anim": "fill", "params": {"on": "#0f0", "off": "#999"}}]}).status_code == 200
        assert c.put(f"/api/drawings/{c.did}/bindings/Kasse", json={"bindings": [
            {"tag": "Andet", "anim": "fill", "params": {"on": "#0f0", "off": "#999"}}]}).status_code == 200
        cfg = {"op": "view", "anims": [{"part": "P1_hjul", "type": "spin", "src": "Drift", "params": {}},
                                       {"part": "all", "type": "fill", "src": "@alarm:active:Temp", "params": {}},
                                       {"part": "all", "type": "blink", "src": "Andet", "params": {}}],
               "chart": None}
        assert c.put(f"/api/drawings/{c.did}/symbols/P1/config", json={"config": cfg}).status_code == 200
        db = c.app.state.manager.db
        db.insert_schedule({"name": "Nat", "tag": "Start", "enabled": True, "default_value": 0, "entries": [], "exceptions": []})
        db.set_trend_view("Tank", {"name": "Tank", "tags": ["Temp", "Andet"], "assign": {"Temp": 1, "Andet": 2}, "range": "1h"})
        db.set_trend_view("Kun temp", {"name": "Kun temp", "tags": ["Temp"], "assign": {}, "range": "1h"})
        db._execute("INSERT INTO api_keys(id, name, key_hash, prefix, scope, created_at, created_by) VALUES (?,?,?,?,?,?,?)",
                    ("k_1", "Måler", "h" * 64, "hv_abc", json.dumps({"all": False, "tags": ["Temp", "Andet"], "prefixes": []}),
                     time.time(), "admin"))
        c.db = db
        yield c


def test_plain_delete_still_blocked_and_usage_shows_impact(api):
    assert api.delete("/api/plcs/plc1").status_code == 409
    u = api.get("/api/plcs/plc1/usage").json()
    assert u["tags"] == 3 and set(u["tag_names"]) == {"Drift", "Start", "Temp"}
    assert u["drawings"] == [{"id": api.did, "name": "Anlæg", "bindings": 1, "symbols": 1}]
    assert u["schedules"] == ["Nat"] and sorted(u["trend_views"]) == ["Kun temp", "Tank"] and u["api_keys"] == ["Måler"]
    assert u["history"] == 1 and [t["key"] for t in u["targets"]] == ["plc2"]


def test_move_keeps_everything(api):
    r = api.post("/api/plcs/plc1/remove", json={"mode": "move", "target": "plc2"})
    assert r.status_code == 200, r.text
    assert r.json() == {"mode": "move", "target": "plc2", "tags": 3, "warnings": []}
    assert api.get("/api/plcs/plc1").status_code == 404
    tags = {t["name"]: t for t in api.get("/api/tags").json()}
    assert tags["Drift"]["source"] == "plc2:di:1" and tags["Start"]["source"] == "plc2:coil:1" and tags["Start"]["writable"]
    assert {b["tag"] for b in api.get(f"/api/drawings/{api.did}/bindings").json()} == {"Drift", "Andet"}
    assert len(api.db.get_symbol_config(api.did, "P1")["config"]["anims"]) == 3
    assert [s["name"] for s in api.db.list_schedules()] == ["Nat"]
    assert any(a["action"] == "plc.remove" for a in api.get("/api/audit").json())


def test_move_validation_changes_nothing(api):
    assert api.post("/api/plcs/plc1/remove", json={"mode": "move", "target": "plc1"}).status_code == 400
    assert api.post("/api/plcs/plc1/remove", json={"mode": "move", "target": "findes_ikke"}).status_code == 404
    assert api.post("/api/plcs/plc1/remove", json={"mode": "move"}).status_code == 400
    assert api.get("/api/plcs/plc1").status_code == 200
    assert {t["source"] for t in api.get("/api/tags").json() if t["name"] != "Andet"} == {"plc1:di:1", "plc1:coil:1", "plc1:ir:3"}


def test_remove_all_cleans_every_reference(api, tmp_path):
    assert api.post("/api/plcs/plc1/remove", json={"mode": "all", "confirm": "forkert"}).status_code == 400
    r = api.post("/api/plcs/plc1/remove", json={"mode": "all", "confirm": "plc1"})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["tags"] == 3 and res["bindings"] == 1 and res["symbols"] == 1 and res["schedules"] == 1
    assert res["views"] == 2 and res["api_keys"] == 1 and res["backup"].startswith("scada-foer-plc-fjern-")
    assert (tmp_path / "backups" / res["backup"]).exists()
    assert api.get("/api/plcs/plc1").status_code == 404
    assert [t["name"] for t in api.get("/api/tags").json()] == ["Andet"]
    assert [b["tag"] for b in api.get(f"/api/drawings/{api.did}/bindings").json()] == ["Andet"]
    anims = api.db.get_symbol_config(api.did, "P1")["config"]["anims"]
    assert [a["src"] for a in anims] == ["Andet"]                               # Drift og alarm på Temp fjernet
    assert api.db.list_schedules() == []
    views = {v["name"]: v for v in api.db.list_trend_views()}
    assert set(views) == {"Tank"} and views["Tank"]["tags"] == ["Andet"] and views["Tank"]["assign"] == {"Andet": 2}
    assert json.loads(api.db.get_api_key("k_1")["scope"])["tags"] == ["Andet"]
    assert api.delete("/api/plcs/plc2").status_code == 409                      # plc2 har stadig sit tag


def test_plc_without_tags_and_roles(api):
    api.post("/api/plcs", json={"key": "tom", "base_url": "http://127.0.0.1:9", "username": "a", "password": "b",
                               "sse_enabled": False})
    assert api.get("/api/plcs/tom/usage").json()["tags"] == 0
    r = api.post("/api/plcs/tom/remove", json={"mode": "all", "confirm": "tom"})
    assert r.status_code == 200 and r.json()["tags"] == 0
    api.post("/api/users", json={"username": "tek", "password": "tek-pw-123456", "role": "engineer"})
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "tek", "password": "tek-pw-123456"})
    assert api.get("/api/plcs/plc1/usage").status_code == 403
    assert api.post("/api/plcs/plc1/remove", json={"mode": "all", "confirm": "plc1"}).status_code == 403


def test_review_fixes_backup_alarms_dir_tag_and_conflict(api):
    """Review af v3.34.0: backuppen kan hentes, alarmer genopstår ikke, løbelysets retnings-tag tømmes, 409 ved nye tags."""
    assert api.put(f"/api/drawings/{api.did}/bindings/Roer", json={"bindings": [
        {"tag": "Andet", "anim": "flow", "params": {"dir_tag": "Drift"}}]}).status_code == 200
    alarms = api.app.state.alarm_service
    row = {"key": "Temp:hi", "tag": "Temp", "plc": "plc1", "kind": "hi", "level": "high", "priority": "high",
           "state": "active_unack", "raised_at": time.time(), "value": 99, "message": "Høj temperatur"}
    comm = {**row, "key": "comm:plc1", "tag": "", "kind": "comm"}
    for r in (row, comm):
        alarms.state[r["key"]] = dict(r)
        api.db.upsert_alarm_state(dict(r))
    # nye tags imens → transaktionen afvises
    assert api.db.remove_plc_cascade("plc1", ["Drift"], [], [], [], {}, {}, "admin") is None
    r = api.post("/api/plcs/plc1/remove", json={"mode": "all", "confirm": "plc1"}).json()
    got = api.get(f"/api/backup/files/{r['backup']}")
    assert got.status_code == 200, got.text
    assert r["history_backup"] is None or r["history_backup"].startswith("trends-foer-plc-fjern-")
    assert "Temp:hi" not in alarms.state and "comm:plc1" not in alarms.state
    alarms.evaluate()
    assert not [a for a in api.db.list_alarm_states() if a["key"] in ("Temp:hi", "comm:plc1")]
    roer = [b for b in api.get(f"/api/drawings/{api.did}/bindings").json() if b["element"] == "Roer"][0]
    assert roer["params"]["dir_tag"] == ""
    kinds = {f["name"]: f["kind"] for f in api.get("/api/backup/files").json()}
    assert kinds[r["backup"]] == "før PLC fjernet"


def test_move_warns_about_disabled_target_and_audits_failures(api):
    api.patch("/api/plcs/plc2", json={"enabled": False})
    r = api.post("/api/plcs/plc1/remove", json={"mode": "move", "target": "plc2"}).json()
    assert any("slået fra" in w for w in r["warnings"])
    assert api.post("/api/plcs/plc2/remove", json={"mode": "all", "confirm": "nej"}).status_code == 400
    fails = [a for a in api.get("/api/audit").json() if a["action"] == "plc.remove" and "error" in a["detail"]]
    assert fails and "bekræfte" in fails[0]["detail"]["error"]


def test_remove_tags_in_use_cleans_references(api, tmp_path):
    """v3.35.0: et tag i brug kan slettes direkte — tagget og alle henvisninger forsvinder i én transaktion (backup først)."""
    u = api.post("/api/tags/usage", json={"names": ["Drift", "Temp"]}).json()
    assert u["in_use"] and u["tags"] == 2 and u["history"] == 1
    assert u["drawings"] == [{"id": api.did, "name": "Anlæg", "bindings": 1, "symbols": 1}]
    assert sorted(u["trend_views"]) == ["Kun temp", "Tank"] and u["api_keys"] == ["Måler"] and u["schedules"] == []
    assert api.post("/api/tags/usage", json={"names": ["Drift", "findes_ikke"]}).status_code == 404
    assert api.post("/api/tags/remove", json={"names": ["Drift", "findes_ikke"]}).status_code == 404
    assert {t["name"] for t in api.get("/api/tags").json()} == {"Drift", "Start", "Temp", "Andet"}   # intet slettet
    r = api.post("/api/tags/remove", json={"names": ["Drift", "Temp"]})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["tags"] == 2 and res["bindings"] == 1 and res["symbols"] == 1 and res["views"] == 2 and res["api_keys"] == 1
    assert res["backup"].startswith("scada-foer-tag-slet-") and (tmp_path / "backups" / res["backup"]).exists()
    assert {t["name"] for t in api.get("/api/tags").json()} == {"Start", "Andet"}
    assert api.get("/api/plcs/plc1").status_code == 200                                   # PLC'en bliver
    assert [b["tag"] for b in api.get(f"/api/drawings/{api.did}/bindings").json()] == ["Andet"]
    assert [a["src"] for a in api.db.get_symbol_config(api.did, "P1")["config"]["anims"]] == ["Andet"]
    views = {v["name"]: v for v in api.db.list_trend_views()}
    assert set(views) == {"Tank"} and views["Tank"]["tags"] == ["Andet"]
    assert json.loads(api.db.get_api_key("k_1")["scope"])["tags"] == ["Andet"]
    assert [s["name"] for s in api.db.list_schedules()] == ["Nat"]                         # bruger Start, ikke slettet
    kinds = {f["name"]: f["kind"] for f in api.get("/api/backup/files").json()}
    assert kinds[res["backup"]] == "før tags slettet"
    assert any(a["action"] == "tag.remove" for a in api.get("/api/audit").json())


def test_remove_unused_tag_without_backup_and_schedule_tag(api):
    api.post("/api/tags", json={"name": "Loes", "source": "plc2:hr:3"})
    r = api.post("/api/tags/remove", json={"names": ["Loes"]}).json()
    assert r["tags"] == 1 and r["backup"] is None
    assert api.post("/api/tags/usage", json={"names": ["Start"]}).json()["schedules"] == ["Nat"]
    r = api.post("/api/tags/remove", json={"names": ["Start"]}).json()
    assert r["schedules"] == 1 and api.db.list_schedules() == []
    assert api.post("/api/tags/remove", json={"names": []}).status_code == 422


def test_remove_tags_roles_api_keys_and_backup_failure(api, monkeypatch):
    """Review v3.35.0: kun admin må indsnævre API-nøgler; backup-fejl → intet slettet; operatør har ingen adgang."""
    def boom(*a, **k):
        raise OSError("disken er fuld")
    monkeypatch.setattr(api.app.state.backup_service, "save_to_server", boom)
    r = api.post("/api/tags/remove", json={"names": ["Drift"]})
    assert r.status_code == 500 and "intet er slettet" in r.json()["error"]
    assert any(t["name"] == "Drift" for t in api.get("/api/tags").json())
    monkeypatch.undo()
    for user, role in (("tek", "engineer"), ("op", "operator")):
        api.post("/api/users", json={"username": user, "password": f"{user}-pw-123456", "role": role})
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "op", "password": "op-pw-123456"})
    assert api.post("/api/tags/usage", json={"names": ["Drift"]}).status_code == 403
    assert api.post("/api/tags/remove", json={"names": ["Drift"]}).status_code == 403
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "tek", "password": "tek-pw-123456"})
    api.post("/api/auth/password", json={"old_password": "tek-pw-123456", "new_password": "tek-pw-123456-ny"})
    r = api.post("/api/tags/remove", json={"names": ["Temp"]})                  # bruges af API-nøglen "Måler"
    assert r.status_code == 403 and "Måler" in r.json()["error"]
    assert api.post("/api/tags/remove", json={"names": ["Drift"]}).status_code == 200   # ingen API-nøgle → tekniker må
