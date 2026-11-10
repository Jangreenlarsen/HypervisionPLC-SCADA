"""Signalveje i drift (v5.0.0): hvornår er en signalvej aktiv — beregnet af serveren hvert tick.

- En **gren** er aktiv, når alle dens betingelser er opfyldt (OG). Uden betingelser er den altid aktiv.
- Et **element** lyser, når mindst én af de grene, der går gennem det, er aktiv (ELLER).
- Resultatet ligger i live-cachen som pseudo-tagget `path:<tegning>:<vej>:<grene>` (fx `…:0` eller `…:0,1`), og vejens
  animationer er almindelige bindinger på det (services/drawings.py) — så Overview tegner dem uden særlig kode.
- Tre-værdi-logik som logikblokkene: en afgørende indgang vinder (OG med en Fra = Fra, ELLER med en Til = Til), ellers er
  resultatet ukendt (komm.fejl) — så viser vejen sin passive tilstand.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


def path_tag(drawing_id: str, path_id: int, branches: Iterable[int]) -> str:
    """Pseudo-tagget for de dele af vejen, som grenene `branches` går igennem. `:` findes ikke i tag-navne."""
    return f"path:{drawing_id}:{path_id}:{','.join(str(b) for b in sorted(set(branches)))}"


def branch_sets(data: dict[str, Any]) -> list[tuple[int, ...]]:
    """De forskellige kombinationer af grene, vejens elementer bruger (højst 2^4 − 1 = 15)."""
    return sorted({tuple(sorted(set(e.get("branches") or [0]))) for e in data.get("elements", [])})


def path_tags(drawing_id: str, path_id: int, data: dict[str, Any]) -> list[str]:
    return [path_tag(drawing_id, path_id, s) for s in branch_sets(data)]


def _and(vals: list[bool | None]) -> bool | None:
    if any(v is False for v in vals):
        return False
    return True if all(v is True for v in vals) else None


def _or(vals: list[bool | None]) -> bool | None:
    if any(v is True for v in vals):
        return True
    return False if all(v is False for v in vals) else None


def branch_results(data: dict[str, Any], value_of: Callable[[str], Any]) -> list[bool | None]:
    """Hver grens resultat: Til/Fra/ukendt."""
    from ..symbols import _input_value      # (her for at undgå en løkke mellem modulerne)
    nb = len(dict.fromkeys([data.get("end", ""), *(data.get("ends") or [])]))
    out: list[bool | None] = []
    for b in range(nb):
        vals: list[bool | None] = []
        for c in data.get("conditions", []):
            if b not in (c.get("branches") or [0]):
                continue
            v = _input_value(value_of(c["src"]), c)
            vals.append(None if v is None else (not v if c.get("neg") else v))
        out.append(_and(vals) if vals else True)
    return out


def evaluate_path(drawing_id: str, path_id: int, data: dict[str, Any], value_of: Callable[[str], Any]) -> dict[str, bool | None]:
    """{pseudo-tag: Til/Fra/ukendt} for vejens kombinationer af grene."""
    br = branch_results(data, value_of)
    return {path_tag(drawing_id, path_id, s): _or([br[b] for b in s if b < len(br)]) for s in branch_sets(data)}
