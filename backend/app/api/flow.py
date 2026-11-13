"""REST for flowet i Tegn (v6.3.0, PLAN.md › Flow-model runde 2): preview af flowet for tegningen, som den ser ud i editoren
lige nu (også ugemt) — med de live værdier eller simuleret (pumper, rate, ventilpositioner). Skriver aldrig til PLC'en og udgiver
ingen live-værdier. Se services/flow_calc.py › preview."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any

from fastapi import APIRouter, Request

from ..services.errors import ServiceError
from ..services.flow_calc import preview
from ..services.flow_defs import merged, piece_types
from ..services.svg_sanitize import MAX_SVG_BYTES
from .auth import ENGINEER

log = logging.getLogger("scada.flow")
router = APIRouter(prefix="/api/drawings")
_busy = asyncio.Semaphore(2)          # en Pi skal ikke regne mange store net på én gang
MAX_OVERRIDES = 500


def _fractions(raw: Any, what: str) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise ServiceError(400, f"{what} skal være et objekt {{element: 0,00–1,00}}")
    out: dict[str, float] = {}
    for k, v in raw.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or not 0 <= v <= 1:
            raise ServiceError(400, f"'{k}': {what.lower()} skal være et tal mellem 0,00 og 1,00")
        out[str(k)[:120]] = round(float(v), 2)
    return out


def _clean(body: dict[str, Any]) -> tuple[str, dict[str, float], dict[str, int], dict[str, float]]:
    svg = body.get("svg")
    if not isinstance(svg, str) or not svg.strip():
        raise ServiceError(400, "Send tegningens SVG (svg)")
    if len(svg.encode("utf-8", "ignore")) > MAX_SVG_BYTES:
        raise ServiceError(400, f"Tegningen er for stor (max {MAX_SVG_BYTES // 1024 // 1024} MB)")
    raw = [body.get("rates") or {}, body.get("positions") or {}, body.get("restricts") or {}]
    if not all(isinstance(x, dict) for x in raw):
        raise ServiceError(400, "rates, positions og restricts skal være objekter {element: værdi}")
    if sum(len(x) for x in raw) > MAX_OVERRIDES:
        raise ServiceError(400, f"Højst {MAX_OVERRIDES} simulerede værdier pr. beregning")
    rates = _fractions(raw[0], "Raten")
    restricts = _fractions(raw[2], "Restriktionen")
    pos_in = raw[1]
    positions: dict[str, int] = {}
    for k, v in pos_in.items():
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < 64:
            raise ServiceError(400, f"Ventilen '{k}': positionen skal være et helt tal (0, 1, 2 …)")
        positions[str(k)[:120]] = v
    return svg, rates, positions, restricts


@router.post("/{drawing_id}/flow/preview", dependencies=[ENGINEER])
async def flow_preview(drawing_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
    st = request.app.state
    st.drawing_service._require(drawing_id)
    if not st.scope_service.can_see_drawing(request.state.user, drawing_id):
        raise ServiceError(404, f"Tegningen '{drawing_id}' findes ikke")
    svg, rates, sim_positions, restricts = _clean(body)
    db, cache = st.drawing_service.db, st.cache
    rt = getattr(st, "symbol_runtime", None)
    configs = {r["element"]: r["config"] for r in db.list_symbol_configs(drawing_id)}
    positions = {e: getattr(rt.states.get((drawing_id, e)), "pos", None) if rt is not None else None for e in configs}
    defs = merged(db.list_symbol_flow())

    def read(tag: str) -> Any:
        lv = cache.get(tag)
        return lv.value if lv is not None and lv.quality == "good" else None

    simulated = bool(rates or sim_positions or restricts)
    if _busy.locked():                    # køer ikke: en optaget Pi svarer "prøv igen" (Tegn spørger igen om 2 s)
        raise ServiceError(429, "Flowberegningen er optaget — prøver igen om lidt")
    async with _busy:
        t0 = time.perf_counter()
        try:
            out = await asyncio.to_thread(preview, svg, defs, configs, positions, read, rates, sim_positions, restricts)
        except Exception as exc:          # en tegning, der ikke kan læses: en forståelig fejl, ikke en 500
            log.warning("Flow-preview fejlede for %s: %s", drawing_id, exc)
            raise ServiceError(400, "Tegningen kunne ikke læses til flowberegningen") from None
        ms = round((time.perf_counter() - t0) * 1000, 1)
    if rt is not None:
        rt.flow.stats["previews"] = rt.flow.stats.get("previews", 0) + 1
    log.debug("Flow-preview %s: %d elementer med flow, %.1f ms (simuleret: %s)", drawing_id, len(out["flows"]), ms, simulated)
    return {**out, "ms": ms, "simulated": simulated,
            "units": {t: d.get("medium", "water") for t, d in defs.items() if d.get("medium")}, "pieces": sorted(piece_types(defs))}
