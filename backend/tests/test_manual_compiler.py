"""Hjælperens LLM-manual (v4.9.0): den store manual kompileret til søgbare stykker + tillæg bundet til afsnit."""

from app.config import Settings
from app.services import manual_compiler as mc
from app.services.assist_knowledge import ManualIndex

CH = """# Symboler

Indledning.

## De seks trin

| Trin | Hvad du gør |
| --- | --- |
| **1. Symbol** | Vælg betjeningsform: kun visning, positioner, trykknap eller setpunkt |
| **2. Signaler** | Vælg de tags, symbolet skriver og læser tilbage, og hvordan der skrives |
| **3. Kontakter** | Kort |

![Trin 1 — Symbol](../../public/manual/guide-1.png)

### Trin 2 — Signaler

Se [Logik](#manual/symboler/m3-logikblokke) og [Alarmer](#manual/alarmer).

### Logikblokke

AND og OR.

## De seks trin

Igen.
"""
ALARM = "# Alarmer\n\n## Kvittér en alarm\n\nTryk Kvittér.\n"


def compiled(extras=None):
    return mc.compile_manual([("10-symboler", CH), ("03-alarmer", ALARM)], extras)


def test_sections_get_paths_and_the_frontends_anchors():
    secs = compiled()
    got = {(s.heading, s.anchor) for s in secs}
    assert ("De seks trin", "m-de-seks-trin") in got
    assert ("De seks trin › Trin 2 — Signaler", "m3-trin-2-signaler") in got        # ### under ##
    assert ("De seks trin", "m-de-seks-trin-2") in got                                 # gentaget overskrift
    assert ("Kvittér en alarm", "m-kvitt-r-en-alarm") in got                           # som slugify i manual.ts
    intro = next(s for s in secs if s.heading == "")
    assert intro.text == "Indledning." and intro.href == "#manual/symboler"


def test_tables_are_flattened_and_long_rows_become_their_own_pieces():
    secs = compiled()
    rows = {s.heading: s for s in secs if s.heading.startswith("De seks trin › ")}
    assert "De seks trin › 1. Symbol" in rows and "De seks trin › 2. Signaler" in rows
    assert rows["De seks trin › 1. Symbol"].text.startswith("Trin 1. Symbol — Hvad du gør: Vælg betjeningsform")
    assert rows["De seks trin › 1. Symbol"].href == "#manual/symboler/m-de-seks-trin"   # henviser til afsnittet
    main = next(s for s in secs if s.anchor == "m-de-seks-trin")
    assert "Trin 3. Kontakter — Hvad du gør: Kort" in main.text                         # kort række bliver i afsnittet
    assert "Se også: 1. Symbol; 2. Signaler." in main.text
    assert "(Skærmbillede: Trin 1 — Symbol)" in main.text and "png" not in main.text


def test_internal_links_are_resolved_to_section_names():
    t = next(s for s in compiled() if s.anchor == "m3-trin-2-signaler").text
    assert "Logik (se Manual › Symboler › De seks trin › Logikblokke)" in t
    assert "Alarmer (se Manual › Alarmer)" in t


def test_long_text_is_split_into_pieces_of_max_words():
    md = "# K\n\n## Lang\n\n" + "\n".join(f"Linje {i} " + "ord " * 30 for i in range(10))
    parts = [s for s in mc.compile_manual([("01-k", md)]) if s.heading == "Lang"]
    assert len(parts) >= 3 and all(len(p.text.split()) <= mc.MAX_WORDS for p in parts)
    assert parts[0].text.startswith("Linje 0") and "Linje 9" in parts[-1].text


def test_extras_are_bound_to_a_source_section_and_searchable(tmp_path):
    sha = mc.section_sha("\nTryk Kvittér.\n")
    extra = (f"# T\n\n## Hvordan acknowledger jeg?\n<!-- kilde: 03-alarmer#m-kvitt-r-en-alarm sha:{sha} -->\nBrug knappen.\n\n"
             "## Uden kilde\nIgnoreres.\n\n## Forkert kilde\n<!-- kilde: 03-alarmer#m-findes-ikke sha:00000000 -->\nX\n")
    secs = [s for s in compiled([("t", extra)]) if s.extra]
    assert len(secs) == 1
    assert (secs[0].keys, secs[0].href, secs[0].text) == ("Hvordan acknowledger jeg?", "#manual/alarmer/m-kvitt-r-en-alarm",
                                                           "Brug knappen.")
    (tmp_path / "03-alarmer.md").write_text(ALARM, encoding="utf-8")
    (tmp_path / "llm").mkdir()
    (tmp_path / "llm" / "t.md").write_text(extra, encoding="utf-8")
    hit = ManualIndex(tmp_path).search("acknowledger", 1)[0][0]
    assert hit.source == "Manual › Alarmer › Kvittér en alarm"                         # kilden i den store manual


def test_check_fails_when_the_source_section_changes_and_sync_fixes_it(tmp_path):
    (tmp_path / "03-alarmer.md").write_text(ALARM, encoding="utf-8")
    (tmp_path / "llm").mkdir()
    sha = mc.section_sha("\nTryk Kvittér.\n")
    f = tmp_path / "llm" / "t.md"
    f.write_text(f"## Spørgsmål\n<!-- kilde: 03-alarmer#m-kvitt-r-en-alarm sha:{sha} -->\nSvar.\n\n## Uden kilde\nX\n",
                 encoding="utf-8")
    assert mc.check(tmp_path) == ["llm/t.md 'Uden kilde': mangler <!-- kilde: fil#anker sha:… -->"]
    (tmp_path / "03-alarmer.md").write_text(ALARM + "Og kvittér alle.\n", encoding="utf-8")   # kilden ændres
    problems = mc.check(tmp_path)
    assert any("er ændret" in p and "Spørgsmål" in p for p in problems)
    assert mc.sync(tmp_path) == 1
    assert not any("er ændret" in p for p in mc.check(tmp_path))
    (tmp_path / "03-alarmer.md").write_text("# Alarmer\n\n## Andet\n\nX\n", encoding="utf-8")  # kilden forsvinder
    assert any("findes ikke mere" in p for p in mc.check(tmp_path))


def test_sha_ignores_blank_lines_and_line_endings():
    assert mc.section_sha("a\r\n\r\nb  \n") == mc.section_sha("\na\nb\n")


def test_real_extras_are_in_step_with_the_manual():
    """Fejler, når et afsnit i den store manual er ændret, uden at LLM-manualens tillæg er tjekket.
    Ret tillægget i frontend/src/manual/llm/ og kør (fra backend/): python -m app.services.manual_compiler --sync"""
    assert mc.check(Settings().manual_dir) == []


def test_real_manual_compiles_and_finds_typical_questions():
    idx = ManualIndex(Settings().manual_dir)
    assert idx.count() > 400
    cases = {
        "hvordan vælger jeg et symbol bag et andet som er foran": "Vælg, flyt og markér",
        "hvad gør trin 2 signaler i guiden": "Trin 2",
        "hvordan laver jeg en logikblok": "Logikblokke",
        "røret har løsnet sig fra symbolet": "Sæt et rør fast igen",
        "hvordan ser jeg energiforbruget pr dag": "Energi",
    }
    for q, want in cases.items():
        hits = [s.source for s, _ in idx.search(q, 3)]
        assert any(want in h for h in hits), (q, hits)
        assert len(set(hits)) == len(hits)                                              # ét stykke pr. afsnit
