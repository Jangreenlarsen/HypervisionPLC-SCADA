"""Klient-side rate-budget pr. PLC (token bucket).

PLC'en tillader 10 req/s (30 burst) pr. IP. Vi holder os til et lavere budget
(default 5 req/s) så PLC'ens eget dashboard og andre klienter stadig har plads.
"""

from __future__ import annotations

import asyncio
import time


class TokenBucket:
    def __init__(self, rate: float, burst: int):
        if rate <= 0 or burst < 1:
            raise ValueError("rate skal være > 0 og burst >= 1")
        self.rate = rate
        self.burst = burst
        self._tokens = float(burst)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        self._tokens = min(self.burst, self._tokens + (now - self._last) * self.rate)
        self._last = now

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                await asyncio.sleep((1 - self._tokens) / self.rate)
