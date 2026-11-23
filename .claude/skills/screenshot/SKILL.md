---
name: screenshot
description: Tag et skærmbillede af en side i SCADA-UI'et til visuel verifikation af layout-ændringer (regel 9). Brug i stedet for at skrive nye engangsscripts (/screenshot <rute> [bredde]).
---

Brug `frontend/tools/shot.mjs` (Playwright, kun læsning) — skriv aldrig nye `_tmp_`-scripts til dette.

```
cd frontend && node tools/shot.mjs "<rute>" "<scratchpad>/navn.png" [--base=URL] [--width=1600] [--height=1000] [--wait=3000] [--selector=CSS] [--text]
```

- **Lokal dev/bygget app**: `--base=http://127.0.0.1:8000` (standard); start først dev-serveren eller backend, hvis den ikke kører, og stop den bagefter (kun egne processer, via PID).
- **Demoen**: `--base=https://scada.laces.dk` med `SCADA_USER`/`SCADA_PASS` som miljøvariabler (login fra memory `demo-plc-access`, aldrig i filer eller svar).
- **Smal visning**: brug `--width=500` (headless har en minimumsbredde over 390 px).
- Læg billedet i scratchpad-mappen, og åbn det med Read for at se det. Scriptet rapporterer også sidefejl fra browseren.
- Meld i afrapporteringen eksplicit, om ændringen er **set** (med rute og bredde) eller kun **bygget**.
- Manualens skærmbilleder tages stadig med `frontend/tools/manual-screenshots.mjs`.

**Forhåndsvis den lokale build mod demoens data** (før deploy): byg frontend (`npm run build`) og lad en Playwright-side servere filerne fra `frontend/dist` for demoens oprindelse, mens `/api/…`-kald går til demoen (kun GET og login; alt andet afvises). Så ses nye layouts på rigtige data ved flere bredder (500, 1000, 1200, 1600 px) uden at lave en release. Nye endpoints, demoen endnu ikke har, mockes med `route.fulfill`. Læg scriptet i scratchpad, ikke i projektet.
