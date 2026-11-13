"""v6.9.4 (Jan): pumpens flow-rate "følger pumpens position" (@pos) — gemmes kun på et symbol med positioner."""
from tests.drawing_api import api  # noqa: F401 — fixture

FLOW = {"pump": True, "capacity": 100, "rate": {"src": "@pos", "max": 1}}
PUMP = {"op": "positions", "passive": True, "positions": [{"label": "Fra"}, {"label": "Til"}],
        "signals": [{"id": "S1", "tag": "P1_drift", "fb": "P1_drift"}], "planes": [{"signal": "S1", "values": [0, 1]}],
        "display": "remote", "validate_s": 5, "flow": FLOW}


def test_rate_from_position_needs_positions(api):
    d = api.d
    r = api.put(f"/api/drawings/{d}/symbols/p1/config", json={"config": PUMP})
    assert r.status_code == 200, r.text
    view_only = {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "P1_drift", "params": {}}], "flow": FLOW}
    r = api.put(f"/api/drawings/{d}/symbols/p1/config", json={"config": view_only})
    assert r.status_code == 400 and "kræver, at symbolet har positioner" in r.text
