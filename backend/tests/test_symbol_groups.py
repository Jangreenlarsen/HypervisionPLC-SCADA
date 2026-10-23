"""Navngivne symbolgrupper (v0.130.0): oprettelse, overlap, unikt navn, rettigheder, backup-rundtur og sletning med tegningen."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"><g id="A" data-hv-type="pumpe"><circle id="A_c" cx="50" cy="40" r="20"/></g>'
       '<g id="B" data-hv-type="pumpe"><circle id="B_c" cx="150" cy="40" r="20"/></g></svg>')


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.did = c.post("/api/drawings", json={"name": "Anlæg", "svg": SVG}).json()["drawing"]["id"]
        yield c


def url(api, tail=""):
    return f"/api/drawings/{api.did}/groups{tail}"


def test_create_list_update_delete(api):
    r = api.post(url(api), json={"name": "Fyr uden akku-tank", "kind": "function", "members": ["A", "B", "A"]})
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["members"] == ["A", "B"] and g["kind"] == "function"
    assert api.get(url(api)).json() == [g]
    # omdøb uden at røre medlemmerne (members udeladt)
    r = api.put(url(api, f"/{g['id']}"), json={"name": "Fyr", "kind": "selection"})
    assert r.status_code == 200 and r.json()["members"] == ["A", "B"] and r.json()["name"] == "Fyr"
    r = api.put(url(api, f"/{g['id']}"), json={"name": "Fyr", "kind": "selection", "members": ["B"]})
    assert r.json()["members"] == ["B"]
    assert api.delete(url(api, f"/{g['id']}")).status_code == 204
    assert api.get(url(api)).json() == []
    assert api.delete(url(api, f"/{g['id']}")).status_code == 404


def test_same_element_in_several_groups_and_unique_names(api):
    a = api.post(url(api), json={"name": "G1", "members": ["A"]}).json()
    b = api.post(url(api), json={"name": "G2", "members": ["A", "B"]})
    assert b.status_code == 201
    groups = {g["name"]: g["members"] for g in api.get(url(api)).json()}
    assert groups == {"G1": ["A"], "G2": ["A", "B"]}
    dup = api.post(url(api), json={"name": "G1", "members": []})
    assert dup.status_code == 409 and "G1" in dup.json()["error"]
    # omdøb til et eksisterende navn afvises og ændrer intet
    r = api.put(url(api, f"/{a['id']}"), json={"name": "G2", "members": ["B"]})
    assert r.status_code == 409
    assert {g["name"]: g["members"] for g in api.get(url(api)).json()}["G1"] == ["A"]


def test_validation_and_unknown(api):
    assert api.post(url(api), json={"name": "  ", "members": []}).status_code in (400, 422)
    assert api.post(url(api), json={"name": "X", "kind": "ukendt"}).status_code in (400, 422)
    assert api.put(url(api, "/999"), json={"name": "X", "kind": "selection"}).status_code == 404
    assert api.get("/api/drawings/findes-ikke/groups").status_code == 404


def test_viewer_can_read_but_not_write(api):
    api.post(url(api), json={"name": "G", "members": ["A"]})
    assert api.post("/api/users", json={"username": "v1", "role": "viewer", "password": "Hemmelig-123"}).status_code == 201
    with TestClient(api.app) as v:
        assert v.post("/api/auth/login", json={"username": "v1", "password": "Hemmelig-123"}).status_code == 200
        assert len(v.get(url(api)).json()) == 1
        assert v.post(url(api), json={"name": "H", "members": []}).status_code == 403


def test_backup_roundtrip_and_cascade(api):
    api.post(url(api), json={"name": "G1", "kind": "function", "members": ["A", "B"]})
    api.post(url(api), json={"name": "G2", "members": ["B"]})
    backup = api.get("/api/backup").json()
    assert {g["name"] for g in backup["symbol_groups"]} == {"G1", "G2"}
    api.delete(url(api, "/" + str(api.get(url(api)).json()[0]["id"])))
    r = api.post("/api/backup/restore", json=backup)
    assert r.status_code == 200, r.text
    groups = {g["name"]: (g["kind"], g["members"]) for g in api.get(url(api)).json()}
    assert groups == {"G1": ("function", ["A", "B"]), "G2": ("selection", ["B"])}
    # grupperne følger tegningen ved sletning
    assert api.delete(f"/api/drawings/{api.did}").status_code in (200, 204)
    assert api.get(url(api)).status_code == 404


def test_restore_rejects_bad_groups(api):
    backup = api.get("/api/backup").json()
    backup["symbol_groups"] = [{"drawing_id": api.did, "name": "G", "kind": "x", "members": []}]
    r = api.post("/api/backup/restore", json=backup)
    assert r.status_code == 400 and "Symbolgruppe" in r.json()["error"]
