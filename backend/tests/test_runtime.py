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
