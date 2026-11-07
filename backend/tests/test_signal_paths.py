"""Signalveje i Tegn (v4.2.0): betingelse → logikblokke, løbelys på vejens dele, ret/slet uden at røre brugerens egen
opsætning, konflikter, rettigheder og backup."""

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


def test_save_builds_logic_on_the_first_pipe_and_flow_on_every_part(api):
    r = api.post(f"/api/drawings/{api.d}/signal-paths", json=body())
    assert r.status_code == 201, r.text
    assert r.json()["changed"] == ["r1", "r2", "r3", "r4", "t1"]
    owner = cfg(api, "r1")
    assert [b["id"] for b in owner["logic"]] == ["L1"]
    assert owner["logic"][0]["name"] == "Signalvej: Kedel → radiator"
    assert [(i["src"], i["cmp"], i["value"]) for i in owner["logic"][0]["inputs"]] == [("P1_drift", "", None),
                                                                                        ("V2_stilling", "ge", 50)]
    assert [(a["part"], a["type"], a["src"], a["when"]) for a in owner["anims"]] == [("all", "flow", "@L1", True)]
    t = cfg(api, "t1")
    assert [(a["part"], a["src"]) for a in t["anims"]] == [("t1_a", "@r1:L1"), ("t1_b", "@r1:L1")]
    assert cfg(api, "r3")["anims"][0]["params"]["reverse"] is True
    assert cfg(api, "p1") is None and cfg(api, "v2") is None          # symbolerne med spørgsmål røres ikke
    lst = api.get(f"/api/drawings/{api.d}/signal-paths").json()
    assert lst[0]["name"] == "Kedel → radiator" and lst[0]["missing"] == [] and len(lst[0]["conditions"]) == 2


def test_no_conditions_means_always_on_and_many_conditions_are_chained(api):
    r = api.post(f"/api/drawings/{api.d}/signal-paths", json=body(conditions=[]))
    assert r.status_code == 201 and cfg(api, "r1")["anims"][0]["src"] == "@on" and not cfg(api, "r1").get("logic")
    conds = [{"element": "p1", "src": "P1_drift"}] * 9
    r = api.put(f"/api/drawings/{api.d}/signal-paths/{r.json()['id']}", json=body(conditions=conds))
    assert r.status_code == 200, r.text
    logic = cfg(api, "r1")["logic"]
    assert [b["id"] for b in logic] == ["L1", "L2", "L3"]             # 4 + 3 + 2 betingelser
    assert logic[1]["inputs"][0]["src"] == "@L1" and logic[2]["inputs"][0]["src"] == "@L2"
    assert cfg(api, "t1")["anims"][0]["src"] == "@r1:L3"
    too_many = [{"element": "p1", "src": "P1_drift"}] * 26
    assert api.post(f"/api/drawings/{api.d}/signal-paths", json=body(name="x", conditions=too_many)).status_code == 422


def test_users_own_setup_is_kept_on_update_and_delete(api):
    # Brugerens egen opsætning på r2: en farve-animation og en logikblok
    own = {"op": "view", "anims": [{"part": "all", "type": "stroke", "src": "Ekstra",
                                    "params": {"on": "#ff0000", "off": "#555555"}}],
           "logic": [{"id": "L1", "name": "Egen", "op": "and", "inputs": [{"src": "Ekstra"}]}]}
    assert api.put(f"/api/drawings/{api.d}/symbols/r2/config", json={"config": own}).status_code == 200
    sid = api.post(f"/api/drawings/{api.d}/signal-paths", json=body()).json()["id"]
    r2 = cfg(api, "r2")
    assert [a["type"] for a in r2["anims"]] == ["stroke", "flow"] and [b["id"] for b in r2["logic"]] == ["L1"]
    # Vejen rettes: kortere (r4 udgår) og en anden ejer
    b = body()
    b["elements"] = [e for e in b["elements"] if e["element"] not in ("r1", "r4")]
    assert api.put(f"/api/drawings/{api.d}/signal-paths/{sid}", json=b).status_code == 200
    assert cfg(api, "r1") is None and cfg(api, "r4") is None          # oprettet af vejen → fjernet igen
    r2 = cfg(api, "r2")
    assert [b["id"] for b in r2["logic"]] == ["L1", "L2"] and r2["logic"][1]["name"].startswith("Signalvej")
    assert [a["src"] for a in r2["anims"] if a["type"] == "flow"] == ["@L2"]
    assert api.delete(f"/api/drawings/{api.d}/signal-paths/{sid}").status_code == 200
    r2 = cfg(api, "r2")
    assert [a["type"] for a in r2["anims"]] == ["stroke"] and [b["id"] for b in r2["logic"]] == ["L1"]
    assert cfg(api, "t1") is None and api.get(f"/api/drawings/{api.d}/signal-paths").json() == []


def test_existing_flow_needs_confirmation_and_other_paths_are_protected(api):
    flow = {"op": "view", "anims": [{"part": "all", "type": "flow", "src": "Ekstra", "params": {}}]}
    assert api.put(f"/api/drawings/{api.d}/symbols/r3/config", json={"config": flow}).status_code == 200
    r = api.post(f"/api/drawings/{api.d}/signal-paths", json=body())
    assert r.status_code == 409 and r.json()["conflicts"] == [{"element": "r3", "parts": ["all"]}]
    r = api.post(f"/api/drawings/{api.d}/signal-paths", json=body(replace=True))
    assert r.status_code == 201 and [a["src"] for a in cfg(api, "r3")["anims"]] == ["@r1:L1"]
    # En anden signalvej over de samme rør må ikke stjæle dem
    r = api.post(f"/api/drawings/{api.d}/signal-paths", json=body(name="Anden", replace=True))
    assert r.status_code == 409 and "anden signalvej" in r.json()["error"]
    assert api.post(f"/api/drawings/{api.d}/signal-paths", json=body(name="KEDEL → RADIATOR")).status_code == 409


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
    assert r["max_conditions"] == 25
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


def test_backup_roundtrip_keeps_paths(api):
    api.post(f"/api/drawings/{api.d}/signal-paths", json=body())
    bk = api.get("/api/backup").json()
    assert bk["signal_paths"][0]["name"] == "Kedel → radiator" and bk["signal_paths"][0]["data"]["owner"] == "r1"
    api.delete(f"/api/drawings/{api.d}/signal-paths/{api.get(f'/api/drawings/{api.d}/signal-paths').json()[0]['id']}")
    r = api.post("/api/backup/restore", json=bk)
    assert r.status_code == 200, r.text
    lst = api.get(f"/api/drawings/{api.d}/signal-paths").json()
    assert [p["name"] for p in lst] == ["Kedel → radiator"] and cfg(api, "r1")["anims"][0]["src"] == "@L1"
    bad = {**bk, "signal_paths": [{"drawing_id": "findes-ikke", "name": "x", "data": {}}]}
    r = api.post("/api/backup/restore", json=bad)
    assert r.status_code == 400 and "Signalvej 'x'" in r.json()["error"]


def test_engineers_are_never_scoped_but_the_drawing_must_exist(api):
    # Teknikere ser altid alle tegninger (auth.SCOPABLE_ROLES); api/signal_paths.py tjekker alligevel scope som værn
    for r in (api.get("/api/drawings/findes-ikke/signal-paths"),
              api.post("/api/drawings/findes-ikke/signal-paths/info", json={"elements": ["r1"]}),
              api.post("/api/drawings/findes-ikke/signal-paths", json=body())):
        assert r.status_code == 404, r.text


def test_user_changes_after_saving_are_respected(api):
    sid = api.post(f"/api/drawings/{api.d}/signal-paths", json=body()).json()["id"]
    # Brugeren sætter et fejl-tag på T-stykket (oprettet af vejen) og en egen blok L2 på ejeren r1
    t1 = cfg(api, "t1")
    assert api.put(f"/api/drawings/{api.d}/symbols/t1/config", json={"config": {**t1, "fault": "Ekstra"}}).status_code == 200
    r1 = cfg(api, "r1")
    r1["logic"].append({"id": "L2", "name": "Egen", "op": "and", "inputs": [{"src": "Ekstra"}]})
    assert api.put(f"/api/drawings/{api.d}/symbols/r1/config", json={"config": r1}).status_code == 200
    # Ejerens opsætning kan ikke slettes uden om signalvejen
    r = api.delete(f"/api/drawings/{api.d}/symbols/r1/config")
    assert r.status_code == 409 and "signalvejen" in r.json()["error"]
    assert api.delete(f"/api/drawings/{api.d}/signal-paths/{sid}").status_code == 200
    assert cfg(api, "t1")["fault"] == "Ekstra" and cfg(api, "t1")["anims"] == []      # bevaret: ikke længere "tom"
    assert [b["id"] for b in cfg(api, "r1")["logic"]] == ["L2"]                     # brugerens blok bevaret
    assert cfg(api, "r2") is None                                                   # helt tom → fjernet


def test_concurrent_change_is_detected(api):
    db = api.app.state.signal_path_service.db
    r = api.put(f"/api/drawings/{api.d}/symbols/r1/config", json={"config": {"op": "view", "anims": [
        {"part": "all", "type": "stroke", "src": "Ekstra", "params": {"on": "#ff0000", "off": "#555555"}}]}})
    assert r.status_code == 200, r.text
    stale = {"r1": {"op": "noget-andet"}}
    assert db.write_signal_path(api.d, None, "x", {}, {"r1": None}, "test", expect=stale) == -1
    assert cfg(api, "r1") is not None and db.list_signal_paths(api.d) == []


def test_backup_with_broken_path_data_is_refused(api):
    api.post(f"/api/drawings/{api.d}/signal-paths", json=body())
    bk = api.get("/api/backup").json()
    bk["signal_paths"][0]["data"]["elements"] = [{"flows": []}]
    r = api.post("/api/backup/restore", json=bk)
    assert r.status_code == 400 and "element og flows" in r.json()["error"]


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
