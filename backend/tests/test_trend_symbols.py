"""Trends ud fra symbolerne (v0.80.0): GET /api/trends/symbols — opsatte symboler med deres tags, filtreret efter adgang."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">'
       '<g id="P1" data-hv-type="pumpe" data-hv-name="Pumpe 1"><circle id="P1_c" cx="20" cy="20" r="10"/></g>'
       '<g id="P2" data-hv-type="pumpe"><circle id="P2_c" cx="60" cy="20" r="10"/></g>'
       '<g id="L1" data-hv-type="lampe" data-hv-name="Lampe"><circle id="L1_c" cx="90" cy="20" r="10"/></g></svg>')


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        for t in [{"name": "Start", "source": "plc1:coil:10", "writable": True}, {"name": "Drift", "source": "plc1:coil:11"},
                  {"name": "Tryk", "source": "plc1:hr:31"}, {"name": "Lys", "source": "plc1:coil:20"}]:
            assert c.post("/api/tags", json=t).status_code == 201, t
        c.did = c.post("/api/drawings", json={"name": "Anlæg", "svg": SVG}).json()["drawing"]["id"]
        yield c


def _put(api, did, element, cfg):
    r = api.put(f"/api/drawings/{did}/symbols/{element}/config", json={"config": cfg})
    assert r.status_code == 200, r.text


def test_symbols_with_their_tags_and_scope(api):
    _put(api, api.did, "P1", {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "Drift", "params": {}},
                                                    {"part": "all", "type": "opacity", "src": "Tryk", "params": {}},
                                                    {"part": "all", "type": "blink", "src": "Start", "params": {}}]})
    _put(api, api.did, "P2", {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "Drift", "params": {}}]})
    assert api.get("/api/trends/symbols").json() == [
        {"drawing": api.did, "drawing_name": "Anlæg", "element": "P1", "name": "Pumpe 1", "tags": ["Drift", "Tryk", "Start"]},
        {"drawing": api.did, "drawing_name": "Anlæg", "element": "P2", "name": "P2", "tags": ["Drift"]},   # uden navn: id'et
    ]
    # en anden tegning, som en begrænset bruger ikke må se
    other = api.post("/api/drawings", json={"name": "Andet", "svg": SVG}).json()["drawing"]["id"]
    _put(api, other, "L1", {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "Lys", "params": {}}]})
    assert sorted(s["drawing"] for s in api.get("/api/trends/symbols").json()) == sorted([api.did, api.did, other])
    assert api.post("/api/users", json={"username": "vagt", "role": "viewer", "password": "Hemmelig-123",
                                        "drawings": [api.did]}).status_code == 201
    api.post("/api/auth/login", json={"username": "vagt", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert [s["element"] for s in api.get("/api/trends/symbols").json()] == ["P1", "P2"]


def test_config_on_element_missing_from_active_version_is_skipped(api):
    _put(api, api.did, "L1", {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "Lys", "params": {}}]})
    svg2 = SVG.replace('<g id="L1" data-hv-type="lampe" data-hv-name="Lampe"><circle id="L1_c" cx="90" cy="20" r="10"/></g>', '')
    r = api.post(f"/api/drawings/{api.did}/versions", json={"svg": svg2, "activate": True})
    assert r.status_code in (200, 201), r.text
    assert api.get("/api/trends/symbols").json() == []


def test_trend_chart_config(api):
    """Trendgraf (v0.91.0): tags valideres, advarsel uden historik, Y-akse, og Overview får grafen og tagenes metadata."""
    base = f"/api/drawings/{api.did}/symbols/L1/config"
    chart = {"tags": ["Tryk", "Tryk", "Drift"], "range_s": 3600, "style": "bar", "bars": 12}
    r = api.put(base, json={"config": {"op": "view", "chart": chart}})
    assert r.status_code == 200, r.text
    assert r.json()["config"]["chart"]["tags"] == ["Tryk", "Drift"]          # dubletter fjernet
    assert any("gemmer ikke historik" in w for w in r.json()["warnings"])
    for bad, why in [({"tags": []}, "mindst ét tag"), ({"tags": ["Findes"]}, "findes ikke"),
                     ({"tags": ["Tryk"], "y_min": 10, "y_max": 5}, "min skal være mindre"),
                     ({"tags": ["Tryk"], "range_s": 1234}, "perioden"),
                     ({"tags": ["Tryk", "Drift", "Start", "Lys", "Tryk"]}, "")]:
        r = api.put(base, json={"config": {"op": "view", "chart": bad}})
        assert r.status_code == 400 and why in r.text, (bad, r.text)
    view = api.get(f"/api/drawings/{api.did}/view").json()
    assert view["symbol_config"]["L1"]["chart"]["style"] == "bar"
    assert {"Tryk", "Drift"} <= set(view["tags"])
    # grafens tags er symbolets tags: Trends-symbollisten og sletbeskyttelse
    assert [s["tags"] for s in api.get("/api/trends/symbols").json() if s["element"] == "L1"] == [["Tryk", "Drift"]]
    assert api.delete("/api/tags/Drift").status_code == 409

