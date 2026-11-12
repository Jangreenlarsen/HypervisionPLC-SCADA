"""Signalvejens grundanimationer som almindelige symbol-animationer (v5.8.0).

Vejens *Udseende* (løbelys på rørene, farve/blink på ventiler og pumper, en 3-vejsventils porte …) ligger i vejens `data`
(`elements[].flows/anims`). Ved gem skrives de som **almindelige animationer** i vejens symbol-opsætning (`sv~<id>`), mærket
`auto: true` — så symbol-guiden kan ændre dem som i ethvert andet symbol (type, kilde, farve, hastighed, retning, slet).
Gemmes vejen igen, erstattes de `auto`-mærkede på deres plads i rækkefølgen; alt andet (dine egne, og de du har frigjort ved at fjerne
mærket) bevares, i den rækkefølge du har sat dem. Vejens `data["materialized"]` markerer, at det er gjort (opgraderingen rører den ikke igen).
"""

from __future__ import annotations

from typing import Any

from ..symbols import MAX_PATH_ANIMS
from .runtime import path_tag


class TooManyAnims(ValueError):
    """Vejens udseende giver flere animationer, end et symbol kan have."""


def base_anims(drawing_id: str, path_id: int, data: dict[str, Any], parts: set[str]) -> list[dict[str, Any]]:
    """Vejens grundanimationer (rækkefølgen: pr. element, løbelys først). `parts`: de dele, vejens symbol har (et element, der ikke
    findes i tegningen længere, springes over). Kilden er vejens pseudo-tag for de grene, elementet ligger på; alle er aktiv/passiv."""
    style = data.get("style") or {}
    out: list[dict[str, Any]] = []
    for e in data.get("elements", []):
        el = e.get("element")
        if not isinstance(el, str):
            continue
        tag = path_tag(drawing_id, path_id, e.get("branches") or [0])
        items = [("flow", f["part"], {"reverse": bool(f.get("reverse")), "light": style.get("light", "#8fc8ea"),
                                      "speed": style.get("speed", 40), "dash": style.get("dash", 12)}, True)
                 for f in e.get("flows", [])]
        items += [(a["type"], a["part"], dict(a.get("params") or {}), bool(a.get("when", True))) for a in e.get("anims", [])]
        for kind, part, params, when in items:
            target = el if part in ("all", el) else part
            if target not in parts:
                continue
            out.append({"part": target, "type": kind, "when": when, "src": tag, "params": params, "only": None, "auto": True})
    if len(out) > MAX_PATH_ANIMS:
        raise TooManyAnims(f"Vejens udseende giver {len(out)} animationer (højst {MAX_PATH_ANIMS}) — vælg færre animationer eller kortere vej")
    return out


def merge(config: dict[str, Any], base: list[dict[str, Any]]) -> dict[str, Any]:
    """Opsætningen med de nye grundanimationer: de gamle `auto`-animationer erstattes på deres plads (så rækkefølgen mellem vejens og
    dine egne bevares — øverste aktive animation vinder); er der ingen, lægges de nederst (så dine egne ligger over og vinder)."""
    out: list[dict[str, Any]] = []
    placed = False
    for a in config.get("anims", []):
        if a.get("auto"):
            if not placed:
                out.extend(base)
                placed = True
            continue
        out.append(a)
    if not placed:
        out.extend(base)
    return {**config, "anims": out}
