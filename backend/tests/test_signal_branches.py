"""Signalveje 2 (v4.13.0): grene (flere slutpunkter) med OG-kæde pr. gren og ELLER over fælles stykker, og ind/ud-definitioner
pr. symboltype (symbol_flow) med backup."""

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


def blocks(c):
    return {b["id"]: b for b in cfg(c, "r1")["logic"]}


def test_branches_get_their_own_chain_and_the_shared_stretch_gets_an_or(net):
    c = net
    r = c.post(f"/api/drawings/{c.nd}/signal-paths", json=net_body([
        {"element": "vA", "src": "P1_drift", "branches": [0]},
        {"element": "vB", "src": "V2_stilling", "cmp": "ge", "value": 50, "branches": [1]}]))
    assert r.status_code == 201, r.text
    lg = blocks(c)
    assert [(b["id"], b["op"]) for b in lg.values()] == [("L1", "and"), ("L2", "and"), ("L3", "or")]
    assert lg["L1"]["inputs"][0]["src"] == "P1_drift" and lg["L2"]["inputs"][0]["src"] == "V2_stilling"
    assert [i["src"] for i in lg["L3"]["inputs"]] == ["@L1", "@L2"]
    ref = lambda el, part=0: cfg(c, el)["anims"][part]["src"]  # noqa: E731
    assert ref("r1") == "@L3" and ref("t1") == "@r1:L3"                        # stammen: ELLER over begge grene
    assert ref("rA") == "@r1:L1" and ref("rA2") == "@r1:L1"                    # gren A: sin egen kæde
    assert ref("rB") == "@r1:L2" and ref("rB2") == "@r1:L2"
    p = c.get(f"/api/drawings/{c.nd}/signal-paths").json()[0]
    assert p["ends"] == ["radA", "radB"] and p["elements"][1]["branches"] == [0, 1] and p["elements"][1]["block"] == "L3"


def test_a_branch_without_conditions_makes_the_shared_stretch_always_on(net):
    c = net
    assert c.post(f"/api/drawings/{c.nd}/signal-paths", json=net_body(
        [{"element": "vA", "src": "P1_drift", "branches": [0]}])).status_code == 201
    assert [b["id"] for b in blocks(c).values()] == ["L1"]                      # gren B har ingen betingelser → ingen blok
    assert cfg(c, "r1")["anims"][0]["src"] == "@on"                            # stammen lyser altid (ELLER med "altid")
    assert cfg(c, "rA")["anims"][0]["src"] == "@r1:L1" and cfg(c, "rB")["anims"][0]["src"] == "@on"


def test_one_branch_gives_the_same_blocks_as_before(net):
    c = net
    body = net_body([{"element": "vA", "src": "P1_drift"}])
    body["ends"] = []
    body["elements"] = [e for e in body["elements"] if e["branches"] != [1]]
    for e in body["elements"]:
        e["branches"] = [0]
    assert c.post(f"/api/drawings/{c.nd}/signal-paths", json=body).status_code == 201
    assert [(b["id"], b["name"]) for b in blocks(c).values()] == [("L1", "Signalvej: Kedel → radiatorer")]
    assert cfg(c, "rA")["anims"][0]["src"] == "@r1:L1"


def test_edit_and_delete_remove_exactly_what_the_path_made(net):
    c = net
    r = c.post(f"/api/drawings/{c.nd}/signal-paths", json=net_body([
        {"element": "vA", "src": "P1_drift", "branches": [0]}, {"element": "vB", "src": "V2_stilling", "cmp": "ge", "value": 5,
                                                                "branches": [1]}]))
    pid = r.json()["id"]
    # ret til én gren: de gamle blokke og løbelys er væk, og de nye ligger der
    one = net_body([{"element": "vA", "src": "P1_drift"}], ends=[])
    one["ends"] = []
    one["elements"] = [{**e, "branches": [0]} for e in one["elements"] if e["element"] not in ("rB", "vB", "rB2", "radB")]
    assert c.put(f"/api/drawings/{c.nd}/signal-paths/{pid}", json=one).status_code == 200
    assert [b["id"] for b in blocks(c).values()] == ["L1"]
    assert cfg(c, "r1")["anims"][0]["src"] == "@L1"
    assert c.delete(f"/api/drawings/{c.nd}/signal-paths/{pid}").status_code == 200
    for el in ("r1", "rA", "t1"):
        assert c.get(f"/api/drawings/{c.nd}/symbols/{el}/config").json()["config"] is None


def test_the_same_valve_can_have_a_condition_per_branch(net):
    """En 3-vejsventil, der deler vejen: samme element, en betingelse pr. vej (gren)."""
    c = net
    body = net_body([{"element": "vA", "src": "P1_drift", "branches": [0]}, {"element": "vA", "src": "V2_stilling", "cmp": "ge",
                                                                                "value": 5, "branches": [1]}])
    # vA på begge grene (som 3-vejsventilen ville være)
    for e in body["elements"]:
        if e["element"] == "vA":
            e["branches"] = [0, 1]
    assert c.post(f"/api/drawings/{c.nd}/signal-paths", json=body).status_code == 201
    lg = blocks(c)
    assert lg["L1"]["inputs"][0]["src"] == "P1_drift" and lg["L2"]["inputs"][0]["src"] == "V2_stilling"


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


def test_too_many_blocks_gives_a_clear_error(net):
    c = net
    many = [{"element": "vA", "src": "P1_drift", "branches": [0]} for _ in range(4)]
    many += [{"element": "vB", "src": "V2_stilling", "cmp": "ge", "value": 1, "branches": [1]} for _ in range(4)]
    first = c.post(f"/api/drawings/{c.nd}/signal-paths", json=net_body(many))
    assert first.status_code == 201                                                                   # 2 kæder + ELLER = 3 blokke
    assert c.delete(f"/api/drawings/{c.nd}/signal-paths/{first.json()['id']}").status_code == 200
    # 25 betingelser i den ene gren = 8 blokke, plus den anden gren og ELLER → for mange
    huge = [{"element": "vA", "src": "P1_drift", "branches": [0]} for _ in range(24)] + \
           [{"element": "vB", "src": "V2_stilling", "cmp": "ge", "value": 1, "branches": [1]}]
    r = c.post(f"/api/drawings/{c.nd}/signal-paths", json=net_body(huge, name="stor"))
    assert r.status_code in (400, 409) and ("logikblokke" in r.text or "betingelser" in r.text)


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


def test_start_and_end_conditions_get_the_right_branches(net):
    """En betingelse på startsymbolet gælder alle grene; på et slutpunkt kun dets egen gren (uden branches i kaldet)."""
    c = net
    body = net_body([{"element": "kedel", "src": "P1_drift"}, {"element": "radB", "src": "V2_stilling", "cmp": "ge", "value": 5}])
    body["elements"] = [e for e in body["elements"] if e["element"] not in ("kedel", "radB")]
    assert c.post(f"/api/drawings/{c.nd}/signal-paths", json=body).status_code == 201
    lg = {b["id"]: [i["src"] for i in b["inputs"]] for b in blocks(c).values()}
    assert lg["L1"] == ["P1_drift"]                                                  # gren 0: kun startbetingelsen
    assert lg["L2"] == ["P1_drift", "V2_stilling"]                                   # gren 1: start + sit eget slutpunkt


def test_backup_with_bad_signal_path_data_is_rejected(net):
    from app.services.signal_paths import valid_data
    base = {"start": "a", "end": "b", "owner": "r1", "blocks": ["L1"], "final": "", "elements": [
        {"element": "r1", "flows": [], "branches": [0], "block": "L1"}], "conditions": [], "style": {}}
    assert valid_data(base) is None
    assert "block" in valid_data({**base, "elements": [{"element": "r1", "flows": [], "block": "L9"}]})
    assert "branches" in valid_data({**base, "conditions": [{"element": "r1", "branches": [7]}]})
    assert "ui" in valid_data({**base, "ui": {"x": "y" * 9000}})


# ------------------------------------------------------------------ animationer pr. element-type (v4.14.0)

def _cfg_anims(c, el):
    return (cfg(c, el) or {}).get("anims", [])


def test_a_path_can_put_other_animations_on_valves_and_pipes(net):
    c = net
    body = net_body([{"element": "vA", "src": "P1_drift", "branches": [0]}])
    body["ends"] = []
    body["elements"] = [{**e, "branches": [0]} for e in body["elements"] if e["branches"] != [1]]
    for e in body["elements"]:
        if e["element"] == "vA":
            e["anims"] = [{"part": "vA_hus", "type": "fill", "params": {"on": "#00aa00", "off": "#888888"}},
                          {"part": "vA_hus", "type": "blink", "params": {"speed": "fast"}}]
        if e["element"] == "rA":
            e["anims"] = [{"part": "all", "type": "fill", "params": {"on": "#ff0000"}}]
    r = c.post(f"/api/drawings/{c.nd}/signal-paths", json=body)
    assert r.status_code == 201, r.text
    va = {(a["type"], a["part"]): a for a in _cfg_anims(c, "vA")}
    assert va[("fill", "vA_hus")]["params"]["on"] == "#00aa00" and va[("blink", "vA_hus")]["params"]["speed"] == "fast"
    assert va[("fill", "vA_hus")]["when"] is True and va[("fill", "vA_hus")]["src"].startswith("@")      # aktiv/passiv, styret af blokken
    types_ra = sorted((a["type"], a["part"]) for a in _cfg_anims(c, "rA"))
    assert types_ra == [("fill", "all"), ("flow", "all")]                          # løbelys + farve på samme rør
    # ret til kun løbelys: farve- og blink-animationerne er væk, og ventilens egen opsætning er ryddet op
    pid = c.get(f"/api/drawings/{c.nd}/signal-paths").json()[0]["id"]
    for e in body["elements"]:
        e["anims"] = []
    assert c.put(f"/api/drawings/{c.nd}/signal-paths/{pid}", json=body).status_code == 200
    assert _cfg_anims(c, "vA") == []
    assert [a["type"] for a in _cfg_anims(c, "rA")] == ["flow"]
    assert c.delete(f"/api/drawings/{c.nd}/signal-paths/{pid}").status_code == 200
    assert c.get(f"/api/drawings/{c.nd}/symbols/rA/config").json()["config"] is None


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


def test_same_type_on_the_same_part_asks_before_it_is_replaced(net):
    c = net
    url = f"/api/drawings/{c.nd}/signal-paths"
    mine = lambda name: {"name": name, "start": "kedel", "end": "radA", "elements": [  # noqa: E731
        {"element": "vA", "flows": [], "branches": [0], "anims": [{"part": "vA_hus", "type": "fill", "params": {"on": "#00aa00"}}]},
        {"element": "radA", "flows": [], "branches": [0]}], "conditions": [], "style": {}}
    c.put(f"/api/drawings/{c.nd}/symbols/vA/config", json={"config": {"op": "view", "anims": [
        {"part": "vA_hus", "type": "fill", "when": False, "src": "P1_drift", "params": {"on": "#123456"}}]}})
    r = c.post(url, json=mine("første"))
    assert r.status_code == 409 and r.json()["conflicts"][0]["element"] == "vA"
    assert c.post(url, json={**mine("første"), "replace": True}).status_code == 201
    r2 = c.post(url, json=mine("anden"))                                            # en anden signalvej må ikke tage den
    assert r2.status_code == 409


def test_info_lists_the_parts_of_a_symbol(net):
    c = net
    r = c.post(f"/api/drawings/{c.nd}/signal-paths/info", json={"elements": ["vA", "t1"]}).json()
    vA = next(e for e in r["elements"] if e["element"] == "vA")
    assert vA["parts"] == [{"id": "vA_hus", "pid": "", "line": False, "text": ""}] or vA["parts"][0]["id"] == "vA_hus"
