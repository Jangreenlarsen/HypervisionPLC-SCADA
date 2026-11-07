"""Hjælperens viden (v4.1.0, PLAN.md fase 1): manualen opdelt i afsnit og søgt med BM25 i ren Python.

Ingen embeddings-model og ingen ny afhængighed. Afsnittene er manualens `##`-afsnit (et kapitel uden `##` er ét afsnit).
Kildeteksten er manualens markdown (`frontend/src/manual/*.md`; installeret: `<app>/frontend/manual`). Ankrene følger
`frontend/src/lib/manual.ts` (`m-<slug>`), så kilden kan åbnes direkte i Manual-siden.
"""

from __future__ import annotations

import logging
import math
import re
import threading
from collections import Counter
from pathlib import Path

from .manual_compiler import Section, compile_manual, plain, slugify  # noqa: F401 — slugify/plain bruges af andre

log = logging.getLogger("scada.assist")

K1 = 1.4
B = 0.75
_WORD = re.compile(r"[a-zæøå0-9]+")
STOP = set("""
og i at er en et den det de der som på til med for af har kan ikke du man eller fra så vil skal om men også hvis når
hvad hvor hvordan hvorfor hvem jeg mig min mit vi os sig sin sit være været blive bliver blev var have havde få får
denne dette disse dem dig din dit han hun her nu kun alle alt meget mere mest noget nogle ingen over under ved efter
før mod uden igennem gennem ind ud op ned the a an of to is in it what how
se ser pr gør gøre
""".split())
# Endelser der fjernes (længste først), så "alarmerne", "alarmen" og "alarmer" bliver samme ord
SUFFIXES = ("erne", "ene", "ers", "ens", "ets", "er", "en", "et", "es", "e", "s")
# Ord i spørgsmål, som manualen siger med et andet ord (v4.6.1: "et symbol bag et andet, som er foran" fandt ikke
# afsnittet om Alt+klik, fordi manualen skriver "bagved" og "forrest"). Begge retninger, efter stem().
SYNONYMS = {
    "bag": ["bagved", "bagerst", "under", "skjult"], "foran": ["forrest", "øverst"], "forrest": ["foran", "øverst"],
    "bagerst": ["bag", "bagved", "nederst"], "skjul": ["skjult", "bag"], "under": ["bagved", "bag"],
}
PREFIX_WEIGHT = 0.5     # ord, der begynder med søgeordet ("bag" → "bagved"), tæller halvt
HEAD_BOOST = 1.5        # et søgeord i afsnittets overskrift tæller ekstra ("Tags", "Brugere", "Kvittér en alarm")
SYN_WEIGHT = 0.6
COMPOUND_WEIGHT = 0.7   # delene af et sammensat ord, manualen ikke har ("energiforbrug")


def _strip(word: str) -> str:
    for suf in SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= (3 if suf == "s" else 4):   # "tags" → "tag"
            return word[: -len(suf)]
    return word


def stem(word: str) -> str:
    """To gange, så bøjningerne lander samme sted: "brugere" → "bruger" → "brug" = "bruger" → "brug"."""
    w = _strip(_strip(word))
    # dobbelt konsonant før endelsen: "sletter" → "slett" → "slet", "opretter" → "opret"
    if len(w) >= 4 and w[-1] == w[-2] and w[-1] not in "aeiouyæøå":
        w = w[:-1]
    return w


_ACCENTS = str.maketrans("éèêáàâíìóòôúùü", "eeeaaaiiooouuu")   # "Kvittér" = "kvitter" (ellers deles ordet ved é)

def tokens(text: str) -> list[str]:
    return [stem(w) for w in _WORD.findall(text.lower().translate(_ACCENTS)) if w not in STOP and len(w) > 1]


def split_chapter(name: str, raw: str) -> list[Section]:
    """Ét kapitel kompileret (som i LLM-manualen)."""
    return compile_manual([(name, raw)])


class ManualIndex:
    """BM25 over LLM-manualen (manual_compiler: den store manual kompileret + tillæg i llm/). Bygges første gang der
    søges, og igen hvis en fil ændres."""

    def __init__(self, manual_dir: Path):
        self.dir = manual_dir
        self._lock = threading.Lock()
        self._stamp: tuple[tuple[str, int], ...] | None = None
        self.sections: list[Section] = []
        self._tf: list[Counter[str]] = []
        self._head: list[set[str]] = []
        self._len: list[int] = []
        self._df: Counter[str] = Counter()
        self._avg = 1.0

    def _files(self) -> list[Path]:
        try:
            return sorted(self.dir.glob("*.md")) + sorted((self.dir / "llm").glob("*.md"))
        except OSError:
            return []

    def _ensure(self) -> None:
        files = self._files()
        stamp = tuple((f"{f.parent.name}/{f.name}", int(f.stat().st_mtime)) for f in files)
        if stamp == self._stamp:
            return
        main: list[tuple[str, str]] = []
        extras: list[tuple[str, str]] = []
        for f in files:
            try:
                (extras if f.parent.name == "llm" else main).append((f.stem, f.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError):
                log.warning("Manual-fil kunne ikke læses: %s", f.name)
        sections = compile_manual(main, extras)
        tf, lengths, df, head = [], [], Counter(), []
        for s in sections:
            # Overskriften tæller dobbelt: den siger hvad afsnittet handler om
            c = Counter(tokens(f"{s.chapter} {s.heading} {s.heading} {s.keys} {s.keys} {s.text}"))
            tf.append(c)
            head.append(set(tokens(f"{s.heading or s.chapter} {s.keys}")))
            lengths.append(sum(c.values()))
            df.update(c.keys())
        self.sections, self._tf, self._len, self._df, self._head = sections, tf, lengths, df, head
        self._avg = (sum(lengths) / len(lengths)) if lengths else 1.0
        self._stamp = stamp
        log.info("LLM-manual kompileret og indekseret: %d stykker (%d tillæg) fra %d filer",
                 len(sections), sum(s.extra for s in sections), len(files))

    def _split_compound(self, t: str) -> list[str]:
        """Et sammensat ord, manualen ikke har, delt i to ord, den har (evt. med binde-s): "energiforbrug" → energi +
        forbrug, "alarmgrænse" → alarm + grænse. Tomt, hvis ordet findes, eller ingen deling passer."""
        if self._df.get(t) or len(t) < 8:
            return []
        for i in range(len(t) - 4, 3, -1):           # længste forled først
            head, tail = t[:i], t[i:]
            if head.endswith("s") and head[:-1] in self._df and len(head) > 4:
                head = head[:-1]
            tail = stem(tail)
            if head in self._df and tail in self._df:
                return [head, tail]
        return []

    def expand(self, query: str) -> dict[str, float]:
        """Søgeordene med vægt: ordet selv (1), synonymer (SYN_WEIGHT) og manualens ord, der begynder med det
        (PREFIX_WEIGHT; kun for ord, manualen næsten ikke bruger, på mindst 3 bogstaver, og højst 6 bogstaver længere)."""
        weights: dict[str, float] = {}
        def put(t: str, w: float) -> None:
            if w > weights.get(t, 0.0):
                weights[t] = w
        for t in tokens(query):
            put(t, 1.0)
            for syn in SYNONYMS.get(t, []):
                put(stem(syn), SYN_WEIGHT)
            for part in self._split_compound(t):   # "energiforbrug" → "energi" + "forbrug" (v4.9.0)
                put(part, COMPOUND_WEIGHT)
        for t, w in list(weights.items()):
            if len(t) >= 3 and self._df.get(t, 0) <= 2:   # kun sjældne/ukendte ord ("bag") — ikke "alarm" (alarmklokken …)
                for term in self._df:
                    if term != t and term.startswith(t) and len(term) <= len(t) + 6:
                        put(term, w * PREFIX_WEIGHT)
        return weights

    def search(self, query: str, k: int = 2) -> list[tuple[Section, float]]:
        with self._lock:
            self._ensure()
            q = self.expand(query)
            if not q or not self.sections:
                return []
            n = len(self.sections)
            scored = []
            for i, tf in enumerate(self._tf):
                score = 0.0
                for t, w in q.items():
                    f = tf.get(t)
                    if not f:
                        continue
                    idf = math.log(1 + (n - self._df[t] + 0.5) / (self._df[t] + 0.5))
                    score += w * idf * f * (K1 + 1) / (f + K1 * (1 - B + B * self._len[i] / self._avg))
                    if t in self._head[i]:
                        score += w * idf * HEAD_BOOST
                if score > 0:
                    scored.append((score, i))
            scored.sort(reverse=True)
            # Højst ét stykke pr. afsnit i den store manual (v4.9.0): ellers fylder tre stykker af samme lange afsnit
            # (eller tabelrækker) alle pladser, og modellen får kun én kilde
            out: list[tuple[Section, float]] = []
            seen: set[str] = set()
            for s, i in scored:
                sec = self.sections[i]
                if sec.href in seen:
                    continue
                seen.add(sec.href)
                out.append((sec, round(s, 3)))
                if len(out) == k:
                    break
            return out

    def count(self) -> int:
        with self._lock:
            self._ensure()
            return len(self.sections)


def excerpt(text: str, query: str, limit: int) -> str:
    """Højst `limit` tegn af afsnittet — fra det første sted, hvor et søgeord står (så det relevante kommer med)."""
    text = text.replace("<", "‹").replace(">", "›")    # manualen kan heller ikke lukke <data>
    if len(text) <= limit:
        return text
    q = set(tokens(query))
    start = 0
    for m in _WORD.finditer(text.lower()):
        if stem(m.group(0)) in q:
            start = max(0, text.rfind("\n", 0, m.start()) + 1)
            break
    cut = text[start:start + limit]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > limit * 0.8 else cut) + " …"
