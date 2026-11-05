# Plan: Egne symboler — eksport fra Tegn til symbolbiblioteket — 2026-11-05

**Mål:** en tekniker/admin kan markere et objekt eller en gruppe i Tegn og gemme det som et nyt symbol i biblioteket — med alt hvad et bibliotekssymbol har: grafik, navngivne dele, tilslutningspunkter og standardopsætning (betjeningsform, positioner, signaler, kontaktplaner, animationer, graf). Symbolet kan derefter indsættes, sættes op med guiden og afprøves i Symboltest som de indbyggede. Biblioteket kan organiseres: egne sektioner, flytte symboler (også indbyggede) mellem sektioner og ordne dem.

**Jans krav (2026-11-05):** (1) kun admin og tekniker · (2) nye symboler med alt hvad det indebærer · (3) i en "Egne symboler"-sektion, gerne organisering af symboler generelt · (4) ingen automatisk opdatering af tegninger — en ny version af et symbol tages i brug med den eksisterende *Erstat med symbol*.

## Arkitekturvalg

Hvor bor egne symboler?
- (a) Statisk fil i frontend-bygget — kræver nyt build/OTA for hvert symbol. Fravalgt.
- (b) Som "skabelon-tegninger" i drawings-tabellen — genbruger versionering, men blander tegninger og bibliotek. Fravalgt.
- (c) **Valgt:** egne tabeller i SQLite + REST under `/api/library`; frontend fletter dem ind i `SYMBOLS`. Følger mønstret fra tilslutningspunkterne (`symbol_ports`), kommer med i backup, og SVG renses på serveren med den eksisterende `svg_sanitize`.

## Datamodel (ny, additiv — ingen ændring af eksisterende tabeller)

- `library_symbols`: `type` (PK, `u_<slug>` — kan ikke kollidere med indbyggede), `label`, `hint`, `svg` (renset fragment, ét `<g>`, ≤ 256 KB), `preset` (JSON: standardopsætning med del-navne i stedet for element-id'er, tags fjernet), `ports` (JSON), `version` (int, +1 ved hver gem), `created_by`, `updated_by`, `updated_at`.
- `library_sections`: `id`, `label`, `sort` — egne sektioner; "Egne symboler" oprettes automatisk.
- `library_layout`: `type` → `section` + `sort` — placering/rækkefølge for ALLE symboler (indbyggede og egne); uden række står et indbygget symbol i sin oprindelige kategori.

## Trin

1. **Backend** (`services/library.py`, `api/library.py`, `storage/db.py`):
   - `GET /api/library` (VIEWER) → egne symboler, sektioner, layout.
   - `POST/PUT/DELETE /api/library/symbols/{type}` (ENGINEER): rens SVG, validér preset med den eksisterende `validate_config`, ports med `clean_ports`; navn unikt; version +1.
   - `PUT /api/library/layout`, sektioner CRUD (ENGINEER); en sektion med symboler kan ikke slettes.
   - Audit-log + struktureret log på alle ændringer; antal egne symboler på Status/`/metrics`.
   - Med i backup/gendan (validering som `symbol_ports`). Tests.
2. **Udtræk fra Tegn** (`lib/symbolExport.ts`, ren funktion + tests): markering → ét `<g>` flyttet til (0,0); `data-hv-pid` og id'er bliver delnavne (unikke, `[a-z0-9_]`); instans-attributter (`data-hv-name`, rod-id) fjernes; indlejrede bibliotekssymbolers opsætninger flettes til ét preset med del-referencer. Tags fjernes som standard (valg: "behold tags").
3. **Dialogen "Gem som symbol"** i Tegn (Egenskaber-panelet for valgt objekt/gruppe): navn, forklaring, sektion, forhåndsvisning, valget om tags; "Gem som ny version" når navnet findes. Forhåndsvisning i dialogen.
4. **Biblioteket i frontend**: `SYMBOLS` + egne → én kilde (`lib/library.ts`), brugt af paletten i Tegn, *Erstat med symbol*, Symboltest, symbol-editoren og objekttræet; `libraryDefault()` bruger et eget symbols preset. Sektioner og rækkefølge fra layoutet.
5. **Organisering** (Opsætning › Symboler): sektioner (opret/omdøb/slet/ordn), flyt symboler mellem sektioner og ordn dem, omdøb/slet egne symboler, se version og hvem der gemte.
6. **Manual** (nyt afsnit + skærmbilleder af dialogen og organiseringen), CHANGELOG/RELEASE_NOTES, version (MINOR), OTA-pakke, set i browseren.

## Berørte filer
Backend: `storage/db.py`, `services/library.py` (ny), `api/library.py` (ny), `api/routes.py`, `services/backup.py`, tests. Frontend: `lib/library.ts` (ny), `lib/symbolExport.ts` (ny), `pages/DrawEditor.svelte`, `lib/SymbolReplace.svelte`, `pages/SymbolEditor.svelte`, `pages/SymbolTest.svelte`, `lib/draw/ObjectTree.svelte`, `lib/symbolConfig.ts`, `svgedit-host/scada-core.js` (kun hvis indsættelsen skal kende egne typer), manual.

## Risici / åbne punkter
- **Sammenfletning af flere opsatte symboler**: en gruppe med fx to knapper har to betjeningsformer, men et symbol har kun én. Valgt regel: animationer flettes altid; højst ét indlejret symbol må have betjening (ellers vises en fejl, der peger på hvilke); loft 12 animationer/8 signaler som i dag.
- **Sikkerhed**: SVG fra brugere → renses på serveren (samme regler som tegninger), størrelsesloft, kun ENGINEER skriver.
- **Sletning af et symbol, der bruges i tegninger**: tegningerne beholder deres kopi (symboler er altid kopier); dialogen viser hvor mange tegninger der bruger typen.
- **Versionering af SCADA'en**: nye tabeller er additive (ingen migration af eksisterende data) → MINOR-bump.
- Omfanget er stort — leveres i to commits: (1) backend + bibliotek + eksport, (2) organisering + manual.
