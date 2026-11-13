"""Simulator (v6.5.0, PLAN.md › Simulator): test en tegnings tilstande med indskudte værdier.

- **Variablerne** (`variables`): systemet gennemgår tegningen og finder alt, hvad den læser — tags fra PLC'en (bindinger, symbolernes
  signaler og tilbagemeldinger, animationskilder, logikindgange, flowets tags), symbolernes positioner og de alarmer, animationer
  styres af. For hvert tag: type, min/max, enhed, hvor det bruges, og den live værdi lige nu.
- **Beregningen** (`simulate`): med de indskudte værdier (resten følger PLC'en) regnes de AFLEDTE værdier med den samme kode som
  driften — logikblokke, symbolernes position og tilstand, og flowet (`flow:`, `flowp:`, `flowlvl:`). Resultatet er hele den
  værditabel, Overview-motoren tegner ud fra.
- Simulatoren skriver **aldrig** til PLC'en og udgiver intet i live-cachen.
- **Scenarier**: et navngivet sæt værdier og positioner pr. tegning (tabel `sim_scenarios`), følger med i backup.
"""

from __future__ import annotations

import logging
import math
import re
import time
from typing import Any, Callable

from .bindings import binding_tags
from .errors import ServiceError
from .flow_calc import flow_tag, level_tag, ports_tag, ports_text, preview
from .flow_defs import merged
from .live_cache import LiveValue
from .symbol_runtime import compute_state, remote_position
from .svg_sanitize import index_svg
from .symbols import ANIM_LABEL, PSEUDO_KINDS, config_tags, logic_pseudo_tags, logic_results, parse_alarm_ref, pseudo_tag

log = logging.getLogger("scada.simulator")

MAX_VALUES = 1000
MAX_POSITIONS = 500
MAX_SCENARIOS = 50
_NAME = re.compile(r"^[^\x00-\x1f]{1,60}\Z")
DERIVED = ("sym:", "flow:", "flowp:", "flowlvl:")


def _clean_value(k: Any, v: Any) -> Any:
    if not isinstance(k, str) or not 0 < len(k) <= 200:
        raise ServiceError(400, "Et simuleret navn skal være tekst (højst 200 tegn)")
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        if not math.isfinite(v):
            raise ServiceError(400, f"'{k}': værdien skal være et endeligt tal")
        return v
    if isinstance(v, str) and len(v) <= 200:
        return v
    raise ServiceError(400, f"'{k}': værdien skal være Til/Fra, et tal, en kort tekst eller null (komm.fejl)")


def clean_values(raw: Any) -> dict[str, Any]:
    """{tag: værdi} — Til/Fra, tal, tekst eller null (= komm.fejl)."""
    if not isinstance(raw, dict) or len(raw) > MAX_VALUES:
        raise ServiceError(400, f"values skal være et objekt med højst {MAX_VALUES} værdier")
    return {k: _clean_value(k, v) for k, v in raw.items()}


def clean_positions(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict) or len(raw) > MAX_POSITIONS:
        raise ServiceError(400, f"positions skal være et objekt med højst {MAX_POSITIONS} symboler")
    out: dict[str, int] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not 0 < len(k) <= 120 or not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < 64:
            raise ServiceError(400, f"'{k}': positionen skal være et helt tal (0, 1, 2 …)")
        out[k] = v
    return out


def clean_name(raw: Any) -> str:
    name = " ".join(str(raw or "").split())
    if not _NAME.match(name):
        raise ServiceError(400, "Giv scenariet et navn (højst 60 tegn)")
    return name


def clean_scenario(raw: Any) -> dict[str, Any]:
    """Et scenarie fra API'et eller en backup → {name, values, positions}."""
    if not isinstance(raw, dict):
        raise ServiceError(400, "Et scenarie skal være et objekt")
    return {"name": clean_name(raw.get("name")), "values": clean_values(raw.get("values") or {}),
            "positions": clean_positions(raw.get("positions") or {})}


def _names(svg: str) -> dict[str, str]:
    from defusedxml.ElementTree import fromstring
    return {el.get("id"): el.get("data-hv-name") for el in fromstring(svg, forbid_dtd=True).iter()
            if isinstance(el.tag, str) and el.get("id") and el.get("data-hv-name")}


def _lv(v: LiveValue | None) -> dict[str, Any]:
    return {"value": v.value, "quality": v.quality} if v is not None else {"value": None, "quality": "unknown"}


class SimulatorService:
    def __init__(self, db: Any, drawings: Any, cache: Any, runtime: Callable[[], Any]):
        self.db = db
        self.drawings = drawings
        self.cache = cache
        self.runtime = runtime            # symbol-runtimen (positioner valgt af operatøren), kan være None i tests
        self.stats: dict[str, Any] = {"simulations": 0, "last_ms": 0.0, "errors": 0}

    # ------------------------------------------------------------ variablerne

    def _context(self, drawing_id: str, names: bool = True) -> tuple[str, list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
        self.drawings._require(drawing_id)
        svg = self.drawings.svg(drawing_id)
        eff = self.drawings.effective_bindings(drawing_id)
        configs = {r["element"]: r["config"] for r in self.db.list_symbol_configs(drawing_id)}
        return svg, eff, configs, (_names(svg) if names else {})

    def variables(self, drawing_id: str) -> dict[str, Any]:
        svg, eff, configs, names = self._context(drawing_id)
        # v6.8.3 (Jan: "hvad er det for symboler … i den her er en pumpe og en 3-vejs ventil"): kun symboler, der findes i den
        # udgivne tegning — en opsætning på et fjernet element (forældreløs, se Bindinger) og dens tags vises ikke.
        # Beregningen (simulate) bruger stadig dem alle, som driften gør.
        present = set(index_svg(svg))
        orphaned = sorted(e for e in configs if e not in present)
        configs = {e: c for e, c in configs.items() if e in present}
        tags = {t["name"]: t for t in self.db.list_tags()}
        nm = lambda el: names.get(el) or el  # noqa: E731
        uses: dict[str, list[str]] = {}
        els: dict[str, set[str]] = {}

        def use(t: str, what: str, el: str) -> None:
            lst = uses.setdefault(t, [])
            if what not in lst and len(lst) < 20:
                lst.append(what)
            els.setdefault(t, set()).add(el)

        for b in eff:
            el = b.get("symbol") or b.get("group_name") or b.get("conn_group_name") or b["element"]
            for t in binding_tags(b):
                use(t, f"{nm(el)} · {ANIM_LABEL.get(b['anim'], b['anim'])}", b.get("symbol") or b["element"])
        for el, cfg in configs.items():
            for t in config_tags(cfg):
                use(t, f"{nm(el)} · opsætning", el)
            for a in cfg.get("anims", []):
                if (ref := parse_alarm_ref(a.get("src"))) is not None:
                    use(f"alarm:{ref[1]}:{ref[0]}", f"{nm(el)} · {ANIM_LABEL.get(a.get('type'), a.get('type'))}", el)
        out_tags, alarms = [], []
        for t, where in sorted(uses.items()):
            if t.startswith(DERIVED):
                continue
            if t.startswith("alarm:"):
                _, tag, kind = t.split(":", 2) if t.count(":") >= 2 else ("", t, "")
                alarms.append({"name": t, "tag": tag, "kind": kind, "used": where, "elements": sorted(els.get(t, ())),
                               "live": _lv(self.cache.get(t))})
                continue
            row = tags.get(t)
            if row is None:
                continue
            out_tags.append({"name": t, "kind": "bool" if self.drawings._is_bool(row) else "num", "unit": row.get("unit") or "",
                             "min": row.get("min"), "max": row.get("max"), "decimals": row.get("decimals"),
                             "description": row.get("description") or "", "plc": row.get("plc") or "",
                             "used": where, "elements": sorted(els.get(t, ())), "live": _lv(self.cache.get(t))})
        rt = self.runtime()
        positions = []
        for el, cfg in sorted(configs.items()):
            if cfg.get("op") != "positions":
                continue
            st = rt.states.get((drawing_id, el)) if rt is not None else None
            positions.append({"element": el, "name": nm(el), "labels": [p.get("label", "") for p in cfg.get("positions", [])],
                              "states": [p.get("state") for p in cfg.get("positions", [])],
                              "display": cfg.get("display", "remote"), "live": getattr(st, "pos", None)})
        return {"tags": out_tags, "positions": positions, "alarms": alarms, "orphaned": orphaned}

    # ------------------------------------------------------------ beregningen

    def simulate(self, drawing_id: str, values: dict[str, Any], positions: dict[str, int]) -> dict[str, Any]:
        """Hele værditabellen for tegningen med de indskudte værdier (resten live). Skriver og udgiver intet."""
        t0 = time.perf_counter()
        now = time.time()
        svg, eff, configs, _ = self._context(drawing_id, names=False)
        derived: dict[str, LiveValue] = {}

        def lv(name: str) -> LiveValue:
            if name in values:
                v = values[name]
                return LiveValue(value=None, quality="comm_error", ts=now) if v is None else LiveValue(value=v, quality="good", ts=now)
            if name in derived:
                return derived[name]
            return self.cache.get(name)

        # positioner og tilstand FØRST (en logikblok kan læse et symbols position): en tvungen position gælder både vist og fundet
        rt = self.runtime()
        pos_now: dict[str, int | None] = {}
        for e, cfg in configs.items():
            if cfg.get("op") != "positions":
                continue
            if e in positions:
                p = max(0, min(positions[e], len(cfg.get("positions", [])) - 1))   # en position, symbolet har
                remote, comm, chosen = p, False, p
            else:
                remote, comm, _read = remote_position(cfg, lv)
                ch = rt.chosen.get((drawing_id, e)) if rt is not None else None
                chosen = ch["chosen"] if ch else remote
            st = compute_state(cfg, remote, comm, chosen, now - 3600, now)
            pos_now[e] = st.pos
            for kind in PSEUDO_KINDS:
                derived[pseudo_tag(drawing_id, e, kind)] = LiveValue(value=getattr(st, kind), quality="comm_error" if comm else "good",
                                                                     ts=now)
        # logikblokke (kan bruge blokke i andre symboler og symbolernes position)
        logic_cfgs = {e: c for e, c in configs.items() if c.get("logic")}
        for (e, bid), r in logic_results(logic_cfgs, lv).items():
            derived[logic_pseudo_tags(drawing_id, e, logic_cfgs[e])[bid]] = LiveValue(
                value=r, quality="good" if r is not None else "comm_error", ts=now)
        # flowet (samme beregning som driften og Tegn), med positionerne ovenfor
        read = lambda t: (x.value if (x := lv(t)) is not None and x.quality == "good" else None)  # noqa: E731
        flow_notes: list[str] = []
        if any(c.get("flow") for c in configs.values()):
            res = preview(svg, merged(self.db.list_symbol_flow()), configs, pos_now, read)
            flow_notes = res["notes"]
            for el, v in res["flows"].items():
                derived[flow_tag(drawing_id, el)] = LiveValue(value=v, quality="good", ts=now)
            for el, p in res["ports"].items():
                derived[ports_tag(drawing_id, el)] = LiveValue(value=ports_text(p), quality="good", ts=now)
            for el, v in res["levels"].items():
                derived[level_tag(drawing_id, el)] = LiveValue(value=v, quality="good" if v is not None else "comm_error", ts=now)
        # alle navne tegningen læser: bindingernes tags (afledte uden flow = 0 / tom), symbolernes pseudo-tags
        table: dict[str, dict[str, Any]] = {}
        for b in eff:
            for t in binding_tags(b):
                if t.startswith(("flow:", "flowp:")) and t not in derived:
                    table[t] = {"value": 0.0 if t.startswith("flow:") else "", "quality": "good"}
                else:
                    table[t] = _lv(lv(t))
        for e, cfg in configs.items():
            if cfg.get("op") == "positions":
                for kind in PSEUDO_KINDS:
                    t = pseudo_tag(drawing_id, e, kind)
                    table[t] = _lv(lv(t))
            if cfg.get("fault"):
                table[cfg["fault"]] = _lv(lv(cfg["fault"]))
        for t in values:
            table.setdefault(t, _lv(lv(t)))
        ms = round((time.perf_counter() - t0) * 1000, 1)
        self.stats["simulations"] += 1
        self.stats["last_ms"] = ms
        return {"values": table, "notes": flow_notes, "ms": ms, "simulated": len(values) + len(positions)}

    # ------------------------------------------------------------ scenarier

    def scenarios(self, drawing_id: str) -> list[dict[str, Any]]:
        self.drawings._require(drawing_id)
        return [{k: r[k] for k in ("id", "name", "values", "positions", "updated_at", "updated_by")}
                for r in self.db.list_sim_scenarios(drawing_id)]

    def save_scenario(self, actor: Any, drawing_id: str, sid: int | None, body: Any) -> dict[str, Any]:
        self.drawings._require(drawing_id)
        clean = clean_scenario(body)
        if sid is None and len(self.db.list_sim_scenarios(drawing_id)) >= MAX_SCENARIOS:
            raise ServiceError(400, f"Højst {MAX_SCENARIOS} scenarier pr. tegning")
        new = self.db.write_sim_scenario(drawing_id, sid, clean["name"], clean["values"], clean["positions"], actor.username)
        if new is None:
            if sid is not None and not any(r["id"] == sid for r in self.db.list_sim_scenarios(drawing_id)):
                raise ServiceError(404, "Scenariet findes ikke")
            raise ServiceError(409, f"Scenariet '{clean['name']}' findes allerede")
        log.info("Simulator-scenarie '%s' gemt på %s af %s (%d værdier, %d positioner)", clean["name"], drawing_id, actor.username,
                 len(clean["values"]), len(clean["positions"]))
        return next(r for r in self.scenarios(drawing_id) if r["id"] == new)

    def delete_scenario(self, drawing_id: str, sid: int) -> None:
        self.drawings._require(drawing_id)
        if not self.db.delete_sim_scenario(drawing_id, sid):
            raise ServiceError(404, "Scenariet findes ikke")
