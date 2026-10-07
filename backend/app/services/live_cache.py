"""Live-cache: aktuel værdi + kvalitet + tidsstempel pr. tag.

Kvalitet:
- good        — frisk værdi fra PLC'en
- comm_error  — seneste kommunikation med PLC'en fejlede; `value` er sidste kendte værdi
- bad         — tagget kan ikke læses (fx ST-variabel findes ikke, program ikke kompileret)
- unknown     — endnu ingen værdi modtaget

Abonnenter (fase 2: WebSocket) får kun ændringer.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class LiveValue:
    value: Any = None
    quality: str = "unknown"
    ts: float = 0.0  # SCADA-serverens tid (PLC'ens epoch er 0 uden NTP)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveCache:
    def __init__(self) -> None:
        self._values: dict[str, LiveValue] = {}
        self._subscribers: set[asyncio.Queue[dict[str, dict[str, Any]]]] = set()

    def get(self, name: str) -> LiveValue:
        return self._values.get(name, LiveValue())

    def snapshot(self, names: list[str] | None = None) -> dict[str, dict[str, Any]]:
        keys = names if names is not None else list(self._values)
        return {n: self.get(n).as_dict() for n in keys}

    def remove(self, names: list[str]) -> None:
        for n in names:
            self._values.pop(n, None)

    def update(self, changes: dict[str, LiveValue]) -> None:
        """Gem nye værdier; publicér kun dem der reelt er ændret (værdi, kvalitet eller fejl)."""
        delta: dict[str, dict[str, Any]] = {}
        for name, new in changes.items():
            old = self._values.get(name)
            if old is not None and old.value == new.value and old.quality == new.quality and old.error == new.error:
                old.ts = new.ts
                continue
            self._values[name] = new
            delta[name] = new.as_dict()
        if delta:
            for queue in list(self._subscribers):
                if queue.full():
                    # Langsom klient: drop ældste delta frem for at blokere pollingen.
                    queue.get_nowait()
                queue.put_nowait(delta)

    def mark_comm_error(self, names: list[str], message: str) -> None:
        now = time.time()
        self.update({
            n: LiveValue(value=self.get(n).value, quality="comm_error", ts=now, error=message) for n in names
        })

    def subscribe(self, maxsize: int = 100) -> asyncio.Queue[dict[str, dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, dict[str, Any]]] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, dict[str, Any]]]) -> None:
        self._subscribers.discard(queue)
