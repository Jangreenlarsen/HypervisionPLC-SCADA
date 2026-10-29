"""Kopiér et symbols opsætning til flere symboler: oversættelse af dele, overskrivning, fejl pr. mål, lås, audit."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.symbols import map_config

ADMIN_PW = "test-admin-pw-1"


def _sel(i: int, x: int) -> str:
    return (f'<g id="V{i}" data-hv-type="omskifter3" data-hv-name="Vælger V{i}">'
            f'<circle id="V{i}_skive" data-hv-pid="skive" cx="{x}" cy="20" r="15"/>'
            f'<rect id="V{i}_greb" data-hv-pid="greb" x="{x}" y="5" width="4" height="15"/>'
            f'<text id="V{i}_tekst" data-hv-pid="tekst" x="{x}" y="45">0</text></g>')


def _pipe(i: int, y: int) -> str:
    return (f'<g id="R{i}" data-hv-type="ror_vandret" data-hv-name="Rør {i}">'
            f'<path id="R{i}_streg" data-hv-pid="ror" d="M0 {y} H90" stroke="#555" stroke-width="10"/></g>')


SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">'
       + _sel(1, 20) + _sel(2, 80)
       + _pipe(1, 100) + _pipe(2, 120) + _pipe(3, 140)
       # en bøjning uden en "ror"-del: animationer på hele symbolet følger med, del-animationer ikke
       + '<g id="B1" data-hv-type="ror_bojning" data-hv-name="Bøjning 1"><path id="B1_bue" data-hv-pid="bue" d="M0 200 Q20 200 20 220" stroke="#555" stroke-width="10" fill="none"/></g>'
       + '<g id="Lampe"><circle id="Lampe_glas" cx="200" cy="20" r="10"/></g>'
       + '<rect id="Tank" x="300" y="100" width="40" height="80"/></svg>')
TAGS = [
    {"name": "Bit0", "source": "plc1:coil:10", "writable": True},
    {"name": "Bit1", "source": "plc1:coil:11", "writable": True},
    {"name": "Lys", "source": "plc1:coil:20"},
    {"name": "Niveau", "source": "plc1:hr:31"},
]
FLOW = {"op": "view", "anims": [
    {"part": "all", "type": "flow", "src": "Lys", "params": {"dir_tag": "Bit1", "arm": "", "mode": "onoff"}},
    {"part": "R1_streg", "type": "stroke", "src": "Lys", "params": {"on": "#2a7fff"}},
]}


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        for t in TAGS:
            assert c.post("/api/tags", json=t).status_code == 201, t
        c.did = c.post("/api/drawings", json={"name": "Anlæg", "svg": SVG}).json()["drawing"]["id"]
        yield c


def put(api, cfg, element, pin=None):
    body = {"config": cfg} | ({"pin": pin} if pin is not None else {})
    return api.put(f"/api/drawings/{api.did}/symbols/{element}/config", json=body)


def copy(api, source, targets, overwrite=False):
    return api.post(f"/api/drawings/{api.did}/symbols/{source}/copy", json={"targets": targets, "overwrite": overwrite})


def cfg_of(api, element):
    r = api.get(f"/api/drawings/{api.did}/symbols/{element}/config")
    return r.json()["config"] if r.status_code == 200 else None


def test_copy_translates_parts_by_library_name(api):
    assert put(api, FLOW, "R1").status_code == 200
    r = copy(api, "R1", ["R2", "R3"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["ok"], body["skipped"], body["error"]) == (2, 0, 0)
    for el in ("R2", "R3"):
        anims = cfg_of(api, el)["anims"]
        assert [a["part"] for a in anims] == ["all", f"{el}_streg"]
        assert anims[0]["params"]["dir_tag"] == "Bit1"
    # kopierne er selvstændige: ændres R2, rører det ikke R3
    assert put(api, {"op": "view", "anims": [FLOW["anims"][0]]}, "R2").status_code == 200
    assert len(cfg_of(api, "R3")["anims"]) == 2


def test_part_animation_without_matching_part_is_dropped_with_note(api):
    assert put(api, FLOW, "R1").status_code == 200
    res = copy(api, "R1", ["B1"]).json()["results"][0]
    assert res["status"] == "ok"
    assert any("ror" in n and "sprunget over" in n for n in res["notes"])
    assert [a["part"] for a in cfg_of(api, "B1")["anims"]] == ["all"]


def test_existing_config_is_skipped_unless_overwrite(api):
    assert put(api, FLOW, "R1").status_code == 200
    own = {"op": "view", "anims": [{"part": "all", "type": "flow", "src": "Bit0", "params": {}}]}
    assert put(api, own, "R2").status_code == 200
    body = copy(api, "R1", ["R2", "R3"]).json()
    assert {r["element"]: r["status"] for r in body["results"]} == {"R2": "skipped", "R3": "ok"}
    assert cfg_of(api, "R2")["anims"][0]["src"] == "Bit0"
    body = copy(api, "R1", ["R2"], overwrite=True).json()
    assert body["ok"] == 1 and cfg_of(api, "R2")["anims"][0]["src"] == "Lys"


def test_each_target_validated_on_its_own(api):
    """Et mål hvor kopien er ugyldig (løbelys kræver streger), eller som ikke findes, stopper ikke de andre."""
    assert put(api, FLOW, "R1").status_code == 200
    body = copy(api, "R1", ["Lampe", "Findes_ikke", "R2", "R1"]).json()
    st = {r["element"]: r for r in body["results"]}
    assert "R1" not in st                                   # kilden selv springes over
    assert st["Lampe"]["status"] == "error" and "Løbelys" in st["Lampe"]["message"]
    assert st["Findes_ikke"]["status"] == "error" and "aktive version" in st["Findes_ikke"]["message"]
    assert st["R2"]["status"] == "ok"
    assert cfg_of(api, "Lampe") is None


def test_source_must_have_saved_config(api):
    r = copy(api, "R1", ["R2"])
    assert r.status_code == 409 and "gem" in r.json()["error"].lower()
    assert copy(api, "R1", []).status_code == 422


def test_lock_is_not_copied(api):
    cfg = {"op": "positions", "positions": [{"label": "0"}, {"label": "1"}],
           "signals": [{"id": "S1", "tag": "Bit0"}], "planes": [{"signal": "S1", "values": [0, 1]}], "display": "local",
           "anims": [{"part": "V1_greb", "type": "rotate", "src": "@pos", "params": {"angles": [-45, 45]}}],
           "lock": {"positions": [False, True], "leave": False}}
    assert put(api, cfg, "V1", pin="4711").status_code == 200
    res = copy(api, "V1", ["V2"]).json()["results"][0]
    assert res["status"] == "ok" and any("Nøglelåsen" in n for n in res["notes"])
    got = cfg_of(api, "V2")
    assert got["lock"]["positions"] == [False, False]
    assert got["anims"][0]["part"] == "V2_greb"
    assert api.get(f"/api/drawings/{api.did}/symbols/V2/config").json()["has_pin"] is False


def test_copy_is_audited(api):
    assert put(api, FLOW, "R1").status_code == 200
    copy(api, "R1", ["R2", "R3"])
    entry = api.get("/api/audit?action=symbol.copy").json()[0]
    assert entry["target"] == f"{api.did}#R1"
    assert "R2" in str(entry["detail"]) and "R3" in str(entry["detail"])


def test_list_symbols_marks_configured(api):
    assert put(api, FLOW, "R1").status_code == 200
    rows = {r["element"]: r for r in api.get(f"/api/drawings/{api.did}/symbols").json()}
    assert set(rows) == {"V1", "V2", "R1", "R2", "R3", "B1"}
    assert rows["R1"]["configured"] is True and rows["R2"]["configured"] is False
    assert rows["R2"]["type"] == "ror_vandret" and rows["R2"]["name"] == "Rør 2"


def test_map_config_pure():
    src = {"parts": {"A_x": {"pid": "x"}, "A_y": {"pid": None}}}
    tgt = {"parts": {"B_x": {"pid": "x"}}}
    cfg = {"anims": [{"part": "all", "type": "fill"}, {"part": "A_x", "type": "fill"}, {"part": "A_y", "type": "blink"}]}
    out, notes = map_config(cfg, src, tgt)
    assert [a["part"] for a in out["anims"]] == ["all", "B_x"]
    assert len(notes) == 1 and cfg["anims"][1]["part"] == "A_x"   # originalen er urørt


def test_used_ids_include_configs_and_bindings_also_for_missing_elements(api):
    """Tegn må ikke genbruge et id, der stadig har en opsætning eller binding — også når elementet er væk (v0.69.0)."""
    assert put(api, FLOW, "R1").status_code == 200
    assert api.put(f"/api/drawings/{api.did}/bindings/B1", json={"bindings": [{"tag": "Lys", "anim": "fill", "params": {}}]}).status_code == 200
    # ny version uden R1: opsætningen bevares (forsvundet element), og id'et er stadig reserveret
    svg = SVG.replace(_pipe(1, 100), "")
    assert api.post(f"/api/drawings/{api.did}/versions", json={"svg": svg, "activate": True}).status_code in (200, 201)
    ids = api.get(f"/api/drawings/{api.did}/used-ids").json()
    assert "R1" in ids and "B1" in ids
    assert "R2" not in ids
    assert api.get("/api/drawings/findes-ikke/used-ids").status_code == 404

