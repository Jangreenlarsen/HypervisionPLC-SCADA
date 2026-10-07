# HypervisionPLC SCADA

Web-baseret SCADA/HMI til HypervisionPLC, bygget til Raspberry Pi 4.

- Upload en SVG-tegning af anlægget, bind elementer til PLC-tags og se værdierne live på Overview-boardet.
- Redigér tegninger i den indbyggede tegne-editor (SVG-Edit).
- Al kommunikation med PLC'erne går via PLC'ens REST API (+ SSE), og kun SCADA-serveren taler med PLC'erne.

Dokumentation:
- [docs/RESEARCH_OG_DESIGN.md](docs/RESEARCH_OG_DESIGN.md) — research, design og faseplan
- [ARCHITECTURE.md](ARCHITECTURE.md) — lag og projektstruktur
- [FEATURES.md](FEATURES.md) — backlog

Status: v0.1.0 — projektinitialisering, endnu ingen kørende kode.

## Licens

Copyright (C) 2026 Jan Green Larsen

HypervisionPLC SCADA er fri software: du kan videredistribuere og/eller ændre den under betingelserne i **GNU Affero General Public License v3.0 eller senere** (AGPL-3.0-or-later), som udgivet af Free Software Foundation. Se [LICENSE](LICENSE) for den fulde tekst.

Kører du en ændret version, som brugere tilgår over netværket (web-UI, REST API), kræver AGPL §13, at du tilbyder dem den tilsvarende kildekode. SCADA'ens web-UI viser derfor et link til kildekoden.

Tredjepartskomponenter beholder deres egne licenser, fx SVG-Edit (MIT), FastAPI (MIT), Svelte (MIT) og DOMPurify (Apache-2.0/MPL-2.0).
