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
