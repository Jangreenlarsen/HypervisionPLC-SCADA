"""Forsvundne symbolopsætninger (v0.88.0): opsætninger på elementer, der ikke findes i den aktive version — vises og
kan flyttes til et andet element (dele følger id-mønstret, PIN flyttes med) eller fjernes."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"


def pump(i: str, x: int) -> str:
    return (f'<g id="{i}" data-hv-type="pumpe" data-hv-name="Pumpe {i}"><circle id="{i}_c" cx="{x}" cy="40" r="20"/>'
            f'<g id="{i}_pil" data-hv-pid="pil"><path d="M{x - 10} 40 H{x + 10}" stroke="#333"/></g></g>')


def svg(*parts: str) -> str:
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">' + "".join(parts) + "</svg>"


CFG = {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "Drift", "params": {}},
                               {"part": "P_pil", "type": "visible", "src": "Drift", "params": {}}]}


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        assert c.post("/api/tags", json={"name": "Drift", "source": "plc1:coil:10"}).status_code == 201
        c.did = c.post("/api/drawings", json={"name": "Anlæg", "svg": svg(pump("P", 50))}).json()["drawing"]["id"]
        assert c.put(f"/api/drawings/{c.did}/symbols/P/config", json={"config": CFG}).status_code == 200
        yield c


def new_version(api, *parts: str) -> None:
    r = api.post(f"/api/drawings/{api.did}/versions", json={"svg": svg(*parts), "activate": True})
    assert r.status_code == 201, r.text


def test_orphan_listed_and_moved_with_parts_and_pin(api):
    base = f"/api/drawings/{api.did}"
    assert api.put(f"{base}/symbols/P/pin", json={"pin": "1234"}).status_code == 200
    assert api.get(f"{base}/symbols-orphaned").json() == []
    new_version(api, pump("P_2", 50), '<g id="X" data-hv-name="X"><rect id="X_r" width="10" height="10"/></g>')
    orphans = api.get(f"{base}/symbols-orphaned").json()
    assert [o["element"] for o in orphans] == ["P"] and orphans[0]["has_pin"] is True
    assert [(a["part"], a["type"]) for a in orphans[0]["anims"]] == [("all", "fill"), ("P_pil", "visible")]
    # kilden findes ikke længere som element: kun flyt/fjern
    assert api.post(f"{base}/symbols/P/move", json={"target": "findes_ikke"}).status_code == 404
    r = api.post(f"{base}/symbols/P/move", json={"target": "P_2"})
    assert r.status_code == 200, r.text
    assert r.json()["dropped"] == []
    got = api.get(f"{base}/symbols/P_2/config").json()
    assert [a["part"] for a in got["config"]["anims"]] == ["all", "P_2_pil"] and got["has_pin"] is True
    assert api.get(f"{base}/symbols/P/config").json()["config"] is None
    assert api.get(f"{base}/symbols-orphaned").json() == []
    assert api.get("/api/audit?action=symbol.move").json()[0]["target"] == f"{api.did}#P"


def test_move_drops_unknown_parts_and_refuses_bad_targets(api):
    base = f"/api/drawings/{api.did}"
    new_version(api, pump("P_2", 50), '<g id="X" data-hv-name="X"><rect id="X_r" width="10" height="10"/></g>')
    one = {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "Drift", "params": {}}]}
    assert api.put(f"{base}/symbols/P_2/config", json={"config": one}).status_code == 200
    r = api.post(f"{base}/symbols/P/move", json={"target": "P_2"})
    assert r.status_code == 409 and "har allerede en opsætning" in r.json()["error"]
    r = api.post(f"{base}/symbols/P/move", json={"target": "X"})
    assert r.status_code == 200 and r.json()["dropped"] == ["P_pil"]
    assert [a["part"] for a in api.get(f"{base}/symbols/X/config").json()["config"]["anims"]] == ["all"]
    # en opsætning, hvis element stadig findes, kan ikke flyttes
    r = api.post(f"{base}/symbols/X/move", json={"target": "P_2"})
    assert r.status_code == 409 and "findes stadig" in r.json()["error"]


def test_failed_move_leaves_everything_as_before(api):
    """Ugyldig på målet: intet flyttes, og PIN'en efterlades ikke på målet."""
    base = f"/api/drawings/{api.did}"
    api.put(f"{base}/symbols/P/pin", json={"pin": "1234"})
    new_version(api, pump("Q", 50))
    # en opsætning som målet ikke kan bære (Niveau kræver et rektangel — Q er en gruppe), lagt direkte i databasen
    bad = {"type": "pumpe", "op": "view", "anims": [{"part": "all", "type": "level", "src": "Drift", "params": {}}]}
    api.app.state.symbol_service.db.set_symbol_config(api.did, "P", bad, "admin")
    r = api.post(f"{base}/symbols/P/move", json={"target": "Q"})
    assert r.status_code == 400, r.text
    assert api.get(f"{base}/symbols/Q/config").json()["has_pin"] is False
    assert [o["element"] for o in api.get(f"{base}/symbols-orphaned").json()] == ["P"]
