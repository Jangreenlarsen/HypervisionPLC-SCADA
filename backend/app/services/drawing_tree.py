"""Tegningshierarki (ISA-101: overblik → område → detalje, v6.22.0) — rene regler uden I/O.

En tegning kan have én overordnet tegning (`parent_id`). Rod = niveau 1; højst `MAX_DEPTH` niveauer i alt. Reglerne
håndhæves i backend (samme regler som `frontend/src/lib/drawingTree.ts`) både ved ændring og ved gendannelse af en backup.
Alle gennemløb er sikret mod cirkulære data (ældre/beskadigede rækker må aldrig hænge serveren).
"""

from __future__ import annotations

from typing import Any

MAX_DEPTH = 4


def clean_parent(value: Any) -> str | None:
    """Tom streng, whitespace og None = ingen forælder."""
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def ancestors(parents: dict[str, str | None], drawing_id: str) -> list[str]:
    """Forfædre fra nærmeste forælder og opad (uden tegningen selv). Stopper ved ukendt forælder eller cirkel."""
    out: list[str] = []
    seen = {drawing_id}
    cur = parents.get(drawing_id)
    while cur is not None and cur in parents and cur not in seen:
        out.append(cur)
        seen.add(cur)
        cur = parents.get(cur)
    return out


def descendants(parents: dict[str, str | None], drawing_id: str) -> set[str]:
    """Alle efterkommere (børn, børnebørn …) — uden tegningen selv."""
    kids: dict[str, list[str]] = {}
    for child, parent in parents.items():
        if parent is not None:
            kids.setdefault(parent, []).append(child)
    out: set[str] = set()
    stack = list(kids.get(drawing_id, []))
    while stack:
        cur = stack.pop()
        if cur == drawing_id or cur in out:
            continue
        out.add(cur)
        stack.extend(kids.get(cur, []))
    return out


def height(parents: dict[str, str | None], drawing_id: str) -> int:
    """Antal niveauer i undertræet med tegningen som rod (en tegning uden børn = 1)."""
    kids: dict[str, list[str]] = {}
    for child, parent in parents.items():
        if parent is not None:
            kids.setdefault(parent, []).append(child)
    best, seen = 1, {drawing_id}
    level = [drawing_id]
    while level:
        nxt = []
        for node in level:
            for k in kids.get(node, []):
                if k not in seen:
                    seen.add(k)
                    nxt.append(k)
        if nxt:
            best += 1
        level = nxt
    return best


def check_parent(parents: dict[str, str | None], names: dict[str, str], drawing_id: str, parent_id: str | None,
                 reveal_depth: bool = True) -> str | None:
    """Fejltekst (dansk) hvis `parent_id` ikke må være forælder til `drawing_id`, ellers None.
    `parents`: id → forælder for ALLE tegninger; `names`: id → navn (til fejlteksterne).
    `reveal_depth=False` (begrænset bruger): intet dybdetal i teksten — det ville afsløre skjulte undertegningers dybde."""
    if parent_id is None:
        return None
    me = names.get(drawing_id, drawing_id)
    if parent_id == drawing_id:
        return f"Tegningen '{me}' kan ikke være sin egen overordnede tegning"
    if parent_id not in parents:
        return f"Den overordnede tegning '{parent_id}' findes ikke"
    parent = names.get(parent_id, parent_id)
    if parent_id in descendants(parents, drawing_id):
        return f"'{parent}' ligger under '{me}' — det ville give en cirkel i hierarkiet"
    depth = len(ancestors(parents, parent_id)) + 1          # forælderens niveau (rod = 1)
    total = depth + height(parents, drawing_id)
    if total > MAX_DEPTH and not reveal_depth:
        return (f"Hierarkiet må højst have {MAX_DEPTH} niveauer — '{me}' (med undertegninger) kan ikke ligge under "
                f"'{parent}'")
    if total > MAX_DEPTH:
        return (f"Hierarkiet må højst have {MAX_DEPTH} niveauer — '{me}' (med undertegninger) under '{parent}' "
                f"ville give {total}")
    return None


def sanitize_parents(raw: dict[str, Any], names: dict[str, str]) -> tuple[dict[str, str | None], list[str]]:
    """Gendannelse: id → gyldig forælder. Ukendt forælder, sig selv, cirkel eller for stor dybde ryddes til None
    (aldrig en fejl) — hver forælder prøves mod det allerede godkendte, så resultatet altid er et gyldigt hierarki."""
    accepted: dict[str, str | None] = {did: None for did in raw}
    dropped: list[str] = []
    for did in sorted(raw):
        parent = clean_parent(raw[did])
        if parent is None:
            continue
        problem = check_parent(accepted, names, did, parent)
        if problem is not None:
            # id og forælder stammer fra en uploadet fil: escapet og afkortet, så de ikke kan fylde/forfalske loggen
            dropped.append(f"{did[:80]!r}: forælder {parent[:80]!r} ryddet ({problem[:300]!r:.200})")
            continue
        accepted[did] = parent
    return accepted, dropped
