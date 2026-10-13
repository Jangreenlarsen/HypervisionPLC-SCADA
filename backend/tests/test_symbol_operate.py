"""Symbolstandard fase 3: betjening — skriveplan, break-before-make, stop ved fejl, puls med hvile, fejl/låst,
nøglelås, samtidighed, accept, trykknap/setpunkt, adgang og forhåndsvisning."""

import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.test_symbols import ADMIN_PW, SVG, TAGS, dec_bin

V1 = "V1"


def _wait(predicate, timeout=6.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


def _client(tmp_path, timeout_s=5.0):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.1, plc_rate=9, symbol_tick_s=0.1,
                        alarm_tick_s=0.1, plc_timeout_s=timeout_s, frontend_dir=tmp_path / "nope",
                        admin_password=ADMIN_PW, backup_hours=0)
    return TestClient(create_app(settings))


def _setup(c, mock_plc, config=None, element=V1, pin=None):
    c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                              "password": "scada123", "sse_enabled": False})
    for t in TAGS:
        c.post("/api/tags", json=t)
    did = c.post("/api/drawings", json={"name": "Anlæg", "svg": SVG}).json()["drawing"]["id"]
    body = {"config": config or dec_bin(display="remote")}
    if pin:
        body["pin"] = pin
    r = c.put(f"/api/drawings/{did}/symbols/{element}/config", json=body)
    assert r.status_code == 200, r.text
    names = [t["name"] for t in TAGS]
    _wait(lambda: all(v["quality"] == "good" for v in c.get(f"/api/live?tags={','.join(names)}").json()["values"].values()))
    c.did = did
    return did


def _op(c, position, pin=None, element=V1):
    body = {"position": position}
    if pin is not None:
        body["pin"] = pin
    return c.post(f"/api/drawings/{c.did}/symbols/{element}/operate", json=body)


def _coil_writes(mock_plc):
    return [(a, v) for k, a, v in mock_plc.state.writes if k == "coil"]


def _set_bits(mock_plc, n):
    mock_plc.state.coils[10], mock_plc.state.coils[11], mock_plc.state.coils[12] = bool(n & 1), bool(n & 2), bool(n & 4)
    mock_plc.state.di[10] = bool(n & 1)


@pytest.fixture
def api(tmp_path, mock_plc):
    with _client(tmp_path) as c:
        yield c


# ------------------------------------------------------------------ skriveplan

def test_break_before_make_and_only_changed_signals(api, mock_plc):
    _set_bits(mock_plc, 1)                    # position 1: Bit0=1
    _setup(api, mock_plc)
    _wait(lambda: api.app.state.symbol_runtime.state(api.did, V1) and api.app.state.symbol_runtime.state(api.did, V1).pos == 0)
    mock_plc.state.writes.clear()
    r = _op(api, 5)                           # position 6 = 110: Bit0 0 (først), Bit1 1, Bit2 1
    assert r.status_code == 200, r.text
    assert _coil_writes(mock_plc) == [(10, False), (11, True), (12, True)]
    assert [w["tag"] for w in r.json()["writes"]] == ["Bit0", "Bit1", "Bit2"]
    entry = api.get("/api/audit?action=symbol.operate").json()[0]
    assert entry["result"] == "ok" and entry["detail"]["position"] == "6" and entry["detail"]["from"] == "1"
    # PLC'en melder tilbage (DI 10 følger coil 10 — det gør mock-PLC'en ikke selv)
    mock_plc.state.di[10] = mock_plc.state.coils[10]
    # Allerede i position 6 → kun det der mangler skrives (intet)
    _wait(lambda: api.app.state.symbol_runtime.state(api.did, V1).pos == 5)
    mock_plc.state.writes.clear()
    assert _op(api, 5).status_code == 200 and _coil_writes(mock_plc) == []


def test_plan_endpoint_shows_writes_without_writing(api, mock_plc):
    _set_bits(mock_plc, 1)
    _setup(api, mock_plc)
    mock_plc.state.writes.clear()
    r = api.get(f"/api/drawings/{api.did}/symbols/{V1}/plan/5")
    assert r.status_code == 200 and [(w["tag"], w["value"]) for w in r.json()["writes"]] == [("Bit0", 0), ("Bit1", 1), ("Bit2", 1)]
    assert mock_plc.state.writes == []


def test_failed_write_stops_the_plan_and_reports_exactly(api, mock_plc):
    _set_bits(mock_plc, 1)
    _setup(api, mock_plc)
    mock_plc.state.writes.clear()
    mock_plc.state.reject_addr[("coil", 12)] = "Udgang låst af PLC-program"
    r = _op(api, 5)
    assert r.status_code == 409
    body = r.json()
    assert "Udgang låst af PLC-program" in body["error"] and "Skrevet: Bit0, Bit1" in body["error"]
    assert "ikke skrevet: Bit2" in body["error"] and body["not_written"] == ["Bit2"]
    assert _coil_writes(mock_plc) == [(10, False), (11, True)]          # intet rulles tilbage
    assert api.get("/api/audit?action=symbol.operate").json()[0]["result"] == "error"
    assert (api.app.state.symbol_runtime.chosen.get((api.did, V1)) or {}).get("chosen") != 5


def test_register_pulse_writes_value_then_rest(api, mock_plc):
    cfg = dec_bin(display="remote", signals=[{"id": "S1", "tag": "Mode", "fb": "Mode_fb"},
                                             {"id": "S2", "tag": "Kommando", "write": "pulse", "ms": 200, "rest": 0}],
                  positions=[{"label": "Hand"}, {"label": "0"}, {"label": "Auto"}],
                  planes=[{"signal": "S1", "values": [0, 1, 2]}, {"signal": "S2", "values": [11, 12, 13]}],
                  anims=[])
    _setup(api, mock_plc, cfg)
    mock_plc.state.writes.clear()
    r = _op(api, 2)
    assert r.status_code == 200, r.text
    hr = [(a, v) for k, a, v in mock_plc.state.writes if k == "hr"]
    assert hr == [(30, 2), (33, 13), (33, 0)]                # sæt Mode, puls 13 → hvile 0


PULSE_CFG = dec_bin(display="remote", signals=[{"id": "S1", "tag": "Mode"},
                                               {"id": "S2", "tag": "Kommando", "write": "pulse", "ms": 200, "rest": 0}],
                    positions=[{"label": "A"}, {"label": "B"}],
                    planes=[{"signal": "S1", "values": [0, 1]}, {"signal": "S2", "values": [11, 12]}], anims=[])


def test_register_pulse_writes_rest_even_when_value_times_out(tmp_path, mock_plc):
    """Udfaldet af pulsværdien er ukendt (svaret tabt) → hvileværdien skrives alligevel."""
    with _client(tmp_path, timeout_s=0.5) as c:
        mock_plc.state.hr[30] = 1                  # Mode står allerede på B → planen er kun pulsen
        _setup(c, mock_plc, PULSE_CFG)
        mock_plc.state.writes.clear()
        mock_plc.state.slow_writes, mock_plc.state.slow_write_s = 1, 1.0
        r = _op(c, 1)
        assert r.status_code == 503 and "hvileværdien er skrevet" in r.json()["error"]
        assert [(a, v) for k, a, v in mock_plc.state.writes if k == "hr"] == [(33, 12), (33, 0)]
        assert mock_plc.state.hr[33] == 0


def test_timeout_on_set_write_stops_plan_before_pulse(tmp_path, mock_plc):
    with _client(tmp_path, timeout_s=0.5) as c:
        _setup(c, mock_plc, PULSE_CFG)
        mock_plc.state.writes.clear()
        mock_plc.state.slow_writes, mock_plc.state.slow_write_s = 1, 1.0   # Mode svarer for sent
        r = _op(c, 1)
        assert r.status_code == 503 and r.json()["not_written"] == ["Kommando"] and r.json()["uncertain"] == ["Mode"]
        assert "usikkert (intet svar fra PLC'en): Mode" in r.json()["error"]
        assert [(a, v) for k, a, v in mock_plc.state.writes if k == "hr"] == [(30, 1)]


# ------------------------------------------------------------------ blokering, samtidighed, adgang

def test_fault_tag_blocks_operation(api, mock_plc):
    _setup(api, mock_plc, dec_bin(display="remote", fault="Fejl"))
    mock_plc.state.di[11] = True
    _wait(lambda: api.get("/api/live?tags=Fejl").json()["values"]["Fejl"]["value"] is True)
    mock_plc.state.writes.clear()
    r = _op(api, 3)
    assert r.status_code == 409 and "Fejl er aktiv" in r.json()["error"] and mock_plc.state.writes == []


def test_concurrent_operation_is_refused(api, mock_plc):
    _set_bits(mock_plc, 1)
    _setup(api, mock_plc)
    mock_plc.state.slow_writes, mock_plc.state.slow_write_s = 3, 0.4
    results = []
    t1 = threading.Thread(target=lambda: results.append(_op(api, 5)))
    t1.start()
    time.sleep(0.15)
    results.append(_op(api, 2))
    t1.join()
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 409], [r.text for r in results]
    assert any("betjenes allerede" in r.text for r in results)


def test_operator_needs_drawing_access_and_viewer_cannot_operate(api, mock_plc):
    did = _setup(api, mock_plc)
    other = api.post("/api/drawings", json={"name": "Andet", "svg": SVG}).json()["drawing"]["id"]
    for name, role, drawings in (("vis", "viewer", None), ("op_b", "operator", [other])):
        body = {"username": name, "role": role, "password": "Hemmelig-123"}
        if drawings:
            body["drawings"] = drawings
        api.post("/api/users", json=body)
    api.post("/api/auth/login", json={"username": "vis", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert _op(api, 1).status_code == 403
    api.post("/api/auth/login", json={"username": "op_b", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    r = _op(api, 1)
    assert r.status_code == 404 and "findes ikke" in r.json()["error"]
    # og symbolets kommando-tags kan ikke skrives uden om positionerne
    assert api.post("/api/tags/Bit1/write", json={"value": True}).status_code == 403


# ------------------------------------------------------------------ nøglelås

def test_locked_position_needs_pin_with_lockout(api, mock_plc):
    _set_bits(mock_plc, 1)
    cfg = dec_bin(display="remote", lock={"positions": [False] * 5 + [True, False], "leave": False})
    _setup(api, mock_plc, cfg, pin="4711")
    mock_plc.state.writes.clear()
    r = _op(api, 5)
    assert r.status_code == 403 and "indtast koden" in r.json()["error"]
    assert _op(api, 5, "0000").json()["error"] == "Forkert kode (1 af 3 forsøg)"
    assert _op(api, 5, "1111").status_code == 403
    r = _op(api, 5, "2222")
    assert r.status_code == 429 and "spærret i 60 s" in r.json()["error"]
    r = _op(api, 5, "4711")                                 # rigtig kode, men stadig spærret
    assert r.status_code == 429 and "prøv igen om" in r.json()["error"]
    assert mock_plc.state.writes == []
    api.app.state.symbol_operate_service._pin_fails.clear()   # (spærringen udløber)
    assert _op(api, 5, "4711").status_code == 200
    log = api.get("/api/audit?limit=50").json()
    assert [e["action"] for e in log if e["action"] in ("symbol.unlock",)] == ["symbol.unlock"]
    assert sum(e["action"] == "symbol.pin_failed" for e in log) == 3
    assert "4711" not in str(log) and "2222" not in str(log)
    # Uden lås skiftes frit
    assert _op(api, 1).status_code == 200


def test_leaving_locked_position_needs_pin_when_chosen(api, mock_plc):
    _set_bits(mock_plc, 1)
    cfg = dec_bin(display="remote", lock={"positions": [True] + [False] * 6, "leave": True})
    _setup(api, mock_plc, cfg, pin="1234")
    _wait(lambda: api.app.state.symbol_runtime.state(api.did, V1) and api.app.state.symbol_runtime.state(api.did, V1).pos == 0)
    assert _op(api, 3).status_code == 403
    assert _op(api, 3, "1234").status_code == 200


# ------------------------------------------------------------------ accept, trykknap, setpunkt

def test_accept_takes_plc_position_and_writes_nothing(api, mock_plc):
    _set_bits(mock_plc, 3)
    _setup(api, mock_plc, dec_bin(display="local", validate_s=1, alarm="medium"))
    rt = api.app.state.symbol_runtime
    _wait(lambda: rt.state(api.did, V1) and rt.state(api.did, V1).state == "confirmed")
    rt.set_chosen((api.did, V1), 6, "olsen")
    _wait(lambda: rt.state(api.did, V1).state == "mismatch")
    mock_plc.state.writes.clear()
    r = api.post(f"/api/drawings/{api.did}/symbols/{V1}/accept")
    assert r.status_code == 200 and r.json()["label"] == "3"
    assert mock_plc.state.writes == [] and rt.state(api.did, V1).state == "confirmed"
    assert api.post(f"/api/drawings/{api.did}/symbols/{V1}/accept").status_code == 409


def test_pulse_and_entry_symbols(api, mock_plc):
    did = _setup(api, mock_plc, {"op": "pulse", "signals": [{"id": "S1", "tag": "Bit2"}], "pulse_ms": 150,
                                 "anims": [{"part": "Lampe_glas", "type": "fill", "src": "Bit2"}]}, element="Lampe")
    mock_plc.state.writes.clear()
    r = api.post(f"/api/drawings/{did}/symbols/Lampe/pulse")
    assert r.status_code == 200 and _coil_writes(mock_plc) == [(12, True), (12, False)]
    api.put(f"/api/drawings/{did}/symbols/Lampe/config",
            json={"config": {"op": "entry", "signals": [{"id": "S1", "tag": "Setpunkt"}]}})
    r = api.post(f"/api/drawings/{did}/symbols/Lampe/entry", json={"value": 150})
    assert r.status_code == 400 and "over maksimum 100" in r.json()["error"]
    r = api.post(f"/api/drawings/{did}/symbols/Lampe/entry", json={"value": 42})
    assert r.status_code == 200 and r.json()["written"] == 42
    # forkert betjeningsform
    r = api.post(f"/api/drawings/{did}/symbols/Lampe/pulse")
    assert r.status_code == 409 and "setpunkt" in r.json()["error"]


# ------------------------------------------------------------------ gamle bindinger og forhåndsvisning

def test_configured_symbol_ignores_old_bindings(api, mock_plc):
    did = _setup(api, mock_plc)
    api.delete(f"/api/drawings/{did}/symbols/{V1}/config")
    assert api.put(f"/api/drawings/{did}/bindings/V1_greb",
                   json={"bindings": [{"tag": "Lys", "anim": "fill"}]}).status_code == 200
    assert any(b["element"] == "V1_greb" for b in api.get(f"/api/drawings/{did}/view").json()["bindings"])
    api.put(f"/api/drawings/{did}/symbols/{V1}/config", json={"config": dec_bin()})
    assert not any(b["element"] == "V1_greb" and b["tag"] == "Lys"
                   for b in api.get(f"/api/drawings/{did}/view").json()["bindings"])


def test_preview_returns_plans_and_errors_without_saving(api, mock_plc):
    did = _setup(api, mock_plc)
    api.delete(f"/api/drawings/{did}/symbols/{V1}/config")
    r = api.post(f"/api/drawings/{did}/symbols/{V1}/preview", json={"config": dec_bin()})
    assert r.status_code == 200 and r.json()["errors"] == 0
    plans = r.json()["plans"]
    assert len(plans) == 7 and [(w["tag"], w["value"]) for w in plans[0]["writes"]] == [("Bit1", 0), ("Bit2", 0), ("Bit0", 1)]
    bad = dec_bin()
    bad["signals"][0]["tag"] = "Lys"
    r = api.post(f"/api/drawings/{did}/symbols/{V1}/preview", json={"config": bad})
    assert r.json()["errors"] == 1 and "ikke skrivbart" in r.json()["steps"]["2"][0] and r.json()["plans"] == []
    assert api.get(f"/api/drawings/{did}/symbols/{V1}/config").json()["config"] is None
