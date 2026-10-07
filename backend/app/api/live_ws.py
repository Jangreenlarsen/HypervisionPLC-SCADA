"""WebSocket /ws/live — live-værdier til browseren.

Protokol:
  klient → {"type": "subscribe", "tags": ["A", "B"]}
  server → {"type": "snapshot", "values": {...}}          (straks efter subscribe)
  server → {"type": "delta", "values": {...}}             (kun ændrede, kun abonnerede tags)
  server → {"type": "plcs", "plcs": {key: {state, message, sse}}}   (ved ændring, tjekkes hvert 2. s)
  server → {"type": "error", "error": "..."}              (ugyldig besked)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
log = logging.getLogger(__name__)
MAX_TAGS = 2000


def _plc_summary(manager: Any) -> dict[str, Any]:
    out = {}
    for plc in manager.db.list_plcs():
        st = manager.status(plc["key"])
        out[plc["key"]] = {"name": plc["name"], "state": st["state"], "message": st["message"],
                           "sse": st.get("sse", {}).get("state")}
    return out


@router.websocket("/ws/live")
async def live_ws(ws: WebSocket) -> None:
    await ws.accept()
    cache = ws.app.state.cache
    manager = ws.app.state.manager
    queue = cache.subscribe()
    wanted: set[str] = set()

    async def sender() -> None:
        last_status: dict[str, Any] | None = None
        while True:
            try:
                delta = await asyncio.wait_for(queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                delta = None
            if delta and wanted:
                filtered = {k: v for k, v in delta.items() if k in wanted}
                if filtered:
                    await ws.send_json({"type": "delta", "values": filtered})
            status = _plc_summary(manager)
            if status != last_status:
                await ws.send_json({"type": "plcs", "plcs": status})
                last_status = status

    send_task = asyncio.create_task(sender())
    try:
        while True:
            msg = await ws.receive_json()
            tags = msg.get("tags") if isinstance(msg, dict) and msg.get("type") == "subscribe" else None
            if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags) or len(tags) > MAX_TAGS:
                await ws.send_json({"type": "error",
                                    "error": f"Forventet {{'type':'subscribe','tags':[...]}} med max {MAX_TAGS} navne"})
                continue
            wanted = set(tags)
            await ws.send_json({"type": "snapshot", "values": cache.snapshot(sorted(wanted))})
    except WebSocketDisconnect:
        pass
    except ValueError:
        # Ikke-JSON fra klienten: luk pænt i stedet for at efterlade en hængende forbindelse.
        await ws.close(code=1003)
    finally:
        send_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await send_task
        cache.unsubscribe(queue)
