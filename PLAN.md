# Plan: Animationer samlet pr. symbol, og unikke navne på alle symboler (v5.9.0) — 2026-11-12 — afventer OK

Jans ønske: (1) i symbol-guiden for en signalvej skal et symbol med flere dele (3-vejs ventil: port A, B, AB, motor …) have sine animationer **samlet i en gruppe** i stedet for spredt i listen; (2) alle symboler skal have et **unikt navn/id**, så to 3-vejs ventiler — eller to T-stykker — kan kendes fra hinanden i listerne.

## I dag
- Trin 4 viser alle animationer i én lang liste i den rækkefølge, de ligger i opsætningen (kun et filter *Vis animationer for*).
- Et symbol uden navn (`data-hv-name`) vises med sit rå id (`svg_12`) eller sin type; to ens symboler med samme navn kan ikke skelnes. Nye biblioteksymboler får et unikt navn ved indsættelse (`Pumpe 2`), men ældre tegninger og importerede/kopierede symboler kan mangle det.

## Løsning
1. **Grupper i guiden (trin 4, kun signalvej):** animationerne vises under en **sammenfoldelig overskrift pr. element** ("3-vejs motorventil V1 — 3 animationer"), i tegningens rækkefølge; hver gruppe har sin egen *+ Animation* (lægges på elementets dele). ▲▼ flytter inden for gruppen. Selve rækkefølgen i opsætningen (som afgør, hvilken animation der vinder) ændres ikke — kun visningen grupperes (animationer på samme del ligger altid i samme gruppe).
2. **Unikke, læsbare navne overalt (backend `describe_group`):** et element vises med sit navn, hvis det er unikt; er navnet ikke unikt, eller mangler det, vises `navn (id)` — fx `3-vejs motorventil (svg_12)` / `T-stykke (svg_31)`. Bruges i guidens elementfilter, gruppeoverskrifter og delnavne (`… · Port A`).
3. **Giv unikke navne i Tegn:** i *Symbol-oversigt* vises "N symboler har intet navn" og knappen **Giv dem unikke navne** — hvert navnløst biblioteksymbol får typens navn + et løbenummer (`3-vejs ventil 2`), i ét fortryd-trin; navnene gemmes med tegningen (Gem). Findes der kopier med samme navn, vises de allerede som advarsel (eksisterende tjek).

## Trin
FEATURES (planlagt) → `svg_sanitize.describe_group` (unikke labels, `named`, `type`) + test → `SymbolGuide` (grupper som snippet, per-gruppe tilføj, ▲▼ i gruppen, filter-etiketter) → `scada-core.js` `nameUnnamedSymbols` + `SymbolTree`/`DrawEditor` (knap) → manual (kap. 07/08), LLM-tillæg, CHANGELOG, RELEASE_NOTES, **v5.9.0**, OTA → browser: vejen med to 3-vejs ventiler og to T-stykker (demo-kopien) → reviewer er ikke nødvendig (kun visning og navngivning), men kører tests.

## Risici
- Navngivning ændrer tegningen (men kun `data-hv-name`; ids rører vi ikke, så bindinger/forbindelser/vejene består) — ét fortryd-trin, og kun symboler uden navn.
- Gamle tegninger med dublerede navne: vises som `navn (id)`; vi omdøber ikke af os selv.
# Plan: Signalvejen som et rigtigt symbol — vejens egne animationer kan redigeres (v5.8.0) — 2026-11-12 — afventer OK

Jans krav: det er ikke nok at kunne *lægge ekstra animationer* på en vejs elementer. De animationer, vejen selv giver (løbelys på rørene, farve, blink …), skal kunne **ændres som i ethvert andet symbol**: skift type, kilde (et tag, en betingelse/logikblok, "altid til"), parametre (farve, hastighed, retning) og slet dem — så vejen efterfølgende arbejdes med som et symbol, hvor animationer tildeles frit.

## I dag (v5.4)
Vejens grundanimationer (*Udseende* i vejens guide) gemmes i vejens data og lægges på Overview af serveren (`_path_bindings`), men vises **ikke** i symbol-guiden — der ser man kun de egne. De kan derfor ikke redigeres.

## Valgt løsning (af tre)
- **A. Grundanimationerne skrives ind i vejens symbol-opsætning som almindelige animationer (valgt).** Når vejen gemmes, skriver serveren (re)genererer dem i `sv~<id>`-opsætningen; symbol-guiden viser dem i trin 4 som alle andre og kan ændre dem. Hver animation har et nyt felt **`auto`** ("følger vejens udseende"): sat = serveren genskaber den, når vejen gemmes igen; fjernes fluebenet, er den *din* og røres aldrig af vejen.
- B. Vis grundanimationerne skrivebeskyttet i guiden med en knap "Overtag". Intet er redigerbart direkte, og man skal først "overtage" hver — halvt svar på kravet.
- C. Fjern vejens *Udseende*-trin og lad guiden lave alt. Mister den hurtige opsætning ("farv alle rør, løbelys på alle") og vejens enkle start.

## Sådan virker det
1. **Datamodel:** `Anim.auto: bool = false` (backend `Anim`, frontend `Anim`/`normalize`). Ingen ny tabel; `symbol_config` bærer alt.
2. **Gem vej** (`SignalPathService.save`): efter at vejen er gemt, bygges grundanimationerne (løbelys/farve/blink/synlig/roterer pr. element og del, med vejens pseudo-tag som kilde og *aktiv/passiv*) som `auto: true`-animationer og lægges i `sv~<id>`-opsætningen: eksisterende `auto: true` erstattes, alt andet (dine egne og de frigjorte) bevares. Valideres som et almindeligt gem (`validate_config`); fejler det, rulles vejen tilbage.
3. **Visning:** `_path_bindings` (vejens egne bindinger ved siden af symbolet) fjernes — alt kommer nu fra symbol-opsætningen via `_path_symbol_bindings` (samme prioritetsregler som i dag).
4. **Guiden** (trin 4): hver animation på en vej viser **"Følger vejens udseende"** (afkrydsning). Er den sat, står der en hjælpetekst: *ændringer overskrives, når vejen gemmes igen — fjern fluebenet for at beholde dem*. Resten (type, kilde, farve, hastighed, retning, når/ikke når, slet, flyt op/ned, tilføj) er den eksisterende guide.
5. **Opgradering:** ved opstart skrives grundanimationerne for alle eksisterende veje ind én gang (flag i `meta`, samme mønster som v5.1-migreringen) — Overview ser ens ud før og efter.
6. **Backup/gendan:** uændret (alt ligger i `symbol_config`); `auto` er et almindeligt felt.

## Tilføjelse (Jan 2026-11-12): elementer med flere porte — fx en 3-vejs ventil — kan indstilles i vejen
En 3-vejsventil i en vej farver i dag de porte, vejen bruger (valgt i *Udseende*, gruppen *3-vejsventiler*). I v5.8.0 bliver det **én animation pr. port** (A, B, AB) i vejens opsætning, med vejens gren som kilde:
- Du kan sætte **farven pr. port** (fx *port A og AB blå, B grå*), skifte kilde pr. port (et tag, ventilens stilling, en logikblok) og tilføje blink eller løbelys på en port.
- **Hvilke porte der er "i vejen"** følger stadig vejens valg af *vej gennem ventilen* (A↔AB eller B↔AB) — ændres det i vejens guide og vejen gemmes, genskabes portenes `auto`-animationer; dine egne (frigjorte) består.
- **Guiden får et elementfilter** i trin 4: *Vis animationer for: alle / Pumpe 1 / Ventil V2 (3-vejs) …* og en gruppering pr. element, så en vej med 30 elementer ikke bliver en lang liste. *+ Animation* lægger sig på det valgte element, og delvælgeren viser kun dets dele (porte, ramme, tekst …) med deres rigtige navne (*Port A*, *Port AB*, *Motor*).
- Gælder alle elementer med flere dele (ventiler, T-stykker, pumper), ikke kun 3-vejsventilen.

## Trin
1. FEATURES.md (v5.8.0 planlagt) → 2. backend: `Anim.auto`, `signal_paths/materialize.py` (rene funktioner: data → animationer), `save`, `_path_bindings` væk, migrering → 3. frontend: `Anim.auto` + afkrydsning/hjælpetekst i `SymbolGuide` → 4. tests (backend: materialisering, bevarelse af egne/frigjorte, regenerering, migrering, backup-rundtur, restart på eksisterende data; frontend: afkrydsning) → 5. manual (kap. 08), LLM-tillæg, CHANGELOG, RELEASE_NOTES, **v5.8.0**, OTA → 6. **browser:** vej → *Ret som symbol* → løbelyset står som animationer → skift kilde til et tag → gem vejen igen (frigjort består, auto genskabes) → Overview. **Reviewer** (data-integritet, migrering).

## Risici
- **Migrering** af eksisterende veje: skal give præcis samme visning (samme del, type, kilde, parametre, rækkefølge). Testes mod demo-tegningen før/efter.
- **To veje på samme del** og **prioritet** mod andre symbolers animationer: uændret regel (`position` ≥ 100 000, derefter rækkefølgen i opsætningen) — men nu ligger vejens egne først og dine efter, så dine vinder (som i dag).
- **Flere end 12 animationer** (`MAX_ANIMS`): en stor vej kan give mere end grænsen → grænsen hæves for vejsymboler (fx 200 — vejens elementer × delene) eller grundanimationerne grupperes pr. type; afgøres ved at tælle på demo-tegningen.
- `auto`-flag på en animation, der frigøres og senere slettes: ingen genskabelse før næste vejgem — det er bevidst og står i hjælpeteksten.
# Plan: Server-værktøjskasse `scada-tool` (v5.6.0) — 2026-11-12 — afventer OK

Anledning: v5.4.0 kunne ikke starte, rullede tilbage, og opdateringsstatus stod fast på "applying" (maskinen blev genstartet midt i opdateringen) — så ny upload gav "En opdatering er i gang". Det kostede flere SSH-trin at finde og rydde. Jan vil have en **værktøjskasse på serveren** med de mest brugte vedligeholdelsesfunktioner.

## Løsning (af tre)
- **A. Ét kommando `scada-tool` (shell + lidt Python), installeret af `install.sh` ved siden af `scada-maint` (valgt).** Kører som root, dansk output, tørkørsel/bekræftelse ved alt der ændrer noget, hvert skridt logges (`logger -t scada-tool`). Genbruger de eksisterende scripts (`apply-update.sh`, `scada-maint`) i stedet for at kopiere deres logik.
- B. Udvid `scada-maint` med flere kommandoer — blander diskoprydning og drift, og navnet passer ikke.
- C. Kun dokumentation af kommandoer — ingen hjælp, når serveren ikke starter.

## Kommandoer
| Kommando | Gør |
| --- | --- |
| `scada-tool status` | Version/build, tjenestens tilstand og oppetid, `/api/health`, opdateringsstatus, disk, hukommelse, nginx/LLM-tjeneste, de seneste fejl |
| `scada-tool check` | **Diagnose af en server, der ikke starter:** importerer appen med serverens Python (fanger fx en manglende import), tjekker port, `PRAGMA quick_check` på databaserne, rettigheder på data-mappen — og siger *hvad* der er galt |
| `scada-tool logs [-n N] [-f] [--fejl]` | Systemloggen for SCADA (seneste N linjer, følg, kun fejl) — også `--tjeneste nginx\|llm\|update` |
| `scada-tool start\|stop\|restart` | Styrer tjenesten og venter på, at `/api/health` svarer (ellers vis loggen) |
| `scada-tool update status` | Opdateringsstatus + `update.log` |
| `scada-tool update reset` | **Rydder en hængende opdatering** (status "applying/queued", `apply.request`, halvfærdig pakke) — efter at have tjekket, at opdateringstjenesten ikke kører |
| `scada-tool update apply FIL.tar` | Installerer en OTA-pakke fra en fil på serveren (samme kontrol og tilbagerulning som web-opdateringen) — til når web ikke virker |
| `scada-tool update rollback` | Gendanner forrige version (`…scada.prev`) og starter tjenesten |
| `scada-tool backup list\|create` | Viser/laver en backup af konfigurationen (samme som web) |
| `scada-tool user reset NAVN` | Nulstiller en brugers adgangskode (spørger i terminalen, vises aldrig) — hvis man er låst ude |
| `scada-tool config` | Porte, stier, miljø (**aldrig** hemmeligheder), netværk |
| `scada-tool maint …` | Videre til `scada-maint` (disk fuld) |

## Samtidig rettes årsagen
- `services/updates.py`: en opdatering, der står som "applying/queued", men hvor opdateringstjenesten (`hypervisionplc-scada-update.service`) ikke kører, regnes som **hængende** efter 2 minutter (i dag først efter 20) — så ny upload ikke blokeres af en genstart midt i en opdatering. Web-siden viser en knap "Ryd hængende opdatering" (tekniker/admin).

## Trin
1. FEATURES.md registreres før kodning.
2. `deploy/scada-tool.sh` (+ `backend/app/tool.py` til det, der kræver Python: diagnose-import, DB-tjek, nulstilling af adgangskode via samme hashfunktion som web). `install.sh` installerer og opdaterer den.
3. `updates.py`: hurtigere "hængende" + endpoint til at rydde (audit-logget).
4. Manual (kap. 13 *Server-værktøjskassen*), LLM-tillæg, CHANGELOG/RELEASE_NOTES, **v5.6.0**, OTA.
5. Tests: `tool.py` (nulstilling af adgangskode, DB-tjek, config uden hemmeligheder), `updates.py` (hængende efter 2 min når tjenesten ikke kører; ryd), `sh -n` + kørsel af scriptet mod en midlertidig mappestruktur; **på demo-serveren** efter OTA: `status`, `check`, `logs`, `update reset`.
6. **Reviewer** før commit (rod-værktøj: adgangskode, hemmeligheder, rm/gendannelse).

## Risici
- Rod-script kan slette: ingen `rm -rf` på ubekræftede stier; `update reset` rører kun `updates/`-mappen; `rollback` kræver `…prev`.
- Adgangskode-nulstilling må ikke læses fra kommandolinjen eller ende i logs; kun prompt (`read -s`) og audit-linje uden værdien.
- Det er et værktøj til drift af én server (Pi eller VM) — ingen fjernstyring, ingen ny netværksflade.
# Plan: Symbol-oversigt som træ i Tegn (v5.5.0) — 2026-11-11 — afventer OK

Jans ønske: ét samlet sted, hvor man ser **alle symboler på tegningen som et træ** og kan gå til dem for at rette dem — i dag er det spredt ud i editoren (Objekter, Symboler › Grupper, Signalveje, symbol-editoren, Opsæt symbol).

## Tolkning (ret mig, hvis den er forkert)
- "VM-symboler" = de **virtuelle symboler**, altså signalvejene (`sv~<id>`, v5.4.0).
- **Niveau 1** (under tegningen): *Grundsymboler* (bibliotekssymboler og navngivne elementer), *Signalveje* (virtuelle symboler) og *Grupper* (funktionsgrupper og udvalg).
- **Niveau 2:** en signalvej foldes ud til de elementer, den består af; en gruppe foldes ud til sine medlemmer (grundsymboler). Hver række er et symbol, man kan rette — og et grundsymbol kan stå flere steder (som medlem af flere grupper og veje).

## Løsning (kun frontend, ingen backend-ændring — alle data findes allerede)
- Ny komponent `lib/SymbolTree.svelte` + rene funktioner `lib/symbolTree.ts` (bygger træet af: elementlisten fra tegningen (`buildElements`), `GET …/symbols` (opsat ja/nej), `GET …/signal-paths`, `GET …/symbol-groups`). Testet i `symbolTree.test.ts`.
- Panelet **Symbol-oversigt** i Tegns højrepanel (ny `PanelSection`, øverst under Objekter): søgefelt, "kun ikke-opsatte", fold ud/sammen, antal og et ✓ på opsatte symboler.
- Pr. række: **klik** = vælg i tegningen (`selectByIds`, vejen: alle dens elementer); **Opsæt** = symbol-guiden (grundsymbol: elementet; signalvej: `sv~<id>`; gruppe: gruppens animationer, den eksisterende dialog); **Ret vej** (signalveje); **Skift symbol** / **Kopiér opsætning** (de eksisterende dialoger). Ingen ny redigeringslogik — kun én indgang til de eksisterende.
- Opdateres, når guiden/vejene/grupperne gemmes (samme `inspectRev`-mekanisme som Objekter).

## Trin
1. FEATURES.md er allerede registreret (v5.5.0 planlagt).
2. `symbolTree.ts` (rene funktioner) + test.
3. `SymbolTree.svelte` + wiring i `DrawEditor.svelte` (handlinger genbruger `guideFor`, `selectByIds`, signalvej-guiden, gruppe-dialogerne).
4. Manual (kap. 07 *Symbol-oversigt*), LLM-tillæg, CHANGELOG, RELEASE_NOTES, **v5.5.0**, OTA.
5. **Browser:** træet på en tegning med veje og grupper: fold ud/sammen, klik vælger i tegningen, Opsæt åbner guiden, søg/filter.

## Risici
- Store tegninger (hundredvis af symboler): træet bygges kun af elementer med navn/biblioteksttype og foldes sammen som standard.
- Et symbol i flere grupper/veje vises flere steder — det er bevidst, men tællerne skal ikke tælle det dobbelt.
# Plan: Signalvejen som samlet symbol, der kan rettes i symbol-guiden (v5.4.0) — 2026-11-11 — afventer OK

Jans ønske: (1) fra listen over gemte signalveje skal man kunne rette vejen, så **alle dens elementer kan redigeres** — fx ekstra animationer og symbolændringer; (2) det, man selv har rettet, må **ikke blive overskrevet** af vejens automatik (løbelys/animationer ud fra *Udseende*); (3) en signalvej skal være et **samlet symbol**, man kan henvise til og rette i guidens **6 trin** (Symbol · Signaler · Kontakter · Visning · Betjening · Test og gem).

**Vurdering: det kan lade sig gøre** uden at ændre tegningen og uden ny gemt-model for animationer — symbol-opsætningen (`symbol_config`) kan allerede have animationer på dele, logik og tags; vi giver vejen en *virtuel* symbol-identitet.

## Idé
En signalvej `P` får det virtuelle symbol-id `path:<id>` (fx `path:7`). Dens **dele** er alle de elementer (og deres underdele) der ligger på vejen. Brugerens egne rettelser gemmes som en almindelig symbol-opsætning (`symbol_config`, element `path:7`) — **adskilt** fra vejens automatik (`signal_paths.data`). Dermed:
- **Automatikken rører aldrig de manuelle rettelser:** *Gem* på vejen regenererer kun løbelys/animationer fra *Udseende* (som i dag). Symbol-opsætningen ligger ved siden af og lægges *oven på* (højere `position`, så den vinder ved samme slags på samme del).
- **6-trins guiden** kan åbnes for `path:<id>` uden at blive ændret meget: trin 1 viser vejens navn og elementer; trin 2 (signaler) og 3 (kontakter/logik) bruges til egne kilder; trin 4 (visning) lægger ekstra animationer på **vilkårlige dele af vejen**; trin 5 (betjening) er fast *kun visning* (vejen kan ikke betjenes); trin 6 test/gem som i dag.
- **Henvisning:** vejens pseudo-tags (`path:<tegning>:<id>:<grene>`, findes allerede) tilbydes som kilde "Signalvej X — aktiv / gren N" i alle kildevælgere (animationer, logikblokke, alarmer), så andre symboler kan reagere på vejen som på et signal.

## Alternativer (valgt: A)
- **A. Virtuelt symbol `path:<id>` med egen `symbol_config` (valgt).** Genbruger guide, validering, preview, backup og runtime; ingen ændring i tegnings-SVG'en.
- B. Pak vejens elementer ind i en rigtig SVG-gruppe (`<g data-hv-type="signalvej">`). Passer naturligt til guiden, men ændrer tegningen (id'er, grupper, forbindelser, flyt/slet) og bryder signalvejens egen opfattelse af elementerne — for invasivt.
- C. Lad vejen eje alle ekstra animationer i `signal_paths.data` (nyt `manual`-flag pr. animation) og bygge en ny editor. Ny model og nyt UI at vedligeholde, ingen genbrug af de 6 trin.

## Trin
1. **Backend — virtuel symbol (`services/symbols.py`, `services/signal_paths/`)**: `describe_element` for `path:<id>` (type `signalvej`, navn = vejens navn, `parts` = vejens elementer og deres underdele med pid/streg/tekst fra tegningen); `SymbolService.get/put/preview/delete` accepterer `path:<id>` (kun hvis vejen findes; `op` tvinges til `view`; ingen PIN/skriveplan); `orphaned()`/`_symbol_owner`/`_refuse_if_configured` kender virtuelle id'er (de må ikke vises som forældreløse eller afvises); sletning af vejen sletter dens symbol-opsætning (samme transaktion).
2. **Runtime/visning (`drawings._compute`/`config_bindings`)**: bindinger for `path:<id>` med delene = vejens elementer + underdele; lægges efter vejens automatik; logikblokke og pseudo-tags (`logic:…`) og `config_tags` virker som for andre symboler (så `drawing_activity` holder tags polleret).
3. **Kilder**: vejens pseudo-tags i kildelisten (animationer, logik, alarm); hjælpefunktion `path_sources(drawing)` i backend + vist i guiden (trin 2/4).
4. **Frontend — listen (`SpSaved.svelte`)**: pr. vej knappen **Ret som symbol** (åbner `SymbolGuide` for `path:<id>`), og pr. element i vejen **Ret symbol** (den almindelige guide for elementet) og **Skift symbol** (`SymbolReplace`). `DrawEditor`: `guideFor` accepterer `path:`-id'er; guiden i trin 1 viser vejens elementer (klik markerer dem i tegningen).
5. **Overblik/Overview**: ingen ny visning — vejens animationer vises som i dag; de manuelle ligger oveni.
6. **Backup/migrering**: `symbol_config` for `path:<id>` følger med i backup (tabellen er allerede med); gendannelse uden vejen → opsætningen ignoreres og meldes (ingen krasj). Ingen skema-ændring.
7. **Docs**: FEATURES (registreres FØR kodning), manual kap. 07/08 (Signalveje, symbol-guiden), LLM-tillæg, CHANGELOG/RELEASE_NOTES, **v5.4.0**, OTA.
8. **Tests**: backend — virtuelt symbol (gem/hent/valider, tvunget view, slet vejen → opsætning slettet, ikke forældreløs, regenerering af vejen rører ikke opsætningen, bindinger efter vejens automatik, backup-roundtrip); frontend — liste-knapper, guide åbner for `path:`-id, kildevælger viser vejen; **browser** på demo-tegningen: ret en vej som symbol, tilføj en ekstra animation på et rør, gem vejen igen (den ekstra animation består), se Overview. **Reviewer** før commit (data-integritet, nyt id-rum i symbol-API'et).

## Risici
- Id-rummet `path:<id>` kan støde på kode, der antager at et symbol-id er et element i SVG'en (`describe_element`, `orphaned`, `move`, migrering v51, drawing_activity) → kortlægges og dækkes af tests; alt andet end `path:`-id'er er uændret.
- En vej, hvis elementer slettes/omdøbes i tegningen: delene forsvinder fra symbolets dele → animationer på dem vises som advarsel i trin 6 (som for almindelige symboler).
- To veje på samme del: prioritetsreglen i `canvas.ts` afgør som i dag.
- Skrivning/betjening er bevidst ikke med (vejen er passiv visning) — kan udvides senere.

## Afgrænsning / spørgsmål til Jan
- "Auto signalvej tager ikke med" er tolket som: **egne rettelser overskrives aldrig af vejens automatik**. Ret mig, hvis du mente noget andet.
- "Symbolændringer" er tolket som: **ekstra animationer og opsætning på elementerne** (trin 4) samt **Skift symbol** pr. element fra listen.
# Plan: Forbindelser som data i tegningen (v5.3.0) — 2026-11-10 — ✅ udført

Mål: hvad der hænger sammen i en tegning, skal være **gemt**, ikke gættet ud fra afstande, hver gang det bruges. Signalveje, Tjek forbindelser og Ret forbindelser bruger samme gemte forbindelser, så det, man ser grønt i tjekket, er præcis det, en signalvej kan gå igennem.

## I dag
- Kun tegnede rør (`data-hv-pipe`) har gemte ender: `data-hv-from/-to` til et symbols punkt.
- Alt andet — rør-symboler (`roer_l/roer_v`), bøjninger, T-stykker, løse streger og rør til rør — findes ved **geometri** (`contacts()` i `signalpath/graph.ts`: punkter inden for 8 enheder, ende på en anden streg). Det er kilden til de fleste fejl i signalveje og tjekket (tolerancer, kurvepunkter, midtpunkter, skalerede symboler).

## Valgt løsning (af tre)
- **A. En liste på hvert element (valgt):** attributten `data-hv-links="nøgle>andet-id:nøgle;…"` på begge elementer i en forbindelse (nøgler som "ikke i brug" fra v4.22.0: rørets `s`/`e`, symbolpunktets placering, `#i`). Gemmes med tegningen ved Gem kladde/Gem og udgiv (sanitizeren bevarer `data-*`), følger med ved flyt/drej, fortrydes som alt andet.
- B. Én samlet liste i tegningen (fx `<desc id="hv-links">`) — ét sted at se, men skal holdes i trit med sletning/omdøbning af elementer; mere skrøbeligt.
- C. En tabel i backend — adskilt fra tegningens versioner; en ny version kunne passe til forkerte forbindelser.

## Sådan virker det
1. **Bind forbindelser** (ny knap ved Tjek forbindelser): alle forbindelser, geometrien finder i dag, skrives ned som links — ét fortryd-trin. Tjekket viser bagefter tre farver: **grøn** = gemt forbindelse og punkterne mødes, **orange** = gemt, men punkterne er gledet fra hinanden (fx et flyttet rør-symbol; *Ret* flytter enden tilbage), **rød** = åbent punkt.
2. **Automatik i Tegn:** når et rør, et rør-symbol eller et symbol slippes, så et punkt lander på et andet elements åbne punkt (som i dag for tegnede rør), skrives linket med det samme. Ved sletning af et element fjernes dets links fra naboerne (samme fortryd-trin). Indsæt/dupliker fjerner links fra kopien (som `data-hv-from/-to` i dag).
3. **Grafen** (`connectionGraph` + `contacts`): har tegningen gemte links, bruges **kun** de (plus `data-hv-from/-to`); uden gemte links bruges geometrien som i dag (gamle tegninger virker uændret, til man trykker *Bind forbindelser*). Tjekket siger, hvis tegningen ikke er bundet endnu.
4. **Signalveje:** rutesøgningen bruger grafen — ingen ændring i guiden; den går kun gennem gemte forbindelser, når tegningen er bundet.
5. **Ret forbindelser** (v4.19.0) skriver også linket, når den sætter to ender sammen.

## Trin
1. `scada-core.js`: læs/skriv `data-hv-links` (nøgler, symmetrisk), `bindConnections()` (fra geometrien), auto-link ved slip, oprydning ved slet/indsæt/dupliker, graf-noder med `links`.
2. `signalpath/graph.ts`: `contacts()` bruger links, når de findes; `connectionCheck` med status `ok`/`drift`(gledet)/`open`/`isolated` + test (rene funktioner).
3. `DrawEditor.svelte`: knappen *Bind forbindelser*, besked om ubundet tegning, farverne i tjekket.
4. Manual (kap. 07/08), LLM-tillæg, CHANGELOG/RELEASE_NOTES/FEATURES, **v5.3.0**, OTA.
5. Tests: graf/tjek med links (vitest), sanitizer bevarer `data-hv-links` (pytest); **browser** på demo-tegningen: Bind → alt grønt/rødt som før; flyt et rør-symbol → orange; Ret → grøn; signalvej finder samme vej før/efter binding.

## Risici
- Et link til et punkt på et symbol, hvis punkter senere rettes i symbol-editoren: nøglen passer ikke længere → vises som orange/åbent i tjekket og kan bindes igen.
- Store tegninger: `bindConnections` kører den eksisterende geometri én gang (ms for ~200 elementer).
- Backend skal ikke ændres (kun en test af sanitizeren).

# Plan: Symbolstandard fase 8b — fjern den gamle symbolmodel (udført som v5.1.0 efter Jans valg) — 2026-11-10 — ✅ udført

Mål: ét sted at sætte et symbol op — **guiden (symbol_config)**. Bibliotekssymboler (rødder med `data-hv-type`/`data-hv-auto`) skal ikke længere kunne styres af den gamle model. Almindelige bindinger på elementer, der *ikke* er bibliotekssymboler (tekster, figurer, egne SVG-elementer), og automatiske bindinger efter tag-navn på dem **bevares** — de er ikke den gamle symbolmodel.

## Den gamle model i dag (kortlagt)
| Del | Hvor |
| --- | --- |
| Automatiske bindinger fra `data-hv-auto`/`data-hv-part` (betjeningssymboler), når elementets id/navn er et tag | `DrawingService._compute` (symbol_specs → `symbol_bindings`), `bindings.symbol_bindings`, `svg_sanitize.symbol_specs` |
| "Bind symbol til tag" (skriver bindinger for et betjeningssymbol) | `DrawingService.bind_symbol` + `db.set_symbol_bindings`, `POST …/bind` i `api/drawings.py` |
| Eksplicitte bindinger på symbolets rod og dele | tabellen `bindings`; ignoreres allerede, når symbolet har en opsætning (`covered`), ellers gælder de |
| Konvertering (forslag ud fra den gamle model) | `symbol_convert.py`, `GET …/suggest`, `POST /api/drawings/convert-symbols`, `DrawingService.legacy_bindings`, `_compute(legacy=True)` |
| UI | `SymbolConvert.svelte` (panel under Tegninger), guidens "Konvertér", "Avanceret: rå bindinger" for symboler under Bindinger, `elementTree.ts` (`spec`/`writes`), `scada-core.js` (`interactive`) |
| Biblioteket | `symbols.ts` lægger `data-hv-auto`/`data-hv-part` på betjeningssymbolerne; `library.py` bevarer dem ved indsættelse |

## Valgt fremgangsmåde (af tre)
- **A. Automatisk migrering ved opgradering + fjern (valgt).** Ved opstart konverteres alle bibliotekssymboler med gamle bindinger (samme regler som "Konvertér alle"); det, der ikke kan konverteres, listes i en rapport (Meddelelser/Status og loggen); derefter slettes de gamle bindinger på symbolerne, og koden fjernes. Passer til et udviklingssystem og giver én model med det samme.
- B. Spær opgraderingen, til teknikeren selv har trykket "Konvertér alle" — mere sikkert i drift, men unødvendigt her.
- C. Behold den gamle model skrivebeskyttet — fjerner ikke gælden.

## Trin
1. **Migrering (skema 17, ved opstart i app-laget, efter at tjenesterne er bygget):** automatisk backup først (samme som før en OTA); pr. tegning og bibliotekssymbol uden opsætning, med gamle bindinger: lav forslaget og gem det via `SymbolService.put` (fuld validering) → `converted`; ellers `manual` med grund. Slet derefter eksplicitte bindinger på bibliotekssymbolernes rod og dele. Rapporten gemmes i `meta` og vises i Tegn › Meddelelser og på Status, til den ryddes. Konverteringsreglerne flyttes til `services/migrations/v6_symbols.py` (kun til migreringen og gendannelse af gamle backups).
2. **Runtime/visning:** `_compute` mister symbol-delen (`symbol_specs`/`symbol_bindings`) og `legacy`; bindinger på bibliotekssymboler afvises ved oprettelse (400: "Brug guiden"); `legacy_bindings`, `bind_symbol`, `set_symbol_bindings`, `convert-symbols` og `…/suggest` fjernes.
3. **Biblioteket:** betjeningssymbolerne får ikke længere `data-hv-auto`/`data-hv-part` (dele genkendes via `data-hv-pid` som de øvrige); eksisterende attributter i tegninger er harmløse og ignoreres.
4. **Frontend:** fjern `SymbolConvert.svelte`, guidens "Konvertér", "Avanceret: rå bindinger" for symboler, `spec`/`writes` i elementTree og `interactive` i scada-core; Bindinger-siden viser for et symbol kun guiden.
5. **Backup:** gendannelse af en ældre backup kører samme migrering på de gendannede data.
6. **Docs:** SYMBOLSTANDARD_IMPLEMENTERING.md afsnit 11 (udført), manual (kap. 09/10 — Bindinger og guiden), LLM-tillæg, ARCHITECTURE.md, FEATURES (symbolstandarden done), CHANGELOG/RELEASE_NOTES, **v6.0.0**, OTA.
7. **Tests:** migrering (konverteret/manuel/rapport/idempotent/backup først), at bindinger på bibliotekssymboler afvises, at almindelige bindinger og tag-navne-automatik på ikke-symboler virker som før, gendannelse af gammel backup; frontend-tests for guiden/Bindinger; **browser:** demo-tegningen før/efter opgradering (Overview ser ens ud for de konverterede symboler). **Reviewer** før commit (data-integritet, PLC-skrivninger: betjening flyttes fra gamle klik-bindinger til guidens skriveplan).

## Risici
- Symboler, der ikke kan konverteres (fx kun "Gå til tegning" eller ugyldige forslag), mister deres gamle opførsel → står i rapporten, sættes op i guiden. Backup tages først.
- Betjening (klik) på konverterede betjeningssymboler går nu gennem guidens skriveplan: afprøves mod mock-PLC (skift, puls, setpunkt).
- Irreversibelt i databasen — tilbagerulning = gendan backuppen fra trin 1.

# Plan: Signalveje 4 — signalvejen som selvstændigt runtime-objekt (v5.0.0, MAJOR) — 2026-11-10 — ✅ udført

Beslutning (Jan 2026-11-10): **mulighed C**. En signalvej skal være et objekt i sig selv, også i fremtidige versioner. Udviklingssystem: ingen migrering af gamle veje — de slettes (og deres efterladte blokke/animationer ryddes én gang).

## Problemet i dag
Ved *Gem* "kompileres" vejen ind i symbolernes opsætning: logikblokke (OG-kæder, ELLER pr. gren) på et ejer-symbol (højst 8 blokke) og en animation på hver del med blokken som kilde. Det kræver bogføring (`_strip`, `_owned`, `_check_refs`, konflikter/409, `created`), binder vejen til ejer-symbolets id, og en ændring af et symbol kan bryde vejen (eller omvendt).

## Ny model
- **Lagring** (`signal_paths`, samme tabel, ny `data`-form, `SCHEMA_VERSION` 16): `{start, ends[], branches: [{conds: [{src, neg, cmp, value}] }], elements: [{element, branches[], parts: [{part, type, params, when, reverse?}]}], style, ui}` — vejen er ét objekt; **intet skrives i symbolernes opsætning**.
- **Runtime** (`services/signal_paths/runtime.py`, kaldt fra `SymbolRuntime.evaluate()` hvert tick):
  - gren aktiv = OG over grenens betingelser (samme vurdering som logikblokkenes indgange, `symbols.evaluate_logic`-reglerne; dårlig kvalitet → ikke aktiv);
  - pseudo-tags `path:<tegning>:<id>:<grene>` (fx `…:0`, `…:0,1` = ELLER over grenene) skrives i LiveCache som bool med kvalitet;
  - signaturen (`_current_signature`) får `signal_paths` med, så en gemt/slettet vej læses straks.
- **Overview**: `DrawingService.view()` lægger vejens animationer på som almindelige bindinger med pseudo-tagget som kilde (`{element, tag, anim, params:{when …}}`), så `canvas.ts`/`animate.ts` viser dem uden ændringer; prioritet mod delens egne animationer følger de eksisterende regler (`when`).
- **Adgang**: `tags_for_drawing()` medtager vejenes pseudo-tags (som logik-pseudo-tags), så WS-filteret sender dem til dem, der må se tegningen.
- **Ingen grænser fra ejer-symbolet**: højst 32 betingelser pr. gren, 4 grene, 200 elementer, 16 animationer pr. element (som i dag).

## Trin
1. Backend-model og API: ny `valid_data`/Pydantic-body; `service.save/delete/list/info` gemmer kun objektet (fjern `blocks.py`, `_strip`, `_owned`, `_check_refs`, 409-konflikter, `created`); `info` uændret for guiden.
2. Runtime: `runtime.py` (ren funktion `evaluate_paths(paths, values) → {pseudo-tag: (bool, kvalitet)}` + test), koblet ind i `SymbolRuntime` (load ved reload, skriv i cache ved evaluate), signatur udvidet.
3. View og adgang: bindinger i `view()`, pseudo-tags i `tags_for_drawing()`/scope; Overview skal ikke ændres (verificeres i browseren).
4. Migrering (schema 16): fjern gamle vejes efterladenskaber én gang (logikblokke med navn "Signalvej: …" og animationer med kilde i dem) og slet de gamle rækker. Backup: ny `valid_data`; gamle backups med signalveje springes over med en note.
5. Frontend-guiden: gem-body i den nye form (betingelser pr. gren i stedet for `branches` på hver betingelse; animationer pr. del som nu fra `pathLook`); fjern 409-"Erstat"-dialogen og "har allerede løbelys"-advarslen; resten (rutesøgning, klik, via, vend flowet, udseende) uændret.
6. Observability: Status/log — antal veje, aktive grene, evalueringsfejl; logning ved gem/slet (som nu).
7. Docs: manual kap. 08 (hvordan vejen virker nu: ingen ændring i symbolerne, ingen "erstat"), LLM-tillæg, ARCHITECTURE.md (signalvej som runtime-objekt), FEATURES/CHANGELOG/RELEASE_NOTES, version **5.0.0** (schema), OTA.
8. Tests: backend (gem/ret/slet, runtime-evaluering inkl. grene/ELLER/kvalitet, view-bindinger, scope, migrering, backup), frontend (guide gem-body), browser: en vej med pumpe + ventil på demo-tegningen, skift tag-værdier i mock-PLC og se løbelyset tænde/slukke pr. gren. **Reviewer**-agent før commit (PLC-data, adgang, data-integritet).

## Berørte filer
backend: `services/signal_paths/*` (blocks.py udgår, ny runtime.py), `api/signal_paths.py`, `services/symbol_runtime.py`, `services/drawings.py` (view), `services/symbols.py` (tags_for_drawing), `services/scope.py` (hvis nødvendigt), `storage/db.py` (schema 16, migrering), `services/backup.py`, `services/assistant*` (uændret), tests. frontend: `lib/SignalPathGuide.svelte` (gem-body, ingen 409), evt. `lib/pathLook.ts`; Overview uændret. docs.

## Risici
- Prioritet mellem vejens og delens egne animationer på samme del: afprøves (fx rør med egen farve + vejens løbelys).
- Pseudo-tags pr. kombination af grene: højst 2^4−1 = 15 pr. vej; kun de brugte oprettes.
- Bindinger fra veje i Bindinger-siden: vises ikke (ejes af vejen) — kan komme som læs-kun liste senere.
- Uden for denne plan: B (forbindelser som data i tegningen) og guidens forenkling (A) — kan tages bagefter.

# Plan: Refaktorér signalvejs-koden (v4.15.1, ingen funktionsændring) — 2026-11-09 — ✅ udført (trin 1–5; guidens trin 2 og 5 blev i komponenten)

Mål: gøre signalvejen overskuelig uden at ændre adfærd. Nu: `SignalPathGuide.svelte` 890 linjer (~40 state-variabler, 36 funktioner, 5 trin, klik/via/pick/AI/gem blandet), `signalPath.ts` 482 linjer (graf, rutesøgning, retning, spørgsmål, svar i én fil), `signal_paths.py` 464 linjer.

## Trin (hvert trin: tests grønne før næste; ét commit pr. trin-gruppe)
1. **Sikkerhedsnet**: frontend-tests er dækkende (guide 12, flow 21, look 7); backend `test_signal_branches.py`. Ingen ny adfærd.
2. **`signalPath.ts` deles** i `signalpath/` : `graph.ts` (typer, graphKey, contacts, onLine, roleOf), `route.ts` (shortest, findPaths, findViaPath), `flow.ts` (portAt, passAllowed, orient, flowsFor, wayUsed), `net.ts` (describe, describeNet, questionsOf), `answers.ts` (conditionsFrom, answerFrom, suggestAnswer, pickNext). `signalPath.ts` bliver en re-export, så imports og tests virker uændret.
3. **Guiden deles**: logik ud af komponenten i en store `signalGuideState.svelte.ts` (via/klik/pick/forced/cands/net/recompute) og små komponenter: `SpStart.svelte` (trin 1), `SpRoute.svelte` (trin 2), `SpConditions.svelte` (trin 3), `SpLook.svelte` (trin 4), `SpSave.svelte` (trin 5) + `SpList.svelte` (gemte veje). `SignalPathGuide.svelte` bliver ~150 linjer, der binder dem sammen.
4. **Backend `signal_paths.py`**: del i `signal_paths/` (`chains.py` blokke/OR-kæder, `anims.py` animationer/strip/owned, `validate.py` valid_data, `service.py`); offentlig API uændret.
5. Død kode og dubletter ryddes undervejs (fx gentagne `rowOfNet`/`net?.rows.find`). Ingen nye afhængigheder.

## Berørte filer
`frontend/src/lib/signalPath.ts`, `SignalPathGuide.svelte` (+ nye filer), `backend/app/services/signal_paths.py`, ARCHITECTURE.md (kort note), CHANGELOG/RELEASE_NOTES, version 4.15.1 / b0369.

## Risici
- Svelte 5 runes i delt state-fil: kræver `.svelte.ts` og getters; komponenttests fanger regressioner (klik, pick, via).
- Import-stier: re-export holder dem stabile.
- Visuel verifikation i browseren efter trin 3 (layout uændret).

# Plan: Signalveje 3 — klik i tegningen: tilføj rør til vejen, skift en 3-vejsventils vej, og "gå via" ekstra symboler (v4.15.0) — 2026-11-09 — ✅ v4.15.0

Ønsker fra Jan (2026-11-09): (1) **tryk på de enkelte forbindelser** i tegningen og på den måde tilføje dem til signalvejen; (2) **tryk på symboler med flere veje** (3-vejsventil) og skifte mellem symbolets muligheder; (3) **ekstra symboler** i listerne skal have de samme valg som start og slut (rullemenu, *← valgt* og klik i tegningen). *(Punktet om *← valgt* under *Flere slutpunkter* er allerede lavet i v4.14.0.)*

## Design
1. **Gå via** (pr. gren): en liste af elementer, vejen skal gå igennem — rør, symboler, hvad som helst på vejen. Vejen beregnes som start → via 1 → via 2 → … → slut (korteste vej mellem hvert par, i den rækkefølge elementerne ligger fra start). Retningen, ventilvalg og ind/ud virker som før (de gælder hele den samlede vej). Findes der ingen vej gennem et via-punkt, står der hvilket, og vejen vises uden det.
2. **Klik i tegningen** (en tilstand i guidens trin 2: *Ret vejen i tegningen*, slået til som standard, mens trin 2 er åbent):
   - klik på et **rør eller et symbol, der ikke er på vejen** → det tilføjes som via-punkt (vejen omlægges, så den går igennem det);
   - klik på et **via-punkt** (eller *✕* i listen) → det fjernes igen;
   - klik på en **3-vejsventil på vejen** → ventilens vej skifter: *automatisk → AB → A → AB → B → automatisk …*; tegningen viser den nye vej med det samme, og en kort besked siger hvilken vej der er valgt;
   - **Esc** eller *Færdig* slår tilstanden fra (så almindeligt valg i tegningen virker igen).
   - Med flere grene gælder et klik på en 3-vejsventil den gren, der er markeret i listen (klik på en grens overskrift for at vælge den; gren 1 som standard); et via-punkt tilføjes til grenen, som røret ligger nærmest.
3. **Ekstra symboler (gå via)** i trin 1: en række *Gå via* med de samme valg som Start og Slut — rullemenu, *← valgt* og *Vælg på tegningen* — og *✕* pr. punkt.
4. **Gemmes** i `ui.via` (så *Ret* viser dem igen). Backend uændret (via er kun en hjælp til at finde vejen; selve vejen gemmes som før).

## Trin
1. `lib/signalPath.ts`: `findViaPath` (start → via → slut, sorteret efter afstand fra start; første ikke-mulige via-punkt returneres), enhedstests.
2. `SignalPathGuide.svelte`: via-liste, klik-tilstand (valg af rør/symbol, 3-vejsventil-vejskift), gren-valg, rækken *Gå via*; komponenttest af klik-forløbene.
3. Manual (kap. 08) og LLM-tillæg, skærmbillede, docs, version 4.15.0, OTA.

## Risici
- Et klik på et rør skal ikke forveksles med at vælge det til anden brug i Tegn: tilstanden er kun til, mens guidens trin 2 er åbent, og vises tydeligt (en bjælke øverst: *Klik på rør og symboler for at ændre vejen — Esc afslutter*).
- Via-punkter kan gøre vejen lang eller umulig → besked med navn, og vejen vises uden det punkt.
- Grafen ændres, mens man klikker (rev-opdatering): via-punkter, der forsvinder fra tegningen, fjernes stille og meldes.

---

# Plan: Signalveje 2 — valgfrie animationer, grene og porte på 3-vejsventiler (v4.13.0 + v4.14.0) — 2026-11-09 — godkendt (Jan) — leverance 1 (grene, ind/ud, veje, interaktiv guide) ✅ v4.13.0; leverance 2 (valg af animationer) ✅ v4.14.0

Ønske fra Jan (2026-11-09): i *Tegn › Signalveje* kan man ikke (1) vælge hvilke animationer vejen skal give, (2) bestemme hvad vej signalet tager ved T-kryds, eller (3) bestemme, hvordan en 3-vejsventils dele skal stå. Svar: **alle animationstyper, forskellige pr. element-type · vejen må dele sig · vælg ind- og udgang på 3-vejsventilen**.
Tillæg (Jan, samme dag): **VVS-symboler skal have en ind- og udgang**, så fx en pumpe alene bestemmer retningen gennem systemet, når den sidder i en signalvej.
Tillæg 2 (Jan): **for 3- og 4-vejsventiler m.fl. skal man kunne definere, hvad der er fælles**, fx AB → A eller AB → B.
Tillæg 3 (Jan): **ved beregningen af vejen skal man kunne skifte flervejs-ventilernes vej og se en ny signalvej; først når vejen er rigtig, sætter man animationer op og gemmer.**

## Nu (v4.2.0–v4.5.0)
- Kun **løbelys**, kun på rør, bøjninger og T-stykkets ben (`flowsFor`). Ventiler, pumper og 3-vejsventiler får ingen animation, kun et spørgsmål om hvornår de leder.
- Vejen er **lineær** (start → slut); T-kryds følger den fundne vej (op til 3 forslag).
- Alle betingelser OG'es i én logikblok på det første rør; alle rør lyser kun, når alle er sande.

## Design
1. **Animationer pr. element-type** (data: `anims` pr. gruppe — rør, ventil, pumpe, kontakt, 3-vejsventil, andet):
   - typer: *Løbelys* (som nu), *Farve* (til/fra-farver), *Blink*, *Gennemsigtighed*;
   - parametrene er de samme som i symbolguidens trin 4 og valideres af `validate_config`;
   - ikke-rør vælger del: *Hele symbolet* eller en navngiven del (fx *Port A*);
   - en gammel vej uden `anims` får løbelys på rør, præcis som i dag.
2. **Grene** (vejen må dele sig): ét **startpunkt** og op til **4 slutpunkter**.
   - Vejen er foreningen af de korteste veje start → hver slut; fælles stykker (stammen) deles.
   - Et T-stykke lyser de ben, som mindst én gren bruger, hver i sin retning.
   - **Betingelser:** gren *i* = OG af betingelserne på dens vej. Et stykke lyser, når **mindst én** gren, der går igennem det, er aktiv (ELLER). For én gren er det præcis som i dag.
   - Logikblokke: en OG-kæde pr. gren og en ELLER-blok til fælles stykker; højst 8 blokke på ejeren (ellers en klar fejl).
   - Tegn markerer hver gren med sin farve.
3. **3-vejsventil:** ind- og udgang (fx AB → A) aflæses fra, hvor vejen rører ventilens tilslutninger, og kan rettes (se punkt 7: vejene er en del af symbolet). Animationen lægges på de valgte porte (`port_ab`, `port_a`) med retning ind → ud. Betingelsen er ventilens position (eller et tag). En anden signalvej kan bruge AB → B.
4. **Ejerskab og oprydning:** `data.elements[].anims` husker det, vejen har lagt på, så *Ret* og *Slet* fjerner præcis det og intet af brugerens egne animationer (`_strip` og konfliktkontrollen udvides fra kun løbelys til alle typer).
5. **Bagudkompatibel:** `data` er JSON (ingen skemaændring i databasen). Gamle veje, backup og gendannelse virker uændret (`valid_data` accepterer begge former).

6. **Ind og ud på VVS-symboler** (Jans tillæg):
   - Hvert tilslutningspunkt får en **rolle**: *ind*, *ud* eller *begge* (standard). Rollen gemmes sammen med punktet i symbolbiblioteket (`symbol_ports`: `[fx, fy, rolle]`; gamle punkter uden rolle = *begge*) og kan rettes under *Symboler › Tilslutningspunkter*.
   - Standarder for de indbyggede VVS-symboler: **pumper** (pumpe, varmepumpe, motor) har én indgang og én udgang efter den tegnede retning; **kontraventil** ind/ud; ventiler, T-stykker og 3-vejsventiler *begge* (3-vejsventilen styres af valget ind/ud i punkt 3).
   - Rollen følger symbolet, når det drejes eller spejles (samme omregning som punkterne).
   - **Kun i en signalvej:** retningen bruges, når symbolet sidder i en signalvej. Resten af tegningen ændres ikke.
   - Vejen får sin **retning fra symbolerne**: sidder der en pumpe (eller kontraventil) på vejen, løber flowet fra dens udgang mod resten, uanset hvilket symbol du valgte som start. Vælger du start og slut i omvendt rækkefølge, vendes løbelyset automatisk.
   - Er symbolerne uenige (to pumper modsat hinanden, en kontraventil mod strømmen), siger guiden det med navn i stedet for at gætte; Gem er stadig muligt, når du bekræfter.
   - Med grene: en pumpe på stammen giver retningen til alle grene efter den. Uden noget retningsgivende symbol på vejen gælder start → slut, som nu.

7. **Fælles port og veje på flervejs-ventiler** (Jans tillæg 2):
   - Tilslutningspunkterne får et **navn** (A, B, AB, P, T …), og et eller flere punkter kan markeres **fælles**. Punkterne og navnene rettes under *Symboler › Tilslutningspunkter*.
   - Symbolet får en liste af **veje**: de forbindelser, ventilen kan lave, fx 3-vejs: *AB → A* og *AB → B*; 4-vejs: fx *P → A*, *P → B*, *A → T*, *B → T*. Som standard laves vejene automatisk: hver ikke-fælles port parres med hver fælles port; vejene kan rettes.
   - Standarder for de indbyggede symboler: 3-vejs motorventil (begge varianter) har AB som fælles og vejene AB → A og AB → B; en 4-vejsventil, hvis den findes i biblioteket, får to fælles porte.
   - I signalvejen vælger du for hver flervejs-ventil **hvilken vej** den bruges til (listen over symbolets veje; forvalgt efter, hvor vejen rører ventilen). Kun de to porte i den vej lyser, og betingelsen bliver ventilens position for netop den vej. En anden signalvej kan bruge den anden vej gennem samme ventil.
   - Vælger du en vej, der ikke passer til, hvor vejen faktisk rører ventilen, siger guiden det.

8. **Arbejdsgang i guiden** (Jans tillæg 3): vejen fastlægges først, udseendet bagefter.
   1. **Start og slutpunkter** (klik i tegningen, som nu).
   2. **Vejen:** beregnes med det samme og vises i tegningen (en farve pr. gren). Hver flervejs-ventil på vejen har en liste over sine veje (*AB → A*, *AB → B* …). **Skifter du ventilens vej, beregnes vejen forfra med det samme** og tegningen viser den nye vej; ventilens valg tvinger vejen igennem netop de to porte. Ligger der ingen vej med det valg, står det der i stedet for en tom tegning. De øvrige forslag (op til 3 pr. slutpunkt) kan stadig vælges.
   3. **Lås vejen:** *Brug denne vej* låser vejen; først da åbnes de næste trin. Vil du ændre vejen bagefter, går du tilbage (animationer og betingelser, der stadig passer, bevares).
   4. **Betingelser:** hvornår går der flow (ventiler, pumper, kontakter; flervejs-ventilen pr. valgt vej).
   5. **Animationer** pr. element-type (punkt 1) med forhåndsvisning.
   6. **Navn og gem.**
   - Beregningen (`findPaths`) får de valgte veje som krav (`forced`: ventil → vej), så den kun går gennem de valgte porte; den kører i browseren og er hurtig nok til at køre ved hvert skift.

## Trin
1. `lib/symbolPorts` + navne, fælles og veje på punkter; `lib/symbolPorts` + `lib/signalPath.ts`: roller på punkter (standarder, omregning ved drejning), retning fra pumpe/kontraventil, `lib/signalPath.ts`: net med flere slutpunkter (`mergePaths`), grene og betingelser pr. gren, porte for 3-vejsventiler, animationsvalg (`ANIM_CHOICES`) — enhedstests.
2. Backend `services/signal_paths.py` + `api/signal_paths.py`: ny krop (ends, branches, anims), blokke pr. gren + ELLER, ejerskab/oprydning, validering, backup-kontrol — tests. De eksisterende tests skal bestå uændret.
3. `SignalPathGuide.svelte` (guiden): arbejdsgangen i punkt 8 — *Start og slutpunkter* → *Vejen* (ventilvalg og ny beregning, farver pr. gren) → *Brug denne vej* → *Betingelser* → *Animationer* → *Navn og gem*.
4. Hjælperens forslag (v4.3.0) følger med (spørger pr. gren). Manual (kap. 08 og LLM-tillæg), skærmbilleder, docs.
5. Tests, build, **set i browseren** (T-kryds med to grene, 3-vejsventil AB → A/B, farve og blink), reviewer (skriver symbolopsætninger), version 4.13.0, OTA.

## Risici
- Blokgrænsen (8) og 4 indgange pr. blok kan ramme store net → klar fejlbesked og forslag til færre betingelser.
- Flervejs-ventiler i en tegning, der er tegnet af løse figurer uden symbol, har ingen navngivne porte → vejen kan ikke vælges; guiden siger, at symbolet skal sættes ind fra biblioteket.
- Retning ud fra et symbols punkter hænger på, at punkterne er rigtige: findes der ingen rettede punkter, bruges de automatiske, og roller kan da ikke afgøres → vejen bruger start → slut og siger det.
- Samme del med to veje med hver sin retning (modsat flow) → advarsel, første vej vinder.
- Ændring af en del, som brugeren selv har animeret → eksisterende konfliktdialog ("erstat?") udvides til alle typer.
- Stor ændring i én fil (guiden) → bygges i to commits: (a) grene og 3-vejsventil, (b) animationsvalg.

---

# Plan: Manualen gennemgås — mere tekst, flere skærmbilleder, pænere indeks og en skjult LLM-manual (v4.9.0) — 2026-11-07 — godkendt (Jan) — ✅ v4.9.0

Ønske fra Jan: flere afsnit mangler skærmbilleder (fx logikblok), "De seks trin" har næsten ingen tekst, og den lokale LLM fejler, når manualen er for tynd. Indekset skal være pænere. Derudover (Jan): **en særlig manual til LLM'en, som brugerne ikke ser, men som holdes opdateret, når den store manual ændres.**

Måling (`manualstat.py`): 25.132 ord og 79 billeder. Ca. 35 afsnit har under 60 ord. Kap. 08 (Forbindelser) og 15 (Fejlfinding) har 0 billeder; i kap. 13 (System) mangler billeder til Status, Notifikationer, Integrationer, Certifikater og Hjælper.

## Valg: hvordan får LLM'en nok tekst? (3 alternativer)
1. **Kun skrive den store manual tykkere.** Det er godt for brugerne, men LLM'en har brug for korte "sådan gør du"-svar og synonymer. Det gør den læsbare manual tung.
2. **En separat LLM-manual, skrevet uafhængigt.** Den kan løbe ud af trit med den rigtige manual og give forkerte svar, og det var præcis fejlen med "symbol bag et andet".
3. **Valgt: en skjult LLM-manual, som *kompileres automatisk* ud fra den store manual (præcisering fra Jan).** Ingen håndskrevet kopi; den bygges ved hver build/OTA-pakke og er derfor altid opdateret.
   - Kompileren er `tools/compile-llm-manual` (Python i `backend/app/services/manual_compiler.py`, så serveren også kan bygge ved opstart). Den skriver `llm-manual.json`.
   - Hver del er selvstændig:
     - Den har **sti-kontekst** ("Tegn › Vælg › Symbol bag et andet").
     - **Tabeller er foldet ud** til sætninger, så "De seks trin" bliver ét stykke pr. trin.
     - Billedernes alt-tekster og knapnavne er med.
     - Interne links er slået op til navnet på målafsnittet.
     - Der er nøgleord/synonymer.
   - Hver del har en **reference** til afsnittet i den store manual (`07-tegn.md#anker`), så hjælperen altid kan henvise brugeren dertil.
   - Valgfrie **tillæg** i `manual/llm/*.md`: korte spørgsmål og svar pr. afsnit, bundet med `kilde:`+sha. En test fejler, når kildeafsnittet ændres, så tillæggene ikke kan løbe ud af trit.
   - Brugerne ser kun den store manual.

## Trin
1. **Store manual, tekst.** Udvid de tynde afsnit, størst først:
   - kap. 10 "De seks trin" deles i *Trin 1–6* med egen tekst og eget billede pr. trin;
   - kap. 10 "Logikblokke";
   - kap. 03 Alarmer;
   - kap. 08 Forbindelser;
   - kap. 13 System;
   - kap. 02 og 04.
2. **Skærmbilleder.** Udvid `tools/manual-screenshots.mjs` med:
   - logikblok-editoren;
   - De seks trin (ét billede pr. trin);
   - Forbindelser/Signalveje;
   - Hjælper-panelet;
   - System › Status/Notifikationer/Integrationer/Certifikater/Hjælper;
   - Alarmer › Forklar.

   De tages på den lokale testserver med demo-data. Den eksisterende test sikrer, at ingen billeder mangler eller er forældreløse.
3. **Indeks.** Manual-siden får:
   - kapitler grupperet (*Kom i gang · Drift · Opsætning · Tegning · System · Reference*) med ikon og en kort undertekst;
   - kun det aktive kapitels underafsnit foldet ud;
   - markering af det afsnit, man læser (scroll-spy), og "Til toppen";
   - søgning med resultater, der viser kapitel og uddrag;
   - på smal skærm: indekset som en udfoldelig menu.
4. **Kompileret LLM-manual.**
   - `manual_compiler.py`: opdeling, tabel→tekst, sti-kontekst, links og referencer. Den har tests.
   - `assist_knowledge` søger i de kompilerede dele og svarer med reference til den store manual.
   - Kompileringen køres i `make-package.sh` og ved opstart, hvis manualen er nyere.
   - Tillæg med sha-test, og de første tillæg skrives til spørgsmål, der fejlede.
5. **Måling.** `evalsearch.py` udvides til ca. 40 typiske spørgsmål, og træfprocenten (top 3) måles før og efter. Til sidst testes nogle spørgsmål mod Ministral på demoen.
6. Tests og build, visuel kontrol af Manual-siden (bred og smal), docs, version og OTA.

## Berørte filer (ca.)
- `frontend/src/manual/*.md` og ny `frontend/src/manual/llm/`
- `frontend/public/manual/*.png`
- `frontend/tools/manual-screenshots.mjs`
- `frontend/src/pages/Manual.svelte`
- `backend/app/services/assist_knowledge.py` og en ny test
- `deploy/install.sh` og `deploy/make-package.sh`

## Risici
- Det er meget tekst. Det deles i 2–3 commits (tekst+billeder → indeks → LLM-manual), så hver del kan ses for sig.
- sha-testen kan føles irriterende ved små rettelser i den store manual. Sync-scriptet gør det til ét kald, og det er netop meningen, at man skal se efter.
- Skærmbillederne skal tages med samme data og vinduesstørrelse som de eksisterende, så billederne ligner hinanden.

---

# Plan: Vælg LLM-model fra en liste — hentes fra GitHub releases (v4.4.0) — 2026-11-07 — godkendt (Jan: "to-tre varianter på GitHub") — ✅ v4.4.0

Ønske fra Jan: en administrator skal kunne vælge en model fra en liste under *System › Hjælper* uden selv at hente filer fra Hugging Face. LLM-pakkerne udgives derfor som **GitHub releases** i projektets repo, som SCADA-opdateringerne allerede er.

## Valg
| | Alternativ | + | − |
|---|---|---|---|
| **A** | **Færdige LLM-pakker som GitHub releases** (tag `llm-<model>-<llama-build>`), hentet af serveren | samme sted og samme sikkerhed som OTA (SHA256 i releasen); én kendt kilde; virker uden Hugging Face | GitHub tillader højst 2 GiB pr. fil, så pakkerne deles i dele |
| B | Serveren henter llama.cpp og modellen direkte fra GitHub og Hugging Face (`llm-models.json`) | ingen udgivelse | to eksterne kilder, Hugging Face-adresser kan forsvinde, og pakken bygges på serveren |
| C | Kun upload som nu | intet internet | det Jan vil undgå |

**Valg: A.** Upload (C) bevares til lukkede net.

## Trin
1. **Udgivelse:** `deploy/publish-llm-release.sh <arkitektur> <model-id>`:
   - bygger pakken med `make-llm-package.sh` og deler den i dele på 1,9 GB (`….tar.part01`, `….part02`);
   - lægger `….tar.sha256` (hele pakken) og `….tar.json` (manifest: model, størrelse, dele) ved siden af;
   - `gh release create llm-<model>-<build> --latest=false` (prerelease), så SCADA-opdateringerne (`/releases/latest`) aldrig forveksles med en LLM-pakke.
2. **Katalog:** `deploy/llm-models.json` følger med SCADA'en og er listen i UI'et: navn, størrelse, licens, anbefalet RAM/profil og release-tag pr. arkitektur. Kun modeller, der passer til profilen og arkitekturen, kan vælges.
3. **Backend** (`services/llm_catalog.py` + `api/assist.py`):
   - `GET /api/assist/catalog`: listen med status pr. model (installeret / kan hentes / passer ikke til hardwaren).
   - `POST /api/assist/download {model}` (admin):
     - tjekker diskplads (pakke + 1 GB + reserve);
     - henter delene fra GitHub (kun `github.com` og GitHubs download-domæner, ingen proxy fra miljøet, tidsgrænse) og sætter dem sammen i én fil, mens SHA256 beregnes;
     - sammenligner med `.sha256`;
     - klargør pakken som en uploadet pakke (`stage`, samme kontrol);
     - foregår i baggrunden med fremdrift (bytes/s, del x af y) og kan afbrydes. Audit `assist.download`.
   - Installation som i dag: *Installér og slå til* (root-hjælperen tjekker SHA256 igen).
4. **Frontend** (*System › Hjælper*): listen over modeller med størrelse, licens, anbefaling og hastighedsskøn; **Hent og installér** med fremdrift og **Afbryd**. *Upload LLM-pakke …* står under *Lukket net*.
5. **Første udgivelser:** Qwen3.5-4B og Qwen3-4B-Instruct-2507 til x86_64 (begge Apache-2.0; licenserne ligger i pakken). aarch64 (Pi 5) senere.
6. Manual, tests (falsk GitHub via MockTransport: dele, forkert SHA, for lidt plads, afbrudt), review, OTA og afprøvning på demo-VM'en.

## Risici
- **2 GiB pr. fil på GitHub:** løses med dele. Samlet SHA256 tjekkes to gange (SCADA og root-hjælperen).
- **Disk** (demo-VM: 10 GB): delene skrives direkte i den samlede fil, så den kun fylder én gang. Under installationen skal der være plads til både pakken og den udpakkede model. Det tjekkes før hentning, og ellers vises: *fjern den installerede model først*.
- **Kompromitteret GitHub-konto:** samme niveau som OTA i dag (SHA256 fra samme release). Noteres i manualen.
- **Licens:** Apache-2.0 tillader videreudgivelse med licensteksten, og den ligger i pakken (`LICENSES/`).

---

# Plan: Signalvej i Tegn (LLM-hjælper fase 2) — 2026-11-07 — godkendt (Jan) — fase 2a ✅ v4.2.0 — fase 2b ✅ v4.3.0

Mål: brugeren vælger **start** og **slut** i en tegning. Systemet finder rørvejen imellem og spørger om hvert symbol undervejs (ventil, pumpe, kontraventil …): *hvornår går der flow igennem?* Svarene samles til én betingelse, og alle rør på vejen får løbelys, der kører, når betingelsen er opfyldt. Brugeren skal ikke sætte hvert rør op for sig. Til sidst kan man **forklare med egne ord**, og hjælperen (LLM) udfylder svarene som forslag.

## Hvad findes allerede (grundlaget)
- Rør er `<path data-hv-pipe>` med enderne i `data-hv-from`/`data-hv-to` = `"<symbol-id>@fx,fy[,side]"` (svgedit-host/pipes.js). Et T-stykke er et symbol (`t_stykke`) med tre rør. Grafen kan altså bygges ud fra tegningen, deterministisk og uden LLM.
- Løbelys (`flow`) og logikblokke (AND/OR, op til 4 indgange, op til 8 blokke pr. element, kæder via `@L1`) findes i symbolopsætningen. Et løbelys kan have en logikblok som kilde (`@<element>:<blok>`), også fra et andet element.
- Symbolernes egne tilstande findes som pseudo-tags (position, tilstand), så en ventils *åben* kan bruges direkte, hvis ventilen er sat op.

## Valg: hvor gemmes signalvejen? (3 alternativer)
| | Alternativ | + | − |
|---|---|---|---|
| A | Kun som opsætning på rørene (logikblok på første rør, løbelys på alle) | ingen ny tabel | kan ikke vises/rettes som én signalvej; start/slut og svar går tabt |
| **B** | **Ny tabel `signal_paths`** (navn, tegning, start, slut, vej, svar) **+ opsætningen på rørene genereres ud fra den** | kan listes, rettes, slettes samlet; svar kan genåbnes; additiv tabel (MINOR) | to steder at holde i takt (løses: rørenes genererede dele mærkes `sp:<id>` og genskabes ved hver gem) |
| C | Egen runtime-motor for signalveje (uden rør-opsætning) | uafhængig | dobbelt logik ved siden af symbol-runtime; **fravalgt** |

**Valg: B.**

## Trin
**Fase 2a, v4.2.0: signalvej uden LLM**

> **Ændring under implementeringen:**
> - Grafen bygges i frontend (`scada-core.js connectionGraph` + `lib/signalPath.ts`), ikke i `services/signal_path.py`. Tilslutningspunkterne findes automatisk ud fra symbolernes geometri, og den kendes kun i browseren. Demo-tegningen bruger desuden rør-symboler og håndtegnede streger, ikke kun `data-hv-pipe`. Grafen skal derfor også kende sammenfaldende punkter og afgreninger midt på en streg.
> - Backend validerer alt (elementer, dele, tags) og gemmer.
> - Betingelserne er tags (til/fra eller sammenligning), fordi logikblokke ikke kan bruge pseudo-tags. Symbolets egne tags foreslås.
1. `services/signal_path.py` (deterministisk, testes grundigt):
   - graf fra tegningens aktive version: symboler = knuder, rør = kanter (begge ender fast);
   - korteste veje mellem start og slut: op til 3 alternativer og højst 40 led;
   - rollen for hvert symbol på vejen ud fra type:
     - **ventil** (kugleventil, magnetventil, motorventil, regventil): *åben?*;
     - **3-vejs** (trevejs_motorventil): *hvilken stilling leder fra indgang til udgang?*;
     - **pumpe/motor**: *kører?*;
     - **kontraventil**: retning, intet spørgsmål;
     - **T-stykke/bøjning/reduktion/flange**: passiv, intet spørgsmål;
     - **ukendt**: valgfrit spørgsmål;
   - rørets tegneretning mod vejens retning giver `reverse` pr. rør.
2. Tabel `signal_paths` (additiv) + `services/signal_paths.py` (CRUD). Ved gem:
   - **betingelsen:** svarene bliver til logikblokke på startrøret (op til 4 indgange pr. blok; flere kædes) med navnet *Signalvej: <navn>*;
   - **rørene:** hvert rør på vejen får et løbelys (kilde = blokken, retning efter vejen), mærket `sp:<id>`. Rørets øvrige opsætning bevares;
   - **validering og samtidighed:** alt valideres med den eksisterende `validate_config` og gemmes i én transaktion;
   - **ret og slet:** ved rettelse fjernes og genskabes de mærkede dele; ved sletning fjernes de.
3. API (`api/signal_paths.py`, tekniker og op, audit):
   - `POST /api/drawings/{id}/signal-paths/find` {start, slut} → veje + spørgsmål;
   - `GET`/`POST`/`PUT`/`DELETE` på `/signal-paths`.
4. Tegn: knappen **Signalvej …** og `lib/SignalPathGuide.svelte`:
   - (1) klik start- og slutsymbol;
   - (2) vejen fremhæves, og man kan vælge mellem alternativer;
   - (3) ét spørgsmål pr. symbol: tag/stilling/"altid", med svar foreslået ud fra symbolets egen opsætning;
   - (4) navn, farve og fart på løbelyset, forhåndsvisning, *Gem*;
   - listen over signalveje med *Ret* og *Slet*.

   Som *Ret tilslutningspunkter* kræver guiden, at tegningen er gemt (ingen kladde-ændringer). Ellers spørges der først.
5. Manual (*Tegn › Signalvej*, + skærmbilleder), tests, review (opsætning af mange elementer samlet = data-integritet), OTA.

**Fase 2b, v4.3.0: "Forklar med egne ord"**

6. I trin 3: et tekstfelt, fx *"vand fra kedlen til radiatorerne, når pumpe P1 kører og ventil V2 er åben"*.
7. Backend sender kun vejen (symbolernes navne og typer i rækkefølge) og kandidat-tags (navn, beskrivelse, enhed) til LLM'en og beder om et fast JSON-skema: `{element, kilde: tag|stilling|altid, tag?, cmp?, værdi?, stilling?}` pr. symbol.
8. Svaret valideres:
   - **symbol:** skal være på vejen;
   - **tag:** skal findes og være synligt;
   - **værdier:** stillinger og sammenligninger skal være gyldige.

   Ugyldige forslag kasseres og vises som *"ikke udfyldt"*. Forslagene udfyldes i guiden og markeres *forslag fra hjælperen*; **intet gemmes, før brugeren trykker Gem**. Svartiden er 1–3 min (kø, Stop). Uden LLM er knappen der ikke.

## Sikkerhed / integritet
- Kun tekniker og op. Alt skrives gennem den eksisterende validering af opsætninger. Én transaktion pr. gem, og audit på `signal_path.save`/`delete`.
- Kun læsning af tegningen. SVG'en ændres ikke; kun symbolopsætninger og den nye tabel.
- En kopi/backup før en signalvej overskriver eksisterende løbelys på et rør: guiden viser *"rør X har allerede løbelys — erstattes"*, og man skal bekræfte.
- LLM-delen: samme regler som fase 1 (data markeret som data, ingen adresser, kun forslag, rate-grænse).

## Risici
- **Rodede tegninger** (løse rørender, rør der rører hinanden uden T-stykke): de giver ingen kant i grafen. Guiden viser *"vejen stopper ved <rør> (løs ende)"* og peger på det.
- **Tegningen ændres efter en signalvej er gemt** (rør slettes eller tegnes om): ved åbning valideres vejen. Manglende rør markeres, og man kan *Find vejen igen*.
- **Grænser i logikken** (4 indgange, 8 blokke): højst 28 betingelser pr. signalvej. Det er rigeligt; guiden afviser flere.
- **Små modeller misforstår dansk fritekst:** kun forslag, valideres, brugeren godkender.

## Berørte filer (ca.)
- **Nye:**
  - backend: `services/signal_path.py`, `services/signal_paths.py`, `api/signal_paths.py`, `tests/test_signal_path*.py`;
  - frontend: `lib/SignalPathGuide.svelte`, `lib/signalPath.ts` + test.
- **Ændres:**
  - `storage/db.py` (tabel), `main.py`, `services/symbols.py` (fjern/genskab mærkede dele), `services/assistant.py` (2b);
  - `pages/DrawEditor.svelte`, manual 08/10, dokumentation.

---

# Plan: LLM-hjælper integreret i SCADA'en — 2026-11-06 — godkendt (Jan: lokal, én samlet pakke, til/fra) — fase 0 ✅ v4.0.0 — fase 1 ✅ v4.1.0

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

   **Beslutning (v4.1.0, efter målingen på 2–4 tokens/s):** værktøjerne vælges deterministisk ud fra siden og spørgsmålets ord, ikke af modellen. Det giver ét LLM-kald i stedet for op til fire, og tekst fra anlægget kan ikke udløse værktøjskald. Tidsgrænsen er 90 s til første ord og 240 s i alt.
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

**Fase 3 — ✅ v4.10.0 (Jan 2026-11-07: "lave det"):** forslag til tags ud fra ST-variabler (beskrivelse + enhed), hjælp i symbolguiden (trin 2: kommando/tilbagemelding), opsummering af døgnets alarmer (tal beregnes deterministisk). Samme mønster som signalvejen: JSON-skema, validering, intet gemmes.

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
