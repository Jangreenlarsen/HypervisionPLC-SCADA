# Changelog

Nyeste øverst. Format: `## [version build NNNN] — YYYY-MM-DD — beskrivelse`

---

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
