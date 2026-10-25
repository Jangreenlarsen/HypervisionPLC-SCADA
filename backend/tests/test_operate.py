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


@pytest.fixture
def api_short_timeout(tmp_path, mock_plc):
    """Som `api`, men med kort PLC-timeout, så et forsinket svar giver PlcUnreachable hurtigt."""
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9, plc_timeout_s=0.5,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        assert c.post("/api/tags", json={"name": "Motor", "source": "plc1:coil:3", "writable": True}).status_code == 201
        _wait(lambda: c.get("/api/live?tags=Motor").json()["values"]["Motor"]["quality"] == "good")
        yield c


def test_pulse_resets_output_when_on_write_times_out(api_short_timeout, mock_plc):
    """BUGS v0.27.0 #1: TÆND blev udført, men svaret gik tabt → serveren skal alligevel sende SLUK."""
    api = api_short_timeout
    mock_plc.state.writes.clear()
    mock_plc.state.slow_writes, mock_plc.state.slow_write_s = 1, 1.5
    r = api.post("/api/tags/Motor/pulse", json={"ms": 200})
    assert r.status_code == 503
    assert "sat til fra for en sikkerheds skyld" in r.json()["error"]
    assert mock_plc.state.writes == [("coil", 3, True), ("coil", 3, False)]
    assert mock_plc.state.coils[3] is False                       # udgangen er IKKE efterladt tændt
    entry = api.get("/api/audit?action=pulse").json()[0]
    assert entry["result"] == "error"


def test_pulse_rejected_by_plc_sends_no_reset(api, mock_plc):
    """Har PLC'en eksplicit afvist TÆND, skete intet — ingen ekstra SLUK (og ingen misvisende advarsel)."""
    mock_plc.state.writes.clear()
    mock_plc.state.reject_writes = "Safe mode aktiv"
    r = api.post("/api/tags/Motor/pulse", json={"ms": 200})
    assert r.status_code == 409 and "Safe mode aktiv" in r.json()["error"]
    assert mock_plc.state.writes == []


def test_concurrent_toggles_cancel_out(api, mock_plc):
    """BUGS v0.27.0 #2: to samtidige toggles skal give til→fra (ikke til to gange)."""
    import threading
    assert mock_plc.state.coils[3] is False
    mock_plc.state.writes.clear()
    mock_plc.state.slow_writes, mock_plc.state.slow_write_s = 2, 0.3   # hold låsen længe nok til at kaldene overlapper
    results = []
    threads = [threading.Thread(target=lambda: results.append(api.post("/api/tags/Motor/toggle"))) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    assert [w for w in mock_plc.state.writes if w[0] == "coil"] == [("coil", 3, True), ("coil", 3, False)]
    assert mock_plc.state.coils[3] is False
    assert sorted(r.json()["from"] for r in results) == [False, True]


def test_toggle_uses_fresh_plc_value_not_cache(api, mock_plc):
    """Ændres udgangen i PLC'en lige før et toggle (cachen er endnu ikke opdateret), skal toggle gå ud fra PLC'en."""
    mock_plc.state.coils[3] = True          # fx skiftet af PLC-programmet
    mock_plc.state.writes.clear()
    r = api.post("/api/tags/Motor/toggle")
    assert r.status_code == 200 and r.json()["from"] is True
    assert mock_plc.state.writes == [("coil", 3, False)]


def test_non_writable_and_unknown(api):
    r = api.post("/api/tags/Kun_laes/write", json={"value": 1})
    assert r.status_code == 403 and "ikke skrivbart" in r.json()["error"]
    assert api.post("/api/tags/Findes_ikke/write", json={"value": 1}).status_code == 404


def test_writable_only_for_hr_coil_and_st_variables(api):
    for body in ({"name": "X1", "source": "plc1:ir:1", "writable": True},
                 {"name": "X2", "source": "plc1:di:1", "writable": True}):
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


def _drawing_with(api, bindings):
    """Tegning hvor hvert element har ét klik (som admin)."""
    api.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    did = api.post("/api/drawings", json={"name": "Rettigheder", "svg": SVG}).json()["drawing"]["id"]
    for element, b in bindings.items():
        assert api.put(f"/api/drawings/{did}/bindings/{element}", json={"bindings": [b]}).status_code == 200
    return did


def test_operator_rights_follow_the_click_action(api, mock_plc):
    # Setpunkt har kun en til/fra-knap; Motor kun puls → ingen vilkårlig skrivning via API'et
    _drawing_with(api, {"Knap": {"tag": "Setpunkt", "anim": "click:toggle", "params": {"confirm": False}},
                        "Gaa": {"tag": "Motor", "anim": "click:pulse", "params": {"ms": 200}}})
    _login_as(api, "op2", "operator")
    r = api.post("/api/tags/Setpunkt/write", json={"value": 55})
    assert r.status_code == 403 and "adgang" in r.json()["error"]
    assert api.post("/api/tags/Motor/toggle").status_code == 403
    assert api.post("/api/tags/Setpunkt/toggle").status_code == 200
    assert api.post("/api/tags/Motor/pulse", json={"ms": 200}).status_code == 200


def test_selector_operator_may_only_write_its_positions(api, mock_plc):
    pos = [{"value": 0, "label": "Hånd"}, {"value": 10, "label": "0"}, {"value": 20, "label": "Auto"}]
    _drawing_with(api, {"Setpunkt": {"tag": "Setpunkt", "anim": "click:select", "params": {"positions": pos}}})
    _login_as(api, "op3", "operator")
    assert api.post("/api/tags/Setpunkt/write", json={"value": 20}).status_code == 200
    _wait(lambda: mock_plc.state.hr[5] == 200)  # skala 0,1
    r = api.post("/api/tags/Setpunkt/write", json={"value": 15})
    assert r.status_code == 403 and r.json()["error"] == "Værdien 15 er ikke en af omskifterens positioner (0, 10, 20)"
    api.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    denied = [e for e in api.get("/api/audit").json() if e["username"] == "op3" and e["result"] == "error"]
    assert denied and "positioner" in denied[0]["message"]
    assert api.post("/api/tags/Setpunkt/write", json={"value": 15}).status_code == 200  # tekniker/admin: frit inden for min/max


# ------------------------------------------------------------------ ST-variabler (PLC-firmware FEAT-503, v1.7.0)

def test_write_st_variable_and_global(api, mock_plc):
    assert api.post("/api/tags", json={"name": "ST_Start", "source": "plc1:logic:1:Starter", "writable": True}).status_code == 201
    assert api.post("/api/tags", json={"name": "ST_Pumpe", "source": "plc1:logic:1:PumpeKoerer", "writable": True}).status_code == 201
    assert api.post("/api/tags", json={"name": "G_Mode", "source": "plc1:global:Mode", "writable": True}).status_code == 201
    r = api.post("/api/tags/ST_Start/write", json={"value": 12})
    assert r.status_code == 200 and r.json()["written"] == 12 and r.json()["readback"] == 12, r.text
    assert mock_plc.state.programs[1]["variables"][2]["value"] == 12
    r = api.post("/api/tags/G_Mode/write", json={"value": 3})
    assert r.status_code == 200 and r.json()["readback"] == 3
    assert mock_plc.state.globals[0]["value"] == 3
    # til/fra-variabel: skift læser den aktuelle værdi og skriver det modsatte
    mock_plc.state.programs[1]["variables"][1]["value"] = True
    r = api.post("/api/tags/ST_Pumpe/toggle")
    assert r.status_code == 200 and r.json()["written"] is False and mock_plc.state.programs[1]["variables"][1]["value"] is False
    # PLC'ens områdetjek når frem til brugeren
    r = api.post("/api/tags/ST_Start/write", json={"value": 70000})
    assert r.status_code == 409 and "range" in r.json()["error"], r.text   # PLC-afvisninger meldes som 409


def test_write_st_variable_errors_are_specific(api, mock_plc):
    api.post("/api/tags", json={"name": "ST_Start", "source": "plc1:logic:1:Starter", "writable": True})
    api.post("/api/tags", json={"name": "ST_Ukendt", "source": "plc1:logic:1:FindesIkke", "writable": True})
    r = api.post("/api/tags/ST_Ukendt/write", json={"value": 1})
    assert "not found" in r.json()["error"] and "firmwaren" not in r.json()["error"]
    mock_plc.state.bindings = [{"program": 1, "name": "Starter", "type": "INT", "direction": "input", "word_count": 1,
                                "register_type": "DI", "register_addr": 3}]
    r = api.post("/api/tags/ST_Start/write", json={"value": 1})
    assert r.status_code == 409 and "digitalt input" in r.json()["error"], r.text   # DI kan kun læses
    mock_plc.state.bindings = []
    mock_plc.state.var_write = False   # ældre firmware uden endpointet
    r = api.post("/api/tags/ST_Start/write", json={"value": 1})
    assert r.status_code >= 400 and "v7.9.68.141" in r.json()["error"], r.text


def test_to_raw_for_st_variables_scales_and_keeps_type():
    src = parse_source("plc1:logic:1:X")
    assert to_raw(5, src, 1.0, 0.0) == (5, 5)
    assert to_raw(True, src, 1.0, 0.0) == (True, True)
    assert to_raw(2.5, src, 1.0, 0.0) == (2.5, 2.5)
    assert to_raw(50, src, 0.1, 0.0) == (500, 50)
    with pytest.raises(ServiceError):
        to_raw("x", src, 1.0, 0.0)


def test_st_variable_bound_as_input_is_written_through_its_register(api, mock_plc):
    """Regression (v1.9.2): en ST-variabel bundet som INPUT (↔ Begge) afvises af PLC'en ("bound as INPUT from HR 18") — SCADA skriver
    så det register, bindingen læser fra, i stedet for at give en fejl."""
    st = mock_plc.state
    bind = lambda name, typ, kind, addr: {"program": 1, "name": name, "type": typ, "direction": "input", "word_count": 1,   # noqa: E731
                                          "register_type": kind, "register_addr": addr}
    st.programs[1]["variables"] += [{"index": 3, "name": "Mode", "type": "INT", "value": 0},
                                    {"index": 4, "name": "Stor", "type": "DINT", "value": 0},
                                    {"index": 5, "name": "Maal", "type": "REAL", "value": 0.0},
                                    {"index": 6, "name": "Flag", "type": "BOOL", "value": False}]
    st.bindings = [bind("Mode", "INT", "HR", 18), bind("Stor", "DINT", "HR", 40), bind("Maal", "REAL", "HR", 50),
                   bind("Flag", "BOOL", "Coil", 7)]
    for name, src in (("T_Mode", "Mode"), ("T_Stor", "Stor"), ("T_Maal", "Maal"), ("T_Flag", "Flag")):
        assert api.post("/api/tags", json={"name": name, "source": f"plc1:logic:1:{src}", "writable": True}).status_code == 201
    var = lambda n: next(v for v in st.programs[1]["variables"] if v["name"] == n)["value"]   # noqa: E731
    r = api.post("/api/tags/T_Mode/write", json={"value": 2})
    assert r.status_code == 200 and r.json()["matches"] is True, r.text
    assert st.hr[18] == 2 and var("Mode") == 2
    r = api.post("/api/tags/T_Mode/write", json={"value": -3})
    assert st.hr[18] == 65533 and var("Mode") == -3 and r.json()["matches"] is True      # INT: to's komplement
    assert api.post("/api/tags/T_Stor/write", json={"value": -70000}).json()["matches"] is True
    assert var("Stor") == -70000 and st.hr[40] == (-70000 & 0xFFFF) and st.hr[41] == ((-70000 & 0xFFFFFFFF) >> 16)   # lav ord først
    assert api.post("/api/tags/T_Maal/write", json={"value": 12.5}).json()["matches"] is True and var("Maal") == 12.5
    assert api.post("/api/tags/T_Flag/write", json={"value": True}).json()["matches"] is True
    assert st.coils[7] is True and var("Flag") is True
    # audit nævner registret
    api_audit = [e for e in api.get("/api/audit?limit=20").json() if e["target"] == "T_Mode"]
    assert api_audit and api_audit[0]["detail"].get("via_register") == "HR 18"
