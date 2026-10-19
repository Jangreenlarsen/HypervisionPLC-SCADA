# Projekt: HypervisionPLC SCADA

Claudes system-prompt for projektet. Læses først, følges uden undtagelser.

## Projekt
Web-baseret SCADA/HMI til en eller flere **HypervisionPLC**-enheder (`C:\Projekter\HypervisionPLC`), kører på en **Raspberry Pi 4**. Brugeren uploader en SVG-tegning af anlægget; elementer bindes til PLC-tags og opdateres live på et Overview-board, redigeres i en indbygget tegne-editor (SVG-Edit), og operatører kan skrive setpunkter/kommandoer tilbage. Brugere: operatører (betjening), teknikere (tegninger/tags), admin.

**Fast ramme**: al kommunikation med PLC'en foregår **udelukkende via PLC'ens REST API** (plus SSE-strømmen `/api/events` som push-supplement). Kun SCADA-serveren taler med PLC'en — browsere taler kun med SCADA-serveren. PLC-API: `C:\Projekter\HypervisionPLC\docs\manual\B_REST_API_Reference.md`. Research/design: `docs/RESEARCH_OG_DESIGN.md`.

**Licens**: AGPL-3.0-or-later. Nye afhængigheder kræver AGPL-kompatibel licens (MIT, BSD, Apache-2.0, LGPL, MPL-2.0, GPL-3.0/AGPL-3.0) — tjek før de tilføjes, og spørg først. Web-UI'et viser link til kildekoden (AGPL §13).

Stack: Backend: Python 3.11, FastAPI + uvicorn, httpx (PLC-klient), SQLite (WAL), pytest | Frontend: Vite + TypeScript + Svelte, SVG-Edit 7 (`@svgedit/svgcanvas`), DOMPurify | Live-data: WebSocket fra SCADA-serveren | Test-PLC: mock-PLC (FastAPI) | Deploy: Raspberry Pi OS Lite 64-bit, én systemd-service (uvicorn) som ikke-privilegeret bruger; frontend bygges på udviklingsmaskinen og serveres statisk af FastAPI; valgfri Chromium-kiosk
Kommandoer: test backend `cd backend && .venv/Scripts/python.exe -m pytest` · frontend `cd frontend && npm test` | build `cd frontend && npm run build` | dev `cd frontend && npm run dev`
Struktur og lag: se `ARCHITECTURE.md` (læs kun når opgaven rører arkitektur).

---

## Modeller og agenter

Standardmodel er `opusplan` (i `.claude/settings.local.json`): Opus i plan mode, Sonnet ved implementering.

- **Plan/design/analyse (Opus)**: Større opgaver planlægges først i plan mode. Gem planen i `PLAN.md` (mål, trin, berørte filer, risici), så en ny session kan fortsætte uden at gentage kontekst. Ved arkitekturvalg: 2-3 alternativer med kompromiser, vælg ét og noter beslutningen kort.
- **Implementering (Sonnet)**: Små og mellemstore opgaver løses direkte. Afgrænsede opgaver ud fra en godkendt plan kan delegeres til agenten `implementer`.
- **Søgning (Haiku)**: Agenten `Explore` søger i kodebasen og svarer kort. Brug den ved bred søgning, ikke ved opslag i 1-2 filer.
- **Review (Opus)**: Agenten `reviewer` kontrollerer kritiske ændringer (auth, permissions, PLC-skrivninger, API'er, data-integritet, sikkerhed) før commit. Ikke til trivielle ændringer.
- Agenter starter uden samtalekontekst og koster tokens. Giv dem en præcis opgave og bed om kort svar. Én session pr. opgave; `/clear` mellem uafhængige opgaver.

---

## Arbejdsstil (token-økonomi)

- Svar kort. Ingen indledning, ingen opsummering af hvad du lige gjorde. Slut med 1-2 sætninger: resultat + evt. næste skridt.
- Vis kun ændrede dele (diff/relevante linjer), aldrig hele filer i svaret.
- Grep/Glob først, læs derefter kun de nødvendige linjeintervaller. Læs ikke en fil igen, du allerede har i kontekst.
- Kør uafhængige værktøjskald parallelt.
- Uklart krav eller flere rimelige tolkninger: stil ét kort spørgsmål før du bygger. Gæt aldrig på noget dyrt at rette.
- Større eller tværgående opgaver (nyt lag, migration, >3 filer): lav først en kort plan (plan mode) og vent på OK. Små rettelser: gå direkte til implementering.
- Fejlsøgning: find rodårsag med bevis (log/kode) før du retter. Ret hele fejlklassen, ikke kun den rapporterede instans.
- Ingen nye afhængigheder uden at spørge.

---

## Faste regler

1. **Versionering (UFRAVIGELIG)**: `version.json` er eneste versionskilde (backend, frontend, changelog læser herfra). Format `{ "version": "MAJOR.MINOR.PATCH", "build": "NNNN" }`.
   - build +1 ved hvert commit med kodeændring. PATCH ved bugfix (build nulstilles ikke). MINOR ved feature (PATCH=0). MAJOR ved breaking change, fx skema-migration (MINOR og PATCH=0).
   - Debug-serie: `MAJOR.MINOR.PATCH.D` (D starter på 1, +1 pr. debug-commit). Commit: `vX.X.X.D-bNNNN: debug: beskrivelse`.
   - Når Jan bekræfter *"nu virker det som det skal"*: PATCH+1, D nulstilles, commit som `fix:`.
   - Kun-dokumentations-commits: ingen versionsbump.
   - Vis ny version i commit-beskeden.
2. **Dokumentation (saml i ét trin pr. ændring)**:
   - Feature: registrér i `FEATURES.md` FØR implementering, opdatér status bagefter.
   - Bug: registrér i `BUGS.md` straks, opdatér med løsning.
   - Kodeændring: entry i `CHANGELOG.md` (`## [version build NNNN] — YYYY-MM-DD — beskrivelse`, nyeste øverst, berørte filer) og opdatering af `RELEASE_NOTES.md`. Doku-only commits er undtaget fra RELEASE_NOTES.
3. **Hemmeligheder (UFRAVIGELIG)**: Nøgler/adgangskoder aldrig i git, logs eller svar til klient. PLC-adgangskoder/tokens og session-nøglen ligger i git-ignoreret `data/secrets.json` / `.env` på Pi'en. Endpoints returnerer kun *om* en nøgle er sat (og hvorfra), aldrig værdien; sætning er skriv-kun. PLC-API'er returnerer kun `has_password`. PLC-tokens og -adgangskoder må aldrig nå browseren.
4. **Rettigheder**: Forhåndsgodkendt via `.claude/settings.local.json`: læs/skriv/rediger, kør tests, lint, build og lokale dev-servere uden at spørge. Destruktive handlinger (force-push, `reset --hard`, sletning af andet end egne testdata) kræver eksplicit accept.
5. **Git (UFRAVIGELIG)**: Arbejd altid på `dev`. Commit efter hver logisk afsluttet ændring (aldrig bulk af urelaterede ting). Efter commit: push `origin dev` uden at spørge, og spørg derefter: *"Vil du også merge til `main`?"*. Ja (eller blot *"main"*) = merge `dev` → `main` med `--no-ff` og push `origin main`. Nej = bliv på `dev` og sig at `main` ikke er opdateret. Aldrig direkte commit/push til `main`.
6. **Lag-arkitektur**: Respektér `ARCHITECTURE.md`. Intet lag springes over eller kaldes baglæns. Specielt: **kun PLC-klient-laget (`backend/app/plc/`) må lave HTTP-kald til en PLC.**
7. **Logging**: Kritiske handlinger og fejl logges struktureret via Pythons `logging` med kontekst (plc, tag, bruger), niveau via `LOG_LEVEL`. Alle skrivninger til PLC logges desuden i audit-loggen.
8. **Kodekvalitet (UFRAVIGELIG)**: Før en feature/fix meldes færdig, kør tjeklisten i `docs/QUALITY_CHECKLIST.md`. For auth, permissions, PLC-skrivninger, data-integritet, eksterne API'er og bulk-operationer læses den FØR implementering. Kernen: tjek null/fejl før brug, vis specifik backend-fejl til brugeren, undgå lockout i adgangskontrol (håndhæv i backend), brug `is not None` for tal der kan være 0, ingen read-modify-write ved samtidige opdateringer, test i den faktiske runtime-kontekst (systemd-service på Pi'en), og gennemgå alle grene når en regel indføres.
9. **Visuel verifikation (UFRAVIGELIG)**: Layout-ændringer (positionering, flex/grid, hjørne-grupper, z-index, ombrydning) skal ses i browseren før de meldes færdige. Skriv eksplicit om ændringen er *set* eller kun *bygget*.
10. **Tests**: Ny logik der kan fejle uset (fejloversættelse, formatering, fallback, tilstandsskift) skal have en test. Rene visuelle ændringer skal ikke. Kør alle relevante suiter før noget meldes færdigt: backend `cd backend && .venv/Scripts/python.exe -m pytest` · frontend `cd frontend && npm test` og `npm run build`.

---

## Workflow

1. Registrér i FEATURES.md/BUGS.md → 2. implementér i korrekt lag → 3. kør tests/verifikation → 4. opdatér version.json, CHANGELOG.md, RELEASE_NOTES.md → 5. commit `vX.X.X-bNNNN: beskrivelse` → 6. push `origin dev` → 7. spørg om merge til `main`.
