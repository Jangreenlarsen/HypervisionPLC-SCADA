"""Hjælperens LLM-manual (v4.9.0): den store manual *kompileret* til små, selvstændige stykker, som søgningen finder.

Brugerne ser kun den store manual (`frontend/src/manual/*.md`). Den skjulte LLM-manual laves af den, hver gang den
læses (ManualIndex bygger igen, når en fil ændres), så den kan aldrig blive forældet:

- hvert `##`- og `###`-afsnit bliver et stykke med stien som overskrift ("Symboler og guiden › De seks trin › Trin 2");
- tabeller foldes ud til sætninger ("Trin: 2. Signaler — Hvad du gør: …"). Store tabeller giver ét stykke pr. række;
- skærmbilleders billedtekst og interne links ("se Manual › Tegn › Lag") er med, så ordene kan søges;
- lange afsnit deles ved linjeskift (højst MAX_WORDS ord), så det, der sendes til modellen, er det relevante.

Hvert stykke henviser (`href`) til afsnittet i den store manual, så hjælperen kan sende brugeren derhen.

**Tillæg** (`manual/llm/*.md`, vises ikke i Manual-siden): korte spørgsmål/svar og ord, folk bruger. Hvert tillæg er
bundet til et afsnit i den store manual med `<!-- kilde: <fil>#<anker> sha:<8 hex> -->`. `check()` (og en test) fejler,
når kildeafsnittet er ændret eller væk, så tillæggene ikke kan løbe ud af trit. Kør
`python -m app.services.manual_compiler --check` (eller `--sync` efter gennemsyn) fra backend/.
"""

from __future__ import annotations

import hashlib
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

MAX_WORDS = 110          # et stykke er højst så langt (deles ved linjeskift)
ROW_CHUNK_WORDS = 12     # en tabelrække med mindst så mange ord bliver sit eget stykke (i tabeller med ≥ 3 rækker)
_KILDE = re.compile(r"<!--\s*kilde:\s*([\w.-]+?)(?:\.md)?#([\w-]+)\s+sha:([0-9a-f]{8})\s*-->")


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


@dataclass
class Section:
    chapter: str        # kapitlets titel
    heading: str        # afsnittets sti under kapitlet ("" = kapitlets indledning), fx "De seks trin › Trin 2"
    slug: str           # kapitlets slug (filnavn uden nummer)
    anchor: str         # m-<slug> (##), m3-<slug> (###) eller ""
    text: str           # ren tekst
    keys: str = ""      # ekstra søgeord med overskriftens vægt (tillæggets spørgsmål)
    extra: bool = field(default=False)   # True = fra et tillæg (manual/llm)

    @property
    def source(self) -> str:
        return f"Manual › {self.chapter}" + (f" › {self.heading}" if self.heading else "")

    @property
    def href(self) -> str:
        return f"#manual/{self.slug}" + (f"/{self.anchor}" if self.anchor else "")


@dataclass
class _Block:
    h2: str
    h3: str
    anchor: str
    raw: str            # afsnittets markdown (uden overskrift)


def _blocks(md: str) -> tuple[str, list[_Block]]:
    """Kapitlets titel og dets afsnit (indledning, ## og ###) med frontendens ankre (renderMarkdown i manual.ts)."""
    m = re.search(r"^#\s+(.+)$", md, re.M)
    title = plain(m.group(1)) if m else ""
    seen: Counter[str] = Counter()
    blocks = [_Block("", "", "", "")]
    h2 = ""
    fence = False
    for line in md.split("\n"):
        if line.startswith("```"):
            fence = not fence
        hm = None if fence else re.match(r"^(#{1,3})\s+(.+)$", line)
        if hm and len(hm.group(1)) == 1:
            continue
        if hm:
            depth, text = len(hm.group(1)), plain(hm.group(2))
            base = slugify(text)
            seen[f"{depth}:{base}"] += 1
            n = seen[f"{depth}:{base}"]
            anchor = (f"m-{base}" if depth == 2 else f"m3-{base}") + (f"-{n}" if n > 1 else "")
            if depth == 2:
                h2 = text
                blocks.append(_Block(h2, "", anchor, ""))
            else:
                blocks.append(_Block(h2, text, anchor, ""))
            continue
        blocks[-1].raw += line + "\n"
    return title, blocks


def section_sha(raw: str) -> str:
    """Kort fingeraftryk af et afsnits markdown (uden tomme linjer og CRLF-forskelle)."""
    norm = "\n".join(line.rstrip() for line in raw.replace("\r\n", "\n").split("\n") if line.strip())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:8]


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _flatten(raw: str, links: dict[str, str]) -> tuple[str, list[tuple[str, str]]]:
    """Et afsnits markdown → LLM-tekst + rækker, der skal være egne stykker ([(rækkenavn, tekst)])."""
    s = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", lambda m: f"(Skærmbillede: {m.group(1)})" if m.group(1) else "", s)

    def link(m: re.Match[str]) -> str:
        text, url = m.group(1), m.group(2)
        target = links.get(url.split("#manual/")[-1].strip("/")) if "#manual/" in url else None
        return f"{text} (se {target})" if target and target not in text else text
    s = re.sub(r"\[([^\]]+)\]\(([^)]*)\)", link, s)
    out: list[str] = []
    rows_out: list[tuple[str, str]] = []
    lines = s.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            head = _cells(line)
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            big = len(rows) >= 3 and len(head) >= 2
            first = len(rows_out)
            for r in rows:
                parts = []
                for j, c in enumerate(r):
                    if not c:
                        continue
                    h = head[j] if j < len(head) else ""
                    parts.append(f"{h}: {c}" if h and j else (f"{h} {c}" if h and not c.startswith(h) else c))
                sentence = plain(" — ".join(parts))
                if big and len(sentence.split()) >= ROW_CHUNK_WORDS:
                    rows_out.append((plain(r[0]), sentence))
                else:
                    out.append(sentence)
            if len(rows_out) > first:
                out.append("Se også: " + "; ".join(name for name, _ in rows_out[first:] if name) + ".")
            continue
        out.append(line)
        i += 1
    return plain("\n".join(out)), rows_out


def _split(text: str) -> list[str]:
    """Del lang tekst ved linjeskift i stykker på højst MAX_WORDS ord (en enkelt lang linje deles ved sætninger)."""
    pieces: list[str] = []
    for line in text.split("\n"):
        words = line.split()
        if len(words) <= MAX_WORDS:
            pieces.append(line)
            continue
        cur = ""
        for sent in re.split(r"(?<=[.!?])\s+", line):
            if cur and len((cur + " " + sent).split()) > MAX_WORDS:
                pieces.append(cur)
                cur = sent
            else:
                cur = f"{cur} {sent}".strip()
        if cur:
            pieces.append(cur)
    chunks, cur = [], ""
    for p in pieces:
        if cur and len((cur + "\n" + p).split()) > MAX_WORDS:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur}\n{p}" if cur else p
    if cur.strip():
        chunks.append(cur)
    return chunks


def _parse(files: list[tuple[str, str]]) -> list[tuple[str, str, list[_Block]]]:
    """[(filnavn uden .md, markdown)] → [(slug, titel, afsnit)]."""
    out = []
    for name, raw in files:
        md = raw.replace("\r\n", "\n")
        title, blocks = _blocks(md)
        out.append((re.sub(r"^\d+-", "", name), title or re.sub(r"^\d+-", "", name), blocks))
    return out


def _path(b: _Block) -> str:
    return " › ".join(x for x in (b.h2, b.h3) if x)


def compile_manual(files: list[tuple[str, str]], extras: list[tuple[str, str]] | None = None) -> list[Section]:
    """Den store manuals filer (+ tillæg) → LLM-manualens stykker."""
    chapters = _parse(files)
    links: dict[str, str] = {}
    for slug, title, blocks in chapters:
        links[slug] = f"Manual › {title}"
        for b in blocks:
            if b.anchor:
                links[f"{slug}/{b.anchor}"] = f"Manual › {title} › {_path(b)}"
    out: list[Section] = []
    for slug, title, blocks in chapters:
        for b in blocks:
            text, rows = _flatten(b.raw, links)
            path = _path(b)
            for part in _split(text) if text else []:
                out.append(Section(title, path, slug, b.anchor, part))
            for name, row in rows:
                out.append(Section(title, f"{path} › {name}" if path else name, slug, b.anchor, row))
    for name, raw in extras or []:
        out += _compile_extra(name, raw, chapters, links)
    return out


def _find(chapters, file: str, anchor: str):
    slug = re.sub(r"^\d+-", "", file)
    for s, title, blocks in chapters:
        if s == slug:
            for b in blocks:
                if b.anchor == anchor:
                    return s, title, b
    return None


def _compile_extra(name: str, raw: str, chapters, links) -> list[Section]:
    """Et tillæg: `## spørgsmål` + `<!-- kilde: … -->` + svar. Uden gyldig kilde springes stykket over."""
    out = []
    parts = re.split(r"^##\s+(.+)$", raw.replace("\r\n", "\n"), flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        m = _KILDE.search(parts[i + 1])
        found = _find(chapters, m.group(1), m.group(2)) if m else None
        if not found:
            continue
        slug, title, b = found
        text, _ = _flatten(parts[i + 1], links)
        if text:
            out.append(Section(title, _path(b), slug, b.anchor, text, keys=plain(parts[i]), extra=True))
    return out


def check(manual_dir: Path) -> list[str]:
    """Problemer med tillæggene: kilde mangler, findes ikke eller er ændret siden tillægget blev skrevet."""
    chapters = _parse(_read(manual_dir))
    problems = []
    for f in sorted((manual_dir / "llm").glob("*.md")):
        parts = re.split(r"^##\s+(.+)$", f.read_text(encoding="utf-8").replace("\r\n", "\n"), flags=re.M)
        for i in range(1, len(parts) - 1, 2):
            q = parts[i].strip()
            m = _KILDE.search(parts[i + 1])
            if not m:
                problems.append(f"llm/{f.name} '{q}': mangler <!-- kilde: fil#anker sha:… -->")
                continue
            found = _find(chapters, m.group(1), m.group(2))
            if not found:
                problems.append(f"llm/{f.name} '{q}': kilden {m.group(1)}#{m.group(2)} findes ikke mere")
            elif section_sha(found[2].raw) != m.group(3):
                problems.append(f"llm/{f.name} '{q}': kilden {m.group(1)}#{m.group(2)} er ændret "
                                f"(sha {m.group(3)} → {section_sha(found[2].raw)}) — tjek tillægget og kør --sync")
    return problems


def sync(manual_dir: Path) -> int:
    """Skriv kildeafsnittenes nuværende sha i tillæggene (efter at de er tjekket). Returnerer antal rettede."""
    chapters = _parse(_read(manual_dir))
    n = 0
    for f in sorted((manual_dir / "llm").glob("*.md")):
        raw = f.read_text(encoding="utf-8")

        def fix(m: re.Match[str]) -> str:
            nonlocal n
            found = _find(chapters, m.group(1), m.group(2))
            if not found or section_sha(found[2].raw) == m.group(3):
                return m.group(0)
            n += 1
            return m.group(0).replace(f"sha:{m.group(3)}", f"sha:{section_sha(found[2].raw)}")
        new = _KILDE.sub(fix, raw)
        if new != raw:
            f.write_text(new, encoding="utf-8")
    return n


def _read(manual_dir: Path) -> list[tuple[str, str]]:
    return [(f.stem, f.read_text(encoding="utf-8")) for f in sorted(manual_dir.glob("*.md"))]


def anchors(manual_dir: Path) -> list[str]:
    """Alle afsnit som `fil#anker  sti  sha:…` — til at skrive nye tillæg."""
    out = []
    for f in sorted(manual_dir.glob("*.md")):
        _, blocks = _blocks(f.read_text(encoding="utf-8").replace("\r\n", "\n"))
        out += [f"{f.stem}#{b.anchor}  {_path(b)}  sha:{section_sha(b.raw)}" for b in blocks if b.anchor]
    return out


if __name__ == "__main__":   # pragma: no cover — værktøj til udvikleren
    from ..config import Settings
    sys.stdout.reconfigure(encoding="utf-8")   # Windows-konsollen er ellers cp1252
    d = Settings().manual_dir
    arg = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if arg == "--sync":
        print(f"{sync(d)} kilder opdateret")
    elif arg == "--anchors":
        print("\n".join(anchors(d)))
    elif arg == "--dump":
        extras = [(f.stem, f.read_text(encoding="utf-8")) for f in sorted((d / "llm").glob("*.md"))]
        for s in compile_manual(_read(d), extras):
            print(f"--- {s.source}{' [tillæg: ' + s.keys + ']' if s.extra else ''} ({len(s.text.split())} ord)\n{s.text}")
    else:
        p = check(d)
        print("\n".join(p) if p else "LLM-manualens tillæg er i trit med manualen")
        sys.exit(1 if p else 0)
