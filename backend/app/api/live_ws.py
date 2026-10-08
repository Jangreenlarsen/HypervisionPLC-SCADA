"""WebSocket /ws/live — live-værdier til browseren.

Protokol:
  klient → {"type": "subscribe", "tags": ["A", "B"]}
  server → {"type": "snapshot", "values": {...}}          (straks efter subscribe)
  server → {"type": "delta", "values": {...}}             (kun ændrede, kun abonnerede tags)
  server → {"type": "plcs", "plcs": {key: {state, message, sse}}}   (ved ændring, tjekkes hvert 2. s)
  server → {"type": "alarms", "summary": {...}, "active": [...]}   (ved abonnement og ved ændring)
  server → {"type": "error", "error": "..."}              (ugyldig besked)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .auth import websocket_user

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


async def _next_event(queue: asyncio.Queue, alarm_queue: asyncio.Queue,
                      timeout: float) -> tuple[dict[str, Any] | None, bool]:
    """Vent på næste live-delta og/eller alarmændring (højst `timeout` s) → (delta, alarm_changed).

    Begge get-tasks annulleres altid — også når vi selv annulleres midt i ventningen (WebSocket lukket);
    ellers hænger de og logges som "Task was destroyed but it is pending".
    """
    get_delta = asyncio.ensure_future(queue.get())
    get_alarm = asyncio.ensure_future(alarm_queue.get())
    try:
        done, _ = await asyncio.wait({get_delta, get_alarm}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (get_delta, get_alarm):
            if not task.done():
                task.cancel()
    return (get_delta.result() if get_delta in done else None), get_alarm in done


@router.websocket("/ws/live")
async def live_ws(ws: WebSocket) -> None:
    await ws.accept()
    user = websocket_user(ws)
    if user is None:
        await ws.send_json({"type": "error", "error": "Du er ikke logget ind"})
        await ws.close(code=4401)
        return
    cache = ws.app.state.cache
    manager = ws.app.state.manager
    queue = cache.subscribe()
    alarms = ws.app.state.alarm_service
    alarm_queue = alarms.subscribe()
    wanted: set[str] = set()
    visible = ws.app.state.scope_service.visible_tags(user)

    async def send_alarms() -> None:
        await ws.send_json({"type": "alarms", "summary": alarms.summary(visible), "active": alarms.active(visible)})

    async def sender() -> None:
        last_status: dict[str, Any] | None = None
        await send_alarms()
        while True:
            delta, alarm_changed = await _next_event(queue, alarm_queue, 2.0)
            if alarm_changed:
                await send_alarms()
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
            wanted = set(tags) if visible is None else set(tags) & visible
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
        alarms.unsubscribe(alarm_queue)
