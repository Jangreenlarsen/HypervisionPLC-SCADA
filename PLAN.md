# Plan: Symboltest v0.103.0

**Mål**: Symboltest skal kunne afprøve det symbolerne kan i dag: positioner, løbelys (flow) og bibliotekets standardopsætning.

## Trin
1. `symbolTest.ts`: `testInfo` (del-info inkl. `line` som serverens `_shape_info`), `types` pr. del via `typesFor`, `testBinding` med `kind: 'pos'` (+ antal positioner), `librarySetup` (libraryDefault → bindinger + positionsnavne), `runSetup`.
2. `SymbolTest.svelte`: animationslisten filtreres pr. del (inkl. Løbelys), "Tag er" får *Position* med antal positioner, ny sektion *Som i guiden* med knap pr. position (eller Fra/Til).
3. Tests i `symbolTest.test.ts` (pos, flow, libraryDefault for ventil/vippekontakt/kontakt/pumpe, typer pr. del, alle biblioteksdele kan animeres).
4. FEATURES, BUGS (ingen), CHANGELOG, RELEASE_NOTES, version 0.103.0 b0153, OTA-pakke.

## Berørte filer
`frontend/src/lib/symbolTest.ts`, `symbolTest.test.ts`, `frontend/src/pages/SymbolTest.svelte`, manual `06-symboler-og-guiden.md` (kort afsnit), doku, `version.json`.

## Risici
- Løbelys kræver at symbolet er tegnet i DOM (kun verificerbart i browser).
- Kun frontend; ingen backend-/PLC-berøring.
