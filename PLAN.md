# Plan: SVG-import af symboler + flere tegneredskaber i Tegn — 2026-11-06

**Mål (Jan 2026-11-06):**
- **Import af SVG-symboler:** flere filer ad gangen til biblioteket, SVG ind i en åben tegning, og bibliotekspakke (eksport/import af egne symboler med opsætning).
- **Nye tegneredskaber i Tegn:** polygon, stjerne og billede. Desuden stiplet streg, pile og linjeender, gradient og skygge, samt lag og z-orden.

**Rammer:**
- Al SVG saneres i backend (`svg_sanitize.py` tillader allerede `image` med raster-data-URI, `marker`, gradienter og `filter`/`feDropShadow`).
- Egne symboler følger reglerne fra del 1 (`library.py`: ét `<g>`, højst 256 KB, defs omdøbes til `def_*`).
- Ingen nye afhængigheder. Pakken er **JSON** (`.hvlib.json`), ikke zip, så der er ingen zip-bomber og ingen ny pakke.

## Del A — v3.31.0: import til biblioteket + Opsætning › Symboler (= del 2 af egne symboler) — ✅ færdig

1. **Backend `library.py`:**
   - `import_svg(user, filename, svg, label, section, replace)` gør hele filen til ét symbol. Den saneres, og viewBox (eller width/height) bliver til `translate`/`scale` ind i et 0-baseret `<g>`. Elementer med id bliver dele (`data-hv-pid`), og defs omdøbes. Der er ingen standardopsætning, kun grafik og dele.
   - Labelkonflikt giver en ny version (`replace`) eller et nyt navn med `_2`, som ved eksport.
2. **API:**
   - `POST /api/library/import` (engineer): multipart med én eller flere filer, højst 50 filer og 5 MB i alt. Svaret giver en status pr. fil (oprettet, ny version eller fejl med begrundelse). Hver fil auditeres.
   - `GET /api/library/package?types=…` (engineer) eksporterer egne symboler med grafik, preset, version og deres placering i opdelingen.
   - `POST /api/library/package` (engineer) importerer en pakke. Alt valideres som i backup (clean_fragment, check_preset), og der vælges mellem *spring over*, *ny version* og *nyt navn* ved konflikter. Pakkens tags medtages ikke.
3. **Frontend, Opsætning › Symboler (ny side):**
   - sektioner: opret, omdøb, slet, rækkefølge;
   - symboler: flyt og ordn, omdøb og slet egne symboler med "bruges i"-advarsel;
   - knapperne *Importér SVG…* (flere filer, vælg sektion, resultattabel), *Eksportér pakke* og *Importér pakke*.
4. **Tegn-paletten:** *Importér SVG…* i sektionen Egne symboler.
5. **Symboltest/symbol-editoren:** egne symboler kan vælges (rest fra del 1).
6. **Tests:**
   - backend: import af én og flere filer, viewBox-normalisering, script/ekstern href fjernet, for stor fil, labelkonflikt, pakke-roundtrip, pakke med ugyldigt preset;
   - frontend: hjælpere til opdelingen.
7. **Manual:** afsnit + skærmbilleder.

## Del B — v3.32.0: SVG ind i en åben tegning — ✅ færdig (endpoint: `POST /api/library/fragment`)
1. **Backend:** `POST /api/svg/sanitize` (engineer) returnerer en saneret SVG og advarsler, så frontenden aldrig indsætter usaneret SVG. Den gemte version saneres igen ved gem.
2. **Tegn:** *Indsæt › SVG-fil…* og træk og slip af en .svg på lærredet indsætter filen som én gruppe ved musen og skaleret til at passe. Defs-id'er omdøbes, så de ikke kolliderer med tegningens egne. Kan fortrydes. Gruppen kan derefter gemmes som symbol (del 1).
3. **Tests:** sanitize-endpointet, id-omdøbning (frontend-test).

## Del C — v3.33.0: nye tegneredskaber
1. **Former:**
   - **polygon:** klik punkt for punkt, dobbeltklik afslutter;
   - **stjerne og regulær polygon:** træk, med antal hjørner og indre radius i Inspector;
   - **billede:** PNG/JPG/WebP/GIF indlejret som data-URI, højst 2 MB, med bevaret proportion.
   SVG-Edit's egne moduser (`polygon`/`star` via udvidelse, `image`) bruges, hvor de findes, ellers eget værktøj i `scada-core.js`.
2. **Streg** (Inspector):
   - stiplet/prikket/stiplet-prikket med `stroke-dasharray` (skaleres med stregtykkelsen);
   - pile i start og slut via `marker`, som oprettes i tegningens `<defs>` pr. farve;
   - `stroke-linecap` og `stroke-linejoin`.
3. **Gradient og skygge:**
   - fyld: ensfarvet, lineær (vinkel og 2 farver) eller radial;
   - skygge: til/fra, forskydning, sløring og farve via `filter`/`feDropShadow`.
   Defs genbruges og ryddes op, når de ikke længere bruges.
4. **Lag og z-orden:**
   - lagpanel i objekttræet: opret, omdøb, skjul, lås, slet (tomt lag) og flyt markerede til lag;
   - z-orden: ét trin op eller ned (+ Ctrl+[ ]).
5. **Hvidlisten** i `scada-core.js:1789` udvides med `stroke-dasharray`, `stroke-linecap`, `stroke-linejoin`, `marker-start`/`marker-end`, `filter` og `fill-opacity`. Kopiér, indsæt, symbol-eksport og Erstat med symbol tager markører, gradienter og filtre med, hvilket del 1's def-kopiering allerede håndterer.
6. **Tests:** engine-hjælpere (dash-skalering, markør-/gradient-defs, oprydning, lag-operationer), backend roundtrip af en tegning med alle nye elementer gennem sanitizeren.
7. **Manual:** afsnit om værktøjerne, opdaterede skærmbilleder af værktøjslinjen og Inspector.

## Risici
- **SVG-Edit 7's polygon/stjerne** er udvidelser, der måske ikke er med i `@svgedit/svgcanvas`. I så fald bygges et eget værktøj (mere arbejde i C1).
- **Billeder gør tegningerne store** (grænsen er 5 MB pr. tegning). Derfor maks 2 MB pr. billede og en tydelig fejl ved for stor tegning.
- **Lag:** symbolkonfigurationer er knyttet til element-id, ikke lag, så det er sikkert at flytte mellem lag. Låste lag skal også respekteres af markering med træk.
- **Overview's live-binding** skal tåle `filter`/`marker` på bundne elementer (fill-animationer må ikke overskrive gradient-fyld utilsigtet). Det tjekkes visuelt.

Rækkefølge: A → B → C. Hver del er sin egen MINOR-version med commit, OTA og merge-spørgsmål.

---

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
