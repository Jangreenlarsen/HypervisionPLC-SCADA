# Plan: Symboltest på avanceret niveau (v0.110.0 →)

## Analyse af Symboltest i dag (v0.109.0)
**Dækker:** 12 animationstyper pr. del (filtreret efter delens geometri), kilderne til/fra, tal og position (2–8), løbelys, symbolets egne `data-hv-part`, bibliotekets guide-opsætning pr. position, baggrund/zoom, delelisten.

**Mangler (svagheder):**
1. **Kun én animation ad gangen**, én fælles værdi. Kan ikke afprøve samspil (fx pumpe: hjul drejer + lampe grøn + status-tekst fra *samme* eller *forskellige* tags).
2. **Ingen simulerede tags.** Alt styres af én skyder. Logikblokke, *gælder i positionerne* (`only`), `when`, retnings-tag til løbelys og alarm-kilder (`@alarm:`) kan ikke afprøves.
3. **Parametre kan ikke ændres.** Farver, grænser, vinkler, afstande, blink-hastighed, flicker-palet, tekster, `glide_s` står som standard — man kan ikke se, hvordan en *opsætning* ser ud, før den gemmes i guiden.
4. **Ingen tidsforløb.** Man trækker i en skyder i hånden; ingen automatisk sweep/afspilning, så blink, glidning og løbelys vurderes dårligt.
5. **Kvalitet og fejltilstande kan ikke simuleres:** ukendt værdi (PLC nede), dårlig kvalitet, alarm ukvitteret/kvitteret (`hv-alarm-*`).
6. **Ingen kontrol på tværs af biblioteket.** Kvalitetsreglerne (SYMBOLSTANDARD §8: palette, navngivne dele) tjekkes kun i enhedstests, ikke synligt for teknikeren.
7. **Intet kan tages med videre.** Resultatet kan ikke gemmes/deles eller overføres til guiden.
8. **Visning:** kun én størrelse ad gangen; ingen side-om-side lys/mørk, og ingen "som i tegningen" (faktisk størrelse).

## Forslag til pakker (vælges af Jan)
- **A. Flere animationer og simulerede tags** *(kerne)*: en liste af testanimationer (del + type + kilde + parametre) og en tag-liste (navn, til/fra/tal/position, værdi). Hver animation vælger sit tag. Genbruger `applyBinding` — samme kode som Overview.
- **B. Parameter-editor**: redigér den valgte animations parametre live (farver, grænser, vinkler, afstand, hastighed, palet, tekster).
- **C. Afspilning**: sweep (op/ned/loop) med hastighed på et tag; viser blink/glidning/løbelys i bevægelse.
- **D. Fejltilstande**: kvalitet (god/dårlig/ukendt), værdi mangler, alarm ukvitteret/kvitteret.
- **E. Biblioteks-selvtest**: tabel over alle symboler — har navngivne dele, farver i paletten, egne animationer gyldige, guide-opsætning kan køres uden manglende dele; rød/grøn pr. symbol.
- **F. Gem/del**: eksportér/importér testopsætning som JSON; "kopiér til guide" (ud fra bibliotekets format).
- **G. Visning**: lys/mørk side om side, faktisk størrelse.

## Trin (rækkefølge)
1. A (logik i `symbolTest.ts`, ren og testet; UI) → 2. B → 3. D → 4. C → 5. E → 6. F/G.
Hver pakke er en egen commit/version (MINOR), så den kan afprøves og rulles tilbage hver for sig.

## Berørte filer
`frontend/src/lib/symbolTest.ts` (+ evt. `symbolTestScenario.ts`), `symbolTest.test.ts`, `frontend/src/pages/SymbolTest.svelte` (deles op i komponenter), manual `06-symboler-og-guiden.md`, doku.

## Risici
- Layout kræver visuel kontrol (headless Edge-testside som sidst).
- Siden vokser: opdel i komponenter; ingen backend- eller PLC-berøring (alt lokalt i browseren, intet gemmes undtagen valgfri JSON-eksport).
- Ingen nye afhængigheder.
