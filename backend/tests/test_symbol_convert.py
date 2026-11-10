"""Opgradering v5.1.0: den gamle symbolmodel fjernes — bibliotekssymboler med gamle bindinger konverteres til guidens opsætning
(samme regler som det tidligere "Konvertér alle"), de gamle bindinger slettes, og det, der ikke kan konverteres, står i en rapport.
Bagefter afvises simple bindinger på bibliotekssymboler (kun "Gå til tegning" på roden)."""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.bindings import symbol_bindings
from app.services.migrations import v51_symbols
from app.services.svg_sanitize import symbol_specs

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
LINK = '<g id="Link" data-hv-type="knap"><rect id="Link_flade" x="300" y="0" width="30" height="30"/></g>'
LOS = '<g id="Los" data-hv-type="lampe"><circle id="Los_lampe" cx="350" cy="50" r="10"/></g>'
SVG = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">{VIPPE}{OMSK}{KNAP}{TANK}{LINK}{LOS}</svg>'


def _old(c, element, items):
    """Gamle bindinger direkte i databasen (som før v5.1.0 — API'et afviser dem nu på bibliotekssymboler)."""
    ds = c.app.state.drawing_service
    ds.db.set_element_bindings(c.did, element, ds._normalize_bindings(items))


def _old_symbol_tag(c, element, tag):
    """Den gamle "tilknyt tag til hele symbolet": bindinger ud fra symbolets egen beskrivelse (data-hv-auto/-part)."""
    spec = symbol_specs(SVG)[element]
    per: dict[str, list] = {}
    for b in symbol_bindings(spec, element, {"name": tag, "writable": True}):
        per.setdefault(b["element"], []).append({"tag": b["tag"], "anim": b["anim"], "params": b["params"]})
    for el, items in per.items():
        _old(c, el, items)


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
            _old_symbol_tag(c, element, tag)
        assert c.put(f"/api/drawings/{c.did}/bindings/Tank_fyld",
                     json={"bindings": [{"tag": "Niveau", "anim": "level", "params": {"min": 0, "max": 100}}]}).status_code == 200
        c.svc = c.app.state.symbol_service
        yield c


def _suggest(api, element):
    return v51_symbols.suggest(api.svc.drawings, api.did, element)


def _cfg(api, element):
    return api.get(f"/api/drawings/{api.did}/symbols/{element}/config").json()["config"]


def _migrate(api):
    return v51_symbols.migrate(api.svc.db, api.svc, api.app.state.backup_service, force=True)


def test_toggle_select_and_pulse_rules(api):
    cfg = _suggest(api, "Vippe")["config"]
    assert cfg["op"] == "positions" and cfg["confirm"] is False
    assert [p["label"] for p in cfg["positions"]] == ["FRA", "TIL"]
    assert cfg["planes"] == [{"signal": "S1", "values": [0, 1]}] and cfg["signals"][0]["tag"] == "Lys"
    anims = {a["part"]: a for a in cfg["anims"]}
    assert anims["Vippe_spor"]["params"]["colors"] == ["#d6d6d6", "#7cc47f"]
    assert anims["Vippe_vippe"]["params"] == {"dxs": [0.0, 32.0], "dys": [0.0, 0.0]}
    omsk = _suggest(api, "Omsk")["config"]
    assert [p["label"] for p in omsk["positions"]] == ["Hånd", "0", "Auto"] and omsk["anims"][0]["params"]["angles"] == [-45.0, 0.0, 45.0]
    knap = _suggest(api, "Knap")["config"]
    assert knap["op"] == "pulse" and knap["pulse_ms"] == 700 and knap["anims"][0]["src"] == "Kvit"


def test_upgrade_converts_removes_old_bindings_and_reports(api):
    _old(api, "Link", [{"anim": "click:goto", "params": {"drawing": api.did}}])            # "Gå til tegning" på roden bliver stående
    _old(api, "Link_flade", [{"tag": "Kvit", "anim": "click:pulse"}, {"tag": "Kvit", "anim": "fill"}])   # klik på en del: manuel
    before = {(b["element"], b["anim"]) for b in api.get(f"/api/drawings/{api.did}/view").json()["bindings"]}
    assert ("Vippe", "click:toggle") not in before                  # den gamle model gælder ikke længere i visningen
    rep = _migrate(api)
    assert rep is not None
    assert {r["element"] for r in rep["converted"]} == {"Vippe", "Omsk", "Knap"}
    manual = {r["element"]: r for r in rep["manual"]}
    assert set(manual) == {"Link"} and "click:pulse på Link_flade" in manual["Link"]["reasons"][0]
    assert _cfg(api, "Vippe")["op"] == "positions" and _cfg(api, "Knap")["op"] == "pulse" and _cfg(api, "Link") is None
    rows = api.get(f"/api/drawings/{api.did}/bindings").json()
    left = {(b["element"], b["anim"]) for b in rows}
    assert left == {("Link", "click:goto"), ("Tank_fyld", "level")}        # alt andet på symbolerne er slettet
    view = api.get(f"/api/drawings/{api.did}/view").json()["bindings"]
    assert {(b["element"], b["anim"]) for b in view if b["element"].startswith("Vippe")} == {
        ("Vippe_spor", "fill"), ("Vippe_vippe", "move"), ("Vippe_tekst", "text")}
    assert ("Link", "click:goto") in {(b["element"], b["anim"]) for b in view}
    # rapporten kan læses og ryddes; en ny kørsel uden force gør intet
    assert api.get("/api/symbol-migration").json()["converted"][0]["element"] in {"Vippe", "Omsk", "Knap"}
    assert api.delete("/api/symbol-migration").status_code == 204 and api.get("/api/symbol-migration").json() is None
    assert v51_symbols.migrate(api.svc.db, api.svc) is None
    assert any("pre-update" in b["name"] for b in api.app.state.backup_service.list_server_backups())   # backup før ændringen


def test_simple_bindings_on_library_symbols_are_refused(api):
    url = f"/api/drawings/{api.did}/bindings"
    r = api.put(f"{url}/Vippe_spor", json={"bindings": [{"tag": "Lys", "anim": "fill"}]})
    assert r.status_code == 409 and "Opsæt symbol" in r.json()["error"]
    assert api.put(f"{url}/Los", json={"bindings": [{"tag": "Lys", "anim": "fill"}]}).status_code == 409
    assert api.put(f"{url}/Los", json={"bindings": [{"anim": "click:goto", "params": {"drawing": api.did}}]}).status_code == 200
    assert api.put(f"{url}/Tank_fyld", json={"bindings": [{"tag": "Niveau", "anim": "fill"}]}).status_code == 200   # ikke et symbol
    assert api.put(f"/api/drawings/{api.did}/symbols/Vippe", json={"tag": "Lys"}).status_code == 422    # "tilknyt tag" findes ikke
    assert api.put(f"/api/drawings/{api.did}/symbols/Vippe", json={"description": "Lyset"}).status_code == 200
    assert api.get(f"/api/drawings/{api.did}/symbols/Vippe/suggest").status_code in (404, 405)
    assert api.post("/api/drawings/convert-symbols", json={}).status_code in (404, 405)


def test_tag_name_automatic_only_for_plain_elements(api):
    """Et element, hvis id er et tag, bindes stadig automatisk — men ikke et bibliotekssymbol (det sættes op i guiden)."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect id="Lys" width="10" height="10"/>'
           '<g id="Kvit" data-hv-type="lampe"><circle id="Kvit_l" cx="50" cy="50" r="5"/></g></svg>')
    did = api.post("/api/drawings", json={"name": "Auto", "svg": svg}).json()["drawing"]["id"]
    els = {b["element"] for b in api.get(f"/api/drawings/{did}/view").json()["bindings"] if b["source"] == "auto"}
    assert els == {"Lys"}


def test_setpoint_keeps_confirmation_and_toggle_colors_ignore_thresholds(api):
    assert api.post("/api/tags", json={"name": "SP", "source": "plc1:hr:33", "writable": True,
                                       "confirm_write": False}).status_code == 201
    _old(api, "Los", [{"tag": "SP", "anim": "click:write"}])
    cfg = _suggest(api, "Los")["config"]
    assert cfg["op"] == "entry" and cfg["confirm"] is False
    _old(api, "Vippe_spor", [{"tag": "Lys", "anim": "fill", "params": {"on": "#00aa00", "off": "#cccccc",
                                                                       "thresholds": [{"value": 1, "color": "#ff0000"}]}}])
    anims = {a["part"]: a for a in _suggest(api, "Vippe")["config"]["anims"]}
    assert anims["Vippe_spor"]["params"]["colors"] == ["#cccccc", "#00aa00"]


def test_restoring_an_old_backup_converts_it(api):
    bk = api.get("/api/backup").json()                       # indeholder de gamle bindinger på symbolerne
    r = api.post("/api/backup/restore", json=bk)
    assert r.status_code == 200, r.text
    assert r.json()["symbol_migration"]["converted"] == 3
    assert _cfg(api, "Omsk")["op"] == "positions"


def test_manual_symbols_keep_a_record_of_what_was_removed(api):
    _old(api, "Link_flade", [{"tag": "Kvit", "anim": "click:pulse"}, {"tag": "Kvit", "anim": "fill"}])
    rep = _migrate(api)
    link = next(m for m in rep["manual"] if m["element"] == "Link")
    assert {(r["element"], r["anim"]) for r in link["removed"]} == {("Link_flade", "click:pulse"), ("Link_flade", "fill")}
    assert all("notes" in c for c in rep["converted"])
    assert not [b for b in api.get(f"/api/drawings/{api.did}/bindings").json() if b["element"] == "Link_flade"]


def test_goto_only_on_symbols_without_operation(api):
    url = f"/api/drawings/{api.did}/bindings"
    goto = {"bindings": [{"anim": "click:goto", "params": {"drawing": api.did}}]}
    assert api.put(f"{url}/Los", json=goto).status_code == 200                       # ikke opsat: tilladt
    _migrate(api)
    assert _cfg(api, "Vippe")["op"] == "positions"
    assert api.put(f"{url}/Vippe", json=goto).status_code == 409                      # betjent symbol: klik åbner dialogen
    _old(api, "Vippe", goto["bindings"])                                              # en gammel, sovende goto bliver ikke aktiv
    assert ("Vippe", "click:goto") not in {(b["element"], b["anim"]) for b in api.get(f"/api/drawings/{api.did}/view").json()["bindings"]}


def test_a_failing_backup_postpones_the_upgrade(api):
    class Broken:
        def save_to_server(self, *a):
            raise OSError("disken er fuld")
    api.svc.db.set_meta(v51_symbols.DONE_KEY, None)
    assert v51_symbols.migrate(api.svc.db, api.svc, Broken()) is None
    assert v51_symbols.pending(api.svc.db) is True
    assert _cfg(api, "Vippe") is None                                                 # intet ændret
    assert any(b["element"] == "Vippe" for b in api.get(f"/api/drawings/{api.did}/bindings").json())
