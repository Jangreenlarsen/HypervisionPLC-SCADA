"""Adgang pr. tegning: begrænsede viewers/operatører ser og betjener kun deres tegninger."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"
SVG_A = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
         '<text id="Niveau_A">-</text><rect id="Knap_A" width="1" height="1"/><rect id="Til_B" width="1" height="1"/></svg>')
SVG_B = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
         '<text id="Niveau_B">-</text><rect id="Knap_B" width="1" height="1"/></svg>')


def _wait(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


@pytest.fixture
def setup(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        for t in [{"name": "Niveau_A", "source": "plc1:hr:1"}, {"name": "Niveau_B", "source": "plc1:hr:2"},
                  {"name": "Motor_A", "source": "plc1:coil:1", "writable": True},
                  {"name": "Motor_B", "source": "plc1:coil:2", "writable": True}]:
            assert c.post("/api/tags", json=t).status_code == 201
        a = c.post("/api/drawings", json={"name": "Anlæg A", "svg": SVG_A}).json()["drawing"]["id"]
        b = c.post("/api/drawings", json={"name": "Anlæg B", "svg": SVG_B}).json()["drawing"]["id"]
        c.put(f"/api/drawings/{a}/bindings/Knap_A", json={"bindings": [{"tag": "Motor_A", "anim": "click:toggle"}]})
        c.put(f"/api/drawings/{a}/bindings/Til_B", json={"bindings": [{"anim": "click:goto", "params": {"drawing": b}}]})
        c.put(f"/api/drawings/{b}/bindings/Knap_B", json={"bindings": [{"tag": "Motor_B", "anim": "click:toggle"}]})
        r = c.post("/api/users", json={"username": "op_a", "role": "operator", "password": "Hemmelig-123", "drawings": [a]})
        assert r.status_code == 201 and r.json()["drawings"] == [a]
        c.post("/api/auth/login", json={"username": "op_a", "password": "Hemmelig-123"})
        c.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
        _wait(lambda: c.get("/api/live?tags=Motor_A").json()["values"].get("Motor_A", {}).get("quality") == "good")
        yield c, a, b


def _as_admin(c):
    c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})


def _as_op(c):
    c.post("/api/auth/login", json={"username": "op_a", "password": "Hemmelig-123-ny"})


def test_scoped_user_sees_only_own_drawing(setup):
    c, a, b = setup
    assert c.get("/api/auth/me").json()["drawings"] == [a]
    assert [d["id"] for d in c.get("/api/drawings").json()] == [a]
    for path in (f"/api/drawings/{b}", f"/api/drawings/{b}/view", f"/api/drawings/{b}/svg", f"/api/drawings/{b}/bindings"):
        r = c.get(path)
        assert r.status_code == 404 and "findes ikke" in r.json()["error"], path
    view = c.get(f"/api/drawings/{a}/view").json()
    assert not any(x["anim"] == "click:goto" for x in view["bindings"])  # goto til B er fjernet


def test_scoped_user_sees_only_tags_in_own_drawing(setup):
    c, a, b = setup
    assert sorted(t["name"] for t in c.get("/api/tags").json()) == ["Motor_A", "Niveau_A"]  # Niveau_A via auto-binding
    assert c.get("/api/tags/Niveau_B").status_code == 404
    assert set(c.get("/api/live?tags=Niveau_A,Niveau_B,Motor_B").json()["values"]) == {"Niveau_A"}
    with c.websocket_connect("/ws/live", headers={"cookie": f"scada_session={c.cookies.get('scada_session')}"}) as ws:
        ws.send_json({"type": "subscribe", "tags": ["Niveau_A", "Niveau_B", "Motor_B"]})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "snapshot":
                assert set(msg["values"]) == {"Niveau_A"}
                break


def test_scoped_user_sees_flow_direction_tag(setup):
    """Et løbelys' retnings-tag hører til tegningen: en begrænset bruger skal have dets live-værdi."""
    c, a, b = setup
    _as_admin(c)
    assert c.put(f"/api/drawings/{a}/bindings/Niveau_A", json={"bindings": [
        {"tag": "Motor_A", "anim": "flow", "params": {"dir_tag": "Motor_B"}}]}).status_code == 200
    _as_op(c)
    assert "Motor_B" in {t["name"] for t in c.get("/api/tags").json()}
    assert "Motor_B" in c.get("/api/live?tags=Motor_B").json()["values"]


def test_scoped_user_sees_symbol_config_tags(setup):
    """Tags der kun bruges i et symbols konfiguration hører også til tegningen."""
    c, a, b = setup
    _as_admin(c)
    cfg = {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "Motor_B", "params": {}}]}
    r = c.put(f"/api/drawings/{a}/symbols/Knap_A/config", json={"config": cfg})
    assert r.status_code == 200, r.text
    _as_op(c)
    assert "Motor_B" in {t["name"] for t in c.get("/api/tags").json()}
    assert "Motor_B" in c.get("/api/live?tags=Motor_B").json()["values"]


def test_scoped_operator_can_only_operate_own_drawing(setup, mock_plc):
    c, a, b = setup
    assert c.post("/api/tags/Motor_A/toggle").status_code == 200
    r = c.post("/api/tags/Motor_B/toggle")
    assert r.status_code == 403 and "adgang" in r.json()["error"]
    r = c.post("/api/tags/Motor_B/write", json={"value": True})
    assert r.status_code == 403
    assert mock_plc.state.coils[2] is False
    _as_admin(c)
    denied = [e for e in c.get("/api/audit?limit=50").json() if e["target"] == "Motor_B" and e["action"] in ("write", "toggle")]
    assert denied and all(e["result"] == "error" for e in denied)  # afviste forsøg logges


def _ws_until(ws, predicate, timeout=5.0):
    """Læs beskeder indtil `predicate(msg)` er sand. Hver læsning har en tidsgrænse (i en tråd), så en manglende
    besked giver en fejl i stedet for en test der hænger. Lukkes forbindelsen → WebSocketDisconnect."""
    import concurrent.futures
    deadline = time.monotonic() + timeout
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise AssertionError("forventet besked kom ikke")
            try:
                msg = pool.submit(ws.receive_json).result(timeout=left)
            except concurrent.futures.TimeoutError:
                raise AssertionError("forventet besked kom ikke inden for tidsgrænsen") from None
            if predicate(msg):
                return msg
    finally:
        pool.shutdown(wait=False)  # en hængende læsning slippes når forbindelsen lukkes


def test_live_ws_follows_scope_change_and_deactivation(setup):
    """BUGS v0.27.0 #4: en åben /ws/live skal følge ændret tegningsadgang og lukke ved deaktivering."""
    from starlette.websockets import WebSocketDisconnect
    c, a, b = setup
    c.app.state.settings.ws_revalidate_s = 0.2
    op_cookie = {"cookie": f"scada_session={c.cookies.get('scada_session')}"}
    with c.websocket_connect("/ws/live", headers=op_cookie) as ws:
        ws.send_json({"type": "subscribe", "tags": ["Niveau_A", "Niveau_B"]})
        snap = _ws_until(ws, lambda m: m["type"] == "snapshot")
        assert set(snap["values"]) == {"Niveau_A"}
        _as_admin(c)                                     # samme klient; WebSocket'en bruger operatørens cookie
        assert c.patch("/api/users/op_a", json={"drawings": [a, b]}).status_code == 200
        snap = _ws_until(ws, lambda m: m["type"] == "snapshot")   # ny adgang → nyt snapshot uden ny subscribe
        assert set(snap["values"]) == {"Niveau_A", "Niveau_B"}
        assert c.patch("/api/users/op_a", json={"disabled": True}).status_code == 200
        msg = _ws_until(ws, lambda m: m["type"] == "error")
        assert "log ind igen" in msg["error"]
        with pytest.raises(WebSocketDisconnect) as closed:
            _ws_until(ws, lambda m: True)
        assert closed.value.code == 4401


def test_scope_changes_apply_immediately_and_null_means_all(setup):
    c, a, b = setup
    _as_admin(c)
    assert c.patch("/api/users/op_a", json={"drawings": [b]}).json()["drawings"] == [b]
    _as_op(c)
    assert [d["id"] for d in c.get("/api/drawings").json()] == [b]
    _as_admin(c)
    assert c.patch("/api/users/op_a", json={"drawings": None}).json()["drawings"] is None
    _as_op(c)
    assert {d["id"] for d in c.get("/api/drawings").json()} == {a, b}
    _as_admin(c)
    assert c.patch("/api/users/op_a", json={"drawings": []}).json()["drawings"] == []
    _as_op(c)
    assert c.get("/api/drawings").json() == []  # tom liste = ingen tegninger


def test_scope_validation_and_roles(setup):
    c, a, b = setup
    _as_admin(c)
    r = c.patch("/api/users/op_a", json={"drawings": ["findes-ikke"]})
    assert r.status_code == 400 and "findes-ikke" in r.json()["error"]
    # Tekniker ser altid alt, også selvom der er gemt en begrænsning
    c.post("/api/users", json={"username": "tek", "role": "engineer", "password": "Hemmelig-123", "drawings": [a]})
    c.post("/api/auth/login", json={"username": "tek", "password": "Hemmelig-123"})
    c.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert {d["id"] for d in c.get("/api/drawings").json()} == {a, b}
    assert c.get("/api/auth/me").json()["drawings"] is None


def test_deleting_drawing_removes_it_from_scope(setup):
    c, a, b = setup
    _as_admin(c)
    c.delete(f"/api/drawings/{a}")
    user = next(u for u in c.get("/api/users").json() if u["username"] == "op_a")
    assert user["drawings"] == []
    _as_op(c)
    assert c.get("/api/drawings").json() == []


def test_panel_role_has_operator_rights_and_scope_but_nothing_more(setup, mock_plc):
    """Driftpanel: samme rettigheder som operatør (betjening, begrænsning til tegninger) — ikke tekniker-rettigheder."""
    c, a, b = setup
    _as_admin(c)
    r = c.post("/api/users", json={"username": "panel1", "role": "panel", "password": "Hemmelig-123", "drawings": [a]})
    assert r.status_code == 201 and r.json()["role"] == "panel" and r.json()["drawings"] == [a]
    c.post("/api/auth/login", json={"username": "panel1", "password": "Hemmelig-123"})
    c.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    me = c.get("/api/auth/me").json()
    assert me["role"] == "panel" and me["drawings"] == [a]
    assert {d["id"] for d in c.get("/api/drawings").json()} == {a}
    assert c.post("/api/tags/Motor_A/toggle").status_code == 200          # betjener som en operatør
    assert c.post("/api/tags/Motor_B/toggle").status_code == 403          # men kun i sine tegninger
    assert c.post("/api/alarms/ack", json={"keys": None}).status_code == 200      # kan kvittere alarmer
    # Ingen tekniker-/admin-rettigheder
    assert c.post("/api/tags", json={"name": "X", "source": "plc1:hr:9"}).status_code == 403
    assert c.get("/api/users").status_code == 403
    assert c.put(f"/api/drawings/{a}/bindings/Knap_A", json={"bindings": []}).status_code == 403
    # Kan skiftes til operatør og tilbage; ukendt rolle afvises stadig
    _as_admin(c)
    assert c.patch("/api/users/panel1", json={"role": "operator"}).json()["role"] == "operator"
    assert c.patch("/api/users/panel1", json={"role": "panel"}).json()["role"] == "panel"
    assert c.patch("/api/users/panel1", json={"role": "kiosk"}).status_code == 400
