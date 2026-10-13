"""Forslag til en symbol-konfiguration ud fra den gamle model (Konvertér) — lag 3.

Teknik: docs/SYMBOLSTANDARD_IMPLEMENTERING.md afsnit 11. Reference: prototypens `convertDef` og
SYMBOLSTANDARD.md afsnit 7:

| I dag              | I den nye model                                                          |
| click:toggle       | 2 positioner (true_text/false_text), ét til/fra-signal, én kontaktplan   |
| click:select       | positionerne og deres værdier, ét register, én kontaktplan               |
| click:pulse        | betjeningsform Trykknap                                                  |
| click:write        | betjeningsform Setpunkt                                                  |
| fill/stroke        | farve pr. position (ellers efter tagget)                                 |
| text               | positionens navn (ellers tagværdien)                                     |
| move/rotate        | Flyt/Drej pr. position (ellers efter tagget)                             |
| visible/blink      | synlig/blink i de positioner hvor betingelsen er opfyldt                 |
| level/opacity/flow | uændret efter tagget                                                     |

Forslaget gemmes ikke — teknikeren ser det i guiden (eller i rapporten ved "Konvertér alle") og gemmer selv.
"""

from __future__ import annotations

from typing import Any

from .bindings import DEFAULT_OFF, DEFAULT_ON
from .svg_sanitize import describe_element

CLICKS = ("click:toggle", "click:select", "click:pulse", "click:write")


def _color_for(value: float, p: dict[str, Any]) -> str:
    """Som frontendens colorFor: tærskler for tal, ellers on/off."""
    th = p.get("thresholds") or []
    if th:
        color = p.get("off") or DEFAULT_OFF
        for t in th:
            if value >= t["value"]:
                color = t["color"]
        return color
    return (p.get("on") or DEFAULT_ON) if value else (p.get("off") or DEFAULT_OFF)


def _frac(v: float, p: dict[str, Any]) -> float:
    lo, hi = float(p.get("min", 0)), float(p.get("max", 100))
    return 0.0 if hi <= lo else min(1.0, max(0.0, (v - lo) / (hi - lo)))


def suggest(drawings: Any, drawing_id: str, element: str) -> dict[str, Any]:
    """→ {"config": forslag, "notes": [forklaringer], "convertible": bool}. Kaster ikke for ukendte animationer —
    de nævnes i notes."""
    svg = drawings.svg(drawing_id)
    info = describe_element(svg, element)
    if info is None:
        return {"config": None, "notes": [f"Elementet '{element}' findes ikke i den aktive version"], "convertible": False}
    legacy = drawings.legacy_bindings(drawing_id, element)
    notes: list[str] = []
    click = next((b for b in legacy if b["anim"] in CLICKS and b["element"] == element), None)
    cfg: dict[str, Any] = {"op": "view", "positions": [], "signals": [], "planes": [], "anims": [], "confirm": True,
                           "display": "remote", "validate_s": 5, "alarm": "medium", "lock": {"positions": [], "leave": False}}
    values: list[float] = []   # positionernes værdier (til animationer pr. position)
    text_spec = next((b["params"] for b in legacy if b["anim"] == "text" and click and b["tag"] == click["tag"]), {})
    if click is not None:
        tag, p = click["tag"], click["params"]
        if click["anim"] == "click:toggle":
            cfg.update(op="positions", confirm=bool(p.get("confirm", True)),
                       positions=[{"label": text_spec.get("false_text") or "Fra"}, {"label": text_spec.get("true_text") or "Til"}],
                       signals=[{"id": "S1", "tag": tag}], planes=[{"signal": "S1", "values": [0, 1]}])
            values = [0, 1]
            notes.append("Til/fra → 2 positioner med ét signal og én kontaktplan.")
        elif click["anim"] == "click:select":
            pos = p.get("positions") or []
            cfg.update(op="positions", confirm=bool(p.get("confirm", True)),
                       positions=[{"label": x["label"]} for x in pos], signals=[{"id": "S1", "tag": tag}],
                       planes=[{"signal": "S1", "values": [x["value"] for x in pos]}])
            values = [float(x["value"]) for x in pos]
            notes.append(f"Omskifter → {len(pos)} positioner, ét register med værdierne "
                         f"{'/'.join(f'{v:g}' for v in values)}.")
        elif click["anim"] == "click:pulse":
            cfg.update(op="pulse", pulse_ms=int(p.get("ms", 500)), confirm=bool(p.get("confirm", False)),
                       signals=[{"id": "S1", "tag": tag}])
            notes.append("Puls → betjeningsform Trykknap.")
        else:
            cfg.update(op="entry", signals=[{"id": "S1", "tag": tag}])
            notes.append("Setpunkt → betjeningsform Setpunkt.")
    pos_mode = cfg["op"] == "positions"
    n = len(cfg["positions"])
    cfg["lock"]["positions"] = [False] * n
    for b in legacy:
        if b["anim"] in CLICKS or b["anim"] == "click:goto":
            if b["anim"] == "click:goto":
                notes.append(f"'Gå til tegning' på {b['element']} bevares ikke af symbolet — sæt den igen under Bindinger.")
            continue
        part = "all" if b["element"] == element else b["element"]
        p, anim = dict(b["params"]), b["anim"]
        own = click is not None and b["tag"] == click["tag"] and pos_mode
        if not own:
            cfg["anims"].append({"part": part, "type": anim, "src": b["tag"], "params": p})
            continue
        if anim in ("fill", "stroke"):
            cfg["anims"].append({"part": part, "type": anim, "src": "@pos", "params": {"colors": [_color_for(v, p) for v in values]}})
        elif anim == "text":
            cfg["anims"].append({"part": part, "type": "text", "src": "@pos", "params": {}})
        elif anim == "move":
            cfg["anims"].append({"part": part, "type": "move", "src": "@pos", "params": {
                "dxs": [round(float(p.get("dx", 100)) * _frac(v, p), 2) for v in values],
                "dys": [round(float(p.get("dy", 0)) * _frac(v, p), 2) for v in values]}})
        elif anim == "rotate":
            a0, a1 = float(p.get("angle_min", 0)), float(p.get("angle_max", 360))
            cfg["anims"].append({"part": part, "type": "rotate", "src": "@pos",
                                 "params": {"angles": [round(a0 + (a1 - a0) * _frac(v, p), 2) for v in values]}})
        elif anim in ("visible", "blink"):
            on = [bool(v) != bool(p.get("invert")) for v in values]
            cfg["anims"].append({"part": part, "type": anim, "src": "@pos", "params": {"set": on}})
        else:
            cfg["anims"].append({"part": part, "type": anim, "src": b["tag"], "params": p})
    if not legacy:
        notes.append("Symbolet har ingen bindinger i dag — vælg betjening og animationer i guiden.")
    elif not cfg["anims"] and cfg["op"] == "view":
        notes.append("Ingen animationer kunne overføres.")
    return {"config": cfg, "notes": notes, "convertible": bool(legacy) and (cfg["op"] != "view" or bool(cfg["anims"])),
            "symbol": {"type": info["type"], "name": info["name"]}}
