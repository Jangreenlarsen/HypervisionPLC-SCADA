# Projekt: HypervisionPLC SCADA

Claudes system-prompt for projektet. Læses først, følges uden undtagelser.

## Projekt
Web-baseret SCADA/HMI til en eller flere **HypervisionPLC**-enheder (`C:\Projekter\HypervisionPLC`), kører som én systemd-service på **Debian/Raspberry Pi OS (64-bit)**: på en Raspberry Pi (4, eller 5 med hjælperen) eller i en **Linux-VM** (x86_64/arm64; målsystem **16 GB RAM, 30 GB disk**). Pi 5 er ikke et krav; krav, profiler og diskbudget: `docs/PLATFORM_OG_KRAV.md`. Brugeren uploader en SVG-tegning af anlægget; elementer bindes til PLC-tags og opdateres live på et Overview-board, redigeres i en indbygget tegne-editor (SVG-Edit), og operatører kan skrive setpunkter/kommandoer tilbage. Brugere: operatører (betjening), teknikere (tegninger/tags), admin.

**Fast ramme**: al kommunikation med PLC'en foregår **udelukkende via PLC'ens REST API** (plus SSE-strømmen `/api/events` som push-supplement). Kun SCADA-serveren taler med PLC'en — browsere taler kun med SCADA-serveren. PLC-API: `C:\Projekter\HypervisionPLC\docs\manual\B_REST_API_Reference.md`. Research/design: `docs/RESEARCH_OG_DESIGN.md`.

**Licens**: AGPL-3.0-or-later. Nye afhængigheder kræver AGPL-kompatibel licens (MIT, BSD, Apache-2.0, LGPL, MPL-2.0, GPL-3.0/AGPL-3.0) — tjek før de tilføjes, og spørg først. Web-UI'et viser link til kildekoden (AGPL §13).

Stack: Backend: Python 3.11, FastAPI + uvicorn, httpx (PLC-klient), SQLite (WAL), pytest | Frontend: Vite + TypeScript + Svelte, SVG-Edit 7 (`@svgedit/svgcanvas`), DOMPurify | Live-data: WebSocket fra SCADA-serveren | Test-PLC: mock-PLC (FastAPI) | Deploy: Debian 12/13 eller Raspberry Pi OS Lite 64-bit (Pi eller VM), én systemd-service (uvicorn) som ikke-privilegeret bruger; frontend bygges på udviklingsmaskinen og serveres statisk af FastAPI; valgfri Chromium-kiosk
Kommandoer: test backend `cd backend && .venv/Scripts/python.exe -m pytest` · frontend `cd frontend && npm test` | build `cd frontend && npm run build` | dev `cd frontend && npm run dev`
Struktur og lag: se `ARCHITECTURE.md` (læs kun når opgaven rører arkitektur).

---

## Modeller og agenter

Standardmodel er `opusplan` (`.claude/settings.local.json`): Opus i plan mode, Sonnet ved implementering. Effort er **medium** som standard — aldrig low; `max` kun hvis Jan beder om det.

Hovedsessionen er **orkestrator** og beholder selv integration, beslutninger og det endelige svar. Agenter starter uden samtalekontekst og koster tokens, så de bruges kun når det betaler sig:

- **Direkte, uden agent**: opslag og rettelser i 1-2 filer, og søgning hvor man allerede ved hvor.
- **Agent** når opgaven rører **mere end 3 filer**, når koden er ukendt (hvor bor det, hvem kalder det), eller når der skal bruges ekstern viden. Uafhængige delopgaver startes **parallelt i samme kald**. Samme research må ikke udføres både af agent og af orkestratoren.
- **`reviewer` er obligatorisk** ved ændringer i auth, permissions, PLC-skrivninger, eksterne API'er, data-integritet og sikkerhed — før commit. Ikke ved trivielle ændringer.

| Opgavetype | Agent / model | Effort |
|---|---|---|
| Opslag, filsøgning, simple fakta | `Explore` / haiku | medium |
| Ekstern research (PLC-API, biblioteker, licenser, SVG-Edit) | `general-purpose` / sonnet | medium; high ved uklar kilde |
| Afgrænset implementering efter godkendt plan, tests, doku | `implementer` / sonnet | medium |
| Fejlsøgning med uklar årsag, tværgående ændringer | sonnet eller opus | high |
| Arkitektur, planlægning, afvejning af alternativer | opus (plan mode eller `Plan`) | high |
| Kritisk review (se ovenfor) | `reviewer` / opus | high; xhigh kun ved særlig høj risiko |

Angiv `model` og `effort` eksplicit i agentkaldet, vælg den billigste kombination der er pålidelig, og tag den højeste ved PLC-skrivninger og sikkerhed. Skriv én linje om hvilke agenter der startes og hvorfor. Giv hver agent ét præcist spørgsmål, bed om kort svar med fil:linje, og **verificér svaret mod koden** — et agent-svar er et udkast. Research-agenter ændrer ingen filer.

---

## Arbejdsstil (token-økonomi)

- Svar kort på dansk. Ingen indledning eller opsummering; slut med 1-2 sætninger: resultat + evt. næste skridt. Vis kun ændrede dele, aldrig hele filer.
- Grep/Glob først, læs kun nødvendige linjeintervaller, læs ikke en fil igen. Kør uafhængige værktøjskald parallelt.
- Uklart krav eller flere rimelige tolkninger: ét kort spørgsmål før du bygger. Gæt aldrig på noget dyrt at rette.
- Større eller tværgående opgaver (nyt lag, migration, >3 filer): kort plan i plan mode, gem i `PLAN.md` (mål, trin, filer, risici) og vent på OK. Ved arkitekturvalg: 2-3 alternativer, vælg ét, noter beslutningen kort. Små rettelser: direkte.
- Fejlsøgning: find rodårsag med bevis (log/kode) før du retter. Ret hele fejlklassen, ikke kun instansen.
- Ingen nye afhængigheder uden at spørge. Midlertidige scripts lægges i scratchpad, aldrig i projektet (`frontend/tools/_tmp_*` er git-ignoreret).

---

## Faste regler

1. **Versionering (UFRAVIGELIG)**: `version.json` er eneste versionskilde. Format `{ "version": "MAJOR.MINOR.PATCH", "build": "NNNN" }`. Bump med `python deploy/bump_version.py build|patch|minor|major`.
   - build +1 ved hvert commit med kodeændring (nulstilles aldrig). PATCH ved bugfix. MINOR ved feature (PATCH=0). MAJOR ved breaking change, fx skema-migration (MINOR og PATCH=0).
   - Debug-serie: `MAJOR.MINOR.PATCH.D` (D starter på 1, +1 pr. debug-commit). Commit: `vX.X.X.D-bNNNN: debug: beskrivelse`. Når Jan bekræfter *"nu virker det som det skal"*: PATCH+1, D nulstilles, commit som `fix:`.
   - Kun-dokumentations-commits: ingen versionsbump. Vis ny version i commit-beskeden.
2. **Dokumentation efter ændringens størrelse**:
   - **Feature**: registrér i `FEATURES.md` FØR implementering, opdatér status bagefter; CHANGELOG, RELEASE_NOTES og manual med berørte skærmbilleder i samme commit.
   - **Bug**: registrér i `BUGS.md` straks, opdatér med løsning; CHANGELOG, og RELEASE_NOTES hvis fejlen kunne ses af brugeren.
   - **Lille eller intern rettelse**: kun CHANGELOG-linje (`## [version build NNNN] — YYYY-MM-DD — beskrivelse`, nyeste øverst, berørte filer).
   - Ændres UI, opdateres manualtekst og berørte billeder i samme commit.
3. **Hemmeligheder (UFRAVIGELIG)**: Nøgler/adgangskoder aldrig i git, logs eller svar til klient. PLC-adgangskoder/tokens og session-nøglen ligger i git-ignoreret `data/secrets.json` / `.env` på serveren. Endpoints returnerer kun *om* en nøgle er sat (og hvorfra), aldrig værdien; sætning er skriv-kun. PLC-API'er returnerer kun `has_password`. Tokens og adgangskoder må aldrig nå browseren. Login til servere gives til scripts kun som miljøvariabel.
4. **Rettigheder**: Forhåndsgodkendt via `.claude/settings.local.json`: læs/skriv/rediger, tests, lint, build og lokale dev-servere. Destruktive handlinger (force-push, `reset --hard`, sletning af andet end egne testdata) kræver eksplicit accept.
5. **Git (UFRAVIGELIG)**: Arbejd altid på `dev`. Commit efter hver logisk afsluttet ændring (aldrig bulk af urelaterede ting; `git add` med filnavne). Efter commit: push `origin dev` uden at spørge, og spørg derefter *"Vil du også merge til `main`?"*. Ja (eller blot *"main"*) = merge `dev` → `main` med `--no-ff` og push `origin main`. Nej = bliv på `dev` og sig at `main` ikke er opdateret. Siger Jan *"merge automatisk i denne session"*, så spørg ikke igen i den session, men meld at det er sket. Aldrig direkte commit/push til `main`.
   `.githooks/pre-commit` (aktiveret med `git config core.hooksPath .githooks` — gør det i nye kloner) håndhæver: ingen commit på `main`, ingen nøgler i indekset, kodeændring kræver bumpet build og CHANGELOG-entry. Ret årsagen; `SKIP_GUARD=1` kun efter aftale med Jan.
6. **Lag-arkitektur**: Respektér `ARCHITECTURE.md`. Intet lag springes over eller kaldes baglæns. **Kun PLC-klient-laget (`backend/app/plc/`) må lave HTTP-kald til en PLC.**
7. **Logging og observability**: Kritiske handlinger og fejl logges struktureret via `logging` med kontekst (plc, tag, bruger), niveau via `LOG_LEVEL`. Alle PLC-skrivninger logges også i audit-loggen. Tænk log/tæller/Status/metrics ind i hver ny ændring.
8. **Kodekvalitet (UFRAVIGELIG)**: Før en feature/fix meldes færdig, kør `docs/QUALITY_CHECKLIST.md`. For auth, permissions, PLC-skrivninger, data-integritet, eksterne API'er og bulk-operationer læses den FØR implementering. Kernen: tjek null/fejl før brug, vis specifik backend-fejl til brugeren, undgå lockout (håndhæv i backend), `is not None` for tal der kan være 0, ingen read-modify-write ved samtidige opdateringer, test i den faktiske runtime-kontekst (systemd-service på målmaskinen: Pi eller VM), gennemgå alle grene når en regel indføres.
9. **Visuel verifikation (UFRAVIGELIG)**: Layout-ændringer (positionering, flex/grid, hjørne-grupper, z-index, ombrydning) skal ses i browseren før de meldes færdige — brug `/screenshot` (`frontend/tools/shot.mjs`). Skriv eksplicit om ændringen er *set* eller kun *bygget*. Intet må flytte sig ved klik: faste kolonner/pladser og fast bredde på skiftende tekster.
10. **Tests**: Ny logik der kan fejle uset (fejloversættelse, formatering, fallback, tilstandsskift) skal have en test; rene visuelle ændringer ikke. Kør alle relevante suiter før noget meldes færdigt: backend `cd backend && .venv/Scripts/python.exe -m pytest` · frontend `cd frontend && npm test` og `npm run build`.

---

## Workflow

1. Registrér i FEATURES.md/BUGS.md → 2. implementér i korrekt lag → 3. tests, build og (ved layout) `/screenshot` → 4. `reviewer` ved kritiske ændringer → 5. **`/release`**, som tager resten: version bump, CHANGELOG/RELEASE_NOTES, commit `vX.X.X-bNNNN: beskrivelse`, push `origin dev`, OTA-pakke, deploy til scada.laces.dk og tegningskontrol, og spørgsmålet om merge til `main`.

**OTA-pakke og demo-deploy (hver gang efter kodeændring, UFRAVIGELIG)**: `sh deploy/make-package.sh` giver `scada-<version>-b<build>.tar` i projektets rod. Hver ny version deployes altid til scada.laces.dk (`deploy/ota_deploy.py`) uden at spørge; scriptet kører `deploy/audit_drawings.py` bagefter (kun læsning). Meld filnavn, størrelse, SHA256, deploy-resultat og audit-resultat sammenlignet med forrige kørsel — nye flow-beskeder, bindinger uden element eller manglende tags er tegn på regression. Doku-only commits er undtaget.

**Version i UI**: Den installerede version (`v<version> · b<build>`, fra `/api/health`) står altid yderst til højre i topmenuen (`App.svelte`, snippet `version`) — også på login-siden. Bevar den ved ændringer i topmenuen.
