# Arkitektur: HypervisionPLC SCADA

Baggrund og begrundelser: [docs/RESEARCH_OG_DESIGN.md](docs/RESEARCH_OG_DESIGN.md). Design for symboler: [docs/SYMBOLSTANDARD.md](docs/SYMBOLSTANDARD.md) — gælder for alle symboler og al ny symbolkode.

## Principper

1. **Ingen lag må springe et lag over.**
2. **Kun PLC-klient-laget taler med PLC'er** — via PLC'ens REST API (+ SSE). Browsere taler aldrig direkte med en PLC, og PLC-credentials forlader aldrig serveren.
3. **Alle lag eksponerer kun et veldefineret interface** — interne implementeringsdetaljer er skjulte.
4. **Tegninger binder til tag-navne, aldrig til rå PLC-adresser.** Adressen er en egenskab ved tagget.
5. **Al uploadet/redigeret SVG saneres på serveren** før den gemmes.

---

## Lag-oversigt

```
┌──────────────────────────────────────────────────┐
│ Lag 1 — Frontend (browser / Chromium kiosk)      │
│   Overview-viser · Tegne-editor · Admin          │
└───────────────┬──────────────────────────────────┘
                │ HTTPS REST /api/*  +  WebSocket /ws/live
┌───────────────▼──────────────────────────────────┐
│ Lag 2 — API-lag (FastAPI routers)                │
└───────────────┬──────────────────────────────────┘
                │ Python-kald
┌───────────────▼──────────────────────────────────┐
│ Lag 3 — Service-lag                              │
│   tegninger · bindinger · tags · live-cache ·    │
│   abonnementer · skriv+audit · brugere · alarmer │
│   · trend-opsamling                              │
└───────┬───────────────────────────┬──────────────┘
        │                           │
┌───────▼──────────────┐   ┌────────▼─────────────┐
│ Lag 4a — PLC-klient  │   │ Lag 4b — Lager       │
│ login/token, poll-   │   │ SQLite (WAL), SVG-   │
│ planlægger, SSE,     │   │ filer, secrets-fil   │
│ rate-budget, backoff │   │                      │
└───────┬──────────────┘   └──────────────────────┘
        │ REST (+SSE) over HTTP(S)
┌───────▼──────────────┐
│ HypervisionPLC 1..N  │
└──────────────────────┘
```

---

## Lag-beskrivelse

### Lag 1 — Frontend
- **Ansvar**: Overview-board (viser tegning + live-animationer), tegne-editor (SVG-Edit + binding-panel + tag-browser + symbolbibliotek), admin (PLC'er, tags, brugere).
- **Filer**: `frontend/src/`
- **Regler**: Kalder kun SCADA-serverens `/api/*` og `/ws/live`. Kender ikke PLC-adresser i tegningen (kun tag-navne). Indsætter aldrig SVG i DOM uden DOMPurify. Viser altid backendens specifikke fejlbesked.

### Lag 2 — API-lag
- **Ansvar**: HTTP/WebSocket-endpoints, request-validering (pydantic), auth/rolle-tjek, oversættelse af service-fejl til `{"error": "..."}`.
- **Filer**: `backend/app/api/`
- **Regler**: Ingen forretningslogik og ingen direkte DB- eller PLC-kald — alt går gennem service-laget.

### Lag 3 — Service-lag
- **Ansvar**: SVG-sanering og versioner, bindinger, tag-model og -skalering, live-cache (værdi + kvalitet + tid), abonnements-sæt, skrive-service (validering min/max, audit), brugere/roller (inkl. sidste-admin-beskyttelse), alarmer, trend-opsamling (ved ændring + keepalive, batch-skrivning, oprydning).
- **Filer**: `backend/app/services/`
- **Regler**: Kalder PLC-klient-laget og lager-laget; aldrig HTTP direkte.

### Lag 4a — PLC-klient
- **Ansvar**: Én klient pr. PLC: login → Bearer-token, re-login ved 401, bulk-reads planlagt ud fra abonnements-sættet, SSE-lytter, rate-budget (≤ 5 req/s pr. PLC), backoff ved 429/timeout, skrivekald.
- **Filer**: `backend/app/plc/`
- **Regler**: Eneste sted i koden der laver netværkskald til en PLC. Returnerer typede resultater/fejl — aldrig rå httpx-exceptions op til service-laget.

### Lag 4b — Lager
- **Ansvar**: SQLite-tabeller (plcs, tags, drawings, drawing_versions, bindings, users, audit, alarmer), SVG-filer pr. version, secrets. Trend-historik ligger i en separat `trends.db` (samples uden rowid, PK tag+tid), så store datamængder ikke belaster konfigurationsdatabasen.
- **Filer**: `backend/app/storage/`, data i `data/` (git-ignoreret)
- **Regler**: Opdateringer skriver kun ændrede felter (ingen read-modify-write af hele rækker/dokumenter).

---

## Projektstruktur

```
.
├── CLAUDE.md
├── version.json
├── ARCHITECTURE.md
├── FEATURES.md
├── BUGS.md
├── CHANGELOG.md
├── RELEASE_NOTES.md
├── docs/
│   └── RESEARCH_OG_DESIGN.md   # research, design, faseplan
├── .claude/
│   └── settings.local.json
├── backend/                    # Python/FastAPI (fase 1+)
│   ├── app/
│   │   ├── api/                # Lag 2
│   │   ├── services/           # Lag 3
│   │   ├── plc/                # Lag 4a
│   │   └── storage/            # Lag 4b
│   ├── mock_plc/               # mock af HypervisionPLC REST API til dev/test
│   └── tests/
├── frontend/                   # Vite + TS + Svelte (fase 2+)
│   └── src/
├── deploy/                     # install.sh + systemd-units (SCADA, mock-PLC)
└── data/                       # runtime-data på Pi'en (git-ignoreret)
```
