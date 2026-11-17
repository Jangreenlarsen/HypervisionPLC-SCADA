# Analyse: brøndstation med klordosering (option B) som SCADA-demo

Status: analyse, ikke implementeret. Dato: 2026-11-17.

## 1. Hvad kilderne faktisk giver

| Kilde | Indhold | Brug |
|---|---|---|
| Nasby, *Case Study – New Control System and HMI for a Municipal Ground Water Well* (ISA WWID, 2020), Guelph Emma Well | Proces, udstyr, styringsprincip, HMI-opbygning | **Forlægget til procesmodellen** |
| Winnipeg, kontrolbeskrivelse Maclean Pumping Station (2025) | Ventilation/lækagetilstande i klorrum (tilstand 0/1/2), tag- og I/O-struktur, HMI-koder (R, RA, R/W, W1), alarmhandlinger 1/2/3 | Kun inspiration til alarmklasser og tagstruktur. Det er *ikke* vandprocessen |

**Hvad der står om Emma Well:** en 60 HP dykpumpe i brønden giver ca. 35 L/s. Efter pumpen sidder en pilotstyret modtryksventil, der virker som kontraventil. Brønden har niveau-, tryk- og flowmåler; flowmåleren bruges også til at overholde indvindingstilladelsens maks. flow (L/s) og maks. døgnmængde (m³). Efter ventilen doseres 12 % natriumhypoklorit flow-proportionalt (flow og et mål-doseringssetpunkt). Derefter en baffled underjordisk kontakttank (kontakttid/CT), en klor-analysator før og en efter kontakttanken (POE). Efter-analysatoren bruges til høj- og lav-klor-shutdown-interlocks. En motordrevet skylleventil (backflush) spuler kontakttanken, før brøndpumpen starter. HMI: oversigt, trendbillede, popups for pumpe, skylleventil og hypopumpe, setpunkter, interlock-oversigt, alarmliste og en realtids-CT-beregner.

**Hvad der ikke står:** ingen tal for alarmgrænser, forsinkelser, niveaugrænser eller klorgrænser, og ingen PLC-kode. Alle tal i en simulering er derfor **vores antagelser** og skal stå som parametre, ikke som "fra kilden".

## 2. Anlægget vi modellerer

```
Brønd (LT) → Brøndpumpe P1 (FT, PT) → Modtryksventil → [hypo-indsprøjtning P2] → Kontakttank (AT1 før, AT2 efter)
                                                         ↑ Hypotank (LT)           ↓                      → Højdebeholder (LT) → Forbrug
                                      Skylleventil XV1 (spuler kontakttanken før start)
```

Skaleret til vores demo (værdier er forslag): P1 2100 l/min (35 L/s), hypo 12 % NaOCl, kontakttank 40 m³, højdebeholder 300 m³.

Flow-proportional dosering: `hypo [L/h] = Q[L/s] × 3600 × dosis[mg/L] / 120.000` (12 % = 120 g/L). Ved 35 L/s og 1,0 mg/L giver det ca. 1,05 L/h.

## 3. Styring (hvad PLC-koden skal gøre)

1. **Driftsform:** Fra / Manuel / Auto.
2. **Auto-start/stop:** højdebeholder under startniveau → start-sekvens. Over stopniveau → stop-sekvens. Hysterese mellem dem.
3. **Tilladelser (permissives):** brøndniveau over lavt, hypotank over tom, ingen låst alarm, ingen klor-shutdown.
4. **Startsekvens:** (1) åbn skylleventil XV1 i en tid, (2) luk XV1, start P1, (3) vent på stabilt flow, (4) start hypodosering (flow-proportional + trim fra AT2), (5) Drift.
5. **Stopsekvens:** stop hypo, vent kort, stop P1, luk ventiler.
6. **Interlocks (trip):** lavt/højt klor AT2 efter forsinkelse, brøndniveau lavt-lavt, hypotank tom, flow under minimum efter start, maks. flow/døgnmængde (tilladelsen).
7. **Alarmer:** trinvise (advarsel/alarm/trip), med klasse 1/2/3 (som Winnipeg: straks/dagtid/ingen udkald), kvittering og første-årsag.
8. **Beregninger:** CT (klor × kontakttid, kontakttid = tankvolumen / flow), døgnmængde (m³).

## 4. Simulering (hvad PLC-koden skal efterligne)

Alt kører i PLC'en, så SCADA får rigtige tags (som `test_ny_editor` og `varme-plc`).

| Del | Model |
|---|---|
| Brønd | Niveau falder med P1-flow, genoprettes med tilstrømning (1. ordens) |
| Brøndpumpe | Rampe op/ned, flow og tryk afhænger af brøndniveau, motorfejl som scenarie |
| Hypotank/pumpe | Niveau falder med doseret mængde, påfyldning som scenarie |
| Kontakttank | Klor: 1. ordens forsinkelse med tidskonstant = V/Q, plus lille nedbrydning. Forsinkelsen gør AT2 reagerer efter AT1, ligesom i virkeligheden |
| Analysatorer | AT1/AT2 med støj og et "analysator-drift"-scenarie |
| Højdebeholder | Niveau = tilgang minus forbrug (døgnmønster, hurtig tidsfaktor) |
| Scenarier | Hypotank tom, brøndpumpe-trip, lavt brøndniveau, høj efterspørgsel, klorfald/-stigning, analysatorfejl, strømsvigt |

## 5. Passer det i vores PLC og SCADA?

**PLC-grænser** (firmware v7.9.68.168, FEAT-521, opgraderet 2026-11-17): maks. **64 variabler** (uændret), **16 timere** (var 8), **16 strengliterale** (var 8), **2048 AST-noder** (var 512) pr. program og **64 globale variable** (var 16). Variabelgrænsen på 64 gør stadig, at styring plus fuld procesmodel ikke er ét program. Derfor opdeling i tre programmer (varme-plc brugte fire), nu med god luft i noder, timere og globale:

| Program | Indhold | Målt (PC-test) |
|---|---|---|
| `globals.st` | Delte `GLOBAL_VAR` (max 64) | 17 |
| Logic2 | Styring, interlocks og alarmer: driftsform, sekvens, flow-proportional dosering | 53 vars, 574 noder |
| Logic3 | Proces: brønd, pumpe, hypo, højdebeholder, klor, klokke, scenarier | 38 vars, 364 noder |

Samlet i to programmer (Jan: "kombinere i ét modul, hvis muligt"). Et enkelt program er ikke muligt: styringen alene bruger 53 af 64 variable. Demo-PLC'en har Logic2-4 ledige; vandværket bruger Logic2-3, Logic1 beholder `test_ny_editor`, og Logic4 er fri. Implementeret i [demo/vandvaerk/](../demo/vandvaerk/README.md) og kører på demo-PLC'en.

Rest-risiko: variabelgrænsen på 64 og kendte dialektbegrænsninger (fleretiketters `CASE` virker ikke, brug IF/ELSIF).

**SCADA-funktioner vi allerede har og kan bruge direkte:** flowberegning (pumpe, ventiler, T-stykker), løbelys langs rørene, statusfelter med tekst/farve pr. værdi, trykknap, til/fra med bekræftelse, alarmer og kvittering, trends, "flow i et andet element" til at vise doseret mængde.

**Mulige huller (skal tjekkes mod symbolbiblioteket, før vi lover noget):**
- Symbol til analysator (AT1/AT2) og doseringspumpe findes måske ikke. Alternativ: statusfelt/instrument eller nyt symbol i editoren.
- Hypo-indsprøjtning er en meget lille mængde ind i hovedrøret. Det skal vises uden at forstyrre hovedflowet i flowberegningen (separat lille rør med eget flow).
- Kontakttank med baffles tegnes som tank med skillevægge (ren tegning).
- CT og dosering som tal i statusfelter (almindelig tekst-animation).

## 5b. Symboler: hvad findes, og hvad skal være nyt

Biblioteket (`frontend/src/lib/symbols.ts`) har pumpe, tank, rør, T-stykke, reduktion, kontraventil, motor-/magnet-/kugleventil, TT/PT/FT/LT-bobler, statusfelt, værdifelt, setpunkt, trendgraf, betjeningssymboler og alarm-genvej.

| Behov | Findes? | Forslag |
|---|---|---|
| Brøndpumpe, hovedrør, ventiler, flow-/tryk-/niveaumåler | Ja | Genbrug |
| Hypotank, højdebeholder | Ja (Tank) | Genbrug |
| **Klor-analysator (AT)** | Nej | **Nyt**: `bubble('AT')`, samme som FT/LT, kun en linje kode |
| **Doseringspumpe** (lille membran-/peristaltisk) | Nej (Pumpe er for stor og tegnet som centrifugalpumpe) | **Nyt**: lille pumpe med løbehjul/stempel, så den kan flyttes, drejes og bruges i flowberegningen |
| Kontakttank med skillevægge (baffles) | Delvis (Tank uden skillevægge) | Anbefalet nyt: tank med 3–4 skillevægge og "Niveau"-del |
| Brønd med dykpumpe | Delvis | Anbefalet nyt: brønd/boring i snit med dykpumpe |
| Indsprøjtningspunkt for hypo | Delvis (T-stykke + lille rør) | Genbrug T-stykke |
| Vandtårn, vandforbruger | Nej | Valgfrit, kan klares med Tank |

Det mindste, der skal til: **AT og doseringspumpe** (2 symboler). Med kontakttank og brønd (4 symboler) ligner tegningen et rigtigt vandværk.

Konsekvenser af nye symboler: de skal i symbolbiblioteket med rolle i flowberegningen (pumpe/kilde), oversættelser/hint, FEATURES.md først, MINOR-version, genereret manualkapitel (`GEN_MANUAL=1`) og nye bibliotekbilleder. De bruges bagefter i alle andre tegninger.

## 6. Forslag til arbejdsplan

| Trin | Resultat | Berørte filer |
|---|---|---|
| 1. Procesbeskrivelse | Tag-liste, alarmliste, tilstandsdiagram, parametre | `demo/vandvaerk/README.md` |
| 2. ST-program + PC-test | Logic1–4 + globals, testet med PLC'ens egen compiler/VM som `test_ny_editor` | `demo/vandvaerk/*.st`, `test/run.sh` |
| 3a. Nye symboler | AT, doseringspumpe (evt. kontakttank, brønd) i biblioteket, manual og billeder | `symbols.ts`, manual, `FEATURES.md` |
| 3b. Tags og tegning | Tegning `vandvaerk`, bundet til tags, evt. nye symboler | `load.py`, `scada_setup.py`, symboler |
| 4. Betjening | Auto/manuel, setpunkter (start-/stopniveau, dosis, grænser), kvittér, scenarie-vælger | tegning + konfiguration |
| 5. Test på demo | Gennemspil alle scenarier, kontrol `audit_drawings.py` | |
| 6. Dokumentation | README, evt. manualafsnit | |

Trin 3a er den eneste ændring i SCADA-koden og leveres som egen version før tegningen.

## 7. Beslutninger der kræves

1. ~~Hvor kører det?~~ Afgjort: demo-PLC'en har 3 frie programpladser (Logic2–4), `test_ny_editor` beholder Logic1.
2. **Skala:** realistiske værdier (35 L/s, 12 % hypo) eller et mindre, mere overskueligt anlæg?
3. **Tidsfaktor:** realtid eller hurtigere (fx 10×), så et døgn kan ses på få minutter.
4. **Omfang:** kun overbliksbillede, eller også trendbillede og alarmliste som i Emma Well?
