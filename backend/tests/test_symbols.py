"""Symbolstandard fase 1: konfiguration, validering (prototypens regler), PIN som hash, tag-brug, backup."""

import json
import re
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200">'
       '<g id="V1" data-hv-type="omskifter3" data-hv-name="Vælger V1">'
       '<circle id="V1_skive" data-hv-pid="skive" cx="20" cy="20" r="15"/>'
       '<rect id="V1_greb" data-hv-pid="greb" x="18" y="5" width="4" height="15"/>'
       '<text id="V1_tekst" data-hv-pid="tekst" x="0" y="45">0</text></g>'
       '<g id="Ror"><path id="Ror_streg" d="M0 100 H90" stroke="#555" stroke-width="10"/></g>'
       '<g id="Lampe"><circle id="Lampe_glas" cx="200" cy="20" r="10"/></g>'
       '<rect id="Tank" x="100" y="100" width="40" height="80"/></svg>')
TAGS = [
    {"name": "Bit0", "source": "plc1:coil:10", "writable": True},
    {"name": "Bit1", "source": "plc1:coil:11", "writable": True},
    {"name": "Bit2", "source": "plc1:coil:12", "writable": True},
    {"name": "Bit0_fb", "source": "plc1:di:10"},
    {"name": "Mode", "source": "plc1:hr:30", "writable": True, "min": 0, "max": 3},
    {"name": "Mode_fb", "source": "plc1:hr:32"},
    {"name": "Kommando", "source": "plc1:hr:33", "writable": True},
    {"name": "Niveau", "source": "plc1:hr:31"},
    {"name": "Lys", "source": "plc1:coil:20"},
    {"name": "Setpunkt", "source": "plc1:hr:34", "writable": True, "min": 0, "max": 100},
    {"name": "Fejl", "source": "plc1:di:11"},
]


def _wait(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


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
        did = c.post("/api/drawings", json={"name": "Anlæg", "svg": SVG}).json()["drawing"]["id"]
        c.did = did
        yield c


def dec_bin(**over):
    """7-trins vælger, dec → bin: 3 planer og 3 signaler (prototypens eksempel)."""
    cfg = {
        "op": "positions",
        "positions": [{"label": str(j + 1)} for j in range(7)],
        "signals": [{"id": f"S{b + 1}", "tag": f"Bit{b}", "fb": "Bit0_fb" if b == 0 else ""} for b in range(3)],
        "planes": [{"signal": f"S{b + 1}", "values": [((j + 1) >> b) & 1 for j in range(7)]} for b in range(3)],
        "display": "local", "validate_s": 5, "alarm": "high",
        "anims": [{"part": "V1_greb", "type": "rotate", "src": "@pos",
                   "params": {"angles": [-90 + 30 * j for j in range(7)]}}],
    }
    cfg.update(over)
    return cfg


def put(api, cfg, element="V1", pin=None):
    body = {"config": cfg}
    if pin is not None:
        body["pin"] = pin
    return api.put(f"/api/drawings/{api.did}/symbols/{element}/config", json=body)


def errors(r):
    assert r.status_code == 400, r.text
    return r.json()


# ------------------------------------------------------------------ gyldige konfigurationer

def test_dec_bin_selector_saves_and_reads_back(api):
    r = put(api, dec_bin())
    assert r.status_code == 200, r.text
    cfg = r.json()["config"]
    assert cfg["type"] == "omskifter3"                 # fra data-hv-type, ikke fra klienten
    assert [p["values"] for p in cfg["planes"]][0] == [1, 0, 1, 0, 1, 0, 1]
    got = api.get(f"/api/drawings/{api.did}/symbols/V1/config").json()
    assert got["config"] == cfg and got["has_pin"] is False and got["orphaned"] is False
    assert got["symbol"]["parts"]["V1_greb"]["pid"] == "greb"
    assert got["symbol"]["parts"]["V1_tekst"]["text"] == "0" and "text" not in got["symbol"]["parts"]["V1_greb"]
    assert api.get("/api/audit?action=symbol.config").json()[0]["target"] == f"{api.did}#V1"


def test_register_template_and_pulse_signal_with_rest(api):
    cfg = dec_bin(signals=[{"id": "S1", "tag": "Mode", "fb": "Mode_fb"},
                           {"id": "S2", "tag": "Kommando", "write": "pulse", "ms": 300, "rest": 0}],
                  planes=[{"signal": "S1", "values": [0, 1, 2]}, {"signal": "S2", "values": [11, 12, 13]}],
                  positions=[{"label": "Hand"}, {"label": "0"}, {"label": "Auto"}],
                  anims=[{"part": "V1_greb", "type": "rotate", "src": "@pos", "params": {"angles": [-45, 0, 45]}}])
    r = put(api, cfg)
    assert r.status_code == 200, r.text


def test_pulse_entry_and_view_symbols(api):
    assert put(api, {"op": "pulse", "signals": [{"id": "S1", "tag": "Bit0"}], "pulse_ms": 500,
                     "anims": [{"part": "Lampe_glas", "type": "fill", "src": "Bit0", "params": {"on": "#7cc47f"}}]},
               element="Lampe").status_code == 200
    assert put(api, {"op": "entry", "signals": [{"id": "S1", "tag": "Setpunkt"}]}, element="Lampe").status_code == 200
    r = put(api, {"op": "view", "anims": [{"part": "all", "type": "level", "src": "Niveau", "params": {"min": 0, "max": 100}}]},
            element="Tank")
    assert r.status_code == 200, r.text
    r = put(api, {"op": "view", "anims": [{"part": "all", "type": "flow", "src": "Lys",
                                           "params": {"dir_tag": "Bit1", "arm": "", "mode": "onoff"}}]}, element="Ror")
    assert r.status_code == 200, r.text


def test_warnings_do_not_block(api):
    cfg = dec_bin()
    cfg["signals"].append({"id": "S4", "tag": "Mode"})
    cfg["planes"][2]["values"][6] = None                 # røres ikke i position 7 — men stadig entydig
    r = put(api, cfg)
    assert r.status_code == 200, r.text
    w = " ".join(r.json()["warnings"])
    assert "S4 (Mode) bruges ikke" in w and 'røres ikke i "7"' in w


# ------------------------------------------------------------------ fejl pr. trin

@pytest.mark.parametrize("change, step, text", [
    (lambda c: c["signals"][0].update(tag="Findes_ikke"), "2", "findes ikke"),
    (lambda c: c["signals"][0].update(tag="Lys"), "2", "ikke skrivbart"),
    (lambda c: c["signals"][1].update(tag="Bit0"), "2", "samme tag Bit0"),
    (lambda c: c["signals"][0].update(fb="Mode_fb"), "2", "anden type"),
    (lambda c: c.update(fault="Mode"), "2", "Fejl/låst-tagget skal være et til/fra-tag"),
    (lambda c: c["positions"][1].update(label="1"), "3", "samme navn"),
    (lambda c: c["positions"][1].update(label=" "), "3", "skal have et navn"),
    (lambda c: c["planes"][1].update(signal="S1"), "3", "ét signal pr. plan"),
    (lambda c: [p["values"].__setitem__(1, p["values"][0]) for p in c["planes"]], "3", "ens kontaktmønster"),
    (lambda c: c["planes"][0]["values"].__setitem__(0, 2), "3", "Til (1), Fra (0)"),
    (lambda c: c.update(validate_s=0), "4", "Valideringstid"),
    (lambda c: c.update(positions=[{"label": "A"}]), "3", "2–8 positioner"),
])
def test_validation_errors_by_step(api, change, step, text):
    cfg = dec_bin()
    change(cfg)
    body = errors(put(api, cfg))
    assert any(text in m for m in body["steps"][step]), body
    assert body["error"].startswith("Symbolet kan ikke gemmes") and "Trin" in body["error"]


def test_register_values_checked_against_tag_range_and_integers(api):
    cfg = dec_bin(signals=[{"id": "S1", "tag": "Mode"}], positions=[{"label": "A"}, {"label": "B"}, {"label": "C"}],
                  planes=[{"signal": "S1", "values": [0, 4, 1.5]}], anims=[])
    steps = errors(put(api, cfg))["steps"]["3"]
    assert any("4 er uden for 0–3 for Mode" in m for m in steps)
    assert any('"1.5" er ikke et heltal' in m for m in steps)


def test_full_16_bit_range_when_tag_has_no_min_max(api):
    """Kommando har ingen min/max → hele uint-området (0–65535), ikke et eksempels 0–3."""
    cfg = dec_bin(signals=[{"id": "S1", "tag": "Kommando"}], positions=[{"label": "A"}, {"label": "B"}],
                  planes=[{"signal": "S1", "values": [40, 65535]}], anims=[])
    assert put(api, cfg).status_code == 200
    cfg["planes"][0]["values"][1] = 65536
    assert any("uden for 0–65535" in m for m in errors(put(api, cfg))["steps"]["3"])


@pytest.mark.parametrize("signal, text", [
    ({"id": "S2", "tag": "Kommando", "write": "pulse", "ms": 300, "rest": None}, "hvileværdien skal sættes"),
    ({"id": "S2", "tag": "Kommando", "write": "pulse", "ms": 300, "rest": 12}, "også en positions værdi"),
    ({"id": "S2", "tag": "Kommando", "write": "pulse", "ms": 50, "rest": 0}, "pulslængde"),
])
def test_pulse_signal_rules(api, signal, text):
    cfg = dec_bin(signals=[{"id": "S1", "tag": "Mode"}, signal], positions=[{"label": "A"}, {"label": "B"}],
                  planes=[{"signal": "S1", "values": [0, 1]}, {"signal": "S2", "values": [11, 12]}], anims=[])
    assert any(text in m for m in errors(put(api, cfg))["steps"]["5"])


def test_only_pulse_planes_cannot_be_read(api):
    cfg = dec_bin(signals=[{"id": "S1", "tag": "Kommando", "write": "pulse", "ms": 300, "rest": 0}],
                  positions=[{"label": "A"}, {"label": "B"}], planes=[{"signal": "S1", "values": [1, 2]}], anims=[])
    assert any("ikke puls" in m for m in errors(put(api, cfg))["steps"]["5"])


@pytest.mark.parametrize("element, anim, text", [
    ("V1", {"part": "V1_skive", "type": "level", "src": "Niveau"}, "Niveau kræver en rektangel-del"),
    ("V1", {"part": "V1_greb", "type": "text", "src": "Niveau"}, "Værdi kræver en tekst-del"),
    ("Lampe", {"part": "Lampe_glas", "type": "flow", "src": "Lys"}, "Løbelys kræver streger"),
    ("V1", {"part": "V1_findes_ikke", "type": "fill", "src": "Lys"}, "findes ikke i symbolet"),
    ("V1", {"part": "V1_greb", "type": "fill", "src": "@pos", "params": {"colors": ["#fff"]}}, "en værdi pr. position"),
    ("V1", {"part": "V1_greb", "type": "opacity", "src": "@pos"}, "kan ikke styres af positionen"),
    ("V1", {"part": "V1_tekst", "type": "level", "src": "Niveau"}, "rektangel-del"),
    ("V1", {"part": "V1_greb", "type": "blink", "src": "Lys", "params": {"speed": "lynhurtig"}}, "speed"),
    ("Ror", {"part": "all", "type": "flow", "src": "Lys", "params": {"base": "#111", "light": "#111"}}, "forskellige"),
    ("Ror", {"part": "all", "type": "flow", "src": "Lys", "params": {"dir_tag": "Lys"}}, "et andet tag"),
    ("Ror", {"part": "all", "type": "flow", "src": "Lys", "params": {"dir_tag": "Væk"}}, "'Væk' findes ikke"),
])
def test_animation_rules(api, element, anim, text):
    if element == "V1":
        cfg = dec_bin(anims=[anim])
    else:
        cfg = {"op": "view", "anims": [anim]}
    body = errors(put(api, cfg, element=element))
    assert any(text in m for m in body["steps"]["4"]), body


def test_pos_source_requires_positions_and_view_requires_animation(api):
    body = errors(put(api, {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "@pos"}]}, element="Lampe"))
    assert any("ingen positioner" in m for m in body["steps"]["4"])
    body = errors(put(api, {"op": "view", "anims": []}, element="Lampe"))
    assert any("mindst én animation" in m for m in body["steps"]["4"])


def test_pulse_needs_bool_tag_and_entry_needs_number(api):
    assert any("til/fra-tag" in m for m in errors(put(api, {"op": "pulse", "signals": [{"id": "S1", "tag": "Setpunkt"}]},
                                                       element="Lampe"))["steps"]["2"])
    assert any("tal-tag" in m for m in errors(put(api, {"op": "entry", "signals": [{"id": "S1", "tag": "Bit0"}]},
                                                    element="Lampe"))["steps"]["2"])


def test_unknown_fields_and_missing_element(api):
    r = put(api, dec_bin(hemmelig=1))
    assert r.status_code == 400 and "Ugyldig symbol-konfiguration" in r.json()["error"]
    r = put(api, dec_bin(), element="Findes_ikke")
    assert r.status_code == 404 and "findes ikke" in r.json()["error"]


# ------------------------------------------------------------------ nøglelås (kode kun som hash)

def test_locked_positions_need_pin_and_pin_never_leaves_server(api):
    cfg = dec_bin(lock={"positions": [False] * 6 + [True], "leave": False})
    assert any("4 cifre" in m for m in errors(put(api, cfg))["steps"]["5"])
    assert put(api, cfg, pin="12a4").status_code == 400
    r = put(api, cfg, pin="4711")
    assert r.status_code == 200 and r.json()["has_pin"] is True
    got = api.get(f"/api/drawings/{api.did}/symbols/V1/config")
    assert got.json()["has_pin"] is True
    for text in (r.text, got.text, json.dumps(api.get("/api/audit?limit=20").json()), json.dumps(api.get("/api/backup").json())):
        assert not re.search(r"(?<![0-9])4711(?![0-9])", text) and "scrypt$" not in text   # (ikke del af et tidsstempel)
    # Uden ny kode bevares den gamle ved næste gem
    assert put(api, cfg).status_code == 200


# ------------------------------------------------------------------ tags, adgang, sletning, backup

def test_tag_used_by_symbol_cannot_be_deleted(api):
    assert put(api, dec_bin()).status_code == 200
    r = api.delete("/api/tags/Bit2")
    assert r.status_code == 409 and f"{api.did}#V1" in r.json()["error"]
    assert api.delete(f"/api/drawings/{api.did}/symbols/V1/config").status_code == 204
    assert api.delete("/api/tags/Bit2").status_code == 204


def test_backup_roundtrip_keeps_configs_but_not_pins(api):
    assert put(api, dec_bin(lock={"positions": [True] + [False] * 6, "leave": True}), pin="1234").status_code == 200
    backup = api.get("/api/backup").json()
    assert [c["element"] for c in backup["symbol_config"]] == ["V1"]
    assert "symbol_pins" not in backup and "symbol_state" not in backup
    r = api.post("/api/backup/restore", json=backup)
    assert r.status_code == 200, r.text
    got = api.get(f"/api/drawings/{api.did}/symbols/V1/config").json()
    assert got["config"]["planes"] == backup["symbol_config"][0]["config"]["planes"]
    assert got["has_pin"] is False                      # koden skal sættes igen efter restore
    assert any("4 cifre" in w for w in got["warnings"])  # og guiden siger det


def test_backup_with_unknown_tag_in_symbol_config_is_rejected(api):
    assert put(api, dec_bin()).status_code == 200
    backup = api.get("/api/backup").json()
    backup["symbol_config"][0]["config"]["signals"][0]["tag"] = "Fremmed"
    r = api.post("/api/backup/restore", json=backup)
    assert r.status_code == 400 and "Fremmed" in r.json()["error"]


def test_deleting_drawing_removes_symbol_configs(api):
    assert put(api, dec_bin()).status_code == 200
    assert api.delete(f"/api/drawings/{api.did}").status_code == 204
    assert api.delete("/api/tags/Bit0").status_code == 204    # ingen symbol bruger det længere


def test_view_contains_symbol_bindings_and_summary(api):
    cfg = dec_bin(lock={"positions": [False] * 6 + [True], "leave": False},
                  anims=[{"part": "V1_greb", "type": "rotate", "src": "@pos", "params": {"angles": [0, 10, 20, 30, 40, 50, 60]}},
                         {"part": "all", "type": "blink", "src": "Lys", "params": {"speed": "slow"}, "only": [True] * 6 + [False]},
                         {"part": "V1_tekst", "type": "text", "src": "@pos"},
                         {"part": "V1_findes_ikke_mere", "type": "fill", "src": "Lys"}])
    # sidste animation peger på en del der ikke findes → afvises ved gem; gem uden den
    assert put(api, cfg, pin="1234").status_code == 400
    cfg["anims"].pop()
    assert put(api, cfg, pin="1234").status_code == 200
    view = api.get(f"/api/drawings/{api.did}/view").json()
    sym = [b for b in view["bindings"] if b["source"] == "symbol"]
    pos = f"sym:{api.did}:V1:pos"
    assert [(b["element"], b["anim"], b["tag"]) for b in sym] == [
        ("V1_greb", "rotate", pos), ("V1", "blink", "Lys"), ("V1_tekst", "text", pos)]
    assert sym[0]["params"]["pos"] is True and sym[0]["params"]["angles"][6] == 60
    assert sym[1]["params"]["only"][6] is False and sym[1]["params"]["pos_tag"] == pos
    assert sym[2]["params"]["labels"] == [str(j + 1) for j in range(7)]
    summary = view["symbol_config"]["V1"]
    assert summary["op"] == "positions" and summary["labels"][0] == "1" and summary["has_pin"] is True
    assert summary["lock_positions"][6] is True and summary["pseudo"]["state"] == f"sym:{api.did}:V1:state"
    assert "1234" not in str(view) and "scrypt" not in str(view)


def test_flicker_animation_on_flame(api):
    """Blafrer (v0.69.0): til/fra-tag eller ≥ for tal; farven valideres; bindingen får animationen "flicker"."""
    ok = put(api, {"op": "view", "anims": [{"part": "Lampe_glas", "type": "flicker", "src": "Lys",
                                            "params": {"palette": ["#ff0000", "#ff8c1a", "#ffff00"]}}]}, element="Lampe")
    assert ok.status_code == 200, ok.text
    view = api.get(f"/api/drawings/{api.did}/view").json()
    b = next(x for x in view["bindings"] if x.get("symbol") == "Lampe")
    assert b["anim"] == "flicker" and b["params"]["palette"] == ["#ff0000", "#ff8c1a", "#ffff00"] and b["tag"] == "Lys"
    # gemt med v0.69.0 (én farve) er stadig gyldigt; uden palette får den standardfarverne
    old = put(api, {"op": "view", "anims": [{"part": "Lampe_glas", "type": "flicker", "src": "Lys", "params": {"color": "#ff8c1a"}}]},
              element="Lampe")
    assert old.status_code == 200, old.text
    assert old.json()["config"]["anims"][0]["params"]["palette"] == ["#ff8c1a", "#ff8c1a", "#ffd21a"]   # den gamle farve først
    none = put(api, {"op": "view", "anims": [{"part": "Lampe_glas", "type": "flicker", "src": "Lys", "params": {}}]}, element="Lampe")
    assert none.json()["config"]["anims"][0]["params"]["palette"] == ["#ff3b00", "#ff8c1a", "#ffd21a"]
    for bad in ([], ["#000000"] * 4):
        body = errors(put(api, {"op": "view", "anims": [{"part": "Lampe_glas", "type": "flicker", "src": "Lys", "params": {"palette": bad}}]},
                          element="Lampe"))
        assert any("palette" in m for m in body["steps"]["4"]), body
    assert put(api, {"op": "view", "anims": [{"part": "all", "type": "flicker", "src": "Niveau", "params": {"at_least": 50}}]},
               element="Tank").status_code == 200
    body = errors(put(api, {"op": "view", "anims": [{"part": "Lampe_glas", "type": "flicker", "src": "Lys", "params": {"color": "orange-ish"}}]},
                      element="Lampe"))
    assert any("color" in m for m in body["steps"]["4"]), body


def test_always_on_source(api):
    """Kilden "Altid til" (@on, v0.71.0): ingen tag; bindingen får tagget "@on", der ikke er et rigtigt tag."""
    r = put(api, {"op": "view", "anims": [{"part": "Lampe_glas", "type": "flicker", "src": "@on", "params": {}},
                                          {"part": "Lampe_glas", "type": "blink", "src": "@on", "params": {}}]}, element="Lampe")
    assert r.status_code == 200, r.text
    view = api.get(f"/api/drawings/{api.did}/view").json()
    on = [b for b in view["bindings"] if b.get("symbol") == "Lampe"]
    assert {b["tag"] for b in on} == {"@on"}
    assert "@on" not in view["tags"]          # ikke et tag: ingen metadata, ingen live-data
    r = put(api, {"op": "view", "anims": [{"part": "all", "type": "flow", "src": "@on", "params": {}}]}, element="Ror")
    assert r.status_code == 200, r.text
    for anim in ({"part": "all", "type": "level", "src": "@on", "params": {}}, {"part": "all", "type": "text", "src": "@on", "params": {}}):
        body = errors(put(api, {"op": "view", "anims": [anim]}, element="Tank"))
        assert any("Altid til" in m for m in body["steps"]["4"]), body


def test_active_passive_animations(api):
    """Aktiv/passiv (v0.72.0): to løbelys på samme rør med hver sit tag og sæt farver + en standard med "altid til"."""
    anims = [
        {"part": "all", "type": "flow", "src": "Bit0", "when": True, "params": {"light": "#ff0000"}},
        {"part": "all", "type": "flow", "src": "Bit1", "when": True, "params": {"light": "#00ff00"}},
        {"part": "all", "type": "flow", "src": "@on", "params": {"light": "#8fc8ea"}},
    ]
    r = put(api, {"op": "view", "anims": anims}, element="Ror")
    assert r.status_code == 200, r.text
    assert [a["when"] for a in r.json()["config"]["anims"]] == [True, True, False]
    view = api.get(f"/api/drawings/{api.did}/view").json()
    rb = [b for b in view["bindings"] if b.get("symbol") == "Ror"]
    assert [(b["tag"], b["params"].get("when", False)) for b in rb] == [("Bit0", True), ("Bit1", True), ("@on", False)]
    assert [b["position"] for b in rb] == sorted(b["position"] for b in rb)   # rækkefølgen (prioriteten) bevares
    body = errors(put(api, {"op": "view", "anims": [{"part": "all", "type": "level", "src": "Niveau", "when": True, "params": {}}]},
                      element="Tank"))
    assert any("aktiv/passiv" in m for m in body["steps"]["4"]), body



def test_value_animation_expression_and_unit(api):
    """Værdi-animationen i guiden har beregning og "vis enhed" som på siden Bindinger (v0.73.0)."""
    anim = {"part": "V1_tekst", "type": "text", "src": "Niveau", "params": {"expression": "x / 10", "decimals": 1, "show_unit": False, "suffix": " bar"}}
    r = put(api, dec_bin(anims=[anim]))
    assert r.status_code == 200, r.text
    p = r.json()["config"]["anims"][0]["params"]
    assert (p["expression"], p["show_unit"], p["decimals"], p["suffix"]) == ("x / 10", False, 1, " bar")
    body = errors(put(api, dec_bin(anims=[{**anim, "params": {"expression": "x / (2"}}])))
    assert any("beregningen er ugyldig" in m for m in body["steps"]["4"]), body


def test_alarm_source(api):
    """Kilden "alarm på et tag" (v0.74.0): @alarm:active|unack:<tag> → bindingens tag alarm:<tag>:<art>."""
    assert api.patch("/api/tags/Fejl", json={"alarm_on": "true"}).status_code == 200
    r = put(api, {"op": "view", "anims": [{"part": "Lampe_glas", "type": "blink", "src": "@alarm:unack:Fejl", "params": {}},
                                          {"part": "Lampe_glas", "type": "fill", "src": "@alarm:active:Fejl", "params": {}}]}, element="Lampe")
    assert r.status_code == 200, r.text
    assert r.json()["warnings"] == [] or all("ingen alarm" not in w for w in r.json()["warnings"])
    view = api.get(f"/api/drawings/{api.did}/view").json()
    tags = sorted(b["tag"] for b in view["bindings"] if b.get("symbol") == "Lampe")
    assert tags == ["alarm:Fejl:active", "alarm:Fejl:unack"]
    # tagget bag alarmen er i brug af symbolet: kan ikke slettes
    assert api.delete("/api/tags/Fejl").status_code == 409
    # tag uden alarm: advarsel, ikke fejl; ugyldig kilde og forkerte typer: fejl
    r = put(api, {"op": "view", "anims": [{"part": "Lampe_glas", "type": "blink", "src": "@alarm:active:Lys", "params": {}}]}, element="Lampe")
    assert r.status_code == 200 and any("ingen alarm" in w for w in r.json()["warnings"]), r.text
    for src, typ, text in (("@alarm:bogus:Fejl", "blink", "ugyldig alarmkilde"), ("@alarm:active:Findes_ikke", "blink", "findes ikke"),
                           ("@alarm:active:Fejl", "level", "kan ikke styres af en alarm")):
        body = errors(put(api, {"op": "view", "anims": [{"part": "all", "type": typ, "src": src, "params": {}}]}, element="Tank"))
        assert any(text in m for m in body["steps"]["4"]), (src, body)


def test_alarm_engine_publishes_pseudo_tags(api):
    """Alarmmotoren udgiver alarm:<tag>:active/unack for tags med alarmopsætning (v0.74.0)."""
    assert api.patch("/api/tags/Fejl", json={"alarm_on": "true"}).status_code == 200
    svc = api.app.state.alarm_service
    cache = api.app.state.manager.cache if hasattr(api.app.state, "manager") else svc.manager.cache
    svc.publish()
    assert cache.get("alarm:Fejl:active").value is False and cache.get("alarm:Fejl:unack").value is False
    svc.state["tag:Fejl:state"] = {"key": "tag:Fejl:state", "tag": "Fejl", "plc": "plc1", "kind": "state", "level": "ON", "priority": "high",
                                   "state": "active_unack", "raised_at": 0, "value": True, "message": "", "acked_by": None, "acked_at": None}
    svc.publish()
    assert cache.get("alarm:Fejl:active").value is True and cache.get("alarm:Fejl:unack").value is True
    svc.state["tag:Fejl:state"]["state"] = "rtn_unack"
    svc.publish()
    assert cache.get("alarm:Fejl:active").value is False and cache.get("alarm:Fejl:unack").value is True
    svc.state.clear()
    assert api.patch("/api/tags/Fejl", json={"alarm_on": None}).status_code == 200
    svc.publish()
    assert cache.get("alarm:Fejl:active").value is None   # ingen alarm mere: fjernet fra cachen


def test_coil_allowed_on_numeric_animations(api):
    """Et coil/til-fra-tag (Fra = 0, Til = 100) kan styre Niveau, Gennemsigtighed og Størrelse."""
    for typ in ("opacity", "scale"):
        r = put(api, {"op": "view", "anims": [{"part": "V1_greb", "type": typ, "src": "Lys", "params": {"min": 0, "max": 100}}]})
        assert r.status_code == 200, (typ, r.text)


def test_scale_animation_numeric_only(api):
    """Størrelse (v0.85.0): kun et tal-tag; procenterne skal være positive."""
    base = {"op": "view", "anims": []}
    ok = put(api, {**base, "anims": [{"part": "V1_greb", "type": "scale", "src": "Niveau", "params": {"min": 0, "max": 100, "size_min": 50, "size_max": 200}}]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["config"]["anims"][0]["params"]["size_max"] == 200
    for src, why in [("@on", "kan ikke styres af"), ("@pos", "ingen positioner")]:
        r = put(api, {**base, "anims": [{"part": "V1_greb", "type": "scale", "src": src, "params": {}}]})
        assert r.status_code == 400 and why in r.text, (src, r.text)
    r = put(api, {**base, "anims": [{"part": "V1_greb", "type": "scale", "src": "Niveau", "params": {"size_min": 0}}]})
    assert r.status_code == 400


def test_rotate_speed(api):
    """Hastighed på Drej (v0.97.0): 0-10 s eller ingen (som før)."""
    for glide, code in [(0, 200), (2.5, 200), (None, 200), (11, 400), (-1, 400)]:
        params = {"angles": [-90 + 30 * j for j in range(7)]} | ({"glide_s": glide} if glide is not None else {})
        r = put(api, dec_bin(anims=[{"part": "V1_greb", "type": "rotate", "src": "@pos", "params": params}]))
        assert r.status_code == code, (glide, r.text)
        if code == 200:
            assert r.json()["config"]["anims"][0]["params"]["glide_s"] == glide



def test_click_step_mode_is_stored_for_positions_and_shown_in_the_view(api):
    """v1.11.0: "step" = tryk venstre/højre side af symbolet for at skifte position. Standard er dialog."""
    r = put(api, dec_bin())
    assert r.status_code == 200 and r.json()["config"]["click"] == "dialog"
    r = put(api, dec_bin(click="step"))
    assert r.status_code == 200 and r.json()["config"]["click"] == "step"
    assert api.get(f"/api/drawings/{api.did}/view").json()["symbol_config"]["V1"]["click"] == "step"
    assert api.get(f"/api/drawings/{api.did}/symbols/V1/config").json()["config"]["click"] == "step"
    # ugyldig værdi afvises; og for symboler uden positioner nulstilles den (har ingen betydning)
    assert put(api, dec_bin(click="swipe")).status_code == 400
    r = put(api, {"op": "view", "click": "step", "anims": [{"part": "V1_greb", "type": "fill", "src": "Bit0", "params": {}}]})
    assert r.status_code == 200 and r.json()["config"]["click"] == "dialog"
    # kopieret opsætning bevarer valget
    put(api, dec_bin(click="step"))
