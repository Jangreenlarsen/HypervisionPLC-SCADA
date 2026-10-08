# Changelog

Nyeste øverst. Format: `## [version build NNNN] — YYYY-MM-DD — beskrivelse`

---

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
