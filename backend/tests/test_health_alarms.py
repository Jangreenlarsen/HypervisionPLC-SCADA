"""Interne alarmer om SCADA selv: problemer fra systemhelbredet → almindelige alarmer (støjdæmpning, hold, undtagelser)."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.health import assess
from app.services.health_alarms import HealthAlarms

ADMIN_PW = "test-admin-pw-1"


def P(level, code, message="m", area="host"):
    return {"level": level, "area": area, "message": message, "code": code}


def alarms(sample=30.0, hold=120.0):
    return HealthAlarms(None, None, sample_s=sample, warmup_s=0, hold_s=hold)


def keys(a, now=0.0):
    return {c.key: c for c in a.alarm_conditions(now)[0]}


# ------------------------------------------------------------- støjdæmpning og hold

def test_warning_needs_two_consecutive_samples_but_error_is_immediate():
    a = alarms()
    a.update([P("warn", "disk"), P("error", "temp")], 100.0)
    assert set(keys(a)) == {"sys:temp"}                      # rød straks, gul først efter anden måling
    a.update([P("warn", "disk"), P("error", "temp")], 130.0)
    assert set(keys(a)) == {"sys:temp", "sys:disk"}


def test_condition_fields_and_priority():
    a = alarms()
    a.update([P("error", "disk", "Næsten fuld disk"), P("warn", "mem", "Lidt hukommelse")], 0.0)
    a.update([P("error", "disk", "Næsten fuld disk"), P("warn", "mem", "Lidt hukommelse")], 30.0)
    c = keys(a)
    assert c["sys:disk"].priority == "high" and c["sys:mem"].priority == "medium"
    d = c["sys:disk"]
    assert (d.kind, d.level, d.tag, d.plc) == ("sys", "SYS", "", "") and d.message == "System: Næsten fuld disk"


def test_alarm_stays_for_hold_seconds_after_the_problem_disappears():
    a = alarms(hold=120.0)
    a.update([P("error", "temp")], 0.0)
    a.update([], 30.0)
    assert "sys:temp" in keys(a)                              # væk i 30 s: grænse-flimren må ikke rydde alarmen
    a.update([], 100.0)
    assert "sys:temp" in keys(a)
    a.update([], 130.0)                                       # 130 s siden sidst set > hold
    assert keys(a) == {} and a.active == {}


def test_a_flapping_warning_counts_across_gaps_shorter_than_hold():
    a = alarms(hold=120.0)
    a.update([P("warn", "loop_lag")], 0.0)
    a.update([], 30.0)
    assert keys(a) == {}
    a.update([P("warn", "loop_lag")], 60.0)                   # set igen inden for hold → tæller som anden måling
    assert "sys:loop_lag" in keys(a)


def test_a_warning_that_was_gone_longer_than_hold_starts_over():
    a = alarms(hold=120.0)
    a.update([P("warn", "disk")], 0.0)
    a.update([P("warn", "disk")], 500.0)                      # mere end hold siden første → regnes som ny
    assert keys(a) == {}


def test_plc_problems_and_since_boot_power_are_not_alarms():
    a = alarms()
    for t in (0.0, 30.0, 60.0):
        a.update([P("error", "plc", area="plc"), P("warn", "power_past"), P("error", "power")], t)
    assert set(keys(a)) == {"sys:power"}


def test_problem_without_code_is_ignored():
    a = alarms()
    a.update([{"level": "error", "area": "x", "message": "m"}], 0.0)
    assert keys(a) == {}


def test_level_is_held_at_the_highest_within_hold_so_the_alarm_does_not_flicker():
    a = alarms(hold=120.0)
    a.update([P("error", "temp")], 0.0)
    a.update([P("warn", "temp")], 30.0)                       # tilbage til gul lige under grænsen
    assert keys(a)["sys:temp"].priority == "high"             # stadig rød
    a.update([P("warn", "temp")], 100.0)
    assert keys(a)["sys:temp"].priority == "high"
    a.update([P("warn", "temp")], 130.0)                      # rødt ikke set i mere end hold → nu gul
    assert keys(a)["sys:temp"].priority == "medium"
    a.update([P("error", "temp")], 160.0)                     # og rød igen straks
    assert keys(a)["sys:temp"].priority == "high"


def _stored(*keys_):
    return {k: {"state": "active_unack", "priority": "high", "message": f"System: gemt {k}"} for k in keys_}


def test_stored_alarms_are_repeated_during_warmup_so_a_restart_does_not_clear_and_raise_them():
    rows = _stored("sys:disk")
    rows["sys:old"] = {"state": "rtn_unack", "priority": "high", "message": "x"}       # ophørt: ikke en betingelse
    rows["tag:T:high"] = {"state": "active_unack", "priority": "high", "message": "x"}  # ikke en sys-alarm
    a = HealthAlarms(None, None, warmup_s=0, stored=lambda: rows)
    c = keys(a)
    assert set(c) == {"sys:disk"} and c["sys:disk"].message == "System: gemt sys:disk" and c["sys:disk"].priority == "high"


def test_after_first_sample_a_restored_warning_does_not_start_over_but_a_solved_problem_clears():
    a = HealthAlarms(None, None, warmup_s=0, stored=lambda: _stored("sys:disk", "sys:mem"))
    a.update([P("warn", "disk", "Lav ledig plads")], 0.0)       # mem er løst, disk findes stadig (gul, første gang set)
    assert set(keys(a)) == {"sys:disk"}                         # gemt alarm fortsætter uden at vente på en anden måling
    assert keys(a)["sys:disk"].message == "System: Lav ledig plads"
    a2 = HealthAlarms(None, None, warmup_s=0)
    a2.update([P("warn", "disk")], 0.0)
    assert keys(a2) == {}                                       # uden gemt alarm gælder to-målinger-reglen som før


@pytest.mark.anyio
async def test_alarm_sampling_uses_one_sample_interval_for_the_lag_window():
    import asyncio
    seen = {}

    class Stub:
        async def details(self, state, lag_window_s=60.0):
            seen["window"] = lag_window_s
            return {"problems": []}

    a = HealthAlarms(Stub(), None, sample_s=12.5, warmup_s=0)
    task = asyncio.create_task(a.run())
    await asyncio.sleep(0.05)
    task.cancel()
    assert seen["window"] == 12.5 and a.sampled


def test_backup_warning_waits_for_the_first_automatic_backup():
    young = _d(uptime_s=100, backup={"interval_h": 24, "last_age_s": None})
    assert assess(young)["level"] == "ok"
    older = _d(uptime_s=700, backup={"interval_h": 24, "last_age_s": None})
    assert [p["code"] for p in assess(older)["problems"]] == ["backup"]


# ------------------------------------------------------------- koder fra assess

def _d(**kw):
    base = {"now": 1_000_000.0, "uptime_s": 100_000, "plcs": [], "loop": {"lag_max_s": 0.01}, "db": {"ok": True, "latency_s": 0.001},
            "disk": {"total": 100e9, "used": 10e9, "free": 90e9},
            "host": {"mem_total": 4e9, "mem_available": 2e9, "cpu_temp_c": 50.0, "throttled": None},
            "backup": {"interval_h": 24, "last_age_s": 3600}}
    base.update(kw)
    return base


@pytest.mark.parametrize("patch, code", [
    ({"loop": {"lag_max_s": 1.5}}, "loop_lag"), ({"db": {"ok": False, "error": "x"}}, "database"),
    ({"disk": {"total": 100e9, "used": 97e9, "free": 3e9}}, "disk"), ({"host": {"mem_total": 4e9, "mem_available": 1e8}}, "mem"),
    ({"host": {"cpu_temp_c": 90.0}}, "temp"), ({"host": {"throttled": {"now": ["undervoltage"], "past": []}}}, "power"),
    ({"host": {"throttled": {"now": [], "past": ["undervoltage"]}}}, "power_past"), ({"backup": {"interval_h": 24, "last_age_s": 99 * 3600}}, "backup"),
    ({"tls": {"days_left": 3, "self_signed": False}}, "tls"),
])
def test_assess_gives_every_problem_a_code(patch, code):
    assert [p["code"] for p in assess(_d(**patch))["problems"]] == [code]


def test_plc_problem_code_is_plc():
    d = _d(plcs=[{"name": "K", "enabled": True, "state": "error", "message": "x", "partial": [], "attention": False, "last_throttled": None}])
    assert [(p["area"], p["code"]) for p in assess(d)["problems"]] == [("plc", "plc")]


# ------------------------------------------------------------- gennem hele systemet

@pytest.fixture
def api(tmp_path):
    s = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW,
                 backup_hours=0, alarm_tick_s=0.1, health_alarm_warmup_s=0.0, health_alarm_sample_s=0.1)
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        yield c


def _wait(predicate, timeout=8.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


def _active(c):
    return {a["key"]: a for a in c.get("/api/alarms").json()["active"]}


def test_system_problem_raises_acknowledgeable_alarm_and_clears(api):
    problems = [P("error", "disk", "Næsten fuld disk: 0.10 GB ledig (1 %)", area="disk")]

    async def details(state, **kw):
        return {"problems": list(problems)}

    api.app.state.health_service.details = details
    api.app.state.health_alarms.hold_s = 0.3
    a = _wait(lambda: _active(api).get("sys:disk"))
    assert a["level"] == "SYS" and a["priority"] == "high" and a["state"] == "active_unack"
    assert "Næsten fuld disk" in a["message"] and a["kind"] == "sys"
    assert api.post("/api/alarms/ack", json={"keys": ["sys:disk"]}).status_code == 200
    problems.clear()                                              # problemet er løst
    _wait(lambda: "sys:disk" not in _active(api) or _active(api)["sys:disk"]["state"] in ("rtn_unack",) or False)
    hist = api.get("/api/alarms/history").json()
    assert any(e["key"] == "sys:disk" for e in hist)


def test_health_alarms_can_be_switched_off(tmp_path):
    s = Settings(data_dir=tmp_path, frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0, health_alarms=False,
                 health_alarm_warmup_s=0.0, health_alarm_sample_s=0.1, alarm_tick_s=0.1)
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})

        async def details(state, **kw):
            return {"problems": [P("error", "disk")]}

        c.app.state.health_service.details = details
        time.sleep(0.8)
        assert "sys:disk" not in _active(c)
