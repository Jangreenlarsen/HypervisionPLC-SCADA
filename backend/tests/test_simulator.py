"""Simulatoren (v6.5.0, services/simulator.py): tegningens variabler, beregning med indskudte værdier (logik, positioner, flow) uden
at skrive eller udgive noget, og scenarier (inkl. backup)."""

from tests.drawing_api import api  # noqa: F401 — fixture
from tests.test_flow_calc import IN, OUT, PUMP, loop

VALVE = {"op": "positions", "passive": True, "positions": [{"label": "Lukket"}, {"label": "Åben"}],
         "signals": [{"id": "S1", "tag": "V2_stilling", "fb": "V2_stilling"}],
         "planes": [{"signal": "S1", "values": [0, 1]}], "display": "remote", "validate_s": 5,
         "anims": [{"part": "all", "type": "fill", "src": "@pos", "params": {"colors": ["#000000", "#00ff00"]}}]}
P1 = {"op": "view", "anims": [{"part": "all", "type": "blink", "src": "@L1", "params": {}}],
      "logic": [{"id": "L1", "op": "and", "inputs": [{"src": "P1_drift"}, {"src": "Ekstra", "neg": True}]}]}


def _setup(api):
    d = api.d
    r = api.put(f"/api/drawings/{d}/symbols/v2/config", json={"config": VALVE})
    assert r.status_code == 200, r.text
    r = api.put(f"/api/drawings/{d}/symbols/p1/config", json={"config": P1})
    assert r.status_code == 200, r.text
    return d


def sim(api, d, values=None, positions=None):
    r = api.post(f"/api/drawings/{d}/simulate", json={"values": values or {}, "positions": positions or {}})
    assert r.status_code == 200, r.text
    return r.json()["values"]


def test_variables_lists_what_the_drawing_reads(api):
    d = _setup(api)
    v = api.get(f"/api/drawings/{d}/simulator").json()
    tags = {t["name"]: t for t in v["tags"]}
    assert {"P1_drift", "Ekstra", "V2_stilling"} <= set(tags)
    assert tags["P1_drift"]["kind"] == "bool" and tags["V2_stilling"]["kind"] == "num"
    assert any("P1" in u for u in tags["P1_drift"]["used"])
    assert v["positions"] == [{"element": "v2", "name": "V2", "labels": ["Lukket", "Åben"], "states": [None, None], "display": "remote", "live": None}]
    assert not [t for t in tags if t.startswith(("sym:", "flow"))]                    # afledte værdier er ikke variabler


def test_simulate_derives_logic_and_positions(api):
    d = _setup(api)
    vals = sim(api, d, {"P1_drift": True, "Ekstra": False, "V2_stilling": 1})
    assert vals[f"sym:{d}:p1:logic:L1"] == {"value": True, "quality": "good"}
    assert vals[f"sym:{d}:v2:pos"]["value"] == 1 and vals[f"sym:{d}:v2:state"]["value"] == "confirmed"
    vals = sim(api, d, {"P1_drift": True, "Ekstra": True})
    assert vals[f"sym:{d}:p1:logic:L1"]["value"] is False
    # en tvungen position og en komm.fejl
    vals = sim(api, d, {"P1_drift": None}, {"v2": 0})
    assert vals[f"sym:{d}:v2:pos"]["value"] == 0
    assert vals["P1_drift"]["quality"] == "comm_error" and vals[f"sym:{d}:p1:logic:L1"]["quality"] == "comm_error"


def test_simulate_computes_the_flow_and_writes_nothing(api):
    d = api.post("/api/drawings", json={"name": "Sim flow", "svg": loop()}).json()["drawing"]["id"]
    pump = {**PUMP, "flow": {**PUMP["flow"], "rate": {"src": "Ekstra", "max": 1}}}
    assert api.put(f"/api/drawings/{d}/symbols/p/config", json={"config": pump}).status_code == 200
    before = api.app.state.cache.snapshot()
    assert sim(api, d, {"Ekstra": True})[f"flow:{d}:r1"]["value"] == 100
    assert sim(api, d, {"Ekstra": False})[f"flow:{d}:r1"]["value"] == 0
    assert api.app.state.cache.snapshot() == before                                  # intet udgivet
    assert api.get("/api/health/details").json()["simulator"]["simulations"] >= 2
    assert IN and OUT


def test_simulate_input_rules_and_access(api):
    d = _setup(api)
    for bad in ({"values": {"x": [1]}}, {"values": {"x": {"a": 1}}}, {"positions": {"v2": -1}},
                {"positions": {"v2": True}}, {"values": {f"t{i}": 1 for i in range(1001)}}):
        assert api.post(f"/api/drawings/{d}/simulate", json=bad).status_code == 400, bad
    raw = api.post(f"/api/drawings/{d}/simulate", content='{"values": {"x": Infinity}}', headers={"Content-Type": "application/json"})
    assert raw.status_code == 400
    assert api.post("/api/drawings/findes-ikke/simulate", json={}).status_code == 404
    api.post("/api/users", json={"username": "op1", "password": "op-pass-123456", "role": "operator"})
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "op1", "password": "op-pass-123456"})
    assert api.post(f"/api/drawings/{d}/simulate", json={}).status_code == 403
    assert api.get(f"/api/drawings/{d}/simulator").status_code == 403


def test_scenarios_crud_and_backup(api):
    d = _setup(api)
    url = f"/api/drawings/{d}/sim-scenarios"
    r = api.post(url, json={"name": "Pumpe fejl", "values": {"P1_drift": None, "Ekstra": True}, "positions": {"v2": 1}})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert api.post(url, json={"name": "PUMPE FEJL", "values": {}}).status_code == 409        # uden hensyn til store/små bogstaver
    assert api.post(url, json={"name": "Pumpe fejl", "values": {}}).status_code == 409
    assert api.post(url, json={"name": "", "values": {}}).status_code == 400
    assert api.put(f"{url}/{sid}", json={"name": "Sommer", "values": {"Ekstra": False}}).json()["name"] == "Sommer"
    assert api.put(f"{url}/9999", json={"name": "X", "values": {}}).status_code == 404
    lst = api.get(url).json()
    assert {s["name"] for s in lst} >= {"Sommer"}
    bk = api.get("/api/backup").json()
    assert any(s["name"] == "Sommer" for s in bk["sim_scenarios"])
    assert api.delete(f"{url}/{sid}").status_code == 204
    assert api.post("/api/backup/restore", json=bk).status_code == 200
    assert any(s["name"] == "Sommer" and s["values"] == {"Ekstra": False} for s in api.get(url).json())
    bad = {**bk, "sim_scenarios": [{"drawing_id": d, "name": "X", "values": {"a": [1]}}]}
    assert api.post("/api/backup/restore", json=bad).status_code == 400
    acts = [a["action"] for a in api.get("/api/audit?limit=30").json()]
    assert "sim_scenario.create" in acts and "sim_scenario.delete" in acts


def test_review_fixes_position_is_clamped_and_scenarios_follow_the_drawing(api):
    d = _setup(api)
    assert sim(api, d, {}, {"v2": 9})[f"sym:{d}:v2:pos"]["value"] == 1          # kun de positioner, symbolet har
    api.post(f"/api/drawings/{d}/sim-scenarios", json={"name": "A", "values": {}})
    bk = api.get("/api/backup").json()
    old = {k: v for k, v in bk.items() if k != "sim_scenarios"}                  # en backup fra før v6.5.0
    assert api.post("/api/backup/restore", json=old).status_code == 200
    assert api.get(f"/api/drawings/{d}/sim-scenarios").json() == []
    assert api.post("/api/backup/restore", json=bk).status_code == 200
    assert [s["name"] for s in api.get(f"/api/drawings/{d}/sim-scenarios").json()] == ["A"]
    assert api.delete(f"/api/drawings/{d}").status_code in (200, 204)
    assert api.app.state.drawing_service.db.list_sim_scenarios(d) == []              # slettes med tegningen
