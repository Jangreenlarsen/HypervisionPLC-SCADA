# Changelog

Nyeste øverst. Format: `## [version build NNNN] — YYYY-MM-DD — beskrivelse`

---

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
