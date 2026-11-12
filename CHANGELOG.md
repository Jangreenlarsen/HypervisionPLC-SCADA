# Changelog

Nyeste øverst. Format: `## [version build NNNN] — YYYY-MM-DD — beskrivelse`

---

## [6.0.0 build 0395] — 2026-11-12 — Signalvejene og de virtuelle signaler er fjernet (frisk tilstand)

Jan: "fjern alt om den signal editor så vi har en frisk tilstand". Versionen forbliver 6.0.0 (vi går tilbage, ikke frem; OTA'en afviser nedgradering, så kun build tælles op). *Ind/ud og veje* (symbol-flow), *Tjek/Bind forbindelser* og tilslutningspunkter består.

- **Backend:** slettet `services/signal_paths/`, `api/signal_paths.py`, `services/migrations/v60_paths.py`. `symbols.py`: vejsymbolet `sv~` (`path_symbol_id`, `parse_path_symbol`, `MAX_PATH_ANIMS`), afledte signaler som input (`derived_signals`, `signal_ids`, `signal_users`, `sym_refs`, `_signal_cycle`, `pseudo` i `validate_config`) og virtuelle signaler er fjernet; `Signal.virtual` og `Anim.auto` læses stadig fra ældre opsætninger, men ignoreres (gemmes som `False`). `GET /api/drawings/{id}/signals` fjernet. `drawings.py` (`_path_symbol_bindings`, `symbols_info`), `symbol_runtime.py`, `svg_sanitize.py` (`describe_group`, `sv~`-reservation), `backup.py` (eksporterer ingen veje; gendannelse springer veje og `sv~`-opsætninger over), `db.py` (vejmetoderne og v5.0-opgraderingen `_drop_old_signal_paths`; ny `remove_signal_paths`/`count_signal_paths`; tabellen `signal_paths` står tom), `main.py`, `api/backup.py`.
- **Oprydning ved opstart:** ny `services/migrations/remove_paths.py` (én gang, backup `foer-signalvej-fjern` først; fejler backuppen, ændres intet): gemte veje og `sv~`-opsætninger (kode, tilstand) slettes; symboler, der brugte en vej eller et virtuelt signal, røres ikke, men står i rapporten (`report.remove_paths`, audit `signal_path.removed`). Køres også efter gendannelse.
- **Frontend:** slettet `SignalPathGuide`, `SpSaved`, `SpStart`, `signalGuideHarness`, `signalpath/{flow,route,net,pick}.ts` og deres tests; `signalPath.ts` eksporterer kun forbindelses-grafen. `DrawEditor.svelte` (sektionen Signalveje, vinduet over tegningen, vejnavne), `scada-core.js` (`highlightPath`, vejnavne), `SymbolTree`/`symbolTree.ts` (kun grundsymboler og grupper), `draw/panels.ts`. `SymbolGuide.svelte`, `symbolConfig.ts` (+ test) tilbage til v5.1.0 (alle senere ændringer var vej/virtuelt), med v5.4.0's z-index (dialoger over Tegn-værktøjslinjen).
- Tests: `test_signal_paths.py`, `test_signal_branches.py` og de virtuelle tests i `test_symbol_operate.py` fjernet; nye `tests/drawing_api.py` (fælles fixture), `test_symbol_flow.py`, `test_remove_paths.py` (oprydning, backupfejl, API'et uden veje, gamle opsætninger, gendannelse af ældre backup); frontend `graph.test.ts`, `symbolFlow.test.ts`, `symbolTree.test.ts`.
- **Fejlrettelse (BUGS.md):** server-backups af slagsen `pre-v6` (og den nye `foer-signalvej-fjern`) kunne ikke hentes/gendannes — `_BACKUP_NAME` bygges nu af `_KIND_TEXT`. Oprydningen bruger `GLOB 'sv~[0-9]*'` (kun rigtige vej-id'er).
- Manual: kap. 08 Signalveje fjernet, kap. 07/10 rettet, LLM-tillæg (12 afsnit fjernet), billederne `signalvej-*.png` og deres skærmbilledscript fjernet. FEATURES/ACCEPTTEST.

## [6.0.0 build 0394] — 2026-11-12 — Signalvejen er kun en definition og bruges som et almindeligt symbol

**MAJOR** (vejens datamodel ændres). Jans forklaring: en signalvej *definerer* kun, hvad den består af; hvornår den er aktiv og hvordan den ser ud, sættes op i symbol-guiden.

- **Backend:** `services/signal_paths/` er skåret ned til definitionen: `service.py` (`save` gemmer elementer, grene og `flows`; betingelser/udseende/anims fra ældre klienter ignoreres), `validate.py` (`valid_data` tolerant over for det gamle, `strip_legacy`, `is_legacy`); `runtime.py` og `materialize.py` er slettet; `api/signal_paths.py` (`extra="ignore"`, `/suggest` og betingelser væk); `assist_signal.py` kun `pick_tags`. **Vejsymbolet** (`sv~<id>`): `validate_config` tillader `op: positions` (tvinges passivt: intet at skrive), tilbagemelding (`fb`) kan være et andet symbols position (`derived`-signal `sym:…:pos`), `signal_ids`/`signal_users`/`derived_signals` (også vejes position), `config_tags` ignorerer `sym:` og gamle `path:`; `symbol_runtime` publicerer vejsymbolets position som for andre symboler; `drawings._path_symbol_bindings` kun fra opsætningen; `GET /api/drawings/{id}/signals`. **Opgradering** `services/migrations/v60_paths.py` (ved opstart, én gang, backup `pre-v6` først; efter gendannelse af en ældre backup): `strip_legacy`, `sv~`-opsætning nulstilles, rapport (`report.v60_paths`, audit `signal_path.migration`).
- **Frontend:** `SignalPathGuide.svelte` (kun trin 1–3: start/slut, vejen, navn og gem; definitionens `flows` fra `net.rows`), `SpSaved.svelte`; `SymbolGuide.svelte` (vejsymbol: trin 1 *Positioner / Kun animationer*, trin 2 tilbagemelding *PLC-tag eller et symbols position*, trin 3 kontaktflade, trin 4 *Tilføj løbelys langs vejen*; trin 5 skjult; afledte signaler som kilde og logikindgang); `symbolConfig.ts` (`libraryDefault('signalvej')`). **Slettet:** `SpConditions.svelte`, `SpLook.svelte`, `pathLook.ts`, `signalpath/answers.ts` (`pickNext` flyttet til `pick.ts`), *Lav en betjening til vejen*.
- Tests: `test_signal_paths.py` og `test_signal_branches.py` omskrevet (definition, vejsymbol med PLC-tilbagemelding og animationer pr. position, tilbagemelding fra et symbols position, sletning/afvisning, backup, opgradering fra ældre veje, opstart på eksisterende data), `symbolConfig.test.ts`, `SignalPathGuideClick.test.ts`, `signalPath.test.ts`. Set i browseren: opgradering af en kopi af de gamle data (4 veje → definition), vejens guide uden betingelser/udseende, symbol-guiden (positioner, tilbagemelding = et andet symbols position, *Tilføj løbelys langs vejen*) → gemt som `positions/passive` med løbelys i *Til*.
- **Reviewer-rettelser:** opgraderingen ændrer intet, hvis backuppen `pre-v6` fejler (prøves igen ved næste opstart), springer ugyldige veje over pr. vej og lægger rapporten oven på en tidligere; en cyklus mellem symbolers afledte signaler (A læser B, som læser A) afvises i trin 2; et symbol, der skriver til en PLC, kan ikke bruge et symbols position som tilbagemelding; en logikblok, der læses som `sym:…:logic:Lk`, kan ikke fjernes; et symbol kan ikke miste positioner, mens en anden læser dem; gendannelse validerer `sym:`-henvisninger (samme tegning, symbol findes) og tvinger vejsymboler passive; gendannelsens svar viser en fejlet opgradering; `pre-v6` har klartekst; skift til *Kun animationer* i symbol-guiden beder om bekræftelse. Tests tilføjet (løkke, skrivende symbol, backupfejl).
- Manual (kap. 08 omskrevet), LLM-tillæg, FEATURES.

## [5.12.0 build 0393] — 2026-11-12 — Virtuelle signaler, fase C: betjening af en vej

- `lib/SignalPathGuide.svelte` + `pages/DrawEditor.svelte` (`makePathControl`): knappen *Lav en betjening til vejen* — spørger, sætter en klassisk vippekontakt (`vippe_onoff`) ind ved vejens start (`ed.insertSymbol`), gemmer og udgiver tegningen (`ensurePublished`), henter symbolets standardopsætning (`libraryDefault`: OFF/ON med greb), gør signalet virtuelt (`virtual: true`, intet tag) og gemmer den; vejguiden genindlæser signalerne, så *<kontakt>: position* kan vælges som betingelse.
- `lib/SpConditions.svelte`, `signalpath/answers.ts`: ved et symbols position kan betingelsen være *er* eller *er ikke* (`neg`).
- Tests: `signalPath.test.ts` (*er ikke*). Set i browseren: knappen sætter kontakten ind og op (`{tag: "", virtual: true}`, positionerne OFF/ON), og *Symbolers position* har to signaler i vælgeren.
- Manual (kap. 08), LLM-tillæg, FEATURES.

## [5.11.0 build 0392] — 2026-11-12 — Virtuelle signaler, fase B: kun i SCADA

- `services/symbols.py`: `Signal.virtual` (nyt felt); `validate_config`: et virtuelt signal har intet tag, skrives som *Sæt*, kan have en tilbagemelding, og findes kun for positioner (ikke trykknap/setpunkt og ikke passiv visning). Betjening (`symbol_operate`) og skriveplan (`write_plan`) sprang allerede signaler uden tag over — et skift af position skriver derfor intet til PLC'en men huskes som valgt position (`symbol_state`); en `fb` er stadig toneangivende (`display: remote`).
- `lib/SymbolGuide.svelte` (trin 2): *Kommando* kan være *et PLC-tag* eller *kun i SCADA (virtuelt)*; `symbolConfig.ts` (`Signal.virtual`).
- Tests: `test_symbol_operate.py` (virtuelt skift skriver intet og huskes, vejen læser positionen, kun positioner/aldrig passiv, tilbagemeldingen er toneangivende). Set i browseren: trin 2 → *kun i SCADA (virtuelt)* → Gem → `{tag: "", virtual: true}`.
- Manual (kap. 10), LLM-tillæg, FEATURES.

## [5.10.0 build 0391] — 2026-11-12 — Virtuelle signaler, fase A: symbolets position som betingelse

- `services/symbols.py`: `derived_signals(drawing_id)` (symbolers position `sym:…:pos` med positionernes navne, og logikblokke `sym:…:logic:Lk` — blokke, der selv læser en vej, udeladt); `path_condition_users` (veje, hvis betingelser læser et symbol); `delete`/`put`/`_logic_users` afviser at slette et symbol, fjerne dets positioner eller blokke, mens en vej bruger dem.
- `services/signal_paths/service.py`: en betingelses `src` kan være et beregnet signal; `info` giver dem som `tags` med `derived`, `group`, `labels`; tal-signaler (position) kræver `cmp` + værdi. Runtime uændret (`branch_results` læser cachen).
- `lib/SpConditions.svelte`, `signalpath/answers.ts`: vælger med grupperne *Symbolers position* / *Logikblokke*, *"når positionen er <navn>"*; læsbare fejltekster.
- Tests: `test_signal_paths.py` (betingelse på position, tilbagemelding toneangivende, sletning/ændring afvises, logikblokke og løkkeundgåelse), `signalPath.test.ts`. Set i browseren: omskifter-symbol → betingelsen *Radiator: position = Auto* i vejens guide → gemt som `eq 1`.
- Manual (kap. 08), LLM-tillæg, FEATURES.

## [5.9.0 build 0390] — 2026-11-12 — Animationer samlet pr. symbol, og unikke navne

- `svg_sanitize.describe_group`: elementer får et entydigt `label` (navnet, hvis det er unikt; ellers `navn (id)`; uden navn `type (id)` / `rør (id)`), og rødderne `named` og `sym_type`.
- `SymbolGuide.svelte` (signalvej, trin 4): animationerne vises i sammenfoldelige grupper pr. element (`{#snippet animRow}`, `pathGroups`), hver med *+ Animation* (`addAnimFor`); ▲▼ bytter inden for gruppen. Rækkefølgen i opsætningen er uændret.
- `scada-core.js`: `unnamedSymbolCount()` og `nameUnnamedSymbols(labels)` (typens navn + løbenummer via `uniqueNameIn`, ét fortryd-trin; rører kun `data-hv-name`); `DrawEditor.svelte` + `SymbolTree.svelte`: advarslen *N symboler har intet navn* og knappen *Giv dem unikke navne*.
- Tests: `test_signal_paths.py` (entydige labels). Set i browseren på en kopi af demo-tegningen uden navne: 9 navnløse symboler, knappen navngiver dem, Ctrl+Z fortryder; guiden viser én gruppe pr. element (`rør (svg_67)`, `t stykke (t_stykke_2)` …).
- Manual (kap. 07 og 08), LLM-tillæg, FEATURES.

## [5.8.0 build 0389] — 2026-11-12 — Signalvejens animationer kan redigeres som i et almindeligt symbol

- **Backend:** `services/signal_paths/materialize.py` (`base_anims`, `merge`): vejens *Udseende* (`elements[].flows/anims`) bliver almindelige animationer i vejens symbol-opsætning (`sv~<id>`), mærket `auto: true`, med vejens pseudo-tag som kilde og *aktiv/passiv*. `SignalPathService.save` skriver dem i samme transaktion som vejen (`expect` mod samtidige ændringer; en ny vej får dem straks efter, og rulles tilbage, hvis de ikke kan gemmes); `auto`-animationer erstattes, alt andet bevares; egne animationer på en gren, der ikke findes mere, fjernes (`dropped`). `Anim.auto` (nyt felt), `Anim.src` op til 120 tegn, `MAX_PATH_ANIMS = 600` for vejsymboler (12 for andre, tjekkes i `validate_config`). `drawings._path_bindings` er væk — alt kommer fra `_path_symbol_bindings`. `materialize_existing()`: opgradering ved opstart (flag `migration.v58_path_anims`) og efter gendannelse af en backup. `svg_sanitize.describe_group`: `owner` pr. del.
- **Frontend:** `SymbolGuide.svelte` (trin 4 for en vej): afkrydsningen *Følger vejens udseende*, hjælpetekst, elementfilter *Vis animationer for*, grænse 600, *Fjern konfiguration* og *Gem og anvend på flere* skjult for en vej; `symbolConfig.ts` (`Anim.auto`, `PartInfo.owner`, `MAX_PATH_ANIMS`, `partLabel`: en biblioteksdels rigtige navn — *Port A*, *Motor*).
- Tests: `test_signal_paths.py` (grundanimationer som animationer med samme resultat på Overview, frigjort animation består og auto genskabes, grænse 600/12, opgradering skrives én gang), `symbolConfig.test.ts`. Set i browseren på en importeret kopi af demo-tegningen *test-ny-editor* (3-vejs ventil og tanke): animationerne står i guiden, elementfilteret virker, kilden skiftes, vejen gemmes igen — frigjort animation består, de øvrige genskabes.
- **Reviewer-fund rettet:** *(1)* en vej, hvis grundanimationer ikke kan skrives ind i opsætningen, vises stadig ud fra sit udseende (`materialized`-markør i vejens data; `drawings._path_symbol_bindings`), og en grundanimation, som symbolreglerne ikke kan acceptere, udelades i stedet for at blokere vejen; *(2)* en ny vej gemmes alt-eller-intet (rulles tilbage ved enhver fejl i andet trin); *(3)* egne animationer på en del/gren, der er taget ud af vejen, fjernes og tælles (`dropped`, logges og vises i vejguiden) i stedet for at låse vejen; *(4)* 12-grænsen tjekkes nu også i backup (symboler og grupper) og forudindstillinger; *(5)* vejene sorteres efter navn (`100000 + vej·1000 + plads`); *(6)* rækkefølgen mellem vejens og dine animationer bevares (grundanimationerne erstattes på deres plads; nye lægges nederst, øverste aktive vinder); *(7)* opgraderingen rører kun veje uden `materialized` — også efter en gendannelse; flaget sættes selv om en vej fejler; *(9)* for mange animationer (over 600) giver en klar fejl i stedet for stille afkortning; *(10)* opgraderingen skriver vej og opsætning i én transaktion med `expect` og genindlæser; *(11)* forældede pseudo-tags fra gamle grene slipper ikke gennem valideringen; elementfilteret: ▲▼ bytter med nærmeste synlige, *+ Standard* følger filteret.
- Manual (kap. 08), LLM-tillæg, FEATURES.

## [5.7.0 build 0388] — 2026-11-12 — Ur-status (NTP) og pilot-dokumenter

- `services/health.py`: `read_time_sync()` (`timedatectl show -p NTPSynchronized`, huskes 60 s, `None` uden systemd), `host.time_sync` i Status/`/metrics`-detaljerne og en gul advarsel (`code: time`), når uret ikke er synkroniseret. `lib/status.ts`, `pages/Status.svelte`: kortet *Ur (NTP)*.
- Tests: `test_health.py` (advarsel ved `time_sync: False`, oversættelse af `timedatectl`, cache, ingen `timedatectl`). Manual (kap. 13 *Status*).
- Nye dokumenter: `docs/ACCEPTTEST.md`, `docs/UDGIVELSESPROCES.md`, `docs/KATASTROFEOEVELSE.md`.

## [5.6.1 build 0387] — 2026-11-12 — scada-tool: ingen traceback ved `| head`

- `backend/app/tool.py`: `BrokenPipeError` (fx `scada-tool config | head`) giver ikke længere en traceback. Manual (kap. 13): kommandoen køres via `su -` eller med den fulde sti (`/usr/local/sbin` er ikke i PATH under `su -c`). Afprøvet på demo-serveren: `status`, `check`, `config`, `update status`, `logs`.

## [5.6.0 build 0386] — 2026-11-12 — Server-værktøjskasse `scada-tool`

- `backend/app/tool.py` + `deploy/scada-tool.sh` (installeres af `install.sh` som `/usr/local/sbin/scada-tool`): `status`, `check` (appen kan importeres? databaser `quick_check`, ejer af data-mappen, health, hængende opdatering), `logs`, `start|stop|restart` (venter på health), `update status|reset|apply|rollback`, `backup list|create|restore` (SQLite-kopi), `user list|reset` (adgangskode kun fra terminal/stdin, lukker sessioner), `config` (hemmeligheder som "(sat)"), `maint`. Ændringer spørger/`--yes` og logges (`logger -t scada-tool`).
- `services/updates.py`: en opdatering, der står som "applying/queued", regnes som hængende efter **2 min** (før 20), når opdateringstjenesten ikke kører (`helper_running`). *(Et "stalled"-status blokerer ikke for upload, så en ekstra knap i web er ikke nødvendig.)*
- Tests: `tests/test_tool.py` (nulstilling af adgangskode, config uden hemmeligheder, update reset/apply, diagnose af en app der ikke kan importeres, backup-rundtur, hængende opdatering). Manual (kap. 13), LLM-tillæg.

## [5.5.0 build 0385] — 2026-11-12 — Symbol-oversigt (træ)

- `lib/symbolTree.ts` (rene funktioner: `buildTree`, `filterTree`, `countSymbols`) + `symbolTree.test.ts`; `lib/SymbolTree.svelte` (træet, søgning, "ikke opsatte", fold ud/sammen, hentes igen 0,5 s efter en ændring); `pages/DrawEditor.svelte`: panelet *Symbol-oversigt*, `Opsæt` åbner symbol-guiden (grundsymbol: elementet, signalvej: `sv~<id>`), `Animationer` åbner gruppens animationer (`GroupAnims`), oversigten genhentes, når guiden/gruppe-dialogen lukkes.
- Ingen backend-ændring. Set i browseren: tre sektioner, vej og gruppe foldet ud, klik vælger i tegningen, *Opsæt* åbner vejen som symbol, *Animationer* åbner gruppens dialog.
- Manual (kap. 07 *Symbol-oversigt*), LLM-tillæg, FEATURES.

## [5.4.1 build 0384] — 2026-11-12 — fix: serveren startede ikke (v5.4.0)

- `services/symbol_runtime.py`: manglende import af `path_symbol_id` (NameError i `reload()` ved opstart) — se BUGS.
- `tests/test_signal_paths.py`: `test_runtime_reload_and_evaluate_run_the_logic_of_a_path_symbol` kalder runtimens `reload()`/`evaluate()` med et vejsymbol.

## [5.4.0 build 0383] — 2026-11-11 — Signalvejen som samlet symbol

- **Backend:** `services/symbols.py`: det virtuelle symbol-id `sv~<vej-id>` (`path_symbol_id`, `parse_path_symbol`); `SymbolService.info()` giver vejen som ét symbol (type `signalvej`, delene = alle vejens elementer og underdele, via `svg_sanitize.describe_group`); `get/put/preview/copy_to/orphaned/logic_pool` kender det; `validate_config` tvinger `op = view`, afviser "hele symbolet" og accepterer vejenes pseudo-tags (`path:…`) som kilde i animationer og logikblokke; `config_tags` regner dem ikke som rigtige tags. `drawings._path_symbol_bindings`: vejens egne animationer (`source: "path-symbol"`, position ≥ 100 000) lægges efter vejens automatik. `symbol_runtime.reload` regner vejens logikblokke. `signal_paths/service`: listen giver `symbol`, `configured`, `sources`; *Slet* afviser, hvis en anden bruger vejens logikblok (409), og sletter vejens opsætning i samme transaktion. `storage/db.py`: `list_signal_paths` springer en beskadiget række over (logges); backup gemmer og gendanner vejens **id** (`sv~<id>` peger på det); `services/backup.py` dropper vejsymboler uden en gendannet vej.
- **Frontend:** `SpSaved.svelte` (*Ret som symbol* ✓, knapperne i egen række), `SignalPathGuide.svelte` (`onsymbol`), `DrawEditor.svelte` (åbner guiden for `sv~<id>`), `SymbolGuide.svelte` (trin 1 viser vejens elementer, ingen "hele symbolet", ingen preview, kilden *en signalvej* i animationer og logik), `symbolConfig.ts` (`PartInfo.label/root`, `partLabel`). Dialogerne i Tegn løftet over værktøjslinjen (z-index 38/39, se BUGS).
- Tests: backend (`test_signal_paths.py`: vejen som symbol, egne animationer overlever gem og vinder over automatikken, logik og slet, backup bevarer id), frontend (`SpSaved.test.ts`, `partLabel`). Set i browseren: Ret som symbol → trin 1 og 4, animation med signalvej som kilde → Gem → binding `path-symbol` (position 101000) ved siden af vejens løbelys.
- Manual (kap. 08 *Rediger vejen som et symbol*), LLM-tillæg, FEATURES, BUGS.
- Reviewer-fund rettet: gendannelse sætter veje med id først (ingen UNIQUE-konflikt), afviser henvisninger til veje, der ikke kommer med tilbage; *Slet vej* afvises, hvis et andet symbol/en gruppe bruger vejen som kilde, og sker kun, hvis vejens opsætning er uændret (`expect`); pin/state slettes med; ingen kode på en vej; `id="sv~<n>"` fjernes fra uploadede SVG'er; upload-rapporten viser ikke vejsymboler som forældreløse.

## [5.3.0 build 0382] — 2026-11-10 — Forbindelser som data i tegningen

- `svgedit-host/scada-core.js`: `data-hv-links="nøgle>andet-id:nøgle;…"` på begge elementer i en forbindelse (nøgler som "ikke i brug": `s`/`e`, punktets placering, `#i`; `~` = midt på en streg). `connectionGraph()` giver `links`; `bindLinks(pairs)` (gemmer parrene, rydder forbindelser til slettede elementer — ét fortryd-trin), `unlink(id, key)` (begge ender); overlayet viser gledne forbindelser orange (klik = fjern); kopier (indsæt/dupliker) tager ikke forbindelser med.
- `lib/signalpath/graph.ts`: `contacts()` bruger de gemte forbindelser, hvor de findes (geometriske kontakter ved et bundet punkt gælder ikke), ellers geometrien (`geoContacts`); `pairsToBind` (eksisterende + nye fra geometrien: kun egentlige ender, punkt mod punkt inden for 8 enheder, højst én forbindelse mellem to elementer, nærmeste først), `unboundPairs`, `linkGap`, `pointOfKey`; `connectionCheck` med status `drift` (gemt, men > 8 enheder fra hinanden) og `unbound`; `planFixes` flytter en gledet rør-ende tilbage til den gemte modpart. `realEnds` beholder det yderste punkt, når punkter ligger tæt (bøjningens ende — ikke kurvepunktet).
- `pages/DrawEditor.svelte`: *Bind forbindelser (N)*, "N gledet", og *Ret* binder de rettede ender, når tegningen er bundet.
- Tests: `connectionCheck.test.ts` (binding, gledet, ubundne, Ret), `test_svg_sanitize.py`. Simuleret på demo-tegningen: samme signalvej før og efter binding, ingen falske "gledet". Set i browseren: Bind (98 par, 95 elementer) → et rør gjort 15 kortere → 2 orange → Ret → grønt; klik på orange fjerner forbindelsen i begge ender, Ctrl+Z bringer den tilbage; kladden gemmer forbindelserne.
- Manual (kap. 07), LLM-tillæg.

## [5.2.0 build 0381] — 2026-11-10 — Signalvej-guiden i et vindue over tegningen

- `pages/DrawEditor.svelte`: mens en signalvej redigeres, vises guiden i et fast placeret vindue over tegnefladen (`.spwin.floating`: træk i overskriften, ændr størrelse i hjørnet, standard i højre side; valg, placering og størrelse i `localStorage` `draw.spwin`, holdt inden for skærmen). Samme komponent som i panelet (kun CSS), så tilstanden bevares; sektionen *Signalveje* holdes åben, mens vejen redigeres. Knapperne *⇲ Til panelet* / *⇱ Ud over tegningen*.
- `lib/SignalPathGuide.svelte`: `oneditchange(editing)`. Komponenttest. Set i browseren: vinduet åbner, kan trækkes, beholder valgene ved skift mellem vindue og panel og lukker ikke, når en anden sektion åbnes.
- Manual kap. 08.

## [5.1.1 build 0380] — 2026-11-10 — fix: signalvejens trin 4 viste ikke alle symboler

- `lib/pathLook.ts`: gruppen `unit` (*Øvrige symboler*: kedel, tank, radiator …) med farve, stregfarve, blink og "vises kun når aktiv"; `groupOf('unit')`. `lib/SpLook.svelte`: hvert kort viser elementerne, det gælder. Test i `pathLook.test.ts`. Set i browseren (Kedel/fyr Pille under *Øvrige symboler*). Manual kap. 08.

## [5.1.0 build 0379] — 2026-11-10 — Symbolstandard: den gamle symbolmodel er fjernet

- **Opgradering** (`services/migrations/v51_symbols.py`, kørt ved opstart én gang og efter gendannelse af en backup): backup først (`scada-pre-update-…`); bibliotekssymboler med gamle bindinger (eksplicitte på rod/dele eller automatiske fra `data-hv-auto`/`data-hv-part`, når id/navn er et tag) konverteres med de tidligere "Konvertér alle"-regler og gemmes via guidens `SymbolService.put`; derefter slettes de gamle bindinger på symbolerne ("Gå til tegning" på roden bevares). Rapporten (`meta: report.v51_symbols`) vises i Tegn › Meddelelser (`GET/DELETE /api/symbol-migration`) og i health-metrics (`symbol_migration`).
- **Én model** (`services/drawings.py`): `_compute` uden den gamle symbol-del og uden `legacy`; bindinger og tag-navne-automatik på bibliotekssymboler (rod og dele) bruges ikke — kun "Gå til tegning" på roden; simple bindinger på symboler afvises (409); "tilknyt tag til hele symbolet" (`bind_symbol`, `set_symbol_bindings`), `legacy_bindings`, `GET …/suggest` og `POST /api/drawings/convert-symbols` er fjernet. Almindelige bindinger og tag-navne-automatik på elementer, der ikke er symboler, er uændrede.
- **Frontend**: panelet "Konvertér alle" (`SymbolConvert.svelte`) og guidens "Foreslå ud fra symbolet" er fjernet; Bindinger behandler alle bibliotekssymboler som guide-symboler (`elementTree.lib`); Tegn › Meddelelser viser opgraderingsrapporten.
- **Review** (reviewer-agent): rapporten gemmer de slettede bindinger pr. manuelt symbol og konverteringens noter; gendannelse tager en backup af den gendannede tilstand, fanger fejl (gendannelsen gælder stadig, opgraderingen prøves ved næste opstart) og auditeres altid; en gammel rapport ryddes, når der intet er at gøre; "Gå til tegning" kun på roden af et symbol uden betjening (ikke opsat eller kun-visning), som før; Status viser `pending`, hvis opgraderingen ikke er kørt; audit `symbol.migration` ved opstart. Testen af signalvejenes runtime er gjort robust mod den samtidige runtime-løkke.
- `data-hv-auto`/`data-hv-part` i biblioteket bevares som metadata (Symboltest bruger dem), men har ingen virkning i drift.
- `Database.get_meta/set_meta`. Tests: `test_symbol_convert.py` (opgradering, rapport, afvisning, gendannelse), justerede tests i `test_drawings_api.py`, `test_symbol_copy.py`, `test_symbol_groups.py`; `elementTree.test.ts`. Set i browseren: opgradering ved opstart (backup, 1 konverteret, 4 bindinger slettet), rapporten i Meddelelser, delen af et symbol uden "+ Tilføj binding", og den konverterede vippekontakt skifter FRA → TIL mod mock-PLC'en.
- Manual (kap. 10), LLM-tillæg, SYMBOLSTANDARD_IMPLEMENTERING.md (afsnit 11.3 udført).

## [5.0.1 build 0378] — 2026-11-10 — fix: topmenuen bag Tegns værktøjslinje

- `pages/DrawEditor.svelte`: værktøjslinjen `z-index: 30` (under topmenuens 40); `.layout` får egen stablingskontekst (`position: relative; z-index: 0`), så tegnefladens lag ikke dækker Vis/Fang/Meddelelser. Set i browseren.

## [5.0.0 build 0377] — 2026-11-10 — Signalveje 4: signalvejen som selvstændigt runtime-objekt (MAJOR, skema 16)

- **Model** (`services/signal_paths/validate.py`): vejen er ét objekt `{start, end, ends, elements[{element, branches, flows, anims}], conditions[{element, src, neg, cmp, value, branches}], style, ui}`. `blocks.py` er fjernet; `service.py` gemmer kun objektet (ingen `_strip`/`_owned`/`_check_refs`, ingen 409-konflikter, ingen `created`), renser animationernes parametre, kræver sammenligning på tal-tags og at tags og dele findes. Højst 64 betingelser pr. vej.
- **Runtime** (`services/signal_paths/runtime.py`, `SymbolRuntime._evaluate_paths`): gren = OG over dens betingelser (tre-værdi-logik som logikblokke; ingen betingelser = altid), stykker = ELLER over grenene; pseudo-tags `path:<tegning>:<id>:<grene>` i live-cachen; slettede veje ryddes; signaturen omfatter `signal_paths` og tegningernes deaktivering; `path_stats` i `/api/health`-metrics (`signal_paths`).
- **Overview** (`DrawingService._path_bindings`): vejens løbelys og animationer som almindelige bindinger på pseudo-tagget (efter symbolernes og gruppernes, så den eksisterende prioritetsregel gælder). `signal_paths` er med i `CONFIG_TABLES` (gemte bindinger regnes forfra).
- **Adgang og tags**: `tags_for_drawing()` medtager vejenes pseudo-tags; `SymbolService.usage()` nævner signalveje, så et tag i brug ikke kan slettes. Vagten mod at slette en "ejer"-opsætning er fjernet.
- **Opgradering** (`Database._drop_old_signal_paths`, skema 16): veje i det gamle format slettes, og deres logikblokke ("Signalvej: …") og animationer fjernes fra symbolerne (tomme opsætninger, vejen havde oprettet, slettes). Backup: gamle veje springes over.
- **Review** (reviewer-agent): betingelsestags holder pollingen i gang (`drawing_activity`), opgraderingen kører i en transaktion pr. vej, overlever en beskadiget række og fjerner også andre henvisninger til de gamle blokke (egne animationer, retning, egne blokkes indgange); "@on"-løbelys fjernes kun én gang pr. del; ugyldige veje springes over i Overview og runtime (logges); grænseværdien skal være et endeligt tal; en begrænset bruger kan kun bruge tags, han må se.
- **Guiden** (`SignalPathGuide.svelte`): gem-body uden `replace`; "Erstat"-dialogen og "har allerede løbelys"-advarslen er fjernet.
- Tests: `test_signal_paths.py`, `test_signal_branches.py` (gem/ret/slet, view-bindinger, runtime med grene/ELLER/ukendt, gamle veje, backup, tag i brug, valid_data), `SignalPathGuideClick.test.ts` (gem-body). Set i browseren mod mock-PLC: vej gemt, intet i symbolerne, løbelys 0 → 11 → 0 rør, når tagget skiftes.
- Manual (kap. 08), LLM-tillæg, ARCHITECTURE.md.

## [4.22.0 build 0376] — 2026-11-10 — Tjek forbindelser: punkter og symboler, der ikke er i brug

- `svgedit-host/scada-core.js`: attributten `data-hv-unused="nøgle;nøgle"` på symbolet/røret (nøgle = rørets ende `s`/`e`, symbolpunktets placering i boksen med to decimaler, eller `#i`; `*` = hele symbolet). `connectionGraph()` giver `keys`, `unused` og `exempt`; `toggleUnused(id, key)` og `exemptSymbols(ids, on)` ændrer attributten som ét fortryd-trin (så den gemmes med tegningen); overlayet har klikbare prikker (klik = punktet, Skift+klik = hele symbolet), grå stiplede ringe for punkter ikke i brug og grå rammer med et ⊘-mærke for udeladte symboler.
- `lib/signalpath/graph.ts`: `connectionCheck` springer punkter markeret som ikke i brug over (de tæller som `ignored`) og udelader `exempt`-symboler helt; `ConnItem` har `openKeys`, `ignored`, `ignoredKeys`, `exempt`.
- `pages/DrawEditor.svelte`: knappen *Udelad valgte fra tjekket* / *Tag valgte med i tjekket* (Vis-menuen og værktøjslinjen, når tjekket er slået til).
- Backend uændret (sanitizeren bevarer `data-*`-attributter); ny test `test_keeps_unused_connection_marks`. Tests: `connectionCheck.test.ts` (11). Set i browseren: klik på prik, Skift+klik, knap, to gange fortryd, og at attributten ligger i den gemte kladde.
- Manual (kap. 07) og LLM-tillæg.

## [4.21.0 build 0375] — 2026-11-10 — Tegn: meddelelser i en boks

- `pages/DrawEditor.svelte`: de gule bjælker over tegningen (`info` og dublerede navne) er fjernet. Hver ny `info`-besked lægges i en liste (tid, tekst, evt. "Renset ved gem" / "Bindinger uden element" / advarsel om symboler, der ikke findes), og knappen **Meddelelser** i den øverste linje viser antallet af nye (orange) og åbner en boks med listen (nyeste øverst, *Ryd meddelelser*). En advarsel (symboler sat op med guiden, som ikke findes) åbner boksen af sig selv. Dublerede symbolnavne står øverst i boksen med knappen *Giv dem unikke navne*. Højst 30 meddelelser.
- `lib/draw/Menu.svelte`: `badge`, `hot`, `wide`, `align`, bindbar `open` og `onopen`.
- Manual (kap. 07) og skærmbilleder (`tegn`, `tegn-gitter`). Set i browseren: ingen gul bjælke, tal på knappen, boksen åbner/lukker, tallet nulstilles ved åbning.

## [4.20.0 build 0374] — 2026-11-10 — Tegn: samlet værktøjslinje

- `lib/draw/Menu.svelte` (ny): lille rullemenu (knap + panel; lukker ved klik udenfor og Esc).
- `lib/draw/DrawCanvas.svelte`: `bar`-prop (Tegn skjuler linjen over tegnefladen), `onzoom` og `perform(name)` (zoom udefra).
- `pages/DrawEditor.svelte`: zoom (−, %, +, Tilpas) og menuerne **Vis** (gitter + afstand, hjælpelinjer + inddeling/+ Lodret/+ Vandret, navne i tegningen, Tjek forbindelser + Ret N) og **Fang** (gitter, objekter, rør lige, hjælpelinjer, skalér symmetrisk) i den øverste linje; kommentarfeltet er `15rem` (før: fyldte resten); *Størrelse* er kortet til `⤢ 1840 × 850`; en kort opsummering af tjek-forbindelser står i linjen, når det er slået til. Tegnefladen er højere (linjen fjernet).
- Manual (kap. 07), tre skærmbilleder (`tegn`, `tegn-gitter`, `tegn-hjaelp`) og `manual-screenshots.mjs` (åbner menuerne). Set i browseren ved 2569, 1600 og 1000 px bredde.

## [4.19.0 build 0373] — 2026-11-10 — Tegn: ret brudte forbindelser

- `lib/signalpath/graph.ts`: `planFixes(g, items, maxGap)` — for hver åben ende på et rør (eller lige rør-symbol `roer_l`/`roer_v`): den nærmeste anden ende/tilslutningspunkt 8–25 enheder væk (en ende, der selv er åben, foretrækkes ved lige afstand). Et lige rør-symbol foreslås kun, hvis målet ligger på dets akse. Symboler foreslås aldrig flyttet.
- `svgedit-host/scada-core.js`: `fixConnections(moves)` — tegnede rør (`data-hv-pipe`) lægges om og sættes fast i punktet (`data-hv-from/-to`); lige rør-symboler (`matrix(a 0 0 d e f)`) forlænges/forkortes i deres retning; alt andet springes over og tælles. Ét fortryd-trin (*Ret forbindelser*).
- `pages/DrawEditor.svelte`: knappen *Ret N forbindelser* ved *Tjek forbindelser* (N = foreslåede rettelser) og en besked bagefter; tjekket køres forfra.
- Manual (kap. 07) og LLM-tillæg. Tests: `connectionCheck.test.ts` (8). Set i browseren: et lige rør forkortet 15 enheder → knappen vises → rettet (længden næsten som før), åbne ender 25 → 23, Ctrl+Z → 25.

## [4.18.0 build 0372] — 2026-11-10 — Tegn: tjek forbindelser

- `lib/signalpath/graph.ts`: `connectionCheck(g)` — for hvert symbol og rør: `ok` (alle tilslutningspunkter sidder fast), `open` (nogle er åbne) eller `isolated` (intet sidder fast), med de åbne punkter. Samme regler som signalvejene (`contacts`). Bøjninger og T-stykker tæller kun deres egentlige ender (kurvepunkter og midtpunkt ignoreres); visning og løse figurer springes over.
- `svgedit-host/scada-core.js`: `markConnections(items)` og `drawConn()` — eget lag `#hvConnCheck` oven på tegningen: grønt = forbundet, rødt (stiplet = isoleret) med røde prikker ved de åbne ender. Kun visning.
- `pages/DrawEditor.svelte`: afkrydsningen *Tjek forbindelser* med opsummering ("23 med åbne ender, 1 uden forbindelse", navnene i tooltip); køres forfra, når tegningen ændres.
- Manual (kap. 07) og LLM-tillæg. Test: `connectionCheck.test.ts` (4). Set i browseren på en rigtig tegning: rør og bøjninger grønne, ubrugte porte røde; slået fra fjerner laget.

## [4.17.0 build 0371] — 2026-11-10 — Tegn: vis navne i tegningen

- `svgedit-host/scada-core.js`: `setNameLabels({ symbols, pipes, paths })` og `drawNames()` — navne som mærkater (hvid kant, ca. 11 px uanset zoom) i et eget lag oven på tegningen (`#hvNameLabels`); tegnes forfra ved zoom, rul og ændringer. Symboler blå over symbolet; forbindelser (rør-symboler som rør, bøjning, T-stykke og tegnede rør uden navn → id i grå kursiv) grønne; signalvejens navn lilla midt på vejen. Gemmes ikke i tegningen og vises ikke i Overview.
- `pages/DrawEditor.svelte`: *Vis navne* med tre afkrydsninger (symboler / forbindelser / signalveje) i værktøjslinjen; huskes pr. browser (`draw.names`); signalvejenes navne hentes fra API'et og genindlæses, når en signalvej gemmes eller slettes.
- Manual (kap. 07) og LLM-tillæg. Backend uændret. Set i browseren: mærkaterne vises og forsvinder pr. valg; signalvejens navn tegnes.

## [4.16.0 build 0370] — 2026-11-09 — Signalveje: vend flowets retning

- `lib/signalpath/net.ts`: `describeNet(g, paths, defs, flips)` vender en gren efter brugerens ønske (efter `orient`); `Net.manual` fortæller hvilke grene. Ny test i `signalFlow.test.ts`.
- `SignalPathGuide.svelte`: knappen *⇄ Vend flowet* pr. gren (trin 2), besked *Du har vendt flowets retning*, `flips` gemmes i `ui` og kommer tilbage ved *Ret*; nulstilles, når start/slut ændres. Komponenttest. Set i browseren: knappen vises, og pilene vender.
- Manual (kap. 08) og LLM-tillæg. Backend uændret.

## [4.15.1 build 0369] — 2026-11-09 — Refaktorering af signalvejs-koden (ingen funktionsændring)

- `frontend/src/lib/signalPath.ts` (482 linjer) delt i `signalpath/graph.ts`, `flow.ts`, `route.ts`, `net.ts`, `answers.ts`; `signalPath.ts` re-eksporterer, så imports og tests er uændrede.
- `SignalPathGuide.svelte` (890 → ~750 linjer): trin 1 → `SpStart.svelte`, trin 3 → `SpConditions.svelte`, trin 4 → `SpLook.svelte`, listen over gemte veje → `SpSaved.svelte`. Via-handlingerne i guiden er samlet i `viaFromList` / `viaFromSelection`. Ubrugt CSS fjernet.
- `backend/app/services/signal_paths.py` (464 linjer) → pakken `signal_paths/` (`validate.py`, `blocks.py`, `service.py`); `save()` bruger nu `plan_chains` / `make_blocks` / `block_of` til logikblokkene. Importstier uændrede.
- ARCHITECTURE.md: afsnit om signalvejs-lagene. Ny komponenttest for trin 3–5. Set i browseren: trin 1 og klik på rør er uændret.
- Alle tests grønne (frontend 1002, backend uændret antal).

## [4.15.0 build 0368] — 2026-11-09 — Signalveje: ret vejen ved at klikke i tegningen

- `lib/signalPath.ts`: `findViaPath` — en vej fra start til slut gennem via-punkter (sorteret efter afstand fra start); et punkt, der ikke kan bruges (blindgyde, vej ville vende om), droppes og meldes som `missing`.
- `lib/SignalPathGuide.svelte`: "Gå via" (rullemenu, ← valgt, *Vælg via på tegningen*, chips med ✕); klik på rør/symbol i tegningen tilføjer/fjerner et via-punkt; klik på en 3-vejsventil skifter vej for den valgte gren (klik på grenens overskrift vælger gren); klik-tilstand kun mens trin 2 er åbent (*Færdig* / Esc slår den fra); via-punkter gemmes i `ui.via`. Markeringen ryddes efter hvert klik, så det samme element kan klikkes igen, og et tomt valg nulstiller klik-sporingen. En ventil, hvis valgte vej har ødelagt vejen, kan stadig skiftes tilbage, og klik-linjen/beskeden vises også uden gyldig vej.
- Backend uændret.
- Manual (kap. 08) og LLM-tillæg. Tests: `signalFlow.test.ts` (via), `SignalPathGuideClick.test.ts` (7). Set i browseren: klik på rør tilføjer via-punkt og vejen følger det.

## [4.14.0 build 0367] — 2026-11-09 — Signalveje: vælg animationer pr. slags element

- `lib/pathLook.ts` (ny): grupper (rør, ventiler, 3-vejsventiler, pumper, kontakter), animationstyper pr. gruppe (løbelys kun på rør; farve, stregfarve, blink, vises kun når aktiv, roterer), `animsFor` (rør: på de dele, der får løbelys; 3-vejsventil: kun portene i den vej, vejen bruger — via symbolets port-dele; andre: hele symbolet eller en valgt del), `restoreLook`.
- Backend — `services/signal_paths.py` og `api/signal_paths.py`:
  - `PathElement.anims` ({part, type, params, when}); animationerne lægges på med vejens blok som kilde (aktiv/passiv, "vises kun når aktiv" som aktiv/ikke aktiv);
  - konflikter, `_strip` og `_owned` gælder alle typer (same type + del), så *Ret* og *Slet* fjerner præcis det, vejen har lagt på;
  - `info` giver symbolets dele (id, bibliotek-id, tekst); `valid_data` kontrollerer `anims`;
  - en vej uden nogen animation afvises med en forklaring. Gennemsigtighed (opacity) tilbydes ikke: den kræver et tal-tag.
- Guiden: nyt trin *4. Udseende* (kort pr. slags element med hak, farve, blinkhastighed og del) og *5. Navn og gem*; valgene gemmes i `ui.look` og kommer tilbage ved *Ret*. *Flere slutpunkter* har *← valgt*. `scrollIntoView` er beskyttet.
- Manual (kap. 08) med nyt skærmbillede (`signalvej-udseende`) og LLM-tillæg.
- Tests: `pathLook.test.ts`, `test_signal_branches.py` (animationer, konflikter, regler, info), `SignalPathGuide.test.ts`. Set i browseren: farve på portene i 3-vejsventilerne, farve og blink på ventilen, gem, ret igen.

## [4.13.2 build 0366] — 2026-11-09 — fix: vælg slut i tegningen; "Vælg på tegningen" virker igen

- `SignalPathGuide.svelte`: under *Slut* (første slutpunkt) står nu *← valgt* og *Vælg slut på tegningen*; markeringen fjernes ved start af valget; `picking === null` i stedet for `!picking` (slutpunkt 0 var "falsk").
- Test: `SignalPathGuide.test.ts` (ny komponenttest) og `signalGuideHarness.svelte.ts`. BUGS.md. Manual kap. 08.

## [4.13.1 build 0365] — 2026-11-09 — fix: signalvejens markering følger tegningen, når du flytter noget

- `SignalPathGuide.svelte`: ny prop `rev` (tælles op ved hver ændring i tegningen). Guiden henter grafen igen og beregner vejen forfra, samlet over 300 ms og kun hvis `graphKey(graph)` er ændret. Den valgte vej huskes (`wantSig`) og kommer tilbage efter fortryd.
- `lib/signalPath.ts`: `graphKey`. `pages/DrawEditor.svelte` sender `inspectRev`.
- Test: `signalFlow.test.ts` (`graphKey`). BUGS.md.

## [4.13.0 build 0364] — 2026-11-09 — Signalveje 2: grene, ind/ud fra symbolerne, veje gennem 3-vejsventiler og en interaktiv editor

- **Symbolernes ind/ud og veje** — `lib/symbolFlow.ts` (ny): porte med navn, rolle (ind/ud/begge) og *fælles*; veje (*AB → A*, *AB → B*), standarder for pumpe, kontraventil og 3-vejs ventilerne (målt på symbolerne), matchning af punkter efter position.
  - Backend: `services/symbol_flow.py` og `api/symbol_flow.py` (`/api/symbol-flow`, tekniker; gemmes i `meta` som `symbolflow.<type>`, i backup og gendannelse; ældre backups røres ikke).
  - `SymbolFlowEditor.svelte` og fanen *Symboler › Ind/ud og veje*.
- **Beregning** — `lib/signalPath.ts`:
  - `portAt` (også via delens streg, når et rør ender på ventilens streg), `passAllowed` (en 3-vejsventil kan kun passeres gennem en af sine veje, eller den tvungne);
  - `orient` (retning fra pumpe/kontraventil; uenige symboler nævnes), `describeNet` (grene, retning, vej pr. gren), `questionsOf` (ét spørgsmål pr. vej gennem en flervejs-ventil).
  - `connectionGraph` giver nu hvert punkts placering på symbolet (`fracs`) og hver strengs tykkelse og stiplethed.
- **Tynde og stiplede streger er ikke rør** (BUGS.md).
- **Backend** — `services/signal_paths.py` og `api/signal_paths.py`:
  - flere slutpunkter (`ends`, højst 4): en OG-kæde pr. gren og en ELLER-blok over grenene for fælles stykker; én gren giver præcis de samme blokke som før;
  - hvert element husker sin slutblok (`block`) og sine grene (`branches`), og betingelser kan gælde bestemte grene;
  - `ui` (guidens valg) med samme størrelsesgrænse i API og backup; `valid_data` kontrollerer grene og blokke; betingelser på start/slut får de rigtige grene.
- **Guiden** — `SignalPathGuide.svelte` omskrevet: arbejdsgang *Start/slutpunkter → Vejen → Brug denne vej → Betingelser → Navn og gem*, live beregning ved hver ændring, ventilens vej som rullemenu, farve pr. gren, animeret retning i tegningen (`highlightPath` med farver, retning og fokus), peg og klik mellem liste og tegning, valg i tegningen af flere slutpunkter.
- **Manual** (kap. 08) og LLM-tillæg: nye afsnit og 4 nye skærmbilleder (`signalvej-vej`, `signalvej-tegning`, `signalvej-betingelser`, `symbol-ind-ud`).
- Review (reviewer-agent), rettet: størrelsesgrænse på `ui`, betingelser på start/slut, kontrol af data fra backup.
- Tests: `signalFlow.test.ts`, `test_signal_branches.py`. Set i browseren (grene, ventilvej, lås, Ind/ud-fanen).

## [4.12.0 build 0363] — 2026-11-08 — Gemt beregning af bindinger og synlige tags (hurtigere for begrænsede brugere)

- `storage/db.py`: `Database.config_gen` stiger, når en SQL-sætning skriver til en konfigurationstabel (`CONFIG_TABLES`). Det sker via en sqlite-trace-funktion, så ingen skrivevej kan glemme det, heller ikke kaskader og egne transaktioner.
- `storage/files.py`: `DrawingFiles.stamp` (ændringstid og størrelse).
- `services/drawings.py`: `stamp()` (`config_gen` og SVG-stempel) og gemt `effective_bindings` (en kopi af listen returneres; stemplet tages før beregningen).
- `services/scope.py`: gemt `visible_tags` pr. sæt af tegninger.
- Måling: 11 ms beregnet og 0,21 ms gemt (tegningen "varme"). `/metrics`: `scada_bindings_cache_hits_total` og `scada_bindings_cache_misses_total`.
- Tests: `test_bindings_cache.py`. De eksisterende scope-, tegnings-, symbol- og backup-tests er uændrede og bestået.

## [4.11.0 build 0362] — 2026-11-08 — Samme Let's Encrypt-certifikat på SCADA'en som på proxyen

- `deploy/cert-receive.sh` (ny, root, sshd forced command): tager imod en tar med fullchain.pem + privkey.pem på stdin.
  - Kontrol: kun de to navne, almindelige filer, PEM ≤ 64 KB, gælder SCADA'ens navn (`-checkhost`), ikke udløbet; et uændret certifikat springes over.
  - Filerne lægges i `/etc/letsencrypt/live/hypervision-scada` og installeres med `cert-deploy.sh` (parkontrol, `nginx -t`, gendannelse).
  - Log i `<state>/cert-receive.log`.
- `deploy/proxy-cert-push.sh` (ny): certbot deploy-hook på proxyen, der sender certifikatet med en dedikeret ed25519-nøgle (`BatchMode`, `StrictHostKeyChecking`).
- `install.sh` installerer `cert-receive.sh`. `docs/TLS_LETSENCRYPT.md` har et nyt afsnit.
- Test: `test_cert_receive.py` (rigtig openssl og rigtig cert-deploy.sh).

## [4.10.1 build 0361] — 2026-11-07 — fix: Opsummér døgnet blev afbrudt på demoen

- `assist_tools.gather`: ved `summary` sendes kun alarmtallene (ingen manualuddrag); `MAX_SUMMARY` 12 → 10.
- `assistant.py`: hele svaret må tage 420 s (`ANSWER_TOTAL_S`, før 240 s).
- Manual: *Alarmer › Opsummér døgnet*. Test: `test_assist_setup.py`. BUGS.md.

## [4.10.0 build 0360] — 2026-11-07 — Hjælperen fase 3 (tag-beskrivelser, signal-forslag, døgnets alarmer), opvarmning og Raspberry Pi-pakker

- **Fase 3** — `services/assist_setup.py` (ny):
  - `TagDescriber`: beskrivelse (≤ 60 tegn) og enhed (fast liste) ud fra ST-variablernes navne;
  - `SignalHelper`: kommando (kun skrivbare) og tilbagemelding pr. signal; kandidat-tags som i signalvejen (`pick_tags`);
  - begge med JSON-skema og validering, ingen kilder eller adresser i prompten.
- Endpoints `POST /api/assist/describe-tags` og `POST /api/assist/symbol-signals` (tekniker, SSE). Den sidste tjekker tegningsadgang og synlige tags. Audit logger kun metadata.
- **Døgnets alarmer** — `assist_tools.alarm_summary`: deterministisk optælling af historikken (antal, aktiv tid, kvitteringstid, stadig aktive). Den bruges, når `context.summary` er sat (*Alarmer › Opsummér døgnet*). `dur()`.
- **Opvarmning** — `AssistantService.warm_up`/`keep_warm` (baggrundsopgave i `main.py`):
  - et kald med systemprompten og `max_tokens=1`, når tjenesten bliver klar, og igen ved ny model eller genstart;
  - spørgsmål venter på opvarmningen (`warming`), og hændelsen `queued` har `warming`;
  - metrics `scada_assist_warm` og `scada_assist_warmups_total`.
- **Raspberry Pi** — LLM-pakker til aarch64 (Hurtig og Standard) er udgivet og låst fast i `deploy/llm-models.json`:
  - glibc pr. arkitektur i kataloget (aarch64 2.38, x86_64 2.34) og i pakkens manifest (`make-llm-package.sh`);
  - `machine_glibc`/`glibc_problem`: kataloget markerer varianter `blocked`, og en pakke til en nyere glibc afvises.
- **Frontend:**
  - `Tags.svelte`: *✦ Beskriv med hjælperen*, og beskrivelse og enhed kan rettes før import;
  - `SymbolGuide.svelte`: boksen *Foreslå tags* i trin 2;
  - `Alarms.svelte`: *Opsummér døgnet*;
  - `AssistPanel`: *Hjælperen starter op*;
  - `SystemAssist`: viser årsagen, når en variant er blokeret.
- **Manual:** tekst i 03, 05, 10 og 13, og *Menuen* er rettet (klik, ikke hover). Skærmbillederne er taget om på testserveren med v4.9.0 (56 af 58; *tegn-erstat* og *guide-former* er de gamle).
- `manual-screenshots.mjs`: `SKIP`, og menuerne åbnes med klik.
- **BUGS.md:** v0.111.2 lukket; v1.12.1 noteret (plc1 svarer ikke).
- **Review (reviewer-agent), rettet:**
  - markeringen af et spørgsmål i gang udløber først efter den længste ventetid (`ASK_STALE_S`);
  - `complete()` venter også på opvarmningen;
  - fejlet opvarmning prøves igen med stigende pause (højst 30 min);
  - ugyldig `llama[arch]` i kataloget giver ikke fejl 500;
  - ældre ARM-pakker uden glibc-felt behandles som 2.38.
- Tests: `test_assist_setup.py` (ny) og `test_assist.py` (opvarmning, glibc). Set i browseren mod en falsk LLM.
 — 2026-11-07 — Manualen gennemgået; skjult LLM-manual til hjælperen; nyt manual-indeks

- **LLM-manual** — `services/manual_compiler.py` (ny):
  - kompilerer `frontend/src/manual/*.md` til stykker på højst 110 ord med sti-overskrift (`##` og `###`);
  - tabeller foldes ud til sætninger (store tabeller giver et stykke pr. række), billedtekster tages med, og interne links slås op til afsnittets navn;
  - hvert stykke henviser til afsnittet i den store manual (frontendens ankre, også `m3-` for `###`).
- **Tillæg** — `frontend/src/manual/llm/*.md` (nye, vises ikke i Manual-siden): spørgsmål/svar med `<!-- kilde: fil#anker sha:… -->`.
  - `check()`/`sync()` og CLI'en `python -m app.services.manual_compiler --check|--sync|--anchors|--dump`;
  - `make-package.sh` kører `--check`.
- `services/assist_knowledge.py`:
  - søger i den kompilerede manual og tillæggene (spørgsmålet tæller som overskrift);
  - højst ét stykke pr. afsnit i træffene;
  - sammensatte ord, manualen ikke har, deles ("energiforbrug" → energi + forbrug);
  - nye stopord (se, ser, pr, gør).
- `services/assist_tools.py`: `MANUAL_CHARS` 380 → 480.
- **Måling** (top 3 af 45 typiske spørgsmål): 34 → 45. 15 nye formuleringer: 10 → 13 (de to sidste rammer det rigtige afsnit under et andet navn).
- **Manual:**
  - mere tekst i 01, 02, 03, 05, 08, 10 og 13 — *De seks trin* er delt i *Trin 1–6*, og *Logikblokke* har en trin-for-trin-vejledning;
  - fejl rettet: alarmprioriteten følger niveauet, versionen står i topbjælken, og menutabellen er opdateret.
- **11 nye skærmbilleder** — `tools/manual-screenshots.mjs`, taget fra demoen: guide-logik-udfyldt, guide-logik-test, forbindelse-haandtag, signalveje, hjaelper-panel, tags-flere, status, notifikationer, integrationer, certifikater og system-hjaelper.
- **Manual-siden** (`pages/Manual.svelte`, `lib/manual.ts`):
  - kapitlerne i grupper med ikon og undertekst (`GROUPS`, `groupChapters`);
  - afsnittet, man læser, markeres;
  - søgetræf viser afsnit og fører direkte til det;
  - *Til toppen*, brødkrumme og en sammenfoldelig menu på smal skærm;
  - markeringen af søgeordet forsvinder, når søgningen ændres (BUGS.md).
- Tests: `test_manual_compiler.py` (ny) og `manual.test.ts`. Manual-siden er set i browseren, bred og smal.
 — 2026-11-07 — Symboler › Bibliotek: Redigér grafikken

- `lib/SymbolLibrary.svelte`: *Redigér* ved hvert symbol opretter en arbejdstegning ("Symbol – …") og åbner Tegn på `#draw/<tegning>/sym:<type>`.
- `pages/DrawEditor.svelte`:
  - redigeringstilstand: symbolet indsættes og vælges, og et banner viser *Gem i biblioteket (ny version / som kopi)* og *← Tilbage til biblioteket*;
  - navnet foreslås: et eget symbol får samme navn (ny version), et indbygget "… (egen)";
  - bagefter tilbydes at slette arbejdstegningen og gå tilbage.
- `services/library.py` (`export_from_drawing`): en ny version uden opsætning på symbolet beholder den forrige standardopsætning, når delene findes endnu (som ved import). Ellers fjernes den med en besked.
- Test: `test_library.py`. Set i browseren (indbygget → kopi, eget → version 2, arbejdstegningen slettet). Manual: *Tegn › Organisér biblioteket*.

## [4.7.0 build 0357] — 2026-11-07 — Tags: vælg flere og slet dem samlet

- `pages/Tags.svelte`:
  - afkrydsning pr. tag, *Vælg alle* (delvist markeret) og *Fravælg*;
  - *Slet valgte (n)* viser samlet brug (`/api/tags/usage`) og sletter alle i én transaktion med backup (`/api/tags/remove`, samme som et enkelt tag);
  - fejl vises over listen (alt eller intet).
- Ny `lib/multiPick.ts` (`pickInList`: klik og Shift-interval) med test.
- Manual: *PLC'er og tags › Tags*. Set i browseren (Shift-interval, slet 3 af 5).

## [4.6.2 build 0356] — 2026-11-07 — Hjælper: fejl 500 med Ministral (roller skal skifte)

- `services/assistant.py`: ny `alternating` sørger for, at samtalen, der sendes til modellen, skifter mellem bruger og assistent (beskeder i træk slås sammen, start med bruger, slut med assistent). Ministral-3-8B's chat-skabelon afviste ellers kaldet med 500.
- Tests: `test_assist_ask.py` (`alternating` og hele kaldet).

## [4.6.1 build 0355] — 2026-11-07 — Tag fat i et symbol bag et andet; hjælperens manual-søgning finder mere

- `src/lib/draw/engine.ts`:
  - `blockersAbove` + klik-igennem ved museklik på et valgt element, der ligger bag andre, så det trækkes i stedet for at det forreste bliver valgt;
  - et klik uden bevægelse vælger det forreste.

  Test i `engine.test.ts`; afprøvet i browseren.
- `services/assist_knowledge.py`:
  - prefiks-match for sjældne ord og stillings-synonymer (bag/bagved, foran/forrest …);
  - ekstra vægt til overskriftens ord (`HEAD_BOOST`);
  - accenter (é) normaliseres;
  - stammen kører to gange og fjerner dobbelt konsonant; "s" fjernes fra korte ord.
- `services/assist_tools.py`: 3 manualafsnit à 380 tegn (før 2 à 500), så prompten ikke vokser.
- Test: `test_assist_ask.py` (danske varianter, overskrifter). Manual: *Tegn › Vælg, flyt og markér*.

## [4.6.0 build 0354] — 2026-11-07 — Tegn: rør følger med under trækket og fanges snorlige

- `svgedit-host/pipes.js`:
  - `straightTarget`: det første lodrette/vandrette stykke foran tilslutningspunktet, som enden flugter med inden for tolerancen; stubben springes over;
  - `straightEnd`: ét lige stykke i stedet for stub og hak, når enden flugter.
- `svgedit-host/scada-core.js`:
  - under et træk: forhåndsvisning af de tilsluttede rør (eget overlay) og dæmpning af de rigtige rør;
  - blå stiplet linje, når der vil blive fanget;
  - ved slip fanges symbolet, så røret står snorlige. Det vinder over gitter og objekter; hjælpelinjer vinder stadig;
  - `followPipes` bruger rørets forløb fra før trækket, så resultatet bliver lige uden hak.

  Fortryd fungerer som før: ét trin, og forhåndsvisningen er aldrig en del af tegningen.
- `pages/DrawEditor.svelte`: *Fang rør lige* (gemmes som de andre indstillinger).
- Tests: `pipes.test.ts` (fang og lige ende, stub springes over, knæk bag punktet, lige rør mellem to symboler). Set i browseren med en testtegning (lille træk fanges, stort træk følger med med knæk, Ctrl+Z).
- Manual: *Forbindelser › Tilslutningspunkter og retning*.

## [4.5.0 build 0353] — 2026-11-07 — Signalvej: vælg start og slut ved at klikke i tegningen

- `lib/SignalPathGuide.svelte`:
  - *Vælg på tegningen*: første klik på et symbol = start (orange ramme), andet klik = slut, og vejen findes af sig selv;
  - rør, tekster og visninger afvises med en forklaring;
  - *Afbryd valg*/Esc stopper.

  Listerne og *← valgt* findes stadig.
- `lib/signalPath.ts`: `pickNext` (reglen, med test i `signalPath.test.ts`).
- Manual: *Forbindelser › Signalveje*. Set i browseren på demo-tegningen.

## [4.4.3 build 0352] — 2026-11-07 — Trendgraf: "Maximum call stack size exceeded" ved et fladt forløb

- `lib/chartGraphic.ts`:
  - `niceTicks` og `yRange` behandler et spænd, der kun er afrundingsstøj, som fladt;
  - `niceTicks` laver højst max+1 inddelinger og fjerner dubletter;
  - nye `maxOf`/`minOf` erstatter `Math.max/min(...liste)` (y-akse, forklaring).
- Test: `chartGraphic.test.ts` (fladt forløb med støj som på demo'en, loft over inddelinger, lange lister).

## [4.4.2 build 0351] — 2026-11-07 — Betjening: den skrevne værdi vises med det samme

- `services/operate.py`:
  - `_show` lægger PLC'ens tilbagelæste værdi i live-cachen lige efter en skrivning eller et skift, så den ikke venter på næste polling-runde (2–5 s uden SSE);
  - `write_value` (symbolernes betjening) læser én gang tilbage; fejler det, tager pollingen over som før.
- Test: `test_operate.py` (polling sat til 30 s: værdien står alligevel på skærmen straks).
- Fundet ved måling på demo'en (BUGS.md): selve websiden er hurtig, det var PLC-værdierne, der kom sent.

## [4.4.1 build 0350] — 2026-11-07 — Hjælper: pladstjekket regner som root-hjælperen

- `services/assistant.py`:
  - `install_need` (pakken + den installerede model + 1 GB, som `deploy/apply-llm.sh`) bruges i `stage`;
  - ny `precheck_download` kræver plads til både hentning og installation, før en hentning startes, og foreslår at fjerne den installerede model.
- `api/assist.py`: hentningen bruger `precheck_download`.
- Test: `test_llm_catalog.py` (pladsregningen). Fundet på demo-VM'en (BUGS.md).

## [4.4.0 build 0349] — 2026-11-07 — Vælg LLM-model fra en liste (hentes fra GitHub releases)

- Ny `services/llm_catalog.py`:
  - kataloget fra `deploy/llm-models.json` (variant, beskrivelse, profiler, `published`-arkitekturer);
  - GitHub-klient: kun api.github.com/github.com/GitHubs download-domæner, også efter omdirigering, `trust_env=False`;
  - `download`: delene (`.partNN`) skrives i én fil, mens SHA256 beregnes; størrelse og diskplads tjekkes undervejs; kan afbrydes. Passer kontrolsummen ikke, kasseres pakken.
- `api/assist.py`:
  - `GET /api/assist/catalog` og `POST`/`DELETE /api/assist/download` (admin);
  - hentningen kører i baggrunden og klargøres med `stage` (samme kontrol som upload), hvorefter installationen bestilles;
  - audit `assist.download`/`assist.package`.
- `deploy/publish-llm-release.sh`: deler pakken i dele på 1900 MiB og udgiver dem med `.sha256` som release `llm-<model>-<build>` (prerelease, aldrig "latest", så SCADA-OTA'en ikke påvirkes).
- `deploy/llm-models.json`: tre varianter, Hurtig (Qwen3.5-2B, ny), Standard (Qwen3.5-4B) og Stor (Ministral-3-8B), med beskrivelse og profiler. `install.sh` installerer kataloget; `config.py` har `llm_catalog` (`SCADA_LLM_CATALOG`).
- `pages/SystemAssist.svelte`: *Vælg model* med kort pr. variant, *Hent og installér*, fremdrift og *Afbryd*. Upload står under *LLM-pakke (lukket net)*.
- **Review (reviewer-agent) rettet:**
  - pakkens SHA256 er låst fast i kataloget pr. arkitektur (`published: {arch: sha}`), så en ændret udgivelse på GitHub afvises;
  - højst 16 GB pr. pakke;
  - afbrydelse kan ikke gå tabt (nulstilles ved start) og stopper også klargøring og installation;
  - audit `assist.download.cancel` med den, der afbrød;
  - hentningen stoppes ved nedlukning, og en halv pakke ryddes op ved opstart;
  - intet katalog og ingen hentning, når `SCADA_UPDATE_REPO` er tom eller ugyldig;
  - udgivelses-scriptet fjerner gamle dele og opdaterer noterne.
- Tests: `backend/tests/test_llm_catalog.py` (11, falsk GitHub: dele, omdirigering, forkert SHA, fremmed vært, afbrudt, API, roller). Set i browseren.
- Manual: *System › Hjælper (LLM)*.

## [4.3.0 build 0348] — 2026-11-07 — Signalvej: forklar med egne ord (LLM-hjælper fase 2b)

- **Ny `services/assist_signal.py`:**
  - prompten indeholder kun symbolerne på vejen (navn og rolle) og højst 30 kandidat-tags: symbolernes egne først, så dem der deler ord med beskrivelsen, så resten. Hvert tag har navn, til/fra eller tal, enhed og beskrivelse, renset med `clean` og uden kilder eller adresser;
  - svaret skal følge et fast JSON-skema, hvor symbol-id'er og tag-navne er låst til listerne (`enum`, håndhævet af llama-server);
  - `validate`: symbolet skal være på vejen, tagget skal findes og være synligt, til/fra → til/fra, tal → ≥/≤/= og en endelig værdi; resten bliver *ikke udfyldt*;
  - deler kø, rate-grænse og ét-ad-gangen pr. bruger med hjælper-panelet.
- `api/signal_paths.py`: `POST /api/drawings/{id}/signal-paths/suggest` (tekniker og op) som server-sent events. Audit `signal_path.suggest` logger kun antal og svartid. Gemmer intet.
- Ny `api/sse.py`: fælles SSE med keepalive og oprydning. `/api/assist/ask` bruger den nu også.
- Frontend:
  - `lib/assist.ts`: `postStream`;
  - `lib/SignalPathGuide.svelte`: *Forklar med egne ord* i trin 3 med *Udfyld med hjælperen*/*Stop*, tid, mærket *forslag* og *ikke udfyldt*. Vises kun, når hjælperen er slået til.
- Review rettet: element-id'er og tag-navne, der ikke kan stå uændret i prompten, sendes ikke med (kan ikke bryde ud af `<data>`); højst 25 spørgsmål i API'et.
- Tests: `test_signal_paths.py` (+5: gyldige/ugyldige forslag, skema og prompt uden tag-kilder, regler, fejl som hændelse, valg af kandidat-tags, usikre navne). Set i browseren med en falsk LLM.
- Manual: *Forbindelser › Signalveje*.

## [4.2.0 build 0347] — 2026-11-07 — Signalvej i Tegn (LLM-hjælper fase 2a)

- **Ny tabel `signal_paths`** (skema 15, additiv) og `storage/db.py`: `list_signal_paths`, `get_signal_path`, `write_signal_path` (signalvejen og alle berørte symbolopsætninger i ÉN transaktion). Backup eksporterer og gendanner signalveje (`services/backup.py` validerer dem).
- **Ny `services/signal_paths.py`:**
  - betingelserne bliver til logikblokke (OG, højst 4 indgange pr. blok, kædet via `@L1`, højst 25 betingelser) på vejens første element med løbelys;
  - hver del på vejen får et løbelys (kilde = blokken, `reverse` efter vejens retning, `when`);
  - alt valideres med `validate_config`;
  - ret/slet fjerner kun vejens egne løbelys og blokke (genkendt på kilde og del), og opsætninger, som vejen selv oprettede, slettes igen, når de er tomme;
  - konflikter: løbelys, der allerede ligger på et rør, kræver `replace`, og et rør i en anden signalvej afvises.
- **Ny `api/signal_paths.py`** (tekniker og op): `GET`/`POST /api/drawings/{id}/signal-paths`, `PUT`/`DELETE …/{sid}`, `POST …/info` (symbolernes egne tags som forslag + alle tags med til/fra-type). Audit `signal_path.save`/`delete`.
- **Frontend:**
  - `svgedit-host/scada-core.js`:
    - `connectionGraph()`: tilslutningspunkter, streger med punkter langs dem, og rørenes faste ender;
    - `highlightPath()`: orange overlay, kun på skærmen.
  - Ny `lib/signalPath.ts` (ren logik):
    - naboer ud fra sammenfaldende punkter, faste rør-ender og ender midt på en streg (afgrening uden T-stykke);
    - korteste vej + op til 3 alternativer, ikke gennem statusfelter/visning;
    - rolle pr. symbol og løbelysets retning pr. del;
    - svar → betingelser.
  - Ny `lib/SignalPathGuide.svelte` som sektionen *Signalveje* i Tegn (`pages/DrawEditor.svelte`, `lib/draw/panels.ts`).
- **Plan-ændring:** grafen bygges i frontend (geometrien kendes kun i browseren; demo-tegningen bruger rør-symboler og tegnede streger, ikke kun `data-hv-pipe`). Noteret i PLAN.md.
- **Review (reviewer-agent) rettet:**
  - scope-tjek på alle signalvej-endpoints (værn; teknikere er i dag aldrig begrænset);
  - `write_signal_path` tjekker i transaktionen, at opsætningerne ikke er ændret imens (409);
  - en opsætning, vejen har oprettet, slettes kun, når den er helt som standarden;
  - kun vejens egne blokke fjernes (id + navnet "Signalvej: …");
  - backup-data for signalveje valideres;
  - ejerens opsætning kan ikke slettes uden om signalvejen (`SymbolService.delete`/`delete_many`);
  - `info` viser kun tags, brugeren må se.
- **Tests:** `backend/tests/test_signal_paths.py` (12), `frontend/src/lib/signalPath.test.ts` (12). Afprøvet i browseren på demo-varmeanlægget.
- **Manual:** *Forbindelser › Signalveje*.

## [4.1.1 build 0346] — 2026-11-07 — Hjælper: kortere prompt og korrekt tokens/s

- `services/assist_tools.py`: data i prompten højst 2000 tegn (før 3200), manualuddrag 500 tegn (før 700). Målt på demo-VM'en tog prompten 80–120 s at læse.
- `services/assistant.py`: svar højst ca. 80 ord / 220 tokens (før 120 ord / 320).
- `llm/client.py`: `Completion.tokens_per_s` er nu skrivehastigheden (uden `prompt_ms`).
- `lib/AssistPanel.svelte`, manual *Drift › Hjælperen*: svartid 1–2 minutter.
- `docs/LLM_ANALYSE.md`: anden måling (hjælper-panelet på demo-VM'en). Test: `test_assist_ask.py`.

## [4.1.0 build 0345] — 2026-11-07 — Hjælper-panel (LLM-hjælper fase 1)

- Nyt `services/assist_knowledge.py`: manualen opdelt i `##`-afsnit med samme ankre som Manual-siden og søgt med BM25 i ren Python (danske stopord og endelser, ingen ny afhængighed). Indekset bygges igen, når filerne ændres.
- Nyt `services/assist_tools.py`: læse-værktøjer med brugerens rettigheder (aktive alarmer, én alarm, tag-værdier, trend-resumé, tegningens symboler og elementer, manual-søgning). Værktøjerne vælges ud fra siden og ordene i spørgsmålet, ikke af modellen: det giver ét LLM-kald pr. spørgsmål og ingen værktøjskald fra tekst i anlægget. Tekst fra anlægget renses for styretegn, `<`/`>` og netværksadresser. Tag-kilder og PLC-adresser sendes aldrig med.
- `llm/client.py`: `stream()` med strømmede svar (SSE fra llama-server), `cache_prompt`, tidsgrænse til første stykke og for hele svaret, og `prompt_ms`.
- `services/assistant.py`: `prepare` (validering, rate-grænse 30 pr. time og ét ad gangen pr. bruger, data samles før strømmen) og `answer` (kø, hændelser `sources`/`queued`/`delta`/`done`/`error`). Ny tæller `asks`.
- `api/assist.py`: `POST /api/assist/ask` (operatør og op) som server-sent events med keepalive hvert 10. sekund (nginx/proxy-timeout) og `X-Accel-Buffering: no`. Lukker browseren, stoppes modellen. Audit `assist.ask` logger kun side, værktøjer, svartid og tokens. `/available` har nu `can_ask`.
- `config.py`: `manual_dir` (`SCADA_MANUAL_DIR`). `deploy/install.sh` kopierer `frontend/src/manual` til `<app>/frontend/manual`.
- `main.py`: kobler læse-værktøjerne på hjælperen. `services/metrics.py`: `scada_assist_asks_total`.
- Frontend: nyt `lib/AssistPanel.svelte` (panel i højre side, forslag pr. side, strømmet svar, kilder som links, Stop, Ryd, samtalen kun i sessionStorage), `lib/assist.ts` (SSE-tolkning, kontekst fra adressen, sikker markdown uden links/billeder), `lib/assistStore.svelte.ts`. `App.svelte`: knappen **Hjælper** i topbjælken, og indholdet rykker til side på brede skærme. `pages/Alarms.svelte`: knappen **Forklar**. `pages/Status.svelte`: antal spørgsmål.
- Tests: `backend/tests/test_assist_ask.py` (11), `frontend/src/lib/assist.test.ts` (6).
- Manual: *Drift › Hjælperen*, *Alarmer › Forklar en alarm*, *System › Hjælper (LLM)*.

## [4.0.2 build 0344] — 2026-11-07 — Hjælper: selvtestens svar blev klippet

- `services/assistant.py`: selvtestens JSON-skema tillod kun 80 tegn, så svaret blev afbrudt midt i et ord. Nu 240 tegn og 160 tokens.
- `docs/LLM_ANALYSE.md`: første måling på demo-VM'en (3,6 tokens/s, 2 GB RAM, ingen påvirkning af SCADA'en).

## [4.0.1 build 0343] — 2026-11-07 — Hjælper: profilforslag for "16 GB"-VM og korrekt pladsberegning

- `services/hwprofile.py`: grænserne er sat ned til ca. 90 % af nominel RAM (7/14/28 GB). En "16 GB"-VM melder 14.985 MB og fik før forslaget vm-8.
- `deploy/apply-llm.sh` og `services/assistant.py` (`stage`): installationen kræver kun én pakkestørrelse ekstra ad gangen (kilden slettes, før der pakkes ud) plus den gamle installation og 1 GB. Før blev der krævet 2–2,2 gange pakken, og det afviste demo-VM'en (10 GB disk).
- Test: `test_assist.py`.

## [4.0.0 build 0342] — 2026-11-06 — LLM-hjælper fase 0: hardwareprofil, lokal LLM-tjeneste, LLM-pakke og System › Hjælper

- **Backend:**
  - Nyt lag 4c `app/llm/client.py`: kun loopback, `trust_env=False`, typede fejl, `json_schema`. Qwen3.x's "tænkning" slås fra.
  - `services/hwprofile.py`: finder arkitektur, kerner, RAM, AVX2 og Pi-model. Profilerne pi4/lille/pi5/vm-8/vm-16/vm-32 gemmes i `config/hw.json`.
  - `services/assistant.py`:
    - kontrol af LLM-pakken: sikre stier, kun filer og mapper, manifest, arkitektur, modelfil, licenser og diskplads;
    - anmodninger til root-hjælperen (install/start/stop/remove);
    - højst ét kald ad gangen; selvtest; tællere.
  - `api/assist.py`:
    - `GET /api/assist/available` (alle roller);
    - `GET /status`, `PUT /profile`, `POST/DELETE /package` (streamet, SHA256 beregnes undervejs), `POST /service`, `POST /test` (admin);
    - alle handlinger auditeres som `assist.*`.
  - `main.py`, `config.py` (`SCADA_LLM_PORT`), `health.py`, `metrics.py` (`scada_assist_*`).
- **Deploy:**
  - `hypervisionplc-scada-llm.service`: llama-server som `scada-llm` med `Nice`, `CPUWeight=20`, `MemoryMax`, uden swap og med fuld hærdning. Kun 127.0.0.1.
  - `apply-llm.sh` (root) og `hypervisionplc-scada-llm-apply.path`/`.service`:
    - flytter anmodning og pakke ind i rootens mappe og tjekker SHA256 igen;
    - tar-listen skal kunne læses, ellers afvises pakken;
    - modelfilens SHA256 tjekkes mod manifestet;
    - tal valideres, og ældre installationer ryddes.
  - `install.sh`: `--hw <profil>`, brugeren `scada-llm` og hjælper-enhederne.
  - nginx: `/api/assist/package` (16 GB, streamet).
  - `make-llm-package.sh` + `llm-models.json`: bygger én samlet LLM-pakke af llama.cpp b12179 (MIT) og Qwen3.5-4B Q4_K_M eller Ministral-3-8B (Apache-2.0), med faste adresser og SHA256.
- **Frontend:**
  - ny side *System › Hjælper (LLM)* (`pages/SystemAssist.svelte`);
  - `lib/upload.ts` (upload med fremdrift);
  - kort på *Status*; menupunkt i `nav.ts`.
- **Tests:** `test_assist.py` (13, inkl. root-hjælperen med falsk systemctl), `upload.test.ts`, `nav.test.ts`.
- **Dokumentation:** `ARCHITECTURE.md` (lag 4c), manualen (*System › Hjælper*), `PLAN.md`, `docs/LLM_ANALYSE.md`.

## [3.36.0 build 0341] — 2026-11-06 — Opsæt symbol direkte på et element uden navn

- `pages/DrawEditor.svelte`: *Valgt element* viser **Opsæt symbol (6 trin) …** også for elementer uden navn. `nameAndGuide` spørger efter et navn og åbner guiden. Før stod kun en tekst om at give elementet et navn, og den var let at overse for rør.
- Ny `lib/draw/naming.ts` (`suggestName`) foreslår første ledige navn: "Rør 1" for forbindelser, symbolets navn eller elementtypen. Test: `naming.test.ts`.
- **Manual:** `08-forbindelser` (Løbelys og animation).

## [3.35.0 build 0340] — 2026-11-06 — Flervalg i symbolbiblioteket og sletning af tags i brug

- **Flervalg i Symboler › Bibliotek:**
  - `SymbolLibrary.svelte`: afkrydsning pr. symbol, *Vælg alle* og Shift-interval. *Flyt valgte til …* og *Slet valgte* (kun egne symboler).
  - `library.ts`: `moveSymbols`.
  - `libraryStore.svelte.ts`: `deleteOwnMany`.
  - Backend:
    - `POST /api/library/symbols/delete` (`api/library.py`, tekniker, auditeres som `library.delete_many`);
    - `LibraryService.delete_many`;
    - `db.delete_library_symbols` i én transaktion: mangler et symbol, slettes intet.
- **Slet tags i brug:**
  - `pages/Tags.svelte` + ny `lib/tagUsage.ts`: *Slet* viser, hvor tagget bruges, og sletter det med alle henvisninger.
  - Backend:
    - `POST /api/tags/usage` og `POST /api/tags/remove` (`api/routes.py`, tekniker, auditeres som `tag.remove`);
    - `PlcRemovalService.tag_usage`/`remove_tags` (`services/plc_removal.py`). Backup (`scada-foer-tag-slet-…`, og af historikken ved trend) tages, når tagget bruges eller har historik. Scan og transaktion kører uden `await` imellem. Tags, der bruges af API-nøgler, kan kun slettes af admin;
    - `db._remove_tags_cascade` er fælles for Fjern PLC og sletning af tags;
    - `backup.py`: slagsen "før tags slettet".
  - Alarmer tælles ikke længere dobbelt i svaret fra Fjern PLC.
- **Tests:**
  - `test_library.py`: `test_delete_many_all_or_nothing`.
  - `test_plc_removal.py`: 3 nye tests.
  - `tagUsage.test.ts`; `library.test.ts`: `moveSymbols`.
- **Manual:** `05-plcer-og-tags.md` (Slet tag) og `07-tegn.md` (flervalg).

## [3.34.0 build 0339] — 2026-11-06 — Fjern PLC: flyt tagsene til en anden PLC eller fjern alt

- **Backend:**
  - Nyt `backend/app/services/plc_removal.py`:
    - `usage` viser, hvad en fjernelse rammer;
    - `move` validerer alle tags først (`TagService._validate`) og ændrer derefter kilderne i én transaktion; runtimes for begge PLC'er genstartes, og live-værdier ryddes;
    - `remove_all` tager backup først (`scada-foer-plc-fjern-…`). Derefter fjernes i én transaktion bindinger (løbelysets retnings-tag tømmes), tagsene i symbolopsætninger og gruppe-animationer, ugeprogrammer, trendvisninger (tomme visninger slettes), API-nøglers scope, `alarm_state`, tags og PLC. Trendhistorikken glemmes bagefter, og alarmhændelserne bevares.
  - `storage/db.py`: `move_plc_tags` og `remove_plc_cascade`. Begge ruller tilbage, hvis PLC'en har fået tags imens.
  - `api/routes.py`: `GET /api/plcs/{key}/usage` og `POST /api/plcs/{key}/remove` (admin; ved "all" skal nøglen bekræftes). Handlingen auditeres som `plc.remove` med optælling. `main.py`.
- **Frontend:** ny `PlcRemove.svelte` (oversigt, valg og bekræftelse; problemer pr. tag vises). `Plcs.svelte` åbner dialogen fra *Fjern*. `api.ts`: `ApiError.body` (serverens fejlsvar).
- **Rettelser fra review før commit:**
  - Backuppen før fjernelsen kunne ikke hentes (filnavnet blev afvist). `backup.py` kender nu `foer-plc-fjern` og `pre-update` (også opdateringernes backup) og viser deres slags.
  - Historikken tages med i et eget snapshot (`trends-foer-plc-fjern-…`), før den slettes.
  - Alarmerne glemmes også i hukommelsen, så næste evaluering ikke skriver dem tilbage. Det gælder også PLC'ens kommunikationsalarmer (`AlarmService.forget`). Ved flyt følger `alarm_state.plc` med.
  - Backup og sletning af historik kører i en tråd.
  - Mål-PLC'en advarer, hvis den er slået fra eller mangler adgangskode.
  - Fejlede forsøg auditeres også.
  - `dir_tag` læses sikkert, og en forkert kilde samles med de andre problemer.
- **Tests:** `backend/tests/test_plc_removal.py` (7).
- **Manual:** `05-plcer-og-tags.md` og billedet `plc-fjern.png`.

## [3.33.1 build 0338] — 2026-11-06 — Fix: SVG-import ignorerede CSS på elementtyper

- `backend/app/services/library.py` `_inline_css`:
  - Regler på elementtyper (`path,rect,circle{…}`, `text{…}`, `*`) og type.klasse (`rect.w{…}`) skrives nu ind på elementerne ligesom klasse-regler.
  - Rækkefølgen er type < klasse < egen style, som i CSS.
  - Selektorer, der ikke kan bruges, giver én samlet advarsel pr. fil i stedet for én pr. regel.
- `backend/tests/test_library.py`: 2 nye tests med Jans P&ID-filer.
- Manual: `07-tegn.md`.
- Koden kom med i commit `3a34a7f`. Versionsbump og dokumentation fulgte i den næste commit, fordi dokumentationsscriptet fejlede.

## [3.33.0 build 0337] — 2026-11-06 — Nye tegneredskaber i Tegn: polygon, stjerne, n-kant, bue, billede, streg, pile, gradient, skygge og lag

- **Nyt `frontend/svgedit-host/shapes.js`** (ren logik og DOM-hjælpere):
  - former: regulær polygon og stjerne, `regenerate` (nye spidser/hjørner, midte og størrelse bevares) og bue (`arcPath`, `angleTo`);
  - streg: `dashArray`/`dashKind` (skaleret med tykkelsen);
  - defs: pile `hv_pil_<farve>`, gradient `hv_grad_<id>` og skygge `hv_skygge_<id>` (feDropShadow), med `cleanupDefs` ved gem;
  - billeder: kontrol af type og størrelse (højst 2 MB) samt skalering.
- **`scada-core.js`:**
  - formværktøjerne polygon, stjerne, regulær polygon og bue (`setShapeTool`);
  - `setDash`, `setLineStyle`, `setArrow`, `setFillKind`, `setShadow`, `setShapeParams`, `insertImage`, `layers`, `layerOp` (ny, omdøb, vis, lås, aktiv, slet tomt, flyt valgte);
  - `paintOf` med streg, pile, gradient, skygge og form;
  - et låst lag kan ikke vælges, heller ikke med en ramme;
  - `getSvg` rydder ubrugte egne defs op og gemmer skjulte lag som synlige, så Overview altid viser alle lag.
- **`engine.ts`:** formværktøjerne og genvejene Y, S, N, B samt Ctrl+]/[ (ét trin frem/tilbage). Lærredet kopierer ikke længere manglende stil-værdier (`null`) over i stilen for nye figurer (se BUGS.md).
- **Brugerflade:**
  - `DrawCanvas.svelte`: knapper til de nye værktøjer og Billede, en linje med spidser og indre radius, og ét trin frem/tilbage over det markerede;
  - `Inspector.svelte`: fyldtype og gradient, stregtype, ender, hjørner, pile, skygge, spidser og indre radius;
  - `ObjectTree.svelte`: lagpanel.
- **Tests:** `src/lib/draw/shapes.test.ts` (14) og `backend/tests/test_draw_tools_svg.py` (alle nye elementer overlever serverens rensning, og SVG-/eksterne billeder fjernes stadig).
- **Manual:** `07-tegn.md` har et nyt afsnit og billederne `tegn-vaerktoejer.png` og `tegn-lag.png`.

## [3.32.0 build 0336] — 2026-11-06 — SVG-fil ind i en åben tegning + rettelser fra review af SVG-importen

- **SVG ind i tegningen (del B):**
  - Nyt `POST /api/library/fragment` (engineer) renser en SVG-fil til ét `<g>` uden at gemme noget. Det kører i en trådpulje.
  - `scada-core.js` har `insertGraphic`: filen bliver én almindelig gruppe med unikke id'er (gradienter følger med), højst 60 % af tegningen, og kan fortrydes.
  - `DrawCanvas.svelte` tager imod træk og slip af filer.
  - `DrawEditor.svelte` har knappen *Indsæt SVG-fil …* i *Symboler* og viser fejl og advarsler pr. fil.
- **Rettelser fra review af v3.31.0** (`services/library.py`, `storage/db.py`, `api/library.py`):
  - CSS i importerede filer gennemgås nu i lineær tid. Før var regex'erne kvadratiske, så 40 KB `<style>` tog 8 s og kunne blokere serveren. Der er nu et loft på 64 KB CSS og 4 KB pr. regel.
  - Når CSS-klasser skrives ind på elementerne, fjernes dubletter, og der er et samlet loft (256 KB), så hukommelsen ikke kan pustes op.
  - Omdøbningen af id'er bruger en tæller pr. navn (før kvadratisk ved ens id'er), og der er højst 5000 elementer med id.
  - Viewbox med `inf`/`1e308` afvises med en præcis besked.
  - Importen kører i en trådpulje, så live-data ikke blokeres.
  - En ny version fra en SVG-fil beholder den forrige standardopsætning, hvis delene stadig findes. Ellers står der en advarsel i resultatet (før blev den slettet uden besked).
  - Loftet på 500 symboler håndhæves under databaselåsen.
  - Import af en pakke stopper, når biblioteket er fuldt (fejlkode i stedet for teksttjek), og pakkens sektioner kendes kun på navnet og oprettes én gang.
- **Tests:** 3 nye i `test_library.py` (fragment, DoS-lofter og tid, ny version beholder opsætningen).
- **Manual:** `07-tegn.md`.

## [3.31.0 build 0335] — 2026-11-06 — Import af SVG-symboler, bibliotekspakke og organisering af symbolbiblioteket

- **Backend** (`backend/app/services/library.py`, `backend/app/api/library.py`):
  - `import_fragment` laver en hel SVG-fil om til et bibliotekssymbol. Filen renses med tegningernes regler og flyttes til (0,0) ud fra viewBox eller width/height. Er den større end 240, skaleres den ned. Arvede præsentationsattributter fra `<svg>` bevares. CSS-klasser skrives ind på elementerne, og `<style>` fjernes, fordi den ellers ville gælde hele tegningen. Id'er bliver til dele, og defs bliver til `def_*`.
  - `import_files`, `export_package`/`import_package` (`.hvlib.json`, format 1, tags fjernes) og `_section_id` (en manglende sektion fra en pakke oprettes). Ved navnekonflikt vælges *nyt navn*, *ny version* eller *spring over*.
  - Endpoints: `POST /api/library/import`, `GET`/`POST /api/library/package` (engineer). Kroppen læses i bidder med et loft på 12 MB (413), der er højst 50 filer og 10 MB pr. import, og resultatet gives pr. fil. Hvert importeret symbol auditeres.
- **Frontend:**
  - Ny `LibraryImport.svelte` (dialog til SVG-filer og pakker med resultatet pr. fil).
  - Ny `SymbolLibrary.svelte`: siden *Symboler* får fanerne **Bibliotek** (sektioner opret/omdøb/slet/rækkefølge, flyt og ordn symboler, omdøb/slet egne, import/eksport) og **Tilslutningspunkter**.
  - Egne symboler er med i tilslutningspunkt-editoren og i Symboltest.
  - Tegn: *Importér SVG-symboler …* og *Organisér …* i paletten. `libraryStore.svelte.ts`: import-, pakke-, omdøb- og slet-hjælpere.
- **Tests:** `backend/tests/test_library.py` har 4 nye tests (import, konflikter og sektion, grænser og roller, pakke-roundtrip).
- **Manual:** `07-tegn.md` har et nyt afsnit og billederne `symboler-bibliotek.png` og `symboler-import.png`. `08-forbindelser.md` er opdateret.

## [3.30.0 build 0334] — 2026-11-06 — Demo: ny driftsstruktur med 3 modes (Auto / manuel mode 1-3)

- `demo/varme-plc/logic1_styring.st`: driftsform `cmd_mode` 0 Auto, 1-3 manuel mode. Mode 1 Hus + pille (M1 AB-A, M2 AB-A, P1), mode 2 Hus + pille + tank (M1 AB-A, M2 AB-B, P1), mode 3 Hus + tank (M1 AB-B, M2 AB-B, P2). Auto kobler tanken ind (mode 3) ved ATT1 ≥ `sp_tank_ind` (60 °C) og ud (mode 1) under `sp_tank_ud` (45 °C). Varmepumpen startes manuelt (`cmd_vp`). Nye `MODE`, `TANK_IND` og flow-flag pr. kredsdel (`F_HUS`, `F_PILLE`, `F_TANK`, `F_BYPASS`). Fjernet: Fra/Sommer/Kun pille/Manuel, `man_*`, `sp_tank_min`/`sp_tank_hyst`, `sp_sommer`.
- `logic2_kilder.st`: pillefyret sidder i husets kreds (flow fra P1, indløb = vandet til M1 via `g_str`, fremløb STF_SP + 5, højst `sp_pille`) og lader ikke længere tanken. `logic3_tank_hus.st`: husets flow fra P1 eller P2, kilden efter M1/M2's position, tanken gennemstrømmes i mode 2 og 3. `logic4_system.st`: varmepumpen højst 65 °C fremløb. `globals.st`: `g_str` = pillefyrets indløb.
- `test/sim_test.cpp`: skrevet om til de tre modes (ventiler, pumper, flow-flag), auto ind/ud, VP ≤ 65 °C, brændefyret > 80 °C, manuel mode 1-3, håndbetjening og de øvrige fejl-scenarier.
- `scada_setup.py`: nye tags (og sletning af de forældede), omskifter med 4 stillinger (Auto/M1/M2/M3), panelet "Kilder og tid" (varmepumpe til/fra, tidsfaktor) i stedet for "Manuel drift", setpunkterne Tank ind/Tank ud, rør bundet pr. kredsdel (også T-stykkernes grene), og panelet kendes nu på `dp_`-id'erne (det tidligere element-antal efterlod dubletter af infofelterne, da panelet blev mindre). `syms.json`, `tools/symgen.ts`, `README.md`, `PLAN.md`.
- Indlæst på demo-PLC'en og demo-SCADA'en (tegningen `varme` version 135). Alle tre modes er set i browseren.

## [3.29.0 build 0333] — 2026-11-06 — Demo: motorventilerne MVS1/MVS2 kan betjenes

- `demo/varme-plc/logic3_tank_hus.st`: håndbetjening pr. ventil `cmd_mvs1`/`cmd_mvs2` (0 Auto, 1 AB-A, 2 AB-B) — overstyrer styringens kommando i alle driftsformer; gangtiden er stadig 30 s (471/512 AST-noder, 46 variable). `test/sim_test.cpp`: test af begge ventiler og tilbage til Auto.
- `demo/varme-plc/scada_setup.py`: tags `cmd_mvs1`/`cmd_mvs2` (skrivbare 0–2, bekræftelse) og de to 3-vejs motorventiler på tegningen som betjening med positionerne Auto / AB-A / AB-B (portfarverne følger den faktiske position); `--only-configs` (opdatér tags og opsætninger uden ny tegningsversion). `load.py --only=3` (indlæs kun udvalgte programmer). `README.md`.
- Indlæst på demo-PLC'en (kun Logic3) og sat op på demo-SCADA'en; afprøvet i browseren: MVS1 kørt AB-A → AB-B på ca. 30 s og tilbage til Auto.

## [3.28.1 build 0332] — 2026-11-05 — Demo: opsætning af demo-SCADA'en + fix af dobbelte betjeningspaneler

- Nyt `demo/varme-plc/scada_setup.py` (PLC, 87 tags, betjeningspanel og symbolopsætninger på tegningen `varme` via SCADA'ens REST API), `demo/varme-plc/syms.json` + `tools/symgen.ts` (panelets symboler genereret fra frontendens bibliotek), `.gitignore`.
- Fix: scriptet fjernede det tidligere panel via kommentarmarkører, som serveren fjerner ved gem — hver kørsel lagde et panel mere ovenpå (4 på demo-SCADA'en), og klik ramte kopierne uden opsætning. Panelet kendes nu på sin baggrund; alle tidligere paneler (også kopier med nye id'er) fjernes. Demo-SCADA'en rettet (tegningen `varme` version 131). `demo/varme-plc/README.md`, BUGS.md.

## [3.28.0 build 0331] — 2026-11-05 — Egne symboler: gem et objekt fra Tegn i symbolbiblioteket (del 1)

- Backend: ny tabel `library_symbols` (additiv, `storage/db.py`) og opdelingen i meta-nøglen `library.layout` (gemmes med revision — samtidige gem afvises med 409). `services/library.py`: udtræk af objektet fra tegningens gemte version (flyttes til 0,0, dele navngives efter bibliotekets delnavn/id, gradienter/markører følger med under nye navne, instans-attributter fjernes, renses igen med `svg_sanitize`), standardopsætning samlet fra objektets og de indlejrede symbolers opsætninger (delnavne, tags fjernet som standard, nøglelås aldrig med, højst én betjening), versioner, omdøb/slet (svaret siger hvilke tegninger der bruger symbolet) og opdeling. `api/library.py`: `GET /api/library` (viewer), `POST /api/library/symbols`, `PATCH`/`DELETE /api/library/symbols/{type}`, `PUT /api/library/layout` (tekniker/admin, audit-log). Med i backup/gendan (`services/backup.py`; ældre backups lader biblioteket være). `main.py`. Tests: `tests/test_library.py`.
- Frontend: `lib/library.ts` (bibliotek = indbyggede + egne, sektioner, placering, standardopsætning) + `lib/libraryStore.svelte.ts`; `lib/SymbolExport.svelte` (dialogen *Gem som symbol*); `pages/DrawEditor.svelte` (knappen i *Valgt element*, paletten efter opdelingen med *Egne symboler*, egne symboler i *Mine symboler*); `lib/SymbolReplace.svelte` (egne symboler kan søges; *Nyeste version* foreslås først); `lib/symbolConfig.ts` (guidens standardopsætning for egne symboler); `lib/svg.ts` (`sanitizeSvgFragment` — DOMPurify fjernede løse `<g>`-fragmenter helt); `svgedit-host/scada-core.js` (`elementBox`, `elementMarkup`; henvisninger `url(#…)`/`href` følger de nye id'er ved indsættelse); `lib/symbols.ts` (kategorien `egne`). Tests: `lib/library.test.ts`.
- Efter review: et symbol kendes på sit navn (omdøbte symboler beholder deres type, og et nyt symbol med det gamle navn får en ny type), alle id'er i kopierede gradienter/markører omdøbes, revisionen er påkrævet ved gem af opdelingen og fortsætter efter gendannelse, backup med dobbelte typer afvises med en valideringsfejl, og læsere uden tekniker-rolle får ikke standardopsætningen (den kan indeholde tag-navne).
- Manual: `frontend/src/manual/07-tegn.md` (afsnittet *Egne symboler*) og skærmbillederne `tegn-gem-som-symbol.png`, `tegn-egne-symboler.png`.
- `PLAN.md` (ny plan; demo-planen flyttet til `demo/varme-plc/PLAN.md`), `FEATURES.md`.

## [3.27.0 build 0330] — 2026-11-05 — Demo-PLC: varmeanlægget emuleret i ST

- Nyt `demo/varme-plc/`: `globals.st` (16 GLOBAL_VAR), `logic1_styring.st` (styring, alarmer), `logic2_kilder.st` (brændefyr/Laddomat, pillefyr), `logic3_tank_hus.st` (tank i 6 lag, husets kreds, MVS1/MVS2), `logic4_system.st` (tryk, sikkerhedsventiler, udetemp, tidsfaktor, scenarier/fejl, varmepumpe), `load.py` (indlæsning via PLC'ens REST API), `test/run.sh` + `test/sim_test.cpp` (PC-test med PLC'ens egen compiler/VM: AST-noder, scenarier, fysiske grænser), `README.md` (variabel-/bindingstabel).
- Indlæst og verificeret på demo-PLC'en (firmware v7.9.68.166): alle fire programmer kører uden fejl, ca. 1 ms pr. scan.
- Fundet i PLC-firmwaren og omgået: CASE med flere værdier pr. gren rammer ingen, negative startværdier i VAR bliver 0, STRING-startværdier sættes ikke.
- `PLAN.md`, `FEATURES.md`, `.gitignore`.

## [3.26.3 build 0329] — 2026-11-04 — Manual: guidens trin 5 med nyt layout (med i appen)

- `frontend/src/manual/10-symboler-og-guiden.md` (trin 5 beskrevet som bokse) og nye skærmbilleder `frontend/public/manual/guide-5.png`, `guide-interaktiv.png`, `guide-noeglelaas.png`.

## [3.26.2 build 0328] — 2026-11-04 — Guiden, trin 5 Betjening: ryddet op

- `frontend/src/lib/SymbolGuide.svelte`: trin 5 i bokse (Bekræftelse, Betjening på tegningen, Puls, Nøglelås); *Dialog/Interaktiv* som knap · navn · forklaring i faste kolonner — teksten blev før brudt op af flex-layoutet. `frontend/src/lib/SymbolReplace.svelte`: samme fejl i valget af lignende symboler. BUGS.md.

## [3.26.1 build 0327] — 2026-11-04 — Tegn: værktøjslinjen lå foran dialoger

- `frontend/src/lib/draw/DrawCanvas.svelte`: `.draw` får sit eget stablingslag (`isolation: isolate`), så værktøjslinje, højrekliksmenu og besked aldrig ligger over dialoger eller topmenuen. BUGS.md.

## [3.26.0 build 0326] — 2026-11-04 — System › Certifikater: Let's Encrypt (HTTP-01 og DNS-01/deSEC) fra siden

- `deploy/apply-letsencrypt.sh` (ny root-hjælper) + `hypervisionplc-scada-le.{path,service}` (ExecStopPost sætter en afbrudt kørsel til fejl): install / dns-config (token via fil → stdin, slettes straks) / issue (dns|http, live|dry) / info; status i `le-status.json`, overblik i `le-info.json`, log i `le-run.log`.
- `deploy/tls-letsencrypt.sh`: `issue … --method http|dns` — HTTP-01 med `certbot --webroot` (`/var/lib/hypervisionplc-scada-acme`).
- `deploy/nginx-hypervisionplc-scada.conf`: `location ^~ /.well-known/acme-challenge/` på port 80, redirect flyttet ind i `location /`. `deploy/install.sh`: webroot, nye enheder, nginx-sitet opdateres ved opdatering (tidsstemplet backup, `nginx -t` → gammel tilbage; `# hypervisionplc: lokal` = røres ikke).
- `backend/app/services/tls_admin.py`: `le_status`/`le_install`/`le_dns`/`le_issue` (validering, én ad gangen, glemt anmodning ryddes efter 2 min, token skrives først når 409 er udelukket). `backend/app/api/tls.py`: `/api/system/tls/le…` (202).
- `frontend/src/pages/Certificates.svelte`: Let's Encrypt-sektion (metode, deSEC, test mod staging, udsted, status og log); SAN-feltet hedder nu "Gælder for — SAN". `frontend/src/lib/certificates.ts` (+ test). Manual 13-system.
- Tests: `backend/tests/test_tls_admin.py`, `backend/tests/test_letsencrypt.py`.

## [3.25.1 build 0325] — 2026-11-04 — Certifikater: formularens layout

- `frontend/src/pages/Certificates.svelte`: felterne står under hinanden; navn og adresser forudfyldes fra det nuværende certifikat.

## [3.25.0 build 0324] — 2026-11-04 — System › Certifikater: selvsigneret, CSR, import (PKCS#12/PEM), gendan

- `backend/app/services/tls_admin.py` (ny): `TlsAdmin` — selvsigneret (CN, SAN, 1-3650 dage, EC P-256/RSA), CSR med ventende nøgle (0600) + installation af det signerede certifikat, import af PKCS#12 og PEM (krypteret nøgle), kæde sorteres, udløbet afvises, gendan forrige/selvsigneret. Én handling ad gangen; installation via root-hjælper med svar-id. Tællere til `/metrics` (`scada_tls_operations_total`).
- `backend/app/api/tls.py` (ny): `/api/system/tls` (GET, `cert.pem`, `selfsigned`, `csr` POST/DELETE, `signed`, `import`, `restore`) — kun admin, audit uden nøgler/adgangskoder. `main.py`, `services/health.py`, `services/metrics.py`.
- `deploy/apply-tls.sh` (ny root-hjælper) + `hypervisionplc-scada-tls.{path,service}` (hærdet: ProtectSystem=strict), `deploy/cert-deploy.sh` (offentligt certifikat + `has_prev`/`has_selfsigned` til state-mappen), `deploy/install.sh`.
- `frontend/src/pages/Certificates.svelte`, `frontend/src/lib/certificates.ts` (+ test), `lib/nav.ts`, `App.svelte`; manual 13-system.
- Tests: `backend/tests/test_tls_admin.py` (inkl. root-hjælperen ende til ende med sh/openssl).

## [3.24.2 build 0323] — 2026-11-04 — Manual: sådan læses svaret fra /values

- `frontend/src/manual/13-system.md`: eksempel og felt-tabel (`time`, `v`, `q`, `ts`) med betydningen af `good`/`comm_error`/`bad`/`unknown`.

## [3.24.1 build 0322] — 2026-11-04 — Integrationer: forklaring af tags og præfikser

- `frontend/src/pages/Integrations.svelte`: foldbar hjælp *Tags eller præfikser — hvad er forskellen?* ved afgrænsningen. `frontend/src/manual/13-system.md`: samme forklaring.

## [3.24.0 build 0321] — 2026-11-04 — Integrationer: brugseksempler på siden

- `frontend/src/lib/integration.ts`: `usageExamples()` — curl for alle endpoints (info, points, values, history, alarms, stream), Python, PowerShell, Node-RED og Home Assistant (+ test). `frontend/src/pages/Integrations.svelte`: foldbar sektion *Eksempler på brug* med pladsholder-nøgle og første tag.

## [3.23.0 build 0320] — 2026-11-04 — Backup: tidsplan og eksterne destinationer

- `backend/app/services/backup_targets.py` (ny): `BackupScheduler` — én tidsplan (interval/dagligt/ugentligt/fra, lokal tid, forsinket kørsel tages 5 min efter opstart), lokal backup + afsendelse parallelt i tråde til destinationer: SFTP/SCP (paramiko, værtsnøgle godkendes ved test og fastlåses, adgangskode eller Ed25519-nøgle lavet på serveren), FTP/FTPS (ftplib), HTTPS PUT (httpx), SMB (smbprotocol), NFS (root-hjælper monterer). `.part` → omdøb, 2 genforsøg, *behold N* rydder kun egne filnavne, fejltekster renses for hemmeligheder. Tællere, `failing()` → Status-problem/SYS-alarm efter 2 fejl i træk.
- `backend/app/api/backup.py`: `/api/backup/schedule` (GET/PUT), `/run`, `/targets` (GET/POST/PATCH/DELETE), `/targets/{id}/test`, `/targets/{id}/ssh-key` — kun admin, audit uden hemmeligheder. `services/backup.py`: den gamle faste løkke fjernet. `main.py`, `services/health.py` (forventet interval fra tidsplanen, problemer pr. destination), `services/metrics.py` (`scada_backup_*`).
- `deploy/apply-backup-mounts.sh` + `hypervisionplc-scada-backupmount.{path,service}` (ny root-hjælper), `deploy/install.sh` (installerer hjælperen, `nfs-common`). `backend/requirements.txt`: paramiko (LGPL-2.1), smbprotocol (MIT) — godkendt af Jan.
- `frontend/src/lib/BackupTargets.svelte`, `frontend/src/lib/backupTargets.ts` (+ test), `pages/Backup.svelte`; manual 13-system.
- Efter gennemgang: værtsnøgle gemmes kun hvis den matcher det fingeraftryk, administratoren så; NFS-sti kan ikke pege ud af monteringen (heller ikke via symlinks); root-hjælperen afviser eksporter, der starter med "-", og kalder mount med "--"; lås om ændringer af destinationslisten; fil-I/O i tråde.
- Tests: `backend/tests/test_backup_targets.py` (22).

## [3.22.0 build 0319] — 2026-11-04 — Integrationer: SSE-strøm og tag-vælger

- `backend/app/services/integration.py`: `open_stream`/`close_stream` (højst 5 pr. nøgle, 50 i alt → 429), `stream_events` (`snapshot`, `values` samlet pr. interval, `alarm`, `resync` ved overløb, `closed`, hjerteslag 15 s, nøglen genkontrolleres hvert 10. s), `on_alarm_event` (lytter på alarmmotoren; samme afgrænsning og skjulte PLC-fejltekster som `/alarms`), `revalidate`; tællere `streams`/`stream_events`.
- `backend/app/api/integration.py`: `GET /api/v1/integration/stream` (`tags`, `interval`, `alarms`, `max_events`; `X-Accel-Buffering: no`). `backend/app/main.py`: lytter registreret. `backend/app/services/metrics.py`: `scada_integration_streams`, `scada_integration_stream_events_total`.
- `frontend/src/pages/Integrations.svelte`, `frontend/src/lib/integration.ts` (+ test): tags vælges i en søgbar liste, præfiks-forslag som knapper, live forhåndsvisning af hvilke tags afgrænsningen giver (ukendte tags/tomme præfikser markeres); strøm-eksempel. Manual 13-system.
- Efter gennemgang: pladsen frigives også hvis klienten afbryder før første byte (`_Stream`), øjebliksbilleder og genkontrol kører i en tråd, højst ét resync pr. 10 s.
- `backend/tests/test_integration.py`: 8 nye tests for strømmen.

## [3.21.0 build 0318] — 2026-11-04 — Integrationer: API-nøgler og læse-API

- `backend/app/services/integration.py` (ny): `IntegrationService` — nøgler (kun SHA-256, `hv_`+43 tegn genereret i browseren), validering (navn, afgrænsning med eksisterende tags/præfikser, IP-netværk, udløb, højst 50), godkendelse (401/403/429), hastighedsgrænse pr. nøgle, "sidst brugt" højst én skrivning pr. minut, tællere; læse-API `points`/`values`/`history`/`alarms`/`info` afgrænset til nøglen.
- `backend/app/api/integration.py` (ny): `/api/v1/integration/*` (kun Bearer-nøgle, OpenAPI for kun denne del på `/openapi.json`) og admin `/api/system/integration/keys` (kun admin, audit uden nøglen).
- `backend/app/storage/db.py`: tabellen `api_keys`. `backend/app/services/errors.py`, `api/errors.py`: `headers` på `ServiceError` (Retry-After, WWW-Authenticate). `backend/app/main.py`, `services/health.py`, `services/metrics.py`: tjeneste, tællere (`scada_integration_*`).
- `frontend/src/pages/Integrations.svelte`, `frontend/src/lib/integration.ts` (+ test), nav, App; manualafsnit med eksempler til curl, Node-RED og Home Assistant.
- Gennemgået af `reviewer`: PLC-fejltekster og -navne udleveres aldrig (hverken i `values` eller alarmer; kun nøgler med *alle tags* ser kommunikationsalarmer, i generisk form); lås om hastighedsgrænse og tællere (trådpulje); afviste kald pr. IP begrænses (30/min → 429 uden databaseopslag); NaN/uendelig udløb og ekstreme historik-tidspunkter giver 400; samtidig oprettelse med samme navn giver 409; ændre-krop sender kun ændrede felter.
- Tests: `backend/tests/test_integration.py` (60), `frontend/src/lib/integration.test.ts` (9).

## [3.20.0 build 0317] — 2026-11-03 — Resend som e-mail-udbyder

- `backend/app/services/notifier.py`: `provider` (`smtp` | `resend`) på e-mail-kanalen; `_send_resend` (POST `https://api.resend.com/emails`, Bearer-nøgle, fast adresse), Resends fejlbesked i prøvebeskeden; nøglen `resend_key` skriv-kun i `secrets.json` og skjult i fejltekster; krav pr. udbyder (Resend: nøgle + afsender + modtagere; SMTP-login-reglen gælder kun SMTP).
- `backend/app/api/notifications.py`: `provider`, `resend_key`, `clear_resend_key`; audit uden nøglen.
- `frontend/src/pages/Notifications.svelte`, `frontend/src/lib/notifications.ts`: udbyder-valg og Resend-nøgle (skriv-kun). Manual.
- Tests: 16 nye i `backend/tests/test_notifier.py` (73 i alt), 1 i `notifications.test.ts`.

## [3.19.0 build 0316] — 2026-11-03 — Alarmnotifikation (webhook + e-mail)

- `backend/app/services/notifier.py` (ny): `NotificationService` — lytter på alarmmotorens `raise`/`clear`, filtrerer på prioritet, samler i partier (`batch_s`), sender webhook (httpx) og e-mail (smtplib i tråd) med forsøg igen (5/30/120 s), husker de seneste 50 afsendelser, tællere, fejltekster uden hemmeligheder; `httpx`/`httpcore` sat til WARNING (en webhook-adresse er en hemmelighed og stod ellers i INFO-loggen).
- `backend/app/api/notifications.py` (ny, kun admin): `GET/PUT /api/system/notifications`, `POST /test`; audit uden værdier.
- `backend/app/storage/secrets.py`: generelle skriv-kun hemmeligheder pr. afsnit. `backend/app/services/alarms.py`: `listeners` kaldt fra `_event`. `backend/app/services/health.py`, `metrics.py`: problem `notify_*` og `scada_notifications_*`. `backend/app/main.py`: tjeneste + opgave. `ARCHITECTURE.md`: undtagelse for udgående kald.
- `frontend/src/pages/Notifications.svelte`, `frontend/src/lib/notifications.ts` (+ test), `nav.ts`, `App.svelte`; manualafsnit.
- Tests: `backend/tests/test_notifier.py` (43), `frontend/src/lib/notifications.test.ts`.

## [3.18.1 build 0315] — 2026-11-03 — fix: strøm-/undervoltage-status virker på Raspberry Pi

- `deploy/power-info.sh` (ny, root): `vcgencmd get_throttled` → `<state>/power.json`; kører i DHCP-vagtens timer (ExecStartPre i `hypervisionplc-scada-netwatch.service`) og ved installation.
- `backend/app/services/health.py`: `read_throttled`/`read_host(state_dir)` — læser `power.json` (frisk < 5 min), sysfs-stien som reserve. Før: stien fandtes ikke på Pi'ens kerne, så kortet var tomt og alarmen udeblev.
- Tests: `backend/tests/test_power_info.py`. BUGS.md: fejlen beskrevet (fundet på den rigtige Pi).

## [3.18.0 build 0314] — 2026-11-03 — Interne alarmer om SCADA selv

- `backend/app/services/health_alarms.py` (ny): `HealthAlarms` — målinger fra systemhelbredet hvert 30. s (efter 60 s opstartsventetid) → alarmkilde `sys:<kode>` (niveau SYS). Gul = to målinger i træk, rød straks; ophør først 120 s efter sidst set; `plc` og `power_past` er undtaget.
- `backend/app/services/health.py`: hvert problem har en `code`. `backend/app/config.py`: `SCADA_HEALTH_ALARMS`, `SCADA_HEALTH_ALARM_SAMPLE_S`, `SCADA_HEALTH_ALARM_WARMUP_S`. `backend/app/main.py`: kilden og opgaven.
- `frontend/src/lib/api.ts`, `frontend/src/pages/Alarms.svelte`: alarmtypen `sys` ("SCADA-serveren"). Manual: afsnit under Alarmer og Status.
- Tests: `backend/tests/test_health_alarms.py` (22).

## [3.17.0 build 0313] — 2026-11-03 — Let's Encrypt (certbot + deSEC) og certifikatkort på Status

- `deploy/desec-acme-hook.sh` (ny): certbot `--manual-auth-hook`/`--manual-cleanup-hook` mod deSEC's API; skriver TXT-posten i den zone, CNAME'en peger på (Debians `python3-certbot-dns-desec` 1.2.1 følger ikke CNAME'er); tokenet sendes kun via en 0600-headerfil til curl.
- `deploy/tls-letsencrypt.sh` (ny, installeres som `hypervision-letsencrypt`): `install` (apt: certbot, curl), `set-token` (stdin, kun root-læsbar fil), `set-target <zone>`, `issue <navn> <mail> [--dry-run] [--force]` (staging-prøve uden at gemme noget), `status`, `renew-test`. Det selvsignerede certifikat bevares ved fejl.
- `deploy/cert-deploy.sh` (ny): certbots deploy-hook — kun stier under `/etc/letsencrypt/live`, kontrollerer at nøglen passer (før og efter flytning), gemmer `*.prev`/`*.selfsigned`, flytter filerne, `nginx -t` (gendanner det forrige, ellers det selvsignerede par — aldrig et blandet par), genindlæser nginx, skriver `cert.json`. Gennemgået af `reviewer`.
- `deploy/install.sh`: installerer begge scripts (så OTA-opdateringer bevarer dem) og opdaterer certifikat-metadata.
- `backend/app/services/health.py`, `metrics.py`: `read_tls` (dage tilbage regnes ved aflæsning), gul under 21 / rød under 7 dage, `scada_tls_cert_expiry_seconds`, `scada_tls_cert_self_signed`.
- `frontend/src/pages/Status.svelte`, `frontend/src/lib/status.ts`: kortet *HTTPS-certifikat udløber om*; manualafsnit; `docs/TLS_LETSENCRYPT.md`.
- Tests: `backend/tests/test_letsencrypt.py` (60), `test_health.py`, `test_metrics.py`, `frontend/src/lib/status.test.ts`.

## [3.16.2 build 0312] — 2026-11-03 — WiFi-strømbesparelse slås fra (Raspberry Pi)

- `deploy/install.sh`: NetworkManager-maskiner får `/etc/NetworkManager/conf.d/90-hypervisionplc-wifi-powersave.conf` (`wifi.powersave = 2`), og strømbesparelsen slås fra straks på trådløse kort. Målt: `Power save: on` som standard på Pi'ens WiFi.
- BUGS.md: undersøgelsen af "sleep mode" (WiFi-strømbesparelse + undervoltage).

## [3.16.1 build 0311] — 2026-11-02 — fix: fast IP på Raspberry Pi OS Trixie (netplan)

- `deploy/apply-config.sh`: er NetworkManager-profilen skabt af netplan, arbejdes der på en kopi (`nmcli connection clone`); kopien gøres varig ved Bekræft og netplan-originalen slettes, ved Fortryd/timeout/`--recover` slettes kopien. Årsag: en varig `nmcli connection modify` på en netplan-profil fik NetworkManager til at skrive netplan-filer og begrave profilen, så netkortet mistede forbindelsen ved Bekræft.
- `backend/tests/test_netconfig.py`: 7 nye tests (kopi ved bekræft/fortryd/fejl/recover, registrering efter filnavn, ingen kopi for almindelige profiler).
- Gennemgået af `reviewer`: tilstandsfilen fjernes før originalen slettes; kopien starter uden autoconnect, til Bekræft (så slås autoconnect + prioritet 10 til); oprydning og `--recover` sletter kun kopien, hvis originalen findes; unikt navn på kopien (ingen sletning på navn); synlig advarsel hvis originalen ikke kan slettes.
- BUGS.md: fejlen beskrevet med bevis fra Pi'en.

## [3.16.0 build 0310] — 2026-11-01 — Prometheus /metrics med scrape-token

- `backend/app/services/metrics.py` (ny): håndskrevet Prometheus-eksponering (0.0.4) ud fra `HealthService.details()`; målinger uden værdi udelades; kun systemtal.
- `backend/app/api/metrics.py` (ny): `GET /metrics` (kun Bearer-token, 404 når slået fra, 401 + `WWW-Authenticate` ved forkert/manglende; afviste forsøg tælles og logges); admin: `GET/PUT/DELETE /api/system/metrics` (audit uden værdi).
- `backend/app/storage/secrets.py`: scrape-token som SHA-256-kontrolsum (skriv-kun, `hmac.compare_digest`). `backend/app/main.py`: `app.state.secrets`. `backend/app/services/health.py`: `request_count` pr. PLC.
- `frontend/src/lib/MetricsToken.svelte`, `frontend/src/lib/metricsToken.ts` (+ test): token genereres i browseren, vises én gang med færdigt `prometheus.yml`-eksempel; indsat nederst på Status. Manual: afsnit *Prometheus og Grafana*.
- Trådsikkerhed (reviewer): `HealthService.details` er nu async — det event-loopet ændrer (PLC-status, alarmer, lag) læses på loopet, kun database/disk/filer kører i en tråd; token kun URL-sikre tegn; tabellen over afviste IP-adresser er begrænset (1000).
- Tests: `backend/tests/test_metrics.py`, `frontend/src/lib/metricsToken.test.ts`.

## [3.15.0 build 0309] — 2026-11-01 — System › Status (systemhelbred)

- `backend/app/services/health.py` (ny): `HealthService` (event-loop-lag-sonde, WebSocket-tæller, samlet billede) og `assess` (gul/rød-grænser, dansk tekst); læser Pi-throttling, CPU-temperatur, hukommelse fra /proc og /sys.
- `backend/app/api/health.py` (ny): `GET /api/health/details` (tekniker+, kun læsning). `/api/health` er uændret (OTA-rollback).
- `backend/app/main.py`, `backend/app/api/live_ws.py`, `backend/app/services/manager.py`, `backend/app/services/plc_runtime.py`: sonden startes/stoppes i lifespan; `health_service.ws_clients`; `request_rate` i PLC-status.
- `frontend/src/pages/Status.svelte`, `frontend/src/lib/status.ts`, `frontend/src/lib/nav.ts`, `frontend/src/App.svelte`: siden *System › Status* (opdaterer hvert 5. s); `frontend/src/manual/13-system.md`: afsnit.
- Tests: `backend/tests/test_health.py`, `frontend/src/lib/status.test.ts`, `nav.test.ts`.

## [3.14.3 build 0308] — 2026-11-01 — Tegn/Symboler spørger før ugemte ændringer går tabt ved sideskift

- `frontend/src/lib/leaveGuard.ts` (ny): vagt som en side kan tilmelde; `App.svelte` spørger den ved sideskift (menu, adresselinje, tilbage) og sætter adressen tilbage, hvis man bliver.
- `frontend/src/pages/DrawEditor.svelte`, `frontend/src/pages/SymbolEditor.svelte`: tilmelder vagten; "Tilbage" i Symboler spørger kun én gang.
- Test: `frontend/src/lib/leaveGuard.test.ts`. BUGS.md: v3.7.0-fejlen lukket.

## [3.14.2 build 0307] — 2026-11-01 — kommunikationsalarmer for delvise fejl og ikke-startede PLC'er

- `backend/app/services/alarms.py`: `_comm_problems` — alarm `plc:<plc>:partial` (COMM) når kald/områder fejler delvist og `plc:<plc>:comm` for en aktiv PLC, der ikke kan startes (mangler adgangskode); tællere pr. alarmnøgle ryddes, når problemet forsvinder.
- `backend/app/services/plc_runtime.py`: `status.partial` er vedvarende (fjernes først når netop det kald lykkes); fejl, PLC'en svarer med for et eksternt område, tæller med; ryddes ved ændret plan og ved total fejl.
- `backend/app/services/manager.py`: `attention` i PLC-status (aktiv PLC uden adgangskode).
- Tests: `test_alarms.py`, `test_runtime.py`. BUGS.md: Gennemgang #7 og #9 lukket. Gennemgået af `reviewer`.

## [3.14.1 build 0306] — 2026-11-01 — fejlrettelser: Origin bag nginx, ugyldige PLC-værdier, dybt SVG, brugernavne

- `backend/app/main.py`: `origin_matches_host` (værtsnavn; port kun når `Host` har en). `deploy/nginx-hypervisionplc-scada.conf`: `Host $http_host`.
- `backend/app/plc/client.py`, `backend/app/services/plc_runtime.py`: `coerce_register` — `None`/tekst/decimaltal fra PLC giver `PlcApiError` (bulk) eller kvalitet `bad` (eksterne) i stedet for `TypeError`/afkortning; logges med kilde.
- `backend/app/services/svg_sanitize.py`: dybdegrænse (100) med læsbar fejl.
- `backend/app/storage/db.py`, `backend/app/services/auth.py`: brugernavne unikke uanset store/små bogstaver (`get_user_ci`, unikt indeks når muligt).
- Tests: `test_auth.py`, `test_client.py`, `test_svg_sanitize.py`. BUGS.md: fire punkter fra Gennemgang (#13, #15, #16, #18) lukket.

## [3.14.0 build 0305] — 2026-10-31 — OTA-opdatering direkte fra GitHub

- `backend/app/services/github_releases.py` (ny): nyeste Release via GitHub API, hentning af `scada-*.tar` med størrelsesgrænse og SHA256-kontrol; afviser hvis en nyere udgivelse er kommet siden søgningen.
- `backend/app/api/system.py`: `GET /api/system/update/github`, `POST /api/system/update/github/download` (admin, audit `system.update.github`); pakken klargøres via `UpdateService.stage`.
- `backend/app/config.py`, `backend/app/main.py`: `SCADA_UPDATE_REPO` (standard Jangreenlarsen/HypervisionPLC-SCADA; tom = slået fra).
- `frontend/src/pages/Update.svelte`, `frontend/src/lib/updateUi.ts`: boksen *Fra GitHub*.
- Tests: `backend/tests/test_github_releases.py`, `frontend/src/lib/updateUi.test.ts`.

## [3.13.1 build 0304] — 2026-10-31 — Rettet: siden kunne ikke nås efter bootstrap-installation

- `deploy/bootstrap.sh`: nginx med TLS som standard (`--with-nginx <hostnavn> <ip>`), nyt valg `--local-only`, korrekt adresse (`https://<ip>`) i slutbeskeden.
- `README.md`, `frontend/src/manual/13-system.md`, `BUGS.md`.

## [3.13.0 build 0303] — 2026-10-31 — Installation af en ny Pi direkte fra GitHub

- `deploy/bootstrap.sh` (ny): henter nyeste (eller `SCADA_VERSION`) GitHub Release, kontrollerer SHA256, kører `deploy/install.sh` med de givne valg og viser adresse og engangsadgangskode. `DRY_RUN=1` henter og kontrollerer uden at installere.
- `.github/workflows/release.yml` (ny): tag `vX.Y.Z` → tjek mod version.json, frontend-tests, `deploy/make-package.sh`, Release med pakke + `.sha256` og noter fra RELEASE_NOTES.md.
- `README.md`, `frontend/src/manual/13-system.md`: installationsvejledning.

## [3.12.5 build 0302] — 2026-10-31 — Test rettet til de nye billedstier

- `frontend/src/lib/manualImages.test.ts`: leder efter billeder med den relative sti (`../../public/manual/…`). Build 0301 blev lagt ud med 2 fejlende tests i denne fil (programmet var korrekt).

## [3.12.5 build 0301] — 2026-10-31 — Rettet: manualens billeder virker også på GitHub

- `frontend/src/manual/*.md`: 72 billeder henviser nu med den relative sti i repoet (`../../public/manual/…`).
- `frontend/src/lib/manual.ts`: `manualImageSrc` omsætter stien til serverens `/manual/…`, når manualen vises i programmet.
- `frontend/src/lib/manualGen.test.ts`: det genererede bibliotekskapitel skriver relative stier.
- Tests: `src/lib/manual.test.ts` (ingen gamle stier, hvert billede findes).

## [3.12.4 build 0300] — 2026-10-31 — Nye skærmbilleder af Alarmer og Trends

- `frontend/public/manual/alarmer.png`, `alarmer-historik.png`, `trends.png`: taget om fra testserveren 10.1.1.31 — Trends med visningen *Tank Temperatur total* (8 følere) over 7 dage.
- `frontend/tools/manual-screenshots.mjs`: Trends-billedet vælger visningen med tankens temperaturer og *7 dage* (venter på, at visningerne er hentet).
- Manual: billedtekster til de nye billeder; *30 dage* med i listen over tidsrum.

## [3.12.3 build 0299] — 2026-10-31 — Manualen omlagt i flere kapitler og afsnit

- `frontend/src/manual/`: *Tegninger og Tegn* delt i **Tegninger**, **Tegn – tegne-editoren** og **Forbindelser (rør og ledninger)**; *Alarmer* og *Trends* flyttet ud af *Drift* til egne kapitler — alle med egne `##`-afsnit i indholdsfortegnelsen. Rettet forældet tekst (symbolbiblioteket står til højre, tilslutningspunkter fra stregerne, linjen over tegnefladen) og nyt om skillelinjer, Begge/Middel/Rå, Udfyld huller, låste grafer, Nulstil visning, forstør/fjern graf og animation på forbindelser. Kapitlerne er omnummereret (adresserne er uændrede).
- `frontend/src/manual/14-eksempler.md`: billede til hvert eksempel. Tegn-billederne taget om.
- `frontend/src/lib/manualGen.test.ts`: symbolbibliotekets kapitel hedder nu `11-symbolbibliotek.md`.
- `frontend/src/pages/DrawEditor.svelte`: ingen tom boble ved *Valgt element*, når intet er valgt.

## [3.12.2 build 0298] — 2026-10-31 — Rettet: ophobede bugter og nye rørstumper ved flytning af symboler

- `frontend/svgedit-host/pipes.js`: `reroute` lægger altid knæk inden for 60 enheder fra enden om (de er lavet automatisk).
- `frontend/svgedit-host/scada-core.js`: tryk på et symbol med *Forbindelse* valgt skifter til *Vælg* (flytter symbolet); flere lyttere på værktøjsskift (værktøjslinjen fulgte ikke med).
- Manual kap. 04. Tests: `src/lib/pipes.test.ts`.

## [3.12.1 build 0297] — 2026-10-31 — Topmenuen åbner kun ved klik

- `frontend/src/App.svelte`: menuerne i topbjælken åbner ikke længere, når musen føres hen over dem (og lukker ikke af sig selv, når musen forlader dem) — kun ved klik; lukkes ved nyt klik, valg, Escape eller klik udenfor (Jans ønske).

## [3.12.0 build 0296] — 2026-10-31 — Tekstredigering i Egenskaber

- `frontend/svgedit-host/scada-core.js`: `setText` (flere linjer som tspan'er; ét fortryd-trin, samme id); `setStyle` tillader `font-style`, `text-decoration`, `text-anchor` (justering flytter x, så teksten bliver stående); `paintOf` giver kursiv/understreget/justering/tekst.
- `frontend/svgedit-host/edit.js`: `textLines` (testet).
- `frontend/src/lib/draw/Inspector.svelte`: tekst-del med tekstfelt, størrelse (forslag), skrifttyper, F/K/U, justering, *Farve*. Manual kap. 04.

## [3.11.2 build 0295] — 2026-10-31 — Tegn: zoom, tegnehjælp og hjælpelinjer øverst

- `frontend/src/lib/draw/DrawCanvas.svelte`: linjen med zoom, tegnehjælp og hjælpelinjer er flyttet fra bunden op over tegnefladen (Jans ønske); værktøjets hjælpetekst bliver i bunden. Manual kap. 04.

## [3.11.1 build 0294] — 2026-10-31 — Rettet: skrå stykker i rør; værktøjet hedder nu Forbindelse

- `frontend/svgedit-host/pipes.js`: `pipeCorners` genfinder knæk ud fra buerne (også når mellemstykket er 0 langt); `ensureOrthogonal`.
- `frontend/svgedit-host/scada-core.js`: `drawPipe` tegner altid vinkelret (reparerer ældre rør).
- Omdøbt i brugerfladen: *Rør* → **Forbindelse** (kan bruges til rør og el-ledninger) — `DrawCanvas.svelte`, `toolHints.ts`, `Inspector.svelte` (*Ret forbindelsen ud*), `ObjectTree.svelte`, `SymbolEditor.svelte`, manual kap. 04. Internt (data-hv-pipe) uændret.
- Tests: `src/lib/pipes.test.ts`.

## [3.11.0 build 0293] — 2026-10-31 — Tydelig fang til hjælpelinjer

- `frontend/svgedit-host/guides.js`: `snapBoxToGuides` giver også linjen (`atX`/`atY`); `snapHint` (linje + prik på kanten) — testet.
- `frontend/svgedit-host/scada-core.js`: under træk vises linjen, symbolet vil blive fanget til (orange, prik, position) — lytter efter lærredet, så den aktuelle position vises; blink 0,7 s ved fang.
- Manual kap. 04. Tests: `src/lib/guides.test.ts`.

## [3.10.0 build 0292] — 2026-10-31 — Hjælpelinjer i Tegn

- `frontend/svgedit-host/guides.js` (ny, testet): læs/gem `data-hv-guides`, linjer (fast inddeling + frie), fang af bokse og punkter, justér til en linje.
- `frontend/svgedit-host/scada-core.js`: hjælpelinje-lag (kun i Tegn), træk/klik/Delete/Esc, gemt i tegningen med fortryd; fang i `settleSelection`, rør-værktøjet og stykke-træk; `align` til den aktive linje; API `getGuides`/`setGuideEvery`/`addGuide`. Rettet: fang ramte forkert ved zoom ≠ 100 %.
- `frontend/svgedit-host/pipes.js`: `alignDelta` tager ekstra linjer.
- `frontend/src/pages/DrawEditor.svelte`: *Hjælpelinjer*, *Inddeling*, *+ Lodret/+ Vandret*, *Fang til hjælpelinjer* i statuslinjen. `DrawCanvas.svelte`: knaplinjen viser og bruger den aktive linje.
- Manual kap. 04. Tests: `src/lib/guides.test.ts`, backend `test_svg_sanitize.py` (data-hv-guides overlever gem).

## [3.9.0 build 0291] — 2026-10-31 — Alt+klik vælger elementet bagved

- `frontend/src/lib/draw/engine.ts`: Alt+klik i Vælg går gennem elementerne under musen (forrest først, rundt) — `cycleNext` (testet).
- `frontend/src/lib/toolHints.ts`: hjælpeteksten nævner Alt+klik. Manual kap. 04.

## [3.8.0 build 0290] — 2026-10-31 — Læg rør-stykker sammen / Ret røret ud

- `frontend/svgedit-host/pipes.js`: `alignDelta` (fang på linje med parallelle stykker/enderne), `straighten`.
- `frontend/svgedit-host/scada-core.js`: stykke-træk fanger på linje; `straightenPipe`.
- `frontend/src/lib/draw/Inspector.svelte`: knappen *Ret røret ud* for rør. Manual kap. 04. Tests: `src/lib/pipes.test.ts`.

## [3.7.0 build 0289] — 2026-10-31 — Genvej mellem Tegn og symbol-editoren

- `frontend/src/lib/symbolRoute.ts` (ny, testet): `#symbols/<tegning>/<symboltype>`.
- `frontend/src/pages/DrawEditor.svelte`: *Ret tilslutningspunkter …* for valgt bibliotekssymbol og link i *Symboler*; spørger ved ugemte ændringer.
- `frontend/src/pages/SymbolEditor.svelte`: åbner på symbolet fra adressen; *← Tilbage til "<tegning>"*. `App.svelte`: route til siden.
- Manual kap. 04. BUGS.md: åben fejl om ugemte ændringer ved menuskift.

## [3.6.0 build 0288] — 2026-10-31 — Flyt et stykke af et rør

- `frontend/svgedit-host/pipes.js`: `moveSegment` (flyt et stykke på tværs, enderne bliver), `segmentHandles`; `reroute` bevarer ruten og lægger kun om fra det nærmeste knæk, der ikke ligger bag punktet.
- `frontend/svgedit-host/scada-core.js`: blå håndtag midt på det valgte rørs stykker (`startSegmentDrag`); rettet: museslip på håndtagene sendes til lærredet (ellers flyttede næste træk hele røret); "fang efter træk" springes over efter håndtag-træk.
- Manual kap. 04. Tests: `src/lib/pipes.test.ts`.

## [3.5.0 build 0287] — 2026-10-31 — Tegns højre panel: foldbare sektioner med fastgør

- `frontend/src/lib/draw/panels.ts` (ny, testet): fold ud/ind, fastgør, gemt tilstand. `PanelSection.svelte` (ny): overskrift med ▾/▸ og 📌.
- `frontend/src/pages/DrawEditor.svelte`: Valgt element, Egenskaber, Objekter og Symboler som sektioner (Valgt element og Egenskaber lige under hinanden, fastgjort fra start); åbne sektioner deler højden og ruller hver for sig.
- `Inspector.svelte`, `ObjectTree.svelte`: kun indhold (sektionen ejes af Tegn). Manual kap. 04.
- Tests: `src/lib/draw/panels.test.ts`.

## [3.4.0 build 0286] — 2026-10-31 — Rør-ende på rør-ende

- `frontend/svgedit-host/pipes.js`: `mergeRoutes`, `endDir`.
- `frontend/svgedit-host/scada-core.js`: `pipeEndNear`, `pipeMidNear`, `joinPipes` (røret med navn bevares; begge navngivne → ikke sammen), `changeCmd`/`removeCmd`/`commitCmds`; rør-værktøjet starter/slutter på rør-ender (forlænger røret); håndtag kan slippes på en rør-ende (sammen) eller midt på et rør (T-stykke).
- Manual kap. 04. Tests: `src/lib/pipes.test.ts`.

## [3.3.0 build 0285] — 2026-10-31 — Genforbind rør: håndtag på rørets ender

- `frontend/svgedit-host/scada-core.js`: håndtag på det valgte rørs ender (`drawHandles`, `startHandleDrag`) — træk på et tilslutningspunkt sætter enden fast (reroute + reference), andetsteds bliver den fri; ét fortryd-trin. `followPipes`: en flyttet rør-ende inden for 6 enheder af et punkt sættes fast igen (`portNear`).
- Manual kap. 04.

## [3.2.0 build 0284] — 2026-10-31 — T-stykke: rør koblet på rør

- `frontend/svgedit-host/pipes.js`: `nearestOnRoute`, `splitRoute`, `sideToward`, `branchSide`; `reroute` prøver alle ankerpunkter (et gammelt knæk bag det nye punkt gav en sløjfe, når et T-stykke blev flyttet).
- `frontend/svgedit-host/scada-core.js`: rør-værktøjet fanger til eksisterende rør (orange prik); `makeTee` deler røret, indsætter bibliotekets T-stykke drejet efter rør og gren, sætter halvdelene og grenen fast i benene — ét fortryd-trin; `setTeeSymbol`.
- `frontend/svgedit-host/symbolPorts.js`: `data-hv-ports` kan have en side pr. punkt (`fx,fy,side`).
- `frontend/src/pages/DrawEditor.svelte`: giver kernen bibliotekets T-stykke. Manual kap. 04.
- Tests: `src/lib/pipes.test.ts`.

## [3.1.1 build 0283] — 2026-10-31 — Rettet: Esc slog ikke rør-værktøjet fra

- `frontend/src/lib/draw/engine.ts`: et klik i tegnefladen fjerner fokus fra felter i panelerne, så Esc og genvejstaster virker.

## [3.1.0 build 0282] — 2026-10-31 — Rør: bøjningsradius, rigtig indgang efter drejning, punkter fra stregerne

- `frontend/svgedit-host/pipes.js`: `pathSegments`/`pathPoints` (alle stikommandoer), `portsFromVertices` (punkter fra stregerne), `sideDir`/`fracSide`/`turnDir` (retning der drejer med symbolet), `bestRoute`/`routeBetween`/`reroute`/`extendRoute` (vinkelret rute med lige stub ud af punktet), `pipePath`/`pipeCorners` (bløde bøjninger og genfinding af knæk); `simplify` fjerner ikke længere et punkt, hvor røret vender; referencen kan bære siden (`id@fx,fy,r`).
- `frontend/svgedit-host/symbolPorts.js`: buer og cirkler med i hjørnepunkterne; `autoPortsWithSide`.
- `frontend/svgedit-host/scada-core.js`: tilslutningspunkter med retning; rør-værktøj og "følg med" bruger retningen og lægger enden om, hvis røret kommer ind fra den forkerte side; `setPipeRadius`, `data-hv-radius`, nye rør får den senest brugte radius.
- `frontend/src/lib/draw/Inspector.svelte`: feltet *Bøjningsradius* for rør.
- Tests: `src/lib/pipes.test.ts`.

## [3.0.0 build 0281] — 2026-10-31 — Den nye tegne-editor er Tegn; SVG-Edit-appen er fjernet

- **Breaking:** Tegn kører altid den nye editor (`?editor=ny` er ikke længere nødvendig). SVG-Edits brugerflade i en iframe er væk — med den forsvinder stjerne/polygon, formbiblioteket, pipetten, billedværktøjet, linealerne og SVG-Edits lag-panel. Tegningerne er uændrede (ren SVG); ingen migration.
- `frontend/src/pages/DrawEditor.svelte`: iframe, `connect`, build-tjek og gammel tegnehjælp-/hjælpelinje fjernet.
- Fjernet: `svgedit`-pakken, `scripts/copy-svgedit.mjs`, `scripts/versionHost.mjs`, `svgedit-host/scada-editor.{js,css,html}`, `svgedit-host/locale-da.js`, tests `svgeditPatch.test.ts`, `versionHost.test.ts`; `predev`/`prebuild` i `package.json`. Drejegrebets markør ligger nu i `public/draw/rotate.svg` (MIT, fra SVG-Edit).
- `frontend/src/lib/draw/engine.ts`: *Skalér symmetrisk* virker ved træk i hjørnerne (BUGS.md); afkrydsninger (fx tegnehjælpen) blokerer ikke længere genvejstasterne; `window.scada` til manualens skærmbillede-script.
- `frontend/tools/manual-screenshots.mjs`: venter på tegnefladen i stedet for iframen. Manual kap. 04 beskriver den nye editor. `ARCHITECTURE.md`, `docs/SYMBOLSTANDARD_IMPLEMENTERING.md`, `backend/app/main.py` (kommentar).

## [2.18.0 build 0280] — 2026-10-31 — Ny tegne-editor: objekttræ

- `frontend/src/lib/draw/ObjectTree.svelte` (ny): panelet *Objekter* — elementer pr. lag, forrest øverst, navn og type; klik/Ctrl-klik vælger, ▲▼ rækkefølge, søgefelt.
- `frontend/svgedit-host/scada-core.js`: `objectList`, `toggleSelected`.
- `frontend/src/pages/DrawEditor.svelte`: *Objekter* under *Egenskaber* i den nye editor.

## [2.17.0 build 0279] — 2026-10-30 — Ny tegne-editor, trin 5: træk symboler fra paletten

- `frontend/svgedit-host/scada-core.js`: `insertSymbol(fragment, type, at)` lægger symbolets midte i punktet `at`; `docPointAt`; `screenToDoc` (frisk skærm→tegning-matrix — rettet for rør-værktøjet efter zoom/rulning).
- `frontend/src/lib/draw/DrawCanvas.svelte`: tegnefladen tager imod symboler (grøn stiplet kant mens der trækkes).
- `frontend/src/pages/DrawEditor.svelte`: paletten kan trækkes fra i den nye editor; ingen meddelelse over tegnefladen ved indsættelse (den skubbede fladen ned).

## [2.16.0 build 0278] — 2026-10-30 — Symbol-editor: tilslutningspunkter pr. symboltype

- Backend: `app/services/symbol_ports.py`, `app/api/symbol_ports.py` (nye): `GET/PUT/DELETE /api/symbol-ports[/{type}]` (tekniker), validering (1–32 punkter, 0..1), audit `symbol_ports.set/reset`. `storage/db.py`: gemt i `meta` (`symbolports.<type>`), med i projekt-eksport/gendannelse. `services/backup.py`: `symbol_ports` valideres ved gendannelse. `main.py`: registrering.
- Frontend: `pages/SymbolEditor.svelte` (ny side *Symboler*), `lib/nav.ts`, `App.svelte`. `svgedit-host/symbolPorts.js` (ny): fælles punkt-logik for Tegn og siden. `svgedit-host/scada-core.js`: `setLibraryPorts`; rettede punkter bygges ind ved indsættelse (`data-hv-ports`) og bruges af rør-værktøjet. `pages/DrawEditor.svelte`: henter punkterne.
- Manual kap. 04: *Tilslutningspunkter (siden Symboler)*.
- Loft: højst 500 symboltyper med rettede punkter (API og backup); beskadigede rækker springes over ved læsning (fra review).
- Tests: backend `test_symbol_ports.py`; frontend `symbolPorts.test.ts`, `nav.test.ts`.

## [2.15.1 build 0277] — 2026-10-30 — Rettet: drejning i 15°-trin i den nye editor; fortryd/gentag i værktøjslinjen

- `frontend/src/lib/draw/engine.ts`: drejningens midtpunkt læses uden `consolidate()` (ændrede elementets transform).
- `frontend/svgedit-host/scada-core.js`: `listMatrix` (læser transform uden at ændre den); `applyBox` flytter med translate forrest, så en drejning bevares.
- `frontend/src/lib/draw/DrawCanvas.svelte`: Fortryd og Gentag øverst i venstre værktøjslinje (flyttet fra statuslinjen).

## [2.15.0 build 0276] — 2026-10-30 — Ny tegne-editor, trin 4: rør-værktøj

- `frontend/svgedit-host/pipes.js` (ny): rene beregninger — vinkelret ruteføring (`orthoLeg`, `connect`), ende-flytning der holder røret vinkelret (`moveEnd`), tilslutningspunkter (`portsFrom`), referencer som brøkdel af symbolets boks.
- `frontend/svgedit-host/scada-core.js`: rør-værktøj (`setPipeTool`) med tilslutningspunkter og forhåndsvisning; rør følger deres symboler i samme fortryd-trin (hægtet på fortryd-historikken, virker også i den gamle editor); kopier af rør slipper symbolerne; nye rør lægges bag de symboler, de forbinder.
- `frontend/src/lib/draw/engine.ts`, `DrawCanvas.svelte`: værktøjet *Rør* (tast O) i værktøjslinjen. `src/lib/toolHints.ts`: hjælpetekst.
- Tests: `src/lib/pipes.test.ts` (ny), backend `test_svg_sanitize.py` (rørets data-hv-attributter overlever gem).

## [2.14.0 build 0275] — 2026-10-30 — Ny tegne-editor, trin 2–3: panel, svævende linje, højreklikmenu

- `frontend/svgedit-host/edit.js` (ny): rene beregninger til panelet (`boxMapping`, `editBox`, `distribute`).
- `frontend/svgedit-host/scada-core.js`: `inspect`, `setBox`, `setAngle`, `setStyle`, `align`, `distribute`, `order`, `flip`. Størrelse/placering sættes med lærredets eget translate/scale/translate-mønster, så elementet får rene mål (x, width …) i stedet for en matrix; ét fortryd-trin pr. ændring.
- `frontend/src/lib/draw/Inspector.svelte` (ny): panelet *Egenskaber*.
- `frontend/src/lib/draw/DrawCanvas.svelte`: svævende linje til det markerede, højreklikmenu, tegnehjælp og hjælpetekst i statuslinjen.
- `frontend/src/lib/draw/engine.ts`: `perform()` (fælles for taster, knapper og menu); drejning i 15°-trin og fri med Shift; piletaster flytter i tegningens enheder uanset zoom.
- `frontend/src/pages/DrawEditor.svelte`: tegnehjælpen som snippet (egen linje i den gamle editor, statuslinjen i den nye); *Egenskaber* øverst i sidepanelet.
- Tests: `src/lib/editMath.test.ts` (ny), `src/lib/draw/engine.test.ts` (drejning).

## [2.13.0 build 0274] — 2026-10-30 — Ny tegne-editor, trin 1: motor uden iframe (bag ?editor=ny)

- `frontend/svgedit-host/scada-core.js` (ny): al vores egen Tegn-logik (gitter, fang, id'er, navne, symboler, `window.scada`-API'et) som `createScada(host)` — uafhængig af SVG-Edits brugerflade. `scada-editor.js` er nu kun SVG-Edit-adapteren.
- `frontend/src/lib/draw/engine.ts` (ny): `@svgedit/svgcanvas` direkte i siden — rulleflade, zoom (Ctrl+hjul, trin, Tilpas), panorering (mellemrum/midterknap), tastatur (fortryd, kopiér/indsæt, dupliker, gruppér, slet, pile, værktøjstaster).
- `frontend/src/lib/draw/DrawCanvas.svelte` (ny): venstre værktøjsrail + statuslinje. `pages/DrawEditor.svelte`: bruger den med `?editor=ny`; venter på tegningslisten før `#draw/<id>` åbnes.
- Rettet: gitteret var forskudt i tegninger uden fuld baggrund (BUGS.md).
- `frontend/package.json`: `@svgedit/svgcanvas` som direkte afhængighed (var allerede med via `svgedit`, MIT).
- Tests: `src/lib/draw/engine.test.ts`, `svgeditPatch.test.ts` opdateret.

## [2.12.0 build 0273] — 2026-10-30 — Tilstandsmærket kan fravælges

- `backend/app/services/symbols.py`: feltet `badge` (standard sand) på symbolopsætningen; `symbol_view` sender det.
- `frontend/src/lib/symbolConfig.ts`, `symbolUi.ts` (`showsBadge`), `symbolOverlay.ts` (`badge` i overlaget), `pages/Overview.svelte`, `SymbolGuide.svelte` (*Vis tilstandsmærke* i trin 4).
- Tests: `symbolOverlay.test.ts`, backend `test_symbols.py`. Manual kap. 06.

## [2.11.1 build 0272] — 2026-10-30 — "Gælder i" rydes ved skift til kilden position

- `frontend/src/lib/symbolConfig.ts`: `keepsOnly`. `frontend/src/lib/SymbolGuide.svelte`: `resetParams` bruger den.
- `backend/app/services/symbols.py`: `only` rydes også, når kilden er `@pos`.
- Tests: `symbolConfig.test.ts`, backend `test_symbols.py`.

## [2.11.0 build 0271] — 2026-10-30 — Gem og tegn omskifteren om (fra guiden)

- `frontend/src/lib/SymbolGuide.svelte`: i trin 3 erstattes henvisningen til Tegn af knappen *Gem og tegn omskifteren om* (nyt prop `selectorRedraw`; `onsaved({ redraw })`).
- `frontend/src/pages/DrawEditor.svelte`: guiden får `selectorRedraw="auto"` (Gem tegner allerede om); ny rute `#draw/<tegning>/<element>` vælger omskifteren og tegner den om (`redrawFromRoute`).
- `frontend/src/pages/Editor.svelte`: *Gem og tegn omskifteren om i Tegn* gemmer og åbner Tegn med omskifteren valgt.
- `frontend/src/manual/06-symboler-og-guiden.md`: beskrevet.

## [2.10.2 build 0270] — 2026-10-30 — Eksterne coils/registre genkendes som til/fra og tal

- `frontend/src/lib/symbolConfig.ts`: `tagKind` finder typen rigtigt for `rtu` og `mbx` (og `coils`).
- `frontend/src/lib/animPreview.ts`, `AnimPreview.svelte`, `SymbolGuide.svelte`: skyderens område følger tagets min/max, når animationerne ikke har et.
- Tests: `symbolConfig.test.ts` (eksterne kilder), `animPreviewLogic.test.ts` (område).

## [2.10.1 build 0269] — 2026-10-30 — Preview: symbolet vises også, når det står forskudt i tegningen

- `frontend/src/lib/AnimPreview.svelte`: symbolet pakkes ind i en `<g>`, og viewBox måles på den (getBBox medregner ikke elementets egen transform). `AnimPreviewPanel.test.ts`: tjek af indpakningen.

## [2.10.0 build 0268] — 2026-10-30 — Live preview ved animationerne i guiden

- `frontend/src/lib/animPreview.ts` (ny): guidens opsætning → de samme bindinger som Overview bruger (kilde, position, "gælder i", aktiv/passiv, logikblok, alarm, fast værdi, retnings-tag), kontroller og afspilning.
- `frontend/src/lib/AnimPreview.svelte` (ny): lille preview af symbolet ved siden af animationerne i trin 4 med Fra/Til, skyder og positionsknapper, Afspil og Nulstil. Tegnes med Overviews animationsmotor (`renderAll`); gemmer og skriver intet.
- `frontend/src/lib/SymbolGuide.svelte`: monterer preview'et (ved siden af listen på brede skærme, over den på smalle).
- Tests: `animPreviewLogic.test.ts`, `AnimPreviewPanel.test.ts` (+ `AnimPreviewHarness.svelte`). Manual kap. 06.

## [2.9.0 build 0267] — 2026-10-30 — Segment-display (7/11 segmenter, 1–16 cifre)

- `frontend/src/lib/segDisplay.ts` (ny): tegn → segmenter for 7- og 11-segment, layout (justering, foranstillede nuller, decimalpunkt, overløb), tegning af 1–16 cifre og visning.
- `frontend/src/lib/animate.ts`, `api.ts`: ny animationstype `segments` (tal formateres som under Værdi, uden enhed; til/fra = 1/0; ukendt = bindestreg).
- `frontend/src/lib/symbols.ts`: bibliotekssymbolerne *7-segment display* og *11-segment display* (4 cifre); `SEG_OFF` i symbolpaletten.
- `frontend/src/lib/symbolConfig.ts`, `symbolSim.ts`, `AnimParams.svelte`, `SymbolGuide.svelte`: animationen *Segmenter* i guiden og Symboltest (decimaler, beregning, justering, nuller, farver); forslag fra biblioteket.
- `frontend/src/pages/DrawEditor.svelte`: *Display med egne cifre* (type og 1–16 cifre) under *Proces og visning*.
- `backend/app/services/symbols.py`: `ASegments` (parametre valideres), kun som *Hele symbolet* på et display, kun med et tal-tag.
- Tests: `segDisplay.test.ts` (ny), `animate.test.ts`, `symbolConfig.test.ts`, `symbolSimAudit.test.ts`, backend `test_symbols.py`. Manual kap. 04–07.

## [2.8.1 build 0266] — 2026-10-30 — Gør et interaktivt symbol passivt uden at miste kontaktplanerne

- `frontend/src/lib/SymbolGuide.svelte`: knappen *Gør til kun passiv visning (behold trin og kontaktplaner)* under *Interaktiv betjening* (trin 1). Før mistede et symbol sine positioner og kontaktplaner, hvis man først valgte *Kun passiv visning*.
- `frontend/src/manual/06-symboler-og-guiden.md`: beskrevet.

## [2.8.0 build 0265] — 2026-10-30 — Kun passiv visning med positioner

- `backend/app/services/symbols.py`: nyt felt `passive` på symbolopsætningen; ved `passive` ryddes kommando-tag, skrivemåde, bekræftelse, fejlsignal, alarm og nøglelås, visningen tvinges til PLC'ens position, og hvert signal skal have en tilbagemelding (som ikke behøver at være skrivbar). `symbol_view` sender `passive`.
- `backend/app/services/symbol_runtime.py`: positionen findes ud fra tilbagemeldingen alene, når der ikke er et kommando-tag.
- `backend/app/services/symbol_operate.py`: betjening (plan, skift, puls, setpunkt, accepter) af et passivt symbol afvises med 409.
- `backend/app/api/symbols.py`: ingen skriveplan i forhåndsvisningen for passive symboler.
- `frontend/src/lib/symbolConfig.ts`, `symbolUi.ts`, `symbolOverlay.ts`, `pages/Overview.svelte`: `setPassive`, `isOperable`, `markPassive`; passive symboler kan ikke klikkes og får tooltip *Kun visning — kan ikke betjenes*; et valg af betjening efter passiv visning genindsætter bekræftelse og alarm.
- `frontend/src/lib/SymbolGuide.svelte`: trin 1 har *Symbolet har trin* under *Kun passiv visning*; trin 2 gør *Kommando* grå og kræver tilbagemelding; trin 4/5/6 tilpasset; *Hurtig opsætning* rydder ikke en passiv opsætning.
- Tests: backend (`test_symbols.py`, `test_symbol_runtime.py`, `test_symbol_operate.py`), frontend (`symbolConfig.test.ts`, `symbolUi.test.ts`, `symbolOverlay.test.ts`). Manual kap. 06.

## [2.7.0 build 0264] — 2026-10-29 — Nye navne på betjeningsformer, hængelås ved låste positioner

- `frontend/src/lib/symbolConfig.ts`: `OP_TXT` — *Kun passiv visning*, *Interaktiv betjening*.
- `frontend/src/lib/symbolOverlay.ts`: `lockedTexts` + hængelås ud for teksten for hver låst position; `lockGlyph` fælles for begge låse.
- `frontend/src/pages/Overview.svelte`: sender de låste positioners navne til overlaget.
- `frontend/src/lib/symbolOverlay.test.ts` (ny), `symbolCopy.test.ts`, `SymbolGuide.svelte`, manual kap. 06 og 07: nye navne og beskrivelse.

## [2.6.1 build 0263] — 2026-10-29 — Symbol-guiden: robusthedsrettelser

- `frontend/src/lib/SymbolGuide.svelte`: Fjern position fjerner også `pos_values`; *Tid til at bekræfte* min 1 s.
- `backend/app/services/symbols.py`: pulssignalets fejl under trin 2, "mindst ét plan … ikke puls" under trin 3; advarsel når tilbagemelding = kommando-tag.
- `backend/tests/test_symbols.py`: trin rettet; ny test for advarslen.
- Koden kom i commit 1 (uden versionsbump pga. en scriptfejl); version og dokumentation i den efterfølgende commit.

## [2.6.0 build 0262] — 2026-10-29 — Skalér symmetrisk i Tegn

- `frontend/public/svgedit/scada-editor.js`: `guides.keepRatio`; under en størrelsesændring vendes Shift om (SVG-Edit skalerer symmetrisk med Shift). Billeder røres ikke.
- `frontend/src/pages/DrawEditor.svelte`: afkrydsningen *Skalér symmetrisk* ved tegnehjælpen; huskes i `draw.guides`.
- `frontend/src/manual/04-tegninger-og-tegn.md`: indstillingen beskrevet.
- `frontend/src/pages/SymbolTestSweep.test.ts`: gennemgangen af hele biblioteket har 30 s timeout (faldt for 5 s under fuld suite).

## [2.5.2 build 0261] — 2026-10-29 — OTA-pakken kan ikke bygges med ucommittede ændringer

- `deploy/make-package.sh`: stopper med en fejl (i stedet for en advarsel), når der er ucommittede ændringer — ellers fik pakken HEAD's backend og version.json, men arbejdsmappens frontend.

## [2.5.1 build 0260] — 2026-10-29 — Tilbagemelding på alle eller ingen signaler

- `backend/app/services/symbols.py`: `feedback_coverage()` (all/none/mixed); blandet tilbagemelding afvises i trin 2; `display = remote` kræver tilbagemelding på alle signaler i kontaktplanerne.
- `backend/app/services/symbol_runtime.py`: puls-signal med tilbagemelding bruges til at finde positionen (fejl: blev altid sprunget over).
- `frontend/src/lib/symbolConfig.ts`: `feedbackCoverage()`, `hasFeedback()` kræver alle; `foundPosition` bruger puls-signaler med tilbagemelding.
- `frontend/src/lib/SymbolGuide.svelte`, `frontend/src/manual/06-symboler-og-guiden.md`: teksterne forklarer reglen.
- Tests: `test_symbols.py` (dec_bin har nu tilbagemelding på alle tre bit), `test_symbol_operate.py`, `test_symbol_runtime.py`, `symbolConfig.test.ts`.

## [2.5.0 build 0259] — 2026-10-29 — PLC'ens position kræver tilbagemelding

- `backend/app/services/symbols.py`: `has_feedback()`; trin 4 afviser `display = remote` uden tilbagemelding på et signal i en kontaktplan.
- `backend/app/services/symbol_convert.py`: konverterede omskiftere/til-fra får kommando-tagget som tilbagemelding (samme opførsel som før).
- `frontend/src/lib/symbolConfig.ts`: `hasFeedback()`; nye symboler og biblioteksstandarder får `display = local`.
- `frontend/src/lib/SymbolGuide.svelte`: *PLC'ens position* kan ikke vælges uden tilbagemelding; teksten i trin 2 forklarer kravet.
- `frontend/src/manual/06-symboler-og-guiden.md`: kravet beskrevet.
- Tests: `test_symbols.py`, `symbolConfig.test.ts`; testopsætninger uden tilbagemelding bruger nu `local`.

## [2.4.0 build 0258] — 2026-10-29 — Omskifter opdaterer sig med det samme

- `frontend/src/pages/DrawEditor.svelte`: efter guidens Gem tegnes en omskifter automatisk om, hvis opsætningens positioner afviger fra tegningen (`redrawSelector(auto)`), og tegningen gemmes uden at spørge (den var udgivet, før guiden blev åbnet).

## [2.3.0 build 0257] — 2026-10-29 — Skrivbare tags i egen farve

- `frontend/src/app.css`: ny farve `--writable` og klasserne `.tag-writable` og `.badge.writable`.
- `frontend/src/pages/Tags.svelte`: skrivbare tags har navn og badge i lilla.
- `frontend/src/lib/TagSelect.svelte`: skrivbare tags er lilla i alle tag-dropdowns.

## [2.2.0 build 0256] — 2026-10-27 — Version i topmenuen

- `frontend/src/App.svelte`: snippet `version` — serverens version og build (`/api/health`, indtil da sidens egen) yderst til højre i topmenuen og på login-siden; build skjules under 640 px.

## [2.1.2 build 0255] — 2026-10-27 — Trends: aflæsning og y-akse ved lille spænd

- `frontend/src/lib/trendData.ts`: `stepDecimals(incr)` — decimaler der skal til for at skelne aksestregerne.
- `frontend/src/lib/TrendChart.svelte`: y-aksens tekster med `stepDecimals`; aflæsning og tooltip med mindst så mange decimaler som aksen (før rundet til tagets decimaler → stod fast).
- Test: `trendData.test.ts::stepDecimals`.

## [2.1.1 build 0254] — 2026-10-27 — Trends: forkert værdi i aflæsningsfeltet

- `frontend/src/lib/TrendChart.svelte`: legend-værdien bruger kurvens indeks fra `series.map((s, k)` i stedet for `series.indexOf(s)` (gav -1 → tidsaksen).

## [2.1.0 build 0253] — 2026-10-27 — Advarsler om tilbagemeldinger i symbol-guiden

- `backend/app/services/symbols.py`: advarsel når en tilbagemelding er et register (statusord), er skaleret anderledes end kommandoen, eller er en ST-variabel (typen kendes først live).
- `frontend/src/lib/symbolConfig.ts` `feedbackMismatch` + `SymbolGuide.svelte` trin 6: advarsel når tilbagemeldingens live-værdi ikke passer til kommandoens type (til/fra-kommando med fx 3, tal-kommando med til/fra).
- Tests: `test_symbols.py::test_feedback_warnings`, `symbolConfig.test.ts`.

## [2.0.1 build 0252] — 2026-10-27 — Tydeligere alarm-opsætning på tags

- `frontend/src/pages/Tags.svelte`: bedre hjælpetekst under *Alarmer* (grænser vs. til/fra, dødbånd, forsinkelse), live advarsel når begge typer er udfyldt, og gemme-fejlen ryddes når et alarmfelt ændres.

## [2.0.0 build 0251] — 2026-10-27 — Prioritet pr. tag (høj/normal) for eksterne Modbus-tags

- **Skemaændring (MAJOR):** `tags.priority` (`normal`/`high`, standard `normal`), skemaversion 14; eksisterende databaser migreres automatisk.
- `services/tags.py`: validering (kun `rtu`/`mbx` kan være høje; skiftes kilden til intern, bliver den normal); `api/routes.py`; backup/gendannelse (ældre backups → normal).
- `services/plc_runtime.py`: høje og normale eksterne tags planlægges i hver sine områder (aldrig samme `/api/ext`-kald), høje polles først; `plc/client.py` `read_ext(prio=…)` sender `prio=high`; `plc/planner.py` `ExtRange.high`.
- `frontend/src/pages/Tags.svelte`: *Prioritet: Normal/Høj* (låst for interne tags) med hjælpetekst og mærket *høj prioritet* i listen; manualen (PLC'er og tags).
- `tests/test_ext.py` (+3). Spec: `docs/FEATURE_TAG_PRIORITET.md`. Effekten kræver PLC-firmware med FEAT-515; ældre firmware ignorerer parameteren.

## [1.22.2 build 0250] — 2026-10-27 — Bekræftelse før sletning af automatisk bundne tags (funktionsanalyse B6)

- `services/tags.py` `delete(force)` + `auto_usage` (sat i `main.py`); `DELETE /api/tags/{name}?force=true`; `Tags.svelte` spørger først.
- `tests/test_drawings_api.py` (+1, 1 tilpasset).

## [1.22.1 build 0249] — 2026-10-27 — Versionsrapport og gendannelse siger, hvad der går tabt (funktionsanalyse B4 + B5)

- `services/drawings.py`: `orphaned_symbols` i versionsrapporten; `Drawings.svelte`/`DrawEditor.svelte` viser dem.
- `storage/db.py` `replace_project()`: PIN-koder bevares for symboler der findes efter gendannelsen; `services/backup.py`: `missing_pins`, `symbol_configs`, `symbol_groups`; `Backup.svelte` viser dem.
- `tests/test_backup.py` (+1).

## [1.22.0 build 0248] — 2026-10-27 — Simple bindinger og wizard hænger sammen (funktionsanalyse B1–B3)

- `services/drawings.py`: `_config_owner()`/`_refuse_if_configured()` i `set_element_bindings()` og `bind_symbol()`; `click:goto` på roden af et kun-visning-symbol gælder stadig.
- `storage/db.py` `binding_places()`, `services/tags.py`: sletbesked med tegning og element.
- `frontend/src/pages/Editor.svelte`: besked for dele af konfigurerede symboler, *Tilføj binding* skjult.
- Tests (+1, 1 tilpasset).

## [1.21.12 build 0247] — 2026-10-26 — PIN-spærring stiger og overlever genstart (kodeanalyse 2, G3)

- `services/symbol_operate.py`: `PIN_LOCK_STEPS` (60/300/900/3600 s), `SYMBOL_TRIES` (10) pr. symbol, tilstand i databasen, `_fmt_wait()`.
- `tests/test_symbol_operate.py` (+1, 1 tilpasset).

## [1.21.11 build 0246] — 2026-10-26 — Live-forbindelsen følger ændrede tegninger (kodeanalyse 2, G4)

- `api/live_ws.py`: `revalidate()` genberegner `visible` hver gang og sender nyt snapshot ved ændring. `tests/test_scope.py` (+1).

## [1.21.10 build 0245] — 2026-10-26 — Strammere validering (kodeanalyse 2, G2 + G5)

- `services/svg_sanitize.py`: `_css_unescape()` før kontrol af `@import`/`url(` i `<style>`, `style=` og præsentationsattributter.
- 16 valideringsmønstre (auth, backup, bindings, netconfig, schedule_engine, svg_sanitize, symbols, tags, tagsource, updates, storage/files): `\Z` i stedet for `$`.
- `tests/test_svg_sanitize.py` (+2).

## [1.21.9 build 0244] — 2026-10-26 — Login kan ikke længere holde serveren travl (kodeanalyse 2, G1)

- `services/auth.py`: `verify()` med `VERIFY_CONCURRENCY` (2); fejl pr. IP på tværs af brugernavne (`IP_MAX_FAILS` 20 / `IP_FAIL_WINDOW_S` 300); tællere under lås.
- `api/auth.py`: login og skift af adgangskode i `asyncio.to_thread`; `services/symbol_operate.py`: PIN-tjek i en tråd.
- `tests/test_auth.py` (+2).

## [1.21.8 build 0243] — 2026-10-26 — Trend-målinger tabes ikke ved databasefejl (kodeanalyse F3)

- `services/trends.py`: ved fejl i `insert_many` lægges rækkerne tilbage i bufferen (`MAX_BUFFER_ROWS` = 100.000). `tests/test_trends.py` (+1).

## [1.21.7 build 0242] — 2026-10-26 — Tunge trend-kald og oprydning blokerer ikke længere serveren (kodeanalyse F1 + F2 + F7)

- `api/trends.py`: data, CSV og info i `asyncio.to_thread`.
- `storage/trends_db.py`: `purge_before()` pr. tag via primærnøglen; `services/trends.py`: `purge()`/`purge_due()`, kørt i en tråd fra `run()`.
- `services/backup.py`: automatisk backup i en tråd.
- `tests/test_trends.py` (+1).

## [1.21.6 build 0241] — 2026-10-26 — Energi: lineær beregning i tråd og fejlmålinger i tællere (kodeanalyse F6 + F5)

- `services/energy.py`: `counter_energy()`/`power_energy()` i ét gennemløb (lineær tid); tæller-fald kræver bekræftelse (`RESET_LOOKAHEAD` = 3), ellers fejlmåling.
- `api/energy.py`: rapport og CSV regnes i `asyncio.to_thread`.
- `tests/test_energy.py` (+3).

## [1.21.5 build 0240] — 2026-10-26 — Puls: SLUK med genforsøg og alarm (kodeanalyse F4)

- `operate.py`: `_write_rest()` skriver hvileværdien med genforsøg i op til `REST_RETRY_S` (10 s); ved endelig fejl markeres tagget, og `alarm_conditions()` giver en alarm, indtil tagget skrives med succes. Bruges af `pulse()` og `pulse_value()`.
- `plc/client.py`: `urgent`-flag på `request()` og skrivekald — afvises ikke af den lokale rate-limit-pause.
- `main.py`: alarmkilden registreret. `mock_plc`: `throttle_off_writes`. Tests (+2).

## [1.21.4 build 0239] — 2026-10-26 — Rettelse af regression i v1.21.3

- `plc_runtime`: kald-tælleren til rate-limit-diagnostikken læses robust (`_requests_sent()`), så en klient uden `request_count` ikke giver fejl i hver cyklus. `backend/app/services/plc_runtime.py`.

## [1.21.3 build 0238] — 2026-10-26 — PLC-rate-limit (429) giver ikke længere "kommunikation tabt"

- `plc_runtime`: 429 behandles som "PLC'en vil have færre kald": værdierne beholdes, status viser en notits, og først efter `RATE_LIMIT_GRACE_S` (60 s) uafbrudt bliver det en kommunikationsfejl/COMM-alarm. Status har `throttled`/`last_throttled`; loggen viser SCADA's kald/s det seneste minut ved første afvisning.
- PLC'er-siden viser *Rate-limit: afvist N gange · senest …*.
- Rodårsagen var i PLC-firmwaren (BUG-509: fælles rate-limit for alle klienter) — rettet i HypervisionPLC v7.9.68.150.
- `backend/app/services/{plc_runtime,manager}.py`, `tests/test_runtime.py` (+1), `frontend/src/pages/Plcs.svelte`.

## [1.21.2 build 0237] — 2026-10-26 — Trends: tidsvægtet gennemsnit i nedsamplingen

- `TrendDatabase.series` vægter hver værdi med den tid, den stod (værdier gemmes kun ved ændring; højst 360 s pr. række), i stedet for et gennemsnit pr. række. En kort fejlmåling gav før dyk på op til 18,5 °C i kurven (og i middelkurven); nu ca. 1 °C. Spand uden rækker, hvor en uændret værdi stadig gælder, får nu også et punkt; et hul gælder for hele sin varighed.
- `backend/app/storage/trends_db.py`, `tests/test_trends.py` (+1 test, 1 rettet forventning). Kontrolleret på testserverens data.

## [1.21.1 build 0236] — 2026-10-26 — Trends: værdier ved markøren for alle kurver

- Boksen ved markøren og forklaringen viser nu hver kurves nærmeste måling i tid i stedet for "—", når kurverne har forskellige tidspunkter. `lib/TrendChart.svelte` (`valueAt`). Set i Chromium.

## [1.21.0 build 0235] — 2026-10-26 — Trendgraf i tegningen: middelkurve

- Ny opsætning `avg_h` (0–720 timer) og `avg_mode` (`both`/`avg`) på trendgraf-symbolet (backend `Chart`, API-validering + test); grafen i tegningen (og den store visning) henter forløbet før perioden med, regner glidende middel og tegner den stiplet i kontrastfarve (eller i stedet), med egne poster i forklaringen. Valg i Opsæt symbol › Visning. Gamle grafer uændrede (standard: ingen).
- `backend/app/services/symbols.py`, `tests/test_trend_symbols.py`, `frontend/src/lib/{chartGraphic,chartRender,SymbolGuide,trendData}`. Tegningsgrafen set i Chromium (raw / begge / kun middel); selve opsætningsdialogen ikke set.

## [1.20.0 build 0234] — 2026-10-26 — Trends: beskedboks med værdier ved markøren

- `TrendChart.svelte`: en boks ved markøren (uPlot `setCursor`) med tidspunkt og alle kurvers værdi; farveprøve (stiplet for middelkurver); vender til anden side/op ved kanten; rører ikke musen (`pointer-events: none`). Manualen. Set i Chromium.

## [1.19.0 build 0233] — 2026-10-26 — Trends: skift mellem begge, middel og rå kurve

- Tre knapper **Begge / Middel / Rå** ved *Middel over* erstatter afkrydsningen *Stiplet*; valget huskes i browseren (`trend.avgMode`). *Rå* henter ikke det ekstra forløb. `pages/Trends.svelte`, manualen. Set i Chromium.

## [1.18.1 build 0232] — 2026-10-26 — Trends: middelkurven altid i kontrastfarve

- Den stiplede middelkurve får altid en anden farve end råkurven: den palet-farve der ligger længst fra råkurvens i farvetone og ikke bruges af andre kurver i grafen; er alle i brug, næsten sort. `lib/trendData.ts` (`contrastColor`), `TrendChart.svelte` (`color`), `Trends.svelte`; tests (+2). Set i Chromium.

## [1.18.0 build 0231] — 2026-10-26 — Trends: middelkurve som stiplet linje

- *Middel over* tegner nu middelkurven som stiplet linje i samme farve ved siden af den rå kurve (afkrydsning *Stiplet*, standard til; fra = erstat som før). Ekstra kurve pr. tag i samme graf, legend "… (middel 24 t)"; til/fra-kurver røres ikke.
- `frontend/src/lib/TrendChart.svelte` (`dashed`), `pages/Trends.svelte`, manualen. Set i Chromium med mock-API.

## [1.17.0 build 0230] — 2026-10-26 — Trends: kurver som glidende middelværdi (fx 24 timer)

- Ny vælger **Middel over** (Ingen, 15 min, 1 time, 8 timer, 24 timer, 7 dage, egen tid): hver tal-kurve vises som bagudrettet glidende middelværdi; forløbet før perioden hentes med og skæres af, huller tæller ikke med, til/fra-kurver røres ikke. Kun visning. Huskes i browseren.
- `frontend/src/lib/trendData.ts` (`movingAverage`, `AVERAGE_CHOICES`), `pages/Trends.svelte`, manualen, tests (+3). Set i Chromium med mock-API.

## [1.16.3 build 0229] — 2026-10-26 — Trends: graf tegnes efter valg af visning (rigtig årsag) + Nulstil valg

- Grafer bygget midt i en omtegning fik aldrig sat x-aksen (min/max = null) og stod tomme; `TrendChart` tjekker og sætter den nu i næste billede. Genskabt og verificeret i Chromium (5 scenarier).
- Ny knap **Nulstil valg** i Trends: fravælger alle tags, rydder visning, graf-valg og zoom.
- `frontend/src/lib/TrendChart.svelte`, `pages/Trends.svelte`, `pages/TrendsViews.test.ts` (+1 test).

## [1.16.2 build 0228] — 2026-10-26 — Trends: graf tegnes straks efter valg af visning

- `TrendChart` brugte en bredde på 0 for grafer oprettet før layoutet var målt; nu bruges aldrig 0, og grafen tilpasses/tegnes om i næste billede efter opbygning og dataopdatering. `frontend/src/lib/TrendChart.svelte`. Ikke set i browser.

## [1.16.1 build 0227] — 2026-10-26 — Trends: visning tegner graferne robust

- Valg af en gemt visning henter nu dataene først og skifter udvalg, periode og data i ét hug (graferne bygges aldrig tomme), tager kun tags med historik, viser en synlig besked ved fejl eller når intet kan vises, og en nyere valgt visning overstyrer en ældre. Rapporteret: grafer blev ikke tegnet; årsagen blev ikke genskabt (se BUGS.md).
- `frontend/src/pages/Trends.svelte` (`chooseView`, `fetchData`, `period`), `pages/TrendsViews.test.ts` (ny, 3 tests). Ikke set i browser.

## [1.16.0 build 0226] — 2026-10-26 — Trends: gem udvalg af tags som navngivne visninger

- Trends: ny dropdown **Visning** øverst i tag-panelet. Tekniker/admin kan gemme det aktuelle udvalg (tags, graf-valg og tidsrum) under et navn — fx alle 8 temperaturfølere i en tank som *Tank temp* — med **Gem som …**, **Opdatér** (stjerne når udvalget er ændret) og **Slet**. Alle brugere kan vælge en visning; tags de ikke har adgang til/historik for, springes over med en besked (rettigheder håndhæves stadig ved datahentning).
- Backend: `GET/POST/DELETE /api/trends/views` (læs: viewer; gem/slet: engineer, audit-log), lagret som én indstilling pr. visning (`setting.trendview.<navn>`, ingen skemaændring og ingen læs-ændr-skriv på en samlet liste); navne unikke uden hensyn til store/små bogstaver; højst 40 tags/100 visninger; brugerdefineret periode huskes ikke. Med i backup/gendannelse (valideres).
- `backend/app/{services/trend_views.py (ny),storage/db.py,services/backup.py,api/trends.py,main.py}`, `frontend/src/lib/trendViews.ts (ny)`, `pages/Trends.svelte`, manualen, tests (backend 4, frontend 4). Ikke set i browser.

## [1.15.0 build 0225] — 2026-10-25 — Trendgraf i stor udgave

- Overview: et tryk på et trend-symbol viser grafen i et stort vindue (op til 1200×780 px) med valg af periode (15 min … 7 dage) og knappen **← Tilbage til tegningen** (også Esc og klik udenfor). Virker for alle roller (kun visning). Musemarkøren er et forstørrelsesglas over trend-symboler.
- Grafen tegnes af samme kode som i tegningen: `chartRender.mountChartIn()` er trukket ud af `mountCharts()`; en større boks giver flere punkter og diagramlinjer i stedet for at strække grafen.
- `frontend/src/lib/{chartRender.ts,ChartBig.svelte (ny)}`, `pages/Overview.svelte`, `app.css`, manualen, test (2 nye).

## [1.14.0 build 0224] — 2026-10-25 — Omskifter: tegningens gradtal ved Drej pr. position

- Opsæt symbol › Animationer: for bibliotekets omskiftere (omskifter, omskifter3, drejeomskifter) vises **Tegningens vinkler** under *Drej* pr. position (kilde *symbolets position* eller *pr. værdi*), med knappen *Brug tegningens vinkler*. Nye/ændrede Drej-animationer starter med tegningens vinkler i stedet for et gæt (−45…45). Har tegningen et andet antal positioner end opsætningen, vises en besked i stedet.
- `frontend/src/lib/{selectorRedraw.ts,SymbolGuide.svelte}`, manualen, tests (2 nye).

## [1.13.1 build 0223] — 2026-10-25 — "Gælder i" skjules ved "Pr. værdi"

- "Gælder i" læser symbolets EGEN position, ikke positionen afledt af tagget, og var forvirrende ved siden af fra-værdierne. Ved *Pr. værdi* skjules den nu i guiden, og serveren rydder den (`only`). Uden *Pr. værdi* er den uændret.
- `frontend/src/lib/SymbolGuide.svelte`, `backend/app/services/symbols.py`, test.

## [1.13.0 build 0222] — 2026-10-25 — Pr. værdi: afgræns hvilke tag-værdier der hører til hver position

- Jan: en omskifter har faste positioner, så knappen må ikke kunne stå midt imellem, hvis tagget har en uventet værdi. Med *Pr. værdi* angives nu en **fra-værdi pr. position** (stigende, standard 0, 1, 2 …): positionen er den sidste, hvis fra-værdi er nået; under den første: ingen position (delen som tegnet).
- Backend: `Anim.pos_values` (valideres: én pr. position, stigende, endelige tal; ryddes uden *pr. værdi*), sendes som `params.pos_values`. Frontend: `posIndex()` i animate.ts bruges både til visning og til aktiv/passiv; ny linje *Tagets værdi → position* i trin 4; nye positioner forlænger fra-værdierne.
- `backend/app/services/symbols.py`, `frontend/src/lib/{animate.ts,symbolConfig.ts,SymbolGuide.svelte}`, manualen, tests (backend 1, frontend 3).

## [1.12.1 build 0221] — 2026-10-25 — PLC-login: tydelig besked og sjældnere genforsøg ved afvist login

- "Login afvist af PLC" forklarer nu, at PLC'en ikke godkender brugeren med den gemte adgangskode, og hvad man gør (tjek brugeren på PLC'en / sæt adgangskoden igen under PLC'er).
- Afvist login gentages kun hvert `auth_retry_s` (60 s) i stedet for hvert 1–10 s, så PLC'ens log og alarm for login-fejl ikke fyldes. Rettes adgangskoden, genstartes forbindelsen straks som før.
- `backend/app/plc/client.py`, `services/plc_runtime.py`, `mock_plc/app.py` (tæller også afviste login), test.

## [1.12.0 build 0220] — 2026-10-25 — Animationer: tag med positionens nummer ("pr. værdi")

- Jan: ved en 3-trins knap gav *symbolets position* de rigtige tre vinkler, men *et tag* kun min/max-drejning. Nyt: for symboler med positioner kan en animation styret af et tag sættes til **Pr. værdi** — tagets værdi (0, 1, 2 …) vælger da værdien pr. position (vinkel, farve, synlig, blink, flyt, løbelys …) som med kilden *symbolets position*.
- Backend: `Anim.by_value` (valideres som `@pos`: én værdi pr. position; kræver positioner; kun almindelige tags; ikke Værdi-teksten); bindingen får `params.pos`. Frontend: afkrydsning ved tag-valget i trin 4.
- `backend/app/services/symbols.py`, `frontend/src/lib/{symbolConfig.ts,SymbolGuide.svelte}`, manualen, test.

## [1.11.1 build 0219] — 2026-10-25 — fix: betjeningsform kan vælges tilbage i Opsæt symbol

- Trin 1: en betjeningsform man har haft valgt, bliver stående i listen (`opChoices`), så man kan skifte frem og tilbage mellem fx *Kun visning* og *Positioner*. `frontend/src/lib/{symbolConfig.ts,SymbolGuide.svelte}`, test.

## [1.11.0 build 0218] — 2026-10-25 — Symboler med positioner: venstre/højre-betjening på tegningen

- Ny indstilling i Opsæt symbol › trin 5 (*Betjening*) for symboler med positioner: **Dialog** (som hidtil) eller **Interaktiv** — tryk på symbolets venstre side for forrige position og højre side for næste. Stopper i enderne (besked). Bekræftelse og nøglelås gælder uændret (dialogen åbnes med den valgte position); hurtige tryk tæller videre fra den sidst bestilte position; ukendt vist position åbner dialogen. Musemarkøren bliver en venstre/højre-pil (`hv-step`).
- Backend: nyt felt `click` (`dialog`|`step`) i symbolopsætningen (standard `dialog`; nulstilles for symboler uden positioner), med i visningen og i backup. Ingen skemaændring (opsætningen er JSON).
- `backend/app/services/symbols.py`, `frontend/src/lib/{symbolConfig.ts,symbolUi.ts,SymbolGuide.svelte}`, `pages/Overview.svelte`, `app.css`, manualen, tests (backend 1, frontend 5). Ikke set i browser.

## [1.10.0 build 0217] — 2026-10-25 — Overview: beskeder i en fast plads, så tegningen ikke hopper

- Alle beskeder på Overview (PLC-fejl med Kvittér, serverforbindelse, deaktiveret tegning, forsvundne bindinger, fejl og bekræftelser) vises nu i en fast **pille** yderst til højre i værktøjslinjen i stedet for som bannere over tegningen. Pillen viser den alvorligste besked (+ antal); et tryk åbner en liste over alle oven på tegningen (lukkes med klik udenfor/Esc). Tegningen flytter sig derfor aldrig, når en besked kommer og går (før: den hoppede ned og op).
- Driftpanelet (uden værktøjslinje): pillen ligger øverst til højre over tegningen.
- `frontend/src/lib/{messages.ts,MessageSlot.svelte}` (nye), `pages/Overview.svelte`, manualen, test (3 nye). Ikke set i browser. Den globale mørke topbjælke er ikke brugt (den ejes af App-rammen) — kan flyttes dertil, hvis ønsket.

## [1.9.2 build 0216] — 2026-10-25 — fix: ST-variabel bundet som INPUT skrives via sit register

- Hører en ST-variabel til en input-binding (↔ Begge / Input) i PLC'en, skriver SCADA nu det bundne register (HR eller coil) i stedet for at vise PLC'ens afvisning. 32-bit skrives lav ord først. DI afvises tydeligt. Tilbagelæsning venter op til ca. 1,5 s på næste ST-cyklus; audit nævner registret.
- `backend/app/{plc/client.py,services/operate.py}`, `backend/mock_plc/app.py`, tests.

## [1.9.1 build 0215] — 2026-10-25 — fix: fejl ved sletning af tag i brug vises ved tagget

- Tags: afvist sletning vises som en rød linje under tagget (ikke kun øverst på siden). Serverens besked nævner nu tegningerne og antal bindinger. `frontend/src/pages/Tags.svelte`, `backend/app/{services/tags.py,storage/db.py}`, test.

## [1.9.0 build 0214] — 2026-10-25 — Overview: PLC-fejl kan kvitteres

- Røde PLC-bannere på Overview (fx *PLC …: kommunikation tabt*) har nu en knap **Kvittér**, så fejlen ikke står på hovedsiden hele tiden. En kvitteret fejl skjules, og der står en lille linje *Kvitterede PLC-fejl: … — vis igen*. Kvitteringen bortfalder, når PLC'en har været i orden igen, så en NY fejl vises igen.
- Gælder kun denne browserfane (sessionStorage) og ændrer intet på serveren — PLC-status, alarmer og badges i værktøjslinjen er uændrede.
- `frontend/src/lib/plcAck.ts` (ny), `frontend/src/pages/Overview.svelte`, test (3 nye).

## [1.8.3 build 0213] — 2026-10-25 — fix: Opsæt symbol-guiden er smallere og kræver ikke vandret rulning

- Guiden max 780 px (før 960); signal-tabellen i trin 2 med faste kolonner. `frontend/src/lib/SymbolGuide.svelte`.

## [1.8.2 build 0212] — 2026-10-25 — fix: netværksskift fra web afvistes ("fallback_after: ukendt felt")

- `NetworkBody` kender nu `fallback_after` (siden sender det altid). Regression siden v0.123.0: ingen netværksændring kunne anvendes fra System › Konfiguration.
- Ny API-test med frontendens fulde body i alle fire tilstande (fejler uden rettelsen).
- `backend/app/api/system_config.py`, `backend/tests/test_netconfig.py`.

## [1.8.1 build 0211] — 2026-10-25 — fix: signaler kan altid fjernes i Opsæt symbol

- Trin 2 (Signaler): ✕ er ikke længere slået fra ved det sidste signal; forklarende besked når der ingen er; bekræftelse hvis signalets kontaktplan har indhold.
- `frontend/src/lib/SymbolGuide.svelte`.

## [1.8.0 build 0210] — 2026-10-25 — Genstart fra web (SCADA-tjenesten eller maskinen)

- Ny sektion **Genstart** i System › Konfiguration (admin): *Genstart SCADA-tjenesten* og *Genstart maskinen* (fx efter skift til fast IP-adresse), med bekræftelse. Siden venter på serveren og genindlæser, når den svarer igen (op til 6 min.).
- Samme mønster som netværksopsætningen: tjenesten (ikke-privilegeret) lægger `power.request` i `<data>/config/`; en root-hjælper (`deploy/apply-power.sh`, udløst af `hypervisionplc-scada-power.path`) flytter den ind i sin egen mappe, afviser symlinks, ukendte handlinger og anmodninger ældre end 2 min., fjerner anmodningen FØR handlingen og udfører `systemctl restart hypervisionplc-scada` / `systemctl reboot` efter 3 s (så svaret når frem). Ingen værdi fra filen når et shell.
- `install.sh` installerer hjælperen og enhederne og sætter markøren `power-enabled`; på maskiner uden den (ikke opdateret endnu) viser siden en tydelig besked i stedet for knapper.
- API: `GET/POST /api/system/power` (admin, audit `system.power`); dobbelt-bestilling afvises (409).
- `deploy/{apply-power.sh,hypervisionplc-scada-power.path,hypervisionplc-scada-power.service,install.sh}`, `backend/app/services/power.py`, `api/system_power.py`, `main.py`, `frontend/src/pages/SystemConfig.svelte`, manualen, tests (4 nye + hjælperscriptet afprøvet med stub). Symlink-afvisningen kunne ikke afprøves på Windows.

## [1.7.0 build 0209] — 2026-10-24 — ST-variabler kan skrives (kræver PLC-firmware v7.9.68.141)

- Tags på ST-variabler (`plcN:logic:<prog>:<var>`) og GLOBAL_VAR (`plcN:global:<var>`) kan nu være skrivbare. Setpunkt, trykknap, til/fra-skift, symbolpositioner og ugeprogrammer bruger dem som almindelige tags. Skrivningen går via PLC'ens nye `POST /api/logic/{id}/var` og `POST /api/logic/globals/var` (HypervisionPLC FEAT-503, v7.9.68.141), og tilbagelæsning sker fra variabellisten.
- PLC'en konverterer og tjekker værdien efter variablens type; dens afvisninger (område, STRING, variabel bundet som INPUT, ukendt navn) vises ordret. Ældre firmware (endpointet findes ikke) giver beskeden "PLC-firmwaren kan ikke skrive ST-variabler — opdatér PLC'en til v7.9.68.141 eller nyere".
- Mock-PLC'en har de to nye endpoints (og kan efterligne ældre firmware og INPUT-bundne variabler).
- `backend/app/plc/client.py`, `services/{operate,tags,symbols}.py`, `mock_plc/app.py`, `frontend/src/pages/Tags.svelte`, manualen, tests (3 nye).

## [1.6.1 build 0208] — 2026-10-24 — fix: tag-navne skæres ikke over i tag-dropdownen

- `TagSelect`: det valgte tag vises med fuldt navn (uden kilde/enhed) i det lukkede felt; detaljer i tooltip og den åbne liste. Maks-bredden i symbolguiden, gruppernes animationer og animationsparametre hævet fra 15em til 24em.
- `frontend/src/lib/{TagSelect,AnimParams,GroupAnims,SymbolGuide}.svelte`.

## [1.6.0 build 0207] — 2026-10-24 — Tegninger kan deaktiveres (offline)

- Under **Tegninger** kan en tegning sættes i **deaktiveret** tilstand (knappen *Deaktivér* / *Aktivér*, teknikere og admin): den er offline — Overview viser den grå med beskeden *Tegningen er deaktiveret*, uden live-data, bindinger, genveje og betjening. Bevares i backup.
- Server: operatører (og panel) kan ikke længere betjene via en deaktiveret tegning (`scope._operator_bindings`), symbolpositioner kan ikke betjenes (`symbol_operate`), og symbol-runtime springer deaktiverede tegninger over (ingen positioner, ingen afvigelsesalarmer).
- Polling: tags, som KUN deaktiverede tegninger bruger, pollas ikke (`services/drawing_activity.suspended_tags`, `manager.reload_tags`); deres live-værdi står som *ukendt*. Tags med alarm, trend, energi eller ugeprogram pollas som før — alarmer slås bevidst aldrig fra bare fordi en tegning er skjult (afvigelse fra den første beskrivelse: "alarmer slås fra").
- Database: ny kolonne `drawings.disabled` (tilføjes automatisk, `ALTER TABLE`); backup/gendannelse bærer flaget.
- `backend/app/storage/db.py`, `services/{drawings,drawing_activity (ny),manager,scope,symbol_operate,symbol_runtime,backup}.py`, `api/drawings.py`, `main.py`, `frontend/src/pages/{Drawings,Overview}.svelte`, `lib/api.ts`, manualen, tests (4 nye).

## [1.5.0 build 0206] — 2026-10-24 — Brugte farver som hurtigvalg ved farvefelterne

- Ved hvert farvefelt i **Opsæt symbol** (Til/Fra, grænser, blafrer, løbelys …) og i gruppernes animationer vises nu små farveknapper med de farver, der allerede bruges: først animationernes egne, så symbolets tegnede farver (mest brugte først), så tegningens øvrige (højst 10). Ét klik vælger farven; den almindelige farvevælger er der stadig, og den aktuelle farve er markeret.
- Farverne hentes fra tegningens SVG (`GET /api/drawings/{id}/svg`) og fra animationernes parametre. Genbruger `svgedit-host/colors.js` (normalisering af farver).
- `frontend/src/lib/{usedColors.ts (ny),AnimParams,SymbolGuide,GroupAnims}`, test.

## [1.4.1 build 0205] — 2026-10-24 — fix: ét langsomt PLC-kald tager ikke længere hele PLC'en ned

- `plc_runtime.poll_once`: hvert kald (register-område, ST-program, GLOBAL_VAR, ekstern slave) kører isoleret (`_guarded`). Fejler ét, får kun dets tags `comm_error`; resten opdateres normalt. Fejlende kald hviler 2→20 s (`COOL_STEP_S`/`COOL_MAX_S`) i stedet for at blive gentaget hver cyklus. Login-/rettigheds-/rate-fejl (401/403/429) rammer fortsat alt. Fejler *alle* kald, er det en fuld kommunikationsfejl som før.
- Status: `partial` (kald der fejlede i cyklussen) og `slowest` (største svartider) i `/api/plcs`; PLC-siden viser *Delvis kommunikationsfejl* og *Langsomste kald*.
- `backend/app/services/{plc_runtime,manager}.py`, `frontend/src/pages/Plcs.svelte`, tests (3 nye).

## [1.4.0 build 0204] — 2026-10-24 — Fast værdi som kilde til tal-animationer

- Ny kilde **en fast værdi** (`@val:75`) ved siden af *et tag*, *en alarm*, *altid til* og *en logikblok*: tal-animationerne **Niveau, Gennemsigtighed, Størrelse, Drej og Flyt** kan styres af et tal, der indtastes direkte, og som animationen bruger som om et tag havde værdien. Virker i symbolguiden og i gruppernes animationer (også fanen *Alle medlemmer*).
- En fast værdi er ikke et tag: ingen live-abonnement, ingen tag-meta, ingen adgangs-/slettekontrol, ingen kommunikationsfejl. Serveren validerer: kun tal (ikke NaN/uendelig), og kun for de fem tal-typer (Farve/Blink/Synlig/Roterer/Blafrer/Løbelys har allerede *altid til*; *Værdi* vises ikke med fast værdi).
- Skifter man animationstype til en, der ikke kan bruge en fast værdi, nulstilles kilden.
- Ikke med (bevidst): Bindinger-siden (gamle pr.-element-bindinger) og *Værdi*-teksten.
- `backend/app/services/symbols.py`, `bindings.py`, `frontend/src/lib/{symbolConfig.ts,canvas.ts,SymbolGuide,GroupAnims,OwnerAnims}`, manualen, tests (4 nye backend/frontend).

## [1.3.0 build 0203] — 2026-10-24 — Opsæt de valgte samlet: fjern konfiguration fra alle

- Når flere symboler er valgt til **Opsæt de valgte samlet**, kan opsætningen nu fjernes fra alle på én gang (knappen **Fjern konfiguration fra alle**), ligesom for ét symbol. Alt eller intet: bruger et symbol, der ikke fjernes, en logikblok i et af de valgte (eller en gruppe-animation), afvises hele fjernelsen med besked. Symboler uden opsætning springes over.
- Backend: `POST /api/drawings/{id}/symbols/delete-configs` (ENGINEER, audit-log).
- `backend/app/services/symbols.py`, `api/symbols.py`, `frontend/src/lib/SymbolGuide.svelte`, `pages/DrawEditor.svelte`, test.

## [1.2.0 build 0202] — 2026-10-23 — Animationer for gruppen: samme animation på alle medlemmer

- I **Animationer for gruppen** er der en ny fane **Alle medlemmer**: vælg animationerne én gang og anvend dem på alle gruppens symboler — tilføjet til symbolernes egne gruppe-animationer eller som erstatning. Anvendes på *Hele symbolet* (dele hedder forskelligt fra symbol til symbol, så dem sættes op pr. symbol). Hvert symbol valideres for sig; valgfrit springes symboler over, hvor animationen ikke kan bruges (fx Niveau på et symbol uden rektangel), og de meldes. Uden "spring over" gemmes intet, hvis ét fejler.
- Backend: `POST /api/drawings/{id}/groups/{gid}/anims` (ENGINEER, audit-log); loft på 12 animationer pr. symbol gælder.
- `backend/app/services/symbol_groups.py`, `api/symbol_groups.py`, `frontend/src/lib/{GroupAnims.svelte,symbolGroups.ts}`, manualen, tests (3 nye).

## [1.1.0 build 0201] — 2026-10-23 — Opsæt symbol viser symbolets grupper

- Under overskriften i symbolguiden står de grupper, symbolet er medlem af (i gruppens farve, med art som tooltip), eller "Ikke medlem af nogen gruppe".
- `frontend/src/lib/SymbolGuide.svelte`.

## [1.0.1 build 0200] — 2026-10-23 — fix: typetjek (svelte-check) er rent

- `expanded` i Trends flyttet efter `groups`, som den bruger (2 typefejl fra v0.117.0). Ingen ændring i opførsel.
- `frontend/src/pages/Trends.svelte`.

## [1.0.0 build 0199] — 2026-10-23 — MAJOR-bump: skema-migration (symbolgrupper)

- Ingen kodeændring ud over versionsnummeret. Efter Jans afgørelse regnes databaseudvidelsen fra symbolgrupperne (skema 11 → 13, tre nye tabeller i 0.130.0 og 0.131.0) som skema-migration, og CLAUDE.md kræver MAJOR ved skema-migration. De to tidligere udgivelser fik fejlagtigt kun MINOR-bump; historikken omskrives ikke, men fra nu gælder 1.0.0.
- Opdatering fra ≤ 0.129.x opretter tabellerne automatisk (`CREATE TABLE IF NOT EXISTS`); tag en backup først (database kan ikke rulles tilbage til en ældre version uden backup).
- `version.json`.

## [0.131.4 build 0198] — 2026-10-23 — Symbolgrupper: resten af design-review 2
- Dialogen for gruppe-animationer: ingen race mellem symboler (token + spærrede faner), Escape lukker, almindelige knapper med `aria-pressed`.
- Gem af gruppe-animationer kræver medlemskab i selve skrivningen (409 hvis medlemmet er fjernet imens).
- Rækkefølge: funktionsgrupper tæller før udvalg (SQL), tooltip forklarer kæden.
- Gruppenavne unikke uden hensyn til store/små bogstaver; backup tjekker `MAX_GROUPS` og dublet-navne.
- Tests: atomar skrivning, navne/rækkefølge, egne logikblokke afvises, restore-grænser. BUGS.md opdateret (se også åben rest: versionering, cache, backup-validering).
- `backend/app/storage/db.py`, `services/{symbol_groups,backup}.py`, `frontend/src/lib/{GroupAnims,SymbolGroups}.svelte`, tests.

## [0.131.3 build 0197] — 2026-10-23 — fix: regression i vinderreglen + dele ved flyt af gruppemedlemmer

- **Regression (v0.131.2):** uden "passiv" vandt altid den sidste binding, uanset værdier — også i eksisterende tegninger (fx fælles rør med løbelys fra to pumper stod stille, når kun den første kørte). Nu vinder den sidste *aktive* (som et "eller" mellem kilderne); er ingen aktive, vises den sidstes fra-tilstand. Test for første-aktiv/sidste-inaktiv.
- Flyt af forsvundne gruppemedlemmer (og symbol-flyt) oversætter nu delene (`kilde_del` → `mål_del`), dropper animationer på dele der ikke findes og melder det; kasserede animationer ved sammenfald (målet var allerede medlem) meldes også. Tests.
- `frontend/src/lib/canvas.ts`, `backend/app/storage/db.py`, `services/{symbols,symbol_groups}.py`, `frontend/src/pages/Editor.svelte`, `symbolGroups.ts`, tests.

## [0.131.2 build 0196] — 2026-10-23 — Symbolgrupper: resten af design-reviewet

- **Samtidig redigering:** tilføj/fjern medlemmer sender kun de valgte (`POST …/groups/{id}/members`, atomart) — et forældet faneblad kan ikke længere overskrive en kollegas medlemmer og animationer.
- **Ydelse:** `_group_bindings` læser tegningen én gang (`subtree_map`) i stedet for én gang pr. række.
- **Vinder ved overlap:** Overview/Bindinger tegner nu hele del+slags-gruppen om, når flere tags styrer samme del, så den sidste i rækkefølgen altid vinder (før: det tag der sidst ændrede sig). Gruppernes rækkefølge kan ses og ændres (▲▼, `POST …/groups/order`). Gem af gruppe-animationer giver advarsler om overlap med symbolets egne og andre gruppers.
- **Forsvundne medlemmer:** Bindinger kan flytte et forsvundet medlem til det element, der overtog pladsen (gruppe-animationer følger med) eller fjerne det; flytning af en symbolopsætning (`/symbols/{id}/move`) tager gruppernes medlemskab med. Dialogen advarer om animationer på dele, der ikke findes.
- Tests: delta-medlemmer, flyt, rækkefølge, overlap-advarsler, operatør kan ikke redigere, begrænset bruger ser gruppe-tags, symbol-flyt, vinder ved delvis gentegning.
- Ikke gjort (bevidst): backup validerer fortsat ikke dele/logik-henvisninger i gruppe-animationer; `_compute` er ikke cachet (kun den dyreste gentagelse er fjernet).
- `backend/app/storage/db.py`, `services/{symbol_groups,symbols,drawings,svg_sanitize}.py`, `api/symbol_groups.py`, `frontend/src/lib/{canvas,symbolGroups,SymbolGroups,GroupAnims}`, `pages/Editor.svelte`, tests.

## [0.131.1 build 0195] — 2026-10-23 — fix: symbolgrupper efter design-review

- `used_ids` reserverer nu også gruppemedlemmer, så et nyt element ikke kan få et gammelt medlems id og arve gruppens medlemskab og animationer.
- En logikblok, som en gruppe-animation på et andet symbol henviser til, kan ikke længere fjernes/overskrives uden besked (fejlen nævner gruppen).
- Resten af reviewets punkter står i PLAN.md.
- `backend/app/services/symbols.py`, `backend/tests/test_symbol_groups.py`.

## [0.131.0 build 0194] — 2026-10-23 — Symbolgrupper del 2: animationer ejet af gruppen + farvemarkering

- En gruppe kan få egne animationer på hvert af sine symboler (**⋯ › Animationer …** i Tegn, eller **Animationer for gruppen …** i Bindinger). De gælder ud over symbolets egne og andre gruppers (rør i flere grupper = egen opsætning + én pr. gruppe). Rækkefølge: symbolets egne, derefter grupperne i deres rækkefølge; den eksisterende prioritetsregel afgør samme slags på samme del.
- Farvemarkering: hver gruppe har en farve; dialogen og symbolguiden (trin 4) viser andre ejeres animationer skrivebeskyttet i deres farve med gruppens navn, symbolets egne neutralt.
- Backend: ny tabel `symbol_group_anims` (skema 13); `PUT/GET /api/drawings/{id}/groups/{gid}/anims[/{element}]`, `GET …/symbols/{element}/group-anims`; samme validering som symbolets egne animationer (visning uden positioner); fjernes et medlem, fjernes dets animationer; tags i gruppe-animationer tæller med i tag-sletning (409), adgang pr. tegning og backup/gendannelse (valideres).
- Visningen (`/view`) får bindinger med `source: "group"`, `group`, `group_name`.
- Frontend: `AnimParams.svelte` udtrukket fra symbolguiden (ingen funktionsændring), `GroupAnims.svelte`, `OwnerAnims.svelte`.
- `backend/app/storage/db.py`, `services/symbol_groups.py`, `services/symbols.py`, `services/drawings.py`, `services/backup.py`, `api/symbol_groups.py`, `main.py`, `frontend/src/lib/{AnimParams,GroupAnims,OwnerAnims,SymbolGroups,SymbolGuide}.svelte`, `symbolGroups.ts`, `api.ts`, `pages/Editor.svelte`, manualen, tests.

## [0.130.0 build 0193] — 2026-10-23 — Navngivne symbolgrupper (del 1: grupper som valg og markering)

- Ny sektion **Grupper** i Tegn: gem de valgte symboler som en navngiven gruppe (art: funktionsgruppe eller udvalg), markér alle dens symboler med ét klik, tilføj/fjern/sæt til valgte, omdøb, skift art, slet. Samme symbol kan være med i flere grupper (overlap).
- Bindinger: vælg en gruppe over symbollisten for kun at se dens symboler (viser hvis medlemmer er forsvundet).
- Backend: nye tabeller `symbol_groups` og `symbol_group_members` (skema 12), REST `/api/drawings/{id}/groups` (læs viewer, skriv engineer, audit-log), med i backup/gendannelse (ældre backups uden grupper virker). Grupper følger tegningen ved sletning.
- Del 2 (animationer ejet af gruppen + farvemarkering i symbolguiden) er planlagt, se PLAN.md.
- `backend/app/storage/db.py`, `backend/app/services/symbol_groups.py` (ny), `backend/app/services/backup.py`, `backend/app/api/symbol_groups.py` (ny), `backend/app/main.py`, `frontend/src/lib/symbolGroups.ts` (ny), `frontend/src/lib/SymbolGroups.svelte` (ny), `frontend/src/pages/DrawEditor.svelte`, `frontend/src/pages/Editor.svelte`, manualen, tests.

## [0.129.1 build 0191, rettet i 0192] — 2026-10-23 — fix: rullepaneler altid synlige i Tegn

- Tegnefladen (`#workarea`) har nu `overflow: scroll` og tydelige rullepaneler (14 px, mørk grib på lys bane), så de ikke skjules af systemets auto-skjulte rullepaneler.
- `frontend/svgedit-host/scada-editor.css`.

## [0.129.0 build 0190] — 2026-10-23 — Animationer: coil kan bruges hvor der krævedes et register

- Niveau, Gennemsigtighed og Størrelse (og Drej/Flyt) kan nu styres af et coil/til-fra-tag: Fra = 0, Til = 100. Serveren afviser det ikke længere; standardområdet for coil er 0–100 (før 0–1).
- Ændring: i `fraction` (animate.ts) tæller et boolsk tag som 0/100. Eksisterende opsætninger med max 1 virker uændret (værdien klippes til 100 %); en bruger-sat max over 1 på et coil giver nu fuld udslag ved Til.
- `backend/app/services/symbols.py`, `frontend/src/lib/animate.ts`, `frontend/src/lib/symbolConfig.ts`, tests.

## [0.128.0 build 0189] — 2026-10-23 — Opsæt symbol: dialogen kan flyttes

- Symbolguidens dialog kan trækkes rundt på skærmen i overskriften (mus og touch), holdt inden for skærmen.
- `frontend/src/lib/SymbolGuide.svelte`.

## [0.127.0 build 0188] — 2026-10-23 — Bindinger: valgt element markeres lysegrønt og gennemsigtigt

- Det valgte symbol/element i Bindinger markeres på tegningen med lysegrøn kant og gennemsigtig grøn fyld (før blå).
- `frontend/src/pages/Editor.svelte`.

## [0.126.1 build 0187] — 2026-10-23 — fix: animationer virker også med "Reducer bevægelse" (iOS)

- Rod­årsag: `prefers-reduced-motion` slog rotation, blafren, blink, løbelys og alarmblink fra på enheder med tilgængelighedsindstillingen slået til (iOS). Procesanimationerne viser anlæggets tilstand og kører nu altid.
- `frontend/src/app.css`, `frontend/src/App.svelte`, `frontend/src/lib/animate.ts`.

## [0.126.0 build 0186] — 2026-10-23 — Driftpanel: tegningen fylder hele skærmen

- Den smalle sidekolonne (8,5 rem) er fjernet. Log ud, tegningsvalg og "Ingen forbindelse" flyder som små knapper øverst til venstre over tegningen; AGPL-kildelinket står nederst til venstre.
- `frontend/src/pages/Overview.svelte`.

## [0.125.1 build 0185] — 2026-10-22 — fix: netværkssystem og DHCP-klient registreres løbende

- Fund ved test på serveren: `install.sh` ligger kun i opdateringspakken (ikke på serveren), så vejledningen "kør install.sh --update" kunne ikke følges, og en `apt install dhcpcd-base` bagefter slog ikke igennem før næste opdatering.
- `deploy/net-detect.sh` (ny, root) — finder netværkssystem (`nm` / `ifupdown` / `none`) og DHCP-klient og skriver `capabilities` + markører. Køres af `install.sh` og nu også af DHCP-vagtens timer (`ExecStartPre`, hvert 30. s), så siden opdaterer sig selv, og timeren altid er slået til.
- Tekster i siden/vejledningerne rettet (ingen henvisning til `install.sh` på serveren).
- `backend/tests/test_netdetect.py` (ny, 5 tests).

## [0.125.0 build 0184] — 2026-10-22 — Netværk: ifupdown-understøttelse (Debian/Ubuntu-servere, ESXi-VM'er)

- Baggrund: testserveren er en Debian 13-VM med `ifupdown` (ingen NetworkManager, ingen sudo, ingen DHCP-klient) — netværksopsætning via web var derfor slået fra (`no-nmcli`).
- `deploy/apply-config.sh` — ny ifupdown-gren: anvender via `ifdown --force -i <gammel>` + `ifup -i <ny fil>` UDEN at røre `/etc/network/interfaces`; skriver filen varigt (atomisk, sikkerhedskopi, 3 beholdes) + DNS i en almindelig `resolv.conf` + værtsnavn (inkl. `/etc/hosts`) først ved bekræftelse; fortryd/timeout/død proces → den gamle fil gælder (`ifup -i`/`--recover`). Kun netkortets `iface`-blok i hovedfilen omskrives (awk); står den andetsteds, afvises ændringen. Afviser DHCP uden DHCP-klient.
- `deploy/net-watchdog.sh` — ifupdown-gren med iproute2 (lease = adresse med flaget `dynamic`; reserve-IP via `ip addr add/del`, standardrute kun hvis ingen).
- `deploy/install.sh` — finder netværkssystem (`nm` / `ifupdown` / `none`) og DHCP-klient → `capabilities`; `no-backend` i stedet for `no-nmcli`. `hypervisionplc-scada-config.service` — skriverettigheder til `/etc/network` m.m.
- `backend/app/services/netconfig.py`, `frontend/src/pages/SystemConfig.svelte` — `capabilities` (backend, dhcp_available), afvisning af DHCP uden klient, DHCP-valg slået fra i UI, præcis besked ved ikke-understøttet system.
- **Efter review (agent):** `ifup`/`ifdown` køres via `systemd-run` i en egen enhed (`KillMode=process`), så DHCP-klienten ikke dræbes og ikke ligger i tjenestens sandkasse; DNS og `/etc/hosts` skrives uden temp-filer i `/etc` (ProtectSystem=strict) og uden sed-regex (ingen injektion via det gamle værtsnavn); netværksfiler med CRLF, indrykkede nøgleord eller ukendte linjer afvises i stedet for at blive ødelagt; relative `source`-stier gøres absolutte; præcis netkort-sammenligning (ikke regex) og navnet må ikke starte med `-`; sikkerhedskopi-oprydning virker (find i stedet for glob under `set -f`); `ifupdown.state` fjernes straks efter varig skrivning; DHCP-vagten ignorerer en gammel status fra en død ændring, nulstiller sin tilstand efter genstart (boot_id) og er idempotent over for en manglende reserve-adresse; ifupdown kræver **dhcpcd** (dhclient kører med `-1`, udhcpc giver ingen levetid).
- `backend/tests/test_ifupdown.py` (ny, 24 tests) — stanzaer pr. tilstand, omskrivning bevarer øvrige netkort/kommentarer/source, urørt under ventetid, varig skrivning + DNS + værtsnavn, fortryd, ifup-fejl, DHCP uden klient, symlink-resolv.conf, recover, vagten.
- Hele backend-suiten (593 tests) er kørt på testserveren (Debian 13, dash) og består; ifupdown-forløbet er desuden kørt mod serverens rigtige `/etc/network/interfaces` med falske ifup/ifdown.
- Manual (System), `docs/TEST_PI.md` (ESXi-/ifupdown-afsnit).

## [0.124.0 build 0183] — 2026-10-22 — scada-maint: oprydning ved fuld disk

- `backend/app/maint.py` (ny) + `deploy/scada-maint.sh` (installeres som `/usr/local/sbin/scada-maint`) — kommandolinjeværktøj: `status`, `logs`, `backups`, `trends`, `history`, `trends-reset`, `emergency`. Tørkørsel som standard (`--yes` for at udføre), kræver root, logger til systemloggen, rører aldrig tags/brugere/tegninger/bindinger. `--shrink` (VACUUM) afvises uden nok plads; `emergency` stopper, når der er plads nok.
- `frontend/src/pages/SystemConfig.svelte` — advarsel ved lav ledig plads (< 5 % eller < 200 MB) med henvisning til værktøjet; manual (System), `docs/TEST_PI.md` (6b).
- `backend/tests/test_maint.py` (ny); `backend/tests/test_netconfig.py` — API-testen er nu uafhængig af maskinens netkort (fejl fundet ved kørsel på Linux).
- Hele backend-suiten (568 tests) er kørt på testserveren (Debian 13, dash, Python 3.13) og består.

## [0.123.0 build 0182] — 2026-10-22 — System › Konfiguration (trin 4: DHCP-vagt og reserve-IP) + testvejledning

- `deploy/net-watchdog.sh` (ny, root) + `hypervisionplc-scada-netwatch.{service,timer}` + `install.sh` — tæller kontroller uden DHCP-svar; i tilstanden *DHCP, fast IP efter N fejl* lægges reserve-IP'en på midlertidigt (`--temporary` + `device reapply`) efter N og fjernes igen ved lease; tæller ikke når kablet er ude; rører ikke netværket under en ændring; status i `watchdog.json`.
- `deploy/apply-config.sh` — tilstanden `dhcp_fallback` (profilen er ren DHCP), `FALLBACK_AFTER`, og skriver `watchdog.conf` først efter bekræftelse.
- `backend/app/services/netconfig.py` — ny tilstand + `fallback_after` (1–20), `disabled_reason` (`no_nmcli` / `not_installed`), vagtens status i `GET /network`.
- `frontend/src/pages/SystemConfig.svelte` — ny tilstand, N-felt, vagtens status, og en præcis besked om hvorfor netværksændring ikke er aktiveret (NetworkManager mangler / install.sh ikke kørt).
- `docs/TEST_PI.md` (ny) — samlet testvejledning for trin 1–5 på en rigtig Pi; `.gitattributes`, manual (System), `PLAN.md`.
- `backend/tests/test_netwatch.py` + udvidede `test_netconfig.py` — vagten med falsk nmcli (tælling, reserve-IP, fjernelse, kabel ude, ændring i gang, ugyldig konfiguration).
- Kun testet mod falsk nmcli — **ikke afprøvet på en rigtig Pi**.

## [0.122.0 build 0181] — 2026-10-22 — System › Konfiguration (trin 5: flyt trend-databasen)

- `backend/app/storage/trends_db.py` — `relocate()`: konsistent kopi (backup-API) under låsen, kontrol (quick_check + antal rækker), skift af forbindelse; den gamle fil gemmes som `.moved`; fejl efterlader den gamle database uændret.
- `backend/app/services/sysconfig.py` — `validate_trend_dir` (kun under /mnt eller /media, anden disk, skrivbar, plads, ingen eksisterende trends.db), `resolve_trend_db_path` (opstart: manglende disk → tom database i datamappen + advarsel), `save_section`.
- `backend/app/api/system_config.py`, `backend/app/main.py` — `PUT /api/system/config/storage` (admin, auditlogget, én flytning ad gangen); placering og advarsel i `GET`.
- `deploy/hypervisionplc-scada.service` — `ReadWritePaths` udvidet med `-/mnt -/media`.
- `frontend/src/pages/SystemConfig.svelte`, manual (System); `PLAN.md` (ændret afgrænsning af trin 5).
- `backend/tests/test_trend_storage.py` — flytning frem/tilbage, afvisning, validering, opstart uden disk.
- Kun testet; **ikke afprøvet med en rigtig USB-disk** og ikke set i browser.

## [0.121.0 build 0180] — 2026-10-22 — System › Konfiguration (trin 3: netværk)

- `deploy/apply-config.sh` (ny, root) + `hypervisionplc-scada-config.{path,service}` + `install.sh` — anvender en netværksændring med NetworkManager: validerer igen, anvender **midlertidigt** (`--temporary`), venter 90 s på bekræftelse og gør den først varig ved bekræftelse; ellers (eller ved fejl, *Fortryd nu*, genstart, dødt script via `ExecStopPost --recover`) vender den gamle opsætning tilbage. Efter reviewer-gennemgang: root skriver kun i sin egen mappe `/var/lib/hypervisionplc-scada-net` (status/log), anmodningen tages ind med `mv` og symlinks afvises, nmcli-kald har tidsgrænse, `CONFIRM_S` begrænses 20–180, værtsnavn sættes først efter bekræftelse, hærdet service-enhed.
- `backend/app/services/netconfig.py` (ny), `backend/app/api/system_config.py`, `backend/app/main.py`, `backend/app/config.py` (`SCADA_NET_STATE_DIR`) — validering (IP, subnet, gateway i subnettet, DNS, værtsnavn, netkort), `network.request` til hjælperen, tilstandsmaskine (bekræft/fortryd kun når der venter en ændring), endpoints `GET/PUT /network`, `POST /network/confirm|revert` (admin, auditlogget).
- `frontend/src/pages/SystemConfig.svelte` — formular, nedtælling, Bekræft / Fortryd nu; manual (System); `.gitattributes` (LF for .path).
- `backend/tests/test_netconfig.py` — validering, tilstandsmaskine, API-rettigheder og hjælpescriptet med en falsk `nmcli` (bekræftet, fortrudt, afvist, ugyldigt input, manglende profil).
- Kun testet mod en falsk nmcli — **ikke afprøvet på en rigtig Pi** og ikke set i browser.

## [0.120.0 build 0179] — 2026-10-22 — System › Konfiguration (trin 2: trend-indstillinger)

- `backend/app/services/sysconfig.py`, `backend/app/api/system_config.py`, `backend/app/main.py` — `PUT /api/system/config/trends` (admin): opbevaring, skriveinterval, energi-opbevaring; valideres (grænser, energi ≥ historik), gemmes atomisk i `<data>/config/settings.json` (andre afsnit bevares), gælder straks og ved opstart (overstyrer `SCADA_TREND_*`), auditlogges.
- `frontend/src/pages/SystemConfig.svelte` — formular med Gem/Fortryd; manual (System).
- `backend/tests/test_system_config.py` — validering, gem/indlæs/ødelagt fil, bevarelse af andre afsnit, rettigheder, live-effekt og efter genstart.
- Kun bygget og testet, ikke set i browser.

## [0.119.0 build 0178] — 2026-10-22 — System › Konfiguration (trin 1: visning)

- `backend/app/services/sysconfig.py`, `backend/app/api/system_config.py` (nye), `backend/app/main.py` — `GET /api/system/config` (kun admin): datasti, filstørrelser, ledig plads, trend-indstillinger, netværksstatus (`ip -j`, DNS fra resolv.conf). Kun læsning.
- `backend/app/services/trends.py` — skrivemåling: rækker/skrivninger siden start og overslag pr. døgn (`write_stats`).
- `frontend/src/pages/SystemConfig.svelte`, `lib/nav.ts`, `App.svelte` — ny side *System › Konfiguration*.
- `backend/tests/test_system_config.py`, `nav.test.ts`; manual (System), `PLAN.md`, `FEATURES.md`.
- Kun visning — intet ændres på systemet. Kun bygget og testet, ikke set i browser.

## [0.118.1 build 0177] — 2026-10-22 — fix: falske huller i Trends (stabile værdier)

- `frontend/src/lib/trendAnalysis.ts` + test — `DATA_STALE_S` (900 s): et tidshul er først et hul efter 3 × "jeg lever"-intervallet; gælder både *Udfyld huller* og analysens *Hul i data*. Serveren gemmer kun ved ændring, så pauser på op til 5 min er normale.
- `BUGS.md` — rodårsag og hvad der ikke er afgjort.
- Kun frontend. Kun bygget og testet (653 tests).

## [0.118.0 build 0176] — 2026-10-22 — Trends: fjern graf med kryds

- `frontend/src/lib/TrendChart.svelte` — kryds (×) i grafens øverste højre hjørne (prop `onclose`).
- `frontend/src/pages/Trends.svelte` — `removeGroup`: fravælger grafens tags, så grafen forsvinder.
- Kun frontend. Kun bygget og testet (651 tests), ikke set i browser.

## [0.117.0 build 0175] — 2026-10-22 — Trends: dobbeltklik giver graf i fuld størrelse

- `frontend/src/pages/Trends.svelte` — dobbeltklik på en graf viser kun den, i fuld højde (dobbeltklik igen eller Esc: tilbage). Hjælpeteksten er opdateret.
- `frontend/src/lib/TrendChart.svelte` — props `expanded` og `ondblclick`; dobbeltklik zoomer ikke længere ud (det gør *Nulstil visning*).
- Kun frontend. Kun bygget og testet (651 tests), ikke set i browser.

## [0.116.0 build 0174] — 2026-10-22 — Trends: udfyld huller (blinker) og dato ved døgnskift

- `frontend/src/lib/trendAnalysis.ts` + test — `fillGaps`: null-rækker mellem gyldige værdier og tidshuller (> 4 × typisk afstand, højst 200 punkter pr. hul) udfyldes lineært med kunstige punkter; ingen ekstrapolation; rådata uændrede.
- `frontend/src/lib/TrendChart.svelte` — kunstige strækninger tegnes tykke og stiplede og blinker (700 ms); dato (DD.MM.ÅÅÅÅ) står ved hvert døgnskift i grafen, uafhængigt af skillelinjer.
- `frontend/src/pages/Trends.svelte` — tilvalg *Udfyld huller (blinker)* (huskes).
- Kun frontend. Kun bygget og testet (651 tests), ikke set i browser.

## [0.115.2 build 0173] — 2026-10-22 — fix: Trends-grafer får tagnavne som titel

- `frontend/src/pages/Trends.svelte` — grafens titel er nu kurvernes navne (tagget's navn-parameter, ellers tag-navnet) plus enheden, i stedet for kun enheden / "Graf N".
- `frontend/src/lib/TrendChart.svelte` — titlen på én linje med "…" ved overlængde (fuld tekst ved hover).
- Kun frontend. Kun bygget og testet (647 tests), ikke set i browser.

## [0.115.1 build 0172] — 2026-10-22 — Trends: uregelmæssigheder som overlay

- `frontend/src/pages/Trends.svelte` — oversigten *Uregelmæssigheder* er flyttet ud af venstre panel og vises nu som et overlay oven på skærmen (knap i værktøjslinjen, vises med *Analysér data*; lukkes med ×).
- Kun frontend. Kun bygget og testet (647 tests), ikke set i browser.

## [0.115.0 build 0171] — 2026-10-22 — Trends: skillelinjer pr. time/dag

- `frontend/src/lib/trendData.ts` + test — `dividerTimes` (hele timer/dage i lokal tid; ingen linjer ved over 400).
- `frontend/src/lib/TrendChart.svelte` — stiplede lodrette linjer bag kurverne (prop `divider`).
- `frontend/src/pages/Trends.svelte` — vælger *Skillelinjer: Fra / Pr. time / Pr. dag* i værktøjslinjen (huskes).
- Kun frontend. Kun bygget og testet (647 tests), ikke set i browser.

## [0.114.1 build 0170] — 2026-10-22 — Trends: uregelmæssigheder i venstre side

- `frontend/src/pages/Trends.svelte` — oversigten *Uregelmæssigheder* flyttet fra under graferne til panelet i venstre side (under tag-listen), så graferne får mere plads.
- Kun frontend. Kun bygget og testet (644 tests), ikke set i browser.

## [0.114.0 build 0169] — 2026-10-22 — Trends: vælg selv hvilken graf et tag vises i

- `frontend/src/lib/trendData.ts` + test — `groupTags`: tags uden valg grupperes pr. enhed (som før), tags med grafnummer samles i *Graf N*.
- `frontend/src/pages/Trends.svelte` — vælger *Auto / Graf 1–8* ud for hvert valgt tag (huskes i browseren), fælles y-enhed kun hvis alle kurver i grafen har samme.
- Kun frontend. Kun bygget og testet (644 tests), ikke set i browser.

## [0.113.1 build 0168] — 2026-10-22 — fix: Trends-legend hopper ikke ved musebevægelse

- `frontend/src/lib/TrendChart.svelte` — legend-aflæsningerne har fast bredde (tabulære tal, ingen ombrydning), så de ikke skifter størrelse når markøren glider hen over grafen.
- Kun frontend. Kun bygget, ikke set i browser.

## [0.113.0 build 0167] — 2026-10-22 — Trends: lås graferne sammen og nulstil visning

- `frontend/src/lib/TrendChart.svelte` — nye props `linked`/`view`/`onview`/`resetTick`: når grafer er låst sammen, følger alle det udsnit, brugeren zoomer/scroller til i én graf; `resetTick` zoomer ud til hele perioden.
- `frontend/src/pages/Trends.svelte` — knapperne *Lås graferne sammen* og *Nulstil visning* + hjælpetekst.
- Kun frontend. Kun bygget og testet (641 tests), ikke set i browser.

## [0.112.0 build 0166] — 2026-10-22 — Trends: scroll i tid når der er zoomet

- `frontend/src/lib/TrendChart.svelte` — når en graf er zoomet ind, flytter musehjulet (eller Shift+træk) udsnittet i tid, begrænset til den valgte periode.
- `frontend/src/pages/Trends.svelte` — hjælpetekst.
- Kun frontend. Kun bygget, ikke set i browser.

## [0.111.4 build 0165] — 2026-10-20 — Datakvalitet: forklaring og Symboltest som i driften

- `frontend/src/lib/symbolSim.ts` + test — *Dårlig* og *Ukendt* giver ingen værdi (som `plc_runtime`); *Kommunikationsfejl* beholder den sidst kendte.
- `frontend/src/pages/SymbolTest.svelte` — forklaring ved Kvalitet.
- Manual: nyt afsnit *Drift › Datakvalitet* (tabel over de fire kvaliteter, nedtoning, alarmer/betjening/Trends), Symboltest-trin 5, fejlfinding og ordliste.
- Kun frontend og dokumentation. Kun bygget og testet.

## [0.111.3 build 0164] — 2026-10-20 — Størrelse/Gennemsigtighed/Niveau på til/fra-tags

- `frontend/src/lib/symbolConfig.ts` — `animDefaults`: Niveau, Gennemsigtighed og Størrelse får området 0–1 for et til/fra-tag (før 0–100, så Til kun gav 1 %). Gælder også symbolguiden for nye animationer; gemte opsætninger er uændrede.
- `frontend/src/lib/symbolSim.ts` — i Symboltest følger området tagget (tal: min–max, position: 0 … antal−1).
- `frontend/src/pages/SymbolTest.svelte` — plads til symbolet, når en Størrelse-animation gør det større, og billedet klipper (før voksede det ud over siden).
- Tests: `symbolConfig.test.ts`, `symbolSimAudit.test.ts` (størrelse 50/150 %, gennemsigtighed 0/1, niveau tom/fuld, område følger tagget).
- Kun frontend. **Set** i Edge: Størrelse i Symboltest (0 og 100) og i en tegning med translate/rotate.

## [0.111.2 build 0163] — 2026-10-20 — Symboltest: gennemgang, farvevalidering og overlap-advarsel

- `frontend/src/pages/SymbolTest.test.ts`, `SymbolTestSweep.test.ts` (nye, 10 tests) — siden som bruger (jsdom): Fra/Til-farver via hex, vælger og palette; alle 94 symboler; alle valg i alle menuer; alle tag-arter; afspilning; tilføj/fjern/nulstil.
- `frontend/src/lib/symbolSimLibrary.test.ts` (ny, 95 tests) — hele biblioteket: hver del × hver animation × til/fra, tal og position ændrer udseendet.
- `frontend/vite.config.ts` — komponenttests bruger Svelte-browserudgaven.
- `frontend/src/lib/ColorField.svelte`, `symbolSim.ts` — ugyldig farvekode afvises (feltet markeres og viser den gældende farve); farvenavne er gyldige (`isColor`).
- `frontend/src/pages/SymbolTest.svelte`, `symbolSim.ts` — advarsel, når to animationer af samme type rammer samme del (`conflicts`).
- BUGS.md (investigating: off-farven kunne ikke genskabes). Kun frontend. **Set** i Edge: Fra-farven på lampen.

## [0.111.1 build 0162] — 2026-10-20 — Symboltest: tekst, positionsfarver og tilbagemelding

- `frontend/src/lib/symbolSim.ts` — et til/fra-tag giver sand/falsk (som en coil), så Tekst bruger *Tekst ved Til/Fra*; Farve/Streg pr. position får en egen farve pr. position som standard.
- `frontend/src/lib/SimParams.svelte`, `ColorField.svelte` — felterne virker mens man skriver (`oninput`).
- `frontend/src/pages/SymbolTest.svelte` — *✓ Anvendt kl. … — N animationer* og knappen *Anvend igen*.
- `frontend/src/lib/symbolSimAudit.test.ts` (ny, 41 tests) — alle 13 animationstyper × til/fra, tal og position ændrer udseendet; tekst-test.
- BUGS.md. Kun frontend. **Set** i Edge (headless): tekst opdateres mens man skriver, løbelys, statuslinjen.

## [0.111.0 build 0161] — 2026-10-20 — Symboltest: afspilning og fejltilstande

- `frontend/src/lib/symbolSim.ts` + test (6 nye) — `playValue` (til/fra, tal op og ned, positioner), `clampPeriod`, tagfelterne `play`/`period`.
- `frontend/src/pages/SymbolTest.svelte` — pr. tag: *Afspil*, *Runde (s)*, *Kvalitet*, *Værdi mangler*, *Alarm*; *Stop afspilning*; forklaring af alarmmarkeringen.
- Manual (Symboltest) opdateret. Kun frontend. **Set** i Edge (headless): dårlig kvalitet dæmper symbolet, afspilning kører (Stop-knap og skiftende værdi); alarmmarkeringen er kun testet i enhedstests (den vises kun på tekst/niveau-dele).

## [0.110.0 build 0160] — 2026-10-20 — Symboltest: flere tags og animationer, parametre og palette

- `frontend/src/lib/symbolSim.ts` + test (19) — simulerede tags og animationer, `syncSim` (nulstiller ændret/fjernet, anvender alle med samme `applyBinding` som Overview), parameter-felter pr. type og art (`paramFields`), `setParam`/`setItem`/grænser, palette, alarmmarkering.
- `frontend/src/lib/SimParams.svelte`, `ColorField.svelte` (ny) — parameter-editor og farvefelt med bibliotekets palette.
- `frontend/src/pages/SymbolTest.svelte` — ny opbygning: tags, animationer (kort pr. animation), *Hent bibliotekets opsætning*/*Hent symbolets egne*, klikbar palette med kopiering af farvekode.
- **Rettet**: *Hele symbolet* animerede omslaget (`svg`) i stedet for symbolets egen gruppe, så fx en farve ikke kunne ses; nu som i en tegning. Farvepaletten var kun en visning og kunne ikke bruges — nu vælges farver direkte i paletten.
- Manual (Symboltest) opdateret. Kun frontend. **Set** i Edge (headless) på en testside: vippekontakt ON/OFF/ON (greb i position 2), pumpe og trykknap; ikke set i selve appen.

## [0.109.0 build 0159] — 2026-10-20 — Trends: kurvenavne med pile

- `frontend/src/lib/lineLabels.ts` + test — `spreadLabels` (spreder navne med mindste mellemrum), `lastVisible`, `needsArrow`.
- `frontend/src/lib/TrendChart.svelte` — navnekolonne ved højre kant (højst 150 px, lange navne forkortes), farveprik og pil til kurvens punkt, når navnet er flyttet.
- `frontend/src/manual/02-drift.md` — afsnit om kurvenavne.
- Kun frontend. **Set** i Edge (headless) på en testside med 5 kurver, hvoraf tre lå næsten oven i hinanden; ikke set i selve appen.

## [0.108.0 build 0158] — 2026-10-19 — Trends: kun opsatte trends for ikke-teknikere

- `backend/app/api/trends.py` — `_allowed`: viewer/operatør/panel får kun tags fra de trend-symboler/trendgrafer, der er sat op i deres tegninger (data, CSV og info); tekniker/admin uændret.
- `frontend/src/pages/Trends.svelte` — ingen tagliste/søgning/"vælg tags selv" uden tekniker-rettighed; første symbol vælges som start; besked hvis ingen trends er sat op.
- `backend/tests/test_trend_symbols.py`, `test_trends.py` — ny test for de tre roller; eksisterende test fik et opsat symbol.
- Manual opdateret. **Adfærdsændring**: en viewer, der før kunne trende alle tags i sine tegninger, ser nu kun opsatte trends. Frontend **kun bygget og testet** (ikke set i browseren).

## [0.107.0 build 0157] — 2026-10-19 — Trends: Vis ringe

- `frontend/src/pages/Trends.svelte` — valget *Vis ringe* (standard til, huskes pr. browser) skjuler markeringerne i graferne uden at slå analysen fra.
- Kun frontend. **Kun bygget og testet** (ikke set i browseren).

## [0.106.0 build 0156] — 2026-10-19 — Trends: fastfrosset efter tid

- `frontend/src/lib/trendAnalysis.ts` + test — `analyze(points, { frozenMinS })`: fastfrosset kræver samme værdi i mindst den valgte tid (og 3 punkter) i stedet for 12 punkter; `formatSpan`; noten viser varigheden. Standard 6 timer; `null` slår fra.
- `frontend/src/pages/Trends.svelte` — valget *Fastfrosset efter* (1 time … 7 døgn, Aldrig), husket pr. browser.
- Kun frontend. **Kun bygget og testet** (ikke set i browseren).

## [0.105.0 build 0155] — 2026-10-19 — Driftpanel: Trends og kvittering af alarmer

- `frontend/src/App.svelte` — driftpanelet viser Alarmer (kvittér) og Trends, når genvejene i tegningen åbner dem.
- `frontend/src/pages/Overview.svelte` — genvejene Alarmer/Trends virker på panelet; kun Energi afvises.
- Manual opdateret. Ingen backend-ændring: panel har allerede operatørens rettigheder (kvittering) og tegningsadgang filtrerer tags.
- **Kun bygget og testet** (ikke set i browseren).

## [0.104.0 build 0154] — 2026-10-19 — Trends: andel uregelmæssigheder i procent

- `frontend/src/lib/trendAnalysis.ts` + test — `Issue.n` (punkter ramt), `affectedPoints`, `irregularShare`, `formatShare`.
- `frontend/src/pages/Trends.svelte` — pr. kurve "x % af punkterne (a af b)" og en samlet linje "I alt" over alle tal-kurver.
- Kun frontend. **Kun bygget og testet** (ikke set i browseren).

## [0.103.0 build 0153] — 2026-10-19 — Symboltest: positioner, løbelys og guidens opsætning

- `frontend/src/lib/symbolTest.ts` — `testInfo` (del-info inkl. streger som serveren), `types` pr. del via `typesFor` (nu også Løbelys), `testBinding` med kilden *Position*, `librarySetup`/`runSetup` (bibliotekets `libraryDefault` som bindinger).
- `frontend/src/pages/SymbolTest.svelte` — animationslisten følger delen, "Tag er" får *Position* med antal positioner, ny sektion *Som i guiden* med knap pr. position.
- `frontend/src/lib/symbolTest.test.ts` — 9 nye tests (position, løbelys, typer pr. del, opsætning af ventil/vippekontakt/kontakt/pumpe/statusfelt, grebets stilling pr. position, alle biblioteksdele).
- `frontend/src/manual/06-symboler-og-guiden.md` — afsnittet Symboltest.
- Kun frontend. **Kun bygget og testet** (ikke set i browseren).

## [0.102.0 build 0152] — 2026-10-19 — Trends: Skjul spikes udfylder med interpolation

- `frontend/src/lib/trendAnalysis.ts` + test — `hideSpikes` erstatter spikes med lineær interpolation mellem nærmeste gode naboer (hold værdi ved kanten) i stedet for huller; rådata uændrede.
- `frontend/src/pages/Trends.svelte` — tekster opdateret.
- Kun frontend. **Kun bygget og testet** (ikke set i browseren).

## [0.101.0 build 0151] — 2026-10-19 — Trends: 12 kurver og dataanalyse

- `frontend/src/lib/trendData.ts` — `MAX_SERIES` 7 → 12; `colorOf`/`dashOf`: farver genbruges, kurve 8-12 er stiplet; `assignColors` har max-parameter (Energy bruger stadig 7).
- `frontend/src/lib/trendAnalysis.ts` (ny) + test — `analyze` (spike, spring, fastfrosset, hul) og `hideSpikes`; rådata ændres aldrig.
- `frontend/src/lib/TrendChart.svelte`, `frontend/src/pages/Trends.svelte` — tilvalg *Analysér data* / *Skjul spikes* (huskes pr. browser), ring om fundne punkter og oversigt.
- Kun frontend. **Kun bygget og testet** (ikke set i browseren).

## [0.100.0 build 0150] — 2026-10-19 — Symboltest

- `frontend/src/pages/SymbolTest.svelte` (ny) — gitter med alle 94 biblioteksymboler (kategori, søg), stor visning med lys/mørk/skak baggrund og størrelse; vælg del + animation + til/fra eller tal og simulér værdien; symbolets egne animationer kan køres; delene og paletten vises. Ingen PLC, intet gemmes.
- `frontend/src/lib/symbolTest.ts` (ny) — delene, de erklærede animationer, simulerede bindinger (`applyBinding`) og nulstilling. Test i `symbolTest.test.ts`.
- `frontend/src/lib/nav.ts`, `App.svelte` — menupunktet Symboltest (Opsætning, tekniker); `nav.test.ts`. Manual (06) og rolleoversigten (01).
- **Set i browseren** lokalt (API mocket): lampens glas bliver grøn ved Til; motorventilens spindel flytter sig med Flyt på mørk baggrund; symbolerne fylder deres felter. Backend er uændret og ikke kørt.

## [0.99.0 build 0149] — 2026-10-19 — Symbolkvalitet: palette og navngivne dele

- `frontend/src/lib/symbols.ts` — alle hårdkodede farver er erstattet af navngivne konstanter; `SYMBOL_COLORS` er den tilladte palette. Navngivne dele på ventiler (`hus`, `spindel`, `haandhjul`, `haandtag`, `kugle`, `kegle`, `spole`, `membran`, `fjeder`), motor/motor3 (`hus`), lampe/signallampe (`glas`), varmeveksler (`hus`, `veksler`), filter (`hus`, `si`), radiator (`hus`, `finner`).
- `frontend/src/lib/symbolConfig.ts` — danske navne på de nye dele (`PART_LABEL`).
- `frontend/src/lib/symbols.test.ts` — test: kun paletfarver i fyld/streg; komponenterne har de navngivne dele og navne.
- `docs/SYMBOLSTANDARD.md` — nyt afsnit 8 (symbolfarver og navngivne dele). FEATURES.md.
- Ingen ændring af udseende. Symboler der allerede står i tegninger er uændrede; *Erstat med symbol …* henter den nye udgave med delene. **Kun bygget og testet** (ikke set i browseren — ingen placeringsændring).

## [0.98.0 build 0148] — 2026-10-19 — Vippekontaktens greb pr. position

- `frontend/src/lib/toggleSwitch.ts` (ny) — stilling pr. position (Op / Midt / Ned) ↔ animationer: Drej @pos (Ned 0°, Op 180°), grebet skjult og knoppen vist i Midt; læser også håndlavede opsætninger (fx 180/90/0°) tilbage; bevarer andre animationer og en valgt hastighed. Test i `toggleSwitch.test.ts`.
- `frontend/src/lib/SymbolGuide.svelte` — trin 4: tabellen *Grebets stilling pr. position* for `vippe_*`-symboler med positioner, og en note når grebets animationer er sat op på en anden måde.
- `frontend/src/lib/symbols.ts` — ON/OFF har nu også knoppen (skjult), så begge vippekontakter har samme dele. `symbolConfig.ts` — biblioteksforslaget bruger `leverAnims`. Manualens symboltabel genereret.
- **Set i browseren** lokalt: tabellen viser ON 1 = Op, OFF = Midt, ON 2 = Ned (ON/OFF: OFF = Ned, ON = Op); et skift ændrer animationerne; på Overview står grebet op ved 1, kun knoppen ved 0 og grebet ned ved 2.

## [0.97.1 build 0147] — 2026-10-19 — fix: Drej og Flyt fik forkerte indstillinger med et til/fra-tag

- `frontend/src/lib/symbolConfig.ts` — `keepSuggestion(…, before)`: et forslag beholdes kun, når det afviger fra standarden for den forrige (tomme) kilde. `SymbolGuide.svelte` — giver standarden for den forrige kilde med. Test i `symbolConfig.test.ts`. BUGS.md.
- **Set i browseren** lokalt: matrix over 11 animationstyper × 4 kilder (til/fra-tag, tal-tag, alarm, altid til) i begge rækkefølger → 0 forskelle (med den gamle kode: 2 — Drej og Flyt med til/fra-tag); Drej med til/fra-tag får nu Min 0, Max 1, 0°–90°.

## [0.97.0 build 0146] — 2026-10-19 — Hastighed på Drej

- `backend/app/services/symbols.py` — `ARotate.glide_s` (0–10 s; ingen = som før). Test i `test_symbols.py`.
- `frontend/src/lib/animate.ts` — Drej glider med den valgte varighed (CSS-overgang) — også når den følger et tag — når delen ikke har sin egen transform; 0 = med det samme. `symbolConfig.ts` — `GLIDE_SPEEDS`, `glideSeconds()`. `SymbolGuide.svelte` — **Hastighed** på Drej (Med det samme … Ekstra langsom 5 s). Test i `animate.test.ts`. Manual (06).
- **Set i browseren** lokalt: kontaktkniv med "Meget langsom (2 s)" → efter Til drejer den 0° → 4° (0,5 s) → 17° (1,1 s) → 29° (1,6 s) → 32° (2,1 s); guiden viser valget.

## [0.96.2 build 0145] — 2026-10-19 — fix: symboltesten accepterer flere animationer pr. del

- `frontend/src/lib/symbols.test.ts` — testen af betjeningssymbolernes `data-hv-part` antog én animation pr. del; vippekontaktens greb har to (Drej + Synlig, v0.96.1), som serveren læser som en liste. v0.96.1 blev committet med denne ene fejlende test (min kommandokæde stoppede ikke ved fejlen); kun testen er rettet — koden var korrekt (bekræftet: serveren danner bindingerne `rotate` + `visible` på grebet og `visible` på knoppen).

## [0.96.1 build 0144] — 2026-10-19 — Vippekontakterne vipper op og ned

- Jan: "kontakten skal ikke vippe fra side til side, men op og ned for ON/OFF og op/midt/ned for ON/OFF/ON".
- `frontend/src/lib/symbols.ts` — `toggleSwitchSymbol(mid)`: set forfra; grebet tegnes NED og drejes 180° = OP. ON/OFF: OFF = 0 (ned), ON = 1 (op). ON/OFF/ON: OFF = 0 — grebet skjult og kun en **knop** (grebet set for enden) — ON 1 = 1 (op), ON 2 = 2 (ned). Tegningen viser OFF; ON over, OFF/ON 2 under, OFF til højre for midten. `part()` tager nu en liste af animationer (grebet både drejer og skjules).
- `symbolConfig.ts` — biblioteksforslag for begge (positioner, kontaktplan 0/1 hhv. 1/0/2, Drej og Synlig pr. position på greb og knop — kun tagget skal vælges i trin 2); delnavnet "Knop (midterstilling)". Manualens symboltabel (07) regenereret.
- **Set i browseren** lokalt: begge opsat gennem guiden (forslaget + tag) og gemt med de forventede positioner/animationer; på Overview: ON/OFF ned ved 0 og op ved 1 (bekræftet); ON/OFF/ON knop ved 0, greb op ved 1, greb ned ved 2. (Test-PLC'en var overbelastet, så visningen skiftede ind imellem til "ukendt position".)

## [0.96.0 build 0143] — 2026-10-19 — Klassiske vippekontakter ON/OFF og ON/OFF/ON

- `frontend/src/lib/symbols.ts` — `toggleSwitchSymbol(labels)`: monteringsplade, sekskantmøtrik og et greb (usynlig modsat halvdel → vipper om møtrikkens midte), positionernes navne og streger rundt om (vinkler som omskifteren, `selectorAngles`); klik vælger position (`click:select`), så guiden opsætter dem som omskifteren. Nye symboler *Vippekontakt ON/OFF (klassisk)* og *Vippekontakt ON/OFF/ON (klassisk)* (ON 1 / OFF / ON 2 = 0 / 1 / 2). `symbolConfig.ts` — positioner som opsætningsform; tilbyder vælger-eksemplet. Manualens symboltabel (07) regenereret.
- **Set i browseren** lokalt: begge sat ind i Tegn; ON/OFF/ON opsat med positioner på et HR-tag → klik på Overview giver dialogen med ON 1 / OFF / ON 2; værdien 2 → grebet vipper til ON 2 (`rotate(45deg)`) og positionen er bekræftet.

## [0.95.1 build 0142] — 2026-10-19 — Pumpen uden prik i midten

- `frontend/src/lib/symbols.ts` — Pumpe: navet (den mørke prik midt i løbehjulet) er fjernet (Jan). Løbehjulet er stadig symmetrisk om midten, så det drejer på stedet. Manualens symboltabel (07) regenereret.
- **Set i browseren** lokalt: pumpen uden prik; under drift drejer løbehjulet (`hv-spin`), pilen står stille.

## [0.95.0 build 0141] — 2026-10-19 — Trendgraf: opløsning følger størrelsen, diagramlinjer, tekst på to linjer

- Jan: "når man skalerer trendsymboler skal opløsningen blive større eller mindre, vi mangler diagramlinjer, og teksten skal være i to linjer, så den ikke kommer ud over boksen".
- `frontend/src/lib/chartGraphic.ts` — `chartFont()` (vokser langsommere end grafen), `chartPoints(cfg, bredde)` (60–600 punkter efter plottets bredde), `niceTicks()` (runde værdier), `timeTicks()` (runde tider i lokal tid), `wrapLegend()` (højst to linjer inden for bredden, ellers mindre skrift ned til 6), `chartLayout(…, forklaring)` med `yTicks`, `xTicks`, `legendLines` og venstremargen efter tallenes bredde. Tests omskrevet/udvidet.
- `frontend/src/lib/chartRender.ts` — grafen tegnes i tegningens (rodens) koordinater ud fra rammens boks inkl. symbolets transform (ikke inde i symbolet, så den ikke strækkes); diagramlinjer med tekst; forklaringen på flere linjer; grafen fjernes igen, når tegningen skiftes. Manual (06).
- **Set i browseren** lokalt: symbol skaleret 2× og uskaleret med to lange tagnavne → teksten på to linjer inden for rammen (ingen tekst uden for), vandrette linjer ved 30/40/50 og lodrette hvert 10. min (stor) / 15. min (lille), teksten ikke strakt.

## [0.94.0 build 0140] — 2026-10-19 — Kontakt 2-polet og 3-polet

- `frontend/src/lib/symbols.ts` — `contactSymbol(n)`: *Kontakt 2-polet* og *Kontakt 3-polet* (El), tegnet åbne; hver kniv (`kniv1…`) har en usynlig modsat halvdel, så "Drej" drejer om hængslet; `KNIV_LUKKET` = 32°. `symbolConfig.ts` — delnavnene "Kniv 1-3", biblioteksforslaget (Drej på hver kniv ved Til) og `keepSuggestion()` (testet). `SymbolGuide.svelte` — valget af det første tag beholder forslagets indstillinger (BUGS.md). Manualens symboltabel (07) regenereret.
- **Set i browseren** lokalt: begge sat ind i Tegn; 3-polet opsat i guiden (forslaget + samme tag på alle knive), 2-polet via API; på Overview er knivene åbne ved Fra og står lodret mod den faste kontakt ved Til (drejet om hængslet: `rotate(32 16 52)`).

## [0.93.0 build 0139] — 2026-10-19 — Trendgrafens tekst kan sættes op; tags fjernes med ✕

- `backend/app/services/symbols.py` — `Chart`: `legend` (top/bottom/none), `font_scale` (0,5–3), `bold`, `values`. Test i `test_trend_symbols.py`.
- `frontend/src/lib/chartGraphic.ts` — `legendOf()` (standardværdier, også for grafer gemt før), plot-området flyttes efter forklaringens placering og størrelse; `LEGEND_PLACES`, `FONT_SCALES`. Test. `chartRender.ts` — forklaringen over/under/skjult, størrelse, fed, med/uden værdi.
- `SymbolGuide.svelte` — *Tekst med tagene* (Placering, Størrelse, Fed, Vis seneste værdi) og **✕** ud for hvert valgt tag (Jan: "hvordan sletter man tags sat på" — før kun via *— ingen —* i listen). Manual (06).
- **Set i browseren** lokalt: ✕ på det midterste af tre tags → de to andre gemmes; forklaringen under grafen, stor, fed, uden værdier på Overview.

## [0.92.0 build 0138] — 2026-10-19 — Tegningens størrelse og mere intuitive tegneværktøjer

- **Størrelse:** `frontend/svgedit-host/scada-editor.js` — `getSize()`, `setSize(w, h, fit, margin)` (ét fortryd-trin; en baggrund der fyldte tegningen følger med; "tilpas" flytter indholdet op i hjørnet og ser bort fra baggrunden), `syncContentSize()` efter hver ændring (rettelse af SVG-Edits fortryd for størrelsen). `frontend/src/lib/drawingSize.ts` (ny, testet): faste valg og kontrol af bredde/højde. `DrawEditor.svelte` — knappen **Størrelse: B × H** med panel (fast valg, bredde/højde, Tilpas til indholdet med margen).
- **Værktøjerne:** `frontend/svgedit-host/locale-da.js` (ny) — danske tekster for værktøjer, felter, lag og udvidelser lagt oven på SVG-Edits engelske; `localize()` skifter sproget og oversætter knapper/felter igen; udvidelsernes knapper, farvefelterne og genvejsteksterne sættes direkte. `frontend/src/lib/toolHints.ts` (ny, testet) + `onMode()` i værten: hjælpelinjen over tegneområdet. Forbindelsesværktøjet (ext-connector) fjernet; "untitled.svg" skjult (`scada-editor.css`). BUGS.md. Manual (04).
- **Set i browseren** lokalt: Full HD → 1920 × 1080 (baggrunden følger med); bredde 50 → fejlbesked; Tilpas til indholdet → 240 × 150 med indholdet i 20,20; Fortryd → 1920 × 1080 igen (også knappen); gemt version har 240 × 150. Værktøjerne viser "Vælg og flyt", "Rektangel / kvadrat", "Fortryd [ctrl+Z]", "Fyldfarve — klik for at vælge", felterne "Bredde [b]", "Slet [Delete/Backspace]", fanen "Lag"; hjælpelinjen skifter med værktøjet; forbindelsesværktøjet er væk.

## [0.91.1 build 0137] — 2026-10-19 — fix: omskifterens tegning følger opsætningens positioner

- `frontend/src/lib/selectorRedraw.ts` (ny, testet): `selectorMismatch()` (antal/navne), `withSelectorAngles()` (grebets vinkler pr. position efter den nye tegning; animationen flyttes til det nye greb).
- `frontend/svgedit-host/scada-editor.js` — `selectorLabels()`, `partIdByPid()`. `frontend/src/pages/DrawEditor.svelte` — besked + **Tegn omskifteren med N positioner** (tegner med `selectorSymbol` via "Erstat med symbol" med behold id, gemmer og udgiver, retter vinklerne i opsætningen; serverens fejl vises). `SymbolGuide.svelte` — besked i trin 3. BUGS.md. Manual (06).
- **Set i browseren** lokalt: Omskifter Hånd/0/Auto + opsætning med 5 positioner → beskeden i Tegn → knappen → tegningen viser Hånd, 0, Auto, Service, Test, navnet er bevaret, opsætningen sidder stadig på omskifteren med vinklerne −90/−45/0/45/90 på grebet.

## [0.91.0 build 0136] — 2026-10-19 — Trendgraf i tegningen (kurve eller søjler)

- `backend/app/services/symbols.py` — `Chart` i symbolopsætningen (1-4 tags, periode 15 min-7 dage, kurve/søjler, antal søjler 4-60, Y-akse, titel): tags valideres, advarsel når et tag ikke gemmer historik; grafens tags tæller som symbolets tags (adgang for begrænsede brugere, sletbeskyttelse, Trends-symbollisten); Overview får grafen via `symbol_config` og tagenes metadata. Test i `test_trend_symbols.py`.
- `frontend/src/lib/chartGraphic.ts` (ny, testet): Y-akse (valgt/automatisk, søjler med 0), kurver med huller, søjler pr. tidsspand og serie, akse-tekster, opdateringsinterval. `chartRender.ts` (ny): tegner grafen i symbolets ramme på Overview fra `/api/trends/data`, opdaterer løbende, viser serverens fejltekst i grafen.
- `symbols.ts` — symbolet *Trendgraf*; `symbolConfig.ts` — biblioteksforslag; `SymbolGuide.svelte` — sektionen **Graf** i trin 4 (grafens tags også i trin 6 *Historik*). Manual (06, 07).
- **Set i browseren** lokalt: Trendgraf sat ind i Tegn → guiden (to tags) → gemt → Overview viser to kurver med forklaring, Y-akse og tider; som søjler (15 min, 12 søjler) to søjler side om side.

## [0.90.1 build 0135] — 2026-10-18 — SSE-status pr. kilde: RS485 og expansion boards

- `backend/app/plc/sse.py`, `manager.py`, `Plcs.svelte` — `ext`-hændelser tælles pr. kilde (`ext_by_src`: rtu/mbx) og vises under PLC'er ("RS485 N, expansion boards M"), så det kan ses, at også expansion boards leverer via SSE. Test i `test_sse.py`. Manual (03).

## [0.90.0 build 0134] — 2026-10-18 — SSE for eksterne Modbus-registre

- Analyse (PLC-firmware `sse_events.cpp`, FEAT-447): PLC'en sender eksterne registre fra sin Modbus-cache som SSE-hændelsen `ext` (`{src: rtu|mbx, [board, ch], slave, type, addr, value, status}`), men kun i watch_all (`subscribe=all` uden adresselister). Værdierne er kun så friske som cachen — PLC'en læser et register, når ST læser det, eller når nogen spørger via /api/ext.
- `backend/app/plc/sse.py` — `build_watch(…, external)`: eksterne tags → watch_all; `ext`-hændelser valideres og sendes til `on_ext`; tæller `ext_events`. Rettet: i watch_all følger dækningen PLC'ens grænser (IR kun 0-255) — BUGS.md.
- `backend/app/services/plc_runtime.py` — `_on_sse_ext()`: samme lager og regler som pollingen (pending beholder sidst kendte værdi, error markerer tagget, kanal 1-8 → A-H; kun registre som et tag bruger); flerordstags følger med. Pollingen af /api/ext hvert 2. s bevares (den driver PLC'ens læsning).
- `manager.py` + `Plcs.svelte` — status: "eksterne registre via SSE (N)". Mock-PLC'en sender `ext` i watch_all. Test: `test_sse.py`, `test_ext.py`. Manual (03).

## [0.89.0 build 0133] — 2026-10-18 — Systemgennemgang F2: symboler med samme navn

- `frontend/svgedit-host/names.js` — `duplicateNames()` og `uniqueRenames()` (det første beholder navnet, de næste får næste ledige nummer). Test i `names.test.ts`. `scada-editor.js` — `duplicateNames()` og `fixDuplicateNames()` (ét fortryd-trin).
- `frontend/src/pages/DrawEditor.svelte` — advarsel i Tegn med knappen **Giv dem unikke navne**; følges ved hver ændring (kommer igen efter fortryd), ryddes ved en ny tegning.
- Baggrund: fase 1 fandt "Bøjning 90° 6" ×3 i "varme" (kopier fra før v0.63.1). Manual (04).
- **Set i browseren** lokalt: "Bøjning 90° 6" ×3 + "Bøjning 90° 7" → advarsel → knappen giver 6, 8, 7, 9 (det eksisterende 7 springes over) og beskeden vises; Fortryd giver de gamle navne og advarslen igen.

## [0.88.0 build 0132] — 2026-10-18 — Systemgennemgang F1: forsvundne symbolopsætninger kan ses, flyttes og fjernes

- Fase 1 (læse-kun gennemgang): lag, roller pr. endpoint, tegningsadgang, session/CSRF/login-låsning, opdateringspakke og backup (størrelser, stier), hemmeligheder i log, PLC-klientens fejlstatusser og npm-afhængigheder var i orden. Data på testserveren: 4 symbolopsætninger på forsvundne elementer (F1) og 3 symboler med samme navn (F2).
- `backend/app/services/symbols.py` — `orphaned()` og `move()` (dele via id-mønstret `<symbol>_<del>`, ellers droppet med besked; PIN flyttes med og ryddes igen, hvis flytningen afvises; logikblokke brugt af andre symboler blokerer); `backend/app/api/symbols.py` — `GET /api/drawings/{id}/symbols-orphaned`, `POST …/symbols/{element}/move` (audit `symbol.move`). Test: `test_symbol_orphans.py`.
- `frontend/src/pages/Editor.svelte` — *Forsvundne elementer* viser også symbolopsætninger (type, animationer, kode) med **Flyt hertil** / **Fjern** / **Fjern alle**. Rettet samtidig: beskeden efter "Flyt hertil" (også for bindinger, v0.83.0) blev aldrig vist — den blev ryddet, når elementet blev valgt igen efter genindlæsningen.
- Manual (05). BUGS.md. **Set i browseren** lokalt: pumpe `P` med opsætning (+ del `P_pil`), ny version hvor den hedder `P_2`, og et slettet rektangel med opsætning → panelet viser begge; *Flyt hertil* på `P_2` → `all` + `P_2_pil` og beskeden vises; *Fjern* det andet → panelet forsvinder.

## [0.87.0 build 0131] — 2026-10-18 — Alarmmarkering kun på værdivisninger

- `frontend/src/lib/alarmMark.ts` (ny, testet): markering pr. element ud fra bindingerne — kun animationerne `text` (Værdi) og `level` (Niveau); ukvitteret vinder over kvitteret, når et element viser flere tags. `frontend/src/pages/Overview.svelte` — `markAlarms()` bruger den og rydder markeringen på alle andre bundne elementer (før kunne en senere binding på samme element fjerne en tidligere bindings markering).
- Baggrund (Jan, skærmbillede fra "varme"): ved alarmen *plc1_L2_edit høj (H)* blinkede også kedlens ramme (Blafrer) og Pumpe PS1's pil (Størrelse), fordi de bruger samme tag. Manual (02).
- **Set i browseren** lokalt: tag i H-alarm brugt af en værditekst, en blafrende ramme og en pumpepil → kun teksten får `hv-alarm-unack`, efter kvittering `hv-alarm-ack`, efter ophør ingen; rammen blafrer uden markering, pilen er umarkeret.

## [0.86.0 build 0130] — 2026-10-18 — Løbehjul i pumpen

- `frontend/src/lib/symbols.ts` — Pumpe: trekanten er erstattet af et **løbehjul** (del `loebehjul`: fire krumme skovle og et nav, symmetrisk om midten); retningspilen ligger øverst. `symbolConfig.ts`: delnavnet "Løbehjul" og biblioteksforslaget "Roterer på løbehjulet" (ikke for gamle pumper uden løbehjul). Manualens symboltabel (07) regenereret; manual (06).
- **Set i browseren** lokalt: pumpe sat ind i Tegn (dele `loebehjul`, `pil`) → guiden foreslår "Løbehjul · Roterer" → på Overview under drift: løbehjulet `hv-spin`, pilen står stille (to skærmbilleder med forskellig skovlstilling, samme pil).

## [0.85.0 build 0129] — 2026-10-18 — Pumpens pil drejer ikke med; ny animation Størrelse

- `backend/app/services/symbols.py` — animationen `scale` ("Størrelse", `AScale`: min/max + size_min/size_max i %, > 0 og ≤ 1000); kun tal-tag (`NUMERIC_ONLY`). Test i `test_symbols.py`.
- `frontend/src/lib/animate.ts` — `scale`: delen skaleres om sin midte (inderst i transform-listen, efter Drej/Flyt; 100 % og ukendt værdi = ingen ekstra transform). `spinHost()`: Roterer på en gruppe med en retningspil (`data-hv-pid="pil"`) drejer en indre gruppe med resten — pilen står stille og ligger stadig øverst. Test i `animate.test.ts`.
- `frontend/src/lib/symbolConfig.ts`, `SymbolGuide.svelte`, `api.ts` — typen Størrelse med felterne *Størrelse ved min/max (%)*; ingen alarm/"altid til"-kilde (som Niveau/Gennemsigtighed).
- Manual (06). **Set i browseren** lokalt: pumpe med Roterer på hele symbolet og Størrelse på pilen → under drift drejer cirkel og trekant, pilen står vandret; pilen 55/110/165 px ved flow 0/50/100 (50/100/150 %); guiden viser Størrelse med felterne.

## [0.84.0 build 0128] — 2026-10-18 — Opdatér gamle biblioteksymboler med "Erstat med symbol"

- `frontend/src/lib/symbolSuggest.ts` — et symbol fra biblioteket får forslaget "den nyeste udgave af samme symbol" (før: ingen forslag). Test.
- `frontend/svgedit-host/scada-editor.js` — "Behold id": det erstattede elements eget id genbruges, selv om det er reserveret (før fik det et løbenummer, og opsætningen blev forældreløs — BUGS.md); "lignende" for et biblioteksymbol = samme type; med "behold id" springes en lignende del kun over, hvis dens underelementer/tekster er bundne; lignende dele med et navn beholder det. `DrawEditor.svelte`/`SymbolReplace.svelte`: antallet der springes over, følger "behold id".
- Manual (04). **Set i browseren** lokalt: tre gamle pumper (uden pil, drejet −90°, én med opsætning) → forslaget "Pumpe — den nyeste udgave", "Også de 2 lignende" → alle tre har pilen (peger opad som før), samme størrelse og drejning, id'erne `pumpe`, `pumpe_2`, `pumpe_3` og navnene P1–P3 bevaret, opsætningen på `pumpe` virker efter Gem og udgiv.

## [0.83.1 build 0127] — 2026-10-18 — fix: nye 3-vejs ventiler arvede løbelys fra et gammelt rør

- `frontend/src/pages/DrawEditor.svelte` — de reserverede id'er (`/used-ids`) hentes og sættes, **før** tegningen indlæses i SVG-Edit (som giver elementer uden id et `svg_N`-id ved indlæsningen); kan listen ikke hentes, ryddes den (ikke den forrige tegnings). BUGS.md.
- **Set i browseren** lokalt: opsætninger på de forsvundne `svg_1`/`svg_2`, ny version med en 3-vejs ventil hvis to dele ikke har id → før rettelsen fik delene `svg_1` og `svg_2` (og dermed løbelyset), efter rettelsen `svg_3` og `svg_4`.

## [0.83.0 build 0126] — 2026-10-18 — Løsning på "Bindinger til elementer der ikke findes"

- `frontend/src/lib/orphans.ts` (ny, testet): bindingerne pr. forsvundet element; flet flyttede bindinger ind i målets (dubletter springes over, højst 10 som serveren).
- `frontend/src/pages/Editor.svelte` — *Forsvundne elementer*: forklaring, hvad hver binding var (tag · animation), **Flyt hertil** (til det valgte element; målet gemmes først, så intet tabes ved en fejl; afvises med forklaring, hvis målet er sat op med symbolguiden, eller hvis der er ugemte ændringer), **Fjern** og **Fjern alle**; serverens fejl vises.
- `frontend/src/pages/Overview.svelte` — advarslen forklarer årsagen og linker (teknikere) til Bindinger.
- Manual (05). **Set i browseren** lokalt: version 2 hvor `PLC1_Val` har fået id'et `svg_300` og `svg_190` er slettet → Overview-advarsel med link → panelet viser "OrphVal · Tekst" og "OrphBit · Synlighed"; flyt til et guide-symbol afvist med forklaring; flyt til `svg_300` virker; Fjern `svg_190`; advarslen er væk.

## [0.82.1 build 0125] — 2026-10-18 — fix: pumpens pil inde i symbolet

- `frontend/src/lib/symbols.ts` — Jan: "pilen skal være inde i pumpesymbolet". Pilen ligger nu inde i trekanten (stadig egen del `pil`), så pumpen har sin runde form. `scada-editor.js`: tilpasningen uden pilen i "Erstat med symbol" (v0.82.0) er fjernet igen — pumpens boks er cirklen. Manualens symboltabel (07) regenereret.

## [0.82.0 build 0124] — 2026-10-18 — Retningspil på pumpen

- `frontend/src/lib/symbols.ts` — Pumpe: pil på afgangssiden (egen del `pil`, så den kan farves/blinke); tip om at dreje symbolet for at vende retningen. `symbolConfig.ts`: delnavnet "Pil". Manualens symboltabel (07) regenereret.
- `frontend/svgedit-host/scada-editor.js` — "Erstat med symbol" tilpasser efter symbolet uden pilen (`unionBox` af de øvrige dele), så en erstattet pumpe får den tegnede cirkels størrelse.
- **Set i browseren** lokalt: tegnet pumpe (cirkel 100 × 100, trekant nedad) erstattet med Pumpe → cirklen 100 × 100 på samme sted, drejet 90° så pilen peger nedad; pilen er delen `tegnet_pil`; pumpen i biblioteket viser pilen.

## [0.81.1 build 0123] — 2026-10-18 — fix: Roterer og Blafrer på "Hele symbolet" flyttede symbolet

- `frontend/src/lib/animate.ts` — `motionHost()`: har elementet sin egen `transform` (placeret symbol, drejet del), kører Roterer/Blafrer på en gruppe om elementet (oprettes første gang animationen tændes, genbruges), så CSS-animationen ikke erstatter elementets placering; farverne sættes stadig på elementet. Uden transform som før. Test i `animate.test.ts`. BUGS.md.
- **Set i browseren** lokalt (Chrome): seks placerede kedler (skaleret 1,2 × 1,5) med Farve, Stregfarve, Blink, Synlig, Roterer og Blafrer på "Hele symbolet" — alle virker; Roterer drejer om symbolets midte på stedet, Blafrer står på stedet i sin størrelse (før: hoppede op i hjørnet og mistede skaleringen).

## [0.81.0 build 0122] — 2026-10-18 — Forståelige delnavne i guiden; navn på kurverne i Trends

- `frontend/src/lib/symbolConfig.ts` — `partLabel()`: dele uden biblioteksnavn navngives efter formen ("Rektangel", "Cirkel 2", `Tekst "STF"`; et biblioteksymbols første rektangel = "Ramme", de øvrige nummereres uden den) med id'et i parentes. Test i `symbolConfig.test.ts`.
- `backend/app/services/svg_sanitize.py` — `describe_element()`: tekst-dele får `text` (teksten, højst 24 tegn). Test i `test_symbols.py`.
- `frontend/src/pages/Trends.svelte` — under *Administrér* knappen **Navn** pr. tag (sætter tagets beskrivelse; tomt = tag-navnet; serverens fejl vises); tag-navnet som tooltip. `frontend/src/lib/ask.ts` — `askText(…, { allowEmpty })`: tom tekst er et svar, kun Annullér giver null (test i `ask.test.ts`).
- Manual (02, 06). **Set i browseren** lokalt: kedel med ramme, flamme, ekstra rektangel, tekst og cirkel → "Hele symbolet, Ramme (svg_2), Flamme, Rektangel (svg_7), Tekst "STF 1" (svg_8), Cirkel (svg_9)"; i Trends **Navn** → "Fremløbstemperatur" i listen og grafens forklaring, gemt på serveren; tomt navn → tag-navnet igen.

## [0.80.1 build 0121] — 2026-10-18 — fix: Blafrer og Roterer stopper ikke ved ukvitteret alarm

- `frontend/src/app.css` — et element med både Overviews alarmmarkering (`hv-alarm-unack`) og en egen animation (`hv-flicker`, `hv-spin`, `hv-blink`) kører nu begge animationer (før erstattede alarmmarkeringen den anden, da de bruger samme CSS-egenskab); blinkfrekvensen (langsom/hurtig) bevares; "reducér bevægelse" som før. BUGS.md.
- **Set i browseren** lokalt (Chrome): som kedlen i "varme" — Blafrer på rammen og Roterer på en rotor ved ≥ 50, alarm H 90, baggrund blinker på ukvitteret alarm. Ved 95: rammen `hv-flicker, hv-alarm`, rotoren `hv-spin, hv-alarm` (på serveren før rettelsen: kun `hv-alarm`).

## [0.80.0 build 0120] — 2026-10-18 — Trends ud fra symbolerne

- `backend/app/services/symbols.py` — `trend_symbols()`: de opsatte symboler i tegningernes aktive version med deres tags (`config_tags`); en opsætning på et element, der ikke er i den aktive version, springes over; en tegning hvis SVG ikke kan læses, logges og springes over.
- `backend/app/api/trends.py` — `GET /api/trends/symbols` (viewer): kun tegninger og tags brugeren må se; symboler uden synlige tags udelades. Test: `test_trend_symbols.py`.
- `frontend/src/lib/trendSymbols.ts` (ny, testet): rute ↔ nøgle (`#trends/<tegning>/<element>`), hvilke tags der kan vises (med historik, højst 8; resten "uden historik"/"ikke plads"), gruppering pr. tegning.
- `frontend/src/pages/Trends.svelte` — rullelisten **Symbol** (pr. tegning) vælger symbolets kurver; tags uden historik nævnes, og en tekniker kan slå dem til med ét klik (stopper ved første fejl og viser den); vælger man selv et tag, nulstilles symbolvalget; ruten med et symbol vælger det (også hvis adressen ændres, mens siden er åben); ukendt symbol giver en forklaring. `App.svelte` giver Trends ruten.
- `frontend/src/lib/SymbolGuide.svelte` — trin 6: afsnittet **Historik (Trends)** med flueben pr. tag (PATCH `trend`), **Gem historik for alle** og linket **Vis symbolet i Trends** (ny fane, så en åben guide ikke mistes).
- Manual (02, 06). **Set i browseren** lokalt: guidens historik-afsnit → "Gem historik for alle" → begge tags slået til på serveren; `#trends/<tegning>/pp` → symbolet valgt og begge kurver vist; et tag uden historik → nævnt, knappen slår det til og kurven kommer med; manuelt tag-valg nulstiller symbolet; ukendt symbol → forklaring.

## [0.79.0 build 0119] — 2026-10-18 — Tegn og Bindinger åbner tegningen fra Overview

- `frontend/src/lib/nav.ts` — `navHref()` (testet i `nav.test.ts`): fra `#overview/<id>` peger menupunkterne Tegn og Bindinger på `#draw/<id>` / `#editor/<id>`; alle andre sider og ruter som før.
- `frontend/src/App.svelte` — menulinkene bruger `navHref()` med den aktuelle adresse (læst når menuen tegnes: Overview skifter tegning med `replaceState`, som ikke udløser `hashchange`).
- Manual (04). **Set i browseren** lokalt (Firefox): Overview med start-tegningen og med en anden valgt tegning → Tegn og Bindinger åbner hver gang den samme tegning; fra Tags peger Tegn stadig på `#draw`.

## [0.78.0 build 0118] — 2026-10-18 — Mine symboler i Tegn

- `backend/app/services/auth.py` — `palette()` / `set_palette()`: brugerens symbol-id'er i valgt rækkefølge, gemt som indstillingen `palette:<bruger>` (id-format kontrolleres, dubletter fjernes, højst 60); slettes sammen med brugeren.
- `backend/app/api/auth.py` — `GET` / `PUT /api/auth/me/palette` (tekniker og op). Test: `test_my_symbols_palette` (pr. bruger, rækkefølge, ugyldige id'er, grænse, sletning).
- `frontend/src/lib/palette.ts` (ny, testet i `palette.test.ts`): `toggleFavorite`, `moveFavorite`, `knownFavorites` (symboler der ikke findes i biblioteket springes over).
- `frontend/src/pages/DrawEditor.svelte` — sektionen "Mine symboler" øverst i biblioteket; hver flise har ☆/★ (øverste højre hjørne) og i Mine symboler ◀ ▶ (nederste hjørner); ændringen vises straks og rulles tilbage med serverens fejltekst, hvis den ikke kan gemmes; søgningen gælder også sektionen.
- Manual (04). **Set i browseren** lokalt (Chrome og Firefox): tre symboler lagt ind, Varmepumpe flyttet frem, indsat fra sektionen, søgning, listen bevaret efter genindlæsning, Kedel/fyr fjernet igen.

## [0.77.0 build 0117] — 2026-10-18 — Felt-symboler kan gøres bredere uden at strække teksten

- `frontend/svgedit-host/snap.js` — `fieldResize()` (ren, testet i `snap.test.ts`): fladen får den nye størrelse; teksten flyttes (midterstillet følger midten, venstre/højre beholder afstanden til kanten), skriftstørrelsen er uændret; en pille forbliver en pille.
- `frontend/svgedit-host/scada-editor.js` — `normalizeFields()` efter en strækning af Statusfelt, Værdifelt og Auto/Manuel (kun ikke-drejede, dele uden egen transform; gruppens matrix læses uden at ændre den); ét ekstra fortryd-trin.
- Manual (04). **Set i browseren** lokalt: statusfelt trukket ud → flade 76 → 192 bred med runde ender, teksten "STF" stadig 25 bred og i midten; fortryd i to trin tilbage til udgangspunktet.

## [0.76.0 build 0116] — 2026-10-18 — Tilbage til tegningen fra Alarmer, Trends og Energi

- `frontend/src/lib/BackToDrawing.svelte` + `backToDrawing.ts` (ny): "← Tilbage til "<tegning>"" — den sidst viste tegning i fanen (`overview.last`); findes den ikke (mere), går knappen til Overview. Sat ind øverst i `Alarms.svelte`, `Trends.svelte`, `Energy.svelte`.
- Manual (02). Test: `backToDrawing.test.ts`. **Set i browseren** lokalt: fra tegningen "Kedelrum test" via genvejene til hver af de tre sider → knappen "← Tilbage til "Kedelrum test"" → tilbage i Overview på tegningen.

## [0.75.1 build 0115] — 2026-10-18 — Symbolbiblioteket i Tegn ruller for sig selv

- `frontend/src/pages/DrawEditor.svelte` — `fitFrame()` giver sidepanelet editorens højde (ikke på skærme ≤ 900 px); "Valgt element" højst 55 % og ruller selv; "Symboler" fylder resten og ruller selv med overskrift og søgefelt stående øverst. **Set i browseren** (1400×900, 1920×1080, 820×900): panel = editorens højde (756/936 px), rulning i symbolerne flytter kun listen (siden står stille), søgefeltet bliver øverst; med et valgt symbol ruller listen stadig; smal skærm som før.

## [0.75.0 build 0114] — 2026-10-17 — Genvejssymboler: Alarmer, Trends, Energi

- `frontend/src/lib/symbols.ts` — kategorien *Genveje* med `genvej_alarmer`, `genvej_trends`, `genvej_energi` (`navButton`: roden har `data-hv-nav`; alarmknappen har delene `maerke` og `antal`).
- `frontend/src/lib/navSymbols.ts` (ny) — `navTarget()` (kun alarms/trends/energy godtages), `alarmBadge()`, `markNavClickable()`, `applyAlarmBadges()`.
- `frontend/src/pages/Overview.svelte` — klik på en genvej åbner siden (driftpanel: besked i stedet); alarmmærket opdateres ved hver alarmliste fra serveren og når tegningen monteres. `app.css`: mærkets farver og blink. `symbolConfig.ts`: kun visning.
- Manual (04, 07). Tests: `navSymbols.test.ts`. **Set i browseren** lokalt: de tre genveje indsat fra paletten; med én aktiv ukvitteret alarm viste mærket "1" rødt; klik åbnede Alarmer, Trends og Energi.

## [0.74.1 build 0113] — 2026-10-17 — fix: grænser og til/fra-alarm på samme tag afvises; manual om tag-alarmer

- `backend/app/services/tags.py` — et tag kan ikke få både grænser (HH/H/L/LL) og til/fra-alarm (alarmmotoren brugte kun til/fra-alarmen; grænserne blev stille ignoreret for "auto"-tags). Tests: `test_alarms.py` (afvisning; skift tilladt, når den anden ryddes i samme gem).
- `frontend/src/manual/03-plcer-og-tags.md` — "Alarmer på et tag": tabel over felterne, rækkefølge, prioritet pr. niveau, dødbånd og forsinkelse med eksempel, eskalering, kommunikationsfejl. Se BUGS.md.

## [0.74.0 build 0112] — 2026-10-17 — Alarmer i symbolguiden

- `backend/app/services/alarms.py` — `publish()`: alarmtilstanden pr. tag som live-værdier `alarm:<tag>:active` og `alarm:<tag>:unack` (for alle tags med alarmopsætning; efter hver evaluering og kvittering; forældede fjernes).
- `backend/app/services/symbols.py` — kilden `@alarm:active|unack:<tag>` (`parse_alarm_ref`, `alarm_tag`): valideres (gyldig art, tag findes, ikke Niveau/Gennemsigtighed/Værdi; advarsel hvis tagget ingen alarm har), bliver bindingens tag `alarm:<tag>:<art>`; tagget tæller som brugt (`config_tags`, kan ikke slettes); ikke en logikreference.
- `frontend/src/lib/symbolConfig.ts` (`alarmRef`, `parseAlarmRef`), `SymbolGuide.svelte` ("styres af: en alarm — er aktiv / er ukvitteret — på tag"; trin 6 "Alarmer på symbolets tags"; kontrollen køres igen, når en alarm rettes), `TagAlarm.svelte` (én rækkes visning og "Ret alarm" → `PATCH /api/tags/{navn}`, serverens fejltekst vises), `tagAlarm.ts` (opsummering, formular → data, status).
- Manual (02, 06). Tests: `test_symbols.py` (kilden, pseudotags), `tagAlarm.test.ts`. **Set i browseren** lokalt: lampe med Blink styret af "en alarm / er aktiv / AlarmTest"; alarmen sat i trin 6 ("når Til"); Overview: ingen alarm → blinker ikke, tag Til → blinker, tag Fra → stopper; trin 6 viste "Ophørt — ukvitteret".

## [0.73.0 build 0111] — 2026-10-17 — Beregning og enhed i guidens Værdi-animation

- `frontend/src/lib/SymbolGuide.svelte` — Værdi (tal-tag): felterne *Beregning* (fejlbesked straks via `expressionError`) og *Vis enhed*, og "Lige nu: værdi → visning" (`textFor` med tagets enhed). Serveren godtog allerede `expression`/`show_unit` (samme `TextParams` som Bindinger).
- Manual (06): afsnittet "Værdi: decimaler, tekst før/efter, beregning og enhed". Test: `test_symbols.py`. **Set i browseren** lokalt: tag 128 [bar], *x / 10*, 1 decimal, "Tryk: " → guiden viser "Lige nu: 128 → Tryk: 12.8 bar", en ugyldig beregning "Manglende )"; Overview viser "Tryk: 12.8 bar".

## [0.72.0 build 0110] — 2026-10-17 — Aktiv/passiv-animationer og standard

- `backend/app/services/symbols.py` — `Anim.when` ("aktiv/passiv"; kun Farve, Stregfarve, Blink, Synlig, Roterer, Blafrer, Løbelys — `WHEN_TYPES`), bliver `params.when` på bindingen.
- `frontend/src/lib/animate.ts` — `bindingActive()` (er animationen aktiv: løbelys kører, farve Til/grænse nået, til/fra-typerne; ukendt værdi og "gælder ikke i positionen" er ikke aktiv); `resetAnim` eksporteret.
- `frontend/src/lib/canvas.ts` — prioritetsgrupper (`priorityGroups`, `groupWinner`): samme slags animation på samme del med mindst én aktiv/passiv → den øverste aktive vinder (en med "vis fra-tilstand" tæller altid som aktiv); ingen → delen som tegnet; de andre rydder op. Farve og Blafrer er samme slags. Uden aktiv/passiv: som før (den sidste vinder).
- `frontend/src/lib/SymbolGuide.svelte` — "Når den ikke er aktiv: vis fra-tilstand / gør ingenting (passiv)" og knappen *+ Standard* (altid til, nederst). `api.ts`: `Binding.position`.
- Manual (06). Tests: `test_symbols.py`, `canvas.test.ts`, `animate.test.ts`. **Set i browseren** lokalt: rør med løbelys rødt (A, passiv), grønt (B, passiv) og standard blåt — A/B fra/fra → blåt, til/fra → rødt, til/til → rødt, fra/til → grønt, fra/fra → blåt; guiden med valget og *+ Standard*.

## [0.71.0 build 0109] — 2026-10-17 — Manual: løbelysets styring

- `frontend/src/manual/05-bindinger-og-animationer.md` — nyt afsnit "Løbelysets styring": *Til/fra*, *Fortegn (+/−)* og *Kode 0/1/2* (tabel), *Omvendt*, *Retning fra*, ukendt værdi, *altid til* og symbolets position. Afkrydsningsfeltet hedder *Omvendt* i guiden — manualen sagde "Vend retning"; rettet. Kun manualtekst (bygges ind i siden), derfor kun nyt build.

## [0.71.0 build 0108] — 2026-10-17 — Kilden "Altid til" i symbolguiden

- `backend/app/services/symbols.py` — `ON = "@on"`: gyldig kilde for til/fra-animationer (ikke Niveau, Gennemsigtighed, Værdi); ikke en logikreference; bindingen får tagget `@on`. `bindings.py` — `binding_tags()` udelader `@on` (hentes aldrig live, kræver ingen adgang).
- `frontend/src/lib/symbolConfig.ts` (`ON`, `isLogicRef`), `SymbolGuide.svelte` ("styres af": *altid til*; vælgeren vises altid), `canvas.ts` (`@on` = altid aktiv; ikke i `bindingTags`).
- Tests: `test_symbols.py`, `canvas.test.ts`. **Set i browseren** lokalt: fyrets flamme med *altid til* — gemt uden tag; i Overview blafrede den og skiftede farve, mens tagget var slukket.

## [0.70.1 build 0107] — 2026-10-17 — fix: drejede biblioteksrør vokser ikke længere for meget ved anden strækning

- `frontend/svgedit-host/snap.js` — `rotationCenter()` og `recenterOffset()` (rene, testet i `snap.test.ts`).
- `frontend/svgedit-host/scada-editor.js` — `normalizeRotatedGroups()`: efter en strækning af en drejet gruppe lægges strækningen ned i delene, og gruppen drejes kun om sin nye midte (ét ekstra fortryd-trin; udseendet uændret). Se BUGS.md.
- Data på testserveren (efter aftale med Jan): den gamle symbolopsætning på `svg_15` i "varme" (løbelys på ekspansionsbeholderens streg) er fjernet.

## [0.70.0 build 0106] — 2026-10-17 — Blafrer: hele flammen skifter tilfældigt mellem tre farver

- `backend/app/services/symbols.py` — `AFlicker.palette` (1–3 farver, standard rød/orange/gul); gemt med v0.69.0 (`color`, ingen palette) → den farve først.
- `frontend/src/lib/symbolConfig.ts` — `FLICKER_PALETTE`, `flickerPalette()`; guidens standard.
- `frontend/src/lib/animate.ts` — én fælles timer (160 ms) skifter fyldfarven tilfældigt for alle blafrende dele (`nextFlickerColor()`: aldrig samme farve to gange i træk); stoppes, når den sidste flamme slukkes; ingen skift ved "reducer bevægelse". `app.css`: blød overgang mellem farverne.
- `frontend/src/lib/SymbolGuide.svelte` — "Skifter tilfældigt mellem: Farve 1–3"; ældre opsætninger normaliseres ved indlæsning.
- Tests: `test_symbols.py`, `animate.test.ts` (falske timere: alle tre farver, aldrig samme to gange, stop ved sluk), `libraryDefaults.test.ts`. **Set i browseren** lokalt: guiden viser tre farver; i Overview skiftede flammens farve ved alle 11 målinger og blafrede; en opsætning fra v0.69.0 åbner med sin farve først.

## [0.69.0 build 0105] — 2026-10-17 — Blafrende flamme, Gem på alle trin, id'er genbruges ikke

- **Animation "Blafrer"** (`flicker`): `backend/app/services/symbols.py` (`AFlicker`: farve + til/fra/≥/pr. position; navn og pr.-position-felt), `frontend/src/lib/symbolConfig.ts` (type, standard, guidens forslag for Kedel/fyr), `SymbolGuide.svelte` (felt "Flammefarve"), `animate.ts` (`flicker()`: inline-fyld + klassen `hv-flicker`), `app.css` (keyframes: skalerer blødt fra bunden, hælder lidt; slået fra ved "reducer bevægelse"). Biblioteket: Kedel/fyr-hint.
- **Gem på alle trin** i symbolguiden (`SymbolGuide.svelte`): Gem/"Gem i alle N" står ved siden af Næste og er aktiv, så snart opsætningen er uden fejl.
- **Id'er med opsætning/binding genbruges ikke** (se BUGS.md): `SymbolService.used_ids()` + `GET /api/drawings/{id}/used-ids`; værten `setReservedIds()`, `idExists()` og tegningsobjektets `getNextId` springer dem over; Tegn henter listen ved åbning og efter guide/indsæt.
- Tests: `test_symbols.py` (Blafrer), `test_symbol_copy.py` (used-ids), `animate.test.ts`, `libraryDefaults.test.ts`. **Set i browseren** lokalt: Kedel indsat → guiden foreslår Blafrer på flammen, Gem på trin 1 (inaktiv uden tag) og på trin 4 (gemt derfra); Overview: flammen orange med skiftende transform; id-test som i BUGS.md.

## [0.68.0 build 0104] — 2026-10-17 — T-stykke og kryds består af rør (eget løbelys pr. rør)

- `frontend/src/lib/symbols.ts` — `FITTING_LEGS`: T-stykket er *Tilløbsrør 1* (`tilloeb1`), *Tilløbsrør 2* (`tilloeb2`) og *Midterrør* (`midte`, starter ved gennemløbets kant); krydset er *Rør 1–4*. Tegneretning: ind fra venstre, ud til højre og op/ned.
- `frontend/src/lib/symbolConfig.ts` — danske navne på rørene (`PART_LABEL`).
- `frontend/svgedit-host/scada-editor.js` — `splitFitting(id, legs)`: deler et T-stykke/kryds tegnet som én sti i rør (beholder id, navn, type, transform og den gamle stis farve/streg; ét fortryd-trin); markeringen fortæller `type` og `onePath`.
- `frontend/src/pages/DrawEditor.svelte` — knappen *Del i rør* for et T-stykke/kryds med én sti; advarer, hvis opsætningen har animationer på den gamle sti.
- Manual (04, 05, 07). Tests: `symbols.test.ts`. **Set i browseren** lokalt: et T-stykke som i "varme" (én relativ sti, lyserød) → *Del i rør* → tre rør med navne og samme farve; Ctrl+Z/Ctrl+Y; guiden tilbyder Hele symbolet, Tilløbsrør 1, Tilløbsrør 2, Midterrør; Overview med løbelys pr. rør (gennemløbet synkroniseret, midterrøret efter sin egen retning).

## [0.67.0 build 0103] — 2026-10-17 — Løbelys: den indstillede retning har forrang

- `frontend/src/lib/flowChain.ts` — ingen automatisk vending efter flertallet (feltet `flip` er fjernet); `fits()`: to ender kobles kun, når lyset løber ind i samlingen fra den ene del og ud i den anden. Synkroniseringen (fælles koordinat, flertallets lyslængde/fart) er uændret for de dele, der kobles.
- `frontend/src/lib/animate.ts` — hver lysstreg kører i den indstillede retning; et T-stykkes ben får retningen fra "ud fra/ind mod midten".
- `frontend/src/manual/05-bindinger-og-animationer.md` — afsnittet om løbelys over flere rør.
- Tests: `flowChain.test.ts`. **Set i browseren** lokalt: forløb med et lodret rør tegnet nedefra — uden *Vend retning* kører det modsat ved sine to samlinger (som indstillet) og synkroniseres ikke dér; med *Vend retning* passer alle fire samlinger og er synkroniserede.

## [0.66.1 build 0102] — 2026-10-17 — fix: højreklikmenuen i Tegn lukker efter et valg

- `frontend/svgedit-host/scada-editor.js` — `hookContextMenu()`: SVG-Edits højreklikmenu lukkes, når et punkt er valgt (efter editorens egen håndtering), ved Escape og når vinduet mister fokus. Før stod den åben, og et nyt højreklik oven på den ramte menuen i stedet for tegningen. **Set i browseren** (Chrome og Firefox): 6 runder kopiér/indsæt via menuen på rør, bøjning og rektangel — alle rigtige. Se BUGS.md.

## [0.66.0 build 0101] — 2026-10-17 — Symbol: Varmepumpe

- `frontend/src/lib/symbols.ts` — `varmepumpe` (Rør og VVS): aggregat med ventilator (delen `rotor`, tegnet om sit eget centrum uden transform, så "Roterer" drejer den på stedet), varmeveksler-slynge, "VP" og driftslampe (delen `lampe`).
- `frontend/src/lib/symbolConfig.ts` — betjening: start/stop (som pumpe og ventilator); guidens forslag: rotoren drejer og lampen bliver grøn ved drift (tagget vælges i trin 4).
- `frontend/src/lib/symbolSuggest.ts` — "Erstat med symbol": en tegnet del med teksten "varmepumpe"/"varme pumpe" foreslår varmepumpen først.
- `frontend/src/manual/07-symbolbibliotek.md` — genereret med varmepumpen.
- Tests: `libraryDefaults.test.ts`, `symbolSuggest.test.ts`. **Set i browseren** lokalt: paletten (søg "varme"), indsat i Tegn med delene rotor og lampe, og i Overview med drift tændt: rotoren drejer (`hv-spin`), lampen grøn.

## [0.65.1 build 0100] — 2026-10-17 — fix: det øverste midtergreb strækker i stedet for at flytte

- `frontend/svgedit-host/scada-editor.css` — `#selectorGrip_rotateconnector { pointer-events: none; }`: drejegrebets forbindelsesstreg lå oven på det øverste midtergreb, så et træk dér flyttede elementet. Test i `svgeditPatch.test.ts`. **Set i browseren** (Chrome og Firefox) på rør som i "varme": vandret sti, lodret sti (bredde 0), skaleret sti og drejet biblioteksrør kan nu strækkes i begge ender. Se BUGS.md (også en åben post om drejede rør).

## [0.65.0 build 0099] — 2026-10-17 — Løbelys i T-stykkets afgrening starter ved gennemløbets kant

- `frontend/src/lib/flowChain.ts` — `trimInnerEnds()`: en delsti der starter eller slutter inde på en anden delsti (lige stykke) i samme figur, forkortes med en halv stregbredde langs sit første/sidste lige stykke; kryds, ender der mødes, buer og for korte stykker røres ikke.
- `frontend/src/lib/animate.ts` — `buildDashes()` bruger den på delte stier. Kun lyslaget ændres — symbolet i tegningen er uændret, så det virker også for T-stykker, der allerede er sat ind.
- Tests: `flowChain.test.ts` (+4).

## [0.64.2 build 0098] — 2026-10-17 — fix: løbelys kobles kun til de nærmeste ender

- `frontend/src/lib/flowChain.ts` — `chainPhases()`: en ende kobles kun til ender højst 1 enhed længere væk end den nærmeste (kort rør mellem T-stykke og bøjning). Tests: `flowChain.test.ts` (+2). Se BUGS.md.

## [0.64.1 build 0097] — 2026-10-17 — fix: løbelys-forløb med forskellig lyslængde og T-stykker

- `frontend/src/lib/flowChain.ts` — `Piece`/`Phase` har lyslængde og fart; forløbet bruger flertallets (uafgjort → første del). `splitSubpaths()` deler en sti i delstier med absolut start (også relative stier som SVG-Edit gemmer dem).
- `frontend/src/lib/animate.ts` — `flowGroup()` uden lyslængde/fart; `buildDashes()` deler stier med flere delstier; hver lysstreg bruger forløbets lyslængde og fart.
- Tests: `flowChain.test.ts` (+4). Se BUGS.md.

## [0.64.0 build 0096] — 2026-10-17 — Sammenhængende løbelys over flere rør og bøjninger

- `frontend/src/lib/flowChain.ts` (ny, ren): `chainPhases()` samler løbelys-dele, hvis ender rører hinanden (samme gruppe), til forløb med én fælles koordinat g, og ensretter retningen efter flertallet (indstillet retning × tegneretning; uafgjort → første del; T-stykkers ben vendes aldrig). `dashOffset()` giver stiplingens forskydning, så mønstret fortsætter over samlingerne.
- `frontend/src/lib/animate.ts` — `buildDashes()` (fælles for måling og tegning); løbelys registreres pr. tegning med en gruppe (`flowGroup()`: tag, retnings-tag, tilstand, længde, fart); delene måles i tegningens koordinater (`getTotalLength`/`getPointAtLength`, uden zoom); hver lysstreg får sin forskydning og evt. vendt retning; nye medlemmer regner kørende løbelys om (samlet pr. opdatering). Stier med flere delstier (fx T-stykke uden valgt rør) og lukkede figurer kører som før.
- Tests: `flowChain.test.ts` (8, bl.a. at mønstret er det samme set fra begge sider af hver samling). **Set i browseren** lokalt: rør tegnet højre→venstre, bøjning, lodret rør tegnet nedefra, rør, strakt rør (scale 2): målt ved 4 samlinger × 15 tidspunkter — før: lys/mørk sprang 17 gange og 2 samlinger kørte modsat (30/60); efter: 1 spring (en overgang lige i samlingen) og ingen modsat retning.

## [0.63.3 build 0095] — 2026-10-17 — fix: afslutter fejlsøgningen af "Indsæt opsætning" i Firefox

- Jan har bekræftet i Firefox, at *Indsæt opsætning* i et symbol uden navn virker med spørgsmålene på siden (v0.63.2.1). BUGS.md: de to poster lukket. Ingen kodeændringer ud over versionen.

## [0.63.2.1 build 0094] — 2026-10-17 — debug: spørgsmål på siden i stedet for browserens confirm/prompt (Firefox)

- `frontend/src/lib/ask.ts` (ny) — `ask()` / `askText()`: spørgsmål i en kø, besvares i siden; `AskDialog.svelte` (ny) viser køens første (Enter/Escape, fokus på OK eller feltet) og sættes ind én gang i `App.svelte`.
- Alle 21 `confirm()` og den ene `prompt()` er skiftet til `askUser()`/`askText()`: `DrawEditor`, `Editor`, `SymbolGuide`, `SymbolConvert`, `Plcs`, `Schedules`, `Tags`, `Trends`, `Update`, `Users`, `drawingDelete.ts` (slet-knap som farlig handling). Synkrone funktioner der spørger, er gjort asynkrone (`confirmDiscard`, `startNew`, `select`, skabelon-knapperne i guiden).
- Tests: `ask.test.ts`. **Set i Firefox** (Playwright): kopi af "varme" v36 på serveren — med browserens dialog afvist skete der stille ingenting (genskabt); lokalt med den nye dialog: Annullér lader elementet være uden navn, OK navngiver og indsætter; slet tag og "Kassér ændringer?" i Tegn virker; ingen browserdialoger. Se BUGS.md (åben til Jan bekræfter).

## [0.63.2 build 0093] — 2026-10-17 — debug: indsæt i symbol uden navn (gammel tegneeditor, skjulte fejl)

- `frontend/scripts/versionHost.mjs` (ny) + `copy-svgedit.mjs` — værtens filer får `?v=<build>` i deres adresser (importer, script, stylesheet), og buildnummeret bygges ind i værten (`window.scada.build`).
- `frontend/src/pages/DrawEditor.svelte` — editoren indlæses som `scada-editor.html?v=<build>`; melder fejl, hvis editorens build ikke er sidens; `guarded()` viser enhver fejl i *Kopiér/Indsæt opsætning* og *Opsæt de valgte samlet* (med hint ved en forældet editor).
- `backend/app/services/updates.py` — opdatering godtager debug-versioner `MAJOR.MINOR.PATCH.D` (CLAUDE.md); 0.63.1.1 er nyere end 0.63.1. (Denne version hedder 0.63.2, fordi den installerede server endnu ikke godtager fire tal.)
- Tests: `versionHost.test.ts`, `test_updates.py`. **Set i browseren** lokalt: værtsfiler hentes med `?v=0093`; en editor med build 0001 giver beskeden "Tegneeditoren er en ældre version … Ctrl+F5"; en editor uden `nameElements` giver "Indsæt opsætning fejlede: …" i stedet for ingenting; indsæt i elementer uden navn virker. Se BUGS.md (åben).

## [0.63.1 build 0092] — 2026-10-17 — fix: gammel side efter opdatering, dubletnavne ved kopi

- `frontend/vite.config.ts`, `src/globals.d.ts`, `src/lib/staleCheck.ts` (ny) — versionen fra `version.json` bygges ind (`__APP_VERSION__`, `__APP_BUILD__`); `isStale()` sammenligner med serverens.
- `frontend/src/App.svelte` — tjekker `/api/health` hvert minut og når fanen bliver synlig; banner "SCADA er opdateret … Genindlæs" (også i driftpanelet).
- `backend/app/main.py` — `FrontendFiles`: `Cache-Control: no-cache` for index.html, SVG-Edit-værten og andre filer uden hash; `public, max-age=31536000, immutable` for `assets/`.
- `frontend/svgedit-host/names.js` — `nextFreeName()`; `scada-editor.js` — `renameCopies()` efter indsæt/dupliker, så kopier får et ledigt navn.
- Tests: `tests/test_frontend_cache.py`, `staleCheck.test.ts`, `names.test.ts`. **Set i browseren** lokalt: dupliker "Bøjning 90° 6" → "… 8" (7 optaget), kopiér/indsæt → "… 9", fortryd fjerner kopien; banneret vises, når serveren melder en anden version. Se BUGS.md.

## [0.63.0 build 0091] — 2026-10-17 — Opsæt flere symboler samlet i Tegn

- `frontend/src/lib/symbolCopy.ts` — `configSignature()` (opsætningen uafhængigt af symbolets egne id'er: dele efter biblioteksnavn; type og nøglelås tæller ikke), `describeConfig()`, `configGroups()`, `memberNames()`.
- `frontend/src/lib/GroupBasis.svelte` (ny) — *Vælg udgangspunkt*: de forskellige opsætninger blandt de valgte med medlemmer; nævner dem uden opsætning og uden navn.
- `frontend/src/lib/SymbolGuide.svelte` — gruppetilstand (`group`): overskrift "Opsæt N symboler samlet", note om hvem der får opsætningen, *Gem i alle N* gemmer udgangspunktet og kopierer det til de andre (overskriver); det der ikke kunne overføres, vises i guiden, som så bliver åben. *Fjern konfiguration* og *Gem og anvend på flere* skjules i gruppetilstand.
- `frontend/src/pages/DrawEditor.svelte` — *Opsæt de valgte samlet (N)* ved flervalg: gemmer/udgiver først, henter de valgtes opsætninger, spørger om udgangspunkt når der er flere forskellige, navngiver elementer uden navn efter udgangspunktet, og åbner guiden i gruppetilstand.
- Tests: `symbolCopy.test.ts`. **Set i browseren** lokalt: 2 rør (opsætning A), bøjning (B), T-stykke (ingen) og et element uden navn → dialogen viste 2 opsætninger, B valgt → alle 5 fik B, elementet uden navn blev "Bøjning 1_1"; med en pumpe i markeringen blev guiden åben med "Pumpe 1: … Løbelys kræver streger", og de 5 andre fik opsætningen.

## [0.62.0 build 0090] — 2026-10-17 — Indsæt opsætning navngiver elementer uden navn

- `frontend/svgedit-host/names.js` (ny, ren): `numberedNames(base, count, used)` — "<base>_1", "<base>_2" … med ledige numre, basen forkortet så navnet holder sig inden for 60 tegn.
- `frontend/svgedit-host/scada-editor.js` — `nameElements(ids, base)`: navngiver elementer uden navn i tegningens rækkefølge; ét fortryd-trin.
- `frontend/src/lib/symbolCopy.ts` — `pasteTargets()` returnerer nu også de valgte uden navn (`unnamed`) og uden id (`noId`).
- `frontend/src/pages/DrawEditor.svelte` — *Indsæt opsætning*: valgte elementer uden navn får (efter et spørgsmål) kildens navn + løbenummer og derefter opsætningen; tegningen gemmes og udgives med de nye navne. Knappen vises nu også, når ét element uden navn er valgt. `ensurePublished()` kan springe sit eget spørgsmål over, når brugeren allerede er spurgt.
- Tests: `names.test.ts`, `symbolCopy.test.ts`. **Set i browseren** lokalt: kilde "varme pumpe tilgang" med "_1" optaget → ét element uden navn blev "_2"; to uden navn (valgt i omvendt rækkefølge) + et navngivet → "_3"/"_4" i tegningens rækkefølge, alle tre fik opsætningen.

## [0.61.0 build 0089] — 2026-10-17 — Farver på valgte symboler i Tegn

- `frontend/svgedit-host/colors.js` (ny, ren): `normColor()` (#rgb, #rrggbb, rgb(), navngivne → #rrggbb; none/url/currentColor → ingen), `colorsOf()`, `collectColors()`, `recolorAttrs()` (fill/stroke i attributter og style; øvrige style-egenskaber bevares).
- `frontend/svgedit-host/scada-editor.js` — `selectionColors()` og `recolorSelection(from, to)`: gennemgår de valgte elementer og alle deres dele; ændringen er ét fortryd-trin (`ChangeElementCommand` i en `BatchCommand`) og markerer tegningen som ændret.
- `frontend/src/pages/DrawEditor.svelte` — feltet *Farver* i *Valgt element* (ét eller flere valgte): en farvevælger pr. farve i markeringen (højst 12 vist) med antal brug.
- Tests: `src/lib/colors.test.ts`. **Set i browseren** lokalt: 6 rør/fittings valgt → én farve (#555) → skiftet til blå i alle; tegningen markeret "ikke gemt"; fortryd giver #555 igen; pumpen (ikke valgt) urørt.

## [0.60.0 build 0088] — 2026-10-17 — Kopiér/indsæt symbolopsætning i Tegn

- `frontend/src/pages/DrawEditor.svelte` — knapperne *Kopiér opsætning* (ét valgt symbol; kontrollerer at det har en opsætning i den udgivne version) og *Indsæt opsætning* (ét eller flere valgte symboler; bruger `POST …/symbols/{element}/copy`). Spørger før symboler med opsætning overskrives; elementer uden navn springes over; problemer pr. symbol vises som fejl. "Gem og udgiv først" er trukket ud i `ensurePublished()`, som guiden og indsæt deler.
- `frontend/src/lib/symbolCopy.ts` — `pasteTargets()` og `pasteReport()` (rene, testet i `symbolCopy.test.ts`).
- **Set i browseren** lokalt: kopiér fra et symbol uden opsætning giver en forklaring; indsæt i ét rør, i flere (rør, bøjninger, T-stykke; spørgsmål før overskrivning af en bøjning; pumpen afvist med "Løbelys kræver streger"), og med ikke-gemte ændringer (tegningen gemmes og udgives først).

## [0.59.0 build 0087] — 2026-10-17 — Kopiér symbolopsætning til flere symboler

- `backend/app/services/svg_sanitize.py` — `named_symbols()`: tegningens symboler (bibliotekstype eller navn) i dokumentrækkefølge.
- `backend/app/services/symbols.py` — `map_config()` (ren): oversætter en opsætning til et andet symbol — animationer på hele symbolet følger med, del-animationer oversættes efter `data-hv-pid` og springes ellers over med en note; nøglelåsen nulstilles. `SymbolService.list_symbols()` og `copy_to()`: kilden skal have en gemt opsætning (409), hvert mål valideres som et almindeligt gem (inkl. logikblokke brugt af andre ved overskrivning), mål med opsætning springes over uden `overwrite`, fejl i ét mål stopper ikke de andre.
- `backend/app/api/symbols.py` — `GET /api/drawings/{id}/symbols` og `POST /api/drawings/{id}/symbols/{element}/copy` (tekniker; højst 500 mål; audit `symbol.copy`).
- `frontend/src/lib/symbolCopy.ts` + `SymbolCopy.svelte` — dialogen *Anvend opsætningen på flere*: søgning, *Alle af samme type*, *Alle rør og fittings*, *Vælg viste*, *Ryd*, mærket "har opsætning", *Overskriv*-hak og resultattabel (kopieret / sprunget over / fejl med noter).
- `frontend/src/lib/SymbolGuide.svelte` — knappen *Gem og anvend på flere …* (gemmer først med samme kontrol som *Gem*); lukkes guiden derefter, opdateres siden som efter et gem.
- Tests: `tests/test_symbol_copy.py` (9), `symbolCopy.test.ts` (3). **Set i browseren** lokalt: rør → 2 rør, 2 bøjninger og et T-stykke; den bøjning der allerede havde en opsætning, blev sprunget over.

## [0.58.0 build 0086] — 2026-10-17 — Erstat med symbol: ventilens akse og bedre ventilforslag

- `frontend/svgedit-host/snap.js` — `centroid()`, `axisAngle()` (aksen gennem to punkter, 0–180°, uden retning) og `turnAxis()` (korteste drejning så et symbols akse ligger langs målaksen).
- `frontend/svgedit-host/scada-editor.js` — `trianglesIn()`/`valveAxisOf()`: aksen gennem en ventils to trekanter i tegningens koordinater (også for en markering af løse dele); `describeSelection()` leverer `axisAngle`; `replaceSelected({ axisNative })` drejer ventilsymbolet efter aksen (målt før de gamle dele fjernes).
- `frontend/src/lib/symbolSuggest.ts` — `NATIVE_AXIS` (ventil, kugleventil, motorventil, magnetventil, reguleringsventil ligger vandret) og kontraventilen i `NATIVE_DIRECTION`; forslag: én prik → **ventil** (+ regulerings-, sikkerheds-, motor-, kugleventil), prik + motorcirkel → **motorventil**, trekant med tværstreg → **kontraventil**, to løse trekanter + prik → **ventil/reguleringsventil**. Se BUGS.md.
- `frontend/src/lib/SymbolReplace.svelte` — valget "Drej symbolet efter den tegnede ventils akse (vandret/lodret)".
- Tests: `snap.test.ts` (akse og drejning), `symbolSuggest.test.ts` (ventilforslagene). **Afprøvet i browseren** på en lokal kopi af "varme" version 13: AVTB, AVTA ×2 og Laddomat → reguleringsventil (lodrette drejet 90°), Bypass → manuel ventil, to sikkerhedsventiler, kontraventil drejet 180° efter trekanten; den stiplede følerlinje bevaret.

## [0.57.0 build 0085] — 2026-10-16 — Erstat med symbol: flere dele samlet, og spejlvending

Rettelse efter at Jan opdagede, at motorventilerne i "varme" ikke var konverteret (se BUGS.md).

- `frontend/svgedit-host/scada-editor.js` — `describeSelection()` og `replaceSelected()` håndterer **flere valgte dele som én enhed** (samlet boks i tegningens koordinater, samlede figurantal, alle id'er); `selectByIds()`; `replaceSelected({ mirror })` spejlvender symbolet vandret om midten og **vender hver tekst tilbage om sin egen midterlinje**, så bogstaverne ikke spejles; `uniqueNameIn(base, except)` ser bort fra selve symbolet (falsk " 2" i navne).
- `frontend/src/lib/symbolSuggest.ts` — forslag til en markering af flere løse dele: ≥ 3 stier, ≥ 2 ellipser og ≥ 1 streg i ventilstørrelse → **3-vejs motorventil** (88), AB i midten (50), motorventil (40).
- `frontend/src/lib/SymbolReplace.svelte` + `pages/DrawEditor.svelte` — knappen **Erstat markeringen med symbol …** når flere dele er valgt, og valget **Spejlvend vandret (symbolets bogstaver spejles ikke)**.
- Manualen: afsnittet *Erstat tegnede dele med symboler* opdateret (flere dele, spejlvend).
- Tests: `symbolSuggest.test.ts` (flere løse dele → 3-vejs motorventil; for få figurer/forkert størrelse → intet). **Afprøvet i browseren** på en lokal kopi af "varme": MVS1 (10 dele) og MVS2 (10 dele, spejlvendt) erstattet af 3-vejs motorventil på rette sted og i rette størrelse, A/B/AB og M med rigtig læseretning, ingen af de gamle dele tilbage, navne uden falsk " 2".

## [0.56.0 build 0084] — 2026-10-16 — Erstat med symbol: pumpens retning aflæses

- `frontend/svgedit-host/snap.js` — `pathVertices()` (M/L/H/V/Z, relativ og absolut; kurver giver null), `triangleApex()` (ligebenet trekant → toppen og retningen fra grundlinjens midte; ligesidet giver null), `directionAngle()` (retningen efter en matrix) og `turnTo()` (drejning så et symbols retning rammer målet).
- `frontend/svgedit-host/scada-editor.js` — `describeSelection()` leverer `apexAngle` (delens ENE trekant, målt i tegningens koordinater inkl. alle lags drejning; null ved ingen eller flere); `replaceSelected()` tager `apexNative` og drejer hvert nyt symbol, så dets trekant peger som den tegnede — pr. del ved "erstat alle lignende". Retningen måles **før** den gamle del fjernes (en frakoblet del har ingen matrix).
- `frontend/src/lib/SymbolReplace.svelte` + `symbolSuggest.ts` — valget "Drej symbolet, så trekanten peger samme vej som den tegnede (N°)" for retningsgivende symboler (`NATIVE_DIRECTION`: pumpen peger mod højre ved 0°).
- Manualen: afsnittet om retning opdateret.
- Tests: `snap.test.ts` (stiparsing med pumpestierne fra "varme", trekantens top, retning efter matrix, drejning). **Afprøvet** på en lokal kopi af "varme": de fire pumpers trekanter pegede −90°/90°/−90°/90° før og peger efter erstatning samme vej (symbolerne har rotate(−90)/rotate(90)); et første forsøg målte retningen efter fjernelsen og gav −90° til alle — fundet af afprøvningen og rettet.

## [0.55.1 build 0083] — 2026-10-16 — fix: Erstat med symbol rører ikke dele med bindinger

- `frontend/svgedit-host/scada-editor.js` — `describeSelection()` leverer `similarGroups` (id'er pr. lignende del) og `ids` tæller nu også de tekster der ligger inde i delen; `replaceSelected()` tager `protectIds` og **springer lignende dele over**, hvis noget af det der ville forsvinde har en binding (meldes som `skipped`). Selve den valgte del erstattes som valgt.
- `frontend/src/pages/DrawEditor.svelte` + `lib/SymbolReplace.svelte` — henter bindingerne i den gemte version, giver dem videre som beskyttelse, advarer om bindinger på tekster/underelementer der ikke følger med, og viser "N lignende dele med bindinger blev sprunget over".
- Fundet ved prøvekørsel (kun læsning) på den rigtige "varme"-tegning; se BUGS.md.

## [0.55.0 build 0082] — 2026-10-16 — Erstat tegnede dele med symboler

Ønske fra Jan: konvertér "varme"-tegningen til at bruge symboler fra systemet. Metode (valgt af Jan): værktøj med forslag + resultatet som ny kladde-version.

- `frontend/svgedit-host/scada-editor.js` — `describeSelection()` (opbygning, størrelse, drejning, farver, tekster inde i delen, lignende dele, alle id'er), `replaceSelected()` (samme midte, størrelse og drejning — matrixen i tegningens koordinater uden zoom —, id kan beholdes, teksten kan overtages og den gamle fjernes, stræk til at fylde, **alle lignende** (samme størrelse, eller alle af samme slags uanset størrelse/drejning), navn pr. del efter dens egen tekst, alt i ét fortryd-trin), `ungroupSelected()` (en stor gruppe kan opløses, så dens dele kan vælges), `selectById()`; `buildSymbolNode()` er fælles med `insertSymbol`.
- `frontend/src/lib/symbolSuggest.ts` (ny) — forslag ud fra delens form, målt på den rigtige "varme"-tegning: afrundet ufyldt rektangel/sti i pillestørrelse → **statusfelt**; cirkel + trekant → **pumpe**; ventil med stilk og motorcirkel → **motorventil** (m.fl.); lille cirkel med streg → **føler**; stort fyldt rektangel → **tank/kedel**; kedelgruppe → **kedel**; tykke streger → **rør/bøjning**.
- `frontend/src/lib/SymbolReplace.svelte` (ny) + `pages/DrawEditor.svelte` — knappen **Erstat med symbol …** (og **Opløs gruppen** for en gruppe med mere end 20 dele); dialogen med forslag, søgning i hele biblioteket, navn, behold id, overtag tekst, stræk, "andre dele af samme slags", og en advarsel om bindinger på underelementer, som ikke følger med.
- Manualen (Tegninger og Tegn) beskriver værktøjet, med billede (`tegn-erstat.png`).
- Tests: `symbolSuggest.test.ts` (forslagsreglerne med opbygninger fra "varme"). **Afprøvet i browseren** på en lokal kopi af "varme": gruppen opløst (226 dele), 30 etiketter (22 rektangler + 8 stier) → statusfelt med overtaget tekst og eget navn, 4 pumper, 18 følere, tank og kedel erstattet på rette sted og i rette størrelse; ét Ctrl+Z gendanner alle; resultatet gemt som kladde-version 2 med alle symboler, navne og tekster.
- **Kendt begrænsning:** et symbols *retning* (fx pumpens trekant, ventilens akse) er tegnet ind i den gamle del og kan ikke aflæses sikkert; efter erstatning kan symbolet skulle drejes (15°-trin, Shift = fri). Bindinger på underelementer følger ikke med (advarsel vises); bindinger på selve delen følger med, hvis id'et beholdes.

## [0.54.2 build 0081] — 2026-10-16 — fix: løbelys uafhængigt af rørets skalering; fang til gitter er absolut

- `frontend/src/lib/animate.ts` — **løbelys**: lysets længde (`dash`) og fart (`speed`) er nu i tegningens enheder, uanset hvordan røret er skaleret. Stregen måles i tegningen (først efter at laget er sat ind): rørets samlede matrix (egen + forfædres transform) divideret med en probe under roden (så tegningens viewBox/zoom ikke tæller med), og skaleringen langs røret (rect/line: langs linjen; kurve/bøjning: geometrisk middel) omregner lysstykket og forskydningen til rørets lokale enheder. Uden mulighed for at måle (jsdom, uden for skærmen) er faktoren 1 som før. Rør der ikke er skaleret, ser ud som før.
- `frontend/svgedit-host/scada-editor.js` + `snap.js` — **fang til gitter er absolut**: `gridCorrection()` lægger de valgte elementers øverste venstre hjørne på nærmeste gitterpunkt efter en flytning med musen, **indsæt** (`pasteElements`), **duplikér** (`cloneSelectedElements`, ikke tasternes 1–5 px finjustering) og isætning af et symbol fra paletten; fang til objekter vinder i sin retning. Boksen måles nu som geometri i tegningens koordinater (`getBBox` + matrix uden zoom) i stedet for skærmplaceringen. Matrix-hjælpere (`multiplyMatrix`, `invertMatrix`, `transformBox`, `identityMatrix`).
- Manualen: Løbelys og Tegnehjælp opdateret.
- Tests: `animate.test.ts` (lengthScale, strakt/drejet/lodret rør, skalering på tværs, tegningens egen visning tæller ikke), `snap.test.ts` (gridCorrection — også at en kopi havner på samme gitterpunkter —, matricer). **Afprøvet med rigtig mus** i browseren: træk fra (593,337) med fang til gitter → (600,350); duplikat af objekt uden for gitteret → på gitteret; nyt symbol → på gitteret. Ctrl+C/Ctrl+V kunne ikke afprøves i en testbrowser (kræver udklipsholder), men bruger samme hook som duplikering.

## [0.54.1 build 0080] — 2026-10-16 — manual: billeder af Tegnehjælp

- `frontend/public/manual/tegn-gitter.png` (nyt) og et nyt `tegn.png` med rækken Tegnehjælp; billedet er indsat i kapitlet *Tegninger og Tegn*. Verificeret på testserveren efter OTA-installation af 0.54.0: rotationsrettelsen er med i den leverede `Editor.js`, og gitteret ligger over det rigtige anlæg.

## [0.54.0 build 0079] — 2026-10-16 — Tegnehjælp: gitter, fang til gitter/objekter og rotation i 15°-trin

- `frontend/svgedit-host/scada-editor.js` — **gitter** tegnet som et gennemsigtigt lag OVENPÅ tegningen (SVG-Edits eget gitter lå under og var skjult bag baggrundsrektanglet), afstand 5/10/20/25/50 med kraftigere linje for hver 5.; følger zoom og rulning; **fang til gitter** (SVG-Edits egen `gridSnapping`/`snappingStep`); **fang til objekter**: ved museslip efter et træk lægges det flyttede objekt kant mod kant eller midte mod midte med nærmeste objekt inden for 8 skærm-pixel (kan fortrydes). SVG-Edit sender ikke `changed` efter en flytning, så der lyttes på museknappen. API: `window.scada.setGuides({ grid, snapGrid, snapObjects, step })`. `ext-grid` er fjernet.
- `frontend/svgedit-host/snap.js` (ny) — de rene beregninger (`unionBox`, `snapToObjects`, `isDrag`; piletast-justeringer under 3 px fanges ikke).
- `frontend/scripts/copy-svgedit.mjs` — **rotation i 15°-trin, Shift = fri rotation** (SVG-Edit er normalt fri og snapper til 45° med Shift): tekstrettelse i den medfølgende editor-fil; passer teksten ikke (ny SVG-Edit-version), stopper kopieringen med en klar fejl.
- `frontend/src/pages/DrawEditor.svelte` — rækken **Tegnehjælp** under værktøjslinjen (Vis gitter, Fang til gitter, Gitterafstand, Fang til objekter, rotationshint); huskes i browseren (`draw.guides`).
- Manualen (kapitlet Tegninger og Tegn) beskriver det.
- Tests: `snap.test.ts` (fang-beregningerne), `svgeditPatch.test.ts` (rotationsrettelsen og værtssiden er med i den leverede kopi). **Afprøvet med rigtig mus** i browseren: gitter synligt og flugtende med linealen, flytning i 10-trin med fang til gitter, objekt fanget præcis kant mod kant, rotation 30°/75°/−15° uden Shift og ≈ fri med Shift.

## [0.53.0 build 0078] — 2026-10-16 — Skærmbilleder i brugermanualen

- `frontend/tools/manual-screenshots.mjs` (nyt; `npm run manual:screenshots`) — tager billederne fra en kørende server med Playwright (devDependency, Apache-2.0): logger ind som admin, åbner siderne og guiden og gemmer PNG i `frontend/public/manual/`. **Kun læsning** — der trykkes aldrig Gem, og intet skrives eller slettes. Kan afgrænses med `ONLY=navn,navn`. Fold tag-redigeringen ud, så alle felter ses; begræns symbolpaletten til 760 px.
- `frontend/public/manual/*.png` (29 billeder, 1,7 MB) og henvisninger i kapitlerne (menu, Drift, PLC'er og tags, Tegninger og Tegn, Bindinger, guidens 6 trin + logik + hurtig opsætning, Ugeprogrammer, System).
- `frontend/src/lib/manual.ts` — billeder bliver til `<figure>` med billedtekst (alt-teksten, escapet), uden `<p>` omkring; `Manual.svelte` — klik på et billede åbner det stort (Escape/klik lukker), billederne tilpasses bredden.
- Manualen rettet efter skærmbillederne: tag-formularens felter hedder *Skrivbar fra Overview* og *Kræv bekræftelse ved skrivning*.
- Tests: `manualImages.test.ts` (alle henvisninger har en fil >3 kB, ingen forældreløse filer, rene filnavne, billedtekster) og figur-rendering i `manual.test.ts` (fandt at en `<figure>` ellers ender i et tomt `<p>`).

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
