# Plan: passiv visning af positioner + 7-/11-segment display (2026-10-30)

## A. Kun passiv visning med positioner (fx 3-punkts omskifter der kun viser PLC'ens trin)

**Mål:** et symbol med positioner kan vise PLC'ens position uden at kunne betjenes og uden at kræve et kommando-tag.

**Beslutning:** nyt felt `passive: bool` (standard `false`) på symbolopsætningen, sammen med `op = positions`.
Alternativer: ny `op` (flere grene i al kode) · `view` + positioner (ændrer betydningen af `view`). Flaget er mindst invasivt.

**Adfærd når `passive = true`:**
- Trin 1: valget *Kun passiv visning* får for symboler med positioner en underindstilling "Vis symbolets position fra tilbagemelding". *Interaktiv betjening* uændret.
- Trin 2: kolonnen **Kommando** (og *Skrives som*, *Fejlsignal*) er grå/deaktiveret; **Tilbagemelding er krævet** på alle signaler i kontaktplanerne (ellers kan positionen ikke findes).
- Trin 3: kontaktplanerne beskriver tilbagemeldingens mønster pr. position (som nu).
- Trin 4: *Vis* låses til "PLC'ens position"; ingen valideringsalarm for "valgt position".
- Trin 5: "Kun passiv visning — intet at betjene" (ingen bekræftelse, nøglelås, klik-valg).
- Backend: kommando-tag ikke påkrævet/skrivbart; `operate` afviser (409 "kun visning"); låse og skrivning ryddes; runtime finder positionen kun fra tilbagemeldingen.
- Overview: symbolet får ikke `hv-clickable`/`hv-step`, markør er pil, tooltip "Kun visning — kan ikke betjenes". Lille mærke (øje/lås-fri) kan tilføjes ved tilstandsmærket.
- Skift mellem passiv og interaktiv bevarer kontaktplanerne (tilbagemeldingerne bliver til kommando-tags ved skift til interaktiv kræver nyt valg — vises som fejl i trin 2).

**Berørte filer (≈10):** `backend/app/services/symbols.py` (model, validering, plans), `symbol_runtime.py`, `backend/app/api/symbols.py` (operate), `symbol_convert.py`, `frontend/src/lib/symbolConfig.ts`, `SymbolGuide.svelte`, `Overview.svelte`, `symbolUi.ts`, tests (backend + frontend), manual kap. 06, FEATURES/CHANGELOG/RELEASE_NOTES.
**Version:** MINOR (ny feature) → 2.8.0.

## B. Display-element: 7-/11-segment, 1–16 cifre

**Mål:** ét bibliotekssymbol "Segment-display" med valgfri type (7 eller 11 segmenter) og 1–16 cifre, styret af ét tal-tag.

**Antagelse (bekræft):** *7-segment* = a–g + decimalpunkt (8 pladser pr. ciffer). *11-segment* = a–f, midterstregen delt i to (g1/g2), to lodrette midtersegmenter (i/l) og decimalpunkt = 11 — kan vise tal og de fleste store bogstaver.

**Løsning:** (1) Indsættelse i Tegn som *Omskifter med egne positioner*: felter *Type* (7/11) og *Antal cifre* (1–16) → tegner N cifre med segmenter som navngivne dele (`data-hv-pid`, fx `c3_a`). (2) Ny animationstype **Segmenter** (`segments`) på hele symbolet: kilde = tal-tag; parametre: type, cifre, decimaler, fortegn (−), foranstillede nuller (til/fra), farve tændt/slukket, justering (højre/venstre), vis "OFL" ved overløb. Teksten formateres som i `Værdi` (skala/decimaler fra tagget) og hvert tegn slår de rette segmenter til. (3) Hurtig opsætning i guiden: vælg tag → opretter animationen.
Alternativer: ét symbol pr. cifre-antal (mange biblioteksposter) · hvert ciffer sit tag (besværligt). Valgt: ét symbol, én animation.

**Berørte filer (≈12):** `frontend/src/lib/symbols.ts` (+ ny `segDisplay.ts`: tegning + tegn→segmenter), `animate.ts`, `symbolConfig.ts`, `AnimParams.svelte`, `DrawEditor.svelte`, `backend/app/services/symbols.py` (ASegments, ANIM_PARAMS, label), tests (formatering, tegn→segmenter, tegning 1–16 cifre, backend-validering), manual kap. 04/05/06/07, FEATURES/CHANGELOG/RELEASE_NOTES.
**Version:** MINOR → 2.9.0 (efter A).

## Rækkefølge og risici
1. A først (rører backend-datamodel og bør være færdig og testet), commit + OTA-pakke 2.8.0.
2. B bagefter, commit + OTA-pakke 2.9.0.
- **Datamodel:** `passive` er nyt felt; gamle opsætninger mangler det → standard `false`, ingen migration.
- **Sikkerhed/PLC-skrivninger:** `operate` skal afvise passive symboler i backend (ikke kun i UI) — reviewer-agenten kontrollerer A før commit.
- **Visuel verifikation:** begge dele ses i browseren mod testserveren før de meldes færdige.
