"""Flowberegning (v6.1.0, PLAN.md › Flow-model): systemet beregner selv flowet gennem tegningens forbundne symboler og rør.

**Grundlag**
- **Topologien** er tegningens gemte forbindelser (*Bind forbindelser*, `data-hv-links="nøgle>andet-id:nøgle;…"`). En rørende
  hedder `s`/`e` (start/slut) og `~` (midt på), et symbols punkt `x,y` (brøkdel af symbolets boks).
- **Symbolernes flow-data** står i deres opsætning (`flow`: pumpe ja/nej, kapacitet l/min, flow-rate og restriktion fra et tag
  eller en fast værdi, og hvilke veje der er åbne i hver position). Ind/ud og veje pr. symboltype kommer fra `flow_defs.py`.

**Model A (fordeling efter restriktion)**
- Netværket regnes som ledninger med en *ledningsevne* `g`:
  - rør, rørstykker og symboler uden veje: næsten ingen modstand (`G_PIPE`);
  - en åben vej gennem en ventil (eller et symbol med restriktion): `restriktion × G_VALVE`;
  - restriktion 0 = blokeret (vejen findes ikke).
- Hver pumpe, der kører, giver `rate × kapacitet` (l/min) ind i sit UD-punkt og tager det samme ud af sit IND-punkt.
- Flowet fordeler sig som strøm i et elektrisk net: parallelle grene i forhold til deres ledningsevne, og en delvist lukket ventil
  i serie begrænser pumpens flow med forholdet mellem nettets ledningsevne med og uden restriktionerne.
- Envejs-veje (en kontraventil, en pumpe der står, en vej fra IND til UD) lukkes, hvis flowet vil den forkerte vej, og der
  regnes igen (højst `MAX_PASSES` gange). Flere pumper lægges sammen.
- Ligningerne løses eksakt med sparsom Gauss-elimination (laveste grad først). Rørnet er næsten træer, så det er hurtigt
  også på en Raspberry Pi.

**Resultatet** er live-værdier `flow:<tegning>:<element>` i l/min:
- et rør: med fortegn, + = fra rørets start mod slut (tegneretningen);
- et symbol og et rørstykke: uden fortegn (mængden igennem);
- en pumpe: det flow, den giver.

Desuden `flowp:<tegning>:<element>` for et rørstykke (v6.3.0): flowet ind (+) og ud (−) ved hvert af dets punkter, som tekst
`"x,y:+12.0;1,0.5:-12.0"` — så løbelyset på en bøjning, et T-stykke eller et kryds kan vise retningen pr. delstreg.

**Flowmåler** (v6.3.0): et symbol med et målt flow (`flow.measured`, et tag i l/min) skalerer de pumper, der giver flow gennem
det, så beregningen passer med målingen.

**Kun til visning:** flowet er en illustration af, hvordan anlægget hænger sammen — ikke en simulering af det virkelige anlæg.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from defusedxml.ElementTree import fromstring

from .flow_defs import PIPE_SYMBOL_TYPES, directions, kind_of, match_ports, merged, piece_types, way_key, ways_of
from .live_cache import LiveValue

log = logging.getLogger("scada.flow")

G_PIPE = 1000.0       # rør og rørstykker: næsten ingen modstand
G_VALVE = 1.0         # en helt åben ventil (restriktion 1)
MAX_PASSES = 6        # genberegninger, når envejs-veje lukkes
EPS = 1e-9
MAX_CAPACITY = 65535  # l/min (16 bit)
MAX_METER_FACTOR = 10.0   # en flowmåler skalerer pumperne højst så mange gange (en forkert måling må ikke give vilde tal)


def flow_tag(drawing_id: str, element: str) -> str:
    """Live-navnet for et elements beregnede flow (`:` findes ikke i tag-navne)."""
    return f"flow:{drawing_id}:{element}"


def level_tag(drawing_id: str, element: str) -> str:
    """Live-navnet for et symbols flow-niveau (v6.4.0): det målte flow mellem lavt (0,00) og højt (1,00)."""
    return f"flowlvl:{drawing_id}:{element}"


def flow_levels(configs: dict[str, dict[str, Any]], read: Callable[[str], Any]) -> dict[str, float | None]:
    """{element: flow-niveau 0,00–1,00} for symboler med et målt flow og en baseline (Jan: fx lavt 15,1 og højt 16,5 → målt 15,85
    = 0,54). None = målingen er ukendt (komm.fejl)."""
    out: dict[str, float | None] = {}
    for el, c in configs.items():
        m = (c.get("flow") or {}).get("measured") or {}
        src = str(m.get("src") or "")
        if not src or src.startswith("@"):
            continue
        lo, hi = float(m.get("low", 0)), float(m.get("high", 100))
        v = read(src)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or hi <= lo:
            out[el] = None
            continue
        out[el] = round(max(0.0, min(1.0, (float(v) - lo) / (hi - lo))), 3)
    return out


def ports_tag(drawing_id: str, element: str) -> str:
    """Live-navnet for et rørstykkes flow pr. punkt (v6.3.0)."""
    return f"flowp:{drawing_id}:{element}"


def ports_text(ports: dict[str, float]) -> str:
    """{punkt: flow ind (+)/ud (−)} → "x,y:+12.0;…" (sorteret, så teksten kun skifter, når flowet gør)."""
    return ";".join(f"{k}:{v:+.1f}" for k, v in sorted(ports.items()))


# ------------------------------------------------------------------ topologi (fra SVG'en)

@dataclass
class Element:
    id: str
    kind: str                  # pipe | piece | symbol | other
    type: str
    name: str
    keys: set[str] = field(default_factory=set)


@dataclass
class Topology:
    elements: dict[str, Element]
    links: list[tuple[tuple[str, str], tuple[str, str]]]


def _local(tag: Any) -> str:
    return str(tag).rsplit("}", 1)[-1]


def parse_topology(svg: str, pieces: frozenset[str] | None = None) -> Topology:
    """Elementerne og de gemte forbindelser. Forbindelser til elementer, der ikke findes, springes over. `pieces`: typerne, der
    er rørstykker (de indbyggede + typer med rollen rørstykke i deres flow-profil)."""
    pieces = PIPE_SYMBOL_TYPES if pieces is None else pieces
    root = fromstring(svg, forbid_dtd=True)
    elements: dict[str, Element] = {}
    raw: list[tuple[str, str, str, str]] = []
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        eid = el.get("id")
        if not eid:
            continue
        links = el.get("data-hv-links")
        typ = el.get("data-hv-type") or ""
        pipe = el.get("data-hv-pipe") is not None
        if not (links or pipe or typ):
            continue
        kind = "pipe" if pipe else "piece" if typ in pieces else "symbol" if typ else "other"
        e = Element(eid, kind, typ, el.get("data-hv-name") or "")
        if pipe:
            e.keys.update(("s", "e"))
        elements[eid] = e
        for item in (links or "").split(";"):
            gt, colon = item.find(">"), item.rfind(":")
            if gt > 0 and colon > gt + 1 and colon < len(item) - 1:
                raw.append((eid, item[:gt], item[gt + 1:colon], item[colon + 1:]))
    out: list[tuple[tuple[str, str], tuple[str, str]]] = []
    seen: set[tuple[tuple[str, str], tuple[str, str]]] = set()
    for a, ka, b, kb in raw:
        if a not in elements or b not in elements or a == b:
            continue
        pair = tuple(sorted(((a, ka), (b, kb))))
        if pair in seen:
            continue
        seen.add(pair)   # type: ignore[arg-type]
        elements[a].keys.add(ka)
        elements[b].keys.add(kb)
        out.append(((a, ka), (b, kb)))
    return Topology(elements, out)


# ------------------------------------------------------------------ lineær løsning

def solve(n: int, edges: list[tuple[int, int, float]], inject: dict[int, float], ground: int) -> list[float]:
    """Potentialer for et net med ledningsevner `edges` (u, v, g) og indsprøjtet strøm `inject` (summen 0). `ground` = 0.
    Sparsom Gauss-elimination, laveste grad først. Knuder uden forbindelse til `ground` får 0."""
    rows: dict[int, dict[int, float]] = {}
    for u, v, g in edges:
        if u == v or g <= 0:
            continue
        for a, b in ((u, v), (v, u)):
            r = rows.setdefault(a, {})
            r[a] = r.get(a, 0.0) + g
            r[b] = r.get(b, 0.0) - g
    # kun den del af nettet, der hænger sammen med ground
    reach = {ground}
    stack = [ground]
    while stack:
        x = stack.pop()
        for y in rows.get(x, {}):
            if y not in reach:
                reach.add(y)
                stack.append(y)
    A = {i: {j: w for j, w in rows[i].items() if j in reach and j != ground} for i in reach if i != ground and i in rows}
    b = {i: inject.get(i, 0.0) for i in A}
    order: list[int] = []
    pivots: dict[int, dict[int, float]] = {}
    rhs: dict[int, float] = {}
    alive = set(A)
    while alive:
        k = min(alive, key=lambda i: (len(A[i]), i))
        alive.discard(k)
        row = A.pop(k)
        piv = row.get(k, 0.0)
        if abs(piv) < EPS:
            pivots[k], rhs[k] = {}, 0.0
            order.append(k)
            for j in row:
                if j in A:
                    A[j].pop(k, None)
            continue
        bk = b.pop(k)
        for j, ajk in list(row.items()):
            if j == k or j not in A:
                continue
            f = A[j].get(k, 0.0) / piv
            if f == 0.0:
                continue
            for m, akm in row.items():
                if m == k:
                    continue
                A[j][m] = A[j].get(m, 0.0) - f * akm
            A[j].pop(k, None)
            b[j] -= f * bk
        pivots[k], rhs[k] = row, bk
        order.append(k)
    V = [0.0] * n
    for k in reversed(order):
        row = pivots[k]
        piv = row.get(k, 0.0)
        if abs(piv) < EPS:
            continue
        s = rhs[k] - sum(w * V[j] for j, w in row.items() if j != k)
        V[k] = s / piv
    return V


# ------------------------------------------------------------------ nettet for én tegning

@dataclass
class Edge:
    u: int
    v: int
    el: str
    g: float
    oneway: bool          # kun u → v
    sign: float = 1.0     # rør: + = mod rørets slut
    g_open: float = 0.0   # ledningsevnen helt åben (restriktion 1) — til restriktionsfaktoren; 0 = som g
    ka: str = ""          # elementets punkt ved u og v (til flowet pr. punkt på et rørstykke)
    kb: str = ""


@dataclass
class Pump:
    el: str
    out_v: int
    in_v: int
    q: float              # l/min, rate × kapacitet × egen restriktion


def _fraction(spec: Any, read: Callable[[str], Any]) -> float:
    """Flow-rate/restriktion (0–1) fra `{src, max}`: et tag eller en fast værdi (`@val:x`). Ukendt eller dårlig værdi = 0."""
    if not isinstance(spec, dict):
        return 1.0
    src = str(spec.get("src") or "")
    top = float(spec.get("max") or 1) or 1.0
    if not src:
        return 1.0
    if src.startswith("@val:"):
        try:
            v = float(src[5:])
        except ValueError:
            return 0.0
    else:
        raw = read(src)
        if raw is None:
            return 0.0
        v = (1.0 if raw else 0.0) if isinstance(raw, bool) else float(raw) if isinstance(raw, (int, float)) else 0.0
    return max(0.0, min(1.0, v / top))


def build(topo: Topology, defs: dict[str, dict[str, Any]], configs: dict[str, dict[str, Any]], positions: dict[str, int | None],
          read: Callable[[str], Any]) -> tuple[int, list[Edge], list[Pump], list[str]]:
    """Knuder (forbundne punkter slås sammen), kanter og pumper. → (antal knuder, kanter, pumper, beskeder)"""
    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def find(x: tuple[str, str]) -> tuple[str, str]:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in topo.links:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    ids: dict[tuple[str, str], int] = {}

    def node(el: str, key: str) -> int:
        r = find((el, key))
        if r not in ids:
            ids[r] = len(ids)
        return ids[r]

    edges: list[Edge] = []
    pumps: list[Pump] = []
    notes: list[str] = []
    for e in topo.elements.values():
        keys = sorted(e.keys)
        cfg = configs.get(e.id) or {}
        fl = cfg.get("flow") or {}
        if len(keys) < 2 and e.kind != "pipe":
            if fl.get("pump"):
                notes.append(f"Pumpen '{e.name or e.id}' er ikke forbundet på både IND og UD (Bind forbindelser)")
            continue
        prof = defs.get(e.type) or {}
        # uden egen flow-opsætning gælder typens profil (v6.3.0): standard-restriktionen
        restrict = _fraction(fl.get("restrict"), read) if fl else float(prof.get("restrict", 1.0))
        if e.kind == "pipe":
            chain = ["s"] + (["~"] if "~" in e.keys else []) + ["e"]
            for a, b in zip(chain, chain[1:]):
                edges.append(Edge(node(e.id, a), node(e.id, b), e.id, G_PIPE, False, 1.0))
            continue
        d = defs.get(e.type) if e.kind == "symbol" else None
        if d is not None and not d.get("ports"):
            d = None                                     # en profil uden punkter: flowet går mellem alle forbundne punkter
        if d is None:
            if restrict <= 0:
                continue
            # et symbol (radiator, tank, kedel …) er en forbruger: regnes som en ventil med sin restriktion, så flowet deler sig efter
            # symbolerne og ikke efter antallet af rør; rørstykker og løse streger regnes som rør
            valve = e.kind == "symbol"
            g, g_open = (G_VALVE * restrict, G_VALVE) if valve else (G_PIPE, G_PIPE)
            for i, a in enumerate(keys):
                for b in keys[i + 1:]:
                    edges.append(Edge(node(e.id, a), node(e.id, b), e.id, g, False, 1.0, g_open, a, b))
            continue
        names = match_ports(d, keys)                    # nøgle → punktets navn
        by_name = {nm: k for k, nm in names.items()}
        roles = {p["name"]: p.get("role", "both") for p in d.get("ports", [])}
        is_pump = bool(fl.get("pump")) if fl else False
        pos = positions.get(e.id)
        opens = fl.get("open") if fl else None
        if opens is None and cfg.get("op") == "positions" and any(p.get("state") for p in cfg.get("positions", [])):
            # v6.7.0 (design B): de åbne veje fra positionernes tilstande (typens definition)
            # en position uden tilstand: alle veje åbne (som før v6.7.0); en ukendt tilstand: lukket
            by_state = {s["name"]: s.get("open", []) for s in (d.get("states") or [])}
            opens = [by_state.get(p["state"], []) if p.get("state") else None for p in cfg.get("positions", [])]
        if is_pump:
            rate = _fraction(fl.get("rate"), read)
            cap = max(0, min(MAX_CAPACITY, int(fl.get("capacity") or 0)))
            out_n = next((n for n in by_name if roles.get(n) == "out"), None)
            in_n = next((n for n in by_name if roles.get(n) == "in"), None)
            if out_n is None or in_n is None:
                # v6.8.5: sig hvilket punkt der mangler, og hvor rørene sidder i stedet (fx øverst/nederst på en pumpe med IND/UD i siderne)
                missing = " og ".join(n for n, v in (("IND", in_n), ("UD", out_n)) if v is None)
                stray = [k for k in keys if k not in names]
                notes.append(f"Pumpen '{e.name or e.id}' er ikke forbundet på {missing}"
                             + (f" — rørene sidder ved {', '.join(_where(k) for k in stray)}; ret dem i Tegn til pumpens IND- og UD-punkt"
                                if stray else " — tjek forbindelserne i Tegn"))
                continue
            q = rate * cap * restrict
            if q > 0:
                pumps.append(Pump(e.id, node(e.id, by_name[out_n]), node(e.id, by_name[in_n]), q))
                continue
            # en pumpe, der står: flow kan passere ind → ud (som en kontraventil)
        if restrict <= 0:
            continue
        for a, b in ways_of(d):
            if a not in by_name or b not in by_name:
                continue
            if isinstance(opens, list) and cfg.get("op") == "positions":
                cur = opens[pos] if pos is not None and 0 <= pos < len(opens) else []
                if cur is not None and (not isinstance(cur, list) or (way_key(a, b) not in cur and way_key(b, a) not in cur)):
                    continue
            fwd, back = directions(d, a, b)
            if not (fwd or back):
                continue
            ka, kb = by_name[a], by_name[b]
            ua, ub = node(e.id, ka), node(e.id, kb)
            g = G_VALVE * restrict
            if fwd and back:
                edges.append(Edge(ua, ub, e.id, g, False, 1.0, G_VALVE, ka, kb))
            elif fwd:
                edges.append(Edge(ua, ub, e.id, g, True, 1.0, G_VALVE, ka, kb))
            else:
                edges.append(Edge(ub, ua, e.id, g, True, 1.0, G_VALVE, kb, ka))
    return len(ids), edges, pumps, notes


def _currents(n: int, edges: list[Edge], pump: Pump) -> list[float] | None:
    """Strømmen (l/min) i hver kant for én pumpe med `q` = 1, efter at envejs-veje mod strømmen er lukket. None = ingen vej."""
    live = list(range(len(edges)))
    for _ in range(MAX_PASSES):
        es = [(edges[i].u, edges[i].v, edges[i].g) for i in live]
        V = solve(n, es, {pump.out_v: 1.0, pump.in_v: -1.0}, pump.in_v)
        if abs(V[pump.out_v]) < EPS:
            return None
        cur = {i: g * (V[edges[i].u] - V[edges[i].v]) for i, (_, _, g) in zip(live, es)}
        wrong = [i for i in live if edges[i].oneway and cur[i] < -1e-6]
        if not wrong:
            out = [0.0] * len(edges)
            for i, c in cur.items():
                out[i] = c
            out.append(V[pump.out_v])          # potentialforskellen ved 1 l/min (til restriktionsfaktoren)
            return out
        live = [i for i in live if i not in wrong]
    return None


def _measured(configs: dict[str, dict[str, Any]], read: Callable[[str], Any]) -> dict[str, float]:
    """{element: målt flow} for symboler med en flowmåler (`flow.measured`), hvis tagget har en god talværdi."""
    out: dict[str, float] = {}
    for el, c in configs.items():
        src = str(((c.get("flow") or {}).get("measured") or {}).get("src") or "")
        if not src or src.startswith("@"):
            continue
        v = read(src)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[el] = abs(float(v))
    return out


def _where(key: str) -> str:
    """Et punkt ("x,y" i brøkdele af symbolets boks) i ord: øverst, nederst, venstre, højre — eller tallene."""
    try:
        x, y = (float(v) for v in key.split(","))
    except ValueError:
        return key
    return {(0.5, 0.0): "øverst", (0.5, 1.0): "nederst", (0.0, 0.5): "venstre", (1.0, 0.5): "højre"}.get((round(x, 2), round(y, 2)), key)


# v6.8.4 (Jan: "jeg har ikke nogen løbelys animation på forbindelser"): en pumpe-type uden egen flow-opsætning er en pumpe med
# typens kapacitet; farten følger dens position (Fra = stop, Til = kører). Uden positioner og uden rate-tag står den stille.
PUMP_OFF_LABELS = frozenset({"fra", "off", "stop", "stoppet", "slukket", "0"})
PUMP_ON_LABELS = frozenset({"til", "on", "start", "kører", "drift", "1"})


def pump_running(cfg: dict[str, Any], pos: int | None) -> bool:
    """Kører en pumpe uden rate-tag i positionen `pos`? Positionens navn afgør (Fra/Til …); ellers: første position = stop."""
    labels = [str(p.get("label") or "").strip().lower() for p in cfg.get("positions", [])]
    if cfg.get("op") != "positions" or pos is None or not 0 <= pos < len(labels):
        return False
    lbl = labels[pos]
    return lbl in PUMP_ON_LABELS or (lbl not in PUMP_OFF_LABELS and pos > 0)


def type_pumps(topo: Topology, defs: dict[str, dict[str, Any]], configs: dict[str, dict[str, Any]],
               positions: dict[str, int | None]) -> dict[str, dict[str, Any]]:
    """Opsætningerne med pumpe-typer uden egen flow-opsætning som pumper (`flow.by_type`). En egen flow-opsætning vinder."""
    out = configs
    for e in topo.elements.values():
        if e.kind != "symbol" or kind_of(defs, e.type) != "pump":
            continue
        cfg = configs.get(e.id) or {}
        # v6.8.7: kun en pumpe med positioner (Fra/Til) — en "kun visning"-pumpe uden flow-opsætning kan aldrig køre og må ikke
        # gøre tegningen til en flow-tegning (varme på demoen fik ellers løbelys-bindinger og falske beskeder)
        if cfg.get("flow") or cfg.get("op") != "positions":
            continue
        rate = 1.0 if pump_running(cfg, positions.get(e.id)) else 0.0
        cap = max(0, min(MAX_CAPACITY, int((defs.get(e.type) or {}).get("capacity") or 100)))
        if out is configs:
            out = dict(configs)
        out[e.id] = {**cfg, "flow": {"pump": True, "capacity": cap, "rate": {"src": f"@val:{rate}", "max": 1}, "by_type": True}}
    return out


def compute(topo: Topology, defs: dict[str, dict[str, Any]], configs: dict[str, dict[str, Any]],
            positions: dict[str, int | None], read: Callable[[str], Any],
            ports_out: dict[str, dict[str, float]] | None = None) -> tuple[dict[str, float], list[str], dict[str, Any]]:
    """→ ({element: flow l/min}, beskeder, statistik). `ports_out` fyldes med rørstykkernes flow pr. punkt (ind +, ud −)."""
    configs = type_pumps(topo, defs, configs, positions)
    n, edges, pumps, notes = build(topo, defs, configs, positions, read)
    flows: dict[str, float] = {}
    total = [0.0] * len(edges)        # strøm med fortegn pr. kant, summeret over pumperne (modsatrettede går ud mod hinanden)
    pumped = 0
    runs: list[tuple[Pump, list[float], float]] = []
    for p in pumps:
        unit = _currents(n, edges, p)
        if unit is None:
            notes.append(f"Pumpen '{topo.elements[p.el].name or p.el}' har ingen åben vej rundt fra UD til IND")
            flows[p.el] = flows.get(p.el, 0.0)
            continue
        # restriktionsfaktor: nettets modstand med restriktionerne mod den samme vej helt åben (1.0 = ingen begrænsning)
        ref = _currents(n, [Edge(e.u, e.v, e.el, e.g_open or e.g, e.oneway, e.sign) for e in edges], p)
        factor = 1.0 if ref is None or unit[-1] <= EPS else max(0.0, min(1.0, ref[-1] / unit[-1]))
        runs.append((p, unit, p.q * factor))
    # flowmålere (v6.3.0): de pumper, der giver flow gennem måleren, skaleres, så beregningen passer med målingen. Gennem måleren
    # regnes NETTO (med fortegn på den samme kant), så pumper, der løber modsat, trækkes fra.
    scaled_by: dict[int, str] = {}
    for el, m in _measured(configs, read).items():
        idx = [i for i, e in enumerate(edges) if e.el == el]
        name = (topo.elements[el].name if el in topo.elements else "") or el
        if not idx:
            notes.append(f"Flowmåleren '{name}' er ikke forbundet (Bind forbindelser)")
            continue
        ref = max(idx, key=lambda i: abs(sum(unit[i] * q for _, unit, q in runs)))
        through = [unit[ref] * q for _, unit, q in runs]
        calc = abs(sum(through))
        if calc <= EPS:
            if m > EPS:
                notes.append(f"Flowmåleren '{name}' måler {m:g}, men beregningen finder ingen pumpe med flow gennem den")
            continue
        k = m / calc
        if k > MAX_METER_FACTOR:
            notes.append(f"Flowmåleren '{name}' måler {m:g} — over {MAX_METER_FACTOR:g} gange det beregnede; der skaleres højst så meget")
            k = MAX_METER_FACTOR
        for j, t in enumerate(through):
            if abs(t) > EPS:
                if j in scaled_by and scaled_by[j] != name:
                    notes.append(f"Pumpen '{topo.elements[runs[j][0].el].name or runs[j][0].el}' går gennem flere flowmålere "
                                 f"('{scaled_by[j]}' og '{name}') — den sidste gælder")
                scaled_by[j] = name
        runs = [(p, unit, q * k if abs(t) > EPS else q) for (p, unit, q), t in zip(runs, through)]
    for p, unit, q in runs:
        pumped += 1
        flows[p.el] = flows.get(p.el, 0.0) + q
        for i in range(len(edges)):
            total[i] += unit[i] * q
    if ports_out is not None:
        for i, e in enumerate(edges):
            c = total[i]
            if topo.elements[e.el].kind != "piece" or abs(c) < 1e-6 or not e.ka or not e.kb:
                continue
            pp = ports_out.setdefault(e.el, {})
            pp[e.ka] = pp.get(e.ka, 0.0) + c        # strøm u → v: ind ved u's punkt, ud ved v's
            pp[e.kb] = pp.get(e.kb, 0.0) - c
        for el in list(ports_out):
            ports_out[el] = {k: round(v, 1) for k, v in ports_out[el].items() if abs(v) >= 0.05}
    per_el: dict[str, float] = {}
    for i, e in enumerate(edges):
        c = total[i]
        if abs(c) < 1e-6:
            continue
        if topo.elements[e.el].kind == "pipe":         # rør: den største strøm, med fortegn efter rørets retning
            if abs(c) > abs(per_el.get(e.el, 0.0)):
                per_el[e.el] = c * e.sign
        else:                                           # symboler og rørstykker: mængden igennem
            per_el[e.el] = max(per_el.get(e.el, 0.0), abs(c))
    for el, c in per_el.items():
        if el not in flows:                             # (en pumpes egen værdi er det, den giver)
            flows[el] = c
    stats = {"nodes": n, "edges": len(edges), "pumps": len(pumps), "pumping": pumped}
    return {k: round(v, 1) for k, v in flows.items()}, notes, stats


# ------------------------------------------------------------------ preview (Tegn: flowet live og simulering)

MAX_PREVIEW_ELEMENTS = 2000    # forbundne elementer i én preview (en Pi skal også passe resten)
MAX_PREVIEW_PUMPS = 50


def preview(svg: str, defs: dict[str, dict[str, Any]], configs: dict[str, dict[str, Any]], positions: dict[str, int | None],
            read: Callable[[str], Any], rates: dict[str, float] | None = None,
            sim_positions: dict[str, int] | None = None, restricts: dict[str, float] | None = None) -> dict[str, Any]:
    """Flowet for en tegning, som den ser ud i Tegn lige nu (også ugemt) — med de live værdier, eller simuleret (v6.3.0):
    `rates` = {pumpe: 0–1} (en pumpe-type uden egen opsætning bliver en pumpe med profilens kapacitet), `sim_positions` =
    {ventil: position}, `restricts` = {symbol: restriktion 0,00–1,00}. Skriver aldrig noget og udgiver ingen live-værdier."""
    topo = parse_topology(svg, piece_types(defs))
    if len(topo.elements) > MAX_PREVIEW_ELEMENTS:
        return {"flows": {}, "ports": {}, "notes": [f"Tegningen har over {MAX_PREVIEW_ELEMENTS} forbundne elementer"], "stats": {},
                "pumps": [], "valves": [], "symbols": [], "linked": bool(topo.links)}
    cfgs = {k: dict(v) for k, v in configs.items()}
    for el, r in (rates or {}).items():
        e = topo.elements.get(el)
        if e is None:
            continue
        fl = dict(cfgs.get(el, {}).get("flow") or {})
        if not fl.get("pump"):
            if kind_of(defs, e.type) != "pump":
                continue
            fl = {**fl, "pump": True, "capacity": int((defs.get(e.type) or {}).get("capacity") or fl.get("capacity") or 100)}
        fl["rate"] = {"src": f"@val:{max(0.0, min(1.0, float(r)))}", "max": 1}
        cfgs[el] = {**cfgs.get(el, {}), "flow": fl}
    for el, r in (restricts or {}).items():
        if el in topo.elements and topo.elements[el].kind == "symbol":
            fl = dict(cfgs.get(el, {}).get("flow") or {})
            fl["restrict"] = {"src": f"@val:{max(0.0, min(1.0, float(r)))}", "max": 1}
            cfgs[el] = {**cfgs.get(el, {}), "flow": fl}
    pos = {**positions, **(sim_positions or {})}
    n_pumps = sum(1 for c in cfgs.values() if (c.get("flow") or {}).get("pump"))
    if n_pumps > MAX_PREVIEW_PUMPS:
        return {"flows": {}, "ports": {}, "notes": [f"Tegningen har over {MAX_PREVIEW_PUMPS} pumper — for mange til en preview"],
                "stats": {}, "pumps": [], "valves": [], "symbols": [], "linked": bool(topo.links)}
    ports: dict[str, dict[str, float]] = {}
    flows, notes, stats = compute(topo, defs, cfgs, pos, read, ports)
    pumps = [{"id": e.id, "name": e.name, "configured": bool((configs.get(e.id, {}).get("flow") or {}).get("pump")),
              "capacity": int((cfgs.get(e.id, {}).get("flow") or {}).get("capacity") or (defs.get(e.type) or {}).get("capacity") or 100)}
             for e in topo.elements.values() if e.kind == "symbol" and
             ((cfgs.get(e.id, {}).get("flow") or {}).get("pump") or kind_of(defs, e.type) == "pump")]
    valves = [{"id": el, "name": topo.elements[el].name, "labels": [p.get("label", "") for p in c.get("positions", [])],
               "pos": pos.get(el)}
              for el, c in cfgs.items() if el in topo.elements and c.get("op") == "positions" and (c.get("flow") or {}).get("open") is not None]
    # symbolernes restriktion lige nu (0,00–1,00) — til simuleringens skydere
    read_r = lambda el: _fraction(((cfgs.get(el, {}).get("flow") or {}).get("restrict")), read) if (cfgs.get(el, {}).get("flow"))         else float((defs.get(topo.elements[el].type) or {}).get("restrict", 1.0))  # noqa: E731
    symbols = [{"id": e.id, "name": e.name, "restrict": round(read_r(e.id), 2)} for e in topo.elements.values()
               if e.kind == "symbol" and len(e.keys) >= 2]
    return {"flows": flows, "ports": {k: v for k, v in ports.items() if v}, "notes": notes, "stats": stats,
            "pumps": sorted(pumps, key=lambda p: p["name"] or p["id"]), "valves": sorted(valves, key=lambda v: v["name"] or v["id"]),
            "symbols": sorted(symbols, key=lambda s: s["name"] or s["id"]),
            "linked": bool(topo.links), "levels": flow_levels(configs, read)}


# ------------------------------------------------------------------ motoren (kaldes af symbol-runtimen)

class FlowEngine:
    """Holder topologien pr. tegning og udgiver flowet som live-værdier. Regner kun igen, når et input er ændret."""

    def __init__(self, cache: Any):
        self.cache = cache
        self.topos: dict[str, Topology] = {}
        self.defs: dict[str, dict[str, Any]] = merged(None)
        self._last_inputs: dict[str, Any] = {}
        self._published: dict[str, dict[str, float]] = {}
        self._published_ports: dict[str, dict[str, str]] = {}    # rørstykkernes flow pr. punkt (flowp:…), som tekst
        self._published_levels: dict[str, dict[str, float | None]] = {}   # flow-niveauerne (flowlvl:…, v6.4.0)
        self._quality: dict[str, str] = {}
        self.notes: dict[str, list[str]] = {}
        self.stats: dict[str, Any] = {"runs": 0, "last_ms": 0.0, "errors": 0, "drawings": 0, "unbound": []}

    def reload(self, svgs: dict[str, str], custom_defs: dict[str, dict[str, Any]] | None) -> None:
        self.defs = merged(custom_defs)
        topos: dict[str, Topology] = {}
        unbound: list[str] = []
        for did, svg in svgs.items():
            try:
                t = parse_topology(svg, piece_types(self.defs))
            except Exception:
                log.exception("Flow: tegningen %s kunne ikke læses", did)
                continue
            topos[did] = t
            if not t.links:
                unbound.append(did)
        gone = [d for d in self.topos if d not in topos]
        self.topos = topos
        self._last_inputs.clear()
        self.stats["unbound"] = unbound
        self.stats["drawings"] = len(topos)
        for d in gone:
            self._clear(d)

    def _clear(self, did: str) -> None:
        self._quality.pop(did, None)
        old = self._published.pop(did, {})
        old_p = self._published_ports.pop(did, {})
        old_l = self._published_levels.pop(did, {})
        if old or old_p or old_l:
            self.cache.remove([flow_tag(did, e) for e in old] + [ports_tag(did, e) for e in old_p] + [level_tag(did, e) for e in old_l])

    def evaluate(self, symbols: dict[tuple[str, str], dict[str, Any]], states: dict[tuple[str, str], Any], now: float) -> None:
        """Beregn og udgiv med det samme (tests og kald uden event-løkke)."""
        for did, job in self.jobs(symbols, states):
            self.publish(did, job, self.run_job(did, job), now)

    async def evaluate_async(self, symbols: dict[tuple[str, str], dict[str, Any]], states: dict[tuple[str, str], Any]) -> None:
        """Som evaluate, men selve beregningen kører i en tråd, så serverens event-løkke ikke blokeres (et stort net kan tage
        et sekund på en Raspberry Pi). Input samles og resultatet udgives i løkken."""
        import asyncio
        for did, job in self.jobs(symbols, states):
            res = await asyncio.to_thread(self.run_job, did, job)
            self.publish(did, job, res, time.time())

    def jobs(self, symbols: dict[tuple[str, str], dict[str, Any]], states: dict[tuple[str, str], Any]) -> list[tuple[str, Any]]:
        """Tegninger, hvor et input er ændret siden sidst: [(tegning, (topologi, opsætninger, positioner, værdier))]."""
        read = lambda tag: (lv.value if (lv := self.cache.get(tag)) is not None and lv.quality == "good" else None)  # noqa: E731
        out: list[tuple[str, Any]] = []
        for did, topo in self.topos.items():
            configs = {e: c for (d, e), c in symbols.items() if d == did}
            # (v6.4.0) en flowmåler med baseline giver et flow-niveau, også uden en pumpe på tegningen
            by_type = [e.id for e in topo.elements.values() if e.kind == "symbol" and kind_of(self.defs, e.type) == "pump"
                       and not (configs.get(e.id) or {}).get("flow")
                       and (configs.get(e.id) or {}).get("op") == "positions"]      # pumper efter typen (v6.8.4; med positioner v6.8.7)
            if not by_type and not any((c.get("flow") or {}).get("pump") or ((c.get("flow") or {}).get("measured") or {}).get("src")
                                       for c in configs.values()):
                if self._published.get(did) or self._published_levels.get(did):
                    self._clear(did)
                continue
            positions = {e: getattr(states.get((did, e)), "pos", None) for e in configs}
            fl_inputs = tuple(sorted(
                (e, positions.get(e), tuple(_fraction((c.get("flow") or {}).get(k), read) for k in ("rate", "restrict")),
                 _measured({e: c}, read).get(e))
                for e, c in configs.items() if c.get("flow")))
            sig = (fl_inputs, tuple(sorted((e, repr(c.get("flow"))) for e, c in configs.items() if c.get("flow"))),
                   tuple(sorted((e, positions.get(e), repr(configs.get(e, {}).get("positions"))) for e in by_type)))
            if self._last_inputs.get(did) == sig:
                continue
            self._last_inputs[did] = sig
            values = {src: read(src) for c in configs.values() for k in ("rate", "restrict")
                      if (src := str(((c.get("flow") or {}).get(k) or {}).get("src") or "")) and not src.startswith("@")}
            # flowmålernes tags: en måler uden god værdi gør ikke flowet ukendt — så regnes der uden den
            meters = {src: read(src) for c in configs.values()
                      if (src := str(((c.get("flow") or {}).get("measured") or {}).get("src") or "")) and not src.startswith("@")}
            # et input-tag uden god værdi (PLC offline) eller en ventil i ukendt position: flowet er ukendt, ikke 0
            unknown = any(v is None for v in values.values()) or any(
                positions.get(e) is None for e, c in configs.items() if c.get("op") == "positions" and (c.get("flow") or {}).get("open") is not None)
            out.append((did, (topo, self.defs, configs, positions, {**meters, **values}, sig, "comm_error" if unknown else "good")))
        return out

    def run_job(self, did: str, job: Any) -> tuple[Any, ...] | None:
        topo, defs, configs, positions, values = job[:5]
        t0 = time.perf_counter()
        ports: dict[str, dict[str, float]] = {}
        try:
            res = (*compute(topo, defs, configs, positions, values.get, ports), ports, flow_levels(configs, values.get))
        except Exception:
            self.stats["errors"] += 1
            self._last_inputs.pop(did, None)          # prøv igen ved næste ændring
            log.exception("Flow: beregningen fejlede for tegningen %s", did)
            return None
        self.stats["last_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return res

    def publish(self, did: str, job: Any, res: Any, now: float) -> None:
        """Udgiv resultatet — men kun hvis det stadig er det nyeste: mens en beregning kørte i tråden, kan tegningen være fjernet
        (reload) eller inputtene ændret (et nyere resultat er allerede udgivet, eller en ny beregning er på vej)."""
        if res is None or did not in self.topos or self._last_inputs.get(did) != job[5]:
            return
        quality = job[6]
        flows, notes, st, ports, levels = res
        self.stats["runs"] += 1
        self.stats[f"d:{did}"] = st
        if notes != self.notes.get(did):
            for m in notes:
                log.info("Flow (%s): %s", did, m)
        self.notes[did] = notes
        old = self._published.get(did, {})
        changed_q = self._quality.get(did) != quality
        self._quality[did] = quality
        updates = {flow_tag(did, e): LiveValue(value=v, quality=quality, ts=now) for e, v in flows.items() if changed_q or old.get(e) != v}
        zero = {flow_tag(did, e): LiveValue(value=0.0, quality=quality, ts=now) for e in old
                if e not in flows and (changed_q or old[e] != 0.0)}
        self._published[did] = {**{e: 0.0 for e in old}, **flows}
        # rørstykkernes flow pr. punkt (v6.3.0): tom tekst = intet flow
        old_p = self._published_ports.get(did, {})
        texts = {e: ports_text(p) for e, p in ports.items()}
        updates.update({ports_tag(did, e): LiveValue(value=t, quality=quality, ts=now) for e, t in texts.items()
                        if changed_q or old_p.get(e) != t})
        zero.update({ports_tag(did, e): LiveValue(value="", quality=quality, ts=now) for e in old_p
                     if e not in texts and (changed_q or old_p[e] != "")})
        self._published_ports[did] = {**{e: "" for e in old_p}, **texts}
        # flow-niveauerne (v6.4.0): ukendt måling = komm.fejl (animationen viser delen som tegnet)
        old_l = self._published_levels.get(did, {})
        for e, lv in levels.items():
            if changed_q or e not in old_l or old_l[e] != lv:
                updates[level_tag(did, e)] = LiveValue(value=lv, quality="good" if lv is not None else "comm_error", ts=now)
        gone = [level_tag(did, e) for e in old_l if e not in levels]
        if gone:
            self.cache.remove(gone)
        self._published_levels[did] = dict(levels)
        if updates or zero:
            self.cache.update({**zero, **updates})

    def status(self) -> dict[str, Any]:
        per = {k[2:]: v for k, v in self.stats.items() if k.startswith("d:")}
        return {"runs": self.stats["runs"], "last_ms": self.stats["last_ms"], "errors": self.stats["errors"],
                "drawings": self.stats["drawings"], "unbound": self.stats["unbound"], "per_drawing": per,
                "previews": self.stats.get("previews", 0),
                "notes": {d: n for d, n in self.notes.items() if n},
                "flowing": sum(1 for d in self._published.values() for v in d.values() if v)}
