"""Server-sent events for hjælperens lange svar (v4.3.0): fælles for /api/assist/ask og signalvejens forslag.

Modellen kan bruge over et minut, før der kommer noget (prompten læses på CPU). En kommentarlinje hvert KEEPALIVE_S holder
forbindelsen åben gennem nginx og proxyer (proxy_read_timeout er typisk 60 s). Lukker browseren, annulleres producenten,
så forbindelsen til llama-server lukkes, og modellen stopper. `close` kaldes præcis én gang — også hvis browseren afbryder,
før strømmen nåede at starte (baggrundsopgave efter svaret).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Callable

from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

KEEPALIVE_S = 10.0


def sse_response(source: Callable[[], AsyncIterator[dict[str, Any]]],
                 close: Callable[[dict[str, Any]], None]) -> StreamingResponse:
    """`source()` giver hændelser ({"type": …}); `close(sidste done/error-hændelse eller {})` kaldes én gang til sidst."""
    state: dict[str, Any] = {"last": {}, "closed": False}

    def finish() -> None:
        if state["closed"]:
            return
        state["closed"] = True
        close(state["last"])

    async def events() -> AsyncIterator[bytes]:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def produce() -> None:
            try:
                async for ev in source():
                    await queue.put(ev)
            finally:
                await queue.put(None)

        task = asyncio.create_task(produce())
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_S)
                except asyncio.TimeoutError:
                    yield b": venter\n\n"
                    continue
                if ev is None:
                    break
                if ev.get("type") in ("done", "error"):
                    state["last"] = ev
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode()
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):   # noqa: BLE001
                    pass
            finish()

    return StreamingResponse(events(), media_type="text/event-stream", background=BackgroundTask(finish),
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
