# Features

Format: `[status] vX.X.X — beskrivelse`
Status: `planned` | `in-progress` | `done`

Faseplan og detaljer: [docs/RESEARCH_OG_DESIGN.md](docs/RESEARCH_OG_DESIGN.md#4-faseplan).

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
- [ ] planned — Upload af SVG med server-side sanering og versionering
- [ ] planned — Overview-board: vis tegning og opdatér bindinger live via WebSocket (delta-frames)
- [ ] planned — Kvalitetsvisning (stale/kommunikationsfejl) på bundne elementer

### Fase 3 — Bindinger
- [ ] planned — Binding-editor: klik element → vælg tag + animation (text, fill, stroke, visible, blink, level, rotate, move, opacity, click:write/toggle/pulse/goto)
- [ ] planned — Auto-forslag af bindinger ud fra element-id / inkscape:label
- [ ] planned — Advarsel om forældreløse bindinger efter gen-upload

### Fase 4 — Tegne-editor
- [ ] planned — SVG-Edit 7 indlejret som fuld tegne-editor med live-preview
- [ ] planned — Symbolbibliotek (pumpe, ventil, tank, motor, rør, værdifelt) i ISA-101-stil
- [ ] planned — Versioner, udgiv og rollback af tegninger

### Fase 5 — Betjening og adgang
- [ ] planned — Skrivning til PLC (setpunkt-dialog, toggle, puls) med bekræftelse og PLC-fejlbesked til operatør
- [ ] planned — Brugere og roller (viewer/operator/engineer/admin) med sidste-admin-beskyttelse i backend
- [ ] planned — Audit-log over alle skrivninger og konfigurationsændringer

### Fase 6 — Drift
- [ ] planned — Alarmer (grænser pr. tag + PLC'ens `/api/alarms`) og alarmliste
- [ ] planned — Trends (RAM-ringbuffer + PLC'ens trend recorder)
- [ ] planned — Raspberry Pi 4 deployment: install-script, systemd-service, Chromium-kiosk
- [ ] planned — Backup/restore af hele SCADA-projektet (tegninger, tags, bindinger)

### Tværgående
- [ ] planned — Kildekode-link i web-UI'et (AGPL-3.0 §13), konfigurerbar URL til forks
