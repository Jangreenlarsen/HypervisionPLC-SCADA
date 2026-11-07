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
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("scada.assist")

K1 = 1.4
B = 0.75
_WORD = re.compile(r"[a-zæøå0-9]+")
STOP = set("""
og i at er en et den det de der som på til med for af har kan ikke du man eller fra så vil skal om men også hvis når
hvad hvor hvordan hvorfor hvem jeg mig min mit vi os sig sin sit være været blive bliver blev var have havde få får
denne dette disse dem dig din dit han hun her nu kun alle alt meget mere mest noget nogle ingen over under ved efter
før mod uden igennem gennem ind ud op ned the a an of to is in it what how
""".split())
# Endelser der fjernes (længste først), så "alarmerne", "alarmen" og "alarmer" bliver samme ord
SUFFIXES = ("erne", "ene", "ers", "ens", "ets", "er", "en", "et", "es", "e", "s")


def slugify(text: str) -> str:
    """Som `slugify` i frontend/src/lib/manual.ts."""
    s = text.lower().replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "afsnit"


def plain(md: str) -> str:
    """Markdown → læsbar tekst (billeder, links, fremhævning og tabelstreger fjernes)."""
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"[*_`>#|]", "", s)
    s = re.sub(r"-{3,}", "", s)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


def stem(word: str) -> str:
    for suf in SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            return word[: -len(suf)]
    return word


def tokens(text: str) -> list[str]:
    return [stem(w) for w in _WORD.findall(text.lower()) if w not in STOP and len(w) > 1]


@dataclass
class Section:
    chapter: str        # kapitlets titel
    heading: str        # afsnittets overskrift ("" = kapitlets indledning)
    slug: str           # kapitlets slug (filnavn uden nummer)
    anchor: str         # m-<slug> eller ""
    text: str           # ren tekst

    @property
    def source(self) -> str:
        return f"Manual › {self.chapter}" + (f" › {self.heading}" if self.heading else "")

    @property
    def href(self) -> str:
        return f"#manual/{self.slug}" + (f"/{self.anchor}" if self.anchor else "")


def split_chapter(name: str, raw: str) -> list[Section]:
    md = raw.replace("\r\n", "\n")
    slug = re.sub(r"^\d+-", "", name)
    m = re.search(r"^#\s+(.+)$", md, re.M)
    title = plain(m.group(1)) if m else slug
    parts = re.split(r"^##\s+(.+)$", md, flags=re.M)   # [intro, h1, body1, h2, body2, ...]
    out: list[Section] = []
    intro = plain(re.sub(r"^#\s+.+$", "", parts[0], count=1, flags=re.M))
    if intro:
        out.append(Section(title, "", slug, "", intro))
    seen: Counter[str] = Counter()
    for i in range(1, len(parts) - 1, 2):
        heading = plain(parts[i])
        base = slugify(heading)
        seen[base] += 1
        anchor = f"m-{base}" if seen[base] == 1 else f"m-{base}-{seen[base]}"
        body = plain(parts[i + 1])
        if body:
            out.append(Section(title, heading, slug, anchor, body))
    return out


class ManualIndex:
    """BM25 over manualens afsnit. Bygges første gang der søges (og igen, hvis filerne ændres)."""

    def __init__(self, manual_dir: Path):
        self.dir = manual_dir
        self._lock = threading.Lock()
        self._stamp: tuple[tuple[str, int], ...] | None = None
        self.sections: list[Section] = []
        self._tf: list[Counter[str]] = []
        self._len: list[int] = []
        self._df: Counter[str] = Counter()
        self._avg = 1.0

    def _files(self) -> list[Path]:
        try:
            return sorted(self.dir.glob("*.md"))
        except OSError:
            return []

    def _ensure(self) -> None:
        files = self._files()
        stamp = tuple((f.name, int(f.stat().st_mtime)) for f in files)
        if stamp == self._stamp:
            return
        sections: list[Section] = []
        for f in files:
            try:
                sections += split_chapter(f.stem, f.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                log.warning("Manual-fil kunne ikke læses: %s", f.name)
        tf, lengths, df = [], [], Counter()
        for s in sections:
            # Overskriften tæller dobbelt: den siger hvad afsnittet handler om
            c = Counter(tokens(f"{s.chapter} {s.heading} {s.heading} {s.text}"))
            tf.append(c)
            lengths.append(sum(c.values()))
            df.update(c.keys())
        self.sections, self._tf, self._len, self._df = sections, tf, lengths, df
        self._avg = (sum(lengths) / len(lengths)) if lengths else 1.0
        self._stamp = stamp
        log.info("Manual indekseret: %d afsnit fra %d filer", len(sections), len(files))

    def search(self, query: str, k: int = 2) -> list[tuple[Section, float]]:
        with self._lock:
            self._ensure()
            q = set(tokens(query))
            if not q or not self.sections:
                return []
            n = len(self.sections)
            scored = []
            for i, tf in enumerate(self._tf):
                score = 0.0
                for t in q:
                    f = tf.get(t)
                    if not f:
                        continue
                    idf = math.log(1 + (n - self._df[t] + 0.5) / (self._df[t] + 0.5))
                    score += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * self._len[i] / self._avg))
                if score > 0:
                    scored.append((score, i))
            scored.sort(reverse=True)
            return [(self.sections[i], round(s, 3)) for s, i in scored[:k]]

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
