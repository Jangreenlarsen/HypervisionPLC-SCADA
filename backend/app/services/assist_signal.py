"""Kandidat-tags til hjælperens forslag (v4.3.0; v6.0.0: kun `pick_tags` er tilbage).

"Forklar med egne ord" til signalvejens betingelser er fjernet i v6.0.0 (en signalvej er kun en definition; tilbagemelding og animationer
sættes op i symbol-guiden, hvor hjælperens forslag til signaler — `assist_setup.py` — bruger `pick_tags`).
"""

from __future__ import annotations

from typing import Any

from .assist_knowledge import tokens
from .assist_tools import clean

MAX_TAGS = 30


def pick_tags(tags: dict[str, dict[str, Any]], own: list[str], text: str, names: list[str]) -> list[str]:
    """Kandidat-tags: symbolernes egne tags først, derefter dem hvis navn/beskrivelse deler ord med beskrivelsen og
    symbolernes navne, til sidst resten. Højst MAX_TAGS (prompten skal være kort på CPU)."""
    tags = {n: t for n, t in tags.items() if clean(n, 60) == n}   # navnet skal kunne stå uændret i prompten og skemaet
    out = [t for t in dict.fromkeys(own) if t in tags]
    words = set(tokens(" ".join([text, *names]))) | {w.lower() for w in text.replace(",", " ").split() if len(w) >= 2}
    scored = []
    for name, t in tags.items():
        if name in out:
            continue
        bag = set(tokens(f"{name.replace('_', ' ')} {t.get('description') or ''}")) | {name.lower()}
        score = len(words & bag)
        if score:
            scored.append((-score, name))
    out += [n for _, n in sorted(scored)]
    # Fyld op med de øvrige (navnene siger ikke altid noget, fx "P2_drift" for "pumpe 5") — modellen vælger selv
    out += [n for n in sorted(tags) if n not in out]
    return out[:MAX_TAGS]
