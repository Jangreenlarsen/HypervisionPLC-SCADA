"""PLC-klienten mod en rigtig (mock-)server over HTTP."""

import pytest

from app.plc.client import PlcClient
from app.plc.errors import PlcApiError, PlcAuthError, PlcRateLimited, PlcUnreachable
from app.services.tagsource import decode_words

pytestmark = pytest.mark.anyio


def _client(url: str, password: str = "scada123", **kw) -> PlcClient:
    kw.setdefault("rate", 50)
    kw.setdefault("burst", 50)
    return PlcClient(url, "scada", password, **kw)


async def test_login_and_bulk_read(mock_plc):
    mock_plc.state.hr[10] = 1234
    mock_plc.state.coils[3] = True
    client = _client(mock_plc.url)
    try:
        hr = await client.read_bulk("hr", 0, 20)
        coils = await client.read_bulk("coil", 0, 8)
        ir = await client.read_bulk("ir", 300, 20)
    finally:
        await client.logout()
        await client.close()
    assert hr[10] == 1234 and len(hr) == 20
    assert coils[3] == 1 and coils[0] == 0
    assert set(ir) == set(range(300, 320))
    assert mock_plc.state.logins == 1
    assert mock_plc.state.sessions == {}  # logout frigav session-pladsen


async def test_token_reused_and_relogin_after_revoke(mock_plc):
    client = _client(mock_plc.url)
    try:
        await client.read_bulk("hr", 0, 1)
        await client.read_bulk("hr", 0, 1)
        assert mock_plc.state.logins == 1  # samme token genbrugt
        mock_plc.state.revoke_all_sessions()  # fx en gated ACL-ændring på PLC'en
        await client.read_bulk("hr", 0, 1)
        assert mock_plc.state.logins == 2
    finally:
        await client.close()


async def test_wrong_password_gives_auth_error_with_plc_message(mock_plc):
    client = _client(mock_plc.url, password="forkert")
    try:
        with pytest.raises(PlcAuthError, match="Login afvist af PLC: Authentication required"):
            await client.read_bulk("hr", 0, 1)
    finally:
        await client.close()


async def test_plc_validation_error_message_is_passed_through(mock_plc):
    client = _client(mock_plc.url)
    try:
        with pytest.raises(PlcApiError, match="Invalid register address") as info:
            await client.write_hr(300, 1)
        assert info.value.status == 400
    finally:
        await client.close()


async def test_rate_limit_429_sets_backoff(mock_plc):
    mock_plc.state.burst = 2
    mock_plc.state.rate = 0.01
    client = _client(mock_plc.url)
    try:
        with pytest.raises(PlcRateLimited):
            for _ in range(5):
                await client.read_bulk("hr", 0, 1)
        # Under backoff sendes intet til PLC'en
        before = len(mock_plc.state.request_log)
        with pytest.raises(PlcRateLimited, match="prøver igen"):
            await client.read_bulk("hr", 0, 1)
        assert len(mock_plc.state.request_log) == before
    finally:
        await client.close()


async def test_unreachable():
    from tests.conftest import free_port

    client = _client(f"http://127.0.0.1:{free_port()}", timeout=1)
    try:
        with pytest.raises(PlcUnreachable, match="127.0.0.1"):  # refused eller timeout afh. af OS
            await client.read_bulk("hr", 0, 1)
    finally:
        await client.close()


async def test_write_real_roundtrip(mock_plc):
    client = _client(mock_plc.url)
    try:
        await client.write_hr(30, 3.25, "real")
        words = await client.read_bulk("hr", 30, 2)
    finally:
        await client.close()
    assert decode_words([words[30], words[31]], "real") == pytest.approx(3.25)


async def test_logic_endpoints(mock_plc):
    client = _client(mock_plc.url)
    try:
        programs = await client.logic_programs()
        prog = await client.logic_program(1)
        globals_ = await client.logic_globals()
    finally:
        await client.close()
    assert [p["id"] for p in programs] == [1, 2]
    assert prog["variables"][0]["name"] == "Niveau"
    assert globals_[0]["name"] == "Mode"
