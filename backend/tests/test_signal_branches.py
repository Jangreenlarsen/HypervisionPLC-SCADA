"""Signalveje med grene (flere slutpunkter) som definition (v6.0.0), og ind/ud-definitioner pr. symboltype (symbol_flow) med backup."""

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


FL = [{"part": "all", "reverse": False}]


def net_body(**kw):
    els = [("kedel", [], [0, 1]), ("r1", FL, [0, 1]), ("t1", [{"part": "t1_a", "reverse": False}, {"part": "t1_b", "reverse": False},
                                                          {"part": "t1_c", "reverse": False}], [0, 1]),
           ("rA", FL, [0]), ("vA", [], [0]), ("rA2", FL, [0]), ("radA", [], [0]),
           ("rB", FL, [1]), ("vB", [], [1]), ("rB2", FL, [1]), ("radB", [], [1])]
    return {"name": "Kedel → radiatorer", "start": "kedel", "end": "radA", "ends": ["radB"],
            "elements": [{"element": e, "flows": f, "branches": b} for e, f, b in els], **kw}


@pytest.fixture
def net(api):
    api.nd = api.d = api.post("/api/drawings", json={"name": "Net", "svg": NET}).json()["drawing"]["id"]   # cfg() bruger api.d
    return api


def test_a_path_with_two_branches_is_saved_as_one_definition(net):
    c = net
    r = c.post(f"/api/drawings/{c.nd}/signal-paths", json=net_body())
    assert r.status_code == 201, r.text
    p = c.get(f"/api/drawings/{c.nd}/signal-paths").json()[0]
    assert p["ends"] == ["radA", "radB"]
    assert {e["element"]: e["branches"] for e in p["elements"]}["t1"] == [0, 1]       # T-stykket ligger på begge grene
    assert {e["element"]: e["branches"] for e in p["elements"]}["rB"] == [1]


def test_branch_rules(net):
    c = net
    url = f"/api/drawings/{c.nd}/signal-paths"
    five = net_body(ends=["radB", "rB2", "rB", "vB"])
    assert c.post(url, json=five).status_code == 400                            # end + 4 = 5 slutpunkter
    assert c.post(url, json=net_body(ends=["a", "b", "c", "d", "e"])).status_code == 422   # listen selv: højst 4
    bad_branch = net_body()
    bad_branch["elements"][3]["branches"] = [2]
    assert c.post(url, json=bad_branch).status_code == 400 and "gren" in c.post(url, json=bad_branch).json()["error"]
    same = net_body()
    same["start"] = "radA"
    assert c.post(url, json=same).status_code == 400
    assert c.post(url, json=net_body(ends=["findes-ikke"])).status_code == 400


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
    assert c.post(url, json=net_body(ui={"x": "y" * 9000})).status_code == 422
    ok = c.post(url, json=net_body(ui={"forced": {"0": {"vA": "AB>A"}}, "picks": [0, 0]}))
    assert ok.status_code == 201, ok.text
    backup = c.get("/api/backup").json()
    assert c.post("/api/backup/restore", json=backup).status_code == 200            # round trip: valid_data accepterer det gemte
    p = c.get(f"{url}").json()[0]
    assert p["ui"]["picks"] == [0, 0] and p["ends"] == ["radA", "radB"]


def test_valid_data_rules():
    from app.services.signal_paths import is_legacy, strip_legacy, valid_data
    base = {"start": "a", "end": "b", "ends": [], "elements": [{"element": "r1", "branches": [0], "flows": [{"part": "all", "reverse": False}]}],
            "ui": {}}
    assert valid_data(base) is None and not is_legacy(base)
    assert "gamle format" in valid_data({**base, "owner": "r1"})
    assert "branches" in valid_data({**base, "elements": [{**base["elements"][0], "branches": [1]}]})       # kun én gren
    assert "flows" in valid_data({**base, "elements": [{**base["elements"][0], "flows": [{"part": "a b"}]}]})
    assert "ui" in valid_data({**base, "ui": {"x": "y" * 9000}})
    old = {**base, "conditions": [{"src": "T"}], "style": {"light": "#fff"}, "materialized": True,
           "elements": [{**base["elements"][0], "anims": []}]}
    assert valid_data(old) is None and is_legacy(old)                              # ældre veje (backup) accepteres …
    assert strip_legacy(old) == base                                                # … og bliver til en ren definition
