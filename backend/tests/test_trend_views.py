"""Gemte trend-visninger (v1.16.0): fælles navngivne udvalg af tags, grafer og periode."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.errors import ServiceError
from app.services.trend_views import clean_view

ADMIN_PW = "test-admin-pw-1"


@pytest.fixture
def api(tmp_path):
    settings = Settings(data_dir=tmp_path, frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0, start_runtimes=False)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        yield c


VIEW = {"name": "Tank temp", "tags": [f"T{i}" for i in range(8)], "assign": {"T0": 1, "T1": 1, "T2": 2, "Ukendt": 3}, "range": "8h"}


def test_save_list_overwrite_delete(api):
    r = api.post("/api/trends/views", json=VIEW)
    assert r.status_code == 200 and r.json()["assign"] == {"T0": 1, "T1": 1, "T2": 2}   # graf-valg for tags uden for visningen droppes
    assert api.get("/api/trends/views").json() == [r.json()]
    # samme navn (andre bogstaver) erstatter — navnet er unikt uden hensyn til store/små
    api.post("/api/trends/views", json={**VIEW, "name": "TANK TEMP", "tags": ["T0"], "range": "24h"})
    views = api.get("/api/trends/views").json()
    assert len(views) == 1 and views[0]["name"] == "TANK TEMP" and views[0]["tags"] == ["T0"] and views[0]["range"] == "24h"
    assert api.delete("/api/trends/views", params={"name": "tank temp"}).status_code == 204
    assert api.get("/api/trends/views").json() == []
    assert api.delete("/api/trends/views", params={"name": "tank temp"}).status_code == 404


def test_validation():
    ok = clean_view({"name": " X ", "tags": ["A", "A", "B"], "assign": {"A": 9, "B": 2}, "range": "custom"})
    assert ok == {"name": "X", "tags": ["A", "B"], "assign": {"B": 2}, "range": "1h"}
    for bad in ({"name": "", "tags": ["A"]}, {"name": "x" * 41, "tags": ["A"]}, {"name": "a\nb", "tags": ["A"]},
                {"name": "X", "tags": []}, {"name": "X", "tags": "A"}, {"name": "X", "tags": [f"T{i}" for i in range(41)]},
                {"name": "X", "tags": ["A"], "assign": ["x"]}):
        with pytest.raises(ServiceError):
            clean_view(bad)


def test_viewer_can_list_but_not_change(api):
    api.post("/api/trends/views", json=VIEW)
    assert api.post("/api/users", json={"username": "v1", "role": "viewer", "password": "Hemmelig-123"}).status_code == 201
    with TestClient(api.app) as v:
        v.post("/api/auth/login", json={"username": "v1", "password": "Hemmelig-123"})
        v.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
        v.post("/api/auth/login", json={"username": "v1", "password": "Hemmelig-123-ny"})
        assert [x["name"] for x in v.get("/api/trends/views").json()] == ["Tank temp"]
        assert v.post("/api/trends/views", json=VIEW).status_code == 403
        assert v.delete("/api/trends/views", params={"name": "Tank temp"}).status_code == 403


def test_views_survive_backup_roundtrip(api):
    api.post("/api/trends/views", json=VIEW)
    backup = api.get("/api/backup").json()
    assert [v["name"] for v in backup["trend_views"]] == ["Tank temp"]
    api.delete("/api/trends/views", params={"name": "Tank temp"})
    assert api.post("/api/backup/restore", json=backup).status_code == 200
    assert [v["name"] for v in api.get("/api/trends/views").json()] == ["Tank temp"]
    backup["trend_views"][0]["name"] = ""
    r = api.post("/api/backup/restore", json=backup)
    assert r.status_code == 400 and "Trend-visning" in r.json()["error"]
