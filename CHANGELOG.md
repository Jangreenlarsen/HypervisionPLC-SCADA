# Changelog

Nyeste øverst. Format: `## [version build NNNN] — YYYY-MM-DD — beskrivelse`

---

## [0.52.2 build 0077] — 2026-10-16 — manual: setpunktets tag vælges i trin 2

- `frontend/src/manual/10-eksempler.md` — eksemplet "Setpunkt med beregning" sagde, at registeret vælges i trin 1; det vælges i guidens trin 2 (Signaler). Rettet ved gennemlæsning mod guiden.

## [0.52.1 build 0076] — 2026-10-16 — fix: topmenu og manual på smalle skærme

- `frontend/src/App.svelte` — på skærme ≤ 640 px er alle fire menupunkter, alarmklokken og AGPL-linket på én linje (Bruger-menuen blev før skubbet ud over kanten); pilene og "· kildekode" skjules, AGPL-linket bliver.
- `frontend/src/pages/Manual.svelte` — kapitelvælger (rulleliste) i stedet for den lange liste på smalle skærme. Set i browser. Se BUGS.md.

## [0.52.0 build 0075] — 2026-10-16 — Brugermanual i systemet

- `frontend/src/manual/*.md` (nye, 11 kapitler) — kom i gang og roller; Drift (Overview, Alarmer, Trends, Energi); PLC'er og tags; Tegninger og Tegn; Bindinger og animationer (inkl. beregning); symboler og guiden (positioner, kontaktplaner, logikblokke, nøglelås, hurtig opsætning af 3-vejs ventil); symbolbiblioteket (**genereres** af `src/lib/manualGen.test.ts` ud fra koden: 85 symboler med de betjeningsformer guiden tilbyder); ugeprogrammer; System (Log, Brugere, Backup, Opdatering); 11 trin-for-trin-eksempler; fejlfinding og ordliste.
- `frontend/src/pages/Manual.svelte` + `lib/manual.ts` — siden **Manual** (Bruger-menuen, `#manual/<kapitel>/<afsnit>`): kapiteloversigt med afsnit, søgning på tværs af kapitler med træf og uddrag, fremhævning af søgeordet, forrige/næste kapitel. Markdown vises med `marked` (MIT — kompatibel med AGPL) og renses med DOMPurify.
- `frontend/src/lib/nav.ts` — `USER_PAGES`: Manual er en side under **Bruger** for alle roller; `pageFor`/`groupOf` kender den.
- Tests: `manual.test.ts` (opbygning, anker, rendering, rensning af farligt indhold, søgning, fremhævning, og at **alle menusider og alle 85 symboler er omtalt**), `manualGen.test.ts` (kapitlet er opdateret), `nav.test.ts`. En fejl i søgefremhævningen (regex med g-flag sprang tekstnoder over) blev fundet af testen og rettet.

## [0.51.1 build 0074] — 2026-10-16 — Bruger-menuen yderst til højre

- `frontend/src/App.svelte` — **Bruger**-punktet står nu yderst til højre i topbjælken (efter alarmklokke og kildekode-linket), de tre andre menuer til venstre. Set i browser.

## [0.51.0 build 0073] — 2026-10-16 — Hovedmenu: Drift, Opsætning, System, Bruger med rullemenuer

- `frontend/src/App.svelte` — topbjælken har nu fire menupunkter i stedet for ét "Menu"-panel: **Drift**, **Opsætning**, **System** (efter rolle) og **Bruger**. En rullemenu åbner af sig selv, når musen føres hen over et punkt (kun rigtig mus — touch bruger tryk), lukker 220 ms efter at musen forlader den (så man kan gå skråt ned i menuen) og skifter straks ved flytning mellem punkter; klik åbner/lukker, Escape og klik udenfor lukker, valg af en side lukker. Det punkt hvis side man står på, er understreget. **Bruger** (til højre for menuerne) viser navn og rolle, Skift adgangskode, Log ud og version. Brødkrumme, alarmklokke og kildekode-link uændrede; Driftpanel-rollen har stadig ingen topmenu. Menuindholdet er uændret (`nav.ts`). Layoutet er **set** i browser på testserveren.

## [0.50.1 build 0072] — 2026-10-16 — fix: OTA viser build og tjekker build; pakkekort skjules under opdatering

Fundet ved afprøvning på testserveren (se BUGS.md); selve opdateringen blev installeret **gennem OTA-siden**.

- `deploy/apply-update.sh` — status og besked viser "version build N" (før: "0.50.0 → 0.50.0" når kun build ændredes); sundhedstjekket efter opdateringen og efter tilbagerulning kræver både version og build.
- `frontend/src/pages/Update.svelte` — pakkekortet (med "geninstallér alligevel" og knapper) skjules mens en opdatering kører.

## [0.50.0 build 0071] — 2026-10-16 — OTA-opdatering fra web-GUI'et

- `backend/app/services/updates.py` (ny) — `inspect_package()` kontrollerer en pakke uden at pakke den ud (kun filer og mapper under `scada/`, ingen `..`/absolutte stier/links, størrelses- og antalsgrænser, nødvendige filer, gyldigt `version.json`, SHA-256); `UpdateService`: status (aktiveret, klargjort pakke, tilstand idle/queued/applying/done/failed/rolled_back/stalled, log), `stage`, `apply` (kontrolsummen skal svare til den klargjorte pakke; ældre version afvises; samme version kræver bekræftelse; backup `scada-pre-update-*` før anmodningen), `discard`; intet kan ændres mens en opdatering er i gang.
- `backend/app/api/system.py` (ny, kun admin) — `GET /api/system/update`, `POST …/upload` (streames, max 60 MB), `POST …/apply`, `DELETE …/staged`; alt i audit-loggen.
- `deploy/apply-update.sh` + `hypervisionplc-scada-update.{path,service}` (nye) — root-hjælper udløst af en anmodningsfil: sletter anmodningen først, kopierer pakken til en root-ejet arbejdsmappe, tjekker kontrolsum og version, gemmer forrige kode, kører `install.sh --update`, tjekker `/api/health` (skal melde den nye version) og **ruller tilbage** ved fejl; skriver `status.json` og `update.log`. Ligger uden for programmappen, som installationen erstatter.
- `deploy/install.sh` — `--update` (springer apt/pip-opgradering over), installerer hjælper og enheder, `updates/`-mappen og markøren `enabled`; genstarter mock-PLC'en hvis den kører.
- `deploy/make-package.sh` (ny) — bygger pakken af det committede.
- `frontend/src/pages/Update.svelte` + `lib/updateUi.ts` — siden System › Opdatering (upload, version og kontrolsum, bekræftelse, fremdrift gennem serverens genstart, resultat/tilbagerulning, log); menupunkt og rute.
- Tests: `test_updates.py` (38) og `updateUi.test.ts`.
- **Afgrænsning:** kontrolsummen beskytter mod beskadigelse, ikke mod en ondsindet admin (kode kører som root via opdateringen). Signerede pakker kan tilføjes senere.

## [0.49.0 build 0070] — 2026-10-16 — Betjeningsformer efter symbol i guidens trin 1

- `frontend/src/lib/symbolConfig.ts` — `allowedOps(type, current)`: hvilke af Kun visning / Positioner / Trykknap / Setpunkt der giver mening for hvert bibliotekssymbol (3-vejs motorventil: visning + positioner; reguleringsventil: visning + setpunkt; pumper, motorer, kontaktorer: visning + positioner + trykknap; rør, tanke, målere, lamper og solcelledele: kun visning; betjeningssymboler: deres egen form). Ukendte typer og egne tegninger får alle fire; den nuværende (gemte) form skjules aldrig.
- `frontend/src/lib/SymbolGuide.svelte` — trin 1 viser kun de relevante former med afkrydsningen "Vis alle betjeningsformer". Kun i brugerfladen; serveren afviser ikke de øvrige. Tests i `libraryDefaults.test.ts`.
- Knappen "Eksempel: 7-trins vælger" vises kun for vælgere og egne tegninger.

## [0.48.1 build 0069] — 2026-10-16 — fix: hurtig opsætning af 3-vejs ventil skifter til "Kun visning"

- `frontend/src/lib/SymbolGuide.svelte` — uden et valgt skrivbart tag skifter hurtig opsætning symbolet fra "Positioner" til "Kun visning" (så trin 2 ikke viser en fejl, og forslagets positions-animationer fjernes) og oplyser det. Set på testserveren. Se BUGS.md.

## [0.48.0 build 0068] — 2026-10-16 — 3-vejs ventil: hurtig opsætning med ét til/fra-tag

- `frontend/src/lib/symbolConfig.ts` — `valveFromTag()` (+ `isValveType`): tre farve-animationer for portene A, B og AB ud fra ét tag (Til = AB → A, Fra = AB → B, AB altid åben); erstatter kun animationer på de tre porte; melder om symbolet mangler portene eller der ikke er plads (højst 12).
- `frontend/src/lib/SymbolGuide.svelte` — sektionen **Hurtig opsætning** øverst i trin 4 for de to 3-vejs motorventiler: vælg et til/fra-tag, tryk **Opret animationer** (bekræftelse hvis portene allerede har animationer; tal-tags afvises med en klar besked). Virker også for skrivebeskyttede indgange (visning).
- Tests: `libraryDefaults.test.ts` (frontend) og `test_symbol_logic.py` (serveren accepterer formen).

## [0.47.2 build 0067] — 2026-10-16 — fix: 3-vejs motorventilerne har tre hvide porte

- `frontend/src/lib/symbols.ts` — portene A, B og AB er hvide i begge varianter (før: to sorte og én hvid), så farven alene styres af animationerne. Set i browser. Se BUGS.md.

## [0.47.1 build 0066] — 2026-10-16 — fix: guidens tag-dropdowns pressede "Skrives som" ud

- `frontend/src/lib/SymbolGuide.svelte` — tag-dropdowns i guidens tabeller og animationsrækker er højst 15 em brede (`:global`, da TagSelect er en underkomponent); "Skrives som" har mindstebredde og må ombrydes. Se BUGS.md. Layoutet er **set** på testserveren (1280 px).

## [0.47.0 build 0065] — 2026-10-16 — 3-vejs motorventil med AB i midten

- `frontend/src/lib/symbols.ts` — nyt symbol **3-vejs motorventil (AB i midten)**: AB nederst, A til venstre, B til højre, motor øverst; samme delnavne (`port_a`, `port_b`, `port_ab`, `motor`).
- `frontend/src/lib/symbolConfig.ts` — guidens forslag (AB → A / AB → B med farver pr. port) gælder begge varianter; test i `libraryDefaults.test.ts`.

## [0.46.0 build 0064] — 2026-10-16 — 3-vejs motorventil + logikblok som løbelysets retning

- `frontend/src/lib/symbols.ts` — nyt bibliotekssymbol **3-vejs motorventil** (Rør og VVS): portene A (venstre), B (top) og AB (højre) og motoren er egne dele (`port_a`, `port_b`, `port_ab`, `motor`), så hver port kan farves for sig.
- `frontend/src/lib/symbolConfig.ts` + `SymbolGuide.svelte` — `libraryDefault()`: et nyt 3-vejs symbol får et forslag med to positioner **AB → A** og **AB → B** og farve pr. port (A og AB åbne i den første, B og AB i den anden); tag vælges i trin 2. Danske delnavne (Port A/B/AB, Motor).
- `backend/app/services/symbols.py` + `SymbolGuide.svelte` — løbelysets **Retning fra** kan være et tag **eller en logikblok** (i symbolet selv eller et andet); serveren oversætter blokken til dens live-værdi, validerer at den findes, og blokken tæller som brugt (advarsel/integritet).
- Tests: backend `test_symbol_logic.py` (36), `test_expression_and_delete.py` (31), frontend `logicExpr.test.ts` (36) — dækker logikblokke, beregning (parity med browseren), slet tegning og retning fra blok; regel 14 indhentet for v0.41–v0.45.

## [0.45.0 build 0063] — 2026-10-16 — Logikblokke kan bruges i andre symboler

**Bemærk:** implementeret uden nye tests efter Jans ønske (Jan tester først). Kun kompilering, en røgtest af beregning og løkkekontrol, og de eksisterende suiter er kørt.

- `backend/app/services/symbols.py` — en blok i et andet symbol på samme tegning kan bruges som kilde i en animation eller som indgang i en blok: `@<symbol>:<blok>` (egne blokke er stadig `@L1`). `logic_results()` regner hele tegningens blokke på én gang (med memo og vagt mod løkker); `_logic_cycle()` afviser løkker på tværs af symboler ved gem; `validate_config` tjekker at det andet symbol og dets blok findes og at blokken ikke bruges uden advarsel. Integritet: en blok (eller et symbols konfiguration) der bruges af et andet symbol kan ikke fjernes, før henvisningen er fjernet dér (400 ved gem, 409 ved "Fjern konfiguration"). `GET …/config` leverer `logic_pool` (de andre symbolers blokke) til guiden.
- `backend/app/services/symbol_runtime.py` — blokkene regnes pr. tegning, så en blok kan afhænge af blokke i andre symboler.
- `backend/app/api/symbols.py` — kontrollen i guiden (`preview`) kender de andre symboler.
- `frontend/src/lib/SymbolGuide.svelte` + `symbolConfig.ts` — valglisterne for kilde og indgang har nu grupperne "Dette symbol" og "Andre symboler"; trin 6 viser også blokke fra andre symboler live (`evalLogic` med `foreign`).

## [0.44.0 build 0062] — 2026-10-16 — Logikblokke i symbol-guiden

**Bemærk:** implementeret uden nye tests efter Jans ønske (Jan tester først). Kun kompilering er kontrolleret, plus en kørsel af de eksisterende suiter (backend symbol/backup: 106 bestået, frontend: 175 bestået) og en røgtest af beregningen.

- `backend/app/services/symbols.py` — nyt skema `logic` (højst 8 blokke): `LogicBlock` (`id` L1…, `name`, `op` and/or, 1–4 `inputs`, `invert`) og `LogicInput` (`src` = tag eller tidligere blok `@L1`, `neg`, for tal-tags `cmp` ge/le/eq + `value`). `evaluate_logic()` regner blokkene i rækkefølge med tre-værdi-logik: en afgørende indgang vinder (AND med Fra = Fra, OR med Til = Til), ellers er resultatet ukendt. Valideringen (trin 4) kontrollerer unikke id'er, 1–4 indgange, at tags findes, at en blok kun bruger blokke over sig (ingen løkker), at tal-tags har sammenligning og til/fra-tags ikke har, og at animationer kun peger på blokke der findes (ikke Niveau/Gennemsigtighed); en ubrugt blok giver en advarsel. `config_tags` tager blokkenes tags med (så de ikke kan slettes, og backup tjekker dem); animationer med kilde `@L1` bliver bindinger på blokkens pseudo-tag; `tags_for_drawing` tager blokkenes pseudo-tags med (adgang pr. tegning).
- `backend/app/services/symbol_runtime.py` — beregner logikblokkene for alle symboler med `logic` (også visnings-symboler) og lægger dem i live-cachen som `sym:<tegning>:<element>:logic:<id>`; slettede blokke ryddes. Ukendt resultat = kvalitet `comm_error`.
- `frontend/src/lib/symbolConfig.ts` — typer, `newBlock`, `removeBlock`, `describeBlock` og `evalLogic` (samme regler som serveren, til trin 6).
- `frontend/src/lib/SymbolGuide.svelte` — sektionen **Logik** øverst i trin 4 (blokke med AND/OR, NOT pr. indgang og på resultatet, op til 4 indgange, tal-tags med ≥/≤/=, en blok som indgang i en senere blok); en animations kilde kan nu være **en logikblok**; trin 6 viser blokkenes live-værdier.

## [0.43.0 build 0061] — 2026-10-16 — Guiden i 6 trin er den primære model for symboler

**Bemærk:** implementeret uden nye tests efter Jans ønske (Jan tester først); kun kompilering er kontrolleret.

- `frontend/src/pages/DrawEditor.svelte` — et navngivet symbol har knappen **Opsæt symbol (6 trin)**, som åbner guiden direkte i Tegn. Guiden arbejder på tegningens aktive version, så en ny eller ændret tegning gemmes og udgives først (efter bekræftelse; ny tegning kræver et navn). Efter indsættelse af et symbol vises en opfordring til at opsætte det.
- `frontend/src/pages/Editor.svelte` (Bindinger) — den gamle sektion "Symbol" (ét tag på hele symbolet, v0.27.0) er fjernet fra brugerfladen; sektionen **Symbol** har nu guiden som primær knap ("Opsæt/Ret symbol (6 trin)"), status og **Forklaring**. Bagvedliggende `PUT …/symbols/{element}` med `tag` er uændret i backend (fjernes sammen med den gamle model, når Jan godkender).

## [0.42.0 build 0060] — 2026-10-16 — Slet tegning fra Tegn, med oversigt over hvad der rammes

**Bemærk:** implementeret uden nye tests efter Jans ønske (Jan tester først); kun kompilering er kontrolleret.

- `frontend/src/pages/DrawEditor.svelte` — knappen **Slet tegning** i Tegn; efter sletning åbnes en ny, tom tegning og listen opdateres
- `frontend/src/lib/drawingDelete.ts` (ny) — fælles sletteflow for Tegn og Tegninger: henter hvad sletningen rammer, viser en bekræftelse og sletter; Tegninger-siden bruger nu samme flow
- `backend/app/services/drawings.py` + `api/drawings.py` + `storage/db.py` — `GET /api/drawings/{id}/usage` (tekniker+): antal versioner og bindinger, andre tegninger med en "gå til"-knap hertil (bliver døde), om det er start-tegningen, og brugere med adgang
- Bekræftelsen nævner kun det der rammes; sletning er uændret en kaskade (versioner, bindinger, forklaringer, symbolkonfiguration og brugeradgang slettes med tegningen)

## [0.41.0 build 0059] — 2026-10-16 — Beregning på tekst-bindinger

**Bemærk:** implementeret efter Jans ønske UDEN nye tests — Jan tester først, derefter gennemgås og testes resten (se FEATURES). Kun kompilering/typecheck er kontrolleret.

- `frontend/src/lib/expression.ts` (ny) — lille parser uden `eval`: tal (komma eller punktum), `x`/`værdi`/`parameter` = værdien, `+ - * / %`, parenteser, fortegn og funktionerne abs, round, floor, ceil, sqrt, min, max (flere værdier adskilles med `;`, da komma er decimalkomma); højst 80 tegn; dansk fejltekst ("Ukendt navn …", "Manglende )" …); resultat der ikke er et endeligt tal (fx ÷ 0) = ingen værdi
- `frontend/src/lib/animate.ts` — tekst-animationen beregner udtrykket FØR decimaler og enhed (`x / 10` med 1 decimal: 128 → `12.8`); gælder kun tal, ikke til/fra
- `frontend/src/lib/bindingForm.ts` + `pages/Editor.svelte` — feltet **Beregning** i tekst-animationen med hjælpetekst, fejl vist mens man skriver og i "Vises som"-linjen; ugyldigt udtryk afvises ved gem
- `backend/app/services/expression.py` (ny) + `services/bindings.py` — `TextParams.expression`; serveren parser samme grammatik og afviser ugyldige udtryk ved gem, opret, import og restore (så en tegning aldrig kan indeholde en formel der ikke kan beregnes)

## [0.40.0 build 0058] — 2026-10-14 — Ny hovedmenu: smal topbjælke, menuen foldes ud over tegningen

- `frontend/src/lib/nav.ts` (ny) + `nav.test.ts` — siderne i grupperne Drift / Opsætning / System med rollekrav og ikoner; `navFor(rolle)` (tomme grupper udelades), `pageFor(rute, rolle)` (ikke tilladt/ukendt side → Overview), `groupOf`.
- `frontend/src/App.svelte` — den flade menu (13 sider på én linje, ombrudt til op til 133 px) er erstattet af en topbjælke på 2,5 rem: "Menu"-knap, gruppe › side, alarmtæller, kildekode-link (AGPL §13) og bruger. Menuen foldes ud som et panel *over* indholdet (skubber ikke tegningen ned) med grupperne som kolonner og bruger-delen (skift adgangskode, log ud, version); lukkes ved valg, Escape eller klik udenfor. Sidefoden er fjernet (version står i menuen, kildekode-linket i bjælken). Driftpanel uændret.
- Set i Chromium ved 1440, 1024 og 420 px: bjælken er 37,5 px i alle bredder, ingen vandret rulning, tegningen ændrer ikke størrelse når menuen åbnes, valg og Escape lukker menuen, Bindinger og Tegn har fuld højde. Ved 1024 px er Overview-tegningen 857 × 643 px.

## [0.39.0 build 0057] — 2026-10-14 — Rolle Driftpanel

- `backend/app/services/auth.py` — ny rolle `panel` (Driftpanel) med operatørens rettighedsniveau (`ROLE_LEVEL`; `role_at_least` bruger niveauer i stedet for listeplacering) og begrænsning til udvalgte tegninger som viewer/operatør.
- `frontend/src/lib/api.ts` — `Role` + `roleAtLeast` med samme niveauer som backend.
- `frontend/src/App.svelte` — driftpanel-brugere får kun drifttegningen: ingen topmenu, alarmklokke eller sidefod (efter tvunget skift af adgangskode).
- `frontend/src/pages/Overview.svelte` — driftpanel-tilstand: smal kolonne i venstre side med "Log ud", tegningerne som knapper (kun hvis brugeren har adgang til flere), "Ingen forbindelse" ved afbrudt forbindelse og kildekode-linket (AGPL §13); ingen værktøjslinje; "Tilpas" svæver over tegningen når der er zoomet ind. Fejl- og forbindelsesbeskeder vises stadig.
- `frontend/src/pages/Users.svelte` — rollen kan vælges og begrænses til tegninger; forklaring i rollelisten.
- Tests: `test_scope.py` (driftpanel betjener og kvitterer som operatør, kun i egne tegninger, ingen tekniker-/admin-rettigheder, rolleskift), `api.test.ts` (`roleAtLeast`). PIN-lækagetests søger nu efter koden som selvstændigt tal (se BUGS.md). Set i Chromium ved 1280×800 og 800×1000: ingen topmenu/sidefod, ingen vandret rulning, skift mellem tegninger, log ud; begrænset til én tegning → kun "Log ud"; admin ser stadig den almindelige menu.

## [0.38.1 build 0056] — 2026-10-13 — fix: fund fra gennemgangen af symbolstandardens fase 6–8

- `backend/app/services/symbol_convert.py` — klik-handlinger på dele og "Gå til tegning" er nu "blockers": forslaget er ikke konverterbart, og Konvertér alle viser "kræver manuel handling" med grunden; setpunkt arver taggets `confirm_write`; til/fra-farver ignorerer tærskler (som frontendens `colorFor`); manglende/`None`-parametre giver standardværdien; note når for-/eftertekst ikke kommer med; én `legacy_bindings`-beregning pr. symbol.
- `backend/app/services/symbols.py` — koden kontrolleres med `fullmatch` på præcis 4 ASCII-cifre.
- `frontend/src/lib/SymbolGuide.svelte` — indlæsningsfejl adskilt fra gem/fjern-fejl (kontrollen fortsætter efter en fejl); hver ændring gør ældre kontrolsvar forældede; Gem er spærret mens kontrollen kører.
- Tests: `test_symbol_convert.py` (tab af link/klik → manuel, setpunktets bekræftelse, til/fra-farver), `test_symbol_pin.py` (kodeformat).

## [0.38.0 build 0055] — 2026-10-13 — Symbolstandard fase 8: Konvertér alle (tør-kørsel og rapport)

- `backend/app/services/symbol_convert.py` — `convert_all()`: alle bibliotekssymboler med gamle bindinger på tværs af tegninger → rapport pr. symbol (kan konverteres / konverteret / kræver manuel handling med grund / allerede sat op / ingen bindinger). Tør-kørsel som standard; ved `apply` gemmes kun forslag uden fejl (fejl på ét symbol stopper ikke resten).
- `backend/app/services/svg_sanitize.py` — `symbol_roots()`: bibliotekssymbolerne i en tegning.
- `backend/app/api/symbols.py` — `POST /api/drawings/convert-symbols` (tekniker), audit `symbol.convert_all` ved konvertering.
- `frontend/src/lib/SymbolConvert.svelte` (ny), `frontend/src/pages/Drawings.svelte` — panelet "Symbolstandard: konvertér alle" under Tegninger: Tør-kørsel → rapport med links til symbolerne i Bindinger → "Konvertér N symboler".
- `docs/SYMBOLSTANDARD_IMPLEMENTERING.md` afsnit 11 — Konvertér alle; fjernelse af den gamle model er bevidst ikke udført (kræver godkendelse).
- Tests: `test_symbol_convert.py` (tør-kørsel gemmer intet, apply, manuel ved kun "Gå til tegning", allerede sat op, ukendt tegning). Kontrolleret mod hele biblioteket (82 symboler) i den kørende app: de 7 betjeningssymboler konverteres uden fejl; alle tilladte animationstyper validerer på alle dele. Panelet set i Chromium.

## [0.37.0 build 0054] — 2026-10-13 — Symbolstandard fase 7: nøglelåsens kode

- `backend/app/services/symbols.py` — `set_pin()` (kun symboler med konfiguration; præcis 4 cifre; gemmes som scrypt-hash) og `clear_pin()`; svar kun `has_pin`.
- `backend/app/services/symbol_operate.py` — `reset_pin_fails()`: ny eller fjernet kode ophæver spærring og fejltæller for symbolet.
- `backend/app/api/symbols.py` — `PUT`/`DELETE …/pin` (tekniker, skriv-kun), audit `symbol.pin_set`/`symbol.pin_cleared` (også når koden sættes sammen med konfigurationen) — aldrig koden.
- `frontend/src/lib/SymbolGuide.svelte` — trin 5: "Fjern kode" (med advarsel når der er låste positioner); manglende kode efter fjernelse/gendannelse vises som fejl på trinnet ("sæt en ny kode") og spærrer Gem.
- `docs/SYMBOLSTANDARD_IMPLEMENTERING.md` afsnit 5.4 — reglerne ovenfor.
- Tests: `test_symbol_pin.py` (ny): sæt/skift/fjern, låst uden kode → 409, ny kode ophæver spærring, formatregler, kun tekniker, koden findes ikke i svar, app-log, audit eller backup. Set i Chromium: fjern kode → fejl på trin 5, ny kode → gemt.

## [0.36.0 build 0053] — 2026-10-13 — Symbolstandard fase 6: guiden under Bindinger og Konvertér

- `frontend/src/lib/SymbolGuide.svelte` (ny) — guiden i 6 trin (Symbol, Signaler, Kontakter, Visning, Betjening, Test og gem) som vindue fra "Opsæt symbol (guide)"/"Ret symbol (guide)" under Bindinger: betjeningsform, signaler (kommando, tilbagemelding, sæt/puls med hvileværdi), fejlsignal, positioner, kontaktplaner med skabeloner A–D og eksemplet "7-trins vælger", rækken "Aktive signaler", visning/alarmniveau, animationer pr. del (typer efter delens geometri, kilde = position eller tag, værdier pr. position, "gælder i", ▲▼), bekræftelse, pulslængde, nøglelås med kode (skriv-kun), live-værdier, fundet position og skriveplan pr. position. Valideringen er serverens (`POST …/preview`, kaldt løbende) — fejl vises pr. trin med prik på fanen; Gem er spærret ved fejl eller manglende kode. "Fjern konfiguration" giver symbolets gamle bindinger tilbage.
- `frontend/src/lib/symbolConfig.ts` (ny) + `symbolConfig.test.ts` — datamodel og ren logik: standardværdier, skabeloner A–D, eksemplet dec → bin, positioner tilføjet/fjernet (alle arrays følger med), aktive signaler, cellecyklus, fundet position, skift af betjeningsform, animationstyper efter geometri og standardparametre.
- `frontend/src/pages/Editor.svelte` — afsnittet "Symbolstandard" for grupper og symboler (status + knap til guiden); visningen genindlæses efter gem.
- `backend/app/services/symbol_convert.py` (ny) — Konvertér: forslag til en konfiguration ud fra symbolets bindinger i dag (til/fra → 2 positioner, vælg position → positionerne, puls → trykknap, skriv → setpunkt; farver/tekst/flyt/drej/synlig/blink omsat til værdier pr. position; øvrige følger fortsat deres tag). Gemmes ikke.
- `backend/app/services/drawings.py` — `legacy_bindings()`: symbolets gamle bindinger uanset konfiguration (grundlag for forslaget).
- `backend/app/api/symbols.py` — `GET …/suggest` (tekniker).
- Tests: `test_symbol_convert.py` (ny; forslaget kan gemmes uændret og giver samme visning). Set i den kørende app i Chromium med mock-PLC: omskifter konverteret og gemt, eksemplet 7-trins vælger med tags, låst position uden/med kode, kun visning med Niveau, trykknap, ret eksisterende og fjern.

## [0.35.0 build 0052] — 2026-10-13 — Symbolstandard fase 4–5: Overview og animationer

- `backend/app/services/symbols.py` — `config_bindings()`: symbolets animationer som almindelige bindinger (kilde "position" → pseudo-tag `…:pos` + `params.pos`; "gælder i positionerne" → `params.only` + `pos_tag`; positionsnavne til Værdi); `symbol_view()`: det Overview behøver (betjeningsform, navne, visning, bekræftelse, låste positioner, om kode er sat — aldrig koden).
- `backend/app/services/drawings.py` — `view()` medtager symbolernes bindinger og `symbol_config`.
- `frontend/src/lib/animate.ts` — værdier pr. position (farve, synlig/blink/roterer, Drej-vinkel, Flyt dx/dy, løbelysretning, positionsnavn), "gælder i positionerne" (delen vises som tegnet udenfor), "når ≥ X", blinkfrekvens 0,5/1/2 Hz i takt (fase fra uret, sat kun når blinket starter), ny animation Roterer (`spin`), glidende Flyt/Drej som CSS-transform (kun symbol-animationer på dele uden egen transform).
- `frontend/src/lib/symbolUi.ts` (ny) — klik-regler (`clickAction`, `pickAction`), nøglelås (`needsPin`), knaptekst; `symbolOverlay.ts` (ny) — tilstandsmærke ✓ … ! ?, skygge "PLC: …" ved afvigelse og hængelås i et lag øverst i tegningen.
- `frontend/src/pages/Overview.svelte` — klik på et konfigureret symbol: 2 positioner uden bekræftelse skifter straks; ellers dialog med positioner (nuværende markeret, låste med hængelås), skriveplan fra serveren, kodefelt ved låst position ("Lås op og skift til …"), "Acceptér <PLC'ens position>" ved afvigelse; trykknap og setpunkt. Serverens fejltekst vises uændret.
- `frontend/src/pages/Alarms.svelte`, `app.css`, `api.ts` — prioritet Lav; symbolalarmer viser niveauet (Høj/Medium/Lav) og symbolet.
- `frontend/src/lib/canvas.ts` — `pos_tag` i `bindingTags`; positionens live-værdi sendes til animationerne.
- Tests: `symbolUi.test.ts` (ny), `animate.test.ts`, `canvas.test.ts`, backend `test_symbols.py` (view). Set i den kørende app i Chromium med mock-PLC: vippekontakt glider 0 → 32 på 0,4 s, omskifter med skriveplan, Afvigelse med skygge og alarm "Høj", accept, låst position med forkert/rigtig kode, trykknap, setpunkt med fejl og ok.

## [0.34.0 build 0051] — 2026-10-13 — Symbolstandard fase 3: betjening

- `backend/app/services/symbol_operate.py` (ny) — positionsskift efter skriveplanen (kun signaler der ændres; break-before-make: mod 0/Fra først), stop ved første fejl uden tilbagerulning med præcis besked (skrevet / usikkert pga. timeout / ikke skrevet), pulssignaler med hvileværdi som selvstændige opgaver (hvile skrives også ved afbrudt request og ved timeout på værdien), fejl/låst-tag (aktivt eller ukendt blokerer), komm.fejl blokerer, én betjening ad gangen pr. symbol (409), nøglelås med kode (låst mål eller "kode for at forlade"; 3 forkerte → 60 s spærring pr. symbol og bruger; konstant-tids kontrol), accept af PLC'ens position (skriver intet), trykknap og setpunkt. Audit `symbol.operate/.pulse/.entry/.accept/.unlock/.pin_failed` — aldrig koden.
- `backend/app/services/symbols.py` — `targets()`, `write_plan()`, `needs_pin()` (delt mellem betjening og guidens forhåndsvisning).
- `backend/app/services/operate.py` — `write_value()` og `pulse_value()` (samme omregning, min/max og tag-lås; uden audit, som symbolet logger samlet).
- `backend/app/api/symbols.py` — `GET …/plan/{position}`, `POST …/operate|pulse|entry|accept` (operatør, tegningsadgang), `POST …/preview` (tekniker: validering + skriveplan pr. position uden at gemme).
- `backend/app/services/drawings.py`, `svg_sanitize.py` — gamle bindinger på et konfigureret symbol og dets dele ignoreres (`subtree_ids`).
- `backend/mock_plc/app.py` — testkrog `reject_addr` (afvis bestemte adresser).
- Tests: `backend/tests/test_symbol_operate.py` (ny, 15).

## [0.33.0 build 0050] — 2026-10-13 — Symbolstandard fase 2: position, tilstand og afvigelsesalarm

- `backend/app/services/symbol_runtime.py` (ny) — `remote_position()` (præcis én position hvis alle læsbare planer matcher tilbagemelding/kommando; pulsplaner og "røres ikke" tæller ikke; komm.fejl → ukendt) og `compute_state()` (Remote/Lokal, Venter i valideringstiden, Afvigelse, Ukendt, hængelås) som prototypens `remotePos`/`status`. `SymbolRuntime` genberegner ved hver live-ændring og mindst hvert `SCADA_SYMBOL_TICK_S` (0,5 s), lægger `sym:<tegning>:<element>:pos|remote|state|locked` i live-cachen, gemmer sidst valgte position i `symbol_state` (overlever genstart; første gang = det PLC'en viser) og fjerner pseudo-tags for slettede symboler. Genindlæser ved ændrede konfigurationer eller tegningsversioner.
- `backend/app/services/alarms.py` — eksterne alarmkilder (`providers`) med egen prioritet og "frosne" tags; prioritet `low`; sortering Høj → Medium → Lav; ændret prioritet slår igennem på en aktiv alarm.
- `backend/app/main.py`, `backend/app/config.py` — runtime startes og leverer afvigelsesalarmer (Lokal + alarm valgt), med symbolets navn i teksten ("Vælger V1: valgt 6, PLC viser 3"). Komm.fejl fryser alarmen.
- Tests: `backend/tests/test_symbol_runtime.py` (ny, 15): alle 7 positioner i dec→bin, registerskabelon, pulsplaner, tidslinjer Lokal/Remote, pseudo-tags mod mock-PLC, alarm med valgt niveau og genstart, frosset alarm, fjernede pseudo-tags.

## [0.32.0 build 0049] — 2026-10-13 — Symbolstandard fase 1: konfiguration og validering

- `backend/app/storage/db.py` — skema 11: tabellerne `symbol_config`, `symbol_pins` (kun scrypt-hash), `symbol_state`; metoder til dem; backup-eksport af konfigurationerne (aldrig koder eller tilstand), restore lægger dem ind igen.
- `backend/app/services/symbols.py` (ny) — skema (positioner, signaler, kontaktplaner, visning, alarmniveau, bekræftelse, lås, animationer) og validering pr. trin efter prototypens regler: skrivbare tags, ét tag pr. signal, samme type på tilbagemelding, ét signal pr. plan, unikke kontaktmønstre, register-celler inden for tagets min/max ellers datatypens område og præcist skrivbare, puls med påkrævet hvileværdi, mindst ét læsbart plan, trykknap/setpunkt/visning, animationer mod delens geometri (Niveau → rect, Værdi → text, Løbelys → streger/rør), værdier pr. position, retnings-tag, nøglelås kræver kode. Advarsler blokerer ikke. `config_tags()` og pseudo-tag-navne (`sym:<tegning>:<element>:pos|remote|state|locked`).
- `backend/app/api/symbols.py` (ny) — `GET/PUT/DELETE /api/drawings/{d}/symbols/{e}/config`; PUT tager valgfri `pin` (gemmes kun som hash; svar siger kun `has_pin`); fejl med `steps` pr. trin og `warnings`.
- `backend/app/services/svg_sanitize.py` — `describe_element()` (dele, elementtyper, data-hv-type/-pid).
- `backend/app/services/errors.py`, `backend/app/api/errors.py` — ServiceError kan bære ekstra felter i svaret.
- `backend/app/services/scope.py` — begrænsede brugere ser også symbolernes tags og pseudo-tags.
- `backend/app/services/tags.py` — et tag der bruges af en symbol-konfiguration kan ikke slettes.
- `backend/app/services/backup.py` — validerer symbol-konfigurationer ved restore (skema + tags findes).
- `frontend/svgedit-host/scada-editor.js` — indsatte symboler får `data-hv-type` og delene `data-hv-pid`.
- Tests: `backend/tests/test_symbols.py` (ny, 42), `test_scope.py`.
- `docs/SYMBOLSTANDARD_IMPLEMENTERING.md` — validering mod geometri i stedet for bibliotekets meta.

## [0.31.4 build 0048] — 2026-10-13 — fix: live-forbindelsen følger sessionen og tegningsadgangen

- `backend/app/api/live_ws.py` — `revalidate()` hvert `ws_revalidate_s` og ved hver subscribe: ugyldig session → fejlbesked + luk 4401; ændret rolle/tegningsadgang → genberegn synlige tags, nyt snapshot og alarmer. Klientens ønskede tags huskes, så adgangen kan udvides uden ny subscribe.
- `backend/app/config.py` — `SCADA_WS_REVALIDATE_S` (standard 10 s).
- `backend/tests/test_scope.py` — åben WebSocket får nyt snapshot ved udvidet tegningsadgang og lukkes med 4401 ved deaktivering; læsninger med tidsgrænse, så en manglende besked fejler i stedet for at hænge.

## [0.31.3 build 0047] — 2026-10-13 — fix: live-ændringer går ikke tabt hos langsomme klienter

- `backend/app/services/live_cache.py` — `update`: fuld klient-kø → alle ventende deltaer flettes til én (seneste værdi pr. tag), i stedet for at den ældste smides væk.
- `backend/tests/test_live_cache.py` (ny) — kun ændringer publiceres; fuld kø bevarer første ændring og seneste værdi; andre abonnenter er upåvirkede.

## [0.31.2 build 0046] — 2026-10-13 — fix: toggle er atomisk og bruger PLC'ens aktuelle værdi

- `backend/app/services/operate.py` — `write(toggle=True)`: værdien læses frisk fra PLC'en under tag-låsen, og den nye værdi beregnes derfra; `toggle()` bruger den. min/max-tjek flyttet til `_check_limits()` (samme regel for write og toggle). Svaret på write er uændret; toggle returnerer fortsat `from`.
- `backend/tests/test_operate.py` — to samtidige toggles giver til→fra; toggle går ud fra PLC'en når cachen er bagud.

## [0.31.1 build 0045] — 2026-10-13 — fix: puls efterlader aldrig udgangen tændt

- `backend/app/services/operate.py` — `pulse`: ved `PlcUnreachable` på TÆND (udfald ukendt) sendes SLUK alligevel; fejlbesked "Puls kunne ikke bekræftes (udgangen er sat til fra for en sikkerheds skyld)" eller ADVARSEL hvis SLUK også fejler; audit-detalje `on_result`. Eksplicit afvisning fra PLC'en (fx 409) sender ingen SLUK.
- `backend/mock_plc/app.py` — testkrog `slow_writes`/`slow_write_s`: skrivningen udføres, svaret forsinkes (tabt svar).
- `backend/tests/test_operate.py` — puls ved timeout på TÆND nulstilles; puls afvist af PLC'en sender intet ekstra.

## [0.31.0 build 0044] — 2026-10-13 — Løbelys: retning fra et andet tag

- `backend/app/services/bindings.py` — `FlowParams.dir_tag` og `binding_tags()` (bindingens tag + evt. retnings-tag), brugt alle steder der samler en bindings tags:
  - `drawings.py` — retnings-tagget skal findes og være et andet end start/stop-tagget; tag-metadata i `view()` medtager det.
  - `scope.py` — begrænsede brugere får live-værdien (adgang pr. tegning).
  - `backup.py` — import afvises hvis retnings-tagget mangler.
  - `storage/db.py` — `count_bindings_for_tag` tæller også `params.dir_tag`, så tagget ikke kan slettes mens det bruges.
- `frontend/src/lib/canvas.ts` — `bindingTags()`; `byTag()` indekserer under begge tags, så en ændring på retnings-tagget gentegner løbelyset; `renderBinding` sender retningens live-værdi med.
- `frontend/src/lib/animate.ts` — `withDirection()`: Fra = som valgt, Til = modsat, ukendt = stop.
- `frontend/src/pages/Editor.svelte`, `frontend/src/lib/bindingForm.ts` — "Retning styres af (valgfrit)" med tag-vælgeren; preview abonnerer også på retnings-tagget. Afkrydsningsfelterne står på hver sin linje.
- Tests: `withDirection`, løbelys i DOM med retnings-tag, `bindingTags`/`byTag`, formular; backend: validering, metadata, tag-sletning blokeret, adgang pr. tegning, backup-import.
- `docs/prototyper/symbolguide.html`, `docs/SYMBOLSTANDARD.md` — samme valg i prototypen (demo-tag `Demo_retning`); prototypens tag-lister medtager også retnings-tagget.
- Set i den kørende app i Chromium med mock-PLC: rør og T-stykke (op ind) med Pumpe (coil 5) og Retning (coil 6) — Retning fra/til vender lyset, Pumpe fra stopper.

## [0.30.0 build 0043] — 2026-10-13 — Løbelys i T-stykke og kryds

- `backend/app/services/bindings.py` — `FlowParams.arm` ('' | left | right | up | down) og `arm_flow` (in | out).
- `frontend/src/lib/animate.ts` — `segmentsOf()` (lige linjestykker fra path M/L/H/V/Z inkl. relative, line, polyline, polygon, rect), `junctionArms()` (krydspunkt + rør), `armName()` (rørets retning på skærmen via elementets CTM, så roterede/spejlede symboler følger det man ser) og `armFlowsOut()`. Med valgt rør tegnes én lys-linje pr. rør fra krydspunktet: det valgte løber ind/ud, de øvrige modsat; "tilbage" vender alt. Findes røret ikke, eller har elementet buer, falder lyset tilbage til tegneretningen med en advarsel.
- `frontend/src/lib/bindingForm.ts`, `frontend/src/pages/Editor.svelte` — "T-stykke/kryds: valgt rør" og "Det valgte rør løber ind/ud".
- Tests: krydspunkt/rør for kryds og T-stykke, relative paths, buer/parallelle, skærmretning ved rotation og spejling, ind/ud-logik, kryds og T-stykke i DOM inkl. kode 2, manglende rør (`animate.test.ts`); formular (`bindingForm.test.ts`); backend-validering.
- `docs/prototyper/symbolguide.html`, `docs/SYMBOLSTANDARD.md` — samme valg i prototypen og standarden.
- Set i den kørende app i Chromium: kryds (venstre ind), T-stykke (op ud) og T-stykke roteret 90° (højre ind) — retninger målt pr. rør i skærmkoordinater, også ved kode 2 og 0.

## [0.29.0 build 0042] — 2026-10-13 — Ny animation: Løbelys

- `backend/app/services/bindings.py` — ny animationstype `flow` med `FlowParams` (mode onoff/signed/code, reverse, invert, base, light, speed 5–500, dash 2–200; farver valideres som de øvrige).
- `frontend/src/lib/animate.ts` — `flowState()` (tagværdi → frem/tilbage/stop) og løbelyset: røret får farve 1, og et lag med en stiplet kopi af hver streg (et lige rør/rect får en streg ad midterlinjen) løber via Web Animations (startTime 0, så alle løbelys er i takt). Laget genskabes kun når tilstanden ændres, så animationen ikke hopper ved hver live-opdatering. Ukendt værdi/kommunikationsfejl = stop. Ingen id'er i kopien; `pointer-events: none`. Advarsel på elementer uden streg.
- `frontend/src/lib/bindingForm.ts`, `frontend/src/pages/Editor.svelte`, `frontend/src/lib/api.ts` — Løbelys i binding-editoren: styring (til/fra, fortegn, kode), to farver, hastighed, streglængde, vend retning, omvendt; danske fejlbeskeder (fx ens farver).
- Tests: `animate.test.ts` (tilstande, lag på rect/gruppe, stop, ingen genskabelse, ukendt værdi, advarsel), `bindingForm.test.ts` (standard, validering, round-trip), `backend/tests/test_drawings_api.py` (validering og standardparametre).
- `docs/RESEARCH_OG_DESIGN.md` — `flow` i animationstabellen.
- Set i den kørende app i Chromium med mock-PLC: lige rør, bøjning 90°/45° og T-stykke løber, kode 2 vender retningen, fra/0 stopper.

## [0.28.2 build 0041] — 2026-10-13 — fix: Bøjning 45° har lige lange ben

- `frontend/src/lib/symbols.ts` — Bøjning 45°: knækpunkt (45,45), begge ben 45 lange som på Bøjning 90°, T-stykke og kryds (før 30 og ca. 42); stadig radius 20.
- `frontend/src/lib/symbols.test.ts` — test af at alle ben på bøjninger, T-stykke og kryds er 45 fra midtpunktet.
- `docs/prototyper/symbolguide.html` — indlejret symbolbibliotek opdateret.

## [0.28.1 build 0040] — 2026-10-13 — fix: rør og fittings ens tykke i paletten, rund 45°-bøjning

- `frontend/src/lib/symbols.ts` — `PIPE_IDS` og `previewViewBox()`: rør og fittings får samme målestok i forhåndsvisningen (før blev hvert symbol skaleret efter egen størrelse, og stregen blev klippet fordi getBBox ikke medregner den). Rør (vandret/lodret) 160 → 90 lange som udgangspunkt. Bøjning 45° tegnet med bue (radius 20) i stedet for knæk; enderne ligger samme sted.
- `frontend/src/pages/DrawEditor.svelte` — forhåndsvisningen bruger `previewViewBox`.
- `frontend/src/lib/symbols.test.ts` — tests af målestok, centrering og bøjninger.
- `docs/prototyper/symbolguide.html` — indlejret symbolbibliotek opdateret.

## [0.28.0 build 0039] — 2026-10-13 — Trykknap (puls) ligner en trykknap

- `frontend/src/lib/symbols.ts` — Trykknap (puls) tegnet om fra en flad rektangel-knap til en tavlemonteret trykknap set forfra: frontplade 76×76, metalkrave, rund knap (`flade`, samme fyld-binding som før) med glans, og et skilt (`tekst`) med "Start" under. Bindinger (`click:pulse`, fyld) er uændrede. Set i Chromium.
- `docs/prototyper/symbolguide.html` — det indlejrede symbolbibliotek opdateret.

## [0.27.1 build 0038] — 2026-10-13 — fix: elmåler har plads til 5 cifre

- `frontend/src/lib/symbols.ts` — Elmåler (kWh): hus 90 → 130 bredt, display 70 → 110, tallet højrestillet ved x=114, "kWh" centreret; plads til fx "12345.6 kWh" (før løb et 5-cifret tal med decimal ud over displayet). Set i Chromium.

## [0.27.0 build 0037] — 2026-10-09 — Al symbol-konfiguration samlet under Bindinger

**Bemærk:** implementeret efter Jans ønske UDEN nye tests og uden browser-/PLC-test — Jan tester først, og først derefter gennemgås og testes resten (se FEATURES). Eksisterende tests er ikke kørt for dette commit ud over frontendens enhedstests (115 består) og at backend kan importeres.

**Ny arbejdsdeling:** i **Tegn** tegnes og *navngives* kun (symbolets navn er dets identitet, unikt); **tag, forklaring og animationer sættes udelukkende under Bindinger**.

- `frontend/src/pages/DrawEditor.svelte` + `svgedit-host/scada-editor.js` — Tegn har ikke længere tag-valg, betjeningssymbol-hjælp og forklaring; kun **Navn** (unikt — "bruges allerede" afvises), "Konfigurér under Bindinger"-link (åbner symbolet direkte, når tegningen er gemt) og id under "Avanceret"; indsatte symboler får et unikt navn automatisk ("Vippekontakt", "Vippekontakt 2" …) via `uniqueName()`
- `backend/app/services/drawings.py` + `api/drawings.py` — `PUT /api/drawings/{id}/symbols/{element}` (tekniker+, audit `drawing.symbol`): `{description}` gemmer forklaringen, `{tag}` tilknytter et tag til hele symbolet — serveren danner bindingerne (klik på roden, visning på delene) ud fra symbolets egen beskrivelse og erstatter symbolets eksisterende bindinger i én transaktion; `{tag: null}` fjerner dem; ikke-skrivbart tag giver visning uden klik-handling og en klar advarsel; samme valideringsregler som manuelle bindinger (`_normalize_bindings`)
- `backend/app/storage/db.py` — skema 10: tabellen `symbol_meta` (forklaring pr. tegning og element; slettes med tegningen); `set_symbol_bindings()` (flere elementer atomisk); med i backup/restore (`symbol_meta`, valideret; ældre backups uden er fortsat gyldige)
- `view` leverer `symbols` (forklaringer); Overview og Bindinger viser dem som tooltip — forklaringen kan ændres uden ny tegningsversion; en ældre forklaring i selve tegningen bruges som reserve
- `frontend/src/pages/Editor.svelte` (Bindinger) — listen viser som standard kun **navngivne symboler, elementer med bindinger og alt under et symbol** (plus forfædre som kontekst); "Vis alle elementer" viser resten; ved et valgt symbol: sektionen **Symbol** med tag (kun skrivbare, hvis symbolet betjener PLC'en), "Fjern tag", forklaring og besked om hvad der blev oprettet; delene kan stadig finjusteres enkeltvis
- `frontend/src/lib/elementTree.ts` — `relevantElements()`, `spec`/`writes` pr. element

## [0.26.0 build 0036] — 2026-10-09 — Symboler med flere elementer: træ, navn og forklaring

- `frontend/src/lib/elementTree.ts` — elementlisten som træ: forælder/dybde via nærmeste forfader med id, sammenfoldning, søgning (id, label, navn, forklaring) der viser forfædre som kontekst, antal elementer under et sammenfoldet symbol, korte navne på et symbols dele (`tekst` i stedet for `vippekontakt_tekst`), standard: rene grupper foldet ud og symboler foldet sammen
- `frontend/src/pages/Editor.svelte` (Bindinger) — elementlisten er et træ med indrykning og fold-ud-knapper ("Fold alle ud" / "Fold alle sammen" / "Standard"); symboler vises med deres navn i fed og id som sekundær; det valgte element viser navn, forklaring og "Del af <symbol>"; det valgte elements forældre foldes ud automatisk
- `frontend/src/pages/DrawEditor.svelte` + `svgedit-host/scada-editor.js` — felterne **Navn** (højst 60 tegn) og **Forklaring** (højst 500 tegn) på det valgte element, gemt i tegningen som `data-hv-name`/`data-hv-desc` med fortryd; tomme felter gemmes ikke; indsatte symboler får deres navn automatisk (`withName`)
- `frontend/src/lib/canvas.ts` — navn og forklaring vises som tooltip (`<title>`) på Overview og i Bindinger (ikke på tekst-elementer, hvis tekst en tekst-binding overskriver)
- `backend/app/services/svg_sanitize.py` — `data-hv-name`/`data-hv-desc` er ren tekst og bevares (også med fx "Måledata:" i teksten, som ellers ramte "data:"-filteret), længdegrænser 60/500 med rapport; øvrige data-attributter kontrolleres som før
- Tests: `elementTree.test.ts` (8), `symbols.test.ts` (+2), `canvas.test.ts` (+2), `test_svg_sanitize.py` (+3) — 272 backend, 115 frontend
- Verificeret i browser: symbol indsat med navn, navn og forklaring sat i Tegn og gemt (overlever SVG-Edit og serverens sanering), Bindinger-træet sammenfoldet/udfoldet med indrykning, søgning på forklaring, "Del af"-link, tooltips på Overview; Jans store Varme-tegning (311 elementer) vises som træ

## [0.25.1 build 0035] — 2026-10-09 — fix: eksterne tags blev overskrevet af PLC'ens egne SSE-hændelser

- `backend/app/services/plc_runtime.py` — `_on_sse_register()` opdaterer kun tags på PLC'ens egne registre (`source.is_register`); et eksternt tag med samme type/adresse (fx `plc1:mbx:1:D:1:coil:0` vs. `plc1:coil:0`) blev før overskrevet ved hver SSE-hændelse
- `backend/tests/test_ext.py` — regressionstest

## [0.25.0 build 0034] — 2026-10-09 — Tags fra eksterne Modbus-enheder (PLC /api/ext)

- `backend/app/services/tagsource.py` — nye kilder `plcN:rtu:<slave>:<type>:<adresse>[:datatype]` (RS485-slave 1-247) og `plcN:mbx:<board>:<kanal A-H|1-8>:<slave>:<type>:<adresse>[:datatype]` (expansion board); adresse 0-65535; samme datatyper og 32-bit-regler som interne
- `backend/app/plc/client.py` — `read_ext()` (count ≤ 16, `max_age`, valgfri `wait`; værdi + status pr. adresse) og `write_ext()` (med `wait`; `ok`/`timeout`/`queued` returneres, slavens `error` kastes; 502/504-svar med resultat læses i stedet for at kaste); fejltekster fra /api/ext-svar uden "error"-felt er læsbare
- `backend/app/plc/planner.py` — `plan_ext_reads()`: kun ægte sammenhængende adresser samles (højst 16), pr. (bus, board, kanal, slave, type)
- `backend/app/services/plc_runtime.py` — eksterne tags polles hvert `SCADA_POLL_EXT_S` (standard 2 s) uden `wait` med `max_age` = intervallet; `pending` = "venter på første svar" (sidste kendte værdi bevares), slavens `error` og PLC-fejl for ét område (404 board ikke konfigureret, 409 Modbus Master fra, 502) markerer KUN de berørte tags — resten af PLC'en kører videre
- `backend/app/services/operate.py` — skrivning til eksterne slaver med bekræftelse; ikke bekræftet (`timeout`/`queued`) afgøres ved tilbagelæsning (`max_age=0`, `wait`), ellers fejl med klar besked; `slave_result` i audit
- `backend/app/plc/sse.py` — SSE-overvågning af HR 0-255 og IR 0-319 (PLC v7.9.68.124+, BUG-486); ældre firmware ses i `connected.watching` og polles som før
- Frontend: Tags-hjælpeteksten forklarer de tre kilder; mærkerne "Extern (RS485)"/"Expansion board" i tag-listen og tag-dropdowns
- Tests: `test_ext.py` (22: kilder, planlægger, klient mod ÆGTE PLC1-svar via transport, poll-logik med pending/fejl-isolering/interval, ikke-bekræftet skrivning) — ingen ændringer i mock-PLC'en (efter Jans ønske); SSE/runtime-tests tilpasset de nye grænser — 268 backend, 103 frontend
- **Verificeret mod den rigtige PLC1 (10.1.1.30, v7.9.68.125) via testserveren:** RS485-slave 90 HR 0-1 læses (235/236) i ét kald; slave 247 (findes ikke) → fejl kun på sit tag, resten af PLC'en "ok"; expansion board 1 kanal D slave 1 coil 0 læst og skiftet 6 gange Til/Fra med korrekt tilbagelæsning, slutter på udgangsværdien. To PLC-firmwarefund beskrevet i HYPERVISIONPLC_ANALYSE.md §7.3

## [0.24.0 build 0033] — 2026-10-09 — Omskifter med valgfrit antal positioner

- `backend/app/services/bindings.py` — ny klik-handling `click:select` (`SelectParams`: 2-8 positioner med værdi og navn, forskellige værdier, valgfri bekræftelse og titel); tæller som skrivende klik (kræver skrivbart tag)
- `backend/app/services/scope.py` + `api/operate.py` + `services/operate.py` — operatørrettigheder pr. handling: skriv kræver setpunkt-felt eller omskifter (med kun omskifter: kun dens positioner), til/fra kræver til/fra, puls kræver puls; afvisninger logges i audit
- Frontend: "Klik: vælg position" i binding-editoren (positioner med værdi/navn, + Position, bekræftelse, titel); Overview-dialog med én knap pr. position, aktiv position markeret, bekræftelse "Sæt X til 'Auto'?", besked med positionens navn
- `frontend/src/lib/symbols.ts` — `selectorSymbol()` bygger en omskifter med de angivne navne rundt om grebet (2-8 positioner, symmetrisk fordelt, værdier 0, 1, 2 …); greb med "Rotation" til den aktive position; fast symbol "Omskifter Hånd/0/Auto" og felt i Tegn til "Omskifter med egne positioner"
- Tests: `test_operate.py` (2 nye: rettigheder pr. handling, omskifter kun egne positioner), `symbols.test.ts` (3), `bindingForm.test.ts` (2), `actions.test.ts` (1) — 248 backend, 102 frontend
- Verificeret i browser: omskifter "1, 2, 3, 4" indsat i Tegn og bundet til et tag, Overview-dialog med 4 knapper, valg af "3" → register = 2 og grebet drejet til 22,5°; Hånd/0/Auto → Auto = 2; for få positioner afvises med besked

## [0.23.1 build 0032] — 2026-10-08 — Fix: tal i fejlbeskeder uden ".0"

- `backend/app/services/operate.py`, `services/tags.py` — min/max- og alarmgrænse-beskeder formaterer tal som tastet ("maksimum 100", ikke "100.0"); ugeprogrammer gjorde det allerede
- `tests/test_operate.py` — 1 ny test af de præcise beskeder — 246 backend

## [0.23.0 build 0031] — 2026-10-08 — Tags: fast redigeringspanel

- `frontend/src/pages/Tags.svelte` — redigeringspanelet er `position: sticky` øverst (højst 60 % af skærmhøjden, egen scroll), Gem/Annullér og fejlbeskeden står fast i bunden af panelet, og den redigerede række markeres i listen
- Verificeret i browser ved 1400×900 og 390×844 med 40 tags: Redigér på tag 35 → panelet står øverst, bliver stående ved videre scroll, knapperne er synlige, Gem virker

## [0.22.0 build 0030] — 2026-10-08 — Ugeprogrammer

- `backend/app/services/schedule_engine.py` — ren beregning: perioder pr. ugedag (også over midnat, 24:00 som slut), senere periode vinder, undtagelser pr. dato (tom værdi = standard), standardværdi; skift og ugeoversigt; lokal tid (`SCADA_TZ`, standard Europe/Copenhagen) så 06:00 er 06:00 året rundt
- `backend/app/services/schedules.py` — validering (skrivbart tag, min/max, til/fra-tags kun Til/Fra, klokkeslæt, datoer, højst 50 perioder/100 undtagelser) brugt af både API og backup-restore; afvikling hvert 15. s: skriver ved skift og kun hvis PLC'en ikke allerede har værdien (manuel overstyring holder til næste skift), gennem `OperateService` (min/max, tilbagelæsning, audit som "ugeprogram:<navn>"); fejl vises og prøves igen efter 60 s
- `backend/app/api/schedules.py` — `GET/POST /api/schedules`, `PUT/DELETE /api/schedules/{id}`, `POST /api/schedules/preview` (tekniker+, audit)
- Skema 9: tabellen `schedules`; med i backup (valideret med samme regler) og restore
- Tags: et tag der bruges i et ugeprogram kan ikke slettes eller gøres ikke-skrivbart
- Trend-CSV skriver nu dansk tid (`SCADA_TZ`) uanset serverens tidszone (en Pi står ofte på UTC); energi bruger samme tidszone
- Frontend: side **Ugeprogrammer** (tekniker/admin): liste med nu/næste skift/status/fejl og ugeoversigt; formular med ugedage + genveje (Hverdage/Weekend/Alle), tider, værdier (til/fra som Til/Fra), undtagelser og live forhåndsvisning beregnet af serveren
- Tests: `test_schedule_engine.py` (8: perioder, over midnat, prioritet, undtagelser, sommertid, ugeoversigt), `test_schedules.py` (16: validering, beskyttede tags, skrivning ved skift, manuel overstyring, ingen skrivning når værdien findes, fejl + gentagelse, slået fra, kun tekniker, backup) — fandt før release at backup-validering af ugeprogrammer lå efter fejl-kontrollen; `scheduleUi.test.ts` (6) — 245 backend, 96 frontend
- Verificeret i browser og i realtid mod mock-PLC: formular, valideringsfejl i forhåndsvisning, undtagelse, afvikling skrev 21,5 °C og pumpe Til, audit viser "ugeprogram:<navn>"

## [0.21.0 build 0029] — 2026-10-08 — Energirapporter

- `backend/app/services/energy.py` — perioder (dag/uge/måned) i dansk tid inkl. sommertid; tæller: summen af stigninger (fald = nulstilling → tæller fra 0, huller springes over); effekt: integration med værdien holdt til næste måling, højst 10 min og aldrig efter "nu"; huller tæller som 0; omregning til kWh pr. tag
- `backend/app/api/energy.py` — `GET /api/energy/tags`, `/report` (standard: seneste 14 dage / 12 uger / 12 måneder), `/export` (CSV til dansk Excel med I alt-række); adgang pr. tegning respekteres
- Tags: felterne `energy` (tæller/effekt) og `energy_factor` — skema 8; valideret i alle grene (opret, opdatér — også når historikken slås fra —, import, backup): kræver historik og et tal-tag
- `backend/app/storage/trends_db.py` + `services/trends.py` — energi-tags slettes først efter `SCADA_ENERGY_DAYS` (standard 400), anden historik efter `SCADA_TREND_DAYS`; `samples_with_prev()` giver tællerens udgangspunkt før perioden
- `requirements.txt` — `tzdata` (Apache-2.0) så dansk tid virker overalt
- Frontend: ny side **Energi** (periodeknapper, valg af tags, grupperede søjler med faste farver, tabel med I alt, igangværende periode markeret, CSV); energi-felter i Tags-redigering med forklaring af omregning
- Tests: `test_energy.py` (7: sommertid, uge/måned, tæller med nulstilling og huller, effekt med hold/huller/periodegrænser, faktor), `test_trends.py` (3 nye), `energyData.test.ts` (5) — 220 backend, 90 frontend
- Verificeret i browser med 14 dages genereret historik (indlæst via flet): dag/uge/måned, tabel, CSV, mobil uden vandret scroll; energi sat via Tags-siden

## [0.20.1 build 0028] — 2026-10-08 — Fix: rigtige fejlbeskeder ved indlæsning af historik gennem nginx

- `deploy/nginx-hypervisionplc-scada.conf` — indlæsnings-adressen mellemlagrer igen uploadet (fjernet `proxy_request_buffering off`), så tjenestens fejlbeskeder når frem i stedet for 502
- Verificeret på testserveren: 70 MB gennem nginx → 401 fra tjenesten (andre adresser stadig max 64 MB → 413); øjebliksbillede som tjenestens bruger `scada` af den rigtige historik (12 tags, 11.141 værdier)

## [0.20.0 build 0027] — 2026-10-08 — Backup af trend-historik

- `backend/app/storage/trends_db.py` — `snapshot()` (SQLites backup-API på en separat forbindelse — blokerer ikke opsamlingen), `check_file()` (er det en trend-historik? quick_check), `merge_from()` (flet tag for tag; tags matches på navn; eksisterende (tag, tidspunkt) bevares — intet overskrives)
- `backend/app/services/backup.py` — komprimeret øjebliksbillede (`trends-auto-*.db.gz`) ved hver automatisk backup, de seneste `SCADA_TREND_BACKUP_KEEP` (standard 2) gemmes og vises i fillisten som "historik"; indlæsning af .db eller .db.gz (højst 2 GB udpakket)
- `backend/app/api/backup.py` — `GET /api/backup/trends` (download) og `POST /api/backup/trends/merge` (upload streames til disk, højst 1 GB); admin; audit
- `deploy/nginx-hypervisionplc-scada.conf` — egen location til indlæsning: 1 GB, ingen mellemlagring, 15 min timeout
- `frontend/src/pages/Backup.svelte` — sektion "Trend-historik" (hent, indlæs og flet, resultat); `lib/api.ts` sender filer (Blob) uændret
- Tests: `test_trends.py` (2 nye: download → ændret fil → flet bevarer eksisterende værdier, ukomprimeret/ugyldig fil; øjebliksbilleder på serveren og oprydning), `api.test.ts` (1 ny) — 211 backend, 85 frontend
- Verificeret i browser lokalt og på testserveren gennem nginx og den sandkassede systemd-tjeneste

## [0.19.0 build 0026] — 2026-10-08 — Betjeningssymboler

- `frontend/src/lib/symbols.ts` — ny sektion "Betjening (skriver til PLC)": trykknap (puls 500 ms), start/stop (til/fra med bekræftelse, lampe + status), vippekontakt (til/fra, vippen flytter sig), drejeomskifter 0/1 (grebet drejer ±45°), auto/manuel, setpunkt-felt (klik → indtast værdi). Symbolerne beskriver selv deres bindinger: `data-hv-auto` (klik-handling på roden) og `data-hv-part` (visning på delene)
- `backend/app/services/svg_sanitize.py` — `symbol_specs()` finder betjeningssymboler og deres dele
- `backend/app/services/bindings.py` — `symbol_bindings()`: bindinger ud fra symbolets beskrivelse, valideret som alle andre bindinger; ugyldige/ukendte udelades, "gå til" aldrig; klik-handlinger der skriver dannes kun for skrivbare tags
- `backend/app/services/drawings.py` — automatisk binding bruger symbolets beskrivelse når elementets id/label er et tag
- `backend/app/services/scope.py` — operatørers betjeningsret ud fra de *effektive* bindinger (også betjeningssymbolernes) — fundet af testen før release: uden rettelsen fik operatører "ingen adgang"
- `frontend/src/pages/DrawEditor.svelte` + `svgedit-host/scada-editor.js` — ved et betjeningssymbol vises kun skrivbare tags og en forklaring; advarsel hvis tagget ikke er skrivbart
- Tests: `test_drawings_api.py` (2 nye: bindinger for skrivbart/ikke-skrivbart tag, ugyldige beskrivelser, operatør kan betjene), `symbols.test.ts` (1 ny) — 209 backend, 84 frontend
- Verificeret i browser hele vejen: symboler indsat i Tegn, tag valgt, gemt (`data-hv-*` overlever SVG-Edit og serverens sanering) → Overview: vippekontakt skifter coil og vippen flytter sig, drejeomskifter spørger og drejer, setpunkt-felt skriver værdien

## [0.18.1 build 0025] — 2026-10-08 — Fix: historik kan slås fra og slettes fra Trends

- `frontend/src/pages/Trends.svelte` — "Administrér" (tekniker/admin): pr. tag "Gem"/"Stop" (tagets historik-felt; det gemte bevares) og "Slet" (med bekræftelse og antal værdier); besked efter handlingen
- `backend/app/api/trends.py` — `DELETE /api/trends/history/{navn}` (tekniker+, audit `trend.delete`) — slår ikke opsamlingen fra
- `backend/app/services/trends.py` — `TrendRecorder.forget()` sletter også værdier i bufferen, så de ikke dukker op igen
- `backend/app/services/tags.py` + `main.py` — `on_change`: opsamleren læser historik-indstillingerne straks ved oprettelse/ændring/import (før: ved næste skrivning, op til 5 s); sletning af et tag går nu også gennem `forget`
- Tests: `test_trends.py` (2 nye; CSV-testen venter nu på den forventede værdi, fordi opsamlingen starter straks) — 207 backend
- Verificeret i browser med driftens skriveinterval (5 s): Stop → gemmes ikke mere, kan stadig vises; Slet → 0 værdier, også efter en hel skrivecyklus

## [0.18.0 build 0024] — 2026-10-08 — Overview: zoom/panorering og start-tegning

**Start-tegning:**
- `backend/app/storage/db.py` — indstillinger i den eksisterende `meta`-tabel (`get_setting`/`set_setting`, én række pr. nøgle — ingen skemaændring); start-tegningen med i projekt-eksport og i restore-transaktionen
- `backend/app/services/drawings.py` + `api/drawings.py` — `PUT /api/drawings/start` (tekniker+, audit `drawing.start`), `start`-flag i tegningslisten; ukendt tegning afvises (404), slettes start-tegningen nulstilles valget
- `backend/app/services/backup.py` — start-tegningen med i backup (valgfri ved restore; peger den på en tegning der ikke er i backuppen, ignoreres den)
- `frontend/src/pages/Drawings.svelte` — "Start"-mærke og "Gør til start"/"Fjern som start"
- Overview åbner: tegningen i adressen → den sidst viste i denne fane → start-tegningen → den første (`pickDrawing`); brugere med adgang til udvalgte tegninger får kun tegninger de må se

**Zoom og panorering** (`frontend/src/lib/viewport.ts` + `pages/Overview.svelte`):
- Musehjul zoomer om musens position, knapperne − / + / Tilpas og zoom-procent i værktøjslinjen, træk for at panorere, knib med to fingre på touch; højst 20×, aldrig ud forbi hele tegningen og aldrig ud over kanten
- Et træk/knib udløser ikke klik-handlinger i tegningen; et almindeligt klik gør stadig

- Tests: `viewport.test.ts` (6 nye), `test_drawings_api.py` (2 nye), backup-roundtrip omfatter start-tegningen — 83 frontend, 205 backend
- Verificeret i browser: ny fane åbner start-tegningen, sidst viste huskes efter besøg på Tags; hjul-zoom om musen, træk over en klikbar knap panorerer uden dialog, klik åbner dialogen, Tilpas nulstiller; ingen side-scroll. Knib er kun testet via logikken (ingen touch-enhed i testen)

## [0.17.0 build 0023] — 2026-10-08 — Animation "Flyt"

- `backend/app/services/bindings.py` — ny animation `move` (`MoveParams`: min/max for værdien, `dx`/`dy` = forskydning ved max, ±100000)
- `frontend/src/lib/animate.ts` — Flyt forskyder elementet `translate(f·dx f·dy)`; Flyt og Rotation gemmer hver sin del af transform og sammensættes som original + flyt + rotation, så de kan kombineres på samme element; afrundede værdier i transform
- `frontend/src/lib/bindingForm.ts` + `src/pages/Editor.svelte` — "Flyt" i animationslisten med felterne "Flyt X/Y ved max"; begge 0 afvises
- Tests: `animate.test.ts` (2 nye), `bindingForm.test.ts` (1 ny), `test_drawings_api.py` (2 nye valideringstilfælde)
- Verificeret i browser: glider følger værdien; spjæld med Flyt + Rotation samtidig

## [0.16.0 build 0022] — 2026-10-08 — Symbolsektion: Solcelleanlæg

- `frontend/src/lib/symbols.ts` — ny kategori `sol` med 16 symboler: solcellepanel, solcellestreng, sol/indstråling ("Gennemsigtighed"), inverter, hybridinverter, MPPT-regulator, batteri (indre felt til "Niveau" = ladetilstand), batteribank, DC-/AC-afbryder, overspændingsbeskyttelse, elmåler (tekst-felt til kWh), elnet, forbrug/hus, elbillader, energiflow-pil — i alt 75 symboler
- `symbols.test.ts` — fangede en dobbelt `stroke-width` (ugyldig XML) i batteribanken før release; solcelle-symboler med i kontrollen af ønskede symboler
- Verificeret i browser: alle 75 symboler indsat og gemt uden at saneringen fjernede noget; panelet ved 1600, 1280 og 390 px uden overløb. 74 frontend-tests

## [0.15.0 build 0021] — 2026-10-08 — Udvidet symbolbibliotek (VVS og el)

- `frontend/src/lib/symbols.ts` — 59 symboler i tre kategorier (før 9):
  - **Proces og visning** (6): pumpe, motor, tank, værdifelt, lampe, knap
  - **Rør og VVS** (30): lige rør, bøjning 90°/45°, T-stykke, kryds, reduktion, prop, flangesamling, strømningsretning; ventiler (manuel, kugle-, kontra-, 3-vejs, motor-, magnet-, regulerings-, sikkerhedsventil); varmeveksler, filter, ekspansionsbeholder, radiator, ventilator, kedel; TT/PT/FT/LT-bobler, manometer (viser kan bindes til "Rotation"), termometer ("Niveau" på søjlen)
  - **Elektrisk** (23): ledninger, forbindelsespunkt, klemme, slutte-/brydekontakt, trykknap, nødstop, kontaktor 3-polet, relæspole, sikring, automatsikring, motorværn, motor 3~, frekvensomformer, transformer, strømforsyning, jord, signallampe, modstand, nærhedsføler, hovedafbryder, PLC
  - Fittings har rørtykkelse 10 som de lige rør; roterende dele (manometerviser, ventilatorrotor) er symmetriske om omdrejningspunktet
- `frontend/src/pages/DrawEditor.svelte` — symbolpanel med søgning og sammenklappelige sektioner pr. kategori; forhåndsvisning skaleret efter hvert symbols egen størrelse; faste kolonner så lange navne ikke skubber panelet ud
- Tests: `symbols.test.ts` (4 nye: gyldig SVG med ét `<g>`, unikke id-er, kendte kategorier, de ønskede symboler findes) — 74 frontend
- Verificeret i browser: alle 59 symboler indsat og gemt — serverens sanering fjernede ingen elementer eller attributter; panelet ved 1600, 1280 og 390 px uden overløb

## [0.14.2 build 0020] — 2026-10-08 — Fix: alle sider skalerer med browservinduet

- `frontend/src/App.svelte` — breddegrænsen på 1600 px er fjernet for alle sider (main og sidefod)
- `frontend/src/lib/canvas.ts` — fælles `availableHeight()` (ledig højde ned til sidefoden), `fitSvg()` (tegning i containerens bredde og vinduets højde) og `onLayoutChange()` (resize/zoom, menu-ombrydning, elementstørrelse)
- `frontend/src/pages/Overview.svelte` — bruger de fælles hjælpere
- `frontend/src/pages/Editor.svelte` (Bindinger) — tegningen fylder den ledige højde, markeringsboksene følger med ved resize; sidepanelet er 300-360 px, så tegningen får resten af bredden
- `frontend/src/pages/DrawEditor.svelte` (Tegn) — editorens højde beregnes ud fra den ledige plads (mindst 600 px, så hele SVG-Edits værktøjslinje ses) i stedet for `100vh - 170px`
- `frontend/src/pages/Trends.svelte` + `lib/TrendChart.svelte` — tal-graferne deler den ledige højde (150-700 px; titel/legend-forbrug måles på de tegnede grafer), til/fra-grafer er faste; tag-listen går ned til sidefoden
- Verificeret i browser: alle 11 sider ved 2560×1440, 1920×1080, 1280×720, 900×900 og 390×844 — ingen vandret scroll; Overview, Bindinger, Trends og de korte sider passer præcis i vinduet på skrivebordsstørrelser (Tegn scroller bevidst 60 px ved 720 px højde); markeringsbokse i Bindinger rammer elementet før og efter resize. 70 frontend- og 203 backend-tests

## [0.14.1 build 0019] — 2026-10-08 — Fix: Overview skalerer med browservinduet

- `frontend/src/lib/canvas.ts` — `fitSize()`: største størrelse med tegningens proportioner der passer i den ledige plads (minimumshøjde 200 px)
- `frontend/src/pages/Overview.svelte` — `fit()` sætter tegningens størrelse ud fra den faktisk ledige plads (under menu/værktøjslinje, over sidefod); genberegnes ved vinduesresize/zoom og via ResizeObserver når menuen ombrydes; den faste `max-height: calc(100vh - 170px)` er fjernet
- `frontend/src/App.svelte` — Overview er ikke længere begrænset til 1600 px bredde (de øvrige sider er uændrede)
- Tests: `canvas.test.ts` (5 nye) — 70 frontend
- Verificeret i browser med Jans tre tegninger fra testserveren ved 2560×1440, 1920×1080, 1280×720, 900×900 og 390×844: siden er præcis vinduets højde (ingen scroll), ingen vandret scroll, tegningen fylder bredden eller højden; også ved resize uden genindlæsning

## [0.14.0 build 0018] — 2026-10-08 — Flere animationer i én binding

- `frontend/src/lib/bindingForm.ts` — `Draft` (formular + gruppe-id), `toDrafts()` (gruppér pr. tag; gå-til-tegning og tomt tag står for sig), `groupIds()`, `flatten()` (samlet rækkefølge til backenden), `nextBinding()` (arver tag, vælger ubrugt animation)
- `frontend/src/pages/Editor.svelte` — én binding = ét tag-valg + en eller flere animationer med hver sine parametre; "+ Animation", "×" pr. animation, "Fjern binding"; tag-skift gælder alle bindingens animationer; fejlbeskeder nævner binding og animation
- Fix: "+ Tilføj binding" på et auto-bundet element smed den automatiske binding væk ved gem — den tages nu med
- Backend uændret: én række pr. animation som før
- Tests: `bindingForm.test.ts` (5 nye) — 65 frontend, 203 backend
- Verificeret i browser: test01 = tekst ("Status: Til/Fra") + blink i samme binding, gemt og genindlæst som én binding, blinker på Overview når sand

## [0.13.2 build 0017] — 2026-10-08 — Fix: Trends — historik kan slås til direkte, enkeltstående værdier ses

- `frontend/src/pages/Trends.svelte` — besked når intet tag gemmer historik (forklarer de grå tags); knappen "Gem historik" ud for tags uden historik (tekniker/admin, `PATCH /api/tags/{navn}` `{trend: true}`), der også vælger tagget; viewer/operatør ser ingen knap, og hjælpeteksten om Tags vises kun for tekniker/admin
- `frontend/src/App.svelte` — `canEdit` sendes til Trends
- `frontend/src/lib/trendData.ts` — `isolatedPoints()`: værdier uden gyldig nabo; `TrendChart.svelte` viser dem som prikker (8 px), ellers kun linjer
- Tests: `trendData.test.ts` (3 nye) — 60 frontend, 203 backend
- Verificeret i browser: admin slår historik til fra Trends, og første måling ses som prik; viewer ser ingen knap

## [0.13.1 build 0016] — 2026-10-08 — Fix: hængende tasks når en live-forbindelse lukkes

- `backend/app/api/live_ws.py` — ventningen på live-delta/alarmændring er flyttet til `_next_event()`, som altid annullerer begge `queue.get()`-tasks i en `finally`. Før blev de efterladt, når WebSocketen lukkede midt i ventningen, og loggen fik "Task was destroyed but it is pending!" ved hvert sideskift.
- `backend/tests/test_live_ws.py` — 2 nye tests; begge fejler uden rettelsen. 203 backend-tests.

## [0.13.0 build 0015] — 2026-10-08 — Tekst før/efter værdien i tekst-bindinger

- `backend/app/services/bindings.py` — `TextParams` har nu `prefix` og `suffix` (højst 40 tegn, mellemrum bevares som skrevet; standard tom)
- `frontend/src/lib/animate.ts` — `textFor()`: tekst før + værdi (+ enhed) + tekst efter, også rundt om "—" når værdien mangler
- `frontend/src/lib/bindingForm.ts` + `src/pages/Editor.svelte` — felterne "Tekst før"/"Tekst efter" og linjen "Vises som:" med tagets aktuelle værdi; tegningen opdateres live inden der gemmes
- Tests: `test_drawings_api.py` (2 nye tilfælde), `animate.test.ts` og `bindingForm.test.ts` (5 nye) — 201 backend og 57 frontend
- Verificeret i browser: "Tank : 88.7 liter" i editoren før gem og på Overview efter gem

## [0.12.0 build 0014] — 2026-10-08 — Trends

**Backend:**
- `app/storage/trends_db.py` — separat `trends.db` (WAL, `synchronous=NORMAL`): `trend_tags` + `samples(tag_id, ts, value)` WITHOUT ROWID; server-side nedsampling i tidsspand (gennemsnit/min/max), sidste værdi før perioden som startpunkt, rå udtræk, statistik, oprydning
- `app/services/trends.py` — `TrendRecorder`: gemmer ved første værdi, ved ændring efter minimumsintervallet, straks ved til/fra-skift og ved hul/genetablering (NULL = ingen gyldig værdi), keepalive hvert 5. min; batch-skrivning (`SCADA_TREND_FLUSH_S`, standard 5 s) med værdiens egen tid; sletning efter `SCADA_TREND_DAYS` (standard 30); sidste værdier skrives ved nedlukning; sletning af tag fjerner dets historik
- Tags: `trend` og `trend_interval_s` (1-3600 s, standard 10) — migrering til skema 7, validering ved opret/opdatér/import og i backup/restore
- `app/api/trends.py` — `GET /api/trends/data` (højst 20 tags, 10-2000 punkter, højst 400 dage), `GET /api/trends/export` (CSV med `;`, decimalkomma, BOM — åbner direkte i dansk Excel), `GET /api/trends/info`; alt filtreret efter brugerens adgang pr. tegning
- 200 backend-tests (15 nye i `test_trends.py`)

**Frontend:**
- Ny side **Trends**: tag-liste med søgning (tags uden historik er deaktiveret), perioder 15 min-30 dage eller valgfri, live-opdatering hvert 5. s for perioder op til 24 timer, CSV-eksport, valg huskes i browseren
- `src/lib/TrendChart.svelte` — uPlot 1.6 (MIT): én graf pr. enhed (aldrig to y-akser), synkroniseret markør, dansk 24-timers tidsakse, til/fra som trin med Til/Fra-akse; x-aksen viser altid hele den valgte periode; træk-zoom bevares under live-opdatering, dobbeltklik zoomer ud til perioden
- `src/lib/trendData.ts` — fletning af serier (hul vs. manglende punkt), til/fra bruger max pr. tidsspand så korte pulser ses, faste farver der følger tagget (palet valideret for farveblindhed; rød er reserveret til alarmer)
- Tags-siden: afsnit "Historik" (gem historik, minimumsinterval)

**Verificeret** i browser mod mock-PLC (desktop 1400 px og mobil 390 px): grafer pr. enhed, legend ved hover, zoom/live/udzoom, CSV, ingen konsolfejl og ingen vandret scroll.

## [0.11.0 build 0013] — 2026-10-08 — Alarmer

**Backend:**
- `app/services/alarms.py` — alarmmotor (ISA-18.2 forenklet): høj-/lavalarm pr. tag (H/HH, L/LL) med dødbånd og eskalering/nedgradering, til/fra-alarm (`alarm_on`), forsinkelse, PLC-kommunikationsalarm (`SCADA_ALARM_COMM_DELAY_S`, standard 10 s); tilstande active_unack/active_ack/rtn_unack; tags uden gyldig værdi bevarer deres alarmtilstand; evaluering hvert sekund og ved hver ændring i live-værdier
- Tabeller `alarm_state` (aktive alarmer — overlever genstart) og `alarm_events` (historik, seneste 50.000); migrering tilføjer alarmkolonner til `tags`
- Tags: `alarm_hh/h/l/ll`, `alarm_deadband`, `alarm_delay_s`, `alarm_on` — valideret på den endelige tilstand ved opret/opdatér/import (stigende grænser, grænser kun på tal-tags, til/fra-alarm kun på til/fra-tags, dødbånd ≥ 0, forsinkelse 0-3600 s) og i backup/restore
- `app/api/alarms.py` — `GET /api/alarms` (aktive + opsummering), `POST /api/alarms/ack` (operator+, enkelte eller alle synlige), `GET /api/alarms/history`; alt filtreret efter brugerens adgang pr. tegning; kvittering i audit-loggen
- WebSocket sender `{"type":"alarms"}` ved forbindelse og ved hver ændring
- 185 backend-tests (21 nye i `test_alarms.py`)

**Frontend:** alarmklokke i toppen (antal aktive/ukvitterede, rød ved høj prioritet, blinker ved ukvitterede); ny side **Alarmer** (aktive med kvittering, historik); elementer bundet til et tag i alarm blinker rødt (ukvitteret) eller er rødt markeret (kvitteret) i Overview; alarmfelter i tag-redigering.

**Verificeret** i browser mod mock-PLC: grænser sat i UI, alarmer udløses, klokke + markering i tegningen, kvittering registrerer bruger, historik.

## [0.10.0 build 0012] — 2026-10-08 — Fase 4: tegne-editor (SVG-Edit)

**Frontend:**
- Ny side **Tegn** (engineer+): SVG-Edit 7.4 (npm `svgedit`, MIT m.fl. — AGPL-kompatible) i en iframe fra samme origin (`/svgedit/scada-editor.html` + eksternt modul `scada-editor.js`, ingen inline-script pga. CSP); udvidelser begrænset til lokale (connector, eyedropper, grid, markers, panning, polystar, shapes) — ingen browser-lagring/filåbning; dansk sprog
- Værktøjslinje: ny tegning med navn, åbn en vilkårlig version, **Gem kladde** (ny version, Overview uændret), **Gem og udgiv**, **Udgiv denne version** (rollback), kommentar pr. version, advarsel om ikke-gemte ændringer
- Panel "Valgt element": samme tag-dropdown som binding-editoren sætter elementets id = tag-navn (auto-binding); manuelt id med kontrol af dubletter; fortryd via SVG-Edit
- Symbolbibliotek (ISA-101): pumpe, motor, ventil, tank, værdifelt, lampe, knap, rør — indsættes med unikke id'er, forskudt, valgt og med fortryd
- `src/lib/TagSelect.svelte` — fælles tag-dropdown (binding-editor og tegne-editor)
- `scripts/copy-svgedit.mjs` kopierer SVG-Edit til `public/svgedit/` før dev/build (git-ignoreret)

**Deploy:** nginx `X-Frame-Options: SAMEORIGIN` og CSP `frame-ancestors 'self'` (iframe fra samme origin).

**Backend:** test af at SVG-Edit-output (`se:`-navnerum, lag) renses og bevarer id'er. 164 backend-tests.

**Verificeret:** flowet set i browser lokalt (ny tegning med symboler → tag via dropdown → auto-binding live i Overview; kladde → udgiv; eksisterende id'er bevares), og SVG-Edit kørt på testserveren under nginx' CSP uden fejl.

## [0.9.0 build 0011] — 2026-10-08 — Adgang pr. tegning

**Backend:**
- `users.scoped` + tabel `user_drawings` (migrering af eksisterende database: alle eksisterende brugere beholder adgang til alle tegninger)
- `app/services/scope.py` — synlige tegninger, synlige tags (eksplicitte + automatiske bindinger i brugerens tegninger) og betjenbare tags pr. bruger
- Håndhævet i backend: tegningsliste filtreres, andre tegninger svarer 404 (view/svg/bindings), "gå til"-bindinger til skjulte tegninger fjernes, `/api/tags`, `/api/tags/{navn}`, `/api/live` og WebSocket filtreres
- **Skærpet:** operatører kan kun betjene tags der har en klik-handling (write/toggle/pulse) i en tegning de har adgang til — afviste forsøg logges; tekniker/admin uændret
- Brugere-API: `drawings` (null = alle, liste = kun de valgte) ved oprettelse og ændring; ukendte tegninger afvises; sletning af en tegning fjerner den fra brugeres adgang
- `effective_bindings()` udskilt fra `view()` i DrawingService
- 163 backend-tests (6 nye i `test_scope.py`)

**Frontend:** Brugere-siden har kolonnen "Tegninger" og valg af "Alle tegninger" / "Kun valgte" ved oprettelse og redigering; rollebeskrivelser opdateret.

**Verificeret** i browser: operatør oprettet med adgang til én tegning ser kun den og dens tags.

## [0.8.1 build 0010] — 2026-10-08 — fix: SSE-dækning (afslutter debug-serien 0.7.0.x)

Jan bekræftede at DO2 nu opdaterer lige så hurtigt som DO1. Rettelsen er den fra 0.7.0.1 (se nedenfor); denne version lukker fejlen i BUGS.md.

## [0.8.0 build 0009] — 2026-10-08 — Backup og restore

**Backend:**
- `app/services/backup.py` — eksport af PLC-forbindelser (uden adgangskoder), tags, tegninger med alle versioner og bindinger som JSON (format `hypervisionplc-scada-backup` v1); brugere, sessioner, audit og hemmeligheder er ikke med
- Restore: hele filen valideres først (kilder, skrivbar-regel, min/max, SVG'er saneres igen, bindinger mod tags/tegninger i backuppen) — ved fejl ændres intet og alle fejl listes; derefter automatisk backup af nuværende tilstand, SVG-filer i staging-mappe der byttes ind, databasen udskiftes i én transaktion (`replace_project`) og filerne byttes tilbage hvis den fejler; adgangskoder bevares for eksisterende PLC-nøgler, manglende listes; PLC-runtimes genstartes
- Automatisk backup på serveren (`SCADA_BACKUP_HOURS`, standard 24; `SCADA_BACKUP_KEEP`, standard 7) i `<data>/backups/`
- `app/api/backup.py` — `GET /api/backup`, `POST /api/backup/restore` (max 64 MB), `GET /api/backup/files[/{navn}]` (kun admin, filnavne valideres); audit-log
- nginx: `client_max_body_size 64m`
- 157 backend-tests (10 nye)

**Frontend:** ny side **Backup** (admin): hent, gendan med opsummering og bekræftelse, liste over backups på serveren.

**Verificeret** i browser (lokal stak).

## [0.7.0.1 build 0008] — 2026-10-08 — debug: langsom opdatering mod rigtig PLC

**Årsag:** SSE-watch-listen blev sendt URL-kodet (`coils=0%2C1%2C2`). PLC'en afkoder ikke query-strengen og overvågede kun første adresse pr. type, mens SCADA'en antog at alle var dækket og kun pollede dem hvert 2. s. ST-variabler blev også kun pollet hvert 2. s når SSE var sund.

**Ændret:**
- `app/plc/sse.py` — query bygges med ukodede kommaer (`build_query`); HR/IR-loft 159 som PLC'en; "dækning" afledes af PLC'ens `connected.watching` — kun bekræftede adresser regnes som leveret af SSE, ellers advarsel i status
- `app/services/plc_runtime.py` — alt SSE ikke leverer (ST-variabler, GLOBAL_VAR, 32-bit, ubekræftede adresser) polles hvert 0,5 s; SSE-dækkede adresser får kontrol-poll hvert 2 s
- `mock_plc/app.py` — URL-afkoder ikke query-strengen og har PLC'ens adresselofter (som den rigtige PLC), så fejlen fanges i test
- PLC-siden viser hvor mange adresser SSE dækker
- 147 backend-tests (4 nye regressionstests)

## [0.7.0 build 0007] — 2026-10-08 — Fase 5: betjening og audit-log

**Backend:**
- `app/services/operate.py` — skriv/toggle/puls: kun skrivbare hr/coil-tags; invers skalering (rå = (værdi − offset)/scale) med afrunding og typegrænser (uint/int/dint/dword); min/max håndhæves i backend (0 er gyldig grænse); læs-tilbage efter skrivning med advarsel når PLC'en (fx en ST-binding) har overskrevet værdien; puls nulstilles af serveren også hvis requesten afbrydes; lås pr. tag; PLC-fejl oversat (afvist → PLC'ens tekst, svarer ikke, mangler skriverettighed, overbelastet)
- `app/services/audit.py` + tabel `audit` — alle skrivninger (også afviste) og konfigurationsændringer (PLC'er, tags, tegninger, bindinger, brugere, login); hemmeligheder maskeres (`***`); automatisk oprydning (seneste 50.000)
- `app/api/operate.py` — `POST /api/tags/{navn}/write|toggle|pulse` (operator+), `GET /api/audit` (engineer+)
- Bindinger: `click:write`, `click:toggle`, `click:pulse`, `click:goto` — validering: skrivbart tag, til/fra kræver ikke-real, højst én klik-handling pr. element, goto-tegning skal findes
- Tags: skrivbar kun for hr/coil — vurderet på den endelige tilstand ved oprettelse, opdatering og import
- `view` leverer skrivbar/min/max/bekræftelse/type pr. tag til dialogerne
- Mock-PLC: `reject_writes` (fx safe mode) og `locks` (simuleret ST-overskrivning)
- 143 backend-tests (24 nye for betjening)

**Frontend:**
- Overview: klikbare elementer (markeret ved hover); setpunkt-dialog med nuværende værdi, tilladt interval, validering og bekræftelsestrin; til/fra- og puls-bekræftelse; gå-til-tegning; grøn/gul/rød besked med PLC'ens egen fejltekst eller advarsel om overskrevet værdi; viewer får "kræver rollen operatør"
- Binding-editor: klik-handlinger med parametre; **tag-valg som dropdown** grupperet pr. PLC (ønske fra Jan)
- Tags: redigér tag (kilde, enhed, skala, skrivbar, min/max, bekræftelse); "skrivbar"-markering
- Ny side **Log** (engineer+) med filtre
- 46 frontend-tests

**Verificeret** i browser mod mock-PLC (desktop + mobil). Der er IKKE skrevet til den rigtige PLC 10.1.1.30.

## [0.6.0 build 0006] — 2026-10-08 — Fase 3: binding-editor

**Frontend:**
- `src/pages/Editor.svelte` — ny side "Bindinger" (engineer+): klik på et element i tegningen (nærmeste forfader med id vælges, fx gruppen bag en pumpe) eller vælg i en søgbar elementliste med status (bundet/auto); valg- og hover-ramme; formularer pr. animation (tekst, fyld-/stregfarve med tærskler, synlighed, blink, niveau, rotation, gennemsigtighed); live-forhåndsvisning med rigtige værdier før gem; "Tilpas" gør en auto-binding eksplicit; fortryd; advarsel om ukendt tag og om niveau på andet end `<rect>`; liste over forsvundne elementer med "Fjern bindinger"
- `src/lib/bindingForm.ts` — formular ↔ params med danske fejlbeskeder (decimalkomma, 0 er gyldig, tom er fejl, min < max, stigende tærskler), elementvalg, farvekonvertering; 9 tests
- `src/lib/canvas.ts` — fælles SVG-rendering for Overview og editor
- Genveje: "Redigér bindinger" fra Overview og "Bindinger" fra Tegninger

**Backend:** `PUT /bindings/{element}` med tom liste fjerner bindinger også for forsvundne elementer.

**Verificeret** i browser (desktop + mobil): valg via klik og liste, auto → eksplicit, gem, forhåndsvisning af niveau, fejlbesked ved ugyldig min/max, Overview bruger de nye bindinger.

## [0.5.0 build 0005] — 2026-10-07 — TLS med nginx (selvsigneret certifikat)

**Tilføjet:**
- `deploy/nginx-hypervisionplc-scada.conf` — nginx foran uvicorn (127.0.0.1:8000): HTTP→HTTPS-omdirigering, TLS 1.2/1.3, WebSocket-proxy for `/ws/`, `X-Real-IP`/`X-Forwarded-Proto`, sikkerheds-headere (CSP, X-Frame-Options, nosniff, Referrer-Policy), `client_max_body_size 8m`; HSTS bevidst udeladt indtil Let's Encrypt
- `deploy/tls-selfsigned.sh` — selvsigneret EC P-256-certifikat (SAN: hostnavn + IP, 825 dage) i `/etc/hypervisionplc-scada/tls/`; overskriver aldrig et eksisterende certifikat (stierne genbruges af Let's Encrypt senere)
- `deploy/install.sh --with-nginx <hostnavn> [ip]` — installerer nginx/openssl, certifikat og site, fjerner nginx' default-site, sætter `SCADA_COOKIE_SECURE=true`
- `.gitattributes`: `*.conf` med LF

**Rettet før release:** deploy-filer redigeret på Windows fik CRLF (`set: Illegal option -` på Debian). Deploy sker nu fra `git archive` (LF-normaliseret) i stedet for arbejdsmappen — se README.

## [0.4.0 build 0004] — 2026-10-07 — Login, brugere og roller

**Backend:**
- `app/services/auth.py` — scrypt-hashede adgangskoder (unikt salt), sessioner (kun SHA-256 af token gemmes, glidende udløb), login-låsning efter 5 fejl pr. (bruger, IP), ens svar/svartid for ukendt bruger, regler for adgangskoder (min. 10 tegn, ≠ brugernavn, ikke tom/blank), bootstrap af `admin` (SCADA_ADMIN_PASSWORD eller genereret engangsadgangskode i `initial-admin-password.txt`, chmod 600, skal skiftes)
- `app/storage/db.py` — tabeller `users` og `sessions`; sidste aktive admin beskyttes atomisk i én transaktion ved nedgradering, deaktivering og sletning
- `app/api/auth.py` — `/api/auth/login|logout|me|password`, `/api/users` (admin); rolle-afhængigheder på ALLE routes: viewer (se), engineer (tegninger/tags/bindinger, se PLC'er), admin (PLC-forbindelser, brugere); WebSocket `/ws/live` kræver gyldig session (lukkes med 4401)
- Session-cookie `scada_session`: HttpOnly, SameSite=Strict, Secure når `SCADA_COOKIE_SECURE=true`; ændrende kald fra fremmed Origin afvises (403)
- Rolle-, adgangskode- og deaktiveringsændringer afslutter brugerens sessioner straks
- Advarsel ved opstart hvis serveren lytter på netværket uden TLS
- 119 backend-tests (16 nye for auth)

**Frontend:** login-side, tvunget adgangskodeskift, brugermenu (skift adgangskode, log ud), side "Brugere" (admin), menupunkter og redigeringsknapper vises efter rolle; udløbet session → login.

**Verificeret** i browser: fejl-login, engangsadgangskode → tvunget skift, admin-visning, afvist nedgradering af sidste admin, viewer på mobil uden redigering, log ud.

## [0.3.0 build 0003] — 2026-10-07 — Fase 2: SVG-tegninger og Overview med live-værdier

**Backend:**
- `app/services/svg_sanitize.py` — server-side sanering (defusedxml, hvidliste af SVG-elementer; fjerner script, on*-handlere, foreignObject, SMIL, eksterne href/url(), @import; kun raster-data-URI'er i `<image>`; tilføjer viewBox ud fra width/height; rapport over fjernet indhold)
- `app/services/drawings.py` + `app/storage/files.py` — tegninger med versioner (DB tildeler versionsnummer atomisk), aktiv version, sletning; `view` samler SVG + eksplicitte og automatiske bindinger (element-id/inkscape:label = tag-navn) + tag-metadata; advarsel om forældreløse bindinger
- `app/services/bindings.py` — validering af animationer: text, fill, stroke, visible, blink, level, rotate, opacity (farver hvidlistet, tærskler sorteret, min<max)
- `app/api/drawings.py` — `/api/drawings[...]`, `/svg` serveres med CSP, `PUT /bindings/{element}` erstatter kun ét elements bindinger
- `app/api/live_ws.py` — WebSocket `/ws/live`: snapshot + delta pr. abonnerede tags + PLC-status
- Tag der bruges i en binding kan ikke slettes (409)
- `/api/health` returnerer `source_url` (AGPL §13); `defusedxml` og `websockets` tilføjet som afhængigheder
- 102 backend-tests

**Frontend (ny):** Vite + Svelte 5 + TypeScript — sider Overview, Tegninger, Tags, PLC'er; DOMPurify som ekstra sanering; kvalitetsvisning (udtonet ved kommunikationsfejl) og fejlbanner med PLC'ens egen fejltekst; kildekode-link i footer. 27 vitest-tests.

**Eksempler:** `docs/examples/demo-tank.svg` (mock-PLC), `docs/examples/plc1-io.svg` (HypervisionPLC 10.1.1.30).

**Verificeret:** set i browser (Playwright) på desktop og mobil — lokalt mod mock-PLC (inkl. PLC offline) og på testserveren mod den rigtige PLC 10.1.1.30 med SSE.

## [0.2.0 build 0002] — 2026-10-07 — Fase 1: backend, PLC-klient, mock-PLC og tag-model

**Tilføjet:**
- `backend/app/plc/` — PLC-klient-laget: `client.py` (én keep-alive-forbindelse, serielle kald, Bearer-token genbrugt + re-login ved 401, rate-budget 5 req/s, backoff ved 429, typede fejl med PLC'ens egen fejltekst), `planner.py` (bulk-poll-plan; 32-bit-par deles aldrig), `sse.py` (SSE-lytter med watch-list/`subscribe=all`, håndterer 503/fuld, slået fra og PLC BUG-483), `errors.py`, `ratelimit.py`
- `backend/app/services/` — `tagsource.py` (kilde-grammatik `plc:hr:100:real`, `plc:logic:1:Var`, `plc:global:Var`; afkodning high word først; skalering), `live_cache.py` (værdi/kvalitet/tid, publicerer kun ændringer), `plc_runtime.py` (poll-løkke med adaptiv rate: 0,5 s uden SSE / 2 s med sund SSE), `manager.py`, `plcs.py` (CRUD, skriv-kun adgangskode, tag-forslag fra ST-variabler), `tags.py` (CRUD + import, samme validering ved opret/opdatér/import)
- `backend/app/storage/` — SQLite (WAL, kun ændrede felter skrives) + `secrets.json` (PLC-adgangskoder, chmod 600)
- `backend/app/api/` — REST: `/api/health`, `/api/plcs[/{key}[/discover]]`, `/api/tags[/{name}|/import]`, `/api/live`; alle fejl som `{"error": "..."}` inkl. FastAPI-valideringsfejl
- `backend/mock_plc/` — mock af HypervisionPLC REST API (bearer-login, 8 sessions, rate-limit, bulk-formater, IR 0-319, ST-variabler, SSE med 3 pladser) med simuleret proces
- `backend/tests/` — 67 tests; klient/SSE/runtime/API testes mod mock-PLC over rigtige sockets
- `deploy/` — `install.sh` (Debian/Raspberry Pi OS), systemd-units for SCADA (hærdet, egen bruger `scada`) og mock-PLC

**Verificeret** på Debian 13-testserver (10.1.1.31) som systemd-service: polling + SSE mod mock-PLC, alle demo-tags `good`.

## [0.1.0 build 0001] — 2026-10-07 — Projektinitialisering

**Filer tilføjet:**
- `CLAUDE.md` — projektdefinition og systemregler (udfyldt for HypervisionPLC SCADA)
- `version.json` — versionskilde (0.1.0 build 0001)
- `ARCHITECTURE.md` — lag: frontend → API → service → PLC-klient/lager
- `FEATURES.md` — feature-backlog fordelt på fase 1–6
- `BUGS.md` — bug-register
- `CHANGELOG.md` — denne fil
- `RELEASE_NOTES.md` — release-noter
- `docs/RESEARCH_OG_DESIGN.md` — research af web-SCADA/SVG-HMI, valgt design og faseplan
- `.gitignore`
