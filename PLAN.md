# Plan: Navngivne symbolgrupper (Tegn + Bindinger)

Ønske (Jan, 2026-10-23): i Tegn skal man kunne samle symboler i navngivne grupper i en ny sektion i symbollisten. Samme symbol må være med i flere grupper (overlap). To slags: (1) gruppe efter funktion (rør, vinkelrør, T-stykker, bøjninger …), (2) gruppe af det man har valgt på tegningen (fx 3-vejs ventil, rør, akkutank). Skal kunne bruges i både Tegn og Bindinger.

## Beslutninger (Jan, 2026-10-23)
- En **gruppe** = navngivet udvalg af placerede symboler/elementer på tegningen (pr. tegning), fx "Fyr uden akku-tank" (funktion) eller et frit udvalg (3-vejs ventil, rør, akkutank). Teknisk samme mekanisme; `kind` = `function` | `selection` bruges kun til at sortere listen i to underafsnit.
- **Overlap**: et symbol må være med i flere grupper.
- **Bindinger på gruppen = animationer ejet af gruppen**: gruppen kan få egne animationer/tags på sine symboler (fx "fyr kører" farver alle rør i gruppen). Et rør i to grupper har sin egen opsætning + én pr. gruppe, og de gælder samtidig. Symbolets egen opsætning ændres ikke.
- **Farver i symbolguiden**: hver animation mærkes med sin ejer — symbolets egne neutralt, hver gruppes i gruppens farve + gruppenavn. I den kontekst man åbnede fra kan kun ejerens egne rækker redigeres; andre ejeres rækker vises låst (så man ser, hvad man ikke skal røre).
- Rører IKKE SVG-tegningen (ingen `<g>`). Vises i Tegn (sektion "Grupper" i symbollisten) og i Bindinger.

## Lagring (alternativer)
A) nye tabeller `symbol_groups`, `symbol_group_members`, `group_anims` (en række pr. animation, ejer = gruppe + element + del) · B) JSON-blob pr. gruppe · C) kun browser. Valg **A**: delt, med i backup, ingen read-modify-write af hele listen. C afvist.

## Trin
1. FEATURES.md (planned).
2. Backend: tabeller + migration (`storage/db.py`, MINOR); `services/symbol_groups.py` (CRUD, medlemmer, gruppe-animationer med samme validering som symbolets egne via `symbols.py`); API i `api/symbols.py` (ENGINEER skriv / VIEWER læs; audit-log; unikt navn, grænser). Medlemmer der ikke findes længere vises som forsvundne.
3. Live-visning: gruppe-animationer flettes ind i drawing-viewets bindinger efter symbolets egne (eksisterende prioritetsregel "øverste aktive vinder" pr. del og type gælder; rækkefølge: symbolets egne, derefter grupper efter gruppens rækkefølge). Skal måles på Pi (antal bindinger).
4. Backup: grupper + gruppe-animationer med i eksport/import.
5. Tegn (`DrawEditor.svelte`): sektionen "Grupper" (to underafsnit), "Gem markering som gruppe …", klik markerer alle, omdøb/slet, tilføj/fjern medlem. Opsæt-gruppe-animationer åbner `SymbolGuide` i gruppe-kontekst.
6. `SymbolGuide.svelte`: ejer-markering med farve/navn og låste rækker for andre ejere.
7. Bindinger (`Editor.svelte`): grupper som valg/filter i "Symboler og bundne".
8. Tests (backend CRUD/overlap/rettigheder/backup/live-fletning; frontend gruppelogik) + visuel kontrol i browser.
9. Version 0.130.0, CHANGELOG, RELEASE_NOTES, OTA-pakke. Evt. delt i flere commits: (a) grupper + liste, (b) gruppe-animationer + farvemarkering.

## Risici
- Samme type animation (fx Farve) på samme del fra symbol og to grupper: rækkefølge/prioritet skal være forudsigelig og vises i guiden.
- "Erstat med symbol" uden "behold id" giver nyt id → medlem forsvinder (vises som forsvundet, kan flyttes).
- Omfanget er stort — foreslår at levere i to trin: (a) grupper som valg/markering (Tegn + Bindinger), derefter (b) gruppe-ejede animationer + farvemarkering.

## Efter design-review (2026-10-23) — v0.131.1 rettet, resten venter på Jans OK
Rettet i v0.131.1: (1) `used_ids` reserverer gruppemedlemmer; (2) en logikblok, som en gruppe-animation henviser til, kan ikke fjernes.
Åbne punkter, i prioriteret rækkefølge:
3. **Samtidig redigering**: medlemsændringer sender hele listen fra skærmens kopi → forældet fane kan slette andres medlemmer + deres animationer. Løsning: delta-endpoints (tilføj/fjern) eller `updated_at` som If-Match (409).
4. **Ydelse**: `_group_bindings` kalder `subtree_ids` (parser hele SVG) pr. række; `_compute` kører også ved hver operatørskrivning (`scope.operable_tags`). Løsning: én id→efterkommere-tabel pr. kald og/eller cache af `_compute` pr. (tegning, version, ændringstæller). Mål på Pi.
5. **Vinder ved overlap**: uden `when` vinder den binding, hvis tag sidst ændrede sig (Overview/Editor gentegner kun ændrede bindinger) — ikke "den sidste". Løsning: tegn altid hele `element+kanal`-gruppen om; advarsel ved overlap af samme del+type på tværs af ejere; ret teksten i `GroupAnims.svelte`; lad gruppernes rækkefølge kunne ses/ændres.
6. **Forældreløse medlemmer**: ingen "flyt" som for symbolopsætninger; gruppe-animationer på forsvundne dele advarer ikke; backup validerer ikke dele/logik-henvisninger.
7. Manglende tests: `visible_tags` for begrænset bruger med kun gruppe-tags; operatør får ikke skriveret via gruppe; `priorityGroups` på tværs af symbol og grupper.
