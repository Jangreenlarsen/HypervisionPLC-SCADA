import asyncio

import pytest

from app.plc.client import PlcClient
from app.services.live_cache import LiveCache
from app.services.plc_runtime import PlcRuntime, RuntimeTag
from app.services.tagsource import parse_source
from tests.conftest import wait_for

pytestmark = pytest.mark.anyio


def _tags(*specs):
    return [RuntimeTag(name, parse_source(src), scale, offset) for name, src, scale, offset in specs]


async def _runtime(mock_plc, password="scada123", sse=False):
    client = PlcClient(mock_plc.url, "scada", password, rate=50, burst=50)
    cache = LiveCache()
    rt = PlcRuntime("plc1", client, cache, sse_enabled=sse, fast_interval=0.05, slow_interval=0.2,
                    error_retry_max=0.2)
    return rt, cache


async def test_poll_decodes_scales_and_reads_st_variables(mock_plc):
    mock_plc.state.hr[10] = 500
    mock_plc.state.set_hr_real(20, 21.5)
    mock_plc.state.set_hr_dint(40, -70000)
    mock_plc.state.coils[0] = True
    rt, cache = await _runtime(mock_plc)
    rt.set_tags(_tags(
        ("Niveau", "plc1:hr:10", 0.1, 0.0),
        ("Temp", "plc1:hr:20:real", 1.0, 0.0),
        ("Taeller", "plc1:hr:40:dint", 1.0, 0.0),
        ("Pumpe", "plc1:coil:0", 1.0, 0.0),
        ("ST_Niveau", "plc1:logic:1:Niveau", 1.0, 0.0),
        ("ST_Mangler", "plc1:logic:1:FindesIkke", 1.0, 0.0),
        ("ST_Ikke_Kompileret", "plc1:logic:2:X", 1.0, 0.0),
        ("Mode", "plc1:global:Mode", 1.0, 0.0),
        ("AndenPLC", "plc2:hr:1", 1.0, 0.0),  # filtreres fra
    ))
    rt.start()
    try:
        await wait_for(lambda: cache.get("Niveau").quality == "good")
    finally:
        await rt.stop()
    assert cache.get("Niveau").value == pytest.approx(50.0)
    assert cache.get("Temp").value == pytest.approx(21.5)
    assert cache.get("Taeller").value == -70000
    assert cache.get("Pumpe").value is True
    assert cache.get("ST_Niveau").value == 42.5
    assert cache.get("ST_Mangler").quality == "bad" and "findes ikke" in cache.get("ST_Mangler").error
    assert "ikke kompileret" in cache.get("ST_Ikke_Kompileret").error
    assert cache.get("Mode").value == 1
    assert cache.get("AndenPLC").quality == "unknown"
    # HR 10 og HR 20-21 og 40-41 ligger tæt → ét HR-kald; + coil + 2 programmer + globals
    assert rt.requests_per_cycle == 5


async def test_comm_error_keeps_last_value_and_reports_plc_message(mock_plc):
    mock_plc.state.hr[1] = 9
    rt, cache = await _runtime(mock_plc)
    rt.set_tags(_tags(("A", "plc1:hr:1", 1.0, 0.0)))
    rt.start()
    try:
        await wait_for(lambda: cache.get("A").quality == "good")
        mock_plc.state.users["scada"] = "nyt-kodeord"
        mock_plc.state.revoke_all_sessions()
        await wait_for(lambda: cache.get("A").quality == "comm_error")
        value = cache.get("A")
        assert value.value == 9  # sidste kendte værdi bevares
        assert "Login afvist" in value.error
        assert rt.status.state == "error"
    finally:
        await rt.stop()


async def test_sse_updates_arrive_between_polls(mock_plc):
    rt, cache = await _runtime(mock_plc, sse=True)
    rt.slow_interval = 30  # SSE sund → næsten ingen polling; ændringen skal komme via SSE
    rt.set_tags(_tags(("A", "plc1:hr:3", 1.0, 0.0), ("W", "plc1:hr:50:real", 1.0, 0.0)))
    rt.start()
    try:
        await wait_for(lambda: rt.sse.status.state == "connected" and cache.get("A").quality == "good")
        await asyncio.sleep(0.3)
        mock_plc.state.hr[3] = 4242
        await wait_for(lambda: cache.get("A").value == 4242, timeout=3)
        assert rt.sse.status.events > 0
    finally:
        await rt.stop()


async def test_cache_publishes_only_changes(mock_plc):
    rt, cache = await _runtime(mock_plc)
    queue = cache.subscribe()
    rt.set_tags(_tags(("A", "plc1:hr:1", 1.0, 0.0)))
    rt.start()
    try:
        first = await asyncio.wait_for(queue.get(), timeout=5)
        assert first["A"]["quality"] == "good"
        await wait_for(lambda: rt.status.cycles >= 5)
        assert queue.empty()  # uændret værdi → ingen nye deltas
        mock_plc.state.hr[1] = 5
        delta = await asyncio.wait_for(queue.get(), timeout=5)
        assert delta["A"]["value"] == 5
    finally:
        await rt.stop()


async def test_uncovered_tags_poll_fast_while_sse_is_healthy(mock_plc):
    """Regression: ST-variabler og registre SSE ikke leverer, må ikke vente på den langsomme poll."""
    rt, cache = await _runtime(mock_plc, sse=True)
    rt.slow_interval = 30  # kontrol-poll af SSE-dækkede adresser sker praktisk talt aldrig i testen
    # 32-bit-registre leveres aldrig via SSE (begge ord skal komme fra samme læsning)
    rt.set_tags(_tags(("A", "plc1:hr:3", 1.0, 0.0), ("Hoej", "plc1:hr:200:dint", 1.0, 0.0),
                      ("Var", "plc1:logic:1:Starter", 1.0, 0.0)))
    rt.start()
    try:
        await wait_for(lambda: rt.sse.covers("hr", 3) and cache.get("Var").quality == "good")
        await asyncio.sleep(0.3)
        mock_plc.state.programs[1]["variables"][2]["value"] = 99
        mock_plc.state.set_hr_dint(200, 1234)
        await wait_for(lambda: cache.get("Var").value == 99 and cache.get("Hoej").value == 1234, timeout=3)
    finally:
        await rt.stop()


async def test_one_failing_call_only_marks_its_own_tags(mock_plc, monkeypatch):
    """Et langsomt/fejlende kald (her ST-program 1) tager ikke hele PLC'en ned: kun dets tags får kommunikationsfejl."""
    from app.plc.errors import PlcUnreachable
    import app.services.plc_runtime as mod
    monkeypatch.setattr(mod, "COOL_STEP_S", 0.05)
    mock_plc.state.hr[1] = 9
    rt, cache = await _runtime(mock_plc)
    rt.set_tags(_tags(("A", "plc1:hr:1", 1.0, 0.0), ("ST", "plc1:logic:1:Niveau", 1.0, 0.0)))
    real, calls = rt.client.logic_program, {"n": 0}
    broken = {"on": True}

    async def flaky(program_id):
        calls["n"] += 1
        if broken["on"]:
            raise PlcUnreachable("PLC'en svarede ikke inden for tidsgrænsen (test)")
        return await real(program_id)

    rt.client.logic_program = flaky  # type: ignore[method-assign]
    rt.start()
    try:
        await wait_for(lambda: cache.get("A").quality == "good" and cache.get("ST").quality == "comm_error")
        assert rt.status.state == "ok" and "Delvis kommunikationsfejl" in rt.status.message and "ST-program 1" in rt.status.message
        assert rt.status.partial == [{"what": "ST-program 1", "message": "PLC'en svarede ikke inden for tidsgrænsen (test)", "tags": 1}]
        mock_plc.state.hr[1] = 11
        await wait_for(lambda: cache.get("A").value == 11)          # resten af PLC'en opdateres stadig
        broken["on"] = False
        await wait_for(lambda: cache.get("ST").quality == "good")   # og det fejlende kald genoptages af sig selv
        await wait_for(lambda: rt.status.message == "" and rt.status.partial == [])
    finally:
        await rt.stop()


async def test_failing_call_rests_instead_of_hammering_the_plc(mock_plc, monkeypatch):
    from app.plc.errors import PlcUnreachable
    import app.services.plc_runtime as mod
    monkeypatch.setattr(mod, "COOL_STEP_S", 0.4)
    mock_plc.state.hr[1] = 9
    rt, cache = await _runtime(mock_plc)
    rt.set_tags(_tags(("A", "plc1:hr:1", 1.0, 0.0), ("ST", "plc1:logic:1:Niveau", 1.0, 0.0)))
    calls = {"n": 0}

    async def always_down(program_id):
        calls["n"] += 1
        raise PlcUnreachable("nede")

    rt.client.logic_program = always_down  # type: ignore[method-assign]
    rt.start()
    try:
        await wait_for(lambda: cache.get("ST").quality == "comm_error")
        await asyncio.sleep(0.6)   # ~12 poll-cyklusser à 50 ms
    finally:
        await rt.stop()
    assert calls["n"] <= 3, calls   # nedkølingen holder kaldet fra PLC'en mellem forsøgene
    assert rt.slowest() == [] or isinstance(rt.slowest(), list)


async def test_all_calls_failing_is_still_a_full_comm_error(mock_plc):
    from app.plc.errors import PlcUnreachable
    mock_plc.state.hr[1] = 9
    rt, cache = await _runtime(mock_plc)
    rt.set_tags(_tags(("A", "plc1:hr:1", 1.0, 0.0), ("B", "plc1:coil:0", 1.0, 0.0)))
    rt.start()
    try:
        await wait_for(lambda: cache.get("A").quality == "good")

        async def down(*_a, **_k):
            raise PlcUnreachable("nede")

        rt.client.read_bulk = down  # type: ignore[method-assign]
        await wait_for(lambda: rt.status.state == "error" and cache.get("A").quality == "comm_error" and cache.get("B").quality == "comm_error")
    finally:
        await rt.stop()


async def test_rejected_login_is_retried_rarely(mock_plc):
    """v1.12.1: et afvist login gentages kun hvert `auth_retry_s` (ikke hvert sekund) — hvert forsøg er en auth-fejl på PLC'en."""
    client = PlcClient(mock_plc.url, "scada", "forkert", rate=50, burst=50)
    cache = LiveCache()
    rt = PlcRuntime("plc1", client, cache, sse_enabled=False, fast_interval=0.05, slow_interval=0.2, error_retry_max=0.05,
                    auth_retry_s=5.0)
    rt.set_tags(_tags(("A", "plc1:hr:1", 1.0, 0.0)))
    before = mock_plc.state.login_attempts
    rt.start()
    try:
        await wait_for(lambda: rt.status.state == "error")
        await asyncio.sleep(2.0)
    finally:
        await rt.stop()
    tries = mock_plc.state.login_attempts - before
    assert 1 <= tries <= 2, tries   # uden ventetiden ville det være mange forsøg på 2 s
    assert "API" not in rt.status.message and "'scada'" in rt.status.message and "PLC'er" in rt.status.message


async def test_rate_limit_keeps_values_and_only_later_is_a_comm_error(mock_plc):
    """429 fra PLC'en (BUG-509 i PLC'en gjorde budgettet fælles for alle klienter): PLC'en lever, så de sidste værdier
    beholdes og der gives ingen "kommunikation tabt" — først hvis det varer ved, bliver det en kommunikationsfejl."""
    from app.plc.errors import PlcRateLimited
    mock_plc.state.hr[1] = 9
    client = PlcClient(mock_plc.url, "scada", "scada123", rate=50, burst=50)
    cache = LiveCache()
    rt = PlcRuntime("plc1", client, cache, sse_enabled=False, fast_interval=0.05, slow_interval=0.2,
                    error_retry_max=0.2, rate_limit_grace_s=1.0)
    rt.set_tags(_tags(("A", "plc1:hr:1", 1.0, 0.0)))
    real, limited = client.read_bulk, {"on": False}

    async def maybe_429(kind, start, count):
        if limited["on"]:
            raise PlcRateLimited("PLC'en afviste kaldet (rate-limit): Too many requests", status=429)
        return await real(kind, start, count)

    client.read_bulk = maybe_429  # type: ignore[method-assign]
    rt.start()
    try:
        await wait_for(lambda: cache.get("A").quality == "good")
        limited["on"] = True
        await wait_for(lambda: rt.status.throttled >= 1)
        assert cache.get("A").quality == "good" and cache.get("A").value == 9    # sidste værdi beholdes
        assert rt.status.state != "error" and "færre kald" in rt.status.message
        assert rt.status.last_throttled > 0
        await wait_for(lambda: rt.status.state == "error", timeout=8)              # varer det ved: kommunikationsfejl
        assert cache.get("A").quality == "comm_error" and "afvist kald i" in rt.status.message
        limited["on"] = False
        await wait_for(lambda: cache.get("A").quality == "good" and rt.status.state == "ok", timeout=8)
        assert rt.status.message == ""
    finally:
        await rt.stop()
