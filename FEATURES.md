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
- [ ] planned — Animation `move`
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
- [ ] planned — Raspberry Pi 4 deployment: Chromium-kiosk på lokal skærm (udskudt efter ønske — testserver 10.1.1.31 bruges indtil videre; install-script og systemd findes allerede)
- [x] done v0.8.0 — Backup/restore af hele SCADA-projektet (PLC-forbindelser uden adgangskoder, tags, tegninger med alle versioner, bindinger; ikke brugere): download/restore som JSON (admin), fuld validering før noget ændres, automatisk backup før restore, atomisk udskiftning med tilbagerulning, automatiske døgn-backups på serveren (7 gemmes)

### Tværgående
- [x] done v0.7.0 — Tag-valg som dropdown (grupperet pr. PLC, med kilde og enhed) i binding-editoren; ikke-skrivbare tags nedtonet ved klik-handlinger — genbruges i tegne-editoren (fase 4)
- [x] done v0.5.0 — TLS trin 1: nginx (TLS + WebSocket) foran uvicorn på 127.0.0.1 med selvsigneret certifikat (CN/SAN scada.laces.dk + IP), Secure-cookie, sikkerheds-headere; certifikat-stier klar til Let's Encrypt
- [ ] planned — TLS trin 2: Let's Encrypt-certifikat for scada.laces.dk med automatisk fornyelse — DNS hos one.com (intet API) → `_acme-challenge` CNAME til deSEC; værktøj (certbot-dns-desec / acme.sh / lego) afklares ift. CNAME-delegering
- [x] done v0.3.0 — Kildekode-link i web-UI'et (AGPL-3.0 §13), konfigurerbar URL til forks (`SCADA_SOURCE_URL`)
