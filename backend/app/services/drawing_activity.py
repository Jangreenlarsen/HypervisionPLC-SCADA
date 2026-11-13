"""Hvilke tags der ikke mere skal pollas, fordi KUN deaktiverede tegninger bruger dem (v1.6.0).

Et tag stoppes kun, hvis (1) mindst én deaktiveret tegning bruger det, (2) ingen aktiv tegning bruger det, og (3) intet andet har
brug for det: alarmer, trend-optagelse, energi og ugeprogrammer. Alarmer er sikkerhedsfunktioner og slås derfor ALDRIG fra, fordi
en tegning er skjult — har tagget en alarm, bliver det pollet som før."""

from __future__ import annotations

from typing import Any

from .bindings import binding_tags


def suspended_tags(db: Any, drawings: Any, symbols: Any) -> set[str]:
    off = drawings.disabled_ids()
    if not off:
        return set()
    used_off: set[str] = set()
    used_on: set[str] = set()
    for d in db.list_drawings():
        did = d["id"]
        names = {t for b in drawings.effective_bindings(did) for t in binding_tags(b)} | symbols.tags_for_drawing(did)
        (used_off if did in off else used_on).update(names)
    candidates = used_off - used_on
    if not candidates:
        return set()
    keep = {s["tag"] for s in db.list_schedules()}
    for t in db.list_tags():
        has_alarm = t.get("alarm_on") is not None or any(t.get(f"alarm_{k}") is not None for k in ("hh", "h", "l", "ll"))
        if has_alarm or t.get("trend") or t.get("energy"):
            keep.add(t["name"])
    return {n for n in candidates if n not in keep and any(t["name"] == n for t in db.list_tags())}
