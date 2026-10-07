from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass
from typing import Iterator

import pytest
import uvicorn

from mock_plc.app import MockPlcState, create_mock_plc, default_state


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class MockHandle:
    state: MockPlcState
    url: str
    port: int


class _Server:
    def __init__(self, app, port: int):
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                                timeout_graceful_shutdown=1)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self) -> "_Server":
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("mock-PLC startede ikke")
            time.sleep(0.02)
        return self

    def __exit__(self, *exc: object) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


@pytest.fixture
def mock_plc() -> Iterator[MockHandle]:
    state = default_state()
    port = free_port()
    state.sse_port = port
    state.sse_heartbeat_s = 1.0
    with _Server(create_mock_plc(state), port):
        yield MockHandle(state, f"http://127.0.0.1:{port}", port)


async def wait_for(predicate, timeout: float = 5.0, interval: float = 0.05):
    """Vent (async) til predicate() er sand; returnér værdien eller fejl med timeout."""
    import anyio

    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() > deadline:
            raise AssertionError("betingelse blev ikke opfyldt inden for timeout")
        await anyio.sleep(interval)
