"""Live-WebSocketens ventelogik (`_next_event`)."""

import asyncio

from app.api.live_ws import _next_event


def test_next_event_returns_delta_and_alarm():
    async def run():
        q, aq = asyncio.Queue(), asyncio.Queue()
        q.put_nowait({"A": 1})
        assert await _next_event(q, aq, 1.0) == ({"A": 1}, False)
        aq.put_nowait(True)
        assert await _next_event(q, aq, 1.0) == (None, True)
        assert await _next_event(q, aq, 0.01) == (None, False)  # timeout
        # Ingen ventende get'ere efter normal afslutning — og intet element er tabt
        q.put_nowait({"B": 2})
        assert q.qsize() == 1 and await _next_event(q, aq, 1.0) == ({"B": 2}, False)

    asyncio.run(run())


def test_cancelled_while_waiting_leaves_no_pending_gets():
    """Regression: WebSocket lukket midt i ventningen efterlod to hængende Queue.get-tasks."""
    async def run():
        q, aq = asyncio.Queue(), asyncio.Queue()
        before = asyncio.all_tasks()
        task = asyncio.ensure_future(_next_event(q, aq, 30.0))
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0)  # lad annulleringerne blive færdige
        assert asyncio.all_tasks() - before == set()
        # Køerne virker stadig bagefter (intet element "spist" af en død get)
        q.put_nowait({"A": 1})
        assert await _next_event(q, aq, 1.0) == ({"A": 1}, False)

    asyncio.run(run())
