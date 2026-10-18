"""Tags fra eksterne Modbus-enheder (PLC /api/ext, docs/HYPERVISIONPLC_ANALYSE.md §7).

Uden mock-PLC: klienten testes mod de ÆGTE svar fra PLC1 (v7.9.68.125) via en lille transport,
og poll-logikken mod en stub-klient. Selve funktionen er verificeret mod PLC1.
"""

import json

import httpx
import pytest

from app.plc.client import PlcClient, ext_base
from app.plc.errors import PlcApiError
from app.plc.planner import ExtRange, plan_ext_reads
from app.services.live_cache import LiveCache
from app.services.plc_runtime import PlcRuntime, RuntimeTag
from app.services.tagsource import TagSourceError, parse_source

pytestmark = pytest.mark.anyio

# Ægte svar fra PLC1 10.1.1.30 (2026-10-09)
RTU_HR_0_2 = {"src": "rtu", "slave": 90, "type": "hr", "address": 0, "format": "uint", "value": 234, "status": "ok",
              "age_ms": 936, "count": 2, "values": [234, None], "states": ["ok", "error"], "ages_ms": [936, 208]}
MBX_COILS_0_4 = {"src": "mbx", "board": 1, "channel": "D", "slave": 1, "type": "coils", "address": 0, "format": "bool",
                 "value": False, "status": "ok", "age_ms": 105, "count": 4, "values": [False, False, False, False],
                 "states": ["ok", "ok", "ok", "ok"], "ages_ms": [105, 74, 41, 9]}
PENDING_ONE = {"src": "rtu", "slave": 90, "type": "hr", "address": 7, "format": "uint", "value": None, "status": "pending"}
WRITE_OK = {"src": "mbx", "board": 1, "channel": "D", "slave": 1, "type": "coils", "address": 0, "registers": 1, "result": "ok"}


# ------------------------------------------------------------------ tag-kilde

@pytest.mark.parametrize("text, expected, device", [
    ("plc1:rtu:90:hr:0", "plc1:rtu:90:hr:0", "RS485-slave 90"),
    ("plc1:rtu:90:hr:4:real", "plc1:rtu:90:hr:4:real", "RS485-slave 90"),
    ("plc1:mbx:1:D:1:coils:0", "plc1:mbx:1:D:1:coil:0", "slave 1 på expansion board 1 kanal D"),
    ("plc1:mbx:1:4:1:coil:0", "plc1:mbx:1:D:1:coil:0", "slave 1 på expansion board 1 kanal D"),  # kanal 4 = D
])
def test_parse_external_sources(text, expected, device):
    s = parse_source(text)
    assert str(s) == expected and s.is_external and not s.is_register and s.device == device
    assert parse_source(str(s)) == s


@pytest.mark.parametrize("text, message", [
    ("plc1:rtu:0:hr:0", "1-247"),
    ("plc1:rtu:90:xx:0", "registertype"),
    ("plc1:mbx:1:Z:1:hr:0", "Kanal"),
    ("plc1:mbx:0:D:1:hr:0", "Board-nummer"),
    ("plc1:rtu:90:hr:65535:real", "2 registre"),
    ("plc1:rtu:90:coil:1:real", "altid bool"),
    ("plc1:rtu:90:hr", "forventet"),
])
def test_parse_external_errors(text, message):
    with pytest.raises(TagSourceError, match=message):
        parse_source(text)


def test_ext_base_paths():
    assert ext_base(parse_source("plc1:rtu:90:hr:0")) == "/api/ext/rtu/90"
    assert ext_base(parse_source("plc1:mbx:1:D:1:coil:0")) == "/api/ext/mbx/1/D/1"


# ------------------------------------------------------------------ planlægger

def test_ext_plan_groups_only_truly_contiguous_and_max_16():
    g = ("rtu", None, None, 90, "hr")
    plan = plan_ext_reads({g: {(0, 0), (1, 2), (5, 5)} | {(a, a) for a in range(20, 40)}})
    assert plan == [ExtRange(g, 0, 3), ExtRange(g, 5, 1), ExtRange(g, 20, 16), ExtRange(g, 36, 4)]
    # 32-bit-par deles ikke over to kald
    assert plan_ext_reads({g: {(a, a) for a in range(15)} | {(15, 16)}}) == [ExtRange(g, 0, 15), ExtRange(g, 15, 2)]


# ------------------------------------------------------------------ klient (ægte svar)

def _client(handler):
    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/login":
            return httpx.Response(200, json={"token": "t"})
        return handler(request)
    return PlcClient("http://plc", "scada", "pw", rate=100, burst=100, transport=httpx.MockTransport(route))


async def test_read_ext_parses_real_responses():
    seen = []

    def handler(req):
        seen.append(str(req.url))
        return httpx.Response(200, json=RTU_HR_0_2 if "/rtu/" in req.url.path else MBX_COILS_0_4)

    c = _client(handler)
    assert await c.read_ext("/api/ext/rtu/90", "hr", 0, 2, max_age_ms=2000) == [(234, "ok"), (None, "error")]
    assert await c.read_ext("/api/ext/mbx/1/D/1", "coil", 0, 4) == [(False, "ok")] * 4
    assert seen[0] == "http://plc/api/ext/rtu/90/hr/0?count=2&max_age=2000"
    assert "/api/ext/mbx/1/D/1/coils/0?count=4" in seen[1]  # coil → coils i PLC'ens URL
    await c.close()


async def test_read_ext_single_value_and_write_result():
    def handler(req):
        if req.method == "POST":
            body = json.loads(req.content)
            assert body == {"value": True} and "wait=1500" in str(req.url)
            return httpx.Response(200, json=WRITE_OK if "/coils/0" in req.url.path else {**WRITE_OK, "result": "timeout"})
        return httpx.Response(200, json=PENDING_ONE)

    c = _client(handler)
    assert await c.read_ext("/api/ext/rtu/90", "hr", 7, 1) == [(None, "pending")]
    assert await c.write_ext("/api/ext/mbx/1/D/1", "coil", 0, True) == "ok"
    assert await c.write_ext("/api/ext/mbx/1/D/1", "coil", 3, True) == "timeout"  # ikke bekræftet ≠ fejl
    await c.close()


async def test_plc_error_status_for_ext_is_api_error():
    c = _client(lambda req: httpx.Response(404, json={"error": "Board not configured", "status": 404}))
    with pytest.raises(PlcApiError, match="Board not configured"):
        await c.read_ext("/api/ext/mbx/2/A/1", "hr", 0, 1)
    await c.close()


# ------------------------------------------------------------------ poll-logik (stub-klient)

class StubClient:
    """Svar pr. (base, type, start): liste af (værdi, status) eller en PlcApiError."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    async def read_ext(self, base, kind, start, count, *, max_age_ms=None, wait_ms=None):
        self.calls.append((base, kind, start, count, max_age_ms))
        a = self.answers[(base, kind, start)]
        if isinstance(a, Exception):
            raise a
        return a

    async def read_bulk(self, kind, start, count):
        return {start + i: 0 for i in range(count)}


def _rt(answers, *tags):
    cache = LiveCache()
    client = StubClient(answers)
    rt = PlcRuntime("plc1", client, cache, sse_enabled=False, ext_interval=2.0)  # type: ignore[arg-type]
    rt.set_tags([RuntimeTag(n, parse_source(s), scale, 0.0) for n, s, scale in tags])
    return rt, cache, client


async def test_ext_values_pending_and_error_isolation():
    answers = {
        ("/api/ext/rtu/90", "hr", 0): [(234, "ok"), (None, "error")],
        ("/api/ext/mbx/1/D/1", "coil", 0): [(True, "ok")],
        ("/api/ext/mbx/2/A/1", "hr", 0): PlcApiError("Board not configured", status=404),
        ("/api/ext/rtu/91", "hr", 0): [(None, "pending")],
    }
    rt, cache, client = _rt(answers, ("Temp", "plc1:rtu:90:hr:0", 0.1), ("Fejl", "plc1:rtu:90:hr:1", 1),
                            ("Relae", "plc1:mbx:1:D:1:coil:0", 1), ("Board2", "plc1:mbx:2:A:1:hr:0", 1),
                            ("Ny", "plc1:rtu:91:hr:0", 1), ("Intern", "plc1:hr:5", 1))
    await rt.poll_once()
    assert cache.get("Temp").value == pytest.approx(23.4) and cache.get("Temp").quality == "good"
    assert cache.get("Relae").value is True
    assert cache.get("Fejl").quality == "bad" and "RS485-slave 90" in cache.get("Fejl").error
    assert cache.get("Board2").quality == "bad" and "Board not configured" in cache.get("Board2").error
    assert cache.get("Ny").quality == "unknown" and "Venter på første svar" in cache.get("Ny").error
    assert cache.get("Intern").quality == "good"  # resten af PLC'en påvirkes ikke
    assert rt.status.state == "ok"
    # Ét kald for HR 0-1 på slave 90 (sammenhængende), max_age = poll-intervallet
    assert ("/api/ext/rtu/90", "hr", 0, 2, 2000) in client.calls


async def test_pending_keeps_last_known_value_and_interval():
    answers = {("/api/ext/rtu/90", "hr", 0): [(234, "ok")]}
    rt, cache, client = _rt(answers, ("Temp", "plc1:rtu:90:hr:0", 1))
    await rt.poll_once()
    answers[("/api/ext/rtu/90", "hr", 0)] = [(None, "pending")]
    rt._ext_last = 0.0  # gennemtving ny ekstern læsning
    await rt.poll_once()
    assert cache.get("Temp").value == 234 and cache.get("Temp").quality == "good"
    n = len(client.calls)
    await rt.poll_once()  # inden for ext-intervallet → ingen nye /api/ext-kald
    assert len(client.calls) == n


async def test_write_ext_unconfirmed_is_returned_not_raised():
    """Fundet mod PLC1: expansion boardet nåede ikke at bekræfte (504 + result=timeout), men relæet skiftede.
    'timeout' er derfor ikke en fejl i sig selv — tilbagelæsningen afgør (OperateService)."""
    def handler(req):
        coil = req.url.path.rsplit("/", 1)[1]
        result = {"0": "timeout", "1": "queued", "2": "error"}[coil]
        return httpx.Response(504 if result == "timeout" else 502 if result == "error" else 200,
                              json={**WRITE_OK, "address": int(coil), "result": result})

    c = _client(handler)
    assert await c.write_ext("/api/ext/mbx/1/D/1", "coil", 0, False) == "timeout"
    assert await c.write_ext("/api/ext/mbx/1/D/1", "coil", 1, False) == "queued"
    with pytest.raises(PlcApiError, match="Slaven svarede med en fejl"):
        await c.write_ext("/api/ext/mbx/1/D/1", "coil", 2, False)
    await c.close()


def test_error_message_for_ext_body_is_readable():
    from app.plc.errors import extract_error_message
    assert extract_error_message(504, {**WRITE_OK, "result": "timeout"}, "") == "slaven svarede 'timeout'"


async def test_sse_event_for_internal_coil_does_not_touch_external_tag():
    """Fundet af Jan (v0.25.0): plc1:mbx:1:D:1:coil:0 skiftede også, når PLC'ens EGEN coil 0 ændrede sig —
    SSE-hændelsen blev fordelt efter type+adresse uden at tjekke, om tagget er internt."""
    answers = {("/api/ext/mbx/1/D/1", "coil", 0): [(False, "ok")]}
    rt, cache, _ = _rt(answers, ("Relae", "plc1:mbx:1:D:1:coil:0", 1), ("DO1", "plc1:coil:0", 1))
    await rt.poll_once()
    assert cache.get("Relae").value is False
    await rt._on_sse_register("coil", 0, 1)  # intern coil 0 går høj
    assert cache.get("DO1").value is True
    assert cache.get("Relae").value is False  # det eksterne relæ er uændret


async def test_sse_ext_events_update_external_tags():
    """v0.90.0: SSE `ext` fra PLC'ens Modbus-cache opdaterer straks de eksterne tags — samme regler som pollingen."""
    answers = {("/api/ext/rtu/90", "hr", 0): [(100, "ok"), (5, "ok")], ("/api/ext/mbx/1/D/1", "coil", 2): [(False, "ok")]}
    rt, cache, _ = _rt(answers, ("Temp", "plc1:rtu:90:hr:0", 0.1), ("Dobbelt", "plc1:rtu:90:hr:0:dint", 1),
                       ("Relae", "plc1:mbx:1:D:1:coil:2", 1), ("HR0", "plc1:hr:0", 1))
    await rt.poll_once()
    assert cache.get("Temp").value == pytest.approx(10.0)
    ev = lambda **kw: {"src": "rtu", "slave": 90, "type": "hr", "addr": 0, "value": 0, "status": "ok", **kw}
    rt._on_sse_ext(ev(value=234))
    assert cache.get("Temp").value == pytest.approx(23.4)
    assert cache.get("Dobbelt").value == (234 << 16) + 5          # 32-bit tag over adresse 0-1 følger med
    assert cache.get("HR0").value == 0                             # PLC'ens egen HR 0 er uberørt
    rt._on_sse_ext(ev(value=0, status="pending"))                  # pending beholder sidste kendte værdi
    assert cache.get("Temp").value == pytest.approx(23.4)
    rt._on_sse_ext(ev(status="error"))
    assert cache.get("Temp").quality == "bad" and "RS485-slave 90" in cache.get("Temp").error
    rt._on_sse_ext({"src": "mbx", "board": 1, "ch": 4, "slave": 1, "type": "coil", "addr": 2, "value": 1, "status": "ok"})
    assert cache.get("Relae").value is True                        # kanal 4 = D
    before = dict(rt._ext_raw)
    rt._on_sse_ext(ev(slave=91))                                   # en slave ingen tags bruger (ST's egen)
    rt._on_sse_ext({"src": "mbx", "board": 1, "ch": 9, "slave": 1, "type": "coil", "addr": 2, "value": 1, "status": "ok"})
    assert rt._ext_raw == before


async def test_external_tags_switch_sse_to_watch_all():
    class FakeSse:
        def __init__(self):
            self.calls = []

        def set_addresses(self, addrs, external=False):
            self.calls.append((addrs, external))

    fake = FakeSse()
    rt = PlcRuntime("plc1", StubClient({}), LiveCache(), sse_listener=fake)  # type: ignore[arg-type]
    rt.set_tags([RuntimeTag("HR5", parse_source("plc1:hr:5"), 1, 0.0)])
    rt.set_tags([RuntimeTag("HR5", parse_source("plc1:hr:5"), 1, 0.0), RuntimeTag("Ext", parse_source("plc1:rtu:90:hr:0"), 1, 0.0)])
    assert [c[1] for c in fake.calls] == [False, True]
