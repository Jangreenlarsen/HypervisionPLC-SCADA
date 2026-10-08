"""Tegninger, bindinger og WebSocket via REST/WS med rigtig lifespan mod mock-PLC'en."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
       'viewBox="0 0 200 100">'
       '<rect id="Pumpe" width="20" height="20"/>'
       '<text id="Niveau">--</text>'
       '<rect id="rect9" inkscape:label="Pumpe" width="5" height="5"/>'
       '<rect id="Tank" width="10" height="50"/>'
       '<circle id="Ukendt" r="3"/>'
       '<script>alert(1)</script></svg>')


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW)
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW}).status_code == 200
        client.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                       "password": "scada123", "sse_enabled": False})
        client.post("/api/tags", json={"name": "Pumpe", "source": "plc1:coil:0"})
        client.post("/api/tags", json={"name": "Niveau", "source": "plc1:hr:10", "scale": 0.1, "unit": "%"})
        yield client


def _ws_cookie(client):
    return {"cookie": f"scada_session={client.cookies.get('scada_session')}"}


def _create(api, name="Tank anlæg Ø1", svg=SVG):
    r = api.post("/api/drawings", json={"name": name, "svg": svg})
    assert r.status_code == 201, r.text
    return r.json()


def test_upload_sanitizes_and_reports(api):
    body = _create(api)
    assert body["drawing"]["id"] == "tank-anlaeg-oe1"
    assert body["report"]["removed_elements"] == {"script": 1}
    svg = api.get("/api/drawings/tank-anlaeg-oe1/svg")
    assert "script" not in svg.text and "default-src 'none'" in svg.headers["content-security-policy"]
    assert _create(api)["drawing"]["id"] == "tank-anlaeg-oe1-2"  # samme navn → unikt id


def test_invalid_svg_gives_specific_error(api):
    r = api.post("/api/drawings", json={"name": "x", "svg": "<html/>"})
    assert r.status_code == 400 and "ikke en SVG" in r.json()["error"]
    r = api.post("/api/drawings", json={"name": "   ", "svg": SVG})
    assert r.status_code == 400 and "navn" in r.json()["error"]


def test_versions_activate_and_orphans(api):
    did = _create(api)["drawing"]["id"]
    assert api.put(f"/api/drawings/{did}/bindings/Tank",
                   json={"bindings": [{"tag": "Niveau", "anim": "level", "params": {"min": 0, "max": 100}}]}).status_code == 200
    r = api.post(f"/api/drawings/{did}/versions", json={"svg": SVG.replace('id="Tank"', 'id="Tank2"')})
    assert r.status_code == 201
    assert r.json()["version"] == 2 and r.json()["report"]["orphaned_bindings"] == ["Tank"]
    view = api.get(f"/api/drawings/{did}/view").json()
    assert view["version"] == 2 and view["orphaned_bindings"] == ["Tank"]
    # forældreløse bindinger kan ikke ændres, men kan fjernes
    r = api.put(f"/api/drawings/{did}/bindings/Tank", json={"bindings": [{"tag": "Niveau", "anim": "text"}]})
    assert r.status_code == 400
    assert api.put(f"/api/drawings/{did}/bindings/Tank", json={"bindings": []}).status_code == 200
    assert api.get(f"/api/drawings/{did}/view").json()["orphaned_bindings"] == []
    api.put(f"/api/drawings/{did}/bindings/Tank", json={"bindings": []})
    assert api.patch(f"/api/drawings/{did}", json={"active_version": 1}).json()["active_version"] == 1
    assert api.get(f"/api/drawings/{did}/view").json()["orphaned_bindings"] == []
    r = api.patch(f"/api/drawings/{did}", json={"active_version": 9})
    assert r.status_code == 404


def test_binding_validation(api):
    did = _create(api)["drawing"]["id"]
    cases = [
        ("Findes_ikke", [{"tag": "Niveau", "anim": "text"}], "findes ikke i den aktive version"),
        ("Tank", [{"tag": "Ukendt", "anim": "text"}], "Tagget 'Ukendt' findes ikke"),
        ("Tank", [{"tag": "Niveau", "anim": "explode"}], "Ukendt animation"),
        ("Tank", [{"tag": "Niveau", "anim": "level", "params": {"min": 5, "max": 5}}], "min skal være mindre"),
        ("Tank", [{"tag": "Niveau", "anim": "fill", "params": {"on": "red;x:url(javascript:1)"}}], "ugyldig farve"),
        ("Tank", [{"tag": "Niveau", "anim": "fill", "params": {"thresholds": [{"value": 5, "color": "red"},
                                                                              {"value": 1, "color": "blue"}]}}], "sorteret"),
        ("Tank", [{"tag": "Niveau", "anim": "text", "params": {"ukendt": 1}}], "Ugyldige parametre"),
        ("Tank", [{"tag": "Niveau", "anim": "text", "params": {"prefix": "x" * 41}}], "prefix"),
        ("Tank", [{"tag": "Niveau", "anim": "move", "params": {"min": 5, "max": 5}}], "min skal være mindre"),
        ("Tank", [{"tag": "Niveau", "anim": "move", "params": {"dx": 1e9}}], "dx"),
    ]
    for element, bindings, message in cases:
        r = api.put(f"/api/drawings/{did}/bindings/{element}", json={"bindings": bindings})
        assert r.status_code == 400, (element, r.text)
        assert message in r.json()["error"], r.json()["error"]


def test_text_prefix_suffix_kept_verbatim(api):
    did = _create(api)["drawing"]["id"]
    r = api.put(f"/api/drawings/{did}/bindings/Tank", json={"bindings": [
        {"tag": "Niveau", "anim": "text", "params": {"prefix": "Tank : ", "suffix": " liter", "show_unit": False}}]})
    assert r.status_code == 200, r.text
    text = next(b for b in api.get(f"/api/drawings/{did}/view").json()["bindings"] if b["element"] == "Tank")
    assert (text["params"]["prefix"], text["params"]["suffix"]) == ("Tank : ", " liter")  # mellemrum bevaret
    # Uden for/efter-tekst: tomme standardværdier
    api.put(f"/api/drawings/{did}/bindings/Tank", json={"bindings": [{"tag": "Niveau", "anim": "text"}]})
    text = next(b for b in api.get(f"/api/drawings/{did}/view").json()["bindings"] if b["element"] == "Tank")
    assert (text["params"]["prefix"], text["params"]["suffix"]) == ("", "")


def test_view_merges_explicit_and_auto_bindings(api):
    did = _create(api)["drawing"]["id"]
    api.put(f"/api/drawings/{did}/bindings/Tank",
            json={"bindings": [{"tag": "Niveau", "anim": "level"}, {"tag": "Niveau", "anim": "text"}]})
    view = api.get(f"/api/drawings/{did}/view").json()
    by_element = {}
    for b in view["bindings"]:
        by_element.setdefault(b["element"], []).append((b["anim"], b["source"]))
    assert by_element["Pumpe"] == [("fill", "auto")]      # id = tag-navn, bool → fill
    assert by_element["rect9"] == [("fill", "auto")]      # inkscape:label = tag-navn
    assert by_element["Niveau"] == [("text", "auto")]     # <text> → tekst
    assert by_element["Tank"] == [("level", "explicit"), ("text", "explicit")]
    assert "Ukendt" not in by_element
    assert view["tags"]["Niveau"]["unit"] == "%"
    assert "script" not in view["svg"]


def test_bound_tag_cannot_be_deleted(api):
    did = _create(api)["drawing"]["id"]
    api.put(f"/api/drawings/{did}/bindings/Tank", json={"bindings": [{"tag": "Niveau", "anim": "level"}]})
    r = api.delete("/api/tags/Niveau")
    assert r.status_code == 409 and "binding" in r.json()["error"]
    api.put(f"/api/drawings/{did}/bindings/Tank", json={"bindings": []})
    assert api.delete("/api/tags/Niveau").status_code == 204


def test_delete_drawing(api):
    did = _create(api)["drawing"]["id"]
    assert api.delete(f"/api/drawings/{did}").status_code == 204
    assert api.get(f"/api/drawings/{did}").status_code == 404


def test_websocket_snapshot_delta_and_plc_status(api, mock_plc):
    mock_plc.state.hr[10] = 500
    with api.websocket_connect("/ws/live", headers=_ws_cookie(api)) as ws:
        ws.send_json({"type": "subscribe", "tags": ["Niveau"]})
        seen_snapshot = seen_plcs = False
        deadline = time.monotonic() + 10
        value = None
        while time.monotonic() < deadline and value != 50.0:
            msg = ws.receive_json()
            if msg["type"] == "snapshot":
                seen_snapshot = True
            elif msg["type"] == "plcs":
                seen_plcs = True
                assert "plc1" in msg["plcs"]
            if msg["type"] in ("snapshot", "delta") and "Niveau" in msg["values"]:
                assert set(msg["values"]) == {"Niveau"}  # Pumpe er ikke abonneret
                value = msg["values"]["Niveau"]["value"]
        assert seen_snapshot and value == pytest.approx(50.0)
        mock_plc.state.hr[10] = 700
        while True:
            msg = ws.receive_json()
            seen_plcs = seen_plcs or msg["type"] == "plcs"
            if msg["type"] == "delta" and "Niveau" in msg["values"]:
                assert msg["values"]["Niveau"]["value"] == pytest.approx(70.0)
                break
        while not seen_plcs:  # PLC-status sendes senest efter ~2 s
            seen_plcs = ws.receive_json()["type"] == "plcs"


def test_websocket_requires_login(api):
    from starlette.websockets import WebSocketDisconnect

    with api.websocket_connect("/ws/live", headers={"cookie": "scada_session=forkert"}) as ws:
        msg = ws.receive_json()
        assert msg == {"type": "error", "error": "Du er ikke logget ind"}
        with pytest.raises(WebSocketDisconnect) as info:
            ws.receive_json()
        assert info.value.code == 4401


def test_websocket_rejects_bad_message(api):
    with api.websocket_connect("/ws/live", headers=_ws_cookie(api)) as ws:
        ws.send_json({"type": "subscribe", "tags": "ikke-en-liste"})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "error":
                assert "subscribe" in msg["error"]
                break


def test_websocket_works_under_real_uvicorn(tmp_path):
    """Regression: uvicorn uden WS-bibliotek svarer 404 på /ws/live — TestClient fanger det ikke."""
    import asyncio
    import json

    import websockets

    from tests.conftest import _Server, free_port

    import httpx

    port = free_port()
    settings = Settings(data_dir=tmp_path, frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW)

    async def go() -> set[str]:
        async with httpx.AsyncClient() as http:
            r = await http.post(f"http://127.0.0.1:{port}/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
            cookie = f"scada_session={r.cookies['scada_session']}"
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws/live", additional_headers={"Cookie": cookie}) as ws:
            await ws.send(json.dumps({"type": "subscribe", "tags": []}))
            msgs = [json.loads(await asyncio.wait_for(ws.recv(), 5)) for _ in range(2)]
        return {m["type"] for m in msgs}

    with _Server(create_app(settings), port):
        assert "snapshot" in asyncio.run(go())


def test_start_drawing(api):
    a = _create(api, name="Anlæg A")["drawing"]["id"]
    b = _create(api, name="Anlæg B")["drawing"]["id"]
    assert not any(d["start"] for d in api.get("/api/drawings").json())  # ingen valgt → Overview viser den første
    r = api.put("/api/drawings/start", json={"drawing": b})
    assert r.status_code == 200 and r.json() == {"drawing": b}
    assert [d["id"] for d in api.get("/api/drawings").json() if d["start"]] == [b]
    assert any(e["action"] == "drawing.start" for e in api.get("/api/audit").json())
    # Ukendt tegning afvises med specifik fejl; tom streng = ingen start-tegning
    r = api.put("/api/drawings/start", json={"drawing": "findes-ikke"})
    assert r.status_code == 404 and "findes ikke" in r.json()["error"]
    assert api.put("/api/drawings/start", json={"drawing": "  "}).json() == {"drawing": None}
    # Slettes start-tegningen, nulstilles valget
    api.put("/api/drawings/start", json={"drawing": a})
    api.delete(f"/api/drawings/{a}")
    assert not any(d["start"] for d in api.get("/api/drawings").json())


def test_start_drawing_requires_engineer(api):
    api.post("/api/users", json={"username": "kigger", "role": "viewer", "password": "Hemmelig-123"})
    api.post("/api/auth/login", json={"username": "kigger", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert api.put("/api/drawings/start", json={"drawing": None}).status_code == 403
