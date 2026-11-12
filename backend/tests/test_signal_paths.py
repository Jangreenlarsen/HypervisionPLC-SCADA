"""Signalveje i Tegn (v6.0.0: en vej er kun en definition; den bruges som et almindeligt symbol `sv~<id>` i symbol-guiden):
definitionen (gem/ret/slet, regler, rettigheder), vejen som symbol med positioner og PLC-tilbagemelding, tilbagemelding fra et
andet symbols position, backup, opgradering fra ældre veje og opstart på eksisterende data."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.live_cache import LiveValue

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


def body(name="Kedel → radiator", **kw):
    """Vejens definition: elementerne, grenene og flowretningen (ingen betingelser eller udseende)."""
    return {"name": name, "start": "kedel", "end": "rad",
            "elements": [{"element": "r1", "flows": [{"part": "all"}]}, {"element": "p1", "flows": []},
                         {"element": "r2", "flows": [{"part": "all"}]},
                         {"element": "t1", "flows": [{"part": "t1_a"}, {"part": "t1_b"}]},
                         {"element": "r3", "flows": [{"part": "all", "reverse": True}]}, {"element": "v2", "flows": []},
                         {"element": "r4", "flows": [{"part": "all"}]}], **kw}


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


def _path(api, name="Kedel → radiator", **kw):
    r = api.post(f"/api/drawings/{api.d}/signal-paths", json=body(name, **kw))
    assert r.status_code == 201, r.text
    return r.json()["id"]


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


# Et vejsymbol med positioner: PLC-tilbagemelding (passiv visning), kontaktflade og løbelys pr. position
def passive_path(fb="Ekstra", **over):
    c = {"op": "positions", "passive": True, "display": "remote", "positions": [{"label": "Fra"}, {"label": "Til"}],
         "signals": [{"id": "S1", "tag": "", "fb": fb, "write": "set", "ms": 500, "rest": None}],
         "planes": [{"signal": "S1", "values": [0, 1]}],
         "anims": [{"part": "r1", "type": "flow", "src": "@pos", "params": {"dirs": [0, 1]}},
                   {"part": "r3", "type": "flow", "src": "@pos", "params": {"dirs": [0, -1]}}]}
    c.update(over)
    return c


def selector(el="rad"):
    """En omskifter, der kun styrer visningen (virtuelt signal, v5.11.0)."""
    return {"op": "positions", "display": "local", "positions": [{"label": "Fra"}, {"label": "Auto"}],
            "signals": [{"id": "S1", "tag": "", "virtual": True}], "planes": [{"signal": "S1", "values": [0, 1]}],
            "anims": [{"part": "all", "type": "blink", "src": "@pos", "params": {"set": [False, True]}}]}


def put_cfg(api, el, config):
    return api.put(f"/api/drawings/{api.d}/symbols/{el}/config", json={"config": config})


# --------------------------------------------------------------------- definitionen

def test_save_stores_only_the_definition_and_touches_no_symbol(api):
    pid = _path(api)
    for el in ("r1", "p1", "v2", "rad", "kedel"):
        assert cfg(api, el) is None                                     # intet i symbolernes opsætning
    assert cfg(api, f"sv~{pid}") is None                                # og vejens eget symbol er ikke sat op endnu
    p = api.get(f"/api/drawings/{api.d}/signal-paths").json()[0]
    assert p["ends"] == ["rad"] and [e["branches"] for e in p["elements"]] == [[0]] * 7
    assert p["elements"][4]["flows"] == [{"part": "all", "reverse": True}]              # flowretningen er en del af definitionen
    assert "conditions" not in p and "style" not in p and p["symbol"] == f"sv~{pid}" and p["configured"] is False


def test_conditions_style_and_animations_from_older_clients_are_ignored(api):
    b = body(conditions=[{"element": "p1", "src": "P1_drift"}], style={"light": "#ff0000"})
    b["elements"][0]["anims"] = [{"part": "all", "type": "fill", "params": {"on": "#00ff00"}}]
    r = api.post(f"/api/drawings/{api.d}/signal-paths", json=b)
    assert r.status_code == 201, r.text
    row = api.app.state.symbol_service.db.get_signal_path(api.d, r.json()["id"])["data"]
    assert set(row) == {"start", "end", "ends", "elements", "ui"} and "anims" not in row["elements"][0]


def test_edit_rename_and_delete_only_touch_the_path(api):
    url = f"/api/drawings/{api.d}/signal-paths"
    own = {"op": "view", "anims": [{"part": "all", "type": "stroke", "src": "Ekstra", "params": {"on": "#ff0000", "off": "#555555"}}]}
    assert put_cfg(api, "r1", own).status_code == 200
    sid = _path(api)
    assert api.put(f"{url}/{sid}", json=body(name="Ny")).status_code == 200
    assert [p["name"] for p in api.get(url).json()] == ["Ny"]
    assert api.post(url, json=body(name="ny")).status_code == 409                 # navnet er taget (store/små bogstaver)
    assert api.delete(f"{url}/{sid}").status_code == 200 and api.get(url).json() == []
    assert cfg(api, "r1")["anims"][0]["src"] == "Ekstra"                           # symbolets egen opsætning er urørt
    assert api.delete(f"{url}/{sid}").status_code == 404


def test_validation_errors_change_nothing(api):
    url = f"/api/drawings/{api.d}/signal-paths"
    b = body()
    b["elements"].append({"element": "findes_ikke", "flows": [{"part": "all"}]})
    r = api.post(url, json=b)
    assert r.status_code == 400 and "gem tegningen" in r.json()["error"]
    b = body()
    b["elements"][0]["flows"] = [{"part": "ingen_del"}]
    assert api.post(url, json=b).status_code == 400
    b = body()
    b["elements"][0]["branches"] = [3]
    assert api.post(url, json=b).status_code == 400
    assert api.post(url, json=body() | {"start": "rad"}).status_code == 400                 # start = slut
    assert api.get(url).json() == []


def test_info_lists_the_elements_with_their_parts(api):
    r = api.post(f"/api/drawings/{api.d}/signal-paths/info", json={"elements": ["t1", "r1", "nej"]}).json()["elements"]
    t1, r1, nej = r
    assert t1["name"] == "T1" and t1["type"] == "t_stykke" and {p["id"] for p in t1["parts"]} == {"t1_a", "t1_b", "t1_c"}
    assert r1["configured"] is False and nej == {"element": "nej", "missing": True}


def test_only_engineers_and_audit(api):
    api.post("/api/users", json={"username": "op", "role": "operator", "password": "Hemmelig-123"})
    api.post("/api/auth/login", json={"username": "op", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert api.get(f"/api/drawings/{api.d}/signal-paths").status_code == 403
    assert api.post(f"/api/drawings/{api.d}/signal-paths", json=body()).status_code == 403
    api.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    api.post(f"/api/drawings/{api.d}/signal-paths", json=body())
    assert "signal_path.save" in [a["action"] for a in api.get("/api/audit?limit=20").json()]


def test_the_drawing_must_exist(api):
    for r in (api.get("/api/drawings/findes-ikke/signal-paths"),
              api.post("/api/drawings/findes-ikke/signal-paths/info", json={"elements": ["r1"]}),
              api.post("/api/drawings/findes-ikke/signal-paths", json=body())):
        assert r.status_code == 404, r.text


# --------------------------------------------------------------------- vejen som symbol (v6.0.0)

def test_the_path_is_a_symbol_with_the_elements_as_parts(api):
    pid = _path(api)
    r = api.get(f"/api/drawings/{api.d}/symbols/sv~{pid}/config").json()
    assert r["orphaned"] is False and r["config"] is None
    assert r["symbol"]["type"] == "signalvej" and r["symbol"]["name"] == "Kedel → radiator"
    assert {"r1", "p1", "p1_hjul", "t1_a", "v2_hus", "r4"} <= set(r["symbol"]["parts"])
    assert api.get(f"/api/drawings/{api.d}/symbols/sv~999/config").json()["orphaned"] is True
    assert put_cfg(api, "sv~999", {"op": "view"}).status_code == 404


def test_a_path_symbol_has_positions_from_a_plc_feedback_and_animations_per_position(api):
    """Trin 2: tilbagemelding fra et PLC-tag; trin 3: kontaktfladen (værdi → position); trin 4: løbelys pr. position."""
    pid = _path(api)
    r = put_cfg(api, f"sv~{pid}", passive_path())
    assert r.status_code == 200, r.text
    saved = r.json()["config"]
    assert saved["op"] == "positions" and saved["passive"] is True and saved["signals"][0]["tag"] == ""     # aldrig noget at skrive
    assert api.get(f"/api/drawings/{api.d}/signal-paths").json()[0]["configured"] is True
    rt = api.app.state.symbol_runtime
    rt.reload()
    pos = f"sym:{api.d}:sv~{pid}:pos"
    for value, want in ((0, 0), (1, 1)):                                   # PLC'ens tilbagemelding er toneangivende
        rt.cache.update({"Ekstra": LiveValue(value=value, quality="good", ts=time.time())})
        rt.evaluate()
        assert rt.cache.get(pos).value == want
    flows = {(b["element"]): b for b in api.get(f"/api/drawings/{api.d}/view").json()["bindings"]
             if b.get("source") == "path-symbol" and b["anim"] == "flow"}
    assert set(flows) == {"r1", "r3"} and flows["r1"]["tag"] == pos and flows["r1"]["params"]["pos"] is True


def test_a_path_symbol_cannot_be_operated_or_written(api):
    pid = _path(api)
    bad = passive_path(passive=False, signals=[{"id": "S1", "tag": "Ekstra", "fb": "", "write": "set"}])
    saved = put_cfg(api, f"sv~{pid}", bad)
    assert saved.status_code == 400 or saved.json()["config"]["signals"][0]["tag"] == ""        # (passiv tvinges: ingen kommando)
    assert api.post(f"/api/drawings/{api.d}/symbols/sv~{pid}/operate", json={"position": 1}).status_code in (404, 405, 409, 422)
    assert put_cfg(api, f"sv~{pid}", {"op": "pulse", "signals": []}).status_code == 400 or cfg(api, f"sv~{pid}")["op"] in ("view", "positions")


def test_the_feedback_can_be_another_symbols_position(api):
    """Trin 2: PLC-tag eller et andet symbols position — her en omskifter, der kun er i SCADA."""
    pid = _path(api)
    assert put_cfg(api, "rad", selector()).status_code == 200
    src = f"sym:{api.d}:rad:pos"
    r = put_cfg(api, f"sv~{pid}", passive_path(fb=src))
    assert r.status_code == 200, r.text
    # et symbols egen position kan ikke være dets egen tilbagemelding (løkke), og et ukendt signal afvises
    own = put_cfg(api, f"sv~{pid}", passive_path(fb=f"sym:{api.d}:sv~{pid}:pos"))
    assert own.status_code == 400 and "findes ikke" in own.json()["error"]
    assert put_cfg(api, f"sv~{pid}", passive_path(fb="sym:varme:ukendt:pos")).status_code == 400
    rt = api.app.state.symbol_runtime
    rt.reload()
    rt.set_chosen((api.d, "rad"), 1, "test")                                # omskifteren står på Auto
    rt.evaluate()
    rt.evaluate()                                                          # (vejens position læser omskifterens ved næste beregning)
    assert rt.cache.get(f"sym:{api.d}:sv~{pid}:pos").value == 1


def test_symbols_reading_each_others_positions_cannot_form_a_loop(api):
    pid = _path(api)
    put_cfg(api, "rad", selector())
    assert put_cfg(api, f"sv~{pid}", passive_path(fb=f"sym:{api.d}:rad:pos")).status_code == 200
    looped = selector()
    looped["signals"] = [{"id": "S1", "tag": "", "virtual": True, "fb": f"sym:{api.d}:sv~{pid}:pos"}]
    r = put_cfg(api, "rad", looped)
    assert r.status_code == 400 and "løkke" in r.json()["error"] + str(r.json())


def test_a_symbol_that_writes_to_a_plc_cannot_take_another_symbols_position_as_feedback(api):
    put_cfg(api, "rad", selector())
    cfg_w = {"op": "positions", "display": "remote", "positions": [{"label": "Fra"}, {"label": "Til"}],
             "signals": [{"id": "S1", "tag": "Ekstra", "fb": f"sym:{api.d}:rad:pos", "write": "set", "ms": 500, "rest": None}],
             "planes": [{"signal": "S1", "values": [0, 1]}],
             "anims": [{"part": "all", "type": "blink", "src": "@pos", "params": {"set": [False, True]}}]}
    r = put_cfg(api, "p1", cfg_w)
    assert r.status_code == 400 and "ikke skriver" in str(r.json())


def test_the_upgrade_changes_nothing_when_the_backup_fails(api):
    from app.services.migrations import v60_paths
    pid = _old_path(api)
    db = api.app.state.symbol_service.db

    class Broken:
        def save_to_server(self, kind, by):
            raise OSError("disk fuld")

    db.set_meta(v60_paths.DONE_KEY, None)
    assert v60_paths.migrate(db, Broken()) is None
    assert "conditions" in db.get_signal_path(api.d, pid)["data"] and not db.get_meta(v60_paths.DONE_KEY)


def test_a_symbol_whose_position_is_read_cannot_be_deleted_or_lose_its_positions(api):
    pid = _path(api)
    put_cfg(api, "rad", selector())
    assert put_cfg(api, f"sv~{pid}", passive_path(fb=f"sym:{api.d}:rad:pos")).status_code == 200
    r = api.delete(f"/api/drawings/{api.d}/symbols/rad/config")
    assert r.status_code == 409 and f"sv~{pid}" in r.json()["error"]
    r = put_cfg(api, "rad", {"op": "view", "anims": [{"part": "all", "type": "blink", "src": "Ekstra", "params": {}}]})
    assert r.status_code == 400 and "bruges af" in r.json()["error"]
    # og omvendt: vejens position læses af et symbol — vejen kan ikke slettes, før henvisningen er fjernet
    assert put_cfg(api, f"sv~{pid}", passive_path()).status_code == 200
    assert put_cfg(api, "p1", {"op": "view", "anims": [{"part": "all", "type": "blink", "src": f"sym:{api.d}:sv~{pid}:pos", "params": {}}]}).status_code == 200
    r = api.delete(f"/api/drawings/{api.d}/signal-paths/{pid}")
    assert r.status_code == 409 and "p1" in r.json()["error"]


def test_deleting_the_path_deletes_its_setup_and_pins_are_not_allowed(api):
    pid = _path(api)
    assert put_cfg(api, f"sv~{pid}", passive_path()).status_code == 200
    assert api.put(f"/api/drawings/{api.d}/symbols/sv~{pid}/pin", json={"pin": "1234"}).status_code in (400, 404, 405, 422)
    assert api.delete(f"/api/drawings/{api.d}/signal-paths/{pid}").status_code == 200
    assert cfg(api, f"sv~{pid}") is None and api.get(f"/api/drawings/{api.d}/symbols-orphaned").json() == []


def test_derived_signals_include_symbol_positions_and_path_positions(api):
    pid = _path(api)
    put_cfg(api, "rad", selector())
    put_cfg(api, f"sv~{pid}", passive_path())
    svc = api.app.state.symbol_service
    sig = {x["id"]: x for x in svc.derived_signals(api.d)}
    assert sig[f"sym:{api.d}:rad:pos"]["group"] == "Symbolers position" and sig[f"sym:{api.d}:rad:pos"]["labels"] == ["Fra", "Auto"]
    assert sig[f"sym:{api.d}:sv~{pid}:pos"]["label"] == "Signalvej Kedel → radiator: position"
    assert f"sym:{api.d}:rad:pos" not in svc.signal_ids(api.d, "rad")                 # ikke sit eget signal


def test_a_path_symbol_may_have_many_animations_but_an_ordinary_symbol_only_twelve(api):
    pid = _path(api)
    many = passive_path(anims=[{"part": "p1_hjul", "type": "blink", "src": "Ekstra", "params": {}} for _ in range(30)])
    assert put_cfg(api, f"sv~{pid}", many).status_code == 200
    r = put_cfg(api, "rad", {"op": "view", "anims": [{"part": "all", "type": "blink", "src": "Ekstra", "params": {}} for _ in range(13)]})
    assert r.status_code == 400 and "12" in r.json()["error"]


def test_every_element_on_a_path_can_be_told_apart_by_its_label():
    from app.services.svg_sanitize import describe_group
    svg = ('<svg xmlns="http://www.w3.org/2000/svg"><g id="a" data-hv-type="trevejs_motorventil" data-hv-name="V"><path id="a_x" d="M0 0"/></g>'
           '<g id="b" data-hv-type="trevejs_motorventil" data-hv-name="V"/><g id="c" data-hv-type="t_stykke"/>'
           '<path id="r" data-hv-pipe="1" d="M0 0 H5"/><g id="d" data-hv-name="Pumpe"/><g id="e"/></svg>')
    parts = describe_group(svg, ["a", "b", "c", "r", "d", "e"], "vej")["parts"]
    assert {k: v["label"] for k, v in parts.items()} == {
        "a": "V (a)", "a_x": "V (a) · a_x", "b": "V (b)", "c": "t stykke (c)", "r": "rør (r)", "d": "Pumpe", "e": "e"}
    assert len({v["label"] for v in parts.values() if v["root"]}) == 6


def test_svg_ids_that_look_like_a_path_symbol_are_removed():
    from app.services.svg_sanitize import sanitize_svg
    out = sanitize_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect id="sv~3" width="1" height="1"/><rect id="ok" width="1" height="1"/></svg>')
    assert 'id="sv~3"' not in out.svg and 'id="ok"' in out.svg


# --------------------------------------------------------------------- backup og opgradering

def test_backup_keeps_the_path_id_so_the_path_symbol_still_fits(api):
    api.post(f"/api/drawings/{api.d}/signal-paths", json=body(name="Først"))
    pid = _path(api, "Anden")
    api.delete(f"/api/drawings/{api.d}/signal-paths/1")
    assert put_cfg(api, f"sv~{pid}", passive_path()).status_code == 200
    bk = api.get("/api/backup").json()
    assert [p["id"] for p in bk["signal_paths"]] == [pid]
    assert api.post("/api/backup/restore", json=bk).status_code == 200
    assert [p["id"] for p in api.get(f"/api/drawings/{api.d}/signal-paths").json()] == [pid]
    assert cfg(api, f"sv~{pid}")["op"] == "positions"
    old = {**bk, "signal_paths": [{k: v for k, v in p.items() if k != "id"} for p in bk["signal_paths"]]}
    assert api.post("/api/backup/restore", json=old).status_code == 200                # ældre backup uden id: opsætningen droppes
    assert cfg(api, f"sv~{pid}") is None


def test_restore_with_mixed_path_ids(api):
    pid = _path(api)
    bk = api.get("/api/backup").json()
    extra = {**bk["signal_paths"][0], "name": "Uden id", "id": None}
    nxt = {**bk["signal_paths"][0], "name": "Næste", "id": pid + 1}
    assert api.post("/api/backup/restore", json={**bk, "signal_paths": [extra, nxt, *bk["signal_paths"]]}).status_code == 200
    got = {p["name"]: p["id"] for p in api.get(f"/api/drawings/{api.d}/signal-paths").json()}
    assert got["Næste"] == pid + 1 and got["Kedel → radiator"] == pid and "Uden id" in got


def test_a_backup_cannot_smuggle_more_than_twelve_animations_onto_an_ordinary_symbol(api):
    put_cfg(api, "rad", {"op": "view", "anims": [{"part": "all", "type": "blink", "src": "Ekstra", "params": {}}]})
    bk = api.get("/api/backup").json()
    row = next(c for c in bk["symbol_config"] if c["element"] == "rad")
    row["config"]["anims"] = [row["config"]["anims"][0] for _ in range(13)]
    r = api.post("/api/backup/restore", json=bk)
    assert r.status_code == 400 and "for mange animationer" in r.json()["error"]


def _old_path(api, anims=2):
    """En vej, som den var før v6.0.0: betingelser, udseende og egne animationer i vejens symbol-opsætning (som en tabelrække)."""
    db = api.app.state.symbol_service.db
    pid = _path(api)
    row = db.get_signal_path(api.d, pid)
    old = {**row["data"], "conditions": [{"element": "p1", "src": "P1_drift", "neg": False, "cmp": "", "value": None, "branches": [0]}],
           "style": {"light": "#8fc8ea", "speed": 40, "dash": 12}, "materialized": True}
    old["elements"] = [{**e, "anims": []} for e in old["elements"]]
    cfg_old = {"op": "view", "anims": [{"part": "r1", "type": "flow", "when": True, "src": f"path:{api.d}:{pid}:0", "params": {}, "auto": True}
                                        for _ in range(anims)]}
    assert db.write_signal_path(api.d, pid, row["name"], old, {f"sv~{pid}": cfg_old}, "test") == pid
    return pid


def test_the_upgrade_turns_old_paths_into_a_definition_and_resets_the_path_setup(api):
    from app.services.migrations import v60_paths
    pid = _old_path(api)
    put_cfg(api, "p1", {"op": "view", "anims": [{"part": "all", "type": "blink", "src": "Ekstra", "params": {}}]})
    db = api.app.state.symbol_service.db
    rep = v60_paths.migrate(db, None, force=True)
    assert rep["paths"] == [{"drawing": api.d, "name": "Kedel → radiator", "conditions": 1, "animations": 2, "logic_blocks": 0}] and rep["reset_setups"] == 1
    row = db.get_signal_path(api.d, pid)["data"]
    assert set(row) == {"start", "end", "ends", "elements", "ui"} and row["elements"][4]["flows"] == [{"part": "all", "reverse": True}]
    assert cfg(api, f"sv~{pid}") is None                                          # vejens opsætning er nulstillet
    assert cfg(api, "p1")["anims"][0]["src"] == "Ekstra"                          # andre symboler er urørt
    assert v60_paths.migrate(db, None, force=True) is None                        # intet mere at gøre


def test_the_upgrade_reports_symbols_that_read_a_path_tag_and_runs_once_with_a_backup(api):
    from app.services.migrations import v60_paths
    pid = _old_path(api)
    db = api.app.state.symbol_service.db
    db.set_symbol_config(api.d, "p1", {"op": "view", "anims": [{"part": "all", "type": "blink", "src": f"path:{api.d}:{pid}:0",
                                                                "params": {}}]}, "test")
    saved = []

    class Backups:
        def save_to_server(self, kind, by):
            saved.append(kind)

    db.set_meta(v60_paths.DONE_KEY, None)
    rep = v60_paths.migrate(db, Backups())
    assert saved == ["pre-v6"] and rep["readers"] == [{"drawing": api.d, "element": "p1"}]
    assert db.get_meta(v60_paths.DONE_KEY) and v60_paths.migrate(db, Backups()) is None and saved == ["pre-v6"]    # én gang


def test_a_restored_backup_from_before_v6_becomes_a_definition(api):
    pid = _old_path(api)
    bk = api.get("/api/backup").json()
    assert bk["signal_paths"][0]["data"]["conditions"]
    assert api.post("/api/backup/restore", json=bk).status_code == 200
    row = api.app.state.symbol_service.db.get_signal_path(api.d, pid)["data"]
    assert "conditions" not in row and cfg(api, f"sv~{pid}") is None


def test_the_server_starts_again_on_existing_data_with_a_path_and_its_symbol(tmp_path):
    """v5.4.1: opstarten (lifespan: reload af symbolerne, opgraderingen m.m.) skal prøves på eksisterende data — ikke kun på en tom database."""
    settings = Settings(data_dir=tmp_path / "data", frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0,
                        start_runtimes=False)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        d = c.post("/api/drawings", json={"name": "Varme", "svg": SVG}).json()["drawing"]["id"]
        pid = c.post(f"/api/drawings/{d}/signal-paths", json=body()).json()["id"]
        own = {"op": "view", "anims": [{"part": "p1_hjul", "type": "blink", "src": "@on", "params": {}}]}
        assert c.put(f"/api/drawings/{d}/symbols/sv~{pid}/config", json={"config": own}).status_code == 200
        assert c.put(f"/api/drawings/{d}/symbols/rad/config", json={"config": {"op": "view", "anims": [
            {"part": "all", "type": "blink", "src": "@on", "params": {}}]}}).status_code == 200
    with TestClient(create_app(settings)) as c:                     # genstart på de samme data
        assert c.get("/api/health").json()["status"] == "ok"
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        rt = c.app.state.symbol_runtime
        assert (d, f"sv~{pid}") in rt.symbols and (d, "rad") in rt.symbols
        rt.evaluate()
        assert c.get(f"/api/drawings/{d}/view").status_code == 200


def test_runtime_reload_and_evaluate_run_the_logic_of_a_path_symbol(api):
    pid = _path(api)
    cfgp = {"op": "view", "logic": [{"id": "L1", "name": "Ekstra", "op": "and", "inputs": [{"src": "Ekstra"}]}],
            "anims": [{"part": "r2", "type": "blink", "src": "@L1", "params": {}}]}
    assert put_cfg(api, f"sv~{pid}", cfgp).status_code == 200
    rt = api.app.state.symbol_runtime
    rt.reload()
    assert (api.d, f"sv~{pid}") in rt.symbols and rt.names[(api.d, f"sv~{pid}")] == "Kedel → radiator"
    rt.evaluate()


def test_pick_tags_prefers_own_and_matching_then_fills_up():
    from app.services.assist_signal import MAX_TAGS, pick_tags
    tags = {f"T{i:02d}": {"description": ""} for i in range(40)}
    tags["Kedel_temp"] = {"description": "fremløb fra kedlen"}
    tags["Pumpe_drift"] = {"description": ""}
    out = pick_tags(tags, ["T39"], "når pumpen kører og kedlen er varm", ["Pumpe 1"])
    assert out[0] == "T39" and set(out[1:3]) == {"Kedel_temp", "Pumpe_drift"} and len(out) == MAX_TAGS
