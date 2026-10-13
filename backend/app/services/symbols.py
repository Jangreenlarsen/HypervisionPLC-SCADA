"""Symbolstandard: én konfiguration pr. symbol (lag 3).

Spec: docs/SYMBOLSTANDARD.md · teknik: docs/SYMBOLSTANDARD_IMPLEMENTERING.md afsnit 3 og 5.1.
Reference for opførsel: docs/prototyper/symbolguide.html (`validate`).

Konfigurationen valideres her — guiden i browseren viser det samme live, men serveren afgør. Fejl samles pr.
trin i guiden (2 Signaler, 3 Kontakter, 4 Visning, 5 Betjening), så frontend kan sætte fejlprikker; advarsler
blokerer ikke.

Delene valideres mod tegningens geometri (ikke en kopi af bibliotekets beskrivelse): Niveau kræver et <rect>,
Værdi et <text>, Løbelys streger eller et rør. Så virker reglerne også for symboler brugeren selv har tegnet.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..storage.db import Database
from .auth import CurrentUser, hash_password
from .bindings import (DEFAULT_OFF, DEFAULT_ON, ColorParams, FlowParams, LevelParams, MoveParams, RangeParams,
                       RotateParams, TextParams, ToggleParams, _color)
from .errors import ServiceError
from .operate import INT_RANGES, to_raw
from .svg_sanitize import describe_element
from .tagsource import TagSourceError, parse_source

log = logging.getLogger(__name__)

MAX_POSITIONS, MAX_PLANES, MAX_SIGNALS, MAX_ANIMS = 8, 8, 8, 12
POS = "@pos"
_SIG_ID = re.compile(r"^[A-Za-z0-9_]{1,10}$")
_PIN = re.compile(r"^\d{4}$")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ skema (afsnit 3.2)

class Position(_M):
    label: str = Field(max_length=20)

    _l = field_validator("label")(lambda cls, v: " ".join((v or "").split()))


class Signal(_M):
    id: str
    tag: str = Field(default="", max_length=64)
    fb: str = Field(default="", max_length=64)
    write: Literal["set", "pulse"] = "set"
    ms: int = 500
    rest: float | None = None

    _s = field_validator("tag", "fb")(lambda cls, v: (v or "").strip())


class Plane(_M):
    signal: str
    values: list[float | None]


class Lock(_M):
    positions: list[bool] = Field(default_factory=list)
    leave: bool = False


# Animationernes parametre: appens bindingsparametre (bindings.py) + det der kun giver mening for symboler —
# værdier pr. position (kilde = symbolets position), "når ≥ X" og blinkfrekvens.
class AColor(ColorParams):
    colors: list[str] | None = None

    @field_validator("colors")
    @classmethod
    def _cols(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else [_color(c) for c in v]


class AToggle(ToggleParams):
    at_least: float | None = None
    set: list[bool] | None = None


class ABlink(AToggle):
    speed: Literal["slow", "normal", "fast"] = "normal"


class AText(TextParams):
    pass


class ARotate(RotateParams):
    angles: list[float] | None = None


class AMove(MoveParams):
    dxs: list[float] | None = None
    dys: list[float] | None = None


class AFlow(FlowParams):
    dirs: list[Literal[-1, 0, 1]] | None = None


ANIM_PARAMS: dict[str, type[BaseModel]] = {
    "fill": AColor, "stroke": AColor, "blink": ABlink, "visible": AToggle, "spin": AToggle,
    "level": LevelParams, "opacity": RangeParams, "text": AText, "rotate": ARotate, "move": AMove, "flow": AFlow,
}
ANIM_LABEL = {"fill": "Farve", "stroke": "Stregfarve", "blink": "Blink", "visible": "Synlig", "spin": "Roterer",
              "level": "Niveau", "opacity": "Gennemsigtighed", "text": "Værdi", "rotate": "Drej", "move": "Flyt",
              "flow": "Løbelys"}
# Parametre pr. position: (feltnavn(e) der skal have én værdi pr. position) — kun når kilden er @pos
POS_FIELDS = {"fill": ("colors",), "stroke": ("colors",), "blink": ("set",), "visible": ("set",), "spin": ("set",),
              "rotate": ("angles",), "move": ("dxs", "dys"), "flow": ("dirs",), "text": ()}
NUMERIC_ONLY = {"level", "opacity"}


class Anim(_M):
    part: str = Field(max_length=120)
    type: Literal["fill", "stroke", "blink", "visible", "spin", "level", "opacity", "text", "rotate", "move", "flow"]
    src: str = Field(default="", max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)
    only: list[bool] | None = None

    _s = field_validator("src", "part")(lambda cls, v: (v or "").strip())


class SymbolConfig(_M):
    type: str = "custom"
    op: Literal["positions", "pulse", "entry", "view"] = "view"
    positions: list[Position] = Field(default_factory=list, max_length=MAX_POSITIONS)
    signals: list[Signal] = Field(default_factory=list, max_length=MAX_SIGNALS)
    planes: list[Plane] = Field(default_factory=list, max_length=MAX_PLANES)
    fault: str = Field(default="", max_length=64)
    display: Literal["remote", "local"] = "remote"
    validate_s: float = 5
    alarm: Literal["", "low", "medium", "high"] = "medium"
    confirm: bool = True
    pulse_ms: int = 500
    lock: Lock = Field(default_factory=Lock)
    anims: list[Anim] = Field(default_factory=list, max_length=MAX_ANIMS)

    _f = field_validator("fault")(lambda cls, v: (v or "").strip())


# ------------------------------------------------------------------ hjælp

def _fmt(v: float) -> str:
    return f"{v:g}"


def _is_set(v: Any) -> bool:
    return v is not None


PSEUDO_KINDS = ("pos", "remote", "state", "locked")


def pseudo_tag(drawing_id: str, element: str, kind: str) -> str:
    """Afledt værdi for et symbol i live-cachen (afsnit 5.2). `:` findes ikke i tag-navne, så navnene kan ikke kollidere."""
    return f"sym:{drawing_id}:{element}:{kind}"


def config_tags(config: dict[str, Any]) -> list[str]:
    """Alle tags en konfiguration læser eller skriver (signaler, tilbagemeldinger, fejl/låst, animationskilder og
    løbelysets retnings-tag). Bruges overalt hvor en tegnings tags samles (regel 12)."""
    out: list[str] = []

    def add(name: Any) -> None:
        if isinstance(name, str) and name and name != POS and name not in out:
            out.append(name)

    for s in config.get("signals", []):
        add(s.get("tag"))
        add(s.get("fb"))
    add(config.get("fault"))
    for a in config.get("anims", []):
        add(a.get("src"))
        if a.get("type") == "flow":
            add((a.get("params") or {}).get("dir_tag"))
    return out


def targets(cfg: dict[str, Any], k: int) -> dict[str, float]:
    """Hvad position k sætter: {signal-id: værdi} fra kontaktplanerne (første plan pr. signal; tomme celler røres ikke)."""
    out: dict[str, float] = {}
    sigs = {s["id"] for s in cfg.get("signals", [])}
    for p in cfg.get("planes", []):
        if p["signal"] in sigs and p["signal"] not in out and k < len(p["values"]) and p["values"][k] is not None:
            out[p["signal"]] = p["values"][k]
    return out


def write_plan(cfg: dict[str, Any], k: int, current: Callable[[str], Any] | None = None) -> list[dict[str, Any]]:
    """Skriveplanen for et skift til position k (prototypens `plannedWrites`):
    - sat-signaler springes over hvis kommando-tagget allerede har værdien (`current(tag)`; None = ukendt → skriv);
    - pulssignaler skrives altid (værdi, så hvileværdi efter `ms`);
    - break-before-make: skrivninger mod 0/Fra først, derefter resten — i planernes rækkefølge.
    → [{"signal", "tag", "value", "pulse": bool, "ms", "rest"}]"""
    sigs = {s["id"]: s for s in cfg.get("signals", [])}
    plan = []
    for sid, value in targets(cfg, k).items():
        s = sigs[sid]
        if not s.get("tag"):
            continue
        pulse = s.get("write") == "pulse"
        if not pulse and current is not None:
            now = current(s["tag"])
            if now is not None and not isinstance(now, str) and math.isclose(float(now), float(value), abs_tol=1e-9):
                continue
        plan.append({"signal": sid, "tag": s["tag"], "value": value, "pulse": pulse,
                     "ms": s.get("ms", 500) if pulse else None, "rest": s.get("rest") if pulse else None})
    return sorted(plan, key=lambda w: 0 if float(w["value"]) == 0 else 1)


def needs_pin(cfg: dict[str, Any], shown: int | None, to: int) -> bool:
    """Nøglelås: låst mål, eller (med "kode for at forlade") en låst vist position der forlades."""
    lock = cfg.get("lock") or {}
    locked = lock.get("positions") or []
    is_locked = lambda j: j is not None and 0 <= j < len(locked) and bool(locked[j])  # noqa: E731
    return is_locked(to) or (bool(lock.get("leave")) and is_locked(shown) and shown != to)


class _TagInfo:
    """Det valideringen behøver om et tag."""

    def __init__(self, row: dict[str, Any]):
        self.row = row
        self.name = row["name"]
        try:
            self.source = parse_source(row["source"])
        except TagSourceError:
            self.source = None
        src = self.source
        self.is_bool = bool(src and (src.kind in ("coil", "di") or src.datatype == "bool"))
        # ST-variabler kendes først fra live-værdien — så kan typen ikke afgøres her
        self.known = bool(src and src.kind not in ("logic", "global"))
        self.writable = bool(row["writable"]) and bool(src and src.kind in ("hr", "coil"))

    def range(self) -> tuple[float, float] | None:
        """Tilladt område i tekniske enheder: tagets min/max hvis sat, ellers datatypens område (skaleret)."""
        lo, hi = self.row.get("min"), self.row.get("max")
        if lo is not None and hi is not None:
            return float(lo), float(hi)
        if not self.source or self.source.datatype not in INT_RANGES:
            return None
        rlo, rhi = INT_RANGES[self.source.datatype]
        scale, off = float(self.row["scale"]), float(self.row["offset"])
        a, b = rlo * scale + off, rhi * scale + off
        lo2, hi2 = (min(a, b), max(a, b))
        return (float(lo) if lo is not None else lo2, float(hi) if hi is not None else hi2)

    def range_text(self) -> str:
        r = self.range()
        return f"{_fmt(r[0])}–{_fmt(r[1])}" if r else "tagets område"

    def exact(self, value: float) -> str | None:
        """None hvis værdien kan skrives præcist til tagget; ellers en dansk forklaring."""
        r = self.range()
        if r and not r[0] <= value <= r[1]:
            return f"{_fmt(value)} er uden for {self.range_text()} for {self.name}"
        if self.source is None:
            return None
        try:
            _, actual = to_raw(value, self.source, float(self.row["scale"]), float(self.row["offset"]))
        except ServiceError as exc:
            return exc.message
        if not math.isclose(float(actual), value, rel_tol=1e-9, abs_tol=1e-9):
            return f"{_fmt(value)} kan ikke skrives præcist til {self.name} (bliver {_fmt(float(actual))})"
        return None


# ------------------------------------------------------------------ validering (prototypens `validate`)

class Result:
    def __init__(self) -> None:
        self.steps: dict[str, list[str]] = {"2": [], "3": [], "4": [], "5": []}
        self.warnings: list[str] = []

    def err(self, step: str, msg: str) -> None:
        self.steps[step].append(msg)

    @property
    def count(self) -> int:
        return sum(len(v) for v in self.steps.values())

    def first(self) -> str:
        for step, msgs in self.steps.items():
            if msgs:
                return f"Trin {step}: {msgs[0]}"
        return ""


def validate_config(raw: Any, element: dict[str, Any], tags: dict[str, dict[str, Any]],
                    has_pin: bool) -> tuple[dict[str, Any], Result]:
    """Valider og normalisér en konfiguration mod symbolets geometri (`describe_element`) og tags.
    → (normaliseret config, Result). Skemafejl (forkerte felter/typer) kaster ServiceError 400 straks."""
    try:
        cfg = SymbolConfig.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'config'}: {e['msg']}" for e in exc.errors())
        raise ServiceError(400, f"Ugyldig symbol-konfiguration — {details}") from None
    res = Result()
    info = {n: _TagInfo(t) for n, t in tags.items()}
    cfg.type = element["type"]
    n = len(cfg.positions)
    P = cfg.op == "positions"

    def tag_of(name: str) -> _TagInfo | None:
        return info.get(name)

    # -- betjeningsform
    if P:
        if not 2 <= n <= MAX_POSITIONS:
            res.err("3", f"Et symbol med positioner skal have 2–{MAX_POSITIONS} positioner.")
    else:
        cfg.positions, cfg.planes = [], []
        cfg.lock = Lock()
        n = 0
    if cfg.op == "view":
        cfg.signals = []
    if cfg.op in ("pulse", "entry"):
        if len(cfg.signals) != 1:
            res.err("2", "Vælg præcis ét signal.")
        s = cfg.signals[0] if cfg.signals else None
        t = tag_of(s.tag) if s and s.tag else None
        if s and not s.tag:
            res.err("2", f"{s.id}: vælg et kommando-tag.")
        elif s and t is None:
            res.err("2", f"{s.id}: tagget '{s.tag}' findes ikke.")
        elif t is not None:
            if not t.writable:
                res.err("2", f"{s.id}: {t.name} er ikke skrivbart.")
            if cfg.op == "pulse" and t.known and not t.is_bool:
                res.err("2", "En trykknap kræver et til/fra-tag.")
            if cfg.op == "entry" and t.known and t.is_bool:
                res.err("2", "Et setpunkt kræver et tal-tag (register).")
        if s:
            s.fb, s.write, s.rest = "", "set", None
        if cfg.op == "pulse" and not 100 <= cfg.pulse_ms <= 10_000:
            res.err("5", "Pulslængde skal være 100–10000 ms.")

    # -- signaler (trin 2)
    ids = [s.id for s in cfg.signals]
    if P:
        if not cfg.signals:
            res.err("2", "Tilføj mindst ét signal.")
        seen_tag: dict[str, str] = {}
        for s in cfg.signals:
            if not _SIG_ID.match(s.id):
                res.err("2", f"Signal-id '{s.id}' må kun bestå af bogstaver, tal og _ (højst 10).")
            if ids.count(s.id) > 1:
                res.err("2", f"To signaler har id'et {s.id}.")
            if not s.tag:
                res.err("2", f"{s.id}: vælg et kommando-tag.")
                continue
            t = tag_of(s.tag)
            if t is None:
                res.err("2", f"{s.id}: tagget '{s.tag}' findes ikke.")
                continue
            if not t.writable:
                res.err("2", f"{s.id}: {t.name} er ikke skrivbart.")
            if t.source is not None and t.source.datatype == "real":
                res.err("2", f"{s.id}: {t.name} er et kommatal (real) — brug et til/fra-tag eller et heltals-register.")
            if s.tag in seen_tag:
                res.err("2", f"{s.id} og {seen_tag[s.tag]} bruger samme tag {s.tag}.")
            else:
                seen_tag[s.tag] = s.id
            if s.fb:
                fb = tag_of(s.fb)
                if fb is None:
                    res.err("2", f"{s.id}: tilbagemeldingen '{s.fb}' findes ikke.")
                elif fb.known and t.known and fb.is_bool != t.is_bool:
                    res.err("2", f"{s.id}: tilbagemeldingen har en anden type end kommandoen.")
            if t.is_bool:
                s.write, s.rest = "set", None   # til/fra-signaler sættes altid
            if not any(p.signal == s.id for p in cfg.planes):
                res.warnings.append(f"{s.id} ({s.tag}) bruges ikke af nogen kontaktplan.")
    if cfg.fault:
        ft = tag_of(cfg.fault)
        if ft is None:
            res.err("2", f"Fejl/låst-tagget '{cfg.fault}' findes ikke.")
        elif ft.known and not ft.is_bool:
            res.err("2", "Fejl/låst-tagget skal være et til/fra-tag.")

    # -- positioner og kontaktplaner (trin 3)
    labels = [p.label for p in cfg.positions]
    if P:
        if any(not lb for lb in labels):
            res.err("3", "Alle positioner skal have et navn.")
        if len(set(labels)) != len(labels):
            res.err("3", "To positioner har samme navn.")
        if not cfg.planes:
            res.err("3", "Opret mindst én kontaktplan.")
        sigs = {s.id: s for s in cfg.signals}
        for i, p in enumerate(cfg.planes):
            nm = f"Plan {i + 1}"
            s = sigs.get(p.signal)
            if s is None:
                res.err("3", f"{nm}: vælg hvilket signal planet styrer.")
                continue
            first = next(k for k, q in enumerate(cfg.planes) if q.signal == p.signal)
            if first != i:
                res.err("3", f"{nm}: {s.id} styres allerede af plan {first + 1} — ét signal pr. plan.")
            if len(p.values) != n:
                res.err("3", f"{nm}: skal have én celle pr. position ({n}).")
                continue
            t = tag_of(s.tag)
            for j, v in enumerate(p.values):
                if not _is_set(v) or t is None:
                    continue
                where = f"{nm}, {labels[j] or j + 1}"
                if t.is_bool:
                    if v not in (0, 1):
                        res.err("3", f"{where}: et til/fra-signal er Til (1), Fra (0) eller røres ikke.")
                elif not float(v).is_integer():
                    res.err("3", f'{where}: "{_fmt(v)}" er ikke et heltal.')
                elif (why := t.exact(float(v))) is not None:
                    res.err("3", f"{where}: {why}.")
            skip = [f'"{labels[j]}"' for j, v in enumerate(p.values) if not _is_set(v) and j < n]
            if skip:
                res.warnings.append(f"{nm} røres ikke i {', '.join(skip)} — {s.id} beholder værdien fra forrige position.")
        readable = [p for p in cfg.planes if p.signal in sigs and sigs[p.signal].write != "pulse" and len(p.values) == n]
        cols = [tuple(p.values[j] for p in readable) for j in range(n)]
        for j, col in enumerate(cols):
            k = cols.index(col)
            if k != j:
                res.err("3", f'"{labels[k]}" og "{labels[j]}" har ens kontaktmønster og kan ikke skelnes.')
        # puls med hvileværdi (trin 5)
        for s in cfg.signals:
            if s.write != "pulse":
                continue
            vals = [v for p in cfg.planes if p.signal == s.id for v in p.values if _is_set(v)]
            if not 100 <= s.ms <= 10_000:
                res.err("5", f"{s.id}: pulslængde skal være 100–10000 ms.")
            if s.rest is None:
                res.err("5", f"{s.id}: hvileværdien skal sættes.")
            elif not float(s.rest).is_integer():
                res.err("5", f"{s.id}: hvileværdien skal være et heltal.")
            elif s.rest in vals:
                res.err("5", f"{s.id}: hvileværdien {_fmt(s.rest)} er også en positions værdi.")
            elif (t := tag_of(s.tag)) is not None and (why := t.exact(float(s.rest))) is not None:
                res.err("5", f"{s.id}: hvileværdien — {why}.")
        if cfg.planes and not readable:
            res.err("5", "Mindst ét plan skal styre et signal der sættes (ikke puls), ellers kan positionen ikke aflæses.")

    # -- visning (trin 4)
    if not 1 <= cfg.validate_s <= 120:
        res.err("4", "Valideringstid skal være 1–120 s.")
    parts = element["parts"]
    for i, a in enumerate(cfg.anims):
        nm = f"Animation {i + 1}"
        target = element if a.part == "all" else parts.get(a.part)
        if target is None:
            res.err("4", f"{nm}: delen '{a.part}' findes ikke i symbolet.")
            continue
        if a.type == "level" and target["tag"] != "rect":
            res.err("4", f"{nm}: Niveau kræver en rektangel-del (<rect>), ikke <{target['tag']}>.")
        if a.type == "text" and target["tag"] not in ("text", "tspan"):
            res.err("4", f"{nm}: Værdi kræver en tekst-del (<text>), ikke <{target['tag']}>.")
        if a.type == "flow" and not target["line"]:
            res.err("4", f"{nm}: Løbelys kræver streger eller et rør i delen.")
        if not a.src:
            res.err("4", f"{nm}: vælg hvad der styrer den.")
            continue
        pos_src = a.src == POS
        if pos_src and not P:
            res.err("4", f"{nm}: symbolet har ingen positioner.")
            continue
        if not pos_src:
            t = tag_of(a.src)
            if t is None:
                res.err("4", f"{nm}: tagget '{a.src}' findes ikke.")
                continue
            if a.type in NUMERIC_ONLY and t.known and t.is_bool:
                res.err("4", f"{nm}: {ANIM_LABEL[a.type]} kræver et tal-tag.")
        elif a.type in NUMERIC_ONLY:
            res.err("4", f"{nm}: {ANIM_LABEL[a.type]} kan ikke styres af positionen — vælg et tal-tag.")
            continue
        try:
            params = ANIM_PARAMS[a.type].model_validate(a.params).model_dump()
        except ValidationError as exc:
            res.err("4", f"{nm}: " + "; ".join(f"{'.'.join(str(p) for p in e['loc']) or a.type}: {e['msg']}"
                                               for e in exc.errors()))
            continue
        fields = POS_FIELDS.get(a.type, ())
        if pos_src:
            for f in fields:
                if params.get(f) is None or len(params[f]) != n:
                    res.err("4", f"{nm}: angiv en værdi pr. position ({f}).")
        else:
            for f in fields:
                params[f] = None   # pr.-position-værdier giver kun mening med kilden "position"
        if a.type == "flow":
            if params["base"].lower() == params["light"].lower():
                res.err("4", f"{nm}: løbelysets to farver skal være forskellige.")
            if params["dir_tag"]:
                if params["dir_tag"] == a.src:
                    res.err("4", f"{nm}: retnings-tagget skal være et andet tag end det der styrer start/stop.")
                elif tag_of(params["dir_tag"]) is None:
                    res.err("4", f"{nm}: retnings-tagget '{params['dir_tag']}' findes ikke.")
        a.params = params
        if a.only is not None:
            if not P:
                a.only = None
            elif len(a.only) != n:
                res.err("4", f"{nm}: 'gælder i positionerne' skal have én afkrydsning pr. position.")
            elif not any(a.only):
                res.warnings.append(f"{nm} gælder ikke i nogen position.")
            elif all(a.only):
                a.only = None    # gælder i alle = ingen begrænsning
    if cfg.op == "view" and not cfg.anims:
        res.err("4", "Et visningssymbol skal have mindst én animation.")

    # -- nøglelås (trin 5)
    if P:
        if len(cfg.lock.positions) != n:
            cfg.lock.positions = (cfg.lock.positions + [False] * n)[:n]
        if any(cfg.lock.positions) and not has_pin:
            res.err("5", "Koden til nøglelåsen skal være præcis 4 cifre.")
        if cfg.lock.positions and all(cfg.lock.positions):
            res.warnings.append("Alle positioner er låst — operatøren skal bruge koden til ethvert skift.")
    return cfg.model_dump(), res


# ------------------------------------------------------------------ service

class SymbolService:
    def __init__(self, db: Database, drawings: Any):
        self.db = db
        self.drawings = drawings
        # Kaldes efter gem/slet (fx så runtime genberegner position og pseudo-tags)
        self.on_change: Callable[[str, str], None] | None = None

    def _element(self, drawing_id: str, element: str) -> dict[str, Any]:
        self.drawings._require(drawing_id)
        info = describe_element(self.drawings.svg(drawing_id), element)
        if info is None:
            raise ServiceError(404, f"Elementet '{element}' findes ikke i den aktive version af tegningen")
        return info

    def _tags(self) -> dict[str, dict[str, Any]]:
        return {t["name"]: t for t in self.db.list_tags()}

    def get(self, drawing_id: str, element: str) -> dict[str, Any]:
        """Konfigurationen for et symbol — aldrig PIN eller hash (CLAUDE.md regel 6), kun om en kode er sat."""
        self.drawings._require(drawing_id)
        row = self.db.get_symbol_config(drawing_id, element)
        info = describe_element(self.drawings.svg(drawing_id), element)
        warnings: list[str] = []
        if row is not None and info is not None:
            _, res = validate_config(row["config"], info, self._tags(),
                                     self.db.get_symbol_pin_hash(drawing_id, element) is not None)
            warnings = res.warnings + [f"Trin {k}: {m}" for k, v in res.steps.items() for m in v]
        return {"element": element, "config": row["config"] if row else None,
                "updated_at": row["updated_at"] if row else None, "updated_by": row["updated_by"] if row else None,
                "has_pin": self.db.get_symbol_pin_hash(drawing_id, element) is not None,
                "orphaned": info is None, "symbol": info, "warnings": warnings}

    def put(self, actor: CurrentUser, drawing_id: str, element: str, config: Any, pin: str | None = None) -> dict[str, Any]:
        info = self._element(drawing_id, element)
        if pin is not None and not _PIN.match(pin):
            raise ServiceError(400, "Koden til nøglelåsen skal være præcis 4 cifre", {"steps": {"5": ["Koden til nøglelåsen skal være præcis 4 cifre."]}})
        has_pin = pin is not None or self.db.get_symbol_pin_hash(drawing_id, element) is not None
        normalized, res = validate_config(config, info, self._tags(), has_pin)
        if res.count:
            raise ServiceError(400, f"Symbolet kan ikke gemmes ({res.count} fejl) — {res.first()}",
                               {"steps": res.steps, "warnings": res.warnings})
        self.db.set_symbol_config(drawing_id, element, normalized, actor.username)
        if pin is not None:
            self.db.set_symbol_pin_hash(drawing_id, element, hash_password(pin), actor.username)
        log.info("Symbol %s#%s gemt af %s (op=%s, %d animationer)", drawing_id, element, actor.username,
                 normalized["op"], len(normalized["anims"]))
        if self.on_change is not None:
            self.on_change(drawing_id, element)
        return {"element": element, "config": normalized, "warnings": res.warnings,
                "has_pin": self.db.get_symbol_pin_hash(drawing_id, element) is not None}

    def delete(self, drawing_id: str, element: str) -> None:
        self.drawings._require(drawing_id)
        if not self.db.delete_symbol_config(drawing_id, element):
            raise ServiceError(404, f"'{element}' har ingen symbol-konfiguration")
        if self.on_change is not None:
            self.on_change(drawing_id, element)

    def configs(self, drawing_id: str) -> dict[str, dict[str, Any]]:
        return {r["element"]: r["config"] for r in self.db.list_symbol_configs(drawing_id)}

    def tags_for_drawing(self, drawing_id: str) -> set[str]:
        """Tags + pseudo-tags som tegningens symboler læser/viser (til adgang pr. tegning)."""
        out: set[str] = set()
        for element, cfg in self.configs(drawing_id).items():
            out.update(config_tags(cfg))
            if cfg.get("op") == "positions":
                out.update(pseudo_tag(drawing_id, element, k) for k in PSEUDO_KINDS)
        return out

    def usage(self, tag: str) -> list[str]:
        """Symboler der bruger tagget — så det ikke kan slettes imens (som bindinger og ugeprogrammer)."""
        return [f"{r['drawing_id']}#{r['element']}" for r in self.db.list_symbol_configs()
                if tag in config_tags(r["config"])]


# Bruges af backup-import (tags valideres der mod backuppens tagliste)
__all__ = ["SymbolService", "SymbolConfig", "validate_config", "config_tags", "POS", "DEFAULT_ON", "DEFAULT_OFF"]
