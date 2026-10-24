"""Bindinger mellem SVG-elementer og tags, og validering af animations- og klikparametre.

Animationstyper og klik-handlinger: docs/RESEARCH_OG_DESIGN.md §3.3.
"""

from __future__ import annotations

import re
import json
from typing import Any, Literal

from .expression import ExpressionError, validate_expression
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

AnimType = Literal["text", "fill", "stroke", "visible", "blink", "level", "rotate", "opacity", "move", "flow",
                   "click:write", "click:toggle", "click:pulse", "click:select", "click:goto"]
CLICK_TYPES = ("click:write", "click:toggle", "click:pulse", "click:select", "click:goto")
WRITE_CLICKS = ("click:write", "click:toggle", "click:pulse", "click:select")
ANIM_TYPES: tuple[str, ...] = AnimType.__args__  # type: ignore[attr-defined]

# Farver sættes som SVG-attributter i browseren — kun simple, ufarlige former tillades.
_COLOR = re.compile(r"^(#[0-9a-fA-F]{3,8}|[a-zA-Z]{3,20}|rgba?\(\s*[0-9.,\s%]+\))$")

# ISA-101-inspirerede standardfarver: grå = normal/stop, mørkegrøn = kører, rød kun til alarm.
DEFAULT_ON = "#2e7d32"
DEFAULT_OFF = "#9e9e9e"


def _color(value: str) -> str:
    if not _COLOR.match(value.strip()):
        raise ValueError(f"ugyldig farve '{value}'")
    return value.strip()


def _label(value: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError("navnet må ikke være tomt")
    return v


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextParams(_P):
    decimals: int | None = Field(default=None, ge=0, le=6)
    true_text: str = Field(default="Til", max_length=40)
    false_text: str = Field(default="Fra", max_length=40)
    show_unit: bool = True
    # Fast tekst før/efter værdien, fx "Tank : " … " liter". Mellemrum bevares som skrevet.
    prefix: str = Field(default="", max_length=40)
    suffix: str = Field(default="", max_length=40)
    # Simpel matematik på værdien før visning, fx "x / 10" (128 → 12,8). Se services/expression.py.
    expression: str = Field(default="", max_length=80)

    @field_validator("expression")
    @classmethod
    def _expression(cls, v: str) -> str:
        try:
            return validate_expression(v)
        except ExpressionError as exc:
            raise ValueError(f"beregningen er ugyldig: {exc}") from None


class Threshold(_P):
    value: float
    color: str

    _c = field_validator("color")(lambda cls, v: _color(v))


class ColorParams(_P):
    on: str = DEFAULT_ON
    off: str = DEFAULT_OFF
    thresholds: list[Threshold] = Field(default_factory=list, max_length=10)

    _on = field_validator("on", "off")(lambda cls, v: _color(v))

    @model_validator(mode="after")
    def _sorted(self) -> "ColorParams":
        values = [t.value for t in self.thresholds]
        if values != sorted(values):
            raise ValueError("tærskler skal være sorteret stigende efter værdi")
        return self


class ToggleParams(_P):
    invert: bool = False


class RangeParams(_P):
    min: float = 0
    max: float = 100

    @model_validator(mode="after")
    def _range(self) -> "RangeParams":
        if not self.min < self.max:
            raise ValueError("min skal være mindre end max")
        return self


class LevelParams(RangeParams):
    direction: Literal["up", "down", "left", "right"] = "up"


class RotateParams(RangeParams):
    angle_min: float = 0
    angle_max: float = 360


class MoveParams(RangeParams):
    """Flyt: ved min står elementet hvor det er tegnet; ved max er det forskudt dx/dy (tegningens enheder)."""
    dx: float = Field(default=100, ge=-100_000, le=100_000)
    dy: float = Field(default=0, ge=-100_000, le=100_000)


class FlowParams(_P):
    """Løbelys: stregen får farven `base`, og en stiplet kopi i farven `light` løber langs tegneretningen.

    Tagget styrer start/stop og retning efter `mode`:
    - onoff: kører når tagget er til (eller fra, med `invert`); retningen er fast (`reverse`).
    - signed: > 0 frem, < 0 tilbage, 0 stop (fx en frekvensomformers hastighed).
    - code: 0 stop, 1 frem, 2 tilbage; andre værdier = stop.
    `reverse` vender retningen i alle tilstande, så "frem" kan følge rørets flow uanset tegneretning.

    `dir_tag` (valgfrit): et andet tag der styrer retningen — Fra = frem, Til = tilbage — så start/stop og
    retning kan komme fra to signaler i PLC'en. Ukendt retning = stop.

    T-stykke og kryds: `arm` vælger ét af rørene (som det ses på skærmen) og `arm_flow` om det løber ind i
    eller ud af krydset ved "frem"; de øvrige rør løber den modsatte vej. Tom `arm` = langs tegneretningen.
    """
    mode: Literal["onoff", "signed", "code"] = "onoff"
    reverse: bool = False
    invert: bool = False
    base: str = "#555555"
    light: str = "#8fc8ea"
    speed: float = Field(default=40, ge=5, le=500)   # tegningens enheder pr. sekund
    dash: float = Field(default=12, ge=2, le=200)    # længde af hver lys/mørk streg
    arm: Literal["", "left", "right", "up", "down"] = ""
    arm_flow: Literal["in", "out"] = "in"
    dir_tag: str = Field(default="", max_length=64)

    _d = field_validator("dir_tag")(lambda cls, v: (v or "").strip())

    _c = field_validator("base", "light")(lambda cls, v: _color(v))


class WriteParams(_P):
    title: str = Field(default="", max_length=60)


class ToggleClickParams(_P):
    confirm: bool = True


class PulseParams(_P):
    ms: int = Field(default=500, ge=100, le=10_000)
    confirm: bool = False


class Position(_P):
    value: float
    label: str = Field(min_length=1, max_length=20)

    _l = field_validator("label")(lambda cls, v: _label(v))


class SelectParams(_P):
    """Omskifter: operatøren vælger én af 2-8 positioner; positionens værdi skrives (samme vej som setpunkt)."""
    positions: list[Position] = Field(min_length=2, max_length=8)
    confirm: bool = True
    title: str = Field(default="", max_length=60)

    @model_validator(mode="after")
    def _unique(self) -> "SelectParams":
        values = [p.value for p in self.positions]
        if len(set(values)) != len(values):
            raise ValueError("positionerne skal have forskellige værdier")
        return self


class GotoParams(_P):
    drawing: str = Field(min_length=1, max_length=64)


PARAM_MODELS: dict[str, type[_P]] = {
    "text": TextParams, "fill": ColorParams, "stroke": ColorParams, "visible": ToggleParams,
    "blink": ToggleParams, "level": LevelParams, "rotate": RotateParams, "opacity": RangeParams, "move": MoveParams,
    "flow": FlowParams,
    "click:write": WriteParams, "click:toggle": ToggleClickParams, "click:pulse": PulseParams,
    "click:select": SelectParams,
    "click:goto": GotoParams,
}


class BindingError(ValueError):
    pass


def binding_tags(b: dict[str, Any]) -> list[str]:
    """Alle tags en binding læser: bindingens eget tag og evt. løbelysets retnings-tag. Bruges alle steder
    der samler en tegnings tags (live-data, adgang, sletning, import), så det ekstra tag aldrig glemmes."""
    # "@on" ("Altid til") og "@val:<tal>" (fast værdi) er ikke tags — de læses aldrig fra PLC'en og kræver ingen adgang
    tags = [b["tag"]] if b.get("tag") and b["tag"] != "@on" and not b["tag"].startswith("@val:") else []
    extra = (b.get("params") or {}).get("dir_tag") if b.get("anim") == "flow" else None
    if extra and extra not in tags:
        tags.append(extra)
    return tags


def validate_binding(item: Any) -> dict[str, Any]:
    """Valider én binding og returnér den normaliseret med standardparametre udfyldt."""
    if not isinstance(item, dict):
        raise BindingError("En binding skal være et objekt med tag, anim og params")
    tag, anim, params = item.get("tag"), item.get("anim"), item.get("params") or {}
    if anim == "click:goto":
        tag = ""  # navigation bruger intet tag
    elif not isinstance(tag, str) or not tag.strip():
        raise BindingError("Binding mangler tag")
    if anim not in PARAM_MODELS:
        raise BindingError(f"Ukendt animation '{anim}' (brug {', '.join(ANIM_TYPES)})")
    try:
        normalized = PARAM_MODELS[anim].model_validate(params).model_dump()
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(str(p) for p in e['loc']) or anim}: {e['msg']}" for e in exc.errors())
        raise BindingError(f"Ugyldige parametre for {anim}: {details}") from None
    return {"tag": tag.strip(), "anim": anim, "params": normalized}


def _spec_list(raw: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    items = data if isinstance(data, list) else [data]
    return [i for i in items if isinstance(i, dict)]


def symbol_bindings(spec: dict[str, Any], root_id: str, tag_meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Automatiske bindinger for et betjeningssymbol (data-hv-auto på roden, data-hv-part på dele).
    Alt valideres som almindelige bindinger; ugyldige udelades. Klik-handlinger der skriver, kræver et
    skrivbart tag — ellers udelades de (visningen virker stadig), så en tegning aldrig kan give mere adgang
    end tag-opsætningen."""
    out: list[dict[str, Any]] = []
    entries = [(root_id, item) for item in _spec_list(spec.get("auto", ""))]
    for child_id, raw in spec.get("parts", []):
        entries += [(child_id, item) for item in _spec_list(raw)]
    for element, item in entries:
        anim = item.get("anim")
        if anim == "click:goto" or (anim in WRITE_CLICKS and not tag_meta.get("writable")):
            continue
        try:
            b = validate_binding({"tag": tag_meta["name"], "anim": anim, "params": item.get("params") or {}})
        except BindingError:
            continue
        out.append({"element": element, **b})
    return out


def auto_binding(element_tag: str, tag_meta: dict[str, Any]) -> dict[str, Any] | None:
    """Standard-binding når et elements id/inkscape:label er lig et tag-navn."""
    if element_tag in ("text", "tspan"):
        return {"tag": tag_meta["name"], "anim": "text", "params": TextParams().model_dump()}
    if tag_meta.get("is_bool"):
        return {"tag": tag_meta["name"], "anim": "fill", "params": ColorParams().model_dump()}
    return None
