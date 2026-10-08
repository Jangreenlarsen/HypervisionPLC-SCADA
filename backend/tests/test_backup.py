"""Backup/restore: rundtur, validering uden ændringer, roller, tilbagerulning."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"
SVG1 = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect id="Tank" width="5" height="5"/>'
        '<text id="Niveau">-</text></svg>')
SVG2 = SVG1.replace('id="Tank"', 'id="Tank2"')


def _settings(tmp_path, **kw):
    return Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                    frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0, **kw)


def _wait(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


def _login(c):
    assert c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW}).status_code == 200


@pytest.fixture
def api(tmp_path, mock_plc):
    with TestClient(create_app(_settings(tmp_path / "a"))) as c:
        _login(c)
        c.post("/api/plcs", json={"key": "plc1", "name": "Anlæg", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        c.post("/api/tags", json={"name": "Niveau", "source": "plc1:hr:10", "scale": 0.1, "unit": "%", "min": 0, "max": 100})
        c.post("/api/tags", json={"name": "Motor", "source": "plc1:coil:3", "writable": True})
        main = c.post("/api/drawings", json={"name": "Hoved", "svg": SVG1}).json()["drawing"]["id"]
        c.post(f"/api/drawings/{main}/versions", json={"svg": SVG2, "comment": "v2", "activate": False})
        detail = c.post("/api/drawings", json={"name": "Detalje", "svg": SVG1}).json()["drawing"]["id"]
        c.put(f"/api/drawings/{main}/bindings/Tank", json={"bindings": [
            {"tag": "Niveau", "anim": "level"}, {"anim": "click:goto", "params": {"drawing": detail}}]})
        c.put(f"/api/drawings/{main}/bindings/Niveau", json={"bindings": [{"tag": "Motor", "anim": "click:toggle"}]})
        c.put("/api/drawings/start", json={"drawing": detail})
        yield c


def _state(c):
    drawings = {d["id"]: c.get(f"/api/drawings/{d['id']}").json() for d in c.get("/api/drawings").json()}
    return {
        "plcs": [{k: p[k] for k in ("key", "name", "base_url", "username")} for p in c.get("/api/plcs").json()],
        "tags": c.get("/api/tags").json(),
        "drawings": {i: (d["name"], d["active_version"], [v["version"] for v in d["versions"]]) for i, d in drawings.items()},
        "bindings": {i: c.get(f"/api/drawings/{i}/bindings").json() for i in drawings},
        "svg": {i: c.get(f"/api/drawings/{i}/svg?version=1").text for i in drawings},
        "start": [d["id"] for d in c.get("/api/drawings").json() if d["start"]],
    }


def test_roundtrip_restores_everything_and_keeps_passwords(api):
    before = _state(api)
    r = api.get("/api/backup")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    backup = r.json()
    assert backup["format"] == "hypervisionplc-scada-backup" and "scada123" not in r.text
    assert "password" not in json.dumps(backup["plcs"]) and "users" not in backup

    # Ødelæg tilstanden
    for d in api.get("/api/drawings").json():
        api.delete(f"/api/drawings/{d['id']}")
    api.delete("/api/tags/Niveau")
    api.post("/api/tags", json={"name": "Ny", "source": "plc1:hr:1"})

    r = api.post("/api/backup/restore", content=json.dumps(backup), headers={"content-type": "application/json"})
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["tags"] == 2 and result["drawings"] == 2 and result["versions"] == 3 and result["bindings"] == 3
    assert result["missing_passwords"] == []  # plc1 fandtes → adgangskoden bevares
    assert _state(api) == before
    _wait(lambda: api.get("/api/live?tags=Niveau").json()["values"]["Niveau"]["quality"] == "good")
    assert result["pre_restore_backup"] in [f["name"] for f in api.get("/api/backup/files").json()]


def test_restore_on_fresh_install(api, tmp_path):
    backup = api.get("/api/backup").json()
    with TestClient(create_app(_settings(tmp_path / "b"))) as fresh:
        _login(fresh)
        r = fresh.post("/api/backup/restore", json=backup)
        assert r.status_code == 200, r.text
        assert r.json()["missing_passwords"] == ["plc1"]
        status = fresh.get("/api/plcs/plc1").json()
        assert status["has_password"] is False and "adgangskode" in status["status"]["message"].lower()
        assert len(fresh.get("/api/tags").json()) == 2
        assert [u["username"] for u in fresh.get("/api/users").json()] == ["admin"]  # brugere røres ikke


def test_invalid_backup_changes_nothing(api):
    before = _state(api)
    backup = api.get("/api/backup").json()
    bad = json.loads(json.dumps(backup))
    bad["tags"].append({"name": "Fremmed", "source": "plc9:hr:1"})
    bad["tags"].append({"name": "Input", "source": "plc1:ir:1", "writable": True})
    bad["drawings"][0]["versions"][0]["svg"] = "<html/>"
    bad["bindings"].append({"drawing_id": bad["drawings"][1]["id"], "element": "Tank", "position": 5,
                            "tag": "Findes_ikke", "anim": "text", "params": {}})
    r = api.post("/api/backup/restore", json=bad)
    assert r.status_code == 400
    msg = r.json()["error"]
    assert "intet er ændret" in msg and "plc9" in msg and "kun hr/coil" in msg
    assert "ikke en SVG" in msg and "Findes_ikke" in msg
    assert _state(api) == before
    assert api.get("/api/backup/files").json() == []  # validering sker FØR automatisk backup


def test_svg_in_backup_is_sanitized_again(api):
    backup = api.get("/api/backup").json()
    backup["drawings"][0]["versions"][0]["svg"] = SVG1.replace("</svg>", "<script>alert(1)</script></svg>")
    assert api.post("/api/backup/restore", json=backup).status_code == 200
    did = backup["drawings"][0]["id"]
    assert "script" not in api.get(f"/api/drawings/{did}/svg?version=1").text


@pytest.mark.parametrize("payload, message", [
    (b"ikke json", "gyldig JSON"),
    (b'{"format": "noget-andet"}', "ikke en HypervisionPLC SCADA-backup"),
    (b'{"format": "hypervisionplc-scada-backup", "format_version": 99}', "formatversion"),
])
def test_not_a_backup(api, payload, message):
    r = api.post("/api/backup/restore", content=payload, headers={"content-type": "application/json"})
    assert r.status_code == 400 and message in r.json()["error"]


def test_admin_only_and_audit(api):
    api.post("/api/users", json={"username": "tekniker", "role": "engineer", "password": "Hemmelig-123"})
    api.post("/api/auth/login", json={"username": "tekniker", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert api.get("/api/backup").status_code == 403
    assert api.post("/api/backup/restore", json={}).status_code == 403
    _login(api)
    api.get("/api/backup")
    assert any(e["action"] == "backup.download" for e in api.get("/api/audit").json())


def test_server_backup_files_and_pruning(api):
    svc = api.app.state.backup_service
    svc.keep = 2
    names = []
    for _ in range(3):
        names.append(svc.save_to_server("auto", "test"))
        time.sleep(1.05)  # filnavne har sekund-opløsning
    listed = [f["name"] for f in api.get("/api/backup/files").json()]
    assert listed == list(reversed(names[1:]))  # ældste er ryddet op
    r = api.get(f"/api/backup/files/{names[-1]}")
    assert r.status_code == 200 and r.json()["format"] == "hypervisionplc-scada-backup"
    for bad in ("..%2Fscada.db", "scada.db", "scada-auto-1.json"):
        assert api.get(f"/api/backup/files/{bad}").status_code in (400, 404)


def test_database_failure_rolls_back_files(api, monkeypatch):
    backup = api.get("/api/backup").json()
    did = backup["drawings"][0]["id"]
    before_svg = api.get(f"/api/drawings/{did}/svg?version=1").text
    backup["drawings"][0]["versions"][0]["svg"] = SVG1.replace("Tank", "Anden")

    def boom(_data):
        raise RuntimeError("disk fuld")

    monkeypatch.setattr(api.app.state.backup_service.db, "replace_project", boom)
    r = api.post("/api/backup/restore", json=backup)
    assert r.status_code == 500 and "tidligere tilstand er bevaret" in r.json()["error"]
    assert api.get(f"/api/drawings/{did}/svg?version=1").text == before_svg
