"""Betjening: skriv/toggle/puls mod mock-PLC'en, roller, læs-tilbage, PLC-fejl og audit."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.errors import ServiceError
from app.services.operate import to_raw
from app.services.tagsource import parse_source

ADMIN_PW = "test-admin-pw-1"
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
       '<rect id="Knap" width="10" height="10"/><rect id="Setpunkt" width="10" height="10"/>'
       '<rect id="Gaa" width="10" height="10"/></svg>')


def _wait(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        for tag in [
            {"name": "Setpunkt", "source": "plc1:hr:5", "scale": 0.1, "unit": "°C", "writable": True,
             "min": 0, "max": 80},
            {"name": "Motor", "source": "plc1:coil:3", "writable": True},
            {"name": "Flow", "source": "plc1:hr:20:real", "writable": True},
            {"name": "Kun_laes", "source": "plc1:hr:6"},
        ]:
            assert c.post("/api/tags", json=tag).status_code == 201, tag
        _wait(lambda: c.get("/api/live?tags=Motor").json()["values"]["Motor"]["quality"] == "good")
        yield c


def _login_as(api, username, role):
    """Opret bruger (som admin) og log ind som den på SAMME klient — en ekstra TestClient
    ville køre i sin egen event-loop, mens PLC-forbindelsen lever i appens loop."""
    api.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    api.post("/api/users", json={"username": username, "role": role, "password": "Hemmelig-123"})
    api.post("/api/auth/login", json={"username": username, "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})


# ---------------------------------------------------------------- ren logik

@pytest.mark.parametrize("value, source, scale, offset, raw, actual", [
    (21.5, "plc1:hr:1", 0.1, 0, 215, 21.5),
    (21.56, "plc1:hr:1", 0.1, 0, 216, pytest.approx(21.6)),        # afrundes til nærmeste rå værdi
    (-5, "plc1:hr:1:int", 1, 0, -5, -5),
    (0, "plc1:hr:1", 1, 0, 0, 0),                                   # 0 er en gyldig værdi
    (3.25, "plc1:hr:1:real", 1, 0, 3.25, 3.25),
    (True, "plc1:coil:1", 1, 0, True, True),
    (0, "plc1:coil:1", 1, 0, False, False),
])
def test_to_raw(value, source, scale, offset, raw, actual):
    r, a = to_raw(value, parse_source(source), scale, offset)
    assert r == raw and a == actual


@pytest.mark.parametrize("value, source, message", [
    (-1, "plc1:hr:1", "uden for uint"),
    (70000, "plc1:hr:1", "uden for uint"),
    (40000, "plc1:hr:1:int", "uden for int"),
    ("x", "plc1:hr:1", "et tal"),
    (float("nan"), "plc1:hr:1", "et tal"),
    (2, "plc1:coil:1", "til eller fra"),
])
def test_to_raw_rejects(value, source, message):
    with pytest.raises(ServiceError, match=message):
        to_raw(value, parse_source(source), 1, 0)


# ------------------------------------------------------------------- via API

def test_write_scaled_setpoint_and_readback(api, mock_plc):
    r = api.post("/api/tags/Setpunkt/write", json={"value": 21.5})
    assert r.status_code == 200, r.text
    assert r.json() == {"tag": "Setpunkt", "written": 21.5, "readback": 21.5, "matches": True, "warning": ""}
    assert mock_plc.state.hr[5] == 215
    _wait(lambda: api.get("/api/live?tags=Setpunkt").json()["values"]["Setpunkt"]["value"] == pytest.approx(21.5))


def test_min_max_enforced_in_backend(api, mock_plc):
    r = api.post("/api/tags/Setpunkt/write", json={"value": 90})
    assert r.status_code == 400 and "over maksimum 80" in r.json()["error"]
    r = api.post("/api/tags/Setpunkt/write", json={"value": -0.5})
    assert r.status_code == 400 and "under minimum 0" in r.json()["error"]
    assert api.post("/api/tags/Setpunkt/write", json={"value": 0}).status_code == 200  # grænsen selv er OK
    assert mock_plc.state.writes == [("hr", 5, 0)]


def test_real_and_coil_write(api, mock_plc):
    assert api.post("/api/tags/Flow/write", json={"value": 12.75}).json()["readback"] == pytest.approx(12.75)
    assert api.post("/api/tags/Motor/write", json={"value": True}).json()["readback"] is True
    assert mock_plc.state.coils[3] is True


def test_readback_mismatch_is_reported_not_hidden(api, mock_plc):
    mock_plc.state.locks[("hr", 5)] = 100  # "ST-programmet" holder HR5 på 100
    r = api.post("/api/tags/Setpunkt/write", json={"value": 30}).json()
    assert r["matches"] is False and r["readback"] == pytest.approx(10.0)
    assert "overskrevet" in r["warning"]


def test_plc_rejection_message_reaches_operator(api, mock_plc):
    mock_plc.state.reject_writes = "Safe mode aktiv — udgange er laast"
    r = api.post("/api/tags/Motor/write", json={"value": True})
    assert r.status_code == 409 and "Safe mode aktiv" in r.json()["error"]


def test_toggle_and_pulse(api, mock_plc):
    r = api.post("/api/tags/Motor/toggle")
    assert r.status_code == 200 and r.json()["from"] is False and mock_plc.state.coils[3] is True
    entry = api.get("/api/audit?action=toggle").json()[0]
    assert entry["target"] == "Motor" and entry["detail"]["old"] is False and entry["detail"]["written"] is True
    _wait(lambda: api.get("/api/live?tags=Motor").json()["values"]["Motor"]["value"] is True)
    mock_plc.state.writes.clear()
    r = api.post("/api/tags/Motor/pulse", json={"ms": 200})
    assert r.status_code == 200
    assert mock_plc.state.writes == [("coil", 3, True), ("coil", 3, False)]  # nulstillet af serveren
    r = api.post("/api/tags/Flow/pulse", json={"ms": 200})
    assert r.status_code == 400 and "til/fra" in r.json()["error"]
    assert api.post("/api/tags/Motor/pulse", json={"ms": 50}).status_code == 422


def test_non_writable_and_unknown(api):
    r = api.post("/api/tags/Kun_laes/write", json={"value": 1})
    assert r.status_code == 403 and "ikke skrivbart" in r.json()["error"]
    assert api.post("/api/tags/Findes_ikke/write", json={"value": 1}).status_code == 404


def test_writable_only_for_hr_and_coil(api):
    for body in ({"name": "X1", "source": "plc1:ir:1", "writable": True},
                 {"name": "X2", "source": "plc1:di:1", "writable": True},
                 {"name": "X3", "source": "plc1:logic:1:Niveau", "writable": True}):
        r = api.post("/api/tags", json=body)
        assert r.status_code == 400 and "kun-læs" in r.json()["error"], body
    # samme regel ved opdatering: skrivbart tag må ikke få en kun-læs kilde ...
    r = api.patch("/api/tags/Setpunkt", json={"source": "plc1:ir:5"})
    assert r.status_code == 400 and "kun-læs" in r.json()["error"]
    # ... og et kun-læs tag må ikke gøres skrivbart
    api.post("/api/tags", json={"name": "Input", "source": "plc1:ir:2"})
    assert api.patch("/api/tags/Input", json={"writable": True}).status_code == 400
    # ... og ved import
    r = api.post("/api/tags/import", json={"tags": [{"name": "X4", "source": "plc1:ir:3", "writable": True}]})
    assert r.json()["created"] == [] and "kun-læs" in r.json()["skipped"][0]["reason"]


def test_roles(api, mock_plc):
    _login_as(api, "vaegskaerm", "viewer")
    r = api.post("/api/tags/Setpunkt/write", json={"value": 20})
    assert r.status_code == 403 and "operator" in r.json()["error"]
    _login_as(api, "operatoer", "operator")
    # Operatører kan kun betjene tags med en klik-handling i en tegning de har adgang til
    r = api.post("/api/tags/Setpunkt/write", json={"value": 20})
    assert r.status_code == 403 and "klik-handling" in r.json()["error"]
    api.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    did = api.post("/api/drawings", json={"name": "Betjening", "svg": SVG}).json()["drawing"]["id"]
    api.put(f"/api/drawings/{did}/bindings/Setpunkt", json={"bindings": [{"tag": "Setpunkt", "anim": "click:write"}]})
    api.post("/api/auth/login", json={"username": "operatoer", "password": "Hemmelig-123-ny"})
    assert api.post("/api/tags/Setpunkt/write", json={"value": 20}).status_code == 200
    assert api.get("/api/audit").status_code == 403
    r = api.post("/api/tags", json={"name": "Y", "source": "plc1:hr:9"})
    assert r.status_code == 403  # operatør må betjene, ikke konfigurere


def test_audit_log(api, mock_plc):
    api.post("/api/tags/Setpunkt/write", json={"value": 25})
    api.post("/api/tags/Setpunkt/write", json={"value": 999})
    api.patch("/api/plcs/plc1", json={"password": "scada123"})
    log = api.get("/api/audit?limit=50").json()
    writes = [e for e in log if e["action"] == "write"]
    assert writes[0]["result"] == "error" and "maksimum" in writes[0]["message"]
    assert writes[1]["result"] == "ok" and writes[1]["detail"]["written"] == 25 and writes[1]["username"] == "admin"
    plc_update = next(e for e in log if e["action"] == "plc.update")
    assert plc_update["detail"]["password"] == "***"  # hemmeligheder logges aldrig
    assert "scada123" not in str(log)
    assert any(e["action"] == "login" for e in log)
    assert all(e["action"] == "write" for e in api.get("/api/audit?action=write").json())


def test_click_binding_validation(api):
    did = api.post("/api/drawings", json={"name": "Betjening", "svg": SVG}).json()["drawing"]["id"]
    put = lambda el, b: api.put(f"/api/drawings/{did}/bindings/{el}", json={"bindings": b})  # noqa: E731
    assert put("Knap", [{"tag": "Motor", "anim": "fill"}, {"tag": "Motor", "anim": "click:toggle"}]).status_code == 200
    r = put("Setpunkt", [{"tag": "Kun_laes", "anim": "click:write"}])
    assert r.status_code == 400 and "ikke markeret skrivbart" in r.json()["error"]
    r = put("Setpunkt", [{"tag": "Flow", "anim": "click:toggle"}])
    assert r.status_code == 400 and "til/fra" in r.json()["error"]
    r = put("Knap", [{"tag": "Motor", "anim": "click:toggle"}, {"tag": "Motor", "anim": "click:pulse"}])
    assert r.status_code == 400 and "én klik-handling" in r.json()["error"]
    r = put("Gaa", [{"anim": "click:goto", "params": {"drawing": "findes-ikke"}}])
    assert r.status_code == 400 and "findes ikke" in r.json()["error"]
    assert put("Gaa", [{"anim": "click:goto", "params": {"drawing": did}}]).status_code == 200
    r = put("Knap", [{"tag": "Motor", "anim": "click:pulse", "params": {"ms": 50}}])
    assert r.status_code == 400
    view = api.get(f"/api/drawings/{did}/view").json()
    assert view["tags"]["Motor"]["writable"] is True and view["tags"]["Motor"]["kind"] == "coil"
    assert "" not in view["tags"]  # goto-bindingen har intet tag


def test_limit_messages_without_trailing_zero(api):
    # 80.0 → "80": tal i fejlbeskeder skrives som brugeren tastede dem
    r = api.post("/api/tags/Setpunkt/write", json={"value": 95})
    assert r.status_code == 400 and r.json()["error"] == "Værdien 95 er over maksimum 80"
    r = api.patch("/api/tags/Setpunkt", json={"min": 90})
    assert r.json()["error"] == "min (90) må ikke være større end max (80)"
