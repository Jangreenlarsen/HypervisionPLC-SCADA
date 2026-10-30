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

---

# Plan C: live preview ved animationerne i symbol-guiden (2026-10-30)

**Mål:** i guidens trin 4 står et lille preview af symbolet ved siden af animationerne, som viser, hvordan symbolet ser ud, når animationerne kører — og opdaterer sig med det samme, når en indstilling ændres.

**Beslutning:** ét preview for hele symbolet (alle animationer samtidig, som på Overview) frem for ét pr. animation — det viser samspillet (flere animationer på samme del, aktiv/passiv, prioritet). Alternativ: ét lille billede pr. animation (12 klon af symbolet, uoverskueligt).

**Løsning (kun frontend, ingen backend- eller datamodel-ændring):**
- Ny komponent `AnimPreview.svelte` i trin 4 (sticky i højre kolonne på brede skærme, over animationerne på smalle). Symbolets SVG hentes fra tegningen (guiden henter den allerede til farvehjælpen), klones til en lille indlejret `<svg>` med `viewBox` efter symbolets kasse.
- Genbruger Symboltestens motor (`symbolSim.ts`: `SimTag`, `SimAnim`, `syncSim`, `bindingOf`) og den rigtige animationsmotor (`applyBinding`) — så preview'et ser ud som på Overview.
- Ny ren funktion `simFromConfig(cfg, symbol)` (testet): laver SimAnim/SimTag ud fra guidens opsætning. Kilden afgør betjeningen i preview'et:
  - *til/fra-tag, logikblok, alarm, "altid til"* → to knapper **Fra / Til**
  - *tal-tag* → skyder fra min til max (område efter animationernes Min/Max)
  - *symbolets position* eller *pr. værdi* → en knap pr. position (positionens navn)
  - samme kilde bruges af flere animationer → én kontrol (som i Symboltest)
- Knapper: **Afspil** (løber gennem værdierne), **Nulstil**, og *Kvalitet* (God / Kommunikationsfejl) vises ikke i første version.
- "Gælder i positionerne", aktiv/passiv og "pr. værdi" oversættes som backend gør (`params.pos`, `only`, `when`, `pos_values`) — samme regler som `config_bindings`.
- Preview'et ændrer intet på serveren og gemmer intet.

**Berørte filer (≈5):** `frontend/src/lib/AnimPreview.svelte` (ny), `frontend/src/lib/simFromConfig.ts` (ny, ren logik) + test, `SymbolGuide.svelte` (monterer panelet; tegnings-SVG gemmes), `manual/06` (+ skærmbillede), FEATURES/CHANGELOG/RELEASE_NOTES.
**Version:** MINOR → 2.10.0.

**Risici:** (1) symbolets SVG skal klones uden id-kollisioner med tegningen (klonen sættes i et isoleret `<svg>`; id'er bevares, da dele findes via id); (2) segment-display og løbelys kræver at animationsmotoren kører i et frakoblet DOM — Symboltest gør det allerede; (3) ydeevne: preview'et opdateres med 100 ms debounce ved ændringer.
**Visuel verifikation:** installeres på testserveren og ses i guiden (trin 4) for omskifter, ventil, pumpe og segment-display.
