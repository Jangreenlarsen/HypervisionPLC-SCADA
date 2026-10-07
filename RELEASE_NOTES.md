# Release Notes

---

## v0.2.0 — 2026-10-07 — SCADA-serveren taler med PLC'en

- SCADA-serveren kan forbinde til en eller flere HypervisionPLC'er via REST og holde live-værdier opdateret: bulk-polling, og PLC'ens SSE-strøm som hurtig supplement når den er ledig.
- Tags kan oprettes med kilder som `plc1:hr:100:real`, `plc1:coil:5` eller navngivne ST-variabler (`plc1:logic:1:Niveau`) med skalering og enhed — og foreslås automatisk ud fra PLC'ens ST-programmer.
- PLC-adgangskoder gemmes kun på serveren og vises aldrig.
- Mock-PLC til test uden hardware, og installationsscript + systemd-service til Debian/Raspberry Pi.
- Endnu ingen brugerflade og intet login — API'et lytter derfor kun på localhost som standard.

**Næste skridt**: Fase 2 — SVG-upload og Overview-board med live-værdier.

## v0.1.0 — 2026-10-07 — Projektinitialisering

Projektstruktur, research og arkitektur for HypervisionPLC SCADA er på plads. Der er endnu ingen kørende kode.

**Næste skridt**: Fase 1 — backend-skelet, mock-PLC og PLC-klient (login, bulk-poll, SSE) med tag-model.
