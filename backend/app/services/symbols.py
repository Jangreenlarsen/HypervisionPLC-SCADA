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

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..storage.db import Database
from .auth import CurrentUser, hash_password
from .bindings import (DEFAULT_OFF, DEFAULT_ON, ColorParams, FlowParams, LevelParams, MoveParams, RangeParams,
                       RotateParams, TextParams, ToggleParams, _color)
from .errors import ServiceError
from .operate import INT_RANGES, to_raw
from .svg_sanitize import describe_element, index_svg, named_symbols
from .tagsource import TagSourceError, parse_source

log = logging.getLogger(__name__)

MAX_POSITIONS, MAX_PLANES, MAX_SIGNALS, MAX_ANIMS = 8, 8, 8, 12
MAX_LOGIC, MAX_LOGIC_INPUTS = 8, 4
POS = "@pos"
ON = "@on"   # kilden "Altid til" (v0.71.0): animationen er altid aktiv, uden et tag
VAL = "@val:"   # kilden "fast værdi" (v1.4.0): `@val:75` — et tal i stedet for et tag; kun for tal-animationer
VAL_TYPES = {"level", "opacity", "scale", "rotate", "move"}   # tal-animationer der kan styres af en fast værdi


def parse_val_ref(src: Any) -> float | None:
    """Tallet i en fast værdi (`@val:75` → 75.0); None hvis det ikke er en fast værdi eller tallet er ugyldigt/uendeligt."""
    if not isinstance(src, str) or not src.startswith(VAL):
        return None
    try:
        v = float(src[len(VAL):])
    except ValueError:
        return None
    return v if v == v and abs(v) != float("inf") else None
ALARM_REF = "@alarm:"   # kilden "alarm på et tag" (v0.74.0): @alarm:active:<tag> eller @alarm:unack:<tag>
ALARM_KINDS = ("active", "unack")


def parse_alarm_ref(src: Any) -> tuple[str, str] | None:
    """`@alarm:active:Pumpe1_Fejl` → ("active", "Pumpe1_Fejl"); None hvis det ikke er en (gyldig) alarmkilde."""
    if not isinstance(src, str) or not src.startswith(ALARM_REF):
        return None
    kind, _, tag = src[len(ALARM_REF):].partition(":")
    return (kind, tag) if kind in ALARM_KINDS and tag else None


def alarm_tag(kind: str, tag: str) -> str:
    """Live-navnet alarmmotoren udgiver (`:` findes ikke i tag-navne)."""
    return f"alarm:{tag}:{kind}"
_SIG_ID = re.compile(r"^[A-Za-z0-9_]{1,10}\Z")
_LOGIC_ID = re.compile(r"^L[0-9]{1,2}\Z")
_PIN = re.compile(r"[0-9]{4}")   # bruges med fullmatch: kun ASCII-cifre, ingen linjeskift


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


class LogicInput(_M):
    """Én indgang til en logikblok: et tag (til/fra, eller et tal sammenlignet med en grænse) eller en tidligere blok (`@L1`)."""
    src: str = Field(default="", max_length=64)
    neg: bool = False                                  # NOT på indgangen
    cmp: Literal["", "ge", "le", "eq"] = ""            # kun for tal-tags: ≥, ≤, =
    value: float | None = None

    _s = field_validator("src")(lambda cls, v: (v or "").strip())


class LogicBlock(_M):
    """AND/OR over 1–4 indgange (+ NOT pr. indgang og på resultatet). Kan bruges som kilde (`@L1`) i animationer og som indgang i senere blokke."""
    id: str
    name: str = Field(default="", max_length=40)
    op: Literal["and", "or"] = "and"
    inputs: list[LogicInput] = Field(default_factory=list, max_length=MAX_LOGIC_INPUTS)
    invert: bool = False

    _n = field_validator("name")(lambda cls, v: " ".join((v or "").split()))


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


FLICKER_PALETTE = ["#ff3b00", "#ff8c1a", "#ffd21a"]   # rød, orange, gul


class AFlicker(AToggle):
    """Blafrer: delen blafrer og skifter tilfældigt mellem farverne i `palette` (1–3; v0.70.0), mens kilden er aktiv
    (som Roterer: til/fra, ≥, pr. position). `color` er fra v0.69.0 (én farve) og bruges, hvis der ikke er en palette."""
    palette: list[str] = Field(default_factory=lambda: list(FLICKER_PALETTE), min_length=1, max_length=3)
    color: str | None = None

    @field_validator("palette")
    @classmethod
    def _pal(cls, v: list[str]) -> list[str]:
        return [_color(c) for c in v]

    @field_validator("color")
    @classmethod
    def _col(cls, v: str | None) -> str | None:
        return None if v is None else _color(v)

    @model_validator(mode="after")
    def _from_color(self) -> "AFlicker":
        # gemt med v0.69.0: én farve og ingen palette → den farve først, derefter standardfarverne
        if "palette" not in self.model_fields_set and self.color:
            self.palette = [self.color, *FLICKER_PALETTE[1:]]
        return self


class AText(TextParams):
    pass


class ARotate(RotateParams):
    angles: list[float] | None = None
    # Hastighed (v0.97.0): sekunder om drejet; 0 = med det samme; None = som før (glidende pr. position, ellers straks)
    glide_s: float | None = Field(default=None, ge=0, le=10)


class AMove(MoveParams):
    dxs: list[float] | None = None
    dys: list[float] | None = None


class AScale(RangeParams):
    """Størrelse (v0.85.0): delen skaleres om sin midte — size_min % ved min, size_max % ved max."""
    size_min: float = Field(default=50, gt=0, le=1000)
    size_max: float = Field(default=150, gt=0, le=1000)


class AFlow(FlowParams):
    dirs: list[Literal[-1, 0, 1]] | None = None


ANIM_PARAMS: dict[str, type[BaseModel]] = {
    "fill": AColor, "stroke": AColor, "blink": ABlink, "visible": AToggle, "spin": AToggle,
    "level": LevelParams, "opacity": RangeParams, "text": AText, "rotate": ARotate, "move": AMove, "flow": AFlow,
    "flicker": AFlicker, "scale": AScale,
}
ANIM_LABEL = {"fill": "Farve", "stroke": "Stregfarve", "blink": "Blink", "visible": "Synlig", "spin": "Roterer",
              "level": "Niveau", "opacity": "Gennemsigtighed", "text": "Værdi", "rotate": "Drej", "move": "Flyt",
              "flow": "Løbelys", "flicker": "Blafrer", "scale": "Størrelse"}
# Animationer der kan være "aktiv/passiv" (til/fra-agtige); de andre følger et tal hele tiden
WHEN_TYPES = {"fill", "stroke", "blink", "visible", "spin", "flicker", "flow"}
# Parametre pr. position: (feltnavn(e) der skal have én værdi pr. position) — kun når kilden er @pos
POS_FIELDS = {"fill": ("colors",), "stroke": ("colors",), "blink": ("set",), "visible": ("set",), "spin": ("set",),
              "rotate": ("angles",), "move": ("dxs", "dys"), "flow": ("dirs",), "text": (), "flicker": ("set",)}
NUMERIC_ONLY = {"level", "opacity", "scale"}


class Anim(_M):
    part: str = Field(max_length=120)
    type: Literal["fill", "stroke", "blink", "visible", "spin", "level", "opacity", "text", "rotate", "move", "flow", "flicker", "scale"]
    # "aktiv/passiv" (v0.72.0): når animationen ikke er aktiv, rører den ikke delen — så kan en anden (eller standarden)
    # på samme del bestemme. Standard: "aktiv/ikke aktiv" (viser sin fra-tilstand).
    when: bool = False
    src: str = Field(default="", max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)
    only: list[bool] | None = None
    # v1.12.0: et tag hvis værdi ER positionsnummeret (0, 1, 2 …) — animationen får én værdi pr. position, som med kilden "position"
    by_value: bool = False
    # v1.13.0: hvilke tag-værdier hører til hvilken position — "fra-værdi" pr. position (stigende). Position j gælder for værdier
    # fra pos_values[j] op til næste positions fra-værdi; under den første: ingen position. None = værdien ER positionsnummeret.
    pos_values: list[float] | None = Field(default=None, max_length=MAX_POSITIONS)

    _s = field_validator("src", "part")(lambda cls, v: (v or "").strip())


CHART_RANGES = (900, 3600, 8 * 3600, 86400, 7 * 86400)
MAX_CHART_TAGS = 4


class Chart(_M):
    """Trendgraf (v0.91.0): historikken for 1-4 tags som kurve eller søjler over en periode."""
    tags: list[str] = Field(default_factory=list, max_length=MAX_CHART_TAGS)
    range_s: int = 3600
    style: Literal["line", "bar"] = "line"
    bars: int = Field(default=24, ge=4, le=60)
    y_min: float | None = None
    y_max: float | None = None
    title: str = Field(default="", max_length=60)
    # forklaringen med tagenes navne og værdier (v0.93.0)
    legend: Literal["top", "bottom", "none"] = "top"
    font_scale: float = Field(default=1.0, ge=0.5, le=3.0)
    bold: bool = True
    values: bool = True
    # middelkurve (v1.21.0): glidende middelværdi over de seneste avg_h timer (0 = ingen), som stiplet linje (both) eller i stedet (avg)
    avg_h: float = Field(default=0, ge=0, le=720)
    avg_mode: Literal["both", "avg"] = "both"

    @field_validator("range_s")
    @classmethod
    def _range(cls, v: int) -> int:
        if v not in CHART_RANGES:
            raise ValueError(f"perioden skal være en af {', '.join(str(r) for r in CHART_RANGES)} sekunder")
        return v

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for t in v:
            t = (t or "").strip()
            if t and t not in out:
                out.append(t)
        return out


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
    click: Literal["dialog", "step"] = "dialog"   # v1.11.0: "step" = tryk venstre/højre side af symbolet for at skifte position
    pulse_ms: int = 500
    lock: Lock = Field(default_factory=Lock)
    anims: list[Anim] = Field(default_factory=list, max_length=MAX_ANIMS)
    logic: list[LogicBlock] = Field(default_factory=list, max_length=MAX_LOGIC)
    chart: Chart | None = None

    _f = field_validator("fault")(lambda cls, v: (v or "").strip())


# ------------------------------------------------------------------ hjælp

def _fmt(v: float) -> str:
    return f"{v:g}"


def _is_set(v: Any) -> bool:
    return v is not None


PSEUDO_KINDS = ("pos", "remote", "state", "locked")


def is_logic_ref(src: Any) -> bool:
    """`@L1` — kilden er en logikblok (`@pos` er positionen, `@on` er "Altid til")."""
    return isinstance(src, str) and src.startswith("@") and src not in (POS, ON) and not src.startswith((ALARM_REF, VAL))


def split_logic_ref(src: str, own: str = "") -> tuple[str, str]:
    """`@L1` → (eget symbol, L1); `@pumpe:L1` → (pumpe, L1) — en blok i et andet symbol på samme tegning."""
    element, _, block = src[1:].rpartition(":")
    return (element or own), block


def cfg_refs(cfg: dict[str, Any]) -> list[str]:
    """Alle henvisninger til logikblokke (`@L1`, `@symbol:L1`) i en konfiguration: blokkenes indgange,
    animationernes kilde og løbelysets retning."""
    refs = [i.get("src", "") for b in cfg.get("logic", []) for i in b.get("inputs", [])]
    for a in cfg.get("anims", []):
        refs.append(a.get("src", ""))
        refs.append(str((a.get("params") or {}).get("dir_tag") or ""))
    return [r for r in refs if is_logic_ref(r)]


def logic_pseudo_tags(drawing_id: str, element: str, cfg: dict[str, Any]) -> dict[str, str]:
    """{blok-id: pseudo-tag i live-cachen} for symbolets logikblokke."""
    return {b["id"]: pseudo_tag(drawing_id, element, f"logic:{b['id']}") for b in cfg.get("logic", [])}


def pseudo_tag(drawing_id: str, element: str, kind: str) -> str:
    """Afledt værdi for et symbol i live-cachen (afsnit 5.2). `:` findes ikke i tag-navne, så navnene kan ikke kollidere."""
    return f"sym:{drawing_id}:{element}:{kind}"


def config_tags(config: dict[str, Any]) -> list[str]:
    """Alle tags en konfiguration læser eller skriver (signaler, tilbagemeldinger, fejl/låst, animationskilder og
    løbelysets retnings-tag). Bruges overalt hvor en tegnings tags samles (regel 12)."""
    out: list[str] = []

    def add(name: Any) -> None:
        if isinstance(name, str) and name and not name.startswith("@") and name not in out:
            out.append(name)

    for s in config.get("signals", []):
        add(s.get("tag"))
        add(s.get("fb"))
    add(config.get("fault"))
    for b in config.get("logic", []):
        for i in b.get("inputs", []):
            add(i.get("src"))
    for t in (config.get("chart") or {}).get("tags", []):   # trendgrafens tags (adgang, sletning, Trends)
        add(t)
    for a in config.get("anims", []):
        if (alarm := parse_alarm_ref(a.get("src"))) is not None:
            add(alarm[1])
        add(a.get("src"))
        if a.get("type") == "flow":
            add((a.get("params") or {}).get("dir_tag"))
    return out


def _input_value(lv: Any, inp: dict[str, Any]) -> bool | None:
    """Indgangens sandhedsværdi; None = ukendt (komm.fejl, manglende værdi eller forkert type)."""
    if lv is None or lv.quality != "good" or lv.value is None:
        return None
    v = lv.value
    if isinstance(v, bool):
        return v
    if not isinstance(v, (int, float)):
        return None
    cmp, limit = inp.get("cmp") or "", inp.get("value")
    if not cmp or limit is None:
        return v != 0
    if cmp == "ge":
        return v >= limit
    if cmp == "le":
        return v <= limit
    return abs(v - limit) <= 1e-9 * max(1.0, abs(limit))


def logic_results(configs: dict[str, dict[str, Any]], value_of: Callable[[str], Any]) -> dict[tuple[str, str], bool | None]:
    """Beregn alle logikblokke på én tegning: {(symbol, blok-id): Til/Fra/ukendt}. `configs` = symbol → konfiguration.
    Tre-værdi-logik: en afgørende indgang vinder (AND med en Fra = Fra, OR med en Til = Til) selv om en anden er
    ukendt; ellers er resultatet ukendt. En blok kan bruge blokke i andre symboler (`@symbol:L1`); en løkke
    (afvises ved gem) giver ukendt i stedet for uendelig rekursion."""
    memo: dict[tuple[str, str], bool | None] = {}
    visiting: set[tuple[str, str]] = set()

    def block(element: str, bid: str) -> bool | None:
        key = (element, bid)
        if key in memo:
            return memo[key]
        b = next((x for x in (configs.get(element) or {}).get("logic", []) if x.get("id") == bid), None)
        if b is None or key in visiting:
            return None
        visiting.add(key)
        vals: list[bool | None] = []
        for inp in b.get("inputs", []):
            src = inp.get("src") or ""
            if src.startswith("@"):
                v = block(*split_logic_ref(src, element))
            else:
                v = _input_value(value_of(src), inp)
            vals.append(None if v is None else (not v if inp.get("neg") else v))
        if not vals:
            r = None
        elif b.get("op") == "or":
            r = True if any(v is True for v in vals) else False if all(v is False for v in vals) else None
        else:
            r = False if any(v is False for v in vals) else True if all(v is True for v in vals) else None
        visiting.discard(key)
        memo[key] = (not r) if (r is not None and b.get("invert")) else r
        return memo[key]

    for element, cfg in configs.items():
        for b in cfg.get("logic", []):
            block(element, b["id"])
    return memo


def evaluate_logic(blocks: list[dict[str, Any]], value_of: Callable[[str], Any]) -> dict[str, bool | None]:
    """Ét symbols blokke alene (uden henvisninger til andre symboler)."""
    res = logic_results({"": {"logic": blocks}}, value_of)
    return {bid: v for (_, bid), v in res.items()}


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


def config_bindings(drawing_id: str, element: str, cfg: dict[str, Any], parts: set[str]) -> list[dict[str, Any]]:
    """Symbolets animationer som almindelige bindinger, så Overview tegner dem med den eksisterende motor
    (afsnit 7.1). Kilden "position" bliver pseudo-tagget `…:pos` med `params.pos = True`; "gælder i positionerne"
    bliver `params.only` + `params.pos_tag`; "aktiv/passiv" bliver `params.when`. Dele der ikke findes i tegningen,
    springes over. Rækkefølgen bevares: står flere animationer af samme slags på samme del, og er mindst én aktiv/passiv,
    vinder den øverste aktive (canvas.ts); ellers vinder den sidste."""
    pos_tag = pseudo_tag(drawing_id, element, "pos")
    labels = [p["label"] for p in cfg.get("positions", [])]
    out: list[dict[str, Any]] = []
    for i, a in enumerate(cfg.get("anims", [])):
        target = element if a["part"] == "all" else a["part"]
        if target != element and target not in parts:
            continue
        params = {k: v for k, v in (a.get("params") or {}).items() if v is not None}
        if a["src"] == POS or a.get("by_value"):
            params["pos"] = True   # tagets/positionens værdi (0, 1, 2 …) vælger værdien i listen
            if a.get("by_value") and a.get("pos_values"):
                params["pos_values"] = a["pos_values"]   # tagets værdi → position efter fra-værdierne (aldrig midt imellem)
            if a["type"] == "text":
                params["labels"] = labels
        dir_ref = params.get("dir_tag")
        if isinstance(dir_ref, str) and is_logic_ref(dir_ref):   # løbelysets retning styret af en logikblok
            owner, bid = split_logic_ref(dir_ref, element)
            params["dir_tag"] = pseudo_tag(drawing_id, owner, f"logic:{bid}")
        if a.get("only"):
            params["only"] = a["only"]
            params["pos_tag"] = pos_tag
        if a.get("when"):
            params["when"] = True
        if is_logic_ref(a["src"]):
            owner, bid = split_logic_ref(a["src"], element)
            tag = pseudo_tag(drawing_id, owner, f"logic:{bid}")
        elif (alarm := parse_alarm_ref(a["src"])) is not None:
            tag = alarm_tag(*alarm)
        else:
            tag = pos_tag if a["src"] == POS else a["src"]
        out.append({"element": target, "position": 1000 + i, "tag": tag,
                    "anim": a["type"], "params": params, "source": "symbol", "symbol": element})
    return out


def symbol_view(drawing_id: str, element: str, cfg: dict[str, Any], has_pin: bool) -> dict[str, Any]:
    """Det Overview behøver om et konfigureret symbol (afsnit 6) — aldrig koden, kun om den er sat."""
    view = {"op": cfg.get("op"), "labels": [p["label"] for p in cfg.get("positions", [])],
            "display": cfg.get("display"), "confirm": bool(cfg.get("confirm", True)),
            "lock_positions": (cfg.get("lock") or {}).get("positions") or [],
            "lock_leave": bool((cfg.get("lock") or {}).get("leave")), "has_pin": has_pin,
            "fault": cfg.get("fault") or "", "pulse_ms": cfg.get("pulse_ms"),
            "click": cfg.get("click") if cfg.get("op") == "positions" and cfg.get("click") == "step" else "dialog"}
    if cfg.get("op") == "positions":
        view["pseudo"] = {k: pseudo_tag(drawing_id, element, k) for k in PSEUDO_KINDS}
    if cfg.get("op") in ("pulse", "entry") and cfg.get("signals"):
        view["tag"] = cfg["signals"][0].get("tag")
    if cfg.get("chart"):
        view["chart"] = cfg["chart"]
    return view


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
        self.writable = bool(row["writable"]) and bool(src and src.kind in ("hr", "coil", "logic", "global"))

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


def _logic_cycle(element: str, own: list[dict[str, Any]], others: dict[str, dict[str, Any]]) -> str | None:
    """Find en løkke mellem logikblokke på tværs af symboler (A bruger B der bruger A). → 'symbol:blok' eller None."""
    graph: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for el, blocks in {**{e: c.get("logic", []) for e, c in others.items()}, element: own}.items():
        for b in blocks:
            graph[(el, b["id"])] = [split_logic_ref(i["src"], el) for i in b.get("inputs", []) if i.get("src", "").startswith("@")]
    state: dict[tuple[str, str], int] = {}

    def visit(node: tuple[str, str]) -> tuple[str, str] | None:
        if state.get(node) == 2:
            return None
        if state.get(node) == 1:
            return node
        state[node] = 1
        for nxt in graph.get(node, []):
            if nxt in graph and (hit := visit(nxt)) is not None:
                return hit
        state[node] = 2
        return None

    for node in graph:
        if (hit := visit(node)) is not None:
            return f"{hit[0]}:{hit[1]}" if hit[0] != element else hit[1]
    return None


def map_config(cfg: dict[str, Any], source: dict[str, Any], target: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Oversæt en opsætning fra ét symbol til et andet ("kopiér opsætning til flere"). Animationer på "hele symbolet" følger
    med; en animation på en del oversættes til målets del med samme biblioteksnavn (data-hv-pid) — findes den ikke, springes
    animationen over. Nøglelåsen følger ikke med (koden er pr. symbol). → (ny opsætning, noter til brugeren)."""
    import copy
    out = copy.deepcopy(cfg)
    notes: list[str] = []
    by_pid = {p.get("pid"): pid for pid, p in (target.get("parts") or {}).items() if p.get("pid")}
    kept = []
    for i, a in enumerate(out.get("anims", [])):
        part = a.get("part", "all")
        if part == "all":
            kept.append(a)
            continue
        pid = ((source.get("parts") or {}).get(part) or {}).get("pid")
        mapped = by_pid.get(pid) if pid else None
        if mapped is None:
            notes.append(f"Animation {i + 1} ({ANIM_LABEL.get(a.get('type'), a.get('type'))} på '{pid or part}') findes ikke i dette symbol — sprunget over.")
            continue
        kept.append({**a, "part": mapped})
    out["anims"] = kept
    lock = out.get("lock") or {}
    if any(lock.get("positions") or []):
        out["lock"] = {"positions": [False] * len(lock.get("positions") or []), "leave": False}
        notes.append("Nøglelåsen er ikke kopieret — koden er pr. symbol; sæt den i guiden, hvis den skal bruges her.")
    return out, notes


def validate_config(raw: Any, element: dict[str, Any], tags: dict[str, dict[str, Any]],
                    has_pin: bool, element_id: str = "",
                    others: dict[str, dict[str, Any]] | None = None) -> tuple[dict[str, Any], Result]:
    """Valider og normalisér en konfiguration mod symbolets geometri (`describe_element`) og tags.
    → (normaliseret config, Result). Skemafejl (forkerte felter/typer) kaster ServiceError 400 straks."""
    try:
        cfg = SymbolConfig.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'config'}: {e['msg']}" for e in exc.errors())
        raise ServiceError(400, f"Ugyldig symbol-konfiguration — {details}") from None
    res = Result()
    others = others or {}   # de andre symbolers konfigurationer på tegningen (til henvisninger mellem logikblokke)
    other_blocks = {el: {b["id"] for b in c.get("logic", [])} for el, c in others.items()}
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
        cfg.click = "dialog"   # venstre/højre-betjening giver kun mening for positioner
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

    # -- logikblokke (trin 4)
    block_ids: list[str] = []
    for b in cfg.logic:
        nm = f"Logik {b.id}"
        if not _LOGIC_ID.match(b.id):
            res.err("4", f"Blok-id '{b.id}' skal være som L1, L2 …")
        elif b.id in block_ids:
            res.err("4", f"To logikblokke har id'et {b.id}.")
        if not b.inputs:
            res.err("4", f"{nm}: tilføj mindst én indgang.")
        for k, inp in enumerate(b.inputs):
            w = f"{nm}, indgang {k + 1}"
            if not inp.src:
                res.err("4", f"{w}: vælg et tag eller en tidligere blok.")
                continue
            if inp.src.startswith("@"):
                owner, bid = split_logic_ref(inp.src, element_id)
                if not inp.src[1:].count(":"):
                    if bid not in block_ids:
                        res.err("4", f"{w}: '{bid}' er ikke en tidligere blok (en blok kan kun bruge blokke over sig).")
                elif owner == element_id:
                    res.err("4", f"{w}: brug @{bid} til symbolets egne blokke.")
                elif bid not in other_blocks.get(owner, set()):
                    res.err("4", f"{w}: symbolet '{owner}' har ikke blokken '{bid}'.")
                inp.cmp, inp.value = "", None
                continue
            t = tag_of(inp.src)
            if t is None:
                res.err("4", f"{w}: tagget '{inp.src}' findes ikke.")
            elif inp.cmp:
                if inp.value is None:
                    res.err("4", f"{w}: angiv grænseværdien.")
                if t.known and t.is_bool:
                    res.err("4", f"{w}: {t.name} er et til/fra-tag — en sammenligning kræver et tal-tag.")
            else:
                inp.value = None
                if t.known and not t.is_bool:
                    res.err("4", f"{w}: {t.name} er et tal-tag — vælg ≥, ≤ eller = og en grænseværdi.")
        block_ids.append(b.id)
    if cycle := _logic_cycle(element_id, [b.model_dump() for b in cfg.logic], others):
        res.err("4", f"Logikblokkene danner en løkke (via {cycle}) — en blok kan ikke afhænge af sig selv.")
    own_refs = [i.src for b in cfg.logic for i in b.inputs] + [a.src for a in cfg.anims] + \
               [str((a.params or {}).get("dir_tag") or "") for a in cfg.anims]
    used_blocks = {split_logic_ref(s, element_id)[1] for s in own_refs
                   if is_logic_ref(s) and split_logic_ref(s, element_id)[0] == element_id} | \
                  {split_logic_ref(s)[1] for c in others.values() for s in cfg_refs(c)
                   if ":" in s and split_logic_ref(s)[0] == element_id}
    for b in cfg.logic:
        if b.id not in used_blocks:
            res.warnings.append(f"Logik {b.id}{f' ({b.name})' if b.name else ''} bruges ikke af nogen animation eller blok.")

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
        if a.when and a.type not in WHEN_TYPES:
            res.err("4", f"{nm}: {ANIM_LABEL[a.type]} kan ikke være aktiv/passiv — den følger et tal hele tiden.")
        if a.type == "flow" and not target["line"]:
            res.err("4", f"{nm}: Løbelys kræver streger eller et rør i delen.")
        if not a.src:
            res.err("4", f"{nm}: vælg hvad der styrer den.")
            continue
        pos_src = a.src == POS
        on_src = a.src == ON
        val_src = a.src.startswith(VAL)
        if val_src:
            if parse_val_ref(a.src) is None:
                res.err("4", f"{nm}: ugyldig fast værdi '{a.src[len(VAL):]}' — angiv et tal.")
                continue
            if a.type not in VAL_TYPES:
                res.err("4", f"{nm}: {ANIM_LABEL[a.type]} kan ikke styres af en fast værdi — vælg et tag (eller \"Altid til\").")
                continue
        logic_src = is_logic_ref(a.src)
        alarm_src = a.src.startswith(ALARM_REF)
        if alarm_src:
            ref = parse_alarm_ref(a.src)
            if ref is None:
                res.err("4", f"{nm}: ugyldig alarmkilde — vælg 'aktiv' eller 'ukvitteret' og et tag.")
                continue
            if a.type in NUMERIC_ONLY or a.type == "text":
                res.err("4", f"{nm}: {ANIM_LABEL[a.type]} kan ikke styres af en alarm — vælg et tal-tag.")
                continue
            row = tags.get(ref[1])
            if row is None:
                res.err("4", f"{nm}: tagget '{ref[1]}' findes ikke.")
                continue
            if row.get("alarm_on") is None and all(row.get(f"alarm_{k}") is None for k in ("hh", "h", "l", "ll")):
                res.warnings.append(f"Trin 4: {nm}: tagget '{ref[1]}' har ingen alarm endnu — opsæt den i trin 6.")
        if on_src and (a.type in NUMERIC_ONLY or a.type == "text"):
            res.err("4", f"{nm}: {ANIM_LABEL[a.type]} kan ikke styres af \"Altid til\" — vælg et tal-tag.")
            continue
        if pos_src and not P:
            res.err("4", f"{nm}: symbolet har ingen positioner.")
            continue
        if logic_src:
            owner, bid = split_logic_ref(a.src, element_id)
            if (owner == element_id and ":" not in a.src and bid not in block_ids) or \
                    (":" in a.src and (owner == element_id or bid not in other_blocks.get(owner, set()))):
                res.err("4", f"{nm}: logikblokken '{a.src[1:]}' findes ikke.")
                continue
            if a.type in NUMERIC_ONLY:
                res.err("4", f"{nm}: {ANIM_LABEL[a.type]} kan ikke styres af en logikblok — vælg et tal-tag.")
                continue
        elif not pos_src and not on_src and not alarm_src and not val_src:
            t = tag_of(a.src)
            if t is None:
                res.err("4", f"{nm}: tagget '{a.src}' findes ikke.")
                continue
            # Et coil/til-fra-tag kan også styre Niveau/Gennemsigtighed/Størrelse: Fra = 0, Til = 100 (se fraction i animate.ts)
        elif val_src:
            pass   # fast værdi: intet tag at slå op
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
        # "Pr. værdi": kun for et almindeligt tag og animationer med en værdi pr. position (ikke Værdi-teksten)
        by_value = bool(a.by_value) and not pos_src and not a.src.startswith("@") and bool(fields)
        if by_value and not P:
            res.err("4", f"{nm}: \"pr. værdi\" kræver, at symbolet har positioner (vælg Positioner i trin 1).")
            continue
        a.by_value = by_value
        if not by_value:
            a.pos_values = None
        elif a.pos_values is not None:
            pv = a.pos_values
            if len(pv) != n:
                res.err("4", f"{nm}: angiv en fra-værdi pr. position ({n}).")
                continue
            if any(v != v or abs(v) == float("inf") for v in pv) or any(b <= a_ for a_, b in zip(pv, pv[1:])):
                res.err("4", f"{nm}: positionernes fra-værdier skal være tal i stigende rækkefølge (fx 0, 1, 2).")
                continue
        if pos_src or by_value:
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
                dt = params["dir_tag"]
                if dt == a.src:
                    res.err("4", f"{nm}: retnings-tagget skal være et andet tag end det der styrer start/stop.")
                elif is_logic_ref(dt):
                    owner, bid = split_logic_ref(dt, element_id)
                    local = ":" not in dt
                    if (local and bid not in block_ids) or (not local and (owner == element_id or bid not in other_blocks.get(owner, set()))):
                        res.err("4", f"{nm}: retningens logikblok '{dt[1:]}' findes ikke.")
                elif tag_of(dt) is None:
                    res.err("4", f"{nm}: retnings-tagget '{params['dir_tag']}' findes ikke.")
        a.params = params
        if a.only is not None:
            if not P or a.by_value:   # "gælder i" læser symbolets egen position — ryddes ved "pr. værdi" (v1.13.1)
                a.only = None
            elif len(a.only) != n:
                res.err("4", f"{nm}: 'gælder i positionerne' skal have én afkrydsning pr. position.")
            elif not any(a.only):
                res.warnings.append(f"{nm} gælder ikke i nogen position.")
            elif all(a.only):
                a.only = None    # gælder i alle = ingen begrænsning
    # -- trendgraf (v0.91.0)
    if cfg.chart is not None:
        if not cfg.chart.tags:
            res.err("4", "Graf: vælg mindst ét tag.")
        for t in cfg.chart.tags:
            ti = tag_of(t)
            if ti is None:
                res.err("4", f"Graf: tagget '{t}' findes ikke.")
            elif not ti.row.get("trend"):
                res.warnings.append(f"Graf: tagget '{t}' gemmer ikke historik — slå det til i trin 6, ellers er grafen tom.")
        if cfg.chart.y_min is not None and cfg.chart.y_max is not None and not cfg.chart.y_min < cfg.chart.y_max:
            res.err("4", "Graf: Y-aksens min skal være mindre end max.")
    if cfg.op == "view" and not cfg.anims and not cfg.logic and cfg.chart is None:
        res.err("4", "Et visningssymbol skal have mindst én animation (eller en logikblok til andre symboler).")

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
                                     self.db.get_symbol_pin_hash(drawing_id, element) is not None, element,
                                     {k: v for k, v in self.configs(drawing_id).items() if k != element})
            warnings = res.warnings + [f"Trin {k}: {m}" for k, v in res.steps.items() for m in v]
        return {"element": element, "config": row["config"] if row else None,
                "updated_at": row["updated_at"] if row else None, "updated_by": row["updated_by"] if row else None,
                "has_pin": self.db.get_symbol_pin_hash(drawing_id, element) is not None,
                "orphaned": info is None, "symbol": info, "warnings": warnings,
                "logic_pool": self.logic_pool(drawing_id, element)}

    def put(self, actor: CurrentUser, drawing_id: str, element: str, config: Any, pin: str | None = None) -> dict[str, Any]:
        info = self._element(drawing_id, element)
        if pin is not None and not _PIN.fullmatch(pin):
            raise ServiceError(400, "Koden til nøglelåsen skal være præcis 4 cifre", {"steps": {"5": ["Koden til nøglelåsen skal være præcis 4 cifre."]}})
        has_pin = pin is not None or self.db.get_symbol_pin_hash(drawing_id, element) is not None
        others = {k: v for k, v in self.configs(drawing_id).items() if k != element}
        normalized, res = validate_config(config, info, self._tags(), has_pin, element, others)
        if not res.count:
            gone = {b["id"] for b in (self.db.get_symbol_config(drawing_id, element) or {}).get("config", {}).get("logic", [])} \
                - {b["id"] for b in normalized.get("logic", [])}
            for user, bid in self._logic_users(drawing_id, element, gone):
                res.err("4", f"Blokken {bid} bruges af symbolet '{user}' — fjern dens henvisning dér først.")
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

    def used_ids(self, drawing_id: str) -> list[str]:
        """Element-id'er der har en symbolopsætning eller en binding på tegningen — også dem, der ikke findes i den aktive
        version. Tegn må ikke give nye elementer disse id'er, ellers "vågner" en gammel opsætning op på det nye element."""
        self.drawings._require(drawing_id)
        ids = set(self.configs(drawing_id)) | {b["element"] for b in self.db.list_bindings(drawing_id)}
        ids |= {m for g in self.db.list_symbol_groups(drawing_id) for m in g["members"]}   # gruppemedlemmer (v0.131.1)
        return sorted(ids)

    def list_symbols(self, drawing_id: str) -> list[dict[str, Any]]:
        """Symbolerne i tegningens aktive version, med om de har en opsætning — til "kopiér opsætning til flere"."""
        self.drawings._require(drawing_id)
        configured = set(self.configs(drawing_id))
        return [{"element": s["id"], "name": s["name"], "type": s["type"], "configured": s["id"] in configured}
                for s in named_symbols(self.drawings.svg(drawing_id))]

    def list_symbols_ids(self, drawing_id: str) -> list[dict[str, str]]:
        """Alle elementer med id i tegningens aktive version (til at afgøre, om et gruppemedlem er forsvundet)."""
        return [{"id": e} for e in index_svg(self.drawings.svg(drawing_id))]

    def copy_to(self, actor: CurrentUser, drawing_id: str, source: str, targets: list[str], overwrite: bool) -> dict[str, Any]:
        """Kopiér et symbols GEMTE opsætning til andre symboler på tegningen. Hver kopi oversættes (dele efter navn) og
        valideres som et almindeligt gem; et mål der fejler, påvirker ikke de andre. Symboler der allerede har en opsætning,
        springes over, medmindre `overwrite`. → {"results": [{element, status: ok|skipped|error, message, notes}], …}"""
        self.drawings._require(drawing_id)
        row = self.db.get_symbol_config(drawing_id, source)
        if row is None:
            raise ServiceError(409, "Symbolet har ingen gemt opsætning — gem den i guiden, før den kopieres")
        svg = self.drawings.svg(drawing_id)
        src_info = describe_element(svg, source)
        if src_info is None:
            raise ServiceError(404, f"Elementet '{source}' findes ikke i den aktive version af tegningen")
        tags = self._tags()
        results: list[dict[str, Any]] = []
        for target in dict.fromkeys(targets):        # unikke, i den valgte rækkefølge
            if target == source:
                continue
            res_row: dict[str, Any] = {"element": target, "status": "ok", "message": "", "notes": []}
            results.append(res_row)
            info = describe_element(svg, target)
            if info is None:
                res_row.update(status="error", message="Findes ikke i den aktive version af tegningen")
                continue
            existing = self.db.get_symbol_config(drawing_id, target)
            if existing is not None and not overwrite:
                res_row.update(status="skipped", message="Har allerede en opsætning (sæt hak i 'Overskriv' for at erstatte den)")
                continue
            mapped, notes = map_config(row["config"], src_info, info)
            res_row["notes"] = notes
            has_pin = self.db.get_symbol_pin_hash(drawing_id, target) is not None
            others = {k: v for k, v in self.configs(drawing_id).items() if k != target}
            normalized, res = validate_config(mapped, info, tags, has_pin, target, others)
            if not res.count and existing is not None:
                gone = {b["id"] for b in existing["config"].get("logic", [])} - {b["id"] for b in normalized.get("logic", [])}
                for user, bid in self._logic_users(drawing_id, target, gone):
                    res.err("4", f"Blokken {bid} bruges af symbolet '{user}' — kan ikke overskrives.")
            if res.count:
                res_row.update(status="error", message=res.first())
                continue
            self.db.set_symbol_config(drawing_id, target, normalized, actor.username)
            if self.on_change is not None:
                self.on_change(drawing_id, target)
        counts = {k: sum(1 for r in results if r["status"] == k) for k in ("ok", "skipped", "error")}
        log.info("Opsætning for %s#%s kopieret af %s: %s", drawing_id, source, actor.username, counts)
        return {"source": source, "results": results, **counts}

    def set_pin(self, actor: CurrentUser, drawing_id: str, element: str, pin: str) -> dict[str, Any]:
        """Sæt/skift koden til nøglelåsen (skriv-kun): gemmes kun som hash, returnerer kun at den er sat (regel 6)."""
        self._element(drawing_id, element)
        if self.db.get_symbol_config(drawing_id, element) is None:
            raise ServiceError(404, f"'{element}' har ingen symbol-konfiguration — opsæt symbolet før koden sættes")
        if not _PIN.fullmatch(pin or ""):
            raise ServiceError(400, "Koden til nøglelåsen skal være præcis 4 cifre")
        self.db.set_symbol_pin_hash(drawing_id, element, hash_password(pin), actor.username)
        log.info("Kode til symbol %s#%s sat af %s", drawing_id, element, actor.username)
        if self.on_change is not None:
            self.on_change(drawing_id, element)
        return {"element": element, "has_pin": True}

    def clear_pin(self, actor: CurrentUser, drawing_id: str, element: str) -> dict[str, Any]:
        """Fjern koden. Låste positioner kan derefter ikke vælges før en ny kode er sat (sikker standard)."""
        self.drawings._require(drawing_id)
        if not self.db.delete_symbol_pin(drawing_id, element):
            raise ServiceError(404, f"'{element}' har ingen kode")
        log.info("Kode til symbol %s#%s fjernet af %s", drawing_id, element, actor.username)
        if self.on_change is not None:
            self.on_change(drawing_id, element)
        return {"element": element, "has_pin": False}

    def _logic_users(self, drawing_id: str, element: str, block_ids: set[str]) -> list[tuple[str, str]]:
        """(symbol, blok) for andre symboler på tegningen der bruger en af blokkene i `element`."""
        out: list[tuple[str, str]] = []
        if not block_ids:
            return out
        for other, cfg in self.configs(drawing_id).items():
            if other == element:
                continue
            srcs = cfg_refs(cfg)
            for s in srcs:
                if ":" in s:
                    owner, bid = split_logic_ref(s)
                    if owner == element and bid in block_ids and (other, bid) not in out:
                        out.append((other, bid))
        # gruppe-animationer på andre symboler der henviser til blokkene (v0.131.1)
        for row in self.db.list_group_anims(drawing_id):
            if row["element"] == element:
                continue
            for s in cfg_refs({"anims": row["anims"]}):
                if ":" in s:
                    owner, bid = split_logic_ref(s)
                    label = f"{row['element']} (gruppen {row['group_name']})"
                    if owner == element and bid in block_ids and (label, bid) not in out:
                        out.append((label, bid))
        return out

    def logic_pool(self, drawing_id: str, element: str) -> list[dict[str, Any]]:
        """Logikblokke i de ANDRE symboler på tegningen — til guidens valg af kilde."""
        svg = self.drawings.svg(drawing_id)
        out: list[dict[str, Any]] = []
        for other, cfg in self.configs(drawing_id).items():
            if other == element or not cfg.get("logic"):
                continue
            info = describe_element(svg, other)
            if info is None:
                continue   # forældreløs
            for b in cfg["logic"]:
                out.append({"element": other, "symbol": info.get("name") or other, "id": b["id"], "name": b.get("name") or ""})
        return out

    def delete(self, drawing_id: str, element: str) -> None:
        self.drawings._require(drawing_id)
        old = self.db.get_symbol_config(drawing_id, element)
        if old is not None:
            users = self._logic_users(drawing_id, element, {b["id"] for b in old["config"].get("logic", [])})
            if users:
                raise ServiceError(409, f"Symbolets logikblok {users[0][1]} bruges af symbolet '{users[0][0]}' — fjern henvisningen dér først")
        if not self.db.delete_symbol_config(drawing_id, element):
            raise ServiceError(404, f"'{element}' har ingen symbol-konfiguration")
        if self.on_change is not None:
            self.on_change(drawing_id, element)

    def delete_many(self, drawing_id: str, elements: list[str]) -> dict[str, list[str]]:
        """Fjern opsætningen på flere symboler på én gang (v1.2.1). Alt eller intet: bruger et symbol, der IKKE fjernes, en
        logikblok i et af dem (eller en gruppe-animation gør), afvises hele fjernelsen. Blokke, som kun de fjernede symboler
        bruger indbyrdes, er ikke et problem. Elementer uden opsætning springes over."""
        self.drawings._require(drawing_id)
        targets = list(dict.fromkeys(e for e in elements if e))
        have = {e: self.db.get_symbol_config(drawing_id, e) for e in targets}
        doomed = {e for e, row in have.items() if row is not None}
        for e in sorted(doomed):
            blocks = {b["id"] for b in have[e]["config"].get("logic", [])}
            if remaining := [u for u in self._logic_users(drawing_id, e, blocks) if u[0] not in doomed]:
                raise ServiceError(409, f"Symbolets logikblok {remaining[0][1]} i '{e}' bruges af '{remaining[0][0]}' — fjern henvisningen dér først (intet er fjernet)")
        for e in sorted(doomed):
            self.db.delete_symbol_config(drawing_id, e)
            if self.on_change is not None:
                self.on_change(drawing_id, e)
        return {"removed": sorted(doomed), "skipped": [e for e in targets if e not in doomed]}

    # ------------------------------------------------------------ forsvundne opsætninger (v0.88.0)

    def orphaned(self, drawing_id: str) -> list[dict[str, Any]]:
        """Opsætninger på elementer, der ikke findes i tegningens aktive version (slettet i Tegn eller fået et nyt id)."""
        self.drawings._require(drawing_id)
        present = index_svg(self.drawings.svg(drawing_id))
        return [{"element": e, "type": cfg.get("type", ""), "op": cfg.get("op", ""),
                 "anims": [{"part": a.get("part"), "type": a.get("type"), "src": a.get("src", "")} for a in cfg.get("anims", [])],
                 "has_pin": self.db.get_symbol_pin_hash(drawing_id, e) is not None}
                for e, cfg in self.configs(drawing_id).items() if e not in present]

    def move(self, actor: CurrentUser, drawing_id: str, source: str, target: str) -> dict[str, Any]:
        """Flyt en forsvundet opsætning til et andet element. Dele følger id-mønstret `<symbol>_<del>` (fx `pumpe_pil` →
        `pumpe_4_pil`); animationer på dele, der ikke findes på målet, droppes (med besked). PIN flyttes med."""
        row = self.db.get_symbol_config(drawing_id, source)
        if row is None:
            raise ServiceError(404, f"'{source}' har ingen symbol-opsætning")
        if source in index_svg(self.drawings.svg(drawing_id)):
            raise ServiceError(409, f"'{source}' findes stadig i tegningen — kun en forsvundet opsætning kan flyttes")
        info = self._element(drawing_id, target)
        if self.db.get_symbol_config(drawing_id, target) is not None:
            raise ServiceError(409, f"'{target}' har allerede en opsætning — fjern den først, eller vælg et andet element")
        users = self._logic_users(drawing_id, source, {b["id"] for b in row["config"].get("logic", [])})
        if users:
            raise ServiceError(409, f"Symbolets logikblok {users[0][1]} bruges af symbolet '{users[0][0]}' — fjern henvisningen dér først")
        cfg = dict(row["config"])
        anims, dropped = [], []
        for a in cfg.get("anims", []):
            part = a.get("part", "all")
            if part != "all":
                new = target + part[len(source):] if part.startswith(source + "_") else None
                if new is None or new not in info["parts"]:
                    dropped.append(part)
                    continue
                a = {**a, "part": new}
            anims.append(a)
        cfg["anims"] = anims
        pin_hash = self.db.get_symbol_pin_hash(drawing_id, source)
        if pin_hash is not None:
            self.db.set_symbol_pin_hash(drawing_id, target, pin_hash, actor.username)
        try:
            result = self.put(actor, drawing_id, target, cfg)
        except Exception:
            if pin_hash is not None:
                self.db.delete_symbol_pin(drawing_id, target)   # målet havde ingen opsætning — ryd op igen
            raise
        self.db.delete_symbol_config(drawing_id, source)
        # gruppernes medlemskab og animationer følger med (v0.131.2); deres dele oversættes som symbolets egne
        moved = self.db.rename_element_in_groups(drawing_id, source, target, valid_parts=set(info["parts"]))
        log.info("Symbolopsætning %s#%s flyttet til %s af %s (%d animationer droppet)", drawing_id, source, target,
                 actor.username, len(dropped))
        if self.on_change is not None:
            self.on_change(drawing_id, source)
        return {**result, "dropped": dropped, "group_dropped": moved["dropped"], "group_discarded": moved["discarded"]}

    def trend_symbols(self, drawing_ids: set[str] | None) -> list[dict[str, Any]]:
        """De opsatte symboler med deres tags, tegning for tegning — til "Vælg symbol" i Trends (v0.80.0).
        Kun symboler i tegningens aktive version (en opsætning på et fjernet element springes over).
        drawing_ids=None: alle tegninger."""
        out: list[dict[str, Any]] = []
        for d in self.db.list_drawings():
            if drawing_ids is not None and d["id"] not in drawing_ids:
                continue
            cfgs = self.configs(d["id"])
            if not cfgs:
                continue
            try:
                names = {s["id"]: s["name"] for s in named_symbols(self.drawings.svg(d["id"]))}
            except ServiceError as e:
                log.warning("Trends: symbolerne i '%s' kunne ikke læses: %s", d["id"], e)
                continue
            for element, cfg in cfgs.items():
                tags = config_tags(cfg)
                if element in names and tags:
                    out.append({"drawing": d["id"], "drawing_name": d["name"], "element": element,
                                "name": names[element] or element, "tags": tags})
        return out

    def configs(self, drawing_id: str) -> dict[str, dict[str, Any]]:
        return {r["element"]: r["config"] for r in self.db.list_symbol_configs(drawing_id)}

    def tags_for_drawing(self, drawing_id: str) -> set[str]:
        """Tags + pseudo-tags som tegningens symboler læser/viser (til adgang pr. tegning)."""
        out: set[str] = set()
        for row in self.db.list_group_anims(drawing_id):   # animationer ejet af grupper (v0.131.0)
            out.update(config_tags({"anims": row["anims"]}))
        for element, cfg in self.configs(drawing_id).items():
            out.update(config_tags(cfg))
            if cfg.get("op") == "positions":
                out.update(pseudo_tag(drawing_id, element, k) for k in PSEUDO_KINDS)
            out.update(logic_pseudo_tags(drawing_id, element, cfg).values())
        return out

    def usage(self, tag: str) -> list[str]:
        """Symboler der bruger tagget — så det ikke kan slettes imens (som bindinger og ugeprogrammer)."""
        used = [f"{r['drawing_id']}#{r['element']}" for r in self.db.list_symbol_configs()
                if tag in config_tags(r["config"])]
        used += [f"{r['drawing_id']}#{r['element']} (gruppen {r['group_name']})" for r in self.db.list_group_anims()
                 if tag in config_tags({"anims": r["anims"]})]
        return used


# Bruges af backup-import (tags valideres der mod backuppens tagliste)
__all__ = ["SymbolService", "SymbolConfig", "validate_config", "config_tags", "POS", "ON", "DEFAULT_ON", "DEFAULT_OFF"]
