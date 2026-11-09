"""Signalveje: betingelserne som logikblokke (en OG-kæde pr. gren, en ELLER over grenenes slutblokke). Del af services/signal_paths (v4.15.1)."""

from __future__ import annotations

from typing import Any

from ..symbols import MAX_LOGIC_INPUTS, ON

BLOCK_PREFIX = "Signalvej: "


def _ref(owner: str, element: str, block: str) -> str:
    """Løbelysets kilde: vejens sidste logikblok (`@L3` på ejeren, `@ejer:L3` andre steder) — uden betingelser `@on`."""
    if not block:
        return ON
    return f"@{block}" if element == owner else f"@{owner}:{block}"


def _chunks(conds: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Betingelserne fordelt på blokke: første blok 4, de næste 3 (+ den forrige blok som første indgang)."""
    if not conds:
        return []
    out = [conds[:MAX_LOGIC_INPUTS]]
    rest = conds[MAX_LOGIC_INPUTS:]
    while rest:
        out.append(rest[:MAX_LOGIC_INPUTS - 1])
        rest = rest[MAX_LOGIC_INPUTS - 1:]
    return out


def _free_ids(used: set[str], n: int) -> list[str]:
    out: list[str] = []
    k = 1
    while len(out) < n:
        if f"L{k}" not in used:
            out.append(f"L{k}")
        k += 1
    return out


def plan_chains(conds: list[dict[str, Any]], flowing: list[dict[str, Any]], nb: int
                ) -> tuple[list[list[list[dict[str, Any]]]], list[tuple[int, ...]], int]:
    """Betingelserne fordelt på blokke pr. gren (`chains`), de ELLER-blokke der skal til (`or_sets`: de grene, et stykke går
    igennem), og det samlede antal blokke. Én gren giver præcis de samme blokke som før (v4.13.0)."""
    bconds = [[c for c in conds if br in c["branches"]] for br in range(nb)]
    chains = [_chunks(bc) for bc in bconds]
    or_sets = sorted({tuple(e["branches"]) for e in flowing
                      if len(e["branches"]) > 1 and all(chains[br] for br in e["branches"])})
    return chains, or_sets, sum(len(c) for c in chains) + len(or_sets)


def make_blocks(chains: list[list[list[dict[str, Any]]]], or_sets: list[tuple[int, ...]], nb: int, name: str, ids_new: list[str]
                ) -> tuple[list[dict[str, Any]], list[str], dict[tuple[int, ...], str]]:
    """Selve blokkene (med de id'er, der er afsat), grenenes slutblok (`final`, "" = ingen betingelser) og ELLER-blokkenes id'er."""
    label = f"{BLOCK_PREFIX}{name}"[:40]
    blocks: list[dict[str, Any]] = []
    final: list[str] = []
    k = 0
    for br, chain in enumerate(chains):
        prev = ""
        for i, chunk in enumerate(chain):
            bid = ids_new[k]
            inputs = [{"src": f"@{prev}"}] if prev else []
            inputs += [{"src": c["src"], "neg": bool(c.get("neg")), "cmp": c.get("cmp") or "",
                        "value": c.get("value")} for c in chunk]
            if k == 0:
                nm = label
            elif nb == 1:
                nm = f"{label[:35]} ({i + 1})"
            else:
                nm = f"{label[:33]} (g{br + 1}.{i + 1})"
            blocks.append({"id": bid, "name": nm, "op": "and", "inputs": inputs})
            prev = bid
            k += 1
        final.append(prev)
    or_id: dict[tuple[int, ...], str] = {}
    for n_or, sset in enumerate(or_sets, 1):
        bid = ids_new[k]
        k += 1
        srcs = list(dict.fromkeys(final[br] for br in sset))
        blocks.append({"id": bid, "name": f"{label[:28]} (eller {n_or})", "op": "or", "inputs": [{"src": f"@{x}"} for x in srcs]})
        or_id[sset] = bid
    return blocks, final, or_id


def block_of(br: list[int], final: list[str], or_id: dict[tuple[int, ...], str]) -> str:
    """Slutblokken for et stykke: grenens egen, en ELLER over flere, eller "" (altid) hvis en af dem er uden betingelser."""
    if len(br) == 1:
        return final[br[0]]
    if any(not final[x] for x in br):
        return ""
    return or_id[tuple(br)]
