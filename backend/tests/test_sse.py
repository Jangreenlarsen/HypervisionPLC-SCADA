import asyncio

import pytest

from app.plc.client import PlcClient
from app.plc import sse as sse_mod
from app.plc.sse import SseListener, SseParser, build_query, build_watch
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
    params, watch_all = build_watch({"hr": {1, 2, 200, 300}, "coil": {0}, "ir": {319, 400}})
    assert not watch_all
    # PLC v7.9.68.124+: SSE tager HR 0-255 og IR 0-319 — 300 og 400 polles i stedet
    assert params == {"subscribe": "registers,system", "hr": "1,2,200", "coils": "0", "ir": "319"}
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


def test_build_query_keeps_commas_unencoded():
    # Regression: PLC'en afkoder ikke %2C og læste derfor kun første adresse
    q = build_query({"subscribe": "registers,system", "coils": "0,1,2,3,7", "token": "ab12"})
    assert q == "subscribe=registers,system&coils=0,1,2,3,7&token=ab12"


@pytest.mark.anyio
async def test_listener_watches_all_requested_addresses(mock_plc):
    """Regression mod en mock der — som den rigtige PLC — ikke URL-afkoder query-strengen."""
    received = []
    client = PlcClient(mock_plc.url, "scada", "scada123", rate=50, burst=50)
    listener = SseListener(client, lambda k, a, v: received.append((k, a, v)), heartbeat_timeout_s=5)
    listener.set_addresses({"coil": {0, 1, 2}, "di": {3}})
    task = asyncio.create_task(listener.run())
    try:
        await wait_for(lambda: listener.covers("coil", 2) and listener.covers("di", 3))
        mock_plc.state.coils[2] = True
        await wait_for(lambda: ("coil", 2, 1) in received, timeout=3)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await client.close()


@pytest.mark.anyio
async def test_listener_detects_partial_watch(mock_plc, monkeypatch):
    """Overvåger PLC'en færre adresser end ønsket, må de IKKE regnes som dækket af SSE."""
    from urllib.parse import urlencode

    monkeypatch.setattr(sse_mod, "build_query", lambda params: urlencode(params))  # gammel, fejlagtig kodning
    client = PlcClient(mock_plc.url, "scada", "scada123", rate=50, burst=50)
    listener = SseListener(client, lambda *a: None, heartbeat_timeout_s=5)
    listener.set_addresses({"coil": {0, 1, 2}})
    task = asyncio.create_task(listener.run())
    try:
        await wait_for(lambda: listener.status.state == "connected" and "færre adresser" in listener.status.message)
        assert not listener.covers("coil", 1) and not listener.covers("coil", 0)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await client.close()


def test_build_watch_external_needs_watch_all():
    """Eksterne registre sendes kun i watch_all (PLC FEAT-447) — selv med få interne adresser."""
    assert build_watch({"hr": {1}}, external=True) == ({"subscribe": "all"}, True)
    assert build_watch({}, external=True) == ({"subscribe": "all"}, True)


@pytest.mark.anyio
async def test_listener_ext_events_and_watch_all_coverage(mock_plc):
    """v0.90.0: `ext`-hændelser leveres; i watch_all dækkes IR kun op til 255 (PLC'ens SSE_IR_WATCH_ALL)."""
    ext: list[dict] = []
    client = PlcClient(mock_plc.url, "scada", "scada123", rate=50, burst=50)
    listener = SseListener(client, lambda *a: None, heartbeat_timeout_s=5, on_ext=ext.append)
    listener.set_addresses({"ir": {10, 300}}, external=True)
    task = asyncio.create_task(listener.run())
    try:
        await wait_for(lambda: listener.status.state == "connected" and listener.covers("ir", 10))
        assert not listener.covers("ir", 300)   # IR 256-319 sendes ikke i watch_all — polles
        assert listener.status.extra["watch_all"] and listener.status.extra["external"]
        mock_plc.state.ext["rtu:90:hr:0"] = {"src": "rtu", "slave": 90, "type": "hr", "addr": 0, "value": 234, "status": "ok", "write": False}
        mock_plc.state.ext["bad"] = {"src": "rtu", "slave": "x", "type": "hr", "addr": 0, "value": 1, "status": "ok"}   # ufuldstændig
        mock_plc.state.ext["mbx"] = {"src": "mbx", "board": 1, "ch": 4, "slave": 1, "type": "coil", "addr": 2, "value": 1, "status": "ok"}
        await wait_for(lambda: len(ext) == 2)
        assert [e["src"] for e in ext] == ["rtu", "mbx"] and listener.ext_events == 2
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await client.close()
