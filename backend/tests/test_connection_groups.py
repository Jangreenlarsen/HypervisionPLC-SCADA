"""Forbindelsesgrupper og flow i symbolets opsætning (v6.1.0): API, regler, bindinger til Overview, runtime → live-værdier, backup."""

from tests.drawing_api import api  # noqa: F401 — fixture
from tests.test_flow_calc import IN, OUT, pipe, svg, sym

LOOP = svg(sym("p", "pumpe", f"{OUT}>r1:s;{IN}>r2:e"), pipe("r1", f"s>p:{OUT};e>rad:0,0.5"),
           sym("rad", "radiator", "0,0.5>r1:e;1,0.5>r2:s"), pipe("r2", f"s>rad:1,0.5;e>p:{IN}"))
PUMP = {"op": "view", "flow": {"pump": True, "capacity": 120, "rate": {"src": "Ekstra"}},
        "anims": [{"part": "all", "type": "blink", "src": "@flow", "params": {"at_least": 1}}]}


def _drawing(api):
    d = api.post("/api/drawings", json={"name": "Flow", "svg": LOOP}).json()["drawing"]["id"]
    api.fd = d
    return d


def url(api, rest=""):
    return f"/api/drawings/{api.fd}/connection-groups{rest}"


def test_flow_in_the_symbol_setup_is_validated(api):
    d = _drawing(api)
    r = api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": PUMP})
    assert r.status_code == 200, r.text
    assert api.get(f"/api/drawings/{d}/symbols/p/config").json()["config"]["flow"]["capacity"] == 120
    bad = {**PUMP, "flow": {"pump": True, "rate": {"src": "Findes_ikke"}}}
    assert "findes ikke" in api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": bad}).text
    bad = {**PUMP, "flow": {"pump": True, "rate": {"src": "@val:2", "max": 1}}}
    assert api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": bad}).status_code == 400
    bad = {**PUMP, "flow": {"capacity": 70000}}
    assert api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": bad}).status_code == 400


def test_all_connections_start_in_the_default_group_with_a_running_light(api):
    d = _drawing(api)
    lst = api.get(url(api)).json()
    assert lst["default"]["members"] == ["r1", "r2"] and lst["default"]["anims"] == [{"type": "flow"}] and lst["groups"] == []
    view = api.get(f"/api/drawings/{d}/view").json()
    assert not [b for b in view["bindings"] if b["source"] == "conn-group"]           # ingen pumpe (en pumpe-type uden opsætning): intet
    api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": PUMP})
    view = api.get(f"/api/drawings/{d}/view").json()
    cg = [b for b in view["bindings"] if b["source"] == "conn-group"]
    assert {(b["element"], b["anim"], b["tag"]) for b in cg} == {("r1", "flow", f"flow:{d}:r1"), ("r2", "flow", f"flow:{d}:r2")}
    assert cg[0]["params"]["mode"] == "signed" and cg[0]["params"]["flow_max"] == 120
    own = [b for b in view["bindings"] if b["source"] == "symbol" and b["element"] == "p"]
    assert own[0]["tag"] == f"flow:{d}:p" and own[0]["params"]["abs"] is True       # kilden "symbolets flow"


def test_a_new_group_takes_its_members_out_of_the_others(api):
    d = _drawing(api)
    api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": PUMP})
    r = api.post(url(api), json={"name": "Retur", "members": ["r2"], "anims": [
        {"type": "color", "off": "#9e9e9e", "limits": [{"value": 10, "color": "#1e88e5"}]}, {"type": "blink", "at_most": 0}]})
    assert r.status_code == 201, r.text
    gid = r.json()["id"]
    lst = api.get(url(api)).json()
    assert lst["default"]["members"] == ["r1"] and lst["groups"][0]["members"] == ["r2"]
    g2 = api.post(url(api), json={"name": "Alt", "members": ["r1", "r2"], "anims": [{"type": "fixed", "color": "#ff0000"}]}).json()
    lst = api.get(url(api)).json()
    assert {g["name"]: g["members"] for g in lst["groups"]} == {"Retur": [], "Alt": ["r1", "r2"]}      # én gruppe ad gangen
    view = api.get(f"/api/drawings/{d}/view").json()
    cg = {(b["element"], b["anim"]) for b in view["bindings"] if b["source"] == "conn-group"}
    assert cg == {("r1", "stroke"), ("r2", "stroke")}
    assert api.put(url(api, f"/{gid}"), json={"members": ["r2"]}).status_code == 200
    assert api.delete(url(api, f"/{g2['id']}")).status_code == 204
    assert api.get(url(api)).json()["default"]["members"] == ["r1"]


def test_on_and_off_colors_reach_the_bindings(api):
    # v6.12.0 (Til/Fra): løbelyset har en farve uden flow; farve efter flow kan være "som tegnet" under grænsen
    d = _drawing(api)
    api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": PUMP})
    assert api.put(url(api, "/default"), json={"anims": [{"type": "flow", "stopped": "#9e9e9e"}]}).status_code == 200
    api.post(url(api), json={"name": "Retur", "members": ["r2"], "anims": [
        {"type": "color", "off": "", "limits": [{"value": 0.1, "color": "#1e88e5"}]}]})
    cg = {b["element"]: b for b in api.get(f"/api/drawings/{d}/view").json()["bindings"] if b["source"] == "conn-group"}
    assert cg["r1"]["anim"] == "flow" and cg["r1"]["params"]["stopped"] == "#9e9e9e"
    assert cg["r2"]["anim"] == "stroke" and cg["r2"]["params"]["off"] == ""
    assert api.put(url(api, "/default"), json={"anims": [{"type": "flow", "stopped": "rød"}]}).status_code == 400
    api.put(url(api, "/default"), json={"anims": [{"type": "flow"}]})
    r1 = next(b for b in api.get(f"/api/drawings/{d}/view").json()["bindings"] if b["source"] == "conn-group" and b["element"] == "r1")
    assert "stopped" not in r1["params"]                                               # som tegnet: ingen parameter
    assert r1["params"]["chain"] == "conn"                     # v6.12.4: ét sammenhængende forløb på tværs af forbindelserne


def test_group_rules(api):
    _drawing(api)
    assert api.post(url(api), json={"name": "X", "members": ["rad"]}).status_code == 400              # et symbol, ikke en forbindelse
    assert api.post(url(api), json={"name": "Alle forbindelser", "members": []}).status_code == 400
    assert api.post(url(api), json={"name": "X", "members": [], "anims": [{"type": "blink"}]}).status_code == 400
    assert api.post(url(api), json={"name": "X", "members": [], "anims": [{"type": "flow", "speed": 1}]}).status_code == 400
    assert api.post(url(api), json={"name": "X", "members": []}).status_code == 201
    assert api.post(url(api), json={"name": "X", "members": []}).status_code == 409
    assert api.put(url(api, "/default"), json={"anims": []}).status_code == 200
    assert api.get(url(api)).json()["default"]["anims"] == []
    acts = [a["action"] for a in api.get("/api/audit?limit=20").json()]
    assert "connection_group.create" in acts and "connection_group.default" in acts


def test_the_runtime_publishes_the_flow(api):
    d = _drawing(api)
    api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": PUMP})
    rt = api.app.state.symbol_runtime
    from app.services.live_cache import LiveValue
    api.app.state.cache.update({"Ekstra": LiveValue(value=True, quality="good", ts=0)})
    rt.reload()
    rt.evaluate()
    assert api.app.state.cache.get(f"flow:{d}:r1").value == 120
    assert api.get("/api/health").status_code == 200


def test_groups_follow_the_backup(api):
    d = _drawing(api)
    api.post(url(api), json={"name": "Retur", "members": ["r2"], "anims": [{"type": "fixed", "color": "#00ff00"}]})
    api.put(url(api, "/default"), json={"anims": [{"type": "flow", "speed": 90}]})
    bk = api.get("/api/backup").json()
    assert {g["name"] for g in bk["connection_groups"]} == {"", "Retur"}
    api.delete(url(api, f"/{api.get(url(api)).json()['groups'][0]['id']}"))
    assert api.post("/api/backup/restore", json=bk).status_code == 200
    lst = api.get(f"/api/drawings/{d}/connection-groups").json()
    assert lst["groups"][0]["members"] == ["r2"] and lst["default"]["anims"][0]["speed"] == 90
    bk["connection_groups"][0]["anims"] = [{"type": "nope"}]
    assert api.post("/api/backup/restore", json=bk).status_code == 400


def test_blink_needs_exactly_one_limit_and_backup_checks_names(api):
    _drawing(api)
    r = api.post(url(api), json={"name": "B", "members": [], "anims": [{"type": "blink", "at_least": 1, "at_most": 0}]})
    assert r.status_code == 400
    api.post(url(api), json={"name": "Retur", "members": ["r2"]})
    bk = api.get("/api/backup").json()
    for bad in ({"is_default": "nej"}, {"name": "Alle forbindelser"}, {"name": "x\x01y"}):
        b2 = {**bk, "connection_groups": [{**g, **bad} if g["name"] == "Retur" else g for g in bk["connection_groups"]]}
        assert api.post("/api/backup/restore", json=b2).status_code == 400, bad



def test_default_group_needs_a_pump_that_can_run_and_bound_connections(api):
    """v6.8.7 (regression fra v6.8.4 på demoens "varme"): en pumpe-type kun med "kun visning" gør ikke tegningen til en
    flow-tegning; en pumpe med positioner (Fra/Til) gør; og uden bundne forbindelser er der ingen standardgruppe."""
    d = _drawing(api)
    cg = lambda: {b["element"] for b in api.get(f"/api/drawings/{d}/view").json()["bindings"] if b["source"] == "conn-group"}  # noqa: E731
    view_only = {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "P1_drift", "params": {}}]}
    assert api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": view_only}).status_code == 200
    assert cg() == set()
    fra_til = {"op": "positions", "passive": True, "positions": [{"label": "Fra"}, {"label": "Til"}],
               "signals": [{"id": "S1", "tag": "P1_drift", "fb": "P1_drift"}], "planes": [{"signal": "S1", "values": [0, 1]}],
               "display": "remote", "validate_s": 5}
    r = api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": fra_til})
    assert r.status_code == 200, r.text
    assert cg() == {"r1", "r2"}
    # samme tegning uden bundne forbindelser: ingen standardgruppe
    svg = api.get(f"/api/drawings/{d}/view").json()["svg"]
    import re
    bare = re.sub(r' data-hv-links="[^"]*"', "", svg)
    assert api.post(f"/api/drawings/{d}/versions", json={"svg": bare, "activate": True}).status_code == 201
    assert cg() == set()
