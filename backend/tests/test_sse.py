import asyncio

import pytest

from app.plc.client import PlcClient
from app.plc.sse import SseListener, SseParser, build_watch
from tests.conftest import wait_for


def test_parser_events_and_comments():
    p = SseParser()
    lines = ["event: register", 'data: {"type":"hr","addr":5,"value":9}', "", ": keepalive", "",
             "data: plain", ""]
    events = [e for e in (p.feed_line(l) for l in lines) if e]
    assert events[0].event == "register" and events[0].data == {"type": "hr", "addr": 5, "value": 9}
    assert events[1].event == "message" and events[1].data == "plain"


def test_parser_bug483_status_line_in_stream():
    # PLC BUG-483: en rå "HTTP/1.1 503"-linje kan dukke op midt i strømmen.
    p = SseParser()
    assert p.feed_line("HTTP/1.1 503 Service Unavailable") is None
    ev = p.feed_line("")
    assert ev is None  # ingen data-linje → intet event; listeneren ser den via event-navnet hvis data følger


def test_build_watch_lists_and_all():
    params, watch_all = build_watch({"hr": {1, 2}, "coil": {0}, "ir": {300}})
    assert not watch_all
    assert params == {"subscribe": "registers,system", "hr": "1,2", "coils": "0"}  # IR 300 kan ikke SSE-overvåges
    params, watch_all = build_watch({"hr": set(range(40))})
    assert watch_all and params == {"subscribe": "all"}


@pytest.mark.anyio
async def test_listener_receives_register_changes(mock_plc):
    received: list[tuple[str, int, int]] = []
    client = PlcClient(mock_plc.url, "scada", "scada123", rate=50, burst=50)
    listener = SseListener(client, lambda k, a, v: received.append((k, a, v)), heartbeat_timeout_s=5)
    listener.set_addresses({"hr": {5}, "coil": {2}})
    task = asyncio.create_task(listener.run())
    try:
        await wait_for(lambda: listener.status.state == "connected")
        mock_plc.state.hr[5] = 77
        mock_plc.state.coils[2] = True
        mock_plc.state.hr[6] = 99  # ikke overvåget
        await wait_for(lambda: ("hr", 5, 77) in received and ("coil", 2, 1) in received)
        assert not any(a == 6 for _, a, _ in received)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await client.close()


@pytest.mark.anyio
async def test_listener_reports_full_when_plc_slots_taken(mock_plc):
    mock_plc.state.sse_active = 3  # PLC'ens 3 pladser er brugt af andre
    client = PlcClient(mock_plc.url, "scada", "scada123", rate=50, burst=50)
    listener = SseListener(client, lambda *a: None)
    listener.set_addresses({"hr": {1}})
    task = asyncio.create_task(listener.run())
    try:
        await wait_for(lambda: listener.status.state == "full")
        assert "optaget" in listener.status.message
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await client.close()


@pytest.mark.anyio
async def test_listener_disabled_on_plc(mock_plc):
    mock_plc.state.sse_enabled = False
    client = PlcClient(mock_plc.url, "scada", "scada123", rate=50, burst=50)
    listener = SseListener(client, lambda *a: None)
    listener.set_addresses({"hr": {1}})
    task = asyncio.create_task(listener.run())
    try:
        await wait_for(lambda: listener.status.state == "disabled_on_plc")
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await client.close()
