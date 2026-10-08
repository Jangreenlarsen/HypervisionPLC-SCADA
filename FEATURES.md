# Features

Format: `[status] vX.X.X — beskrivelse`
Status: `planned` | `in-progress` | `done`

Faseplan og detaljer: [docs/RESEARCH_OG_DESIGN.md](docs/RESEARCH_OG_DESIGN.md#4-faseplan).

**Aftalt rækkefølge (Jan, 2026-10-08):** 1) Fase 4 tegne-editor (SVG-Edit, samme tag-dropdown som binding-editoren) → 2) Alarmer → 3) Trends. Raspberry Pi venter; testserver 10.1.1.31 bruges.

---

## Planlagte features

### Fase 1 — Backend og PLC-kommunikation
- [x] done v0.2.0 — Backend-skelet (FastAPI, SQLite, config, logging, serverer frontend statisk)
- [x] done v0.2.0 — Mock-PLC der efterligner HypervisionPLC REST API (login/Bearer, bulk-registre, skriv, 401/429, SSE)
- [x] done v0.2.0 — PLC-klient pr. PLC: login/token-fornyelse, bulk-poll-planlægger, rate-budget ≤ 5 req/s, backoff
- [x] done v0.2.0 — SSE-lytter mod PLC'ens `/api/events` med adaptiv poll-rate som fallback
- [x] done v0.2.0 — Flere PLC'er pr. installation (PLC-forbindelser i DB, adgangskoder i secrets-fil)
- [x] done v0.2.0 — Tag-model (kilde `plcN:type:addr[:datatype]`, skalering, enhed, skrivbar, min/max) + import fra PLC

### Fase 2 — Overview med live-værdier
- [x] done v0.3.0 — Upload af SVG med server-side sanering og versionering
- [x] done v0.3.0 — Overview-board: vis tegning og opdatér bindinger live via WebSocket (delta-frames)
- [x] done v0.3.0 — Kvalitetsvisning (stale/kommunikationsfejl) på bundne elementer

### Fase 3 — Bindinger
- [x] done v0.6.0 — Binding-editor: klik element (eller vælg i elementliste) → vælg tag + animation (text, fill, stroke, visible, blink, level, rotate, opacity) med parametre og live-forhåndsvisning
- [x] done v0.17.0 — Animation "Flyt" (`move`): elementet flyttes fra sin plads (ved min) til en forskydning dx/dy (ved max) efter værdien; kan kombineres med Rotation på samme element
- [x] done v0.7.0 — Klik-handling `click:goto` (navigér til anden tegning)
- [x] done v0.6.0 — Auto-forslag af bindinger ud fra element-id / inkscape:label
- [x] done v0.6.0 — Advarsel om forældreløse bindinger efter gen-upload

### Fase 4 — Tegne-editor
- [x] done v0.10.0 — SVG-Edit 7.4 indlejret som fuld tegne-editor (side "Tegn"): ny tegning, åbn version, gem kladde, gem og udgiv; element ↔ tag med samme tag-dropdown som binding-editoren
- [x] done v0.10.0 — Symbolbibliotek (pumpe, motor, ventil, tank, værdifelt, lampe, knap, rør) i ISA-101-stil
- [x] done v0.10.0 — Versioner, udgiv og rollback af tegninger (kladder ændrer ikke Overview; enhver version kan udgives igen)

### Fase 5 — Betjening og adgang
- [x] done v0.7.0 — Skrivning til PLC via klik-handlinger `click:write` (setpunkt-dialog med min/max, invers skalering, bekræftelse), `click:toggle`, `click:pulse` (server-styret nulstilling); kun hr/coil-tags markeret skrivbare; læs-tilbage efter skrivning med advarsel hvis PLC'en (fx ST) har overskrevet værdien; PLC'ens fejltekst (fx safe mode) vises til operatøren; rolle operator+ med bekræftelse og PLC-fejlbesked til operatør
- [x] done v0.4.0 — Brugere og roller (viewer/operator/engineer/admin) med sidste-admin-beskyttelse i backend: login med session-cookie (HttpOnly, SameSite=Strict), scrypt-hashede adgangskoder, låsning efter gentagne fejl-logins, tvunget skift af genereret admin-adgangskode, rollekrav på alle endpoints inkl. WebSocket (flyttet frem før TLS)
- [x] done v0.9.0 — Adgang pr. tegning (ønske fra Jan): viewer/operatør kan begrænses til udvalgte tegninger — håndhævet i backend for tegninger, tags, live-data (WebSocket) og betjening; operatører kan generelt kun betjene tags med en klik-handling i en tegning de har adgang til
- [x] done v0.7.0 — Audit-log over alle skrivninger og konfigurationsændringer (hvem, hvornår, hvad, gammel → ny, resultat) + side "Log"

### Fase 6 — Drift
- [x] done v0.11.0 — Alarmer: grænser HH/H/L/LL pr. tag med dødbånd og forsinkelse, til/fra-alarmer, PLC-kommunikationsalarm; tilstande aktiv/kvitteret/ophørt (ISA-18.2 forenklet) gemt i DB; historik; kvittering (operator+); alarmtæller i toppen, side "Alarmer", blink i tegningen; adgang pr. tegning respekteres; grænser i Tags og backup
- [x] done (v0.12.0) — Trends: historik pr. tag (slås til i Tags, minimumsinterval, ved ændring + keepalive, huller ved kommunikationsfejl) i separat `trends.db` med batch-skrivning og automatisk sletning (standard 30 dage); side "Trends" med uPlot-grafer, tidsvalg, live-opdatering, server-side nedsampling og CSV-eksport; adgang pr. tegning respekteres
- [x] done v0.13.0 — Tekst før/efter værdien i tekst-bindinger (ønske fra Jan): fx "Tank : " + værdi + " liter" → "Tank : 1002 liter"; vises også rundt om "—" når værdien mangler
- [x] done v0.14.0 — Flere animationer i én binding (ønske fra Jan, fx tekst + blink på "test01", hver med sine egne parametre): binding-editoren viser én binding pr. tag med tag-valg øverst og en eller flere animationer under; "+ Animation" tilføjer en animation der ikke allerede er brugt (tekst → blink → …); den automatiske binding bevares når man tilpasser/tilføjer. Lagres som én række pr. animation (ingen skemaændring)
- [x] done v0.15.0 — Udvidet symbolbibliotek i Tegn (ønske fra Jan): sektioner "Proces", "Rør og VVS" (90°/45°-bøjninger, T-stykke, kryds, reduktion, prop, flange, strømningspil, kontra-/kugle-/3-vejs-/motor-/magnet-/regulerings-/sikkerhedsventil, varmeveksler, filter, ekspansionsbeholder, radiator, ventilator, kedel, måleinstrumenter TT/PT/FT/LT, manometer, termometer) og "Elektrisk" (ledninger, kontakter NO/NC, trykknap, nødstop, kontaktor, relæspole, sikring, automatsikring, motorværn, motor 3~, frekvensomformer, transformer, strømforsyning, jord, signallampe, modstand, føler, hovedafbryder, PLC); søgning og sammenklappelige sektioner; forhåndsvisning skaleret efter hvert symbols egen størrelse
- [x] done v0.16.0 — Symbolsektion "Solcelleanlæg" (ønske fra Jan): solcellepanel, solcellestreng, sol, inverter, hybridinverter, MPPT-regulator, batteri (ladetilstand via Niveau), batteribank, DC-/AC-afbryder, overspændingsbeskyttelse, elmåler, elnet, forbrug/hus, elbillader, energiflow-pil
- [x] done v0.18.0 — Navigation på Overview: zoom (hjul/knapper/knib) og panorering i store tegninger, "tilpas"-knap (ønske fra Jan)
- [x] done v0.18.0 — Start-tegning på Overview: tekniker/admin vælger under Tegninger hvilken tegning der vises først; i samme fane huskes den sidst viste (ønske fra Jan)
- [x] done v0.19.0 — Betjeningssymboler i Tegn (ønske fra Jan): trykknap (puls), start/stop (til/fra), vippekontakt, drejeomskifter, auto/manuel-vælger, setpunkt-felt — vælg et tag i Tegn, så oprettes klik-handling + visning (lampe/vippe/greb/tekst) automatisk; klik-handlinger kun på skrivbare tags
- [x] done v0.20.0 — Backup af trend-historik (ønske fra Jan): download af et konsistent øjebliksbillede (.db.gz), indlæsning der fletter ind i den eksisterende historik, automatisk øjebliksbillede sammen med den daglige backup (de seneste gemmes)
- [ ] planned — Energirapporter: forbrug/produktion pr. dag/uge/måned fra tællere eller effekt, søjlediagram og CSV (ønske fra Jan)
- [ ] planned — Ugeprogrammer/tidsstyring: SCADA'en skriver værdier til PLC-tags efter et ugeskema (fx natsænkning), med undtagelser/ferie og audit (ønske fra Jan)
- [ ] planned — Raspberry Pi 4 deployment: Chromium-kiosk på lokal skærm (udskudt efter ønske — testserver 10.1.1.31 bruges indtil videre; install-script og systemd findes allerede)
- [x] done v0.8.0 — Backup/restore af hele SCADA-projektet (PLC-forbindelser uden adgangskoder, tags, tegninger med alle versioner, bindinger; ikke brugere): download/restore som JSON (admin), fuld validering før noget ændres, automatisk backup før restore, atomisk udskiftning med tilbagerulning, automatiske døgn-backups på serveren (7 gemmes)

### Tværgående
- [x] done v0.7.0 — Tag-valg som dropdown (grupperet pr. PLC, med kilde og enhed) i binding-editoren; ikke-skrivbare tags nedtonet ved klik-handlinger — genbruges i tegne-editoren (fase 4)
- [x] done v0.5.0 — TLS trin 1: nginx (TLS + WebSocket) foran uvicorn på 127.0.0.1 med selvsigneret certifikat (CN/SAN scada.laces.dk + IP), Secure-cookie, sikkerheds-headere; certifikat-stier klar til Let's Encrypt
- [ ] planned — TLS trin 2: Let's Encrypt-certifikat for scada.laces.dk med automatisk fornyelse — DNS hos one.com (intet API) → `_acme-challenge` CNAME til deSEC; værktøj (certbot-dns-desec / acme.sh / lego) afklares ift. CNAME-delegering
- [x] done v0.3.0 — Kildekode-link i web-UI'et (AGPL-3.0 §13), konfigurerbar URL til forks (`SCADA_SOURCE_URL`)
