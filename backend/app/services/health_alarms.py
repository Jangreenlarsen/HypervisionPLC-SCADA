"""Interne alarmer om SCADA selv (lag 3): problemer fra systemhelbredet (disk, event-loop-lag, database, hukommelse, temperatur,
strøm/undervoltage, backup, certifikat) bliver til almindelige alarmer med kvittering og historik — via alarmmotorens
kilde-grænseflade (`alarm_conditions`). PLC-problemer er undtaget: de har allerede kommunikationsalarmer.

Støjdæmpning: en advarsel (gul) skal ses i to målinger i træk, før den bliver en alarm (en kortvarig lag-spids er ingen alarm);
en fejl (rød) udløser straks. En alarm ophører først `hold_s` sekunder efter, at problemet sidst blev set, og niveauet sænkes (rød →
gul) først, når det røde ikke er set i `hold_s` (ingen flimren omkring en grænse). Event-loop-lag måles over ét måleinterval, ikke
et helt minut (en enkelt spids må ikke blive til flere målinger). Målingen tages hvert `sample_s` sekund, og først efter `warmup_s`
(serveren er ikke "stabil" lige efter start); i ventetiden bevares alarmer, der blev gemt før en genstart, i stedet for at blive ryddet og
rejst igen.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from .alarms import Condition

log = logging.getLogger(__name__)

# Problemer der kun står på Status-siden: "siden opstart" varer til genstart og ville give en alarm, der aldrig ophører.
NO_ALARM_CODES = frozenset({"plc", "power_past"})


class HealthAlarms:
    def __init__(self, health: Any, state: Any, *, sample_s: float = 30.0, warmup_s: float = 60.0, hold_s: float = 120.0,
                 stored: Callable[[], dict[str, dict[str, Any]]] | None = None) -> None:
        self.health = health
        self.state = state
        self.stored = stored            # alarmmotorens gemte tilstande (key → række), til alarmer der overlever en genstart
        self.sampled = False            # første måling er taget (før da gentages gemte sys-alarmer)
        self._restored: set[str] = set()
        self.sample_s = sample_s
        self.warmup_s = warmup_s
        self.hold_s = hold_s
        # code → {"level", "message", "area", "seen" (antal målinger i træk), "last" (tidspunkt sidst set)}
        self.active: dict[str, dict[str, Any]] = {}

    async def run(self) -> None:
        await asyncio.sleep(self.warmup_s)
        while True:
            try:
                details = await self.health.details(self.state, lag_window_s=self.sample_s)
                self.update(details.get("problems", []), time.time())
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Måling af systemhelbred til alarmer fejlede")
            await asyncio.sleep(self.sample_s)

    def update(self, problems: list[dict[str, str]], now: float) -> None:
        """Én måling: tæl hvor mange gange i træk hvert problem er set, og glem dem, der har været væk længere end `hold_s`."""
        if not self.sampled:
            self._restored = {k[4:] for k in self._stored_rows()}
            self.sampled = True
        current = {p["code"]: p for p in problems if p.get("code") and p["code"] not in NO_ALARM_CODES}
        for code, p in current.items():
            prev = self.active.get(code)
            fresh = prev is not None and now - prev["last"] <= self.hold_s
            seen = (prev["seen"] + 1) if fresh else 1
            if code in self._restored:
                seen = max(seen, 2)              # en alarm fra før genstarten skal ikke starte forfra som "set én gang"
            red_last = now if p["level"] == "error" else (prev["red_last"] if fresh and prev else None)
            # niveauet sænkes først, når det røde ikke er set i hold_s (ellers flimrer alarmen mellem gul og rød)
            level = "error" if p["level"] == "error" or (red_last is not None and now - red_last <= self.hold_s) else "warn"
            self.active[code] = {"level": level, "message": p["message"], "area": p["area"], "seen": seen, "last": now, "red_last": red_last}
        self._restored = set()                   # gælder kun den første måling efter en genstart
        for code in [c for c, a in self.active.items() if c not in current and now - a["last"] > self.hold_s]:
            del self.active[code]

    def _stored_rows(self) -> dict[str, dict[str, Any]]:
        rows = self.stored() if self.stored else {}
        return {k: r for k, r in rows.items() if k.startswith("sys:") and r.get("state") in ("active_unack", "active_ack")}

    def alarm_conditions(self, now: float) -> tuple[list[Condition], set[str]]:
        conds = []
        if not self.sampled:
            # før første måling: gentag de gemte aktive sys-alarmer, så de hverken ryddes eller rejses igen ved en genstart
            for key, r in self._stored_rows().items():
                conds.append(Condition(key, "", "", "sys", "SYS", None, r["message"], priority=r["priority"]))
            return conds, set()
        for code, a in self.active.items():
            if a["level"] != "error" and a["seen"] < 2:
                continue    # en advarsel skal ses to gange i træk
            conds.append(Condition(f"sys:{code}", "", "", "sys", "SYS", None, f"System: {a['message']}",
                                   priority="high" if a["level"] == "error" else "medium"))
        return conds, set()
