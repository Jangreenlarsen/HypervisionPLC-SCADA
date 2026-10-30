"""Symbolstandard fase 2: fundet position, tilstand og afvigelsesalarm (lag 3).

Teknik: docs/SYMBOLSTANDARD_IMPLEMENTERING.md afsnit 5.2. Reference: prototypens `remotePos` og `status`.

For hvert symbol med positioner i en aktiv tegningsversion:
1. Fundet position: præcis én position hvis alle planer med et sat-signal (ikke puls) og en værdi i cellen
   matcher signalets tilbagemelding (ellers kommando-tagget). Ingen eller flere → ukendt.
2. Tilstand: komm.fejl på et læst tag → unknown. Remote: pending i valideringstiden efter et valg der endnu ikke
   ses, ellers confirmed/unknown. Lokal: fundet = valgt → confirmed; i valideringstiden → pending; ellers mismatch.
3. Pseudo-tags i live-cachen (`sym:<tegning>:<element>:pos|remote|state|locked`) — så Overview og animationerne
   bruger den eksisterende WebSocket uændret.
4. Afvigelse (Lokal, alarm valgt) → alarm med symbolets niveau. Komm.fejl fryser alarmen (rydder den ikke).
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

from ..storage.db import Database
from .alarms import Condition
from .live_cache import LiveCache, LiveValue
from .svg_sanitize import describe_element, index_svg
from .symbols import PSEUDO_KINDS, logic_pseudo_tags, logic_results, pseudo_tag

log = logging.getLogger(__name__)


@dataclass
class SymbolState:
    """Beregnet tilstand for ét symbol (det Overview og alarmerne bruger)."""
    pos: int | None = None        # vist position (Lokal: valgt; Remote: fundet)
    remote: int | None = None     # fundet position
    state: str = "unknown"        # confirmed | pending | mismatch | unknown
    locked: bool = False
    comm_error: bool = False
    read_tags: list[str] = field(default_factory=list)


def _same(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return False
    try:
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-6)
    except (TypeError, ValueError):
        return False


def remote_position(cfg: dict[str, Any], value_of: Any) -> tuple[int | None, bool, list[str]]:
    """(fundet position | None, komm.fejl?, læste tags). `value_of(tag)` → LiveValue."""
    sigs = {s["id"]: s for s in cfg.get("signals", [])}
    n = len(cfg.get("positions", []))
    read: list[str] = []
    values: dict[str, Any] = {}
    comm = False
    for p in cfg.get("planes", []):
        s = sigs.get(p["signal"])
        if not s or not (s.get("tag") or s.get("fb")) or (s.get("write") == "pulse" and not s.get("fb")):
            continue   # passiv visning har kun en tilbagemelding (intet kommando-tag)
        name = s.get("fb") or s["tag"]
        if name in values:
            continue
        lv = value_of(name)
        read.append(name)
        if lv.quality != "good" or lv.value is None:
            comm = True
            values[name] = None
        else:
            values[name] = lv.value
    if comm:
        return None, True, read
    hits = []
    for j in range(n):
        ok, used = True, 0
        for p in cfg.get("planes", []):
            s = sigs.get(p["signal"])
            if not s or not (s.get("tag") or s.get("fb")) or (s.get("write") == "pulse" and not s.get("fb")) or j >= len(p["values"]):
                continue
            cell = p["values"][j]
            if cell is None:
                continue
            used += 1
            if not _same(values.get(s.get("fb") or s["tag"]), cell):
                ok = False
                break
        if ok and used:
            hits.append(j)
    return (hits[0] if len(hits) == 1 else None), False, read


def compute_state(cfg: dict[str, Any], remote: int | None, comm: bool, chosen: int | None, chosen_at: float,
                  now: float) -> SymbolState:
    """Prototypens `status` + `shownPos`."""
    local = cfg.get("display") == "local"
    waiting = now - chosen_at < float(cfg.get("validate_s", 5))
    if comm:
        st = SymbolState(pos=chosen if local else None, remote=None, state="unknown", comm_error=True)
    elif not local:
        if waiting and chosen is not None and remote != chosen:
            st = SymbolState(pos=remote, remote=remote, state="pending")
        else:
            st = SymbolState(pos=remote, remote=remote, state="unknown" if remote is None else "confirmed")
    elif chosen is None:
        st = SymbolState(pos=remote, remote=remote, state="unknown" if remote is None else "confirmed")
    elif remote == chosen:
        st = SymbolState(pos=chosen, remote=remote, state="confirmed")
    elif waiting:
        st = SymbolState(pos=chosen, remote=remote, state="pending")
    else:
        st = SymbolState(pos=chosen, remote=remote, state="mismatch")
    lock = (cfg.get("lock") or {}).get("positions") or []
    st.locked = st.pos is not None and st.pos < len(lock) and bool(lock[st.pos])
    return st


class SymbolRuntime:
    def __init__(self, db: Database, cache: LiveCache, drawings: Any, *, tick_s: float = 0.5):
        self.db = db
        self.cache = cache
        self.drawings = drawings
        self.tick_s = tick_s
        self.symbols: dict[tuple[str, str], dict[str, Any]] = {}     # (tegning, element) → config (aktive)
        self.chosen: dict[tuple[str, str], dict[str, Any]] = {}      # → {"chosen", "chosen_at", "chosen_by"}
        self.states: dict[tuple[str, str], SymbolState] = {}
        self.names: dict[tuple[str, str], str] = {}
        self._signature: Any = None
        self._logic_published: set[str] = set()   # logik-pseudo-tags i live-cachen (så slettede blokke ryddes)

    # ------------------------------------------------------------ indlæsning

    def _current_signature(self) -> Any:
        cfg = self.db._query("SELECT COUNT(*) AS n, MAX(updated_at) AS t FROM symbol_config")[0]
        drawings = tuple((d["id"], d["active_version"]) for d in self.db.list_drawings())
        return (cfg["n"], cfg["t"], drawings)

    def reload(self) -> None:
        """Indlæs konfigurationer for symboler med positioner i de aktive tegningsversioner."""
        symbols: dict[tuple[str, str], dict[str, Any]] = {}
        names: dict[tuple[str, str], str] = {}
        by_drawing: dict[str, list[dict[str, Any]]] = {}
        off = self.drawings.disabled_ids()   # deaktiverede tegninger er offline: ingen positioner, ingen afvigelsesalarmer
        for row in self.db.list_symbol_configs():
            if row["drawing_id"] not in off:
                by_drawing.setdefault(row["drawing_id"], []).append(row)
        for did, rows in by_drawing.items():
            try:
                svg = self.drawings.svg(did)
                index = index_svg(svg)
            except Exception:
                log.exception("Symboler: tegningen %s kunne ikke læses", did)
                continue
            for row in rows:
                cfg = row["config"]
                if row["element"] not in index:
                    continue   # forældreløs: elementet findes ikke i den aktive version
                symbols[(did, row["element"])] = cfg
                info = describe_element(svg, row["element"]) or {}
                names[(did, row["element"])] = info.get("name") or row["element"]
        removed = [k for k in self.symbols if k not in symbols or symbols[k].get("op") != "positions"]
        self.symbols = symbols
        self.names = names
        self.chosen = {(r["drawing_id"], r["element"]): r for r in self.db.list_symbol_states()}
        if removed:
            self.cache.remove([pseudo_tag(d, e, k) for d, e in removed for k in PSEUDO_KINDS])
            for k in removed:
                self.states.pop(k, None)
        self._signature = self._current_signature()

    # ------------------------------------------------------------- beregning

    def evaluate(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        if self._current_signature() != self._signature:
            self.reload()
        updates: dict[str, LiveValue] = {}
        logic_now: set[str] = set()
        by_drawing: dict[str, dict[str, dict[str, Any]]] = {}
        for (d, e), cfg in self.symbols.items():
            if cfg.get("logic"):
                by_drawing.setdefault(d, {})[e] = cfg
        for d, configs in by_drawing.items():   # blokke kan bruge blokke i andre symboler på samme tegning
            for (e, bid), result in logic_results(configs, self.cache.get).items():
                tag = logic_pseudo_tags(d, e, configs[e])[bid]
                updates[tag] = LiveValue(value=result, quality="good" if result is not None else "comm_error", ts=now)
                logic_now.add(tag)
        for key, cfg in self.symbols.items():
            if cfg.get("op") != "positions":
                continue
            remote, comm, read = remote_position(cfg, self.cache.get)
            ch = self.chosen.get(key)
            if ch is None and cfg.get("display") == "local" and remote is not None:
                # Første gang: start med det PLC'en viser (ikke en afvigelse fra en position ingen har valgt)
                ch = self.set_chosen(key, remote, "start", now - float(cfg.get("validate_s", 5)))
            st = compute_state(cfg, remote, comm, ch["chosen"] if ch else None, ch["chosen_at"] if ch else 0.0, now)
            st.read_tags = read
            self.states[key] = st
            quality = "comm_error" if comm else "good"
            d, e = key
            for kind, value in (("pos", st.pos), ("remote", st.remote), ("state", st.state), ("locked", st.locked)):
                updates[pseudo_tag(d, e, kind)] = LiveValue(value=value, quality=quality, ts=now)
        stale = self._logic_published - logic_now
        if stale:
            self.cache.remove(sorted(stale))
        self._logic_published = logic_now
        if updates:
            self.cache.update(updates)

    def set_chosen(self, key: tuple[str, str], position: int | None, by: str, at: float | None = None) -> dict[str, Any]:
        """Sidst valgte position (betjening, accept, start) — gemmes så den overlever genstart."""
        at = time.time() if at is None else at
        row = {"drawing_id": key[0], "element": key[1], "chosen": position, "chosen_at": at, "chosen_by": by}
        self.db.set_symbol_state(key[0], key[1], position, at, by)
        self.chosen[key] = row
        return row

    def state(self, drawing_id: str, element: str) -> SymbolState | None:
        return self.states.get((drawing_id, element))

    # ------------------------------------------------------------ alarmer

    def alarm_conditions(self, now: float) -> tuple[list[Condition], set[str]]:
        """Afvigelse (Lokal) → alarm med symbolets niveau. Ukendt pga. komm.fejl → alarmen fryses."""
        conds: list[Condition] = []
        frozen: set[str] = set()
        for (d, e), cfg in self.symbols.items():
            level = cfg.get("alarm") or ""
            if cfg.get("op") != "positions" or cfg.get("display") != "local" or not level:
                continue
            st = self.states.get((d, e))
            tag = pseudo_tag(d, e, "state")
            if st is None:
                continue
            if st.comm_error:
                frozen.add(tag)
                continue
            if st.state != "mismatch":
                continue
            labels = [p["label"] for p in cfg.get("positions", [])]
            name = self.names.get((d, e), e)
            shown = labels[st.pos] if st.pos is not None and st.pos < len(labels) else "?"
            found = labels[st.remote] if st.remote is not None and st.remote < len(labels) else "ingen position"
            plc = ""
            for s in cfg.get("signals", []):
                t = self.db.get_tag(s.get("tag", "")) if s.get("tag") else None
                if t:
                    plc = t["plc"]
                    break
            conds.append(Condition(f"sym:{d}:{e}", tag, plc, "symbol", "AFV", st.pos,
                                   f"{name}: valgt {shown}, PLC viser {found}", 0.0, priority=level))
        return conds, frozen

    # ------------------------------------------------------------- løkke

    async def run(self) -> None:
        queue = self.cache.subscribe()
        try:
            while True:
                try:
                    await asyncio.wait_for(queue.get(), timeout=self.tick_s)
                    while not queue.empty():
                        queue.get_nowait()
                except asyncio.TimeoutError:
                    pass
                try:
                    self.evaluate()
                except Exception:
                    log.exception("Fejl i symbolberegning")
        finally:
            self.cache.unsubscribe(queue)
