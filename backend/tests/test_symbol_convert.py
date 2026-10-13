"""Symbolstandard: forslag ud fra den gamle model (Konvertér) — og forslaget skal kunne gemmes uændret."""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"


def _auto(items):
    return "'" + json.dumps(items) + "'"


VIPPE = ('<g id="Vippe" data-hv-type="vippekontakt" data-hv-auto=' + _auto([{"anim": "click:toggle", "params": {"confirm": False}}]) + '>'
         '<rect id="Vippe_spor" data-hv-pid="spor" width="64" height="32" data-hv-part=' + _auto({"anim": "fill", "params": {"on": "#7cc47f", "off": "#d6d6d6"}}) + '/>'
         '<circle id="Vippe_vippe" data-hv-pid="vippe" cx="16" cy="16" r="12" data-hv-part=' + _auto({"anim": "move", "params": {"min": 0, "max": 1, "dx": 32, "dy": 0}}) + '/>'
         '<text id="Vippe_tekst" data-hv-pid="tekst" x="32" y="50" data-hv-part=' + _auto({"anim": "text", "params": {"true_text": "TIL", "false_text": "FRA"}}) + '>FRA</text></g>')
OMSK = ('<g id="Omsk" data-hv-type="omskifter3" transform="translate(100 0)" data-hv-auto=' + _auto([{"anim": "click:select", "params": {
        "positions": [{"value": 0, "label": "Hånd"}, {"value": 1, "label": "0"}, {"value": 2, "label": "Auto"}], "confirm": True}}]) + '>'
        '<circle cx="70" cy="70" r="30"/><g id="Omsk_greb" data-hv-pid="greb" data-hv-part=' + _auto({"anim": "rotate", "params": {
            "min": 0, "max": 2, "angle_min": -45, "angle_max": 45}}) + '><rect x="64" y="44" width="12" height="52"/></g></g>')
KNAP = ('<g id="Knap" data-hv-auto=' + _auto([{"anim": "click:pulse", "params": {"ms": 700, "confirm": False}}]) + '>'
        '<rect id="Knap_flade" width="40" height="40" data-hv-part=' + _auto({"anim": "fill", "params": {"on": "#7cc47f", "off": "#d6d6d6"}}) + '/></g>')
TANK = '<g id="Tank"><rect id="Tank_fyld" x="0" y="200" width="40" height="80"/></g>'
SVG = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">{VIPPE}{OMSK}{KNAP}{TANK}</svg>'


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        for t in [{"name": "Lys", "source": "plc1:coil:7", "writable": True},
                  {"name": "Mode", "source": "plc1:hr:30", "writable": True, "min": 0, "max": 2},
                  {"name": "Kvit", "source": "plc1:coil:8", "writable": True},
                  {"name": "Niveau", "source": "plc1:hr:31"}]:
            assert c.post("/api/tags", json=t).status_code == 201
        c.did = c.post("/api/drawings", json={"name": "Gammel", "svg": SVG}).json()["drawing"]["id"]
        for element, tag in (("Vippe", "Lys"), ("Omsk", "Mode"), ("Knap", "Kvit")):
            assert c.put(f"/api/drawings/{c.did}/symbols/{element}", json={"tag": tag}).status_code == 200
        assert c.put(f"/api/drawings/{c.did}/bindings/Tank_fyld",
                     json={"bindings": [{"tag": "Niveau", "anim": "level", "params": {"min": 0, "max": 100}}]}).status_code == 200
        yield c


def _suggest(api, element):
    r = api.get(f"/api/drawings/{api.did}/symbols/{element}/suggest")
    assert r.status_code == 200, r.text
    return r.json()


def _save(api, element, cfg):
    return api.put(f"/api/drawings/{api.did}/symbols/{element}/config", json={"config": cfg})


def test_toggle_becomes_two_positions_with_animations_per_position(api):
    s = _suggest(api, "Vippe")
    cfg = s["config"]
    assert s["convertible"] and cfg["op"] == "positions" and cfg["confirm"] is False
    assert [p["label"] for p in cfg["positions"]] == ["FRA", "TIL"]
    assert cfg["planes"] == [{"signal": "S1", "values": [0, 1]}] and cfg["signals"][0]["tag"] == "Lys"
    anims = {a["part"]: a for a in cfg["anims"]}
    assert anims["Vippe_spor"]["params"]["colors"] == ["#d6d6d6", "#7cc47f"]
    assert anims["Vippe_vippe"]["params"] == {"dxs": [0.0, 32.0], "dys": [0.0, 0.0]}
    assert anims["Vippe_tekst"]["src"] == "@pos"
    r = _save(api, "Vippe", cfg)
    assert r.status_code == 200, r.text


def test_select_becomes_positions_with_angles(api):
    cfg = _suggest(api, "Omsk")["config"]
    assert [p["label"] for p in cfg["positions"]] == ["Hånd", "0", "Auto"]
    assert cfg["planes"][0]["values"] == [0, 1, 2]
    assert cfg["anims"][0]["params"]["angles"] == [-45.0, 0.0, 45.0]
    assert _save(api, "Omsk", cfg).status_code == 200


def test_pulse_and_plain_bindings(api):
    cfg = _suggest(api, "Knap")["config"]
    assert cfg["op"] == "pulse" and cfg["pulse_ms"] == 700 and cfg["signals"][0]["tag"] == "Kvit"
    assert cfg["anims"][0]["src"] == "Kvit"                 # farven følger stadig tagget
    assert _save(api, "Knap", cfg).status_code == 200
    tank = _suggest(api, "Tank")
    assert tank["config"]["op"] == "view" and tank["config"]["anims"][0]["type"] == "level"
    assert _save(api, "Tank", tank["config"]).status_code == 200


def test_converted_symbol_behaves_like_before_in_view(api):
    """Efter konvertering: de gamle bindinger er væk fra visningen, symbolets egne er der i stedet."""
    before = {(b["element"], b["anim"]) for b in api.get(f"/api/drawings/{api.did}/view").json()["bindings"]
              if b["element"].startswith("Vippe")}
    assert ("Vippe", "click:toggle") in before
    assert _save(api, "Vippe", _suggest(api, "Vippe")["config"]).status_code == 200
    after = [b for b in api.get(f"/api/drawings/{api.did}/view").json()["bindings"] if b["element"].startswith("Vippe")]
    assert all(b["source"] == "symbol" for b in after)
    assert {(b["element"], b["anim"]) for b in after} == {("Vippe_spor", "fill"), ("Vippe_vippe", "move"), ("Vippe_tekst", "text")}
    # Forslaget kan stadig hentes (fra den gamle model), selvom symbolet nu er konfigureret
    assert _suggest(api, "Vippe")["config"]["op"] == "positions"


def test_symbol_without_bindings_is_not_convertible(api):
    api.put(f"/api/drawings/{api.did}/bindings/Tank_fyld", json={"bindings": []})
    s = _suggest(api, "Tank")
    assert s["convertible"] is False and "ingen bindinger" in s["notes"][0]
