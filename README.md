# HypervisionPLC SCADA

Web-baseret SCADA/HMI til HypervisionPLC, bygget til Raspberry Pi 4.

- Upload en SVG-tegning af anlægget, bind elementer til PLC-tags og se værdierne live på Overview-boardet.
- Redigér tegninger i den indbyggede tegne-editor (SVG-Edit).
- Al kommunikation med PLC'erne går via PLC'ens REST API (+ SSE), og kun SCADA-serveren taler med PLC'erne.

Dokumentation:
- [docs/RESEARCH_OG_DESIGN.md](docs/RESEARCH_OG_DESIGN.md) — research, design og faseplan
- [ARCHITECTURE.md](ARCHITECTURE.md) — lag og projektstruktur
- [FEATURES.md](FEATURES.md) — backlog

Status: v0.7.0 — Overview med live SVG-tegninger og betjening, binding-editor, tags, audit-log, login, roller og HTTPS.

## Udvikling

```sh
cd backend
py -3.12 -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m pytest              # alle tests
.venv/Scripts/python.exe -m mock_plc --port 8081 # mock-PLC (login scada/scada123)
.venv/Scripts/python.exe -m app                  # SCADA-server på http://127.0.0.1:8000 (API-doc: /docs)
```

Frontend:

```sh
cd frontend
npm install
npm test            # vitest
npm run dev         # http://localhost:5173 (videresender /api og /ws til :8000)
npm run build       # → frontend/dist, som SCADA-serveren serverer
```

Eksempeltegninger: [docs/examples/](docs/examples/).

## Installation (Debian / Raspberry Pi OS)

```sh
sudo sh deploy/install.sh                 # SCADA som systemd-service
sudo sh deploy/install.sh --with-mock-plc # + mock-PLC til test
```
```sh
sudo sh deploy/install.sh --with-nginx scada.laces.dk 10.1.1.31   # + nginx med TLS (selvsigneret certifikat)
```
Konfiguration: `/etc/hypervisionplc-scada.env`. Data: `/var/lib/hypervisionplc-scada`. Certifikat: `/etc/hypervisionplc-scada/tls/`.

### Opdatering af en server fra Windows

Deploy altid det der er committet — `git archive` giver LF-linjeskift uanset Windows-arbejdsmappen:

```sh
cd frontend && npm run build && cd ..
git archive --format=tar --prefix=scada/ HEAD > scada.tar
tar --force-local -rf scada.tar --transform 's,^,scada/,' frontend/dist
# kopiér scada.tar til serveren, pak ud og kør: sudo sh scada/deploy/install.sh [...]
```

## Licens

Copyright (C) 2026 Jan Green Larsen

HypervisionPLC SCADA er fri software: du kan videredistribuere og/eller ændre den under betingelserne i **GNU Affero General Public License v3.0 eller senere** (AGPL-3.0-or-later), som udgivet af Free Software Foundation. Se [LICENSE](LICENSE) for den fulde tekst.

Kører du en ændret version, som brugere tilgår over netværket (web-UI, REST API), kræver AGPL §13, at du tilbyder dem den tilsvarende kildekode. SCADA'ens web-UI viser derfor et link til kildekoden.

Tredjepartskomponenter beholder deres egne licenser, fx SVG-Edit (MIT), FastAPI (MIT), Svelte (MIT) og DOMPurify (Apache-2.0/MPL-2.0).
