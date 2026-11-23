---
name: audit
description: Kør tegningskontrollen (deploy/audit_drawings.py, kun læsning) mod en SCADA-server uden at deploye, og sammenlign med forrige kørsel. Brug til at tjekke demoen på de rigtige tegninger, fx efter en ændring i flow/bindinger eller når noget ser forkert ud (/audit [URL]).
---

Standard-server er `https://scada.laces.dk`; en anden URL kan gives som argument. Kontrollen skriver intet til PLC'en eller serveren.

1. **Login**: hent brugernavn og adgangskode til serveren fra memory `demo-plc-access` (demoen) og sæt dem kun som miljøvariabler på selve kommandoen — aldrig i filer, logs eller svar.
2. **Kør** og gem resultatet i scratchpad som `audit-<værtsnavn>-<tidsstempel>.txt`:
   `SCADA_USER=… SCADA_PASS=… PYTHONIOENCODING=utf-8 backend/.venv/Scripts/python.exe deploy/audit_drawings.py <URL>`
3. **Sammenlign** med den nyeste tidligere `audit-<værtsnavn>-*.txt` i scratchpad (`diff`). Findes ingen, så sig at der ikke er noget at sammenligne med.
4. **Afrapportér kort**: antal tegninger med noget at se på, og hvad der er ændret siden sidst. Tag nye flow-beskeder, standardgruppe uden bundne forbindelser, bindinger uden element og manglende tags alvorligt: de er tegn på regression (v6.8.4 gav 42 løbelys-bindinger og falske flow-beskeder på varmen). Ved fund: find årsagen med bevis før næste opgave, og start ikke en ny ændring ovenpå.
5. Login-fejl (returkode 2) betyder forkert adgangskode eller server nede — meld det, og gæt ikke på andre logins.
