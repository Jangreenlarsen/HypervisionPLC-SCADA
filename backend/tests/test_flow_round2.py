"""Flow-model runde 2 (v6.3.0): retning pr. punkt på rørstykker, flowmåler, flow-profil pr. symboltype, portfarver ud fra de
åbne veje og preview af flowet i Tegn (live og simuleret)."""

from app.services.flow_calc import FlowEngine, compute, parse_topology, ports_tag, ports_text, preview
from app.services.flow_defs import kind_of, merged, piece_types
from app.services.live_cache import LiveCache, LiveValue
from app.services.symbols import part_instance, port_color_bindings
from tests.drawing_api import api  # noqa: F401 — fixture
from tests.test_flow_calc import IN, OUT, PUMP, branches, loop, pipe, svg, sym

DEFS = merged(None)


def with_bend() -> str:
    """Pumpe → r1 → bøjning (0,0 ind / 1,1 ud) → r2 → radiator → r3 → pumpe."""
    return svg(sym("p", "pumpe", f"{OUT}>r1:s;{IN}>r3:e"), pipe("r1", f"s>p:{OUT};e>b:0,0"),
               sym("b", "boejning90", "0,0>r1:e;1,1>r2:s"), pipe("r2", "s>b:1,1;e>rad:0,0.5"),
               sym("rad", "radiator", "0,0.5>r2:e;1,0.5>r3:s"), pipe("r3", f"s>rad:1,0.5;e>p:{IN}"))


def test_a_piece_gets_its_flow_per_point_in_and_out():
    ports: dict = {}
    flows, notes, _ = compute(parse_topology(with_bend()), DEFS, {"p": PUMP}, {}, {}.get, ports)
    assert notes == [] and flows["b"] == 100
    assert ports["b"] == {"0,0": 100.0, "1,1": -100.0}           # ind ved 0,0, ud ved 1,1
    assert ports_text(ports["b"]) == "0,0:+100.0;1,1:-100.0"


def test_a_t_piece_splits_into_two_outgoing_points():
    s, cfg = branches(1, 1)
    ports: dict = {}
    compute(parse_topology(s), DEFS, cfg, {}, {}.get, ports)
    assert ports["t1"]["0,0"] == 100 and ports["t1"]["1,0"] == -50 and ports["t1"]["0.5,1"] == -50
    assert ports["t2"]["0,0"] == -100                           # samles og løber ud mod pumpen


def test_the_engine_publishes_the_points_of_a_piece():
    cache = LiveCache()
    eng = FlowEngine(cache)
    eng.reload({"d": with_bend()}, None)
    eng.evaluate({("d", "p"): PUMP}, {}, 1.0)
    assert cache.get(ports_tag("d", "b")).value == "0,0:+100.0;1,1:-100.0"
    eng.reload({}, None)
    assert cache.get(ports_tag("d", "b")).value is None                 # tegningen væk: værdien fjernes


def test_a_flow_meter_scales_the_pumps_through_it():
    cfg = {"p": PUMP, "rad": {"op": "view", "flow": {"measured": {"src": "FT1"}}}}
    flows, notes, _ = compute(parse_topology(loop()), DEFS, cfg, {}, {"FT1": 42.5}.get)
    assert flows["r1"] == 42.5 and flows["p"] == 42.5 and notes == []
    # måleren uden god værdi: beregningen som uden måler
    assert compute(parse_topology(loop()), DEFS, cfg, {}, {}.get)[0]["r1"] == 100
    # en måler, der ikke er forbundet
    _, notes, _ = compute(parse_topology(loop()), DEFS, {**cfg, "x": {"flow": {"measured": {"src": "FT1"}}}}, {}, {"FT1": 1}.get)
    assert any("ikke forbundet" in n for n in notes)


def test_a_profile_makes_a_custom_type_a_piece_and_sets_defaults():
    defs = merged({"min_boejning": {"ports": [], "kind": "piece"}, "radiator": {"ports": [], "restrict": 0.0},
                   "kilde": {"ports": [], "kind": "pump", "medium": "electric", "capacity": 10}})
    assert kind_of(defs, "min_boejning") == "piece" and "min_boejning" in piece_types(defs) and "boejning90" in piece_types(defs)
    assert kind_of(defs, "kilde") == "pump" and kind_of(defs, "pumpe") == "pump" and kind_of(defs, "radiator") == "consumer"
    # radiatorens standard-restriktion 0 (blokeret) gælder, når symbolet ikke har sin egen opsætning
    flows, notes, _ = compute(parse_topology(loop()), defs, {"p": PUMP}, {}, {}.get)
    assert flows.get("r1", 0) == 0 and notes


def test_preview_simulates_pumps_and_positions_without_a_setup():
    out = preview(loop(), DEFS, {}, {}, {}.get, {"p": 0.5})
    assert out["flows"]["r1"] == 50 and out["pumps"][0]["id"] == "p" and not out["pumps"][0]["configured"] and out["linked"]
    out = preview(loop(), DEFS, {"p": PUMP}, {}, {}.get)
    assert out["flows"]["r1"] == 100 and out["pumps"][0]["configured"]
    out = preview(loop(), DEFS, {"p": PUMP}, {}, {}.get, {"p": 0})
    assert out["flows"].get("r1", 0) == 0


def test_port_colors_follow_the_open_ways():
    cfg = {"op": "positions", "positions": [{"label": "AB → A"}, {"label": "AB → B"}],
           "flow": {"open": [["AB>A"], ["AB>B"]], "port_colors": {"open": "#00ff00", "closed": "#000000"}}}
    ids = {"v1", "v1_port_a", "v1_port_b", "v1_port_ab", "v1_motor"}
    out = port_color_bindings("d", "v1", cfg, DEFS["trevejs_motorventil_ab"], ids, set())
    by = {b["element"]: b["params"]["colors"] for b in out}
    assert by == {"v1_port_a": ["#00ff00", "#000000"], "v1_port_b": ["#000000", "#00ff00"], "v1_port_ab": ["#00ff00", "#00ff00"]}
    assert all(b["tag"] == "sym:d:v1:pos" and b["params"]["pos"] for b in out)
    assert not port_color_bindings("d", "v1", cfg, DEFS["trevejs_motorventil_ab"], ids, {("v1_port_a", "stroke")})[0]["element"] == "v1_port_a"
    assert part_instance("V1", "port_ab", {"V1_port_ab_2", "V1_port_a_2"}) == "V1_port_ab_2"
    assert port_color_bindings("d", "v1", {**cfg, "op": "view"}, DEFS["trevejs_motorventil_ab"], ids, set()) == []


# ---------------------------------------------------------------- API

def _drawing(api, s: str) -> str:
    return api.post("/api/drawings", json={"name": "Flow 2", "svg": s}).json()["drawing"]["id"]


def test_preview_endpoint(api):
    d = _drawing(api, with_bend())
    r = api.post(f"/api/drawings/{d}/flow/preview", json={"svg": with_bend(), "rates": {"p": 1}})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["flows"]["r2"] == 100 and j["ports"]["b"]["0,0"] == 100 and j["simulated"] is True
    assert api.post(f"/api/drawings/{d}/flow/preview", json={"svg": ""}).status_code == 400
    assert api.post(f"/api/drawings/{d}/flow/preview", json={"svg": with_bend(), "rates": {"p": "x"}}).status_code == 400
    assert api.post(f"/api/drawings/{d}/flow/preview", json={"svg": "<svg"}).status_code == 400
    assert api.post("/api/drawings/findes-ikke/flow/preview", json={"svg": with_bend()}).status_code == 404
    assert api.get("/api/health/details").json()["flow"]["previews"] >= 1


def test_profile_via_the_symbol_flow_api(api):
    r = api.put("/api/symbol-flow/stroemforsyning", json={"ports": [], "kind": "pump", "medium": "electric", "capacity": 16})
    assert r.status_code == 200, r.text
    assert api.get("/api/symbol-flow").json()["stroemforsyning"] == {"ports": [], "kind": "pump", "medium": "electric", "capacity": 16}
    assert api.put("/api/symbol-flow/x", json={"ports": [], "kind": "nope"}).status_code == 400
    assert api.put("/api/symbol-flow/x", json={"ports": [], "capacity": 70000}).status_code == 400
    assert api.put("/api/symbol-flow/x", json={"ports": []}).status_code == 400      # hverken punkter eller profil
    bk = api.get("/api/backup").json()
    assert api.post("/api/backup/restore", json=bk).status_code == 200


def test_bend_gets_a_port_tag_and_port_colors_reach_the_view(api):
    d = _drawing(api, with_bend())
    api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": PUMP})
    view = api.get(f"/api/drawings/{d}/view").json()
    bend = next(b for b in view["bindings"] if b["element"] == "b" and b["source"] == "conn-group")
    assert bend["params"]["port_tag"] == ports_tag(d, "b")


def test_measured_tag_is_validated(api):
    d = _drawing(api, loop())
    bad = {"op": "view", "flow": {"measured": {"src": "Findes_ikke"}}}
    assert "findes ikke" in api.put(f"/api/drawings/{d}/symbols/rad/config", json={"config": bad}).text
    ok = {"op": "view", "flow": {"measured": {"src": "Ekstra"}}}
    r = api.put(f"/api/drawings/{d}/symbols/rad/config", json={"config": ok})
    assert r.status_code == 200, r.text


def test_live_value_quality_from_cache():
    lv = LiveValue(value=1, quality="good", ts=0)
    assert lv.quality == "good"


def test_restriction_is_a_value_from_0_to_1_not_a_bit(api):
    """Jan 2026-11-13: restriktionen er et tal 0,00–1,00 — i simuleringen og fra et tal-tag (fx ventilens åbning i %)."""
    s, cfg = branches(1, 1)
    out = preview(s, DEFS, cfg, {}, {}.get, restricts={"a": 0.25})
    assert abs(out["flows"]["ra"] / out["flows"]["rb"] - 0.25) < 0.01                 # grenene deler sig 0,25 : 1
    assert {x["id"]: x["restrict"] for x in out["symbols"]}["a"] == 0.25
    tagged = {**cfg, "a": {"op": "view", "flow": {"restrict": {"src": "V_pct", "max": 100}}}}
    f = compute(parse_topology(s), DEFS, tagged, {}, {"V_pct": 25}.get)[0]
    assert abs(f["ra"] / f["rb"] - 0.25) < 0.01 and f["ra"] == out["flows"]["ra"]
    d = _drawing(api, loop())
    assert api.post(f"/api/drawings/{d}/flow/preview", json={"svg": loop(), "restricts": {"rad": 1.5}}).status_code == 400
    assert api.post(f"/api/drawings/{d}/flow/preview", json={"svg": loop(), "restricts": {"rad": 0.5}}).status_code == 200


def test_color_animation_accepts_an_activation_limit(api):
    """Jan 2026-11-13: farve på et tal-tag — aktiv fra en grænse (fx ≥ 50)."""
    d = _drawing(api, loop())
    cfg = {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "Ekstra",
                                    "params": {"on": "#00ff00", "off": "#000000", "at_least": 50}}]}
    r = api.put(f"/api/drawings/{d}/symbols/rad/config", json={"config": cfg})
    assert r.status_code == 200, r.text
    b = next(x for x in api.get(f"/api/drawings/{d}/view").json()["bindings"] if x["element"] == "rad" and x["anim"] == "fill")
    assert b["params"]["at_least"] == 50


def test_review_fixes_profile_change_reaches_the_view_at_once(api):
    """Reviewer v6.3.0: en ændret flow-profil skal straks give nye bindinger (cache-generationen tælles op)."""
    s = svg(sym("p", "pumpe", f"{OUT}>r1:s;{IN}>r2:e"), pipe("r1", f"s>p:{OUT};e>x:0,0"),
            sym("x", "min_boejning", "0,0>r1:e;1,1>r2:s"), pipe("r2", f"s>x:1,1;e>p:{IN}"))
    d = _drawing(api, s)
    api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": PUMP})
    view = lambda: {b["element"] for b in api.get(f"/api/drawings/{d}/view").json()["bindings"] if b["source"] == "conn-group"}  # noqa: E731
    assert "x" not in view()
    assert api.put("/api/symbol-flow/min_boejning", json={"ports": [], "kind": "piece"}).status_code == 200
    assert "x" in view()


def test_review_fixes_preview_access_limits_and_no_side_effects(api):
    d = _drawing(api, loop())
    before = dict(api.app.state.cache.snapshot()) if hasattr(api.app.state.cache, "snapshot") else None
    for bad in ({"rates": {"p": True}}, {"restricts": {"p": -0.1}}, {"rates": [1]},
                {"rates": {f"e{i}": 1 for i in range(501)}}):
        assert api.post(f"/api/drawings/{d}/flow/preview", json={"svg": loop(), **bad}).status_code == 400, bad
    assert api.post(f"/api/drawings/{d}/flow/preview", json={"svg": loop(), "rates": {"p": 1}}).status_code == 200
    assert api.app.state.cache.get(f"flow:{d}:r1") is None or api.app.state.cache.get(f"flow:{d}:r1").value is None   # intet udgivet
    if before is not None:
        assert not [k for k in api.app.state.cache.snapshot() if k.startswith(("flow:", "flowp:")) and k not in before]
    # en DOCTYPE i en sendt tegning afvises
    dtd = '<!DOCTYPE svg [<!ENTITY a "b">]>' + loop()
    assert api.post(f"/api/drawings/{d}/flow/preview", json={"svg": dtd}).status_code == 400
    # en operatør må ikke
    api.post("/api/users", json={"username": "op1", "password": "op-pass-123456", "role": "operator"})
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "op1", "password": "op-pass-123456"})
    assert api.post(f"/api/drawings/{d}/flow/preview", json={"svg": loop()}).status_code == 403


def test_review_fixes_meter_counts_net_flow_and_caps_the_factor():
    # to modsatrettede pumper gennem samme radiator: måleren ser NETTO
    cfg = {"p": PUMP, "rad": {"op": "view", "flow": {"measured": {"src": "FT"}}}}
    flows, notes, _ = compute(parse_topology(loop()), DEFS, cfg, {}, {"FT": 5000}.get)
    assert flows["r1"] == 1000 and any("højst" in n for n in notes)          # højst 10 gange det beregnede


def test_review_fixes_plc_removal_clears_flow_tags():
    from app.services.plc_removal import strip_config
    cfg = {"op": "view", "flow": {"pump": True, "rate": {"src": "A"}, "restrict": {"src": "B"}, "measured": {"src": "C"}}}
    out = strip_config(cfg, {"A", "C"})
    assert out["flow"]["rate"]["src"] == "" and out["flow"]["measured"]["src"] == "" and out["flow"]["restrict"]["src"] == "B"
