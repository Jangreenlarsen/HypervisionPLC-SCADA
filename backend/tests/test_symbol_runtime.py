"""Symbolstandard fase 2: fundet position, tilstand, pseudo-tags og afvigelsesalarm."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.live_cache import LiveValue
from app.services.symbol_runtime import compute_state, remote_position
from tests.test_symbols import ADMIN_PW, SVG, TAGS, dec_bin


def _lv(values: dict, bad: set[str] = frozenset()):
    def get(name):
        if name in bad:
            return LiveValue(value=values.get(name), quality="comm_error")
        return LiveValue(value=values.get(name), quality="good") if name in values else LiveValue()
    return get


# ------------------------------------------------------------------ ren logik

@pytest.mark.parametrize("j", range(7))
def test_dec_bin_selector_finds_every_position(j):
    cfg = dec_bin()
    n = j + 1   # position j sætter tallet j+1 binært på Bit0..Bit2 (læses via Bit0_fb..Bit2_fb)
    values = {"Bit0_fb": bool(n & 1), "Bit1_fb": bool(n & 2), "Bit2_fb": bool(n & 4)}
    assert remote_position(cfg, _lv(values)) == (j, False, ["Bit0_fb", "Bit1_fb", "Bit2_fb"])


def test_register_template_and_unknown_value():
    cfg = dec_bin(signals=[{"id": "S1", "tag": "Mode", "fb": "Mode_fb", "write": "set"}],
                  positions=[{"label": "Hand"}, {"label": "0"}, {"label": "Auto"}],
                  planes=[{"signal": "S1", "values": [0, 1, 2]}])
    assert remote_position(cfg, _lv({"Mode_fb": 2}))[0] == 2
    assert remote_position(cfg, _lv({"Mode_fb": 7}))[0] is None          # ingen position passer
    assert remote_position(cfg, _lv({"Mode_fb": 2}, bad={"Mode_fb"}))[:2] == (None, True)


def test_pulse_planes_and_untouched_cells_are_ignored_and_ambiguity_is_unknown():
    cfg = dec_bin(signals=[{"id": "S1", "tag": "Mode", "write": "set"},
                           {"id": "S2", "tag": "Kommando", "write": "pulse", "ms": 300, "rest": 0}],
                  positions=[{"label": "A"}, {"label": "B"}],
                  planes=[{"signal": "S1", "values": [1, None]}, {"signal": "S2", "values": [5, 6]}])
    assert remote_position(cfg, _lv({"Mode": 1}))[0] == 0
    # B rører ikke S1, så med Mode=1 passer både A og... nej: B har ingen læsbare celler → bruges ikke
    assert remote_position(cfg, _lv({"Mode": 3}))[0] is None


def test_local_timeline_pending_then_mismatch_then_confirmed():
    cfg = dec_bin(display="local", validate_s=5)
    st = compute_state(cfg, remote=2, comm=False, chosen=4, chosen_at=100.0, now=102.0)
    assert (st.state, st.pos, st.remote) == ("pending", 4, 2)
    st = compute_state(cfg, remote=2, comm=False, chosen=4, chosen_at=100.0, now=106.0)
    assert (st.state, st.pos) == ("mismatch", 4)
    assert compute_state(cfg, remote=4, comm=False, chosen=4, chosen_at=100.0, now=106.0).state == "confirmed"
    st = compute_state(cfg, remote=None, comm=True, chosen=4, chosen_at=100.0, now=106.0)
    assert (st.state, st.pos, st.comm_error) == ("unknown", 4, True)


def test_remote_timeline_and_lock_flag():
    cfg = dec_bin(display="remote", validate_s=5, lock={"positions": [False, True] + [False] * 5, "leave": False})
    assert compute_state(cfg, remote=0, comm=False, chosen=1, chosen_at=100.0, now=101.0).state == "pending"
    st = compute_state(cfg, remote=1, comm=False, chosen=1, chosen_at=100.0, now=101.0)
    assert (st.state, st.pos, st.locked) == ("confirmed", 1, True)
    assert compute_state(cfg, remote=None, comm=False, chosen=None, chosen_at=0.0, now=101.0).state == "unknown"


# ------------------------------------------------------------------ i appen med mock-PLC'en

def _wait(predicate, timeout=6.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


def _app(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.1, plc_rate=9, symbol_tick_s=0.1,
                        alarm_tick_s=0.1, frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    return TestClient(create_app(settings))


def _setup(c, mock_plc, **cfg_over):
    c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                              "password": "scada123", "sse_enabled": False})
    for t in TAGS:
        c.post("/api/tags", json=t)
    did = c.post("/api/drawings", json={"name": "Anlæg", "svg": SVG}).json()["drawing"]["id"]
    r = c.put(f"/api/drawings/{did}/symbols/V1/config", json={"config": dec_bin(**cfg_over)})
    assert r.status_code == 200, r.text
    return did


def _pseudo(c, did, kind):
    name = f"sym:{did}:V1:{kind}"
    return c.get(f"/api/live?tags={name}").json()["values"].get(name, {})


def _set_position(mock_plc, n):
    """Sæt PLC'ens udgange som om vælgeren står på tallet n (position n-1)."""
    mock_plc.state.di[10] = bool(n & 1)      # Bit0_fb
    mock_plc.state.di[11] = bool(n & 2)      # Bit1_fb
    mock_plc.state.di[12] = bool(n & 4)      # Bit2_fb


def test_pseudo_tags_follow_the_plc(tmp_path, mock_plc):
    with _app(tmp_path, mock_plc) as c:
        _set_position(mock_plc, 5)
        did = _setup(c, mock_plc, display="remote")
        _wait(lambda: _pseudo(c, did, "pos").get("value") == 4)
        assert _pseudo(c, did, "state")["value"] == "confirmed"
        assert _pseudo(c, did, "remote")["value"] == 4
        _set_position(mock_plc, 2)
        _wait(lambda: _pseudo(c, did, "pos").get("value") == 1)


def test_local_mismatch_raises_alarm_with_chosen_level_and_survives_restart(tmp_path, mock_plc):
    with _app(tmp_path, mock_plc) as c:
        _set_position(mock_plc, 3)
        did = _setup(c, mock_plc, display="local", validate_s=1, alarm="low")
        _wait(lambda: _pseudo(c, did, "state").get("value") == "confirmed")   # start = det PLC'en viser
        # Operatøren vælger position 6, men PLC'en bliver stående på 3
        c.app.state.symbol_runtime.set_chosen((did, "V1"), 5, "olsen")
        _wait(lambda: _pseudo(c, did, "state").get("value") == "pending")
        _wait(lambda: _pseudo(c, did, "state").get("value") == "mismatch")
        alarm = _wait(lambda: next((a for a in c.get("/api/alarms").json()["active"] if a["kind"] == "symbol"), None))
        assert alarm["priority"] == "low" and "Vælger V1: valgt 6, PLC viser 3" in alarm["message"]
    # Genstart: det valgte bevares, så afvigelsen stadig ses
    with _app(tmp_path, mock_plc) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        _wait(lambda: _pseudo(c, did, "state").get("value") == "mismatch")
        assert _pseudo(c, did, "pos")["value"] == 5
        # PLC'en følger med → bekræftet, og alarmen går
        _set_position(mock_plc, 6)
        _wait(lambda: _pseudo(c, did, "state").get("value") == "confirmed")
        _wait(lambda: all(a["state"] != "active_unack" or a["kind"] != "symbol"
                          for a in c.get("/api/alarms").json()["active"]))


def test_comm_error_freezes_symbol_alarm(tmp_path, mock_plc):
    from app.services.symbol_runtime import SymbolState
    with _app(tmp_path, mock_plc) as c:
        _set_position(mock_plc, 3)
        did = _setup(c, mock_plc, display="local", validate_s=1, alarm="high")
        rt = c.app.state.symbol_runtime
        _wait(lambda: (did, "V1") in rt.states)
        rt.states[(did, "V1")] = SymbolState(pos=5, remote=None, state="unknown", comm_error=True)
        conds, frozen = rt.alarm_conditions(time.time())
        assert conds == [] and frozen == {f"sym:{did}:V1:state"}


def test_removed_config_removes_pseudo_tags(tmp_path, mock_plc):
    with _app(tmp_path, mock_plc) as c:
        _set_position(mock_plc, 1)
        did = _setup(c, mock_plc, display="remote")
        _wait(lambda: _pseudo(c, did, "pos").get("value") == 0)
        assert c.delete(f"/api/drawings/{did}/symbols/V1/config").status_code == 204
        _wait(lambda: _pseudo(c, did, "pos").get("quality") in (None, "unknown"))
