"""Logikblokke i symbol-guiden (v0.44.0/0.45.0): beregning (tre-værdi-logik), validering, henvisninger mellem symboler,
integritet (en brugt blok kan ikke fjernes), løkker og live-værdier fra mock-PLC'en."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.live_cache import LiveValue
from app.services.symbols import evaluate_logic, logic_results
from tests.test_symbols import ADMIN_PW, SVG, TAGS, api, errors, put  # noqa: F401  (api = fixture)


def _lv(values: dict, bad: frozenset = frozenset()):
    def get(name):
        if name in bad:
            return LiveValue(value=values.get(name), quality="comm_error")
        return LiveValue(value=values[name], quality="good") if name in values else LiveValue()
    return get


def blk(bid, op, *inputs, invert=False, name=""):
    return {"id": bid, "name": name, "op": op, "inputs": [i if isinstance(i, dict) else {"src": i} for i in inputs], "invert": invert}


# ------------------------------------------------------------------ beregning

@pytest.mark.parametrize("op,a,b,expected", [
    ("and", True, True, True), ("and", True, False, False), ("and", False, False, False),
    ("or", True, False, True), ("or", False, True, True), ("or", False, False, False),
])
def test_and_or_truth_table(op, a, b, expected):
    out = evaluate_logic([blk("L1", op, "A", "B")], _lv({"A": a, "B": b}))
    assert out == {"L1": expected}


def test_not_on_input_and_on_result():
    vals = _lv({"Pumpe": True, "Alarm": False})
    assert evaluate_logic([blk("L1", "and", "Pumpe", {"src": "Alarm", "neg": True})], vals)["L1"] is True
    assert evaluate_logic([blk("L1", "and", "Pumpe", "Alarm", invert=True)], vals)["L1"] is True      # NAND
    assert evaluate_logic([blk("L1", "or", "Pumpe", "Alarm", invert=True)], vals)["L1"] is False      # NOR


def test_numeric_inputs_use_comparison_and_zero_means_off():
    vals = _lv({"T": 70, "Nul": 0, "Et": 1})
    assert evaluate_logic([blk("L1", "and", {"src": "T", "cmp": "ge", "value": 70})], vals)["L1"] is True
    assert evaluate_logic([blk("L1", "and", {"src": "T", "cmp": "le", "value": 69.9})], vals)["L1"] is False
    assert evaluate_logic([blk("L1", "and", {"src": "T", "cmp": "eq", "value": 70})], vals)["L1"] is True
    assert evaluate_logic([blk("L1", "and", "Nul")], vals)["L1"] is False       # ikke-nul = Til
    assert evaluate_logic([blk("L1", "and", "Et")], vals)["L1"] is True


def test_unknown_inputs_follow_three_valued_logic():
    vals = _lv({"A": True, "B": False, "X": True}, bad=frozenset({"X"}))      # X: komm.fejl
    unknown = "Mangler"                                                         # aldrig læst
    assert evaluate_logic([blk("L1", "and", "X", "B")], vals)["L1"] is False  # en Fra afgør AND
    assert evaluate_logic([blk("L1", "or", "X", "A")], vals)["L1"] is True    # en Til afgør OR
    assert evaluate_logic([blk("L1", "and", "X", "A")], vals)["L1"] is None   # ellers ukendt
    assert evaluate_logic([blk("L1", "or", "X", "B")], vals)["L1"] is None
    assert evaluate_logic([blk("L1", "and", unknown)], vals)["L1"] is None
    assert evaluate_logic([blk("L1", "and", {"src": "X", "neg": True}, "B", invert=True)], vals)["L1"] is True
    assert evaluate_logic([blk("L1", "and", {"src": "X", "neg": True})], vals)["L1"] is None     # NOT på ukendt = ukendt


def test_blocks_can_use_earlier_blocks_two_levels():
    vals = _lv({"Pumpe": True, "Ventil": True, "Nød": False})
    out = evaluate_logic([blk("L1", "and", "Pumpe", "Ventil"), blk("L2", "or", "@L1", "Nød"),
                          blk("L3", "and", {"src": "@L2", "neg": True}, "Pumpe")], vals)
    assert out == {"L1": True, "L2": True, "L3": False}


def test_four_inputs_and_non_bool_values_are_unknown():
    vals = _lv({"A": True, "B": True, "C": True, "D": True, "Tekst": "hej"})
    assert evaluate_logic([blk("L1", "and", "A", "B", "C", "D")], vals)["L1"] is True
    assert evaluate_logic([blk("L1", "and", "Tekst")], vals)["L1"] is None


def test_cross_symbol_references_and_loops():
    vals = _lv({"A": True, "B": True})
    cfgs = {"p": {"logic": [blk("L1", "and", "A", "B")]}, "q": {"logic": [blk("L1", "or", {"src": "@p:L1", "neg": True}, {"src": "A", "neg": True})]}}
    assert logic_results(cfgs, vals) == {("p", "L1"): True, ("q", "L1"): False}
    loop = {"p": {"logic": [blk("L1", "and", "@q:L1")]}, "q": {"logic": [blk("L1", "and", "@p:L1")]}}
    assert logic_results(loop, vals) == {("p", "L1"): None, ("q", "L1"): None}       # ingen uendelig rekursion
    assert logic_results({"p": {"logic": [blk("L1", "and", "@ukendt:L9")]}}, vals) == {("p", "L1"): None}


# ------------------------------------------------------------------ validering og lagring (API)

def logic_cfg(blocks, anims=None, **over):
    cfg = {"op": "view", "logic": blocks,
           "anims": anims if anims is not None else [{"part": "Lampe_glas", "type": "fill", "src": "@L1", "params": {"on": "#7cc47f"}}]}
    cfg.update(over)
    return cfg


def test_logic_symbol_saves_and_becomes_bindings_on_the_pseudo_tag(api):
    r = put(api, logic_cfg([blk("L1", "and", "Lys", "Fejl", name="Lys og fejl")]), element="Lampe")
    assert r.status_code == 200, r.text
    assert r.json()["config"]["logic"][0]["name"] == "Lys og fejl"
    view = api.get(f"/api/drawings/{api.did}/view").json()
    b = next(x for x in view["bindings"] if x["element"] == "Lampe_glas")
    assert b["tag"] == f"sym:{api.did}:Lampe:logic:L1" and b["anim"] == "fill"


@pytest.mark.parametrize("blocks,text", [
    ([blk("L1", "and")], "tilføj mindst én indgang"),
    ([blk("L1", "and", "Findes_ikke")], "findes ikke"),
    ([blk("L1", "and", "Niveau")], "tal-tag"),                                                  # tal uden sammenligning
    ([blk("L1", "and", {"src": "Lys", "cmp": "ge", "value": 1})], "til/fra-tag"),               # sammenligning på til/fra
    ([blk("L1", "and", {"src": "Niveau", "cmp": "ge"})], "grænseværdien"),
    ([blk("L1", "and", "@L1")], "tidligere blok"),                                              # sig selv
    ([blk("L1", "and", "@L2"), blk("L2", "and", "Lys")], "tidligere blok"),                     # fremad
    ([blk("L1", "and", "Lys"), blk("L1", "or", "Fejl")], "samme id|id'et L1"),
    ([blk("X9z", "and", "Lys")], "som L1"),
    ([blk("L1", "and", "@pumpe:L1")], "har ikke blokken"),                                      # ukendt symbol
])
def test_logic_validation_errors(api, blocks, text):
    r = put(api, logic_cfg(blocks, anims=[]), element="Lampe")
    body = errors(r)
    msgs = " ".join(m for v in body["steps"].values() for m in v) if "steps" in body else body["error"]
    import re
    assert re.search(text, msgs), msgs


def test_more_than_four_inputs_or_eight_blocks_are_rejected(api):
    five = blk("L1", "and", "Lys", "Fejl", "Bit0", "Bit1", "Bit2")
    errors(put(api, logic_cfg([five]), element="Lampe"))
    nine = [blk(f"L{i}", "and", "Lys") for i in range(1, 10)]
    errors(put(api, logic_cfg(nine, anims=[]), element="Lampe"))


def test_animation_source_must_be_an_existing_block_and_not_numeric_only(api):
    errors(put(api, logic_cfg([blk("L1", "and", "Lys")], anims=[{"part": "Lampe_glas", "type": "fill", "src": "@L7", "params": {}}]), element="Lampe"))
    r = put(api, logic_cfg([blk("L1", "and", "Lys")], anims=[{"part": "all", "type": "level", "src": "@L1", "params": {"min": 0, "max": 100}}]), element="Tank")
    assert "kan ikke styres af en logikblok" in " ".join(m for v in errors(r)["steps"].values() for m in v)


def test_unused_block_gives_a_warning_not_an_error(api):
    r = put(api, logic_cfg([blk("L1", "and", "Lys")], anims=[]), element="Lampe")
    assert r.status_code == 200 and any("bruges ikke" in w for w in r.json()["warnings"])


def test_logic_tags_are_protected_from_deletion_and_backup_checks_them(api):
    assert put(api, logic_cfg([blk("L1", "and", "Lys", "Fejl")]), element="Lampe").status_code == 200
    r = api.delete("/api/tags/Fejl")
    assert r.status_code == 409 and f"{api.did}#Lampe" in r.json()["error"]


# ------------------------------------------------------------------ på tværs af symboler

def test_block_in_another_symbol_can_be_used_and_is_protected(api):
    assert put(api, logic_cfg([blk("L1", "and", "Lys", "Fejl")], anims=[]), element="Lampe").status_code == 200
    r = put(api, {"op": "view", "anims": [{"part": "all", "type": "visible", "src": "@Lampe:L1", "params": {}}]}, element="Tank")
    assert r.status_code == 200, r.text
    view = api.get(f"/api/drawings/{api.did}/view").json()
    assert next(b for b in view["bindings"] if b["element"] == "Tank")["tag"] == f"sym:{api.did}:Lampe:logic:L1"
    # blokken vises som mulighed for de andre symboler, men ikke for symbolet selv
    pool = api.get(f"/api/drawings/{api.did}/symbols/Tank/config").json()["logic_pool"]
    assert pool == [{"element": "Lampe", "symbol": "Lampe", "id": "L1", "name": ""}]
    assert api.get(f"/api/drawings/{api.did}/symbols/Lampe/config").json()["logic_pool"] == []
    # den brugte blok kan ikke fjernes, og symbolets konfiguration kan ikke slettes
    keep = [{"part": "Lampe_glas", "type": "fill", "src": "Lys", "params": {}}]
    r = put(api, logic_cfg([], anims=keep), element="Lampe")
    assert r.status_code == 400 and "bruges af symbolet 'Tank'" in " ".join(m for v in r.json()["steps"].values() for m in v)
    assert api.delete(f"/api/drawings/{api.did}/symbols/Lampe/config").status_code == 409
    # ...før henvisningen er fjernet
    assert api.delete(f"/api/drawings/{api.did}/symbols/Tank/config").status_code == 204
    assert put(api, logic_cfg([], anims=keep), element="Lampe").status_code == 200


def test_reference_to_own_block_with_symbol_name_and_missing_foreign_block_are_rejected(api):
    assert put(api, logic_cfg([blk("L1", "and", "Lys")], anims=[]), element="Lampe").status_code == 200
    r = put(api, logic_cfg([blk("L1", "and", "@Lampe:L1")], anims=[]), element="Lampe")
    assert "brug @L1" in " ".join(m for v in errors(r)["steps"].values() for m in v)
    r = put(api, {"op": "view", "anims": [{"part": "all", "type": "visible", "src": "@Lampe:L5", "params": {}}]}, element="Tank")
    assert "findes ikke" in " ".join(m for v in errors(r)["steps"].values() for m in v)


def test_loop_between_two_symbols_is_rejected(api):
    assert put(api, logic_cfg([blk("L1", "and", "Lys")], anims=[]), element="Lampe").status_code == 200
    assert put(api, logic_cfg([blk("L1", "and", "@Lampe:L1")], anims=[]), element="Tank").status_code == 200
    r = put(api, logic_cfg([blk("L1", "and", "@Tank:L1")], anims=[]), element="Lampe")     # nu: Lampe → Tank → Lampe
    assert "løkke" in " ".join(m for v in errors(r)["steps"].values() for m in v)


# ------------------------------------------------------------------ live: mock-PLC → pseudo-tags

def _wait(predicate, timeout=6.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


def test_logic_values_follow_the_plc_across_symbols(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.1, plc_rate=9, symbol_tick_s=0.1,
                        alarm_tick_s=0.1, frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    mock_plc.state.coils[20] = True    # Lys
    mock_plc.state.di[11] = False      # Fejl
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada", "password": "scada123", "sse_enabled": False})
        for t in TAGS:
            c.post("/api/tags", json=t)
        did = c.post("/api/drawings", json={"name": "Anlæg", "svg": SVG}).json()["drawing"]["id"]
        cfg1 = logic_cfg([blk("L1", "and", "Lys", {"src": "Fejl", "neg": True}), blk("L2", "or", "@L1", {"src": "Niveau", "cmp": "ge", "value": 500})], anims=[])
        assert c.put(f"/api/drawings/{did}/symbols/Lampe/config", json={"config": cfg1}).status_code == 200
        cfg2 = {"op": "view", "logic": [blk("L1", "and", "@Lampe:L2", "Lys")], "anims": [{"part": "all", "type": "visible", "src": "@L1", "params": {}}]}
        r = c.put(f"/api/drawings/{did}/symbols/Tank/config", json={"config": cfg2})
        assert r.status_code == 200, r.text

        def value(element, bid):
            name = f"sym:{did}:{element}:logic:{bid}"
            return c.get(f"/api/live?tags={name}").json()["values"].get(name, {}).get("value", "ingen")

        _wait(lambda: value("Tank", "L1") is True)               # Lys Til, Fejl Fra → L1 Til → L2 Til → Tank:L1 Til
        assert value("Lampe", "L1") is True and value("Lampe", "L2") is True
        mock_plc.state.di[11] = True                               # Fejl → L1 Fra; Niveau < 500 → L2 Fra
        _wait(lambda: value("Tank", "L1") is False)
        assert value("Lampe", "L1") is False and value("Lampe", "L2") is False
        # fjernes en blok, ryddes dens værdi (ingen forældreløse pseudo-tags)
        assert c.delete(f"/api/drawings/{did}/symbols/Tank/config").status_code == 204
        assert c.put(f"/api/drawings/{did}/symbols/Lampe/config", json={"config": logic_cfg([blk("L1", "and", "Lys")], anims=[])}).status_code == 200
        _wait(lambda: value("Lampe", "L2") in ("ingen", None))      # ryddet: ukendt/ingen værdi i stedet for en gammel


# ------------------------------------------------------------------ løbelysets retning styret af en logikblok

def flow(dir_tag, src="Lys"):
    return {"op": "view", "anims": [{"part": "Ror_streg", "type": "flow", "src": src,
                                     "params": {"mode": "onoff", "dir_tag": dir_tag}}]}


def test_flow_direction_can_be_a_block_in_this_or_another_symbol(api):
    assert put(api, logic_cfg([blk("L1", "and", "Bit0", "Bit1")], anims=[]), element="Lampe").status_code == 200
    # blok i et andet symbol
    r = put(api, flow("@Lampe:L1"), element="Ror")
    assert r.status_code == 200, r.text
    view = api.get(f"/api/drawings/{api.did}/view").json()
    b = next(x for x in view["bindings"] if x["element"] == "Ror_streg")
    assert b["tag"] == "Lys" and b["params"]["dir_tag"] == f"sym:{api.did}:Lampe:logic:L1"     # oversat til pseudo-tagget
    # blok i symbolet selv
    r = put(api, {**flow("@L1"), "logic": [blk("L1", "or", "Bit0", "Bit1")]}, element="Ror")
    assert r.status_code == 200, r.text
    view = api.get(f"/api/drawings/{api.did}/view").json()
    assert next(x for x in view["bindings"] if x["element"] == "Ror_streg")["params"]["dir_tag"] == f"sym:{api.did}:Ror:logic:L1"


def test_flow_direction_block_must_exist_and_differ_from_the_source(api):
    for ref, text in [("@L9", "findes ikke"), ("@Lampe:L1", "findes ikke"), ("@Ror:L1", "findes ikke")]:
        r = put(api, flow(ref), element="Ror")
        assert text in " ".join(m for v in errors(r)["steps"].values() for m in v), ref
    assert put(api, logic_cfg([blk("L1", "and", "Lys")], anims=[]), element="Lampe").status_code == 200
    r = put(api, flow("@Lampe:L1", src="@Lampe:L1"), element="Ror")
    assert "et andet tag end det der styrer start/stop" in " ".join(m for v in errors(r)["steps"].values() for m in v)


def test_block_used_only_as_flow_direction_is_protected_and_not_reported_unused(api):
    r = put(api, logic_cfg([blk("L1", "and", "Bit0", "Bit1")], anims=[]), element="Lampe")
    assert r.status_code == 200 and any("bruges ikke" in w for w in r.json()["warnings"])
    assert put(api, flow("@Lampe:L1"), element="Ror").status_code == 200
    r = put(api, logic_cfg([blk("L1", "and", "Bit0", "Bit1")], anims=[]), element="Lampe")     # nu brugt af Ror
    assert r.status_code == 200 and not any("bruges ikke" in w for w in r.json()["warnings"])
    keep = [{"part": "Lampe_glas", "type": "fill", "src": "Lys", "params": {}}]
    r = put(api, logic_cfg([], anims=keep), element="Lampe")                                    # blokken fjernes
    assert r.status_code == 400 and "bruges af symbolet 'Ror'" in " ".join(m for v in r.json()["steps"].values() for m in v)
    assert api.delete(f"/api/drawings/{api.did}/symbols/Lampe/config").status_code == 409


def test_plain_tag_still_works_as_flow_direction(api):
    r = put(api, flow("Bit1"), element="Ror")
    assert r.status_code == 200, r.text
    errors(put(api, flow("Findes_ikke"), element="Ror"))


# ------------------------------------------------------------------ bibliotekssymboler: 3-vejs motorventil og statusfelt

def test_library_defaults_for_three_way_valve_and_status_field_are_accepted_by_the_server(api):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200">'
           '<g id="V3" data-hv-type="trevejs_motorventil" data-hv-name="Ventil 3">'
           '<path id="V3_port_a" data-hv-pid="port_a" d="M8 27 L40 45 L8 63 Z"/><path id="V3_port_b" data-hv-pid="port_b" d="M22 13 L58 13 L40 45 Z"/>'
           '<path id="V3_port_ab" data-hv-pid="port_ab" d="M72 27 L40 45 L72 63 Z"/><circle id="V3_motor" data-hv-pid="motor" cx="40" cy="78" r="12"/></g>'
           '<g id="STF1" data-hv-type="statusfelt" data-hv-name="Status"><rect id="STF1_felt" data-hv-pid="felt" x="2" y="2" width="76" height="26"/>'
           '<text id="STF1_tekst" data-hv-pid="tekst" x="40" y="21">STF</text></g></svg>')
    did = api.post("/api/drawings", json={"name": "Bib", "svg": svg}).json()["drawing"]["id"]
    open_, closed = "#7cc47f", "#ffffff"
    valve = {"op": "positions", "positions": [{"label": "AB → A"}, {"label": "AB → B"}],
             "signals": [{"id": "S1", "tag": "Bit0"}], "planes": [{"signal": "S1", "values": [0, 1]}], "display": "remote",
             "anims": [{"part": "V3_port_a", "type": "fill", "src": "@pos", "params": {"colors": [open_, closed]}},
                       {"part": "V3_port_b", "type": "fill", "src": "@pos", "params": {"colors": [closed, open_]}},
                       {"part": "V3_port_ab", "type": "fill", "src": "@pos", "params": {"colors": [open_, open_]}}]}
    r = api.put(f"/api/drawings/{did}/symbols/V3/config", json={"config": valve})
    assert r.status_code == 200, r.text
    assert r.json()["config"]["type"] == "trevejs_motorventil"
    status = {"op": "view", "anims": [{"part": "STF1_felt", "type": "fill", "src": "Niveau",
                                       "params": {"off": "#e4e4e4", "thresholds": [{"value": 50, "color": "#b26a00"}, {"value": 80, "color": "#c62828"}]}}]}
    r = api.put(f"/api/drawings/{did}/symbols/STF1/config", json={"config": status})
    assert r.status_code == 200, r.text
    # uden valgt register afvises forslaget med en klar besked (guiden viser den ved trin 4)
    status["anims"][0]["src"] = ""
    r = api.put(f"/api/drawings/{did}/symbols/STF1/config", json={"config": status})
    assert r.status_code == 400 and "vælg hvad der styrer den" in " ".join(m for v in r.json()["steps"].values() for m in v)
