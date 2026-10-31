"""Tilslutningspunkter pr. bibliotekssymbol (symbol-editoren, v2.16.0)."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.errors import ServiceError
from app.services.symbol_ports import clean_ports, clean_type

ADMIN_PW = "test-admin-pw-1"


@pytest.fixture
def api(tmp_path):
    settings = Settings(data_dir=tmp_path, frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0, start_runtimes=False)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        yield c


def test_set_list_overwrite_reset(api):
    assert api.get("/api/symbol-ports").json() == {}
    r = api.put("/api/symbol-ports/ventil", json={"ports": [[0, 0.5], [1, 0.5], [1, 0.5]]})
    assert r.status_code == 200 and r.json()["ports"] == [[0, 0.5], [1, 0.5]]   # dublet fjernet
    api.put("/api/symbol-ports/pumpe", json={"ports": [[0.123456, 0]]})
    assert api.get("/api/symbol-ports").json() == {"pumpe": [[0.1235, 0]], "ventil": [[0, 0.5], [1, 0.5]]}
    api.put("/api/symbol-ports/ventil", json={"ports": [[0.5, 1]]})
    assert api.get("/api/symbol-ports").json()["ventil"] == [[0.5, 1]]
    assert api.delete("/api/symbol-ports/ventil").status_code == 204
    assert "ventil" not in api.get("/api/symbol-ports").json()
    assert api.delete("/api/symbol-ports/ventil").status_code == 204   # nulstil igen: ingen fejl
    actions = [e["action"] for e in api.get("/api/audit").json() if e["action"].startswith("symbol_ports")]
    assert actions.count("symbol_ports.set") == 3 and actions.count("symbol_ports.reset") == 1


def test_validation():
    assert clean_ports([[0, 0], [1, 1]]) == [[0.0, 0.0], [1.0, 1.0]]
    for bad in ([], [[0.5]], [[0, 1.5]], [[-0.1, 0]], [["a", 0]], [[True, 0]], "x", [[0, 0]] * 0, [[i / 40, 0] for i in range(33)]):
        with pytest.raises(ServiceError):
            clean_ports(bad)
    assert clean_type("boejning90") == "boejning90"
    for bad in ("", "Ventil", "a/b", "x" * 41, None, "../x"):
        with pytest.raises(ServiceError):
            clean_type(bad)


def test_api_rejects_bad_input(api):
    assert api.put("/api/symbol-ports/Ventil", json={"ports": [[0, 0]]}).status_code == 400
    assert api.put("/api/symbol-ports/ventil", json={"ports": [[0, 2]]}).status_code == 400
    assert api.put("/api/symbol-ports/ventil", json={"ports": []}).status_code in (400, 422)


def test_viewer_cannot_read_or_change(api):
    assert api.post("/api/users", json={"username": "v1", "role": "viewer", "password": "Hemmelig-123"}).status_code == 201
    with TestClient(api.app) as v:
        v.post("/api/auth/login", json={"username": "v1", "password": "Hemmelig-123"})
        v.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
        v.post("/api/auth/login", json={"username": "v1", "password": "Hemmelig-123-ny"})
        assert v.get("/api/symbol-ports").status_code == 403
        assert v.put("/api/symbol-ports/ventil", json={"ports": [[0, 0]]}).status_code == 403
        assert v.delete("/api/symbol-ports/ventil").status_code == 403


def test_ports_survive_backup_roundtrip(api):
    api.put("/api/symbol-ports/ventil", json={"ports": [[0, 0.5], [1, 0.5]]})
    backup = api.get("/api/backup").json()
    assert backup["symbol_ports"] == {"ventil": [[0, 0.5], [1, 0.5]]}
    api.delete("/api/symbol-ports/ventil")
    assert api.post("/api/backup/restore", json=backup).status_code == 200
    assert api.get("/api/symbol-ports").json() == {"ventil": [[0, 0.5], [1, 0.5]]}
    # ældre backup uden punkter: gendannelsen rydder dem (projektet erstattes helt)
    old = {k: v for k, v in backup.items() if k != "symbol_ports"}
    assert api.post("/api/backup/restore", json=old).status_code == 200
    assert api.get("/api/symbol-ports").json() == {}
    backup["symbol_ports"] = {"ventil": [[3, 3]]}
    r = api.post("/api/backup/restore", json=backup)
    assert r.status_code == 400 and "Tilslutningspunkter" in r.json()["error"]


def test_limit_on_number_of_types_and_bad_rows(api, monkeypatch):
    import app.services.symbol_ports as sp
    monkeypatch.setattr(sp, "MAX_TYPES", 2)
    assert api.put("/api/symbol-ports/a", json={"ports": [[0, 0]]}).status_code == 200
    assert api.put("/api/symbol-ports/b", json={"ports": [[0, 0]]}).status_code == 200
    assert api.put("/api/symbol-ports/a", json={"ports": [[1, 1]]}).status_code == 200   # rette en eksisterende må man
    r = api.put("/api/symbol-ports/c", json={"ports": [[0, 0]]})
    assert r.status_code == 400 and "Højst 2" in r.json()["error"]
    # en beskadiget række springes over ved læsning
    api.app.state.symbol_port_service.db._execute("INSERT INTO meta(key, value) VALUES ('symbolports.x', '\"tekst\"')")
    assert "x" not in api.get("/api/symbol-ports").json()
