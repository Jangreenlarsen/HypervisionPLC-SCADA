# Changelog

Nyeste øverst. Format: `## [version build NNNN] — YYYY-MM-DD — beskrivelse`

---

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
