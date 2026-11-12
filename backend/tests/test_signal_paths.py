"""Signalveje i Tegn (v5.0.0: vejen er sit eget objekt): gem/ret/slet uden at røre symbolernes opsætning, regler,
rettigheder, backup og "Forklar med egne ord"."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"
S = 'stroke="#555" stroke-width="10" fill="none"'
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 200">'
       '<g id="kedel" data-hv-type="kedel" data-hv-name="Kedel"><rect id="kedel_hus" width="40" height="60" fill="#ccc"/></g>'
       f'<path id="r1" data-hv-pipe="1" d="M40 30 H100" {S}/>'
       '<g id="p1" data-hv-type="pumpe" data-hv-name="P1"><circle id="p1_hjul" cx="120" cy="30" r="20" fill="#ccc" stroke="#555"/></g>'
       f'<path id="r2" data-hv-pipe="1" d="M140 30 H200" {S}/>'
       '<g id="t1" data-hv-type="t_stykke" data-hv-name="T1">'
       f'<path id="t1_a" d="M200 30 H245" {S}/><path id="t1_b" d="M245 30 H290" {S}/><path id="t1_c" d="M245 25 V0" {S}/></g>'
       f'<path id="r3" data-hv-pipe="1" d="M290 30 H350" {S}/>'
       '<g id="v2" data-hv-type="kugleventil" data-hv-name="V2"><path id="v2_hus" d="M350 20 L380 40" fill="#ccc"/></g>'
       f'<path id="r4" data-hv-pipe="1" d="M380 30 H440" {S}/>'
       '<g id="rad" data-hv-type="radiator" data-hv-name="Radiator"><rect id="rad_hus" x="440" width="40" height="60" fill="#ccc"/></g>'
       '</svg>')


def body(name="Kedel → radiator", conditions=None, **kw):
    return {"name": name, "start": "kedel", "end": "rad",
            "elements": [{"element": "r1", "flows": [{"part": "all"}]}, {"element": "p1", "flows": []},
                         {"element": "r2", "flows": [{"part": "all"}]},
                         {"element": "t1", "flows": [{"part": "t1_a"}, {"part": "t1_b"}]},
                         {"element": "r3", "flows": [{"part": "all", "reverse": True}]}, {"element": "v2", "flows": []},
                         {"element": "r4", "flows": [{"part": "all"}]}],
            "conditions": conditions if conditions is not None else
            [{"element": "p1", "src": "P1_drift"}, {"element": "v2", "src": "V2_stilling", "cmp": "ge", "value": 50}],
            **kw}


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path / "data", frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0,
                        start_runtimes=False)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada", "password": "scada123",
                                  "sse_enabled": False})
        for t in [{"name": "P1_drift", "source": "plc1:coil:1"}, {"name": "V2_stilling", "source": "plc1:hr:2"},
                  {"name": "Ekstra", "source": "plc1:coil:3"}]:
            assert c.post("/api/tags", json=t).status_code == 201
        d = c.post("/api/drawings", json={"name": "Varme", "svg": SVG}).json()["drawing"]["id"]
        c.d = d
        yield c


def cfg(c, el):
    return c.get(f"/api/drawings/{c.d}/symbols/{el}/config").json()["config"]










def test_validation_errors_change_nothing(api):
    b = body(conditions=[{"element": "p1", "src": "V2_stilling"}])           # tal-tag uden sammenligning
    r = api.post(f"/api/drawings/{api.d}/signal-paths", json=b)
    assert r.status_code == 400 and "tal-tag" in r.json()["error"]
    assert cfg(api, "r1") is None and api.get(f"/api/drawings/{api.d}/signal-paths").json() == []
    b = body(conditions=[{"element": "fremmed", "src": "P1_drift"}])
    assert api.post(f"/api/drawings/{api.d}/signal-paths", json=b).status_code == 400
    b = body()
    b["elements"].append({"element": "findes_ikke", "flows": [{"part": "all"}]})
    r = api.post(f"/api/drawings/{api.d}/signal-paths", json=b)
    assert r.status_code == 400 and "gem tegningen" in r.json()["error"]
    b = body()
    b["elements"][0]["flows"] = [{"part": "ingen_del"}]
    assert api.post(f"/api/drawings/{api.d}/signal-paths", json=b).status_code == 400
    b = body()
    for e in b["elements"]:
        e["flows"] = []
    assert api.post(f"/api/drawings/{api.d}/signal-paths", json=b).status_code == 400
    assert api.get(f"/api/drawings/{api.d}/signal-paths").json() == []


def test_info_suggests_the_symbols_own_tags(api):
    valve = {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "V2_stilling",
                                      "params": {"min": 0, "max": 100}}]}
    api.put(f"/api/drawings/{api.d}/symbols/v2/config", json={"config": {**valve, "anims": [
        {"part": "all", "type": "blink", "src": "Ekstra", "params": {}}]}})
    r = api.post(f"/api/drawings/{api.d}/signal-paths/info", json={"elements": ["v2", "r1", "nej"]}).json()
    v2, r1, nej = r["elements"]
    assert v2["name"] == "V2" and v2["type"] == "kugleventil" and v2["configured"]
    assert v2["tags"] == [{"name": "Ekstra", "is_bool": True, "unit": "", "description": ""}]
    assert r1["configured"] is False and nej == {"element": "nej", "missing": True}
    assert r["max_conditions"] == 64
    assert {t["name"]: t["is_bool"] for t in r["tags"]} == {"P1_drift": True, "V2_stilling": False, "Ekstra": True}


def test_only_engineers_and_audit(api):
    api.post("/api/users", json={"username": "op", "role": "operator", "password": "Hemmelig-123"})
    api.post("/api/auth/login", json={"username": "op", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert api.get(f"/api/drawings/{api.d}/signal-paths").status_code == 403
    assert api.post(f"/api/drawings/{api.d}/signal-paths", json=body()).status_code == 403
    api.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    api.post(f"/api/drawings/{api.d}/signal-paths", json=body())
    acts = [a["action"] for a in api.get("/api/audit?limit=20").json()]
    assert "signal_path.save" in acts




def test_engineers_are_never_scoped_but_the_drawing_must_exist(api):
    # Teknikere ser altid alle tegninger (auth.SCOPABLE_ROLES); api/signal_paths.py tjekker alligevel scope som værn
    for r in (api.get("/api/drawings/findes-ikke/signal-paths"),
              api.post("/api/drawings/findes-ikke/signal-paths/info", json={"elements": ["r1"]}),
              api.post("/api/drawings/findes-ikke/signal-paths", json=body())):
        assert r.status_code == 404, r.text








# ------------------------------------------------------------------ "Forklar med egne ord" (v4.3.0)

def _llm(api, answer):
    import json as _json

    import httpx

    from app.llm.client import LlmClient
    from tests.test_assist import hw
    api.app.state.hw_profile.detector = hw()
    seen = []

    def handler(req):
        if req.url.path == "/v1/chat/completions":
            seen.append(_json.loads(req.content))
            return httpx.Response(200, json={"model": "m", "usage": {"prompt_tokens": 300, "completion_tokens": 40},
                                             "choices": [{"message": {"content": _json.dumps(answer)}}]})
        return httpx.Response(200, json={})
    api.app.state.assistant.client = LlmClient(transport=httpx.MockTransport(handler))
    return seen


def _events(r):
    import json as _json
    return [_json.loads(x[5:]) for x in r.text.splitlines() if x.startswith("data:")]


Q = [{"element": "p1", "role": "pump"}, {"element": "v2", "role": "valve"}]


def test_suggest_fills_valid_answers_and_drops_the_rest(api):
    seen = _llm(api, {"svar": [
        {"element": "p1", "tag": "P1_drift", "tilstand": "til", "sammenligning": "", "vaerdi": None},
        {"element": "v2", "tag": "V2_stilling", "tilstand": "til", "sammenligning": "", "vaerdi": None},   # tal uden grænse
        {"element": "fremmed", "tag": "Ekstra", "tilstand": "til", "sammenligning": "", "vaerdi": None},
    ]})
    r = api.post(f"/api/drawings/{api.d}/signal-paths/suggest", json={"text": "når pumpen kører", "questions": Q})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    done = _events(r)[-1]
    assert done["type"] == "done"
    assert done["suggestions"] == [{"element": "p1", "src": "P1_drift", "on": True, "cmp": "", "value": None}]
    assert done["unfilled"] == ["v2"]
    body = seen[-1]
    sch = body["response_format"]["json_schema"]["schema"]["properties"]["svar"]["items"]["properties"]
    assert sch["element"]["enum"] == ["p1", "v2"] and "P1_drift" in sch["tag"]["enum"] and "" in sch["tag"]["enum"]
    prompt = body["messages"][-1]["content"]
    assert "id p1: P1 (pumpe/motor)" in prompt and "P1_drift (til/fra)" in prompt and "V2_stilling (tal)" in prompt
    assert "plc1" not in prompt and "coil" not in prompt                    # ingen tag-kilder
    assert prompt.endswith("Beskrivelse: når pumpen kører")
    assert api.get(f"/api/drawings/{api.d}/signal-paths").json() == []        # intet gemt
    assert api.app.state.assistant._asking == {}


def test_suggest_numeric_and_off_and_rules(api):
    _llm(api, {"svar": [{"element": "p1", "tag": "P1_drift", "tilstand": "fra", "sammenligning": "", "vaerdi": None},
                        {"element": "v2", "tag": "V2_stilling", "tilstand": "til", "sammenligning": "ge", "vaerdi": 50}]})
    r = api.post(f"/api/drawings/{api.d}/signal-paths/suggest", json={"text": "P1 stoppet og V2 over 50", "questions": Q})
    assert _events(r)[-1]["suggestions"] == [
        {"element": "p1", "src": "P1_drift", "on": False, "cmp": "", "value": None},
        {"element": "v2", "src": "V2_stilling", "on": True, "cmp": "ge", "value": 50.0}]
    assert api.post(f"/api/drawings/{api.d}/signal-paths/suggest", json={"text": "  ", "questions": Q}).status_code == 400
    assert api.post(f"/api/drawings/{api.d}/signal-paths/suggest", json={"text": "x" * 401, "questions": Q}).status_code == 400
    api.app.state.assistant._asking["admin"] = __import__("time").time()
    assert api.post(f"/api/drawings/{api.d}/signal-paths/suggest", json={"text": "x", "questions": Q}).status_code == 429
    api.app.state.assistant._asking.clear()
    from tests.test_assist import hw
    api.app.state.hw_profile.detector = hw(ram_mb=2000)
    assert api.post(f"/api/drawings/{api.d}/signal-paths/suggest", json={"text": "x", "questions": Q}).status_code == 409
    acts = [a["action"] for a in api.get("/api/audit?limit=50").json()]
    assert "signal_path.suggest" in acts


def test_suggest_model_error_is_an_event(api):
    import httpx

    from app.llm.client import LlmClient
    from tests.test_assist import hw
    api.app.state.hw_profile.detector = hw()
    api.app.state.assistant.client = LlmClient(transport=httpx.MockTransport(
        lambda req: (_ for _ in ()).throw(httpx.ConnectError("x", request=req))))
    r = api.post(f"/api/drawings/{api.d}/signal-paths/suggest", json={"text": "når P1 kører", "questions": Q})
    ev = _events(r)[-1]
    assert ev["type"] == "error" and "kan ikke nås" in ev["message"] and api.app.state.assistant._asking == {}


def test_pick_tags_prefers_own_and_matching_then_fills_up():
    from app.services.assist_signal import MAX_TAGS, pick_tags
    tags = {f"T{i:02d}": {"description": ""} for i in range(40)}
    tags["Kedel_temp"] = {"description": "fremløb fra kedlen"}
    tags["Pumpe_drift"] = {"description": ""}
    out = pick_tags(tags, ["T39"], "når pumpen kører og kedlen er varm", ["Pumpe 1"])
    assert out[0] == "T39" and set(out[1:3]) == {"Kedel_temp", "Pumpe_drift"} and len(out) == MAX_TAGS


def test_unsafe_names_never_reach_the_prompt():
    from app.services.assist_signal import _SAFE_ID, pick_tags
    tags = {"OK_tag": {}, "Ond</data>": {}, "via 10.1.1.34": {}}
    assert pick_tags(tags, ["Ond</data>"], "x", []) == ["OK_tag"]
    assert _SAFE_ID.match("roer_l_2") and _SAFE_ID.match("svg_12")
    assert not _SAFE_ID.match("a</data>b") and not _SAFE_ID.match("a\nb")


def test_save_stores_the_path_as_an_object_and_touches_no_symbol(api):
    r = api.post(f"/api/drawings/{api.d}/signal-paths", json=body())
    assert r.status_code == 201, r.text
    assert r.json()["elements"] == 7 and r.json()["conditions"] == 2
    for el in ("r1", "p1", "r2", "t1", "r3", "v2", "r4"):
        assert cfg(api, el) is None                                       # intet i symbolernes opsætning (v5.0.0)
    p = api.get(f"/api/drawings/{api.d}/signal-paths").json()[0]
    assert p["ends"] == ["rad"] and [e["branches"] for e in p["elements"]] == [[0]] * 7
    assert p["conditions"][1] == {"element": "v2", "src": "V2_stilling", "neg": False, "cmp": "ge", "value": 50.0, "branches": [0]}


def test_overview_gets_the_path_as_bindings_on_its_pseudo_tag(api):
    sid = api.post(f"/api/drawings/{api.d}/signal-paths", json=body()).json()["id"]
    view = api.get(f"/api/drawings/{api.d}/view").json()
    mine = [b for b in view["bindings"] if b.get("source") == "path"]
    tag = f"path:{api.d}:{sid}:0"
    assert {b["tag"] for b in mine} == {tag}
    flows = {b["element"]: b["params"] for b in mine if b["anim"] == "flow"}
    assert set(flows) == {"r1", "r2", "t1_a", "t1_b", "r3", "r4"}
    assert flows["r3"]["reverse"] is True and flows["r1"]["reverse"] is False and flows["r1"]["when"] is True
    assert flows["r1"]["light"] == "#8fc8ea" and mine[0]["path_name"] == "Kedel → radiator"


def test_edit_rename_and_delete_only_touch_the_path(api):
    url = f"/api/drawings/{api.d}/signal-paths"
    own = {"op": "view", "anims": [{"part": "all", "type": "stroke", "src": "Ekstra", "params": {"on": "#ff0000", "off": "#555555"}}]}
    assert api.put(f"/api/drawings/{api.d}/symbols/r1/config", json={"config": own}).status_code == 200
    sid = api.post(url, json=body()).json()["id"]
    assert api.put(f"{url}/{sid}", json=body(name="Ny", conditions=[])).status_code == 200
    assert [p["name"] for p in api.get(url).json()] == ["Ny"] and api.get(url).json()[0]["conditions"] == []
    assert api.post(url, json=body(name="ny")).status_code == 409                 # navnet er taget (store/små bogstaver)
    assert api.delete(f"{url}/{sid}").status_code == 200
    assert api.delete(f"{url}/{sid}").status_code == 404
    assert [(a["type"], a["src"]) for a in cfg(api, "r1")["anims"]] == [("stroke", "Ekstra")]     # symbolets egen opsætning urørt
    assert api.put(f"{url}/999", json=body()).status_code == 404


def test_validation_errors_change_nothing(api):
    url = f"/api/drawings/{api.d}/signal-paths"
    r = api.post(url, json=body(conditions=[{"element": "p1", "src": "V2_stilling"}]))     # tal-tag uden sammenligning
    assert r.status_code == 400 and "tal-tag" in r.json()["error"]
    assert api.post(url, json=body(conditions=[{"element": "fremmed", "src": "P1_drift"}])).status_code == 400
    r = api.post(url, json=body(conditions=[{"element": "p1", "src": "Findes_ikke"}]))
    assert r.status_code == 400 and "findes ikke" in r.json()["error"]
    b = body()
    b["elements"].append({"element": "findes_ikke", "flows": [{"part": "all"}]})
    r = api.post(url, json=b)
    assert r.status_code == 400 and "gem tegningen" in r.json()["error"]
    b = body()
    b["elements"][0]["flows"] = [{"part": "ingen_del"}]
    assert api.post(url, json=b).status_code == 400
    b = body()
    for e in b["elements"]:
        e["flows"] = []
    assert api.post(url, json=b).status_code == 400
    assert api.get(url).json() == []


def test_backup_roundtrip_keeps_paths_and_skips_the_old_format(api):
    url = f"/api/drawings/{api.d}/signal-paths"
    api.post(url, json=body())
    bk = api.get("/api/backup").json()
    assert bk["signal_paths"][0]["name"] == "Kedel → radiator" and "owner" not in bk["signal_paths"][0]["data"]
    api.delete(f"{url}/{api.get(url).json()[0]['id']}")
    assert api.post("/api/backup/restore", json=bk).status_code == 200
    assert [p["name"] for p in api.get(url).json()] == ["Kedel → radiator"]
    old = {**bk, "signal_paths": [*bk["signal_paths"], {"drawing_id": api.d, "name": "gammel",
                                                         "data": {"owner": "r1", "blocks": ["L1"], "elements": []}}]}
    assert api.post("/api/backup/restore", json=old).status_code == 200            # det gamle format springes over
    assert [p["name"] for p in api.get(url).json()] == ["Kedel → radiator"]
    bad = {**bk, "signal_paths": [{"drawing_id": "findes-ikke", "name": "x", "data": {}}]}
    r = api.post("/api/backup/restore", json=bad)
    assert r.status_code == 400 and "Signalvej 'x'" in r.json()["error"]
    broken = {**bk, "signal_paths": [{**bk["signal_paths"][0], "data": {**bk["signal_paths"][0]["data"], "elements": [{"flows": []}]}}]}
    r = api.post("/api/backup/restore", json=broken)
    assert r.status_code == 400 and "element" in r.json()["error"]


def test_a_tag_used_by_a_path_cannot_be_deleted_and_scope_sees_the_pseudo_tag(api):
    sid = api.post(f"/api/drawings/{api.d}/signal-paths", json=body()).json()["id"]
    r = api.delete("/api/tags/P1_drift")
    assert r.status_code == 409 and "signalvejen" in r.text
    tags = api.app.state.symbol_service.tags_for_drawing(api.d)
    assert f"path:{api.d}:{sid}:0" in tags


def test_old_paths_are_removed_with_what_they_left_in_the_symbols(api, tmp_path):
    """v5.0.0: veje i det gamle format slettes ved opstart, og deres blokke/animationer fjernes fra symbolernes opsætning."""
    import json as _json
    import time as _time
    db = api.app.state.signal_path_service.db
    own = {"op": "view", "anims": [{"part": "all", "type": "stroke", "src": "Ekstra", "params": {"on": "#ff0000", "off": "#555555"}}]}
    api.put(f"/api/drawings/{api.d}/symbols/r1/config", json={"config": own})
    r1 = {**cfg(api, "r1")}
    r1["logic"] = [{"id": "L1", "name": "Signalvej: gammel", "op": "and", "inputs": [{"src": "P1_drift"}]},
                   {"id": "L2", "name": "Egen", "op": "and", "inputs": [{"src": "Ekstra"}]}]
    r1["anims"] = [*r1["anims"], {"part": "all", "type": "flow", "when": True, "src": "@L1", "params": {}}]
    r2 = {"op": "view", "anims": [{"part": "all", "type": "flow", "when": True, "src": "@r1:L1", "params": {}}]}
    with db._lock:
        now = _time.time()
        for el, c in (("r1", r1), ("r2", r2)):
            db._conn.execute("INSERT INTO symbol_config(drawing_id, element, config, updated_at, updated_by) VALUES (?,?,?,?,?) "
                             "ON CONFLICT(drawing_id, element) DO UPDATE SET config = excluded.config", (api.d, el, _json.dumps(c), now, "t"))
        old = {"start": "kedel", "end": "rad", "owner": "r1", "blocks": ["L1"], "final": "L1", "created": ["r2"],
               "elements": [{"element": "r1", "flows": [{"part": "all"}]}, {"element": "r2", "flows": [{"part": "all"}]}]}
        db._conn.execute("INSERT INTO signal_paths(drawing_id, name, data, updated_at, updated_by) VALUES (?,?,?,?,?)",
                         (api.d, "gammel", _json.dumps(old), now, "t"))
        db._migrate()
    assert db.list_signal_paths(api.d) == []
    after = cfg(api, "r1")
    assert [b["id"] for b in after["logic"]] == ["L2"] and [a["src"] for a in after["anims"]] == ["Ekstra"]
    assert cfg(api, "r2") is None                                                   # oprettet af vejen og nu tom


def test_upgrade_clears_references_to_removed_blocks_and_survives_a_broken_row(api):
    """Reviewer v5.0.0: henvisninger til en gammel vejs blokke andre steder fjernes; "@on" kun én gang; en beskadiget række
    stopper ikke opstarten."""
    import json as _json
    import time as _time
    db = api.app.state.signal_path_service.db
    r1 = {"op": "view", "logic": [{"id": "L1", "name": "Signalvej: gammel", "op": "and", "inputs": [{"src": "P1_drift"}]},
                                  {"id": "L2", "name": "Egen", "op": "and", "inputs": [{"src": "@L1"}, {"src": "Ekstra"}]}],
          "anims": [{"part": "all", "type": "flow", "when": True, "src": "@L1", "params": {}}]}
    v2 = {"op": "view", "anims": [{"part": "all", "type": "blink", "src": "@r1:L1", "params": {}},          # brugerens egen henvisning
                                  {"part": "all", "type": "fill", "src": "Ekstra", "params": {"on": "#00ff00", "off": "#888888"}}]}
    r4 = {"op": "view", "anims": [{"part": "all", "type": "flow", "when": True, "src": "@on", "params": {}},
                                  {"part": "all", "type": "flow", "when": True, "src": "@on", "params": {"speed": 99}}]}  # brugerens egen
    with db._lock:
        now = _time.time()
        for el, c in (("r1", r1), ("v2", v2), ("r4", r4)):
            db._conn.execute("INSERT INTO symbol_config(drawing_id, element, config, updated_at, updated_by) VALUES (?,?,?,?,?) "
                             "ON CONFLICT(drawing_id, element) DO UPDATE SET config = excluded.config", (api.d, el, _json.dumps(c), now, "t"))
        old = {"owner": "r1", "blocks": ["L1"], "final": "L1",
               "elements": [{"element": "r1", "flows": [{"part": "all"}]}, {"element": "r4", "flows": [{"part": "all"}], "block": ""}]}
        db._conn.execute("INSERT INTO signal_paths(drawing_id, name, data, updated_at, updated_by) VALUES (?,?,?,?,?)",
                         (api.d, "gammel", _json.dumps(old), now, "t"))
        db._conn.execute("INSERT INTO signal_paths(drawing_id, name, data, updated_at, updated_by) VALUES (?,?,?,?,?)",
                         (api.d, "ødelagt", "{ikke json", now, "t"))
        db._migrate()
    assert [r["name"] for r in db._query("SELECT name FROM signal_paths")] == ["ødelagt"]   # sprunget over, ikke stoppet
    after = cfg(api, "r1")
    assert [b["id"] for b in after["logic"]] == ["L2"] and [i["src"] for i in after["logic"][0]["inputs"]] == ["Ekstra"]
    assert [a["src"] for a in cfg(api, "v2")["anims"]] == ["Ekstra"]                 # henvisningen til @r1:L1 er fjernet
    assert len(cfg(api, "r4")["anims"]) == 1                                         # kun vejens ene "@on"-løbelys fjernet
    assert cfg(api, "v2") is not None and api.put(f"/api/drawings/{api.d}/symbols/v2/config",
                                                    json={"config": cfg(api, "v2")}).status_code == 200   # kan gemmes igen


def test_condition_tags_keep_polling_and_limits(api):
    from app.services.drawing_activity import suspended_tags
    from app.services.signal_paths import valid_data
    api.post(f"/api/drawings/{api.d}/signal-paths", json=body(conditions=[{"element": "p1", "src": "P1_drift"}]))
    other = api.post("/api/drawings", json={"name": "Skjult", "svg": SVG}).json()["drawing"]["id"]
    api.put(f"/api/drawings/{other}/symbols/r1/config", json={"config": {"op": "view", "anims": [
        {"part": "all", "type": "blink", "src": "P1_drift", "params": {}}]}})
    st = api.app.state
    db = st.signal_path_service.db
    db._conn.execute("UPDATE drawings SET disabled = 1 WHERE id = ?", (other,))     # P1_drift bruges også på en deaktiveret tegning
    assert "P1_drift" not in suspended_tags(db, st.drawing_service, st.symbol_service)   # signalvejen på den aktive tegning holder den i live
    base = {"start": "a", "end": "b", "ends": [], "elements": [{"element": "r1", "branches": [0], "flows": [{"part": "all", "reverse": False}],
                                                                 "anims": []}],
            "conditions": [{"element": "r1", "src": "T", "neg": False, "cmp": "ge", "value": float("nan"), "branches": [0]}], "style": {}, "ui": {}}
    assert "grænseværdi" in valid_data(base)


# --------------------------------------------------------------------- signalvejen som symbol (v5.4.0)

def _path(api):
    r = api.post(f"/api/drawings/{api.d}/signal-paths", json=body())
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_path_is_a_symbol_with_the_elements_as_parts(api):
    pid = _path(api)
    r = api.get(f"/api/drawings/{api.d}/symbols/sv~{pid}/config").json()
    assert r["orphaned"] is False and r["config"] is None
    assert r["symbol"]["type"] == "signalvej" and r["symbol"]["name"] == "Kedel → radiator"
    assert {"r1", "p1", "p1_hjul", "t1_a", "v2_hus", "r4"} <= set(r["symbol"]["parts"])
    assert api.get(f"/api/drawings/{api.d}/symbols/sv~999/config").json()["orphaned"] is True
    assert api.put(f"/api/drawings/{api.d}/symbols/sv~999/config", json={"config": {"op": "view"}}).status_code == 404
    listed = api.get(f"/api/drawings/{api.d}/signal-paths").json()[0]
    assert listed["symbol"] == f"sv~{pid}" and listed["configured"] is False and listed["sources"]


def test_path_symbol_extra_animations_survive_a_resave_and_win_over_the_automatic_ones(api):
    pid = _path(api)
    src = api.get(f"/api/drawings/{api.d}/signal-paths").json()[0]["sources"][0]["tag"]
    mine = {"op": "positions", "anims": [
        {"part": "p1_hjul", "type": "blink", "src": "Ekstra", "params": {}},
        {"part": "r1", "type": "fill", "src": src, "when": True, "params": {"on": "#ff0000"}}]}
    r = api.put(f"/api/drawings/{api.d}/symbols/sv~{pid}/config", json={"config": mine})
    assert r.status_code == 200, r.text
    assert r.json()["config"]["op"] == "view"                       # en vej kan ikke betjenes
    assert api.put(f"/api/drawings/{api.d}/symbols/sv~{pid}/config",
                   json={"config": {"op": "view", "anims": [{"part": "all", "type": "blink", "src": "Ekstra", "params": {}}]}}
                   ).status_code == 400                             # "hele symbolet" findes ikke for en vej
    before = cfg(api, f"sv~{pid}")
    assert api.put(f"/api/drawings/{api.d}/signal-paths/{pid}", json=body(name="Kedel → radiator")).status_code == 200
    assert cfg(api, f"sv~{pid}") == before                          # automatikken rører ikke de egne rettelser
    view = api.get(f"/api/drawings/{api.d}/view").json()["bindings"]
    own = [b for b in view if b.get("source") == "path-symbol"]
    auto = [b for b in view if b.get("source") == "path"]
    assert {(b["element"], b["anim"]) for b in own} == {("p1_hjul", "blink"), ("r1", "fill")}
    assert all(b["position"] >= 100_000 for b in own) and all(b["position"] < 100_000 for b in auto)
    assert next(b for b in own if b["element"] == "r1")["tag"] == src
    assert api.get(f"/api/drawings/{api.d}/symbols-orphaned").json() == []


def test_path_symbol_logic_runs_and_is_deleted_with_the_path(api):
    pid = _path(api)
    cfgp = {"op": "view", "logic": [{"id": "L1", "name": "Pumpe og ekstra", "op": "and",
                                     "inputs": [{"src": "P1_drift"}, {"src": "Ekstra"}]}],
            "anims": [{"part": "r2", "type": "blink", "src": "@L1", "params": {}}]}
    assert api.put(f"/api/drawings/{api.d}/symbols/sv~{pid}/config", json={"config": cfgp}).status_code == 200
    other = {"op": "view", "anims": [{"part": "all", "type": "blink", "src": f"@sv~{pid}:L1", "params": {}}]}
    assert api.put(f"/api/drawings/{api.d}/symbols/rad/config", json={"config": other}).status_code == 200
    r = api.delete(f"/api/drawings/{api.d}/signal-paths/{pid}")
    assert r.status_code == 409 and "L1" in r.json()["error"]       # en anden bruger vejens blok
    assert cfg(api, f"sv~{pid}") is not None
    api.delete(f"/api/drawings/{api.d}/symbols/rad/config")
    assert api.delete(f"/api/drawings/{api.d}/signal-paths/{pid}").status_code == 200
    assert cfg(api, f"sv~{pid}") is None and api.get(f"/api/drawings/{api.d}/symbols-orphaned").json() == []


def test_backup_keeps_the_path_id_so_the_path_symbol_still_fits(api):
    api.post(f"/api/drawings/{api.d}/signal-paths", json=body(name="Først"))          # id 1 — så vejen herunder ikke har id 1
    pid = api.post(f"/api/drawings/{api.d}/signal-paths", json=body(name="Anden",)).json()["id"]
    api.delete(f"/api/drawings/{api.d}/signal-paths/1")
    own = {"op": "view", "anims": [{"part": "p1_hjul", "type": "blink", "src": "Ekstra", "params": {}}]}
    assert api.put(f"/api/drawings/{api.d}/symbols/sv~{pid}/config", json={"config": own}).status_code == 200
    bk = api.get("/api/backup").json()
    assert [p["id"] for p in bk["signal_paths"]] == [pid]
    assert api.post("/api/backup/restore", json=bk).status_code == 200
    assert [p["id"] for p in api.get(f"/api/drawings/{api.d}/signal-paths").json()] == [pid]
    assert cfg(api, f"sv~{pid}")["anims"][0]["part"] == "p1_hjul"
    old = {**bk, "signal_paths": [{k: v for k, v in p.items() if k != "id"} for p in bk["signal_paths"]]}
    assert api.post("/api/backup/restore", json=old).status_code == 200                # ældre backup uden id: opsætningen droppes
    assert cfg(api, f"sv~{pid}") is None


def test_restore_with_mixed_path_ids_and_references_to_missing_paths(api):
    pid = _path(api)
    bk = api.get("/api/backup").json()
    extra = {**bk["signal_paths"][0], "name": "Uden id", "id": None}
    nxt = {**bk["signal_paths"][0], "name": "Næste", "id": pid + 1}      # det nummer, vejen uden id ellers ville få
    assert api.post("/api/backup/restore", json={**bk, "signal_paths": [extra, nxt, *bk["signal_paths"]]}).status_code == 200
    got = {p["name"]: p["id"] for p in api.get(f"/api/drawings/{api.d}/signal-paths").json()}
    assert got["Næste"] == pid + 1 and got["Kedel → radiator"] == pid and "Uden id" in got
    # en anden opsætning, der bruger vejen som kilde, men hvor vejen ikke kommer med tilbage
    src = api.get(f"/api/drawings/{api.d}/signal-paths").json()[0]["sources"][0]["tag"]
    own = {"op": "view", "anims": [{"part": "all", "type": "blink", "src": src, "params": {}}]}
    assert api.put(f"/api/drawings/{api.d}/symbols/rad/config", json={"config": own}).status_code == 200
    bk2 = api.get("/api/backup").json()
    r = api.post("/api/backup/restore", json={**bk2, "signal_paths": []})
    assert r.status_code == 400 and "signalvej" in r.json()["error"]


def test_deleting_a_path_used_as_a_source_is_refused_and_pins_are_not_allowed(api):
    pid = _path(api)
    src = api.get(f"/api/drawings/{api.d}/signal-paths").json()[0]["sources"][0]["tag"]
    own = {"op": "view", "anims": [{"part": "all", "type": "blink", "src": src, "params": {}}]}
    assert api.put(f"/api/drawings/{api.d}/symbols/rad/config", json={"config": own}).status_code == 200
    r = api.delete(f"/api/drawings/{api.d}/signal-paths/{pid}")
    assert r.status_code == 409 and "rad" in r.json()["error"]
    assert api.put(f"/api/drawings/{api.d}/symbols/sv~{pid}/pin", json={"pin": "1234"}).status_code in (400, 404, 405, 422)
    api.delete(f"/api/drawings/{api.d}/symbols/rad/config")
    assert api.delete(f"/api/drawings/{api.d}/signal-paths/{pid}").status_code == 200


def test_svg_ids_that_look_like_a_path_symbol_are_removed():
    from app.services.svg_sanitize import sanitize_svg
    out = sanitize_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect id="sv~3" width="1" height="1"/><rect id="ok" width="1" height="1"/></svg>')
    assert 'id="sv~3"' not in out.svg and 'id="ok"' in out.svg


def test_runtime_reload_and_evaluate_run_the_logic_of_a_path_symbol(api):
    """v5.4.1: runtimen blev ikke startet i testene, så en manglende import i reload() (vejens symbol) gik ubemærket hen."""
    pid = _path(api)
    cfgp = {"op": "view", "logic": [{"id": "L1", "name": "Ekstra", "op": "and", "inputs": [{"src": "Ekstra"}]}],
            "anims": [{"part": "r2", "type": "blink", "src": "@L1", "params": {}}]}
    assert api.put(f"/api/drawings/{api.d}/symbols/sv~{pid}/config", json={"config": cfgp}).status_code == 200
    rt = api.app.state.symbol_runtime
    rt.reload()
    assert (api.d, f"sv~{pid}") in rt.symbols and rt.names[(api.d, f"sv~{pid}")] == "Kedel → radiator"
    rt.evaluate()          # må ikke kaste


def test_the_server_starts_again_on_existing_data_with_a_path_and_its_symbol(tmp_path):
    """v5.4.1: v5.4.0 kunne ikke starte på data med en vej og dens symbol — testene kørte altid på en tom database, så opstarten
    (lifespan: reload af symbolerne m.m.) blev aldrig prøvet på eksisterende data. Her genstartes appen på samme data-mappe."""
    settings = Settings(data_dir=tmp_path / "data", frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0,
                        start_runtimes=False)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        d = c.post("/api/drawings", json={"name": "Varme", "svg": SVG}).json()["drawing"]["id"]
        pid = c.post(f"/api/drawings/{d}/signal-paths", json=body(conditions=[])).json()["id"]
        own = {"op": "view", "logic": [{"id": "L1", "name": "x", "op": "and", "inputs": [{"src": f"path:{d}:{pid}:0"}]}],
               "anims": [{"part": "p1_hjul", "type": "blink", "src": "@on", "params": {}}]}
        assert c.put(f"/api/drawings/{d}/symbols/sv~{pid}/config", json={"config": own}).status_code == 200
        assert c.put(f"/api/drawings/{d}/symbols/rad/config", json={"config": {"op": "view", "anims": [
            {"part": "all", "type": "blink", "src": f"@sv~{pid}:L1", "params": {}}]}}).status_code == 200
    with TestClient(create_app(settings)) as c:                     # genstart på de samme data
        assert c.get("/api/health").json()["status"] == "ok"
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        rt = c.app.state.symbol_runtime
        assert (d, f"sv~{pid}") in rt.symbols and (d, "rad") in rt.symbols
        rt.evaluate()
        assert c.get(f"/api/drawings/{d}/view").status_code == 200
