# SCADA-benchmark 2026-11-23 — v6.16.4 b0441

Commit: eb64f99 · Kriterie-version: 1 · Forrige rapport: ingen (nulpunkt) · UI set: demoen scada.laces.dk — Overview *varme* (deaktiveret) og *vandvaerk* (live) ved 1600 px, Alarmer og Trends ved 1600 px, Overview *varme* ved 500 px

Selvvurdering mod branchens forventninger (ISA-101, ISA-18.2/EEMUA 191, IEC 62443 m.fl.). Ikke en certificering og ingen sikkerhedsklassificering (SIL).

## 1. Resumé

| Gruppe | Score | Forrige | Δ | Kritiske (K) opfyldt |
|---|---|---|---|---|
| A. HMI-design | 79 % | – | – | 3 af 5 |
| B. Alarmstyring | 55 % | – | – | 3 af 5 |
| C. Styring og operatørhandlinger | 88 % | – | – | 3 af 3 |
| D. Data, trends og integration | 86 % | – | – | 3 af 3 |
| E. Cybersikkerhed | 83 % | – | – | 7 af 7 |
| F. Pålidelighed og drift | 83 % | – | – | 3 af 3 |
| G. Konfiguration og vedligehold | 86 % | – | – | 2 af 2 |
| **Samlet** | **79 %** | – | – | **24 af 28** |

Score = sum af vurderinger / (2 × relevante kriterier). U tæller som 0. Samlet: 104 af 132 point, 66 kriterier, ingen markeret – eller U.

Alarmstyring er det klart svageste område (55 %); resten ligger mellem 79 og 88 %.

## 2. Positionering

1. **Klar til nu:** små og mellemstore anlæg (vandværk, varmeanlæg, kedelrum) med en eller få HypervisionPLC'er, til almindelig drift, overvågning og betjening af ikke-sikkerhedskritiske anlæg.
2. **Bør endnu ikke bruges til:** anlæg med formelle alarmkrav (shelving, rationalisering og alarmrate efter ISA-18.2/EEMUA 191), sikkerhedskritiske funktioner, krav om redundans/failover og miljøer med krav om flerfaktor-login.
3. **Adskiller sig positivt fra typiske lette web-HMI'er** (vurdering): backend-håndhævede roller, audit af alle skrivninger, hash-kontrolleret OTA med rollback, hærdet service, omfattende tests og en indbygget tegneeditor med symbolstandard.
4. **Skal først til for næste niveau:** alarmstyring (B5, B6, B1, B7), derefter navigation og fast ramme (A1, A6) og driftsmodenhed (målt kapacitet på Pi'en, øvet gendannelse).

## 3. Styrker

1. **C1, C3, C5, C8** — roller håndhæves i backend, alle skrivninger auditeres (også afviste) og serialiseres pr. tag (`backend/app/api/auth.py:30-42`, `services/operate.py:265-325`, `test_operate.py`, `test_scope.py`).
2. **E1–E5, E8** — scrypt og lockout pr. bruger+IP, HttpOnly/SameSite=Strict-cookie, TLS 1.2/1.3 via nginx, skriv-kun hemmeligheder, hærdet service og SHA256-kontrolleret OTA med rollback (`services/auth.py:42-55`, `deploy/nginx-hypervisionplc-scada.conf:35`, `deploy/hypervisionplc-scada.service:8-18`, `deploy/apply-update.sh`).
3. **G3, F8, G7** — 975 backend-testfunktioner, 93 frontend-testfiler, mock-PLC og hook-håndhævet versionering og CHANGELOG (`backend/tests`, `.githooks/pre-commit`).
4. **A2, A4, A5** — symbolbibliotek med fælles standard, dæmpet palette og test af at kun palettens farver bruges (`frontend/src/lib/symbols.ts:112`, `symbols.test.ts:174-177`, `docs/SYMBOLSTANDARD.md`).
5. **F2, D4, A8** — kommunikationsfejl med timeout/backoff, tydelig status og synlig datakvalitet (`plc/client.py:67,171-197`, `frontend/src/app.css:116-119`, `test_runtime.py`).

## 4. Huller, rangeret

Rækkefølge: K før V før N, derefter laveste vurdering først; ved lighed efter ID. Højst 15 rækker; øvrige huller står i afsnit 6.

| ID | Pri | Hul | Evidens | Forslag | Indsats |
|---|---|---|---|---|---|
| A1 | K | Ingen område→detalje-navigation; flad tegningsliste | `pages/Overview.svelte:652`, `lib/navSymbols.ts:1-4` | Navigationssymboler/links mellem tegninger i tre niveauer | M |
| A6 | K | Fast ramme mangler bruger, ur og forbindelsesstatus på alle sider | `App.svelte:196-232`, `Overview.svelte:665`; set i UI | Bruger, tid og PLC-status i topbaren på alle sider | S |
| B1 | K | Tag-alarmer har kun høj/medium; Alarmer-siden viser tilstandskode (ON/COMM/SYS) i kolonnen Prioritet | `services/alarms.py:32-33`; set i UI (Alarmer, 1600 px) | Tre niveauer pr. alarm og en kolonne med selve niveauet | M |
| B4 | K | Historik kan kun filtreres pr. system; ingen søgning eller eksport | `pages/Alarms.svelte:55,140-152`, `api/alarms.py:48` | Tidsfilter, fritekst og CSV-eksport | S |
| B5 | V | Ingen shelving/undertrykkelse af alarmer | grep i backend og frontend: ingen forekomst | Shelving med begrundelse, varighed og audit | M |
| B6 | V | Ingen felter til konsekvens, handling og svartid | `services/tags.py`, `storage/db.py:278-281` | Felter pr. alarm, vist i *Forklar* | M |
| A3 | V | Farveuafhængighed er ikke testet | `lib/symbolUi.ts` (GLYPH), `docs/SYMBOLSTANDARD.md` §5 | Test af at tilstand kan aflæses uden farve | S |
| A9 | V | To-positionssymboler skifter direkte; ingen faceplate | `pages/Overview.svelte:350-354` | Faceplate-dialog pr. udstyr | L |
| A12 | V | Ingen mørk/natvisning; ved 500 px skalerer tegningen til meget små tekster | `App.svelte:144,371`; set i UI (Overview 500 px) | Natvisning og bedre zoom/ombrydning på smal skærm | M |
| B7 | V | Ingen alarmrate; top-N kun via valgfri LLM-hjælper | `services/metrics.py:78-80`, `assist_tools.py:154` | Alarm-KPI (rate, stående, top-N) på Status | M |
| B9 | V | Intet lydsignal | `pages/Alarms.svelte:115`, `app.css:153-158` | Valgfri lyd ved nye uanerkendte alarmer | S |
| B10 | V | Ændring af alarmgrænser auditeres uden gammel værdi og uden test | `api/routes.py:213-217` | Gammel og ny værdi i audit samt test | S |
| B11 | V | Notifikation uden eskalering | `services/notifier.py:1`, `test_notifier.py:131,576` | Eskalering, når en alarm ikke er anerkendt efter en tid | M |
| C4 | V | Driftsart (manuel/auto) er kun et PLC-tag eller symbol, ikke et eget begreb | `services/symbol_operate.py:82-93` | Fælles visning af driftsart på udstyr | M |
| D2 | V | Nedsampling er ikke påvist i lageret; kun tidsbegrænset opbevaring | `services/trends.py:40,151-155` | Aggregering ved lagring af gamle data | M |

## 5. Ændringer siden forrige

Ingen forrige rapport — dette er nulpunktet. Kriterie-version 1.

## 6. Detaljer pr. gruppe

Stier uden præfiks ligger under `backend/app/` (`services/`, `api/`, `plc/`, `storage/`) eller `frontend/src/` (`pages/`, `lib/`).

### A. HMI-design

| ID | Pri | Vurdering | Evidens | Note |
|---|---|---|---|---|
| A1 | K | 1 | `pages/Overview.svelte:652`, `lib/navSymbols.ts:1-4` | Flad tegningsliste; genveje kun til Alarmer/Trends/Energi |
| A2 | V | 2 | `app.css:1-19`, `lib/symbols.test.ts:174-177`, set i UI | Grå flader; farve forbeholdt alarm og afvigelse; palette testes |
| A3 | V | 1 | `lib/symbolUi.ts` (GLYPH), `docs/SYMBOLSTANDARD.md` §5 | Tilstandsglyffer findes; ingen test af farveuafhængighed |
| A4 | K | 2 | `lib/symbols.ts:112`, `lib/symbolSimLibrary.test.ts:17` | Bibliotek med fælles standard og test pr. symbol |
| A5 | V | 2 | `lib/animate.ts:23`, `lib/trendSymbols.test.ts`; set i UI (vandvaerk) | Enhed, decimaler, område og trendgraf i tegningen |
| A6 | K | 1 | `App.svelte:196-232`, `Overview.svelte:665`; set i UI | Alarmklokke og version altid; bruger kun i menu, intet ur |
| A7 | K | 2 | `lib/symbolOverlay.test.ts:28`, `lib/symbols.ts:144,170`, `services/symbol_operate.py:83` | Positionsmærke, fejl/låst og auto/manuel pr. symbol |
| A8 | K | 2 | `Overview.svelte:611,665`, `app.css:116-119`, `lib/animate.test.ts:100`; set i UI | Afbrudt forbindelse og dårlig kvalitet vises; deaktiveret tegning har banner |
| A9 | V | 1 | `Overview.svelte:350-354`, `lib/symbolUi.test.ts:10` | Dialog ved bekræftelse/setpunkt; to-positioner skifter direkte |
| A10 | N | 2 | `lib/viewport.test.ts:21`, `Overview.svelte:658-662` | Zoom, pan, tilpas og flere tegninger; ved 500 px bliver teksten meget lille |
| A11 | V | 2 | `FEATURES.md:92`, `test_drawings_api.py`, `test_svg_sanitize.py` | Upload og tegn med binding til tags uden kode |
| A12 | V | 1 | `App.svelte:144,371`; set i UI (500 px) | Ingen mørk visning; smal skærm virker, men tegningen bliver meget lille |

### B. Alarmstyring

| ID | Pri | Vurdering | Evidens | Note |
|---|---|---|---|---|
| B1 | K | 1 | `services/alarms.py:32-36`, `test_symbol_runtime.py:126-133`; set i UI | Tag-alarmer høj/medium; UI viser tilstandskode som prioritet |
| B2 | K | 2 | `services/alarms.py:10-12`, `test_alarms.py:94,114,125` | Aktiv/ukvitteret, kvitteret, retur/ukvitteret og normal testet |
| B3 | K | 2 | `services/alarms.py:327-343`, `api/alarms.py:44`, `test_alarms.py:103` | Bruger og tid gemmes; audit `alarm.ack` |
| B4 | K | 1 | `pages/Alarms.svelte:55,140-152`, `api/alarms.py:48` | Historik filtreres pr. system; ingen søgning eller eksport |
| B5 | V | 0 | grep efter shelv/undertryk: ingen forekomst | Ingen shelving eller undertrykkelse |
| B6 | V | 0 | `services/tags.py`, `storage/db.py:278-281` | Ingen felter til konsekvens, handling eller svartid |
| B7 | V | 1 | `services/metrics.py:78-80`, `assist_tools.py:154` | Stående alarmer tælles; ingen alarmrate; top-N kun via LLM |
| B8 | K | 2 | `services/alarms.py:71,93-94`, `test_alarms.py:41,134` | Dødbånd og forsinkelse pr. tag, testet |
| B9 | V | 1 | `pages/Alarms.svelte:115`, `app.css:153-158` | Visuel markering af ukvitterede; intet lydsignal |
| B10 | V | 1 | `api/routes.py:213-217` | Audit med hvem og hvornår; ingen gammel værdi, ingen test |
| B11 | V | 1 | `services/notifier.py:1`, `test_notifier.py:131,576` | Webhook og e-mail; ingen eskalering |

### C. Styring og operatørhandlinger

| ID | Pri | Vurdering | Evidens | Note |
|---|---|---|---|---|
| C1 | K | 2 | `api/auth.py:30-42`, `test_auth.py:92`, `test_operate.py:226`, `test_scope.py:108` | Rolle og tegningsadgang håndhæves i backend (verificeret) |
| C2 | K | 2 | `services/operate.py:250-257`, `services/tags.py:193`, `pages/Overview.svelte:353-387`, `test_operate.py:97` | Grænser i backend; bekræftelse som standard, men kun i UI og kan slås fra |
| C3 | K | 2 | `services/operate.py:246,265-325`, `test_operate.py:244` | Afviste forsøg logges også, med bruger, IP og tid (verificeret) |
| C4 | V | 1 | `services/symbol_operate.py:82-93`, `docs/SYMBOLSTANDARD.md:89-95` | Blokering findes; driftsart er kun PLC-tag eller symbol |
| C5 | V | 2 | `services/operate.py:279`, `symbol_operate.py:95-98`, `test_operate.py` | Serialiseres pr. tag og afvises pr. symbol (409) |
| C6 | N | 1 | `symbol_operate.py:65-66`, `manual/10-symboler-og-guiden.md:43` | Kan spærres pr. symbol eller tegning; ingen samlet lokal/fjern |
| C7 | V | 2 | `services/schedules.py:7`, `api/schedules.py:39-54`, `test_schedules.py` | Ugeplaner med undtagelser og audit |
| C8 | V | 2 | `services/operate.py:40-50,312-326`, `Overview.svelte:402-418` | Udført, afvist eller timeout med PLC'ens egen fejltekst |

### D. Data, trends og integration

| ID | Pri | Vurdering | Evidens | Note |
|---|---|---|---|---|
| D1 | K | 2 | `pages/Trends.svelte:25,365-374`, `test_trends.py:115`; set i UI | Flere kurver, zoom og periode; tom, til tags vælges |
| D2 | V | 1 | `services/trends.py:40,151-155` | 30 dages opbevaring og sletning; nedsampling ikke påvist (agentudsagn uverificeret) |
| D3 | V | 2 | `api/trends.py:115-135`, `api/energy.py:73-86`, `test_trends.py:171` | CSV-eksport af trend og energi |
| D4 | K | 2 | `services/live_cache.py:23-24`, `app.css:116-119`, `lib/animate.test.ts:103` | Kvalitet og tid følger værdien; dårlig kvalitet vises |
| D5 | N | 1 | `services/energy.py:1-14`, `test_energy.py:38,57` | Energi- og tællerrapporter; ingen driftstidsrapport |
| D6 | V | 2 | `api/integration.py:1-9,98-165`, `test_integration.py:291` | Dokumenteret versioneret læse-API med OpenAPI og SSE; ingen skrivning |
| D7 | K | 2 | `services/tags.py:15-17,65-85,192-193` | Enhed, skalering, grænser og beskrivelse; virtuelle signaler er fjernet |

### E. Cybersikkerhed

| ID | Pri | Vurdering | Evidens | Note |
|---|---|---|---|---|
| E1 | K | 2 | `services/auth.py:42-60`, `test_auth.py:79,199` | scrypt, min. 10 tegn, lockout pr. bruger+IP og pr. IP (verificeret) |
| E2 | K | 2 | `api/auth.py:104-113`, `config.py:55,106`, `test_auth.py` | HttpOnly, SameSite=Strict; Secure sættes med nginx-installation |
| E3 | K | 2 | `deploy/nginx-hypervisionplc-scada.conf:23-35`, `services/tls_admin.py` | 301→https, TLS 1.2/1.3 (verificeret) |
| E4 | K | 2 | `storage/secrets.py`, `.gitignore`, `services/plcs.py:56`, `test_api.py:49` | Skriv-kun; kun `has_password` ud (verificeret) |
| E5 | K | 2 | `deploy/hypervisionplc-scada.service:8-27` | `User=scada`, NoNewPrivileges, ProtectSystem=strict (verificeret) |
| E6 | K | 2 | `ARCHITECTURE.md:8`, CLAUDE.md regel 6, `services/manager.py:25` | Ingen browservej til PLC; firewall/segmentering ikke dokumenteret |
| E7 | V | 2 | `api/auth.py:100-103,141-168`, `api/system_config.py:117` | Login, brugerændringer og konfiguration logges; ingen dedikeret test af fejlede logins |
| E8 | V | 2 | `deploy/apply-update.sh:76-132`, `services/updates.py:240`, `test_updates.py:205` | SHA256, backup og rollback; ingen signatur |
| E9 | V | 1 | CLAUDE.md (licensregel), `README.md:157`, `docs/GENNEMGANG_2026-10-12.md:22` | Manuel licenskontrol; ingen automatisk sårbarhedsscanning eller SBOM |
| E10 | K | 2 | `main.py:301-306`, `services/svg_sanitize.py`, `test_auth.py:166` | Origin-tjek, pydantic-validering og SVG-rensning (verificeret) |
| E11 | V | 1 | `docs/KODEANALYSE_2_2026-10-26.md`, `docs/UDGIVELSESPROCES.md` | Sikkerhedsanalyse findes; ingen trusselsmodel eller patch-procedure |
| E12 | N | 0 | grep efter totp/mfa/2fa/webauthn: ingen forekomst | Ingen flerfaktor |

### F. Pålidelighed og drift

| ID | Pri | Vurdering | Evidens | Note |
|---|---|---|---|---|
| F1 | K | 2 | `deploy/hypervisionplc-scada.service` (Restart=always), `test_alarms.py:156` | Selvstart; alarmtilstand overlever genstart; ægte strømtab ikke påvist |
| F2 | K | 2 | `plc/client.py:67,171-197`, `test_runtime.py:61,129,161,222`, `lib/live.ts` | Timeout, backoff, kommunikationsstatus og WS-genforbindelse testet |
| F3 | K | 2 | `api/backup.py:30-205`, `test_backup.py:66,90,159,174` | Backup, planlagte mål og gendannelse på frisk installation testet |
| F4 | V | 2 | `api/health.py`, `api/metrics.py`, `services/health.py:97`, `test_health.py` | Health, Prometheus-metrics, Status-side og logfiler |
| F5 | N | 1 | `docs/HYPERVISIONPLC_ANALYSE.md:15`, `README.md:28` | Enkeltenhed uden failover; afgrænsning ikke begrundet for SCADA selv |
| F6 | V | 1 | `api/live_ws.py:30`, `plc/ratelimit.py`, `docs/PRODUKTIONSANALYSE_2026-11-10.md:22` | Grænser findes; ingen målt kapacitet på Pi |
| F7 | V | 2 | `services/health.py:79-93,193`, `test_health.py:191,206` | NTP-status aflæses og advarer på Status |
| F8 | V | 2 | `version.json`, `deploy/apply-update.sh`, `test_updates.py:205` | Versionering, hash-kontrolleret OTA med rollback |
| F9 | V | 1 | `docs/KATASTROFEOEVELSE.md`, `docs/PRODUKTIONSANALYSE_2026-11-10.md:36` | Procedure dokumenteret; ingen registrering af at den er øvet |

### G. Konfiguration og vedligehold

| ID | Pri | Vurdering | Evidens | Note |
|---|---|---|---|---|
| G1 | K | 2 | `services/plcs.py:54-74`, `test_plc_removal.py:65,86` | Flere PLC'er med egen nøgle, status og tags |
| G2 | V | 2 | `api/backup.py:30,40`, `storage/db.py:60,302`, `test_library.py:172` | JSON-backup med tegningsversioner; symbolpakke-eksport og -import |
| G3 | K | 2 | `backend/tests` (975 testfunktioner), 93 frontend-testfiler, `backend/mock_plc/app.py` | Omfattende suiter med mock-PLC (antal verificeret, kørsel ikke udført nu) |
| G4 | V | 2 | `frontend/src/manual/01-15`, `README.md:39,83`, `/api/v1/integration/openapi.json` | Manual i UI, admin-kapitel, OpenAPI og installationsvejledning |
| G5 | V | 1 | `frontend/index.html:2`, `lib/energyData.ts:17`, `services/schedule_engine.py:19` | Kun dansk UI; dansk dato/tal og konfigurerbar tidszone |
| G6 | V | 1 | `frontend/src` (ca. 362 aria-attributter; ingen reduced-motion) | Delvis; ingen kontrastkontrol eller test |
| G7 | V | 2 | `CHANGELOG.md`, `RELEASE_NOTES.md`, `BUGS.md`, `FEATURES.md`, `.githooks/pre-commit` | Føres og håndhæves af hook |

## 7. Forbehold og afgrænsning

- **Ikke relevant (–):** ingen. **Ukendt (U):** ingen; D2's påstand om nedsampling ved læsning kunne ikke bekræftes og er vurderet ud fra det påviste (1).
- **Metode:** kode, tests og dokumentation er læst; intet er kørt på Pi'en, og testsuiterne er ikke kørt i denne analyse. F1 (strømtab) og F6 (kapacitet) er derfor ikke målt.
- **Verificeret af orkestratoren mod koden:** alle K-vurderinger på 2 i C og E (C1–C3, E1–E6, E10), B1, B4, B5, A12, D7, antallet af tests (975 og 93) og fravær af reduced-motion. Ved C2 er bekræftelse standard (`confirm_write` True), men kan slås fra og findes kun i UI; vurderingen står på 2. Ved E6 er `httpx` i `services/manager.py` kun en typeangivelse; øvrige `httpx`-brugere (LLM, backupmål, GitHub, notifikation) er ikke gennemgået linje for linje.
- **Agenternes uverificerede udsagn:** resten, herunder A- og B-gruppens evidens uden for stikprøverne og D2, F, G.
- **Set i UI:** alle fem billeder viser den ønskede side. *varme* var deaktiveret (offline), og Alarmer viste 10 ukvitterede alarmer, hvoraf en del er testdata fra demoen. Trends er tom, til tags vælges. Ved 500 px skalerer tegningen til meget små tekster.
- **Tolkning:** vurderingerne er min læsning af principperne i ISA-101, ISA-18.2/EEMUA 191 og IEC 62443 og er ikke citeret fra standarderne.

## 8. Anbefalet næste skridt

1. **Alarmstyring til ISA-18.2-niveau** (B5, B6, B1, B7): shelving, rationalisering, tre prioritetsniveauer og alarm-KPI.
2. **Alarmhistorik og sporbarhed** (B4, B10, B9): søgning, CSV-eksport, gammel/ny værdi ved ændring af grænser og valgfrit lydsignal.
3. **Navigation og fast ramme** (A1, A6, A12): niveauer mellem tegninger, bruger/tid/PLC-status på alle sider og bedre visning på smal skærm.
4. **Driftsmodenhed** (F6, F9, E9): mål kapacitet på Pi'en, øv gendannelsen og log det, og kør automatisk sårbarhedsscanning med SBOM i release.
5. **Sikkerhedsdokumentation** (E11, E12): kort trusselsmodel, procedure for sikkerhedsopdateringer og vurdering af flerfaktor for admin.
