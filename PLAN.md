# Plan: ny tegne-editor — egen Svelte-UI på `@svgedit/svgcanvas` (option B, 2026-10-30)

**Mål:** Tegn bliver et SCADA-værktøj i stedet for en generel illustrationseditor. Behold SVG-motoren (`@svgedit/svgcanvas` 7.4.2, MIT) og tegningsformatet; erstat SVG-Edits UI + iframe med egne Svelte-komponenter.

**Beslutning:** B frem for A (flere udvidelser i SVG-Edit — vi kæmper fortsat mod dens UI og patcher minificeret kode) og C (maxGraph/Fabric — kræver konvertering, mister id'er/bindinger). Tegninger, id-regler og backend-rensning er uændrede → ingen migration.

## Nyt layout (erstatter 3 værktøjslinjer: vores øverste, SVG-Edits top-kontekstlinje, SVG-Edits venstre)
```
┌ Topbar: Tegning ▾ (ny/åbn/version) · Gem kladde · Gem og udgiv │ Fortryd Gentag │ Størrelse │ Zoom − 100% + Tilpas ┐
├──┬──────────────────────────────────────────────────────────────┬───────────────────────┤
│▣ │                                                              │ Inspektør (faneblade) │
│╱ │                       Lærred                                 │  Egenskaber: X Y B H ∠│
│⌐ │                                                              │   fyld/streg/tekst    │
│▭ │                                                              │  Binding: tag, guide  │
│T │                                                              │  Lag / objekttræ      │
│◇ │                                                              │                       │
│⊞ │                                                              │                       │
├──┴──────────────────────────────────────────────────────────────┴───────────────────────┤
└ Statuslinje: x,y · gitter ☐ fang gitter ☐ fang objekter ☐ trin [10] · værktøjshjælp           ┘
```
- **Venstre værktøjsrail (SCADA-orienteret, få knapper, grupper med undermenu):** Vælg · Rør (ortogonal, Fase 3) · Linje/pil · Form ▸ (rektangel, ellipse, polygon, stjerne, fri) · Tekst · Symbol ▸ (bibliotek/favoritter, træk-og-slip) · Display/Omskifter · Panorér. Fjernes: pipette som værktøj (bliver knap i Inspektør), billede, SVG-Edits formbibliotek (talebobler m.m.).
- **Topbar:** kun dokument-handlinger + fortryd/zoom. Ingen kontekst-felter dér.
- **Markeringshandlinger** (justér, fordel, gruppér/opløs, frem/tilbage, dupliker, slet) vises som en flydende lille linje over markeringen + i højreklik-menu — ikke i topbaren.
- **Inspektør til højre** samler: geometri, stil, tag-binding, symbolguide, id/navn — erstatter dagens højrepanel i DrawEditor.svelte.
- Statuslinje: koordinater + hjælpelinje-indstillinger (i dag gemt i menu).

## Trin
1. **Motor uden UI** (største risiko): `lib/draw/engine.ts` initialiserer `SvgCanvas` direkte i en `<div>` (ingen iframe), wrapper events (selected/changed/zoomed) til Svelte-stores. Bevis: åbn, tegn rektangel, fortryd, gem → identisk SVG som i dag.
2. **Flyt vores funktioner ind** fra `svgedit-host/scada-editor.js` (1138 linjer) som moduler: gitter/fang (`draw/guides.ts`), id-regler/renameCopies (`draw/ids.ts`), symbolindsættelse, normalize/settle. Tests for id- og fanglogik. Rotations-patchen i `copy-svgedit.mjs` erstattes af egen rotationshåndtering.
3. **Nyt layout**: Topbar, ToolRail, Inspector, StatusBar, SelectionBar som Svelte-komponenter; dansk tekst direkte (ingen localize-hacks). Funktionsparitet med i dag.
4. **Rør-værktøj**: forankringspunkter på symboler, ortogonal routing, rør følger symbolet ved flytning (gemmes som almindelig `<path>` + `data-`-attributter der overlever serverens rensning — tjek rensningen først).
5. **Symbolpalet med træk-og-slip** + justér/fordel.
6. Fjern `svgedit`-pakken, `copy-svgedit.mjs`, `svgedit-host/` og `public/svgedit` når 1–3 er verificeret.

**Version (Jan, 2026-10-30):** når den nye editor er færdig og gjort til standard (trin 6), bumpes til **3.0.0**. Indtil da er hver fase en egen commit/version (MINOR), egen OTA-pakke, visuelt verificeret på 10.1.1.31. Fase 1–3 bag skifter (`?editor=ny`) indtil paritet, så Tegn aldrig er ubrugelig.

## Berørte filer
`frontend/src/pages/DrawEditor.svelte` (opdeles), ny `frontend/src/lib/draw/*`, `frontend/svgedit-host/*` (udfases), `frontend/scripts/copy-svgedit.mjs`, `frontend/package.json` (svgcanvas er allerede installeret; `svgedit` fjernes i trin 6), evt. backend SVG-rensning (trin 4), FEATURES.md, manual-billeder.

## Risici
- `svgcanvas` alene er dårligt dokumenteret; dele af værdien (stifelt-redigering, tekstredigering, kontekstmenu) ligger i SVG-Edit-UI'et → må genbygges. Trin 1 er proof-of-concept; holder den ikke, stop og vurdér igen.
- Paritet: mange små opførsler i scada-editor.js (fang, id'er, guide-hooks) — liste dem op før trin 2 og tjek af én for én.
- Manualens skærmbilleder skal tages om.

---

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
