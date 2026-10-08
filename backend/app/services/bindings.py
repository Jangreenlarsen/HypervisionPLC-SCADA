"""Bindinger mellem SVG-elementer og tags, og validering af animations- og klikparametre.

Animationstyper og klik-handlinger: docs/RESEARCH_OG_DESIGN.md §3.3.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

AnimType = Literal["text", "fill", "stroke", "visible", "blink", "level", "rotate", "opacity",
                   "click:write", "click:toggle", "click:pulse", "click:goto"]
CLICK_TYPES = ("click:write", "click:toggle", "click:pulse", "click:goto")
WRITE_CLICKS = ("click:write", "click:toggle", "click:pulse")
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


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextParams(_P):
    decimals: int | None = Field(default=None, ge=0, le=6)
    true_text: str = Field(default="Til", max_length=40)
    false_text: str = Field(default="Fra", max_length=40)
    show_unit: bool = True


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


class WriteParams(_P):
    title: str = Field(default="", max_length=60)


class ToggleClickParams(_P):
    confirm: bool = True


class PulseParams(_P):
    ms: int = Field(default=500, ge=100, le=10_000)
    confirm: bool = False


class GotoParams(_P):
    drawing: str = Field(min_length=1, max_length=64)


PARAM_MODELS: dict[str, type[_P]] = {
    "text": TextParams, "fill": ColorParams, "stroke": ColorParams, "visible": ToggleParams,
    "blink": ToggleParams, "level": LevelParams, "rotate": RotateParams, "opacity": RangeParams,
    "click:write": WriteParams, "click:toggle": ToggleClickParams, "click:pulse": PulseParams,
    "click:goto": GotoParams,
}


class BindingError(ValueError):
    pass


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


def auto_binding(element_tag: str, tag_meta: dict[str, Any]) -> dict[str, Any] | None:
    """Standard-binding når et elements id/inkscape:label er lig et tag-navn."""
    if element_tag in ("text", "tspan"):
        return {"tag": tag_meta["name"], "anim": "text", "params": TextParams().model_dump()}
    if tag_meta.get("is_bool"):
        return {"tag": tag_meta["name"], "anim": "fill", "params": ColorParams().model_dump()}
    return None
