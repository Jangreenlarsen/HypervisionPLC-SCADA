"""Flowberegningen (v6.1.0, services/flow_calc.py): topologi fra de gemte forbindelser, model A (fordeling efter restriktion),
envejs-veje, 3-vejsventilens åbne veje pr. position, og motoren, der kun udgiver ændringer."""

import pytest

from app.services.flow_calc import FlowEngine, compute, parse_topology, solve
from app.services.live_cache import LiveCache, LiveValue

IN, OUT = "0,0.5", "1,0.5"          # pumpens IND og UD (brøkdele af boksen, som i flow_defs.DEFAULTS)
PUMP = {"op": "view", "flow": {"pump": True, "capacity": 100, "rate": {"src": "@val:1", "max": 1}}}


def svg(*els: str) -> str:
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">' + "".join(els) + "</svg>"


def pipe(i: str, links: str) -> str:
    return f'<path id="{i}" data-hv-pipe="1" d="M0 0 H10" data-hv-links="{links}"/>'


def sym(i: str, typ: str, links: str) -> str:
    return f'<g id="{i}" data-hv-type="{typ}" data-hv-name="{i.upper()}" data-hv-links="{links}"><rect width="10" height="10"/></g>'


def loop() -> str:
    """Pumpe P → r1 → radiator → r2 → P (r2 tegnet fra radiatoren mod pumpen)."""
    return svg(sym("p", "pumpe", f"{OUT}>r1:s;{IN}>r2:e"), pipe("r1", f"s>p:{OUT};e>rad:0,0.5"),
               sym("rad", "radiator", "0,0.5>r1:e;1,0.5>r2:s"), pipe("r2", f"s>rad:1,0.5;e>p:{IN}"))


def run(s: str, configs: dict, positions: dict | None = None, values: dict | None = None):
    return compute(parse_topology(s), __import__("app.services.flow_defs", fromlist=["merged"]).merged(None), configs,
                   positions or {}, (values or {}).get)


def test_solver_splits_like_conductances():
    # 0 → 1 (g 1) og 0 → 1 (g 3) parallelt; 1 l/min ind i 0, ud af 1
    V = solve(2, [(0, 1, 1.0), (0, 1, 3.0)], {0: 1.0, 1: -1.0}, 1)
    assert V[0] == pytest.approx(0.25)


def test_a_pump_drives_its_capacity_round_the_loop_in_the_drawn_direction():
    flows, notes, st = run(loop(), {"p": PUMP})
    assert notes == [] and st["pumping"] == 1
    assert flows["p"] == 100 and flows["r1"] == 100 and flows["r2"] == 100 and flows["rad"] == 100


def test_rate_from_a_tag_and_a_stopped_pump():
    cfg = {"p": {"op": "view", "flow": {"pump": True, "capacity": 200, "rate": {"src": "P_hz", "max": 50}}}}
    assert run(loop(), cfg, values={"P_hz": 25})[0]["r1"] == 100
    flows, _, st = run(loop(), cfg, values={"P_hz": 0})
    assert st["pumping"] == 0 and flows.get("r1", 0) == 0


def test_a_pipe_drawn_against_the_flow_gets_a_negative_value():
    s = loop().replace(f'id="r1" data-hv-pipe="1" d="M0 0 H10" data-hv-links="s>p:{OUT};e>rad:0,0.5"',
                       f'id="r1" data-hv-pipe="1" d="M0 0 H10" data-hv-links="e>p:{OUT};s>rad:0,0.5"')
    s = s.replace("0,0.5>r1:e", "0,0.5>r1:s").replace(f"{OUT}>r1:s", f"{OUT}>r1:e")
    assert run(s, {"p": PUMP})[0]["r1"] == -100


def branches(r_a: float, r_b: float) -> tuple[str, dict]:
    """Pumpe → T → to radiatorer (restriktion r_a, r_b) → T → pumpe."""
    s = svg(sym("p", "pumpe", f"{OUT}>r1:s;{IN}>r9:e"), pipe("r1", f"s>p:{OUT};e>t1:0,0"),
            sym("t1", "t_stykke", "0,0>r1:e;1,0>ra:s;0.5,1>rb:s"),
            pipe("ra", "s>t1:1,0;e>a:0,0"), sym("a", "radiator", "0,0>ra:e;1,1>ra2:s"), pipe("ra2", "s>a:1,1;e>t2:1,0"),
            pipe("rb", "s>t1:0.5,1;e>b:0,0"), sym("b", "radiator", "0,0>rb:e;1,1>rb2:s"), pipe("rb2", "s>b:1,1;e>t2:0.5,1"),
            sym("t2", "t_stykke", "1,0>ra2:e;0.5,1>rb2:e;0,0>r9:s"), pipe("r9", f"s>t2:0,0;e>p:{IN}"))
    cfg = {"p": PUMP, "a": {"op": "view", "flow": {"restrict": {"src": f"@val:{r_a}"}}},
           "b": {"op": "view", "flow": {"restrict": {"src": f"@val:{r_b}"}}}}
    return s, cfg


def test_parallel_branches_split_by_their_restriction():
    s, cfg = branches(0.5, 0.5)
    f = run(s, cfg)[0]
    assert f["ra"] == pytest.approx(f["rb"]) and f["ra"] + f["rb"] == pytest.approx(f["r1"], abs=0.2)
    s, cfg = branches(1.0, 0.5)
    f = run(s, cfg)[0]
    assert f["ra"] == pytest.approx(2 * f["rb"], rel=0.02)


def test_a_closed_valve_blocks_and_a_half_closed_one_in_series_reduces_the_flow():
    s, cfg = branches(0.0, 0.0)
    flows, notes, _ = run(s, cfg)
    assert flows.get("r1", 0) == 0 and "ingen åben vej" in notes[0]
    s = loop()
    half = {"p": PUMP, "rad": {"op": "view", "flow": {"restrict": {"src": "@val:0.5"}}}}
    assert run(s, half)[0]["r1"] == pytest.approx(50, abs=1)


def test_a_check_valve_only_lets_flow_one_way():
    def with_check(reverse: bool) -> str:
        a, b = ("1,0.67", "0,0.67") if reverse else ("0,0.67", "1,0.67")     # kontraventilens IND/UD
        return svg(sym("p", "pumpe", f"{OUT}>r1:s;{IN}>r2:e"), pipe("r1", f"s>p:{OUT};e>k:{a}"),
                   sym("k", "kontraventil", f"{a}>r1:e;{b}>r2:s"), pipe("r2", f"s>k:{b};e>p:{IN}"))
    assert run(with_check(False), {"p": PUMP})[0]["r1"] == 100
    flows, notes, _ = run(with_check(True), {"p": PUMP})
    assert flows.get("r1", 0) == 0 and notes


def test_a_three_way_valve_opens_the_way_of_its_position():
    """Pumpe → AB; A → radiator A, B → radiator B; begge tilbage til pumpen. Position 0 = AB>A, 1 = AB>B."""
    ab, a, b = "0.84,0.46", "0.07,0.46", "0.46,0.08"
    s = svg(sym("p", "pumpe", f"{OUT}>r1:s;{IN}>t2:0,0"), pipe("r1", f"s>p:{OUT};e>v:{ab}"),
            sym("v", "trevejs_motorventil", f"{ab}>r1:e;{a}>ra:s;{b}>rb:s"),
            pipe("ra", f"s>v:{a};e>t2:1,0"), pipe("rb", f"s>v:{b};e>t2:0.5,1"),
            sym("t2", "t_stykke", f"1,0>ra:e;0.5,1>rb:e;0,0>p:{IN}"))
    cfg = {"p": PUMP, "v": {"op": "positions", "positions": [{"label": "A"}, {"label": "B"}],
                            "flow": {"open": [["AB>A"], ["AB>B"]]}}}
    f = run(s, cfg, positions={"v": 0})[0]
    assert f["ra"] == 100 and f.get("rb", 0) == 0
    f = run(s, cfg, positions={"v": 1})[0]
    assert f["rb"] == 100 and f.get("ra", 0) == 0
    assert run(s, cfg, positions={"v": None})[0].get("r1", 0) == 0             # ukendt position: lukket


def test_a_link_the_pipe_end_contradicts_is_not_part_of_the_net():
    # v6.11.3: røret blev delt af et T-stykke og beholdt den gamle forbindelse til tanken — enden sidder i T-stykket (data-hv-to)
    s = svg('<path id="r1" data-hv-pipe="1" d="M0 0 H10" data-hv-from="v@1,0.5,r" data-hv-to="t@0,1,l" '
            'data-hv-links="s&gt;v:1,0.5;e&gt;k:0,0.5"/>',
            sym("v", "kugleventil", "1,0.5>r1:s"), sym("t", "t_stykke", ""), sym("k", "tank", "0,0.5>r1:e"))
    links = {tuple(sorted(x)) for x in parse_topology(s).links}
    assert links == {(("r1", "s"), ("v", "1,0.5"))}
    # en ende uden data-hv-to (fri eller rør mod rør) følger stadig den gemte forbindelse
    s2 = svg('<path id="r1" data-hv-pipe="1" d="M0 0 H10" data-hv-links="e&gt;k:0,0.5"/>', sym("k", "tank", "0,0.5>r1:e"))
    assert len(parse_topology(s2).links) == 1
    # to rørender i samme T-stykke-punkt, bundet til hinanden (varme på demoen): samme sted — beholdes
    s3 = svg('<path id="r1" data-hv-pipe="1" d="M0 0 H10" data-hv-to="t@0.5,0,t" data-hv-links="e&gt;r2:s"/>',
             '<path id="r2" data-hv-pipe="1" d="M10 0 H20" data-hv-from="t@0.5,0,t" data-hv-links="s&gt;r1:e"/>', sym("t", "t_stykke", ""))
    assert len(parse_topology(s3).links) == 1


def test_without_bound_connections_there_is_no_flow():
    s = svg(sym("p", "pumpe", ""), '<path id="r1" data-hv-pipe="1" d="M0 0 H10"/>')
    assert parse_topology(s).links == []
    assert run(s, {"p": PUMP})[0].get("r1", 0) == 0


def test_the_engine_publishes_changes_only_and_clears_stopped_flow():
    cache = LiveCache()
    eng = FlowEngine(cache)
    eng.reload({"d": loop()}, None)
    cfg = {"op": "view", "flow": {"pump": True, "capacity": 80, "rate": {"src": "P_run"}}}
    cache.update({"P_run": LiveValue(value=True, quality="good", ts=0)})
    eng.evaluate({("d", "p"): cfg}, {}, 1.0)
    assert cache.get("flow:d:r1").value == 80 and eng.status()["flowing"] >= 3
    runs = eng.status()["runs"]
    eng.evaluate({("d", "p"): cfg}, {}, 2.0)
    assert eng.status()["runs"] == runs                                           # intet ændret: ingen ny beregning
    cache.update({"P_run": LiveValue(value=False, quality="good", ts=0)})
    eng.evaluate({("d", "p"): cfg}, {}, 3.0)
    assert cache.get("flow:d:r1").value == 0


def test_a_stale_result_from_the_worker_thread_is_not_published():
    """Reviewer v6.1.0: en betjening/reload mens tråden regner — det gamle resultat må ikke overskrive det nye."""
    cache = LiveCache()
    eng = FlowEngine(cache)
    eng.reload({"d": loop()}, None)
    cfg = {"op": "view", "flow": {"pump": True, "capacity": 80, "rate": {"src": "@val:1"}}}
    (did, job), = eng.jobs({("d", "p"): cfg}, {})
    res = eng.run_job(did, job)
    cfg2 = {"op": "view", "flow": {"pump": True, "capacity": 40, "rate": {"src": "@val:1"}}}
    eng.evaluate({("d", "p"): cfg2}, {}, 1.0)                                   # nyere input er allerede udgivet
    eng.publish(did, job, res, 2.0)                                             # det gamle resultat kommer bagefter
    assert cache.get("flow:d:r1").value == 40
    eng.reload({}, None)                                                        # tegningen er væk
    eng.publish(did, job, res, 3.0)
    assert cache.get("flow:d:r1").value is None


def test_an_input_tag_without_a_good_value_gives_unknown_flow_not_zero():
    cache = LiveCache()
    eng = FlowEngine(cache)
    eng.reload({"d": loop()}, None)
    cfg = {"op": "view", "flow": {"pump": True, "capacity": 80, "rate": {"src": "P_run"}}}
    cache.update({"P_run": LiveValue(value=True, quality="good", ts=0)})
    eng.evaluate({("d", "p"): cfg}, {}, 1.0)
    assert cache.get("flow:d:r1").quality == "good"
    cache.update({"P_run": LiveValue(value=None, quality="comm_error", ts=0)})
    eng.evaluate({("d", "p"): cfg}, {}, 2.0)
    assert cache.get("flow:d:r1").quality == "comm_error"


def test_two_pumps_against_each_other_cancel_out():
    """To ens pumper i modsatte retninger i samme løkke: intet netto-flow gennem radiatoren."""
    s = svg(sym("p", "pumpe", f"{OUT}>r1:s;{IN}>r2:e"), pipe("r1", f"s>p:{OUT};e>rad:0,0.5"),
            sym("rad", "radiator", "0,0.5>r1:e;1,0.5>r2:s"), pipe("r2", f"s>rad:1,0.5;e>q:{OUT}"),
            sym("q", "pumpe", f"{OUT}>r2:e;{IN}>r3:s"), pipe("r3", f"s>q:{IN};e>p:{IN}"))
    s = s.replace(f'{IN}>r2:e', f'{IN}>r3:e')
    flows, _, _ = run(s, {"p": PUMP, "q": PUMP})
    assert abs(flows.get("rad", 0)) < 1 and abs(flows.get("r1", 0)) < 1


def test_a_pump_type_without_flow_setup_runs_by_its_position():
    """v6.8.4 (Jan: ingen løbelys i simulatoren): en pumpe-type uden egen flow-opsætning er en pumpe med typens kapacitet;
    farten følger positionen (Fra = stop, Til = kører). Uden positioner står den stille; en egen flow-opsætning vinder."""
    from app.services.flow_calc import pump_running
    from app.services.flow_defs import merged
    cap = merged(None)["pumpe"].get("capacity") or 100
    fra_til = {"op": "positions", "positions": [{"label": "Fra"}, {"label": "Til"}]}
    assert run(loop(), {"p": fra_til}, positions={"p": 1})[0]["r1"] == cap
    assert run(loop(), {"p": fra_til}, positions={"p": 0})[0].get("r1", 0) == 0
    assert run(loop(), {"p": fra_til})[0].get("r1", 0) == 0                     # ukendt position: stille
    assert run(loop(), {})[0].get("r1", 0) == 0                                 # uden opsætning: stille
    flows, notes, st = run(loop(), {"p": {"op": "view"}})                      # v6.8.7: "kun visning" er ingen pumpe
    assert flows.get("r1", 0) == 0 and notes == [] and st.get("pumps", 0) == 0
    assert run(loop(), {"p": {**fra_til, **PUMP}}, positions={"p": 0})[0]["r1"] == 100   # egen flow-opsætning vinder
    # navnene afgør rækkefølgen: "Til" først er også kørende
    assert pump_running({"op": "positions", "positions": [{"label": "Til"}, {"label": "Fra"}]}, 0) is True
    assert pump_running({"op": "positions", "positions": [{"label": "Hånd"}, {"label": "Auto"}]}, 1) is True
    assert pump_running({"op": "view"}, 1) is False


def test_a_pump_wired_at_top_and_bottom_gets_a_precise_note():
    """v6.8.5 (Jan, demoen): rørene sad øverst og nederst på pumpen, IND/UD er venstre og højre — beskeden siger hvor."""
    s = svg(sym("p", "pumpe", "0.5,0>r1:s;0.5,1>r2:e"), pipe("r1", "s>p:0.5,0;e>rad:0,0.5"),
            sym("rad", "radiator", "0,0.5>r1:e;1,0.5>r2:s"), pipe("r2", "s>rad:1,0.5;e>p:0.5,1"))
    flows, notes, _ = run(s, {"p": PUMP})
    assert flows.get("r1", 0) == 0
    assert notes == ["Pumpen 'P' er ikke forbundet på IND og UD — de gemte forbindelser peger på øverst, nederst. Tryk Forbindelser › "
                     "Bind forbindelser i Tegn og gem; sidder rørene ikke ved IND og UD, så ret dem først"]


def test_pump_rate_follows_its_position_with_pos_or_empty_rate():
    """v6.9.4 (Jan): "følger pumpens position" (@pos) — og et tomt rate-felt på en pumpe med positioner — giver start/stop fra
    positionen; en fast værdi eller et tag gælder som før."""
    fra_til = {"op": "positions", "positions": [{"label": "Fra"}, {"label": "Til"}]}
    pos_rate = {**fra_til, "flow": {"pump": True, "capacity": 80, "rate": {"src": "@pos", "max": 1}}}
    assert run(loop(), {"p": pos_rate}, positions={"p": 1})[0]["r1"] == 80
    assert run(loop(), {"p": pos_rate}, positions={"p": 0})[0].get("r1", 0) == 0
    empty = {**fra_til, "flow": {"pump": True, "capacity": 80, "rate": {"src": "", "max": 1}}}
    assert run(loop(), {"p": empty}, positions={"p": 0})[0].get("r1", 0) == 0
    fixed = {**fra_til, "flow": {"pump": True, "capacity": 80, "rate": {"src": "@val:0.5", "max": 1}}}
    assert run(loop(), {"p": fixed}, positions={"p": 0})[0]["r1"] == 40          # fast værdi: som før (uafhængig af positionen)
