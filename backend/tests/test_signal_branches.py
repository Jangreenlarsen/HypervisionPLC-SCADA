"""Signalveje med grene (flere slutpunkter): OG pr. gren og ELLER over fælles stykker — regnet af serveren (v5.0.0) —
animationer pr. element, og ind/ud-definitioner pr. symboltype (symbol_flow) med backup."""

import pytest

from tests.test_signal_paths import S, api, cfg  # noqa: F401 — fixture

NET = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 300">'
       '<g id="kedel" data-hv-type="kedel" data-hv-name="Kedel"><rect id="kedel_hus" width="40" height="60"/></g>'
       f'<path id="r1" data-hv-pipe="1" d="M40 30 H100" {S}/>'
       f'<g id="t1" data-hv-type="t_stykke" data-hv-name="T1"><path id="t1_a" d="M100 30 H145" {S}/><path id="t1_b" d="M145 30 H190" {S}/>'
       f'<path id="t1_c" d="M145 35 V90" {S}/></g>'
       f'<path id="rA" data-hv-pipe="1" d="M190 30 H250" {S}/>'
       '<g id="vA" data-hv-type="kugleventil" data-hv-name="VA"><path id="vA_hus" d="M250 20 L280 40"/></g>'
       f'<path id="rA2" data-hv-pipe="1" d="M280 30 H340" {S}/>'
       '<g id="radA" data-hv-type="radiator" data-hv-name="Radiator A"><rect id="radA_hus" x="340" width="40" height="60"/></g>'
       f'<path id="rB" data-hv-pipe="1" d="M145 90 V140" {S}/>'
       '<g id="vB" data-hv-type="kugleventil" data-hv-name="VB"><path id="vB_hus" d="M135 140 L155 170"/></g>'
       f'<path id="rB2" data-hv-pipe="1" d="M145 170 V230" {S}/>'
       '<g id="radB" data-hv-type="radiator" data-hv-name="Radiator B"><rect id="radB_hus" x="125" y="230" width="40" height="60"/></g>'
       '</svg>')
FL = [{"part": "all", "reverse": False}]


def net_body(conds, **kw):
    els = [("kedel", [], [0, 1]), ("r1", FL, [0, 1]), ("t1", [{"part": "t1_a", "reverse": False}, {"part": "t1_b", "reverse": False},
                                                          {"part": "t1_c", "reverse": False}], [0, 1]),
           ("rA", FL, [0]), ("vA", [], [0]), ("rA2", FL, [0]), ("radA", [], [0]),
           ("rB", FL, [1]), ("vB", [], [1]), ("rB2", FL, [1]), ("radB", [], [1])]
    return {"name": "Kedel → radiatorer", "start": "kedel", "end": "radA", "ends": ["radB"],
            "elements": [{"element": e, "flows": f, "branches": b} for e, f, b in els],
            "conditions": conds, "style": {"light": "#8fc8ea", "speed": 40, "dash": 12}, **kw}


@pytest.fixture
def net(api):
    api.nd = api.d = api.post("/api/drawings", json={"name": "Net", "svg": NET}).json()["drawing"]["id"]   # cfg() bruger api.d
    return api


def runtime_values(c, values):
    """Sæt tag-værdier i live-cachen, beregn signalvejene, og giv {pseudo-tag: værdi} for vejene."""
    from app.services.live_cache import LiveValue
    rt = c.app.state.symbol_runtime
    rt.cache.update({k: (v if isinstance(v, LiveValue) else LiveValue(value=v, quality="good", ts=1.0)) for k, v in values.items()})
    # Runtime-løkken kører også i baggrunden (i appens tråd) og kan overlappe en beregning her: regn igen, til billedet er stabilt
    import time as _time
    want = bool(c.app.state.symbol_service.db.list_signal_paths())            # (rt.paths kan være tom midt i en genindlæsning i baggrunden)
    for _ in range(40):
        rt.evaluate()
        got = {t: rt.cache.get(t).value for t in rt._path_published if rt.cache.get(t) is not None}
        if bool(got) == want:
            return got
        _time.sleep(0.05)
    return got












def test_branch_rules(net):
    c = net
    url = f"/api/drawings/{c.nd}/signal-paths"
    five = net_body([], ends=["radB", "rB2", "rB", "vB"])
    assert c.post(url, json=five).status_code == 400                            # end + 4 = 5 slutpunkter
    assert c.post(url, json=net_body([], ends=["a", "b", "c", "d", "e"])).status_code == 422   # listen selv: højst 4
    too_many = net_body([])
    too_many["ends"] = ["radB", "vB", "rB2", "rB"]
    assert c.post(url, json=too_many).status_code == 400                        # 5 slutpunkter
    bad_branch = net_body([])
    bad_branch["elements"][3]["branches"] = [2]
    assert c.post(url, json=bad_branch).status_code == 400 and "gren" in c.post(url, json=bad_branch).json()["error"]
    bad_cond = net_body([{"element": "vA", "src": "P1_drift", "branches": [3]}])
    assert c.post(url, json=bad_cond).status_code == 400
    same = net_body([])
    same["start"] = "radA"
    assert c.post(url, json=same).status_code == 400
    missing = net_body([], ends=["findes-ikke"])
    assert c.post(url, json=missing).status_code == 400




# ------------------------------------------------------------------ symbol_flow

DEF = {"ports": [{"x": 0.1, "y": 0.5, "name": "A", "role": "both"}, {"x": 0.9, "y": 0.5, "name": "B", "role": "both"},
                 {"x": 0.5, "y": 1, "name": "AB", "role": "both", "common": True, "part": "port_ab"}],
       "ways": [["AB", "A"], ["AB", "B"]]}


def test_symbol_flow_crud_validation_and_audit(api):
    assert api.get("/api/symbol-flow").json() == {}
    r = api.put("/api/symbol-flow/trevejs_x", json=DEF)
    assert r.status_code == 200 and r.json()["ways"] == [["AB", "A"], ["AB", "B"]]
    assert api.get("/api/symbol-flow").json()["trevejs_x"]["ports"][2]["common"] is True
    bad = [
        {"ports": []},
        {"ports": [{"x": 2, "y": 0, "name": "A"}]},
        {"ports": [{"x": 0, "y": 0, "name": "A b"}]},
        {"ports": [{"x": 0, "y": 0, "name": "A"}, {"x": 1, "y": 1, "name": "A"}]},
        {"ports": [{"x": 0, "y": 0, "name": "A", "role": "midt"}]},
        {"ports": [{"x": 0, "y": 0, "name": "A"}], "ways": [["A", "X"]]},
        {"ports": [{"x": 0, "y": 0, "name": "A", "part": "../x"}]},
    ]
    for b in bad:
        assert api.put("/api/symbol-flow/trevejs_x", json=b).status_code == 400, b
    assert api.put("/api/symbol-flow/Ugyldig Type", json=DEF).status_code == 400
    assert api.delete("/api/symbol-flow/trevejs_x").status_code == 204
    assert api.get("/api/symbol-flow").json() == {}
    acts = [a["action"] for a in api.get("/api/audit?limit=30").json()]
    assert "symbol_flow.set" in acts and "symbol_flow.reset" in acts


def test_symbol_flow_needs_engineer_and_follows_the_backup(api):
    api.put("/api/symbol-flow/trevejs_x", json=DEF)
    backup = api.get("/api/backup").json()
    assert backup["symbol_flow"]["trevejs_x"]["ways"] == [["AB", "A"], ["AB", "B"]]
    api.delete("/api/symbol-flow/trevejs_x")
    assert api.post("/api/backup/restore", json=backup).status_code == 200
    assert "trevejs_x" in api.get("/api/symbol-flow").json()                     # gendannet
    old = {k: v for k, v in backup.items() if k != "symbol_flow"}                 # ældre backup: røres ikke
    assert api.post("/api/backup/restore", json=old).status_code == 200
    assert "trevejs_x" in api.get("/api/symbol-flow").json()
    broken = {**backup, "symbol_flow": {"trevejs_x": {"ports": [{"x": 5, "y": 0, "name": "A"}]}}}
    assert api.post("/api/backup/restore", json=broken).status_code == 400
    api.post("/api/users", json={"username": "op", "password": "Operator-pw-123", "role": "operator"})
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "op", "password": "Operator-pw-123"})
    assert api.get("/api/symbol-flow").status_code == 403


def test_ui_has_a_size_limit_and_the_path_survives_a_backup(net):
    c = net
    url = f"/api/drawings/{c.nd}/signal-paths"
    assert c.post(url, json=net_body([], ui={"x": "y" * 9000})).status_code == 422
    ok = c.post(url, json=net_body([{"element": "vA", "src": "P1_drift", "branches": [0]}], ui={"forced": {"0": {"vA": "AB>A"}}, "picks": [0, 0]}))
    assert ok.status_code == 201, ok.text
    backup = c.get("/api/backup").json()
    assert c.post("/api/backup/restore", json=backup).status_code == 200            # round trip: valid_data accepterer det gemte
    p = c.get(f"{url}").json()[0]
    assert p["ui"]["picks"] == [0, 0] and p["ends"] == ["radA", "radB"]






# ------------------------------------------------------------------ animationer pr. element-type (v4.14.0)

def _cfg_anims(c, el):
    return (cfg(c, el) or {}).get("anims", [])




def test_animations_without_flow_and_the_rules(net):
    c = net
    url = f"/api/drawings/{c.nd}/signal-paths"
    only_color = net_body([])
    only_color["ends"] = []
    only_color["elements"] = [{"element": "vA", "flows": [], "branches": [0],
                               "anims": [{"part": "vA_hus", "type": "fill", "params": {"on": "#00aa00"}}]},
                              {"element": "radA", "flows": [], "branches": [0]}]
    assert c.post(url, json=only_color).status_code == 201                          # ingen løbelys: farven alene er nok
    nothing = net_body([])
    nothing["ends"] = []
    nothing["name"] = "ingenting"
    nothing["elements"] = [{"element": "vB", "flows": [], "branches": [0]}, {"element": "radB", "flows": [], "branches": [0]}]
    r = c.post(url, json=nothing)
    assert r.status_code == 400 and "mindst én animation" in r.json()["error"]
    bad_type = {**only_color, "name": "x", "elements": [{"element": "vA", "branches": [0], "anims": [{"part": "all", "type": "opacity"}]}]}
    assert c.post(url, json=bad_type).status_code == 422                            # opacity kræver et tal-tag
    bad_part = {**only_color, "name": "y", "elements": [{"element": "vB", "branches": [0], "anims": [{"part": "findes_ikke", "type": "fill"}]}]}
    assert c.post(url, json=bad_part).status_code == 400
    bad_params = {**only_color, "name": "z", "elements": [{"element": "vB", "branches": [0],
                                                          "anims": [{"part": "vB_hus", "type": "fill", "params": {"on": "ikke-en-farve"}}]}]}
    assert c.post(url, json=bad_params).status_code == 400




def test_info_lists_the_parts_of_a_symbol(net):
    c = net
    r = c.post(f"/api/drawings/{c.nd}/signal-paths/info", json={"elements": ["vA", "t1"]}).json()
    vA = next(e for e in r["elements"] if e["element"] == "vA")
    assert vA["parts"] == [{"id": "vA_hus", "pid": "", "line": False, "text": ""}] or vA["parts"][0]["id"] == "vA_hus"


def test_each_branch_is_an_and_and_the_shared_stretch_an_or(net):
    c = net
    sid = c.post(f"/api/drawings/{c.nd}/signal-paths", json=net_body([
        {"element": "vA", "src": "P1_drift", "branches": [0]},
        {"element": "vB", "src": "V2_stilling", "cmp": "ge", "value": 50, "branches": [1]}])).json()["id"]
    t = lambda s: f"path:{c.nd}:{sid}:{s}"   # noqa: E731
    v = runtime_values(c, {"P1_drift": True, "V2_stilling": 10})
    assert v == {t("0"): True, t("1"): False, t("0,1"): True}                         # gren A aktiv, B ikke; fælles stykke lyser
    v = runtime_values(c, {"P1_drift": False, "V2_stilling": 60})
    assert v == {t("0"): False, t("1"): True, t("0,1"): True}
    v = runtime_values(c, {"P1_drift": False, "V2_stilling": 0})
    assert v[t("0,1")] is False
    from app.services.live_cache import LiveValue
    v = runtime_values(c, {"P1_drift": LiveValue(value=None, quality="comm_error", ts=1.0), "V2_stilling": 0})
    assert v[t("0")] is None and v[t("0,1")] is None                                # ukendt: vejen viser sin passive tilstand
    v = runtime_values(c, {"P1_drift": LiveValue(value=None, quality="comm_error", ts=1.0), "V2_stilling": 99})
    assert v[t("0,1")] is True                                                       # en aktiv gren afgør ELLER
    rt = c.app.state.symbol_runtime
    assert rt.path_stats["paths"] == 1 and rt.path_stats["errors"] == 0
    # slettes vejen, forsvinder dens pseudo-tags fra live-cachen
    c.delete(f"/api/drawings/{c.nd}/signal-paths/{sid}")
    assert runtime_values(c, {}) == {}
    assert rt.cache.get(t("0")).quality == "unknown"


def test_no_conditions_means_always_on_and_neg_and_start_end_conditions(net):
    c = net
    body = net_body([{"element": "kedel", "src": "P1_drift", "neg": True}, {"element": "radB", "src": "V2_stilling", "cmp": "ge", "value": 5}])
    body["elements"] = [e for e in body["elements"] if e["element"] not in ("kedel", "radB")]
    sid = c.post(f"/api/drawings/{c.nd}/signal-paths", json=body).json()["id"]
    p = c.get(f"/api/drawings/{c.nd}/signal-paths").json()[0]
    assert [x["branches"] for x in p["conditions"]] == [[0, 1], [1]]               # start: alle grene; slutpunkt: kun sin egen
    t = lambda s: f"path:{c.nd}:{sid}:{s}"   # noqa: E731
    assert runtime_values(c, {"P1_drift": False, "V2_stilling": 9}) == {t("0"): True, t("1"): True, t("0,1"): True}
    assert runtime_values(c, {"P1_drift": True, "V2_stilling": 9}) == {t("0"): False, t("1"): False, t("0,1"): False}
    free = net_body([], name="altid")
    sid2 = c.post(f"/api/drawings/{c.nd}/signal-paths", json=free).json()["id"]
    v = runtime_values(c, {})
    assert v[f"path:{c.nd}:{sid2}:0,1"] is True                                     # ingen betingelser: altid aktiv


def test_many_conditions_are_fine_without_logic_blocks(net):
    c = net
    many = [{"element": "vA", "src": "P1_drift", "branches": [0]} for _ in range(30)]
    many += [{"element": "vB", "src": "V2_stilling", "cmp": "ge", "value": 1, "branches": [1]} for _ in range(30)]
    assert c.post(f"/api/drawings/{c.nd}/signal-paths", json=net_body(many)).status_code == 201
    too = many + [{"element": "vB", "src": "P1_drift", "branches": [1]} for _ in range(5)]
    assert c.post(f"/api/drawings/{c.nd}/signal-paths", json=net_body(too, name="for mange")).status_code == 422


def test_valid_data_rules():
    from app.services.signal_paths import valid_data
    base = {"start": "a", "end": "b", "ends": [], "elements": [{"element": "r1", "branches": [0], "flows": [{"part": "all", "reverse": False}],
                                                                 "anims": []}],
            "conditions": [{"element": "r1", "src": "T", "neg": False, "cmp": "", "value": None, "branches": [0]}],
            "style": {"light": "#8fc8ea", "speed": 40, "dash": 12}, "ui": {}}
    assert valid_data(base) is None
    assert "gamle format" in valid_data({**base, "owner": "r1"})
    assert "branches" in valid_data({**base, "elements": [{**base["elements"][0], "branches": [1]}]})       # kun én gren
    assert "betingelse" in valid_data({**base, "conditions": [{**base["conditions"][0], "src": "@L1"}]})
    assert "grænseværdi" in valid_data({**base, "conditions": [{**base["conditions"][0], "cmp": "ge"}]})
    assert "anims" in valid_data({**base, "elements": [{**base["elements"][0], "anims": [{"part": "all", "type": "fill", "params": {}}]}]})
    assert "ui" in valid_data({**base, "ui": {"x": "y" * 9000}})
    assert "style.light" in valid_data({**base, "style": {"light": "rød"}})


def test_a_path_can_put_other_animations_on_valves_and_pipes(net):
    c = net
    body = net_body([{"element": "vA", "src": "P1_drift", "branches": [0]}])
    body["ends"] = []
    body["elements"] = [{**e, "branches": [0]} for e in body["elements"] if e["branches"] != [1]]
    for e in body["elements"]:
        if e["element"] == "vA":
            e["anims"] = [{"part": "vA_hus", "type": "fill", "params": {"on": "#00aa00", "off": "#888888"}},
                          {"part": "vA_hus", "type": "visible", "params": {}, "when": False}]
        if e["element"] == "rA":
            e["anims"] = [{"part": "all", "type": "fill", "params": {"on": "#ff0000"}}]
    sid = c.post(f"/api/drawings/{c.nd}/signal-paths", json=body).json()["id"]
    assert cfg(c, "vA") is None and cfg(c, "rA") is None
    mine = [b for b in c.get(f"/api/drawings/{c.nd}/view").json()["bindings"] if b.get("source") == "path-symbol"]
    va = {b["anim"]: b for b in mine if b["element"] == "vA_hus"}
    assert va["fill"]["params"]["on"] == "#00aa00" and va["fill"]["params"]["when"] is True      # farven, aktiv/passiv
    assert "when" not in va["visible"]["params"]                                     # "vises kun når aktiv": ingen aktiv/passiv
    assert sorted(b["anim"] for b in mine if b["element"] == "rA") == ["fill", "flow"]
    assert all(b["tag"] == f"path:{c.nd}:{sid}:0" for b in mine)


def test_the_paths_animations_come_after_the_symbols_own(net):
    c = net
    c.put(f"/api/drawings/{c.nd}/symbols/vA/config", json={"config": {"op": "view", "anims": [
        {"part": "vA_hus", "type": "fill", "when": True, "src": "P1_drift", "params": {"on": "#123456"}}]}})
    body = {"name": "x", "start": "kedel", "end": "radA", "elements": [
        {"element": "vA", "flows": [], "branches": [0], "anims": [{"part": "vA_hus", "type": "fill", "params": {"on": "#00aa00"}}]},
        {"element": "radA", "flows": [], "branches": [0]}], "conditions": [], "style": {}}
    assert c.post(f"/api/drawings/{c.nd}/signal-paths", json=body).status_code == 201   # ingen "erstat"-spørgsmål (v5.0.0)
    fills = [b for b in c.get(f"/api/drawings/{c.nd}/view").json()["bindings"] if b["element"] == "vA_hus" and b["anim"] == "fill"]
    assert [b["source"] for b in sorted(fills, key=lambda b: b["position"])] == ["symbol", "path-symbol"]
    assert cfg(c, "vA")["anims"][0]["params"]["on"] == "#123456"                     # symbolets egen bevaret
