# Plan: LLM-hjælper integreret i SCADA'en — 2026-11-06 — godkendt (Jan: lokal, én samlet pakke, til/fra) — fase 0 ✅ v4.0.0

Baggrund og modelvalg: [docs/LLM_ANALYSE.md](docs/LLM_ANALYSE.md). Ønske fra Jan: en lokal LLM som **hjælper** i SCADA'en, der kører på VM'en (16 GB / 4 vCPU, kun CPU). Hardwaren angives ved installationen og åbner for LLM-funktionerne.

## Mål
- En **Hjælper** (sidepanel), der svarer på spørgsmål om anlægget og systemet, forklarer alarmer og trends, og hjælper i Tegn. Den foreslår fx signal- og rørveje ud fra en forklaring med egne ord.
- **Kun læsning og forslag.** Hjælperen skriver aldrig til en PLC og ændrer aldrig opsætning selv. Forslag anvendes af brugeren med de normale knapper, API'er og rettigheder.
- SCADA'en virker uændret uden LLM (Pi 4, lille VM, model ikke hentet).

## Arkitektur — alternativer
| | Alternativ | Fordele | Ulemper |
|---|---|---|---|
| **A** | **llama.cpp `llama-server` som egen systemd-service** på `127.0.0.1`; styres af en root-hjælper via `.path` (samme mønster som power/update) | Hurtigst på CPU, MIT, ét binært program, OpenAI-kompatibelt API, `json_schema`, fuld kontrol over CPU og RAM (cgroups) | Binært program og model skal installeres og opdateres |
| B | Ollama som service | Nem modelstyring (`pull`) | Større, ekstra dæmon, mindre kontrol over versioner og ressourcer |
| C | llama-cpp-python i SCADA-processen | Ingen ekstra service | Deler proces med live-data og alarmer. **Fravalgt** |

**Valg: A.** Klientlaget taler "OpenAI-kompatibelt", så en admin også kan pege på en **ekstern** server i LAN'et (URL + nøgle i `secrets.json`) med den samme kode, hvis VM'en er for lille. Ekstern kræver et eksplicit valg, fordi data så forlader maskinen.

### Lag
```
Frontend: Hjælper-panel (Tegn, Alarmer, Trends, Overview) ── /api/assist/* (+ SSE-strøm)
API-lag:  api/assist.py (rolle-tjek, pydantic)
Service:  services/assistant.py — samtale, værktøjer (kun læsning), validering, kø (1 ad gangen), tællere
          services/assist_tools.py — værktøjer, der kalder EKSISTERENDE services med brugerens rettigheder
          services/signal_path.py — grafsøgning i tegningen (deterministisk, ingen LLM)
Lag 4c:   backend/app/llm/client.py — ENESTE sted med HTTP til LLM'en (timeout, størrelsesgrænse, ingen hemmeligheder i log)
Service:  scada-llm.service (llama-server, 127.0.0.1:8091, lav prioritet, MemoryMax)
```
`ARCHITECTURE.md` får lag 4c (LLM-klient) med samme regler som undtagelserne for notifier/github: kun den konfigurerede adresse, `trust_env=False` og tidsgrænser.

## Trin
**Fase 0: hardwareprofil og LLM-service (infrastruktur)**
1. Hardwareprofil:
   - `install.sh --hw <pi4|pi5|vm-8|vm-16|vm-32>`;
   - uden parameteren foreslås en profil ud fra `nproc`, `MemTotal` og AVX2, og den skrives i `config/hw.json`;
   - *System › Konfiguration* viser og retter profilen (admin);
   - profilen bestemmer, om LLM kan slås til, og hvilken model der er standard.
2. `deploy/scada-llm.service` + `deploy/apply-llm.sh` (root, `.path`-udløst, samme sikkerhed som apply-power: flyt anmodningen, afvis symlinks, kendte handlinger):
   - **install:** hent llama-server-binær og model fra en fast liste med SHA256, eller brug en fil uploadet til `data/models/` (lukkede net);
   - **start**, **stop**, **skift model**;
   - systemd: bruger `scada-llm` (ikke `scada`), `CPUWeight=20`, `Nice=10`, `MemoryMax` efter profil, `--threads` = vCPU−1, `--parallel 1`.
3. `backend/app/llm/client.py` + `services/assistant.py` grundlag: `health`, `complete(json_schema)` og `stream`. Status, model, svartider og fejl vises på *Status* og i metrics (observability).
4. *System › Hjælper (LLM)* (admin): profil, slå til/fra, model (hentet/mangler, størrelse), lokal/ekstern, test-knap med svartid.

**Fase 1: Hjælper-panel med viden og læse-værktøjer**
5. Viden: manualen (`frontend/src/manual/*.md`) opdelt i afsnit og søgt med BM25 i ren Python. Det kræver ingen embeddings-model og ingen ny afhængighed. Bedste afsnit lægges i prompten, og svaret viser kilden ("Manual › Tags").
6. Værktøjer (kun læsning, med brugerens rolle og tegningsadgang som i `api/trends.py::_allowed`):
   - `aktive_alarmer`;
   - `tag_vaerdi(navne)`;
   - `trend_resume(tag, periode)`: min/max/middel/ændringer, ingen rådata;
   - `tegning_oversigt(id)`: symboler, navne, typer, bindinger;
   - `soeg_manual(tekst)`.

   Højst 4 værktøjstrin pr. spørgsmål og 60 s i alt. Svar strømmes til panelet.
7. Panelet (Svelte):
   - kontekst følger siden (valgt alarm, åben tegning, valgt trend);
   - knappen *Forklar* ved en alarm;
   - samtalen gemmes kun i browserens session (ikke i DB). Audit `assist.ask` logger kun metadata: bruger, side, svartid og tokens.

**Fase 2: signalvej i Tegn**
8. `signal_path.py`:
   - graf fra `data-hv-from`/`data-hv-to` og symbolernes tilslutningspunkter;
   - korteste veje mellem start og slut;
   - symboler på vejen, der skal tolkes (ventil, 3-vejs motorventil, pumpe, kontraventil, forgrening).
9. Signalvej-guide **uden LLM**:
   - vælg start og slut, og vejen fremhæves;
   - spørgsmål pr. symbol (tag, stilling, retning);
   - løbelys/farve på rørene med en samlet betingelse (logik-blokke);
   - gemmes som en navngiven signalvej, der kan rettes.
10. *Forklar med egne ord*: LLM'en får vejen og kandidat-tags (kort prompt) og svarer i fast JSON-skema. Backend validerer (tags findes, stillinger gyldige, symboler på vejen), og svarene udfyldes i guiden, hvor brugeren godkender.

**Fase 3 (senere, efter måling):** forslag til tags ud fra ST-variabler, hjælp i symbolguiden, opsummering af døgnets alarmer.

## Sikkerhed
- Ingen PLC-skrivning og ingen konfigurationsændringer fra LLM'en. Værktøjerne er rene læsefunktioner, der kalder services med brugerens rettigheder.
- Ingen hemmeligheder i prompts: PLC-adresser, adgangskoder, tokens og API-nøgler sendes aldrig med. Tags sendes med navn og enhed, ikke kilde.
- Prompt-injektion via elementnavne og alarmtekster: alt data fra anlægget markeres som data. Værktøjerne har ingen sideeffekter, og output valideres.
- Hvem må hvad:
  - operatør: hjælper med læse-værktøjer inden for egne tegninger;
  - tekniker: også signalvej;
  - admin: også opsætning.
- Rate-grænse pr. bruger og kø (1 ad gangen). Status viser kø og belastning.
- Ekstern LLM kun via eksplicit admin-valg, med advarsel. URL og nøgle er skriv-kun i `secrets.json`.

## Afhængigheder (kræver godkendelse)
- llama.cpp (`llama-server`, MIT) som binær fil på serveren, ikke i Python. Ingen nye Python-pakker; `httpx` findes.
- Modelfiler (GGUF), fx Qwen3.5-4B Q4_K_M (Apache-2.0) med Ministral-3-8B (Apache-2.0) som alternativ. Hentes separat, ikke i git eller OTA.

## Berørte filer (cirka)
- **Nye:**
  - `deploy/`: `scada-llm.service`, `hypervisionplc-scada-llm.path`/`.service`, `apply-llm.sh`, `llm-models.json`;
  - backend: `backend/app/llm/client.py`, `services/assistant.py`, `services/assist_tools.py`, `services/assist_knowledge.py`, `services/signal_path.py`, `api/assist.py`;
  - frontend: `frontend/src/lib/AssistPanel.svelte`, `pages/SystemAssist.svelte`, `lib/SignalPathGuide.svelte`.
- **Ændres:**
  - `deploy/install.sh` (`--hw`), `make-package.sh`;
  - `main.py`, `config.py`, `sysconfig.py`, `health.py`/`metrics.py`;
  - `App.svelte` (panel og menupunkt), `DrawEditor.svelte`;
  - `ARCHITECTURE.md`, manualen (nyt kapitel *Hjælperen*).

## Risici
- Svartid på 4 vCPU (15–40 s): korte prompts, strømmede svar, 4B-model og kø.
- Forkerte svar: kildehenvisninger, kun forslag, validering og brugerens godkendelse.
- RAM og CPU-konkurrence med SCADA: egen service med cgroup-grænser. Måles i fase 0, inden noget mere bygges.
- Mamba/MoE-modellers understøttelse i llama.cpp: standardmodellen er tæt (Qwen3.5-4B).

## Rækkefølge og versioner
Fase 0 → måling på VM'en (`docs/LLM_ANALYSE.md` § 7) → fase 1 → fase 2. Hver fase er sin egen MINOR-version med test, review (reviewer: sikkerhed, rettigheder, root-hjælperen) og OTA-pakke.

---

# Plan: Fjern PLC — flyt tags til en anden PLC eller fjern alt — 2026-11-06 — ✅ færdig (v3.34.0)

**Problem (Jan):** En PLC kan ikke fjernes. `PlcService.delete` afviser med 409, så længe PLC'en har tags. Hvert tag kan igen kun slettes, når ingen binding, symbolopsætning eller ugeprogram bruger det. Det er umuligt i praksis.

**Ønske:** Fjern-dialogen skal give to valg (Jan: "begge muligheder"):
1. **Flyt tags til en anden PLC**, fx når en PLC er udskiftet. Tags, bindinger, opsætninger og historik bevares, og kun kilden skifter fra `plcA:…` til `plcB:…`.
2. **Fjern alt:** PLC'en, dens tags og alle henvisninger til dem fjernes i én handling, efter en oversigt over konsekvenserne og en backup.

En PLC uden tags fjernes som i dag.

## Trin
1. **Backend** (`services/plc_removal.py`, ny; lag 2):
   - **`usage(key)`** giver tags (antal og navne), tegninger med bindinger, symbolopsætninger (også grupper), ugeprogrammer, trendvisninger, API-nøgler med tagsene i scope, aktive alarmer, antal tags med historik og de andre PLC'er, der kan flyttes til.
   - **`move(key, target)`:**
     - Hver kilde valideres med `TagService._validate` (skrivbarhed, energi og alarm). Ved fejl afbrydes der, før noget ændres, og listen over problemer vises.
     - Derefter opdateres `tags.source`/`plc` i én transaktion, og PLC'en og dens adgangskode slettes.
     - Til sidst `reload_plc` (begge PLC'er) og `reload_tags`.
   - **`remove_all(key)`:**
     - Først backup (`save_to_server("foer-plc-fjern")`). Fejler den, afbrydes der.
     - Derefter i én transaktion:
       - bindinger med tagsene (også `dir_tag`) slettes;
       - i symbolopsætninger og grupper fjernes animationer, der bruger tagsene, og signal-, fejl-, logik- og graf-henvisninger tømmes (symbolet skal sættes op igen);
       - ugeprogrammer på tagsene slettes;
       - tagsene fjernes fra trendvisninger og API-nøglers scope;
       - `alarm_state` slettes (alarmhændelser bevares som historik);
       - tags og PLC slettes.
     - Efter commit: trendhistorikken glemmes (`trend_recorder.forget`), adgangskoden slettes, og der reloades.
   - Alt logges og auditeres med optælling.
2. **API** (kun admin):
   - `GET /api/plcs/{key}/usage`;
   - `POST /api/plcs/{key}/remove` med `{mode: "move" | "all", target?, confirm: "<key>"}`. Ved "all" skal PLC'ens nøgle tastes som bekræftelse.
3. **Frontend:** `PlcRemove.svelte`, en dialog fra knappen *Fjern* på siden PLC'er:
   - en oversigt over konsekvenserne;
   - valget *Flyt tags til* (rulleliste med PLC'er) eller *Fjern alt* (tast nøglen);
   - resultat og fejl vises som tekst.
4. **Tests:**
   - flyt (kilder, bindinger og historik intakte; valideringsfejl ændrer intet);
   - fjern alt (alle henvisninger væk, backup-fil skrevet, alarmhændelser bevaret);
   - uden tags, roller og forkert bekræftelse;
   - frontend: hjælpefunktioner.
5. **Dokumentation:** manual (kapitlet om PLC'er og tags), CHANGELOG, RELEASE_NOTES, FEATURES og version 3.34.0.

## Risici
- Hovedbasen og trend-databasen er adskilte. Historikken slettes derfor først efter commit; fejler det, logges det, og en senere oprydning tager resten.
- Symboler, der mister animationer eller signaler, viser derefter "ikke sat op" og kan sættes op igen med guiden. Oversigten siger hvilke.
- Flyt til en PLC af en anden type (fx uden RTU/MBX): valideringen afviser samlet, før noget ændres.

---

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

## Del C — v3.33.0: nye tegneredskaber — ✅ færdig (+ bue-værktøj efter ønske fra Jan)
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
