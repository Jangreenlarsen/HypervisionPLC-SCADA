# Testprogram til tegningen `test_ny_editor`

Et ST-program uden fysisk I/O, der får tegningen til at leve: pumpe, tre 3-vejs ventiler, motorventil, lampe, tank, statusfelter, alarmer og analoge værdier. Programmet har sine **egne tags** (alle med præfikset `TNE_`) og rører ikke varmedemoens tags. SCADA læser og skriver variablerne direkte over PLC'ens REST API.

| Fil | Indhold |
|---|---|
| `test_ny_editor.st` | Programmet. 226 af 512 AST-noder, 34 variable, 8 af 8 timere |
| `load.py` | Indlæser det i ét Logic-nummer: `PLC_USER=… PLC_PASS=… python demo/test-ny-editor/load.py http://<plc> --logic=N` |
| `test/run.sh` | PC-test med PLC'ens egen ST-compiler og VM (`bash demo/test-ny-editor/test/run.sh`, kræver g++ og PLC-repoet) |

**Plads:** varmedemoen bruger alle fire Logic-pladser på demo-PLC'en. Læg testprogrammet på en anden PLC, eller erstat et varmeprogram med `--force`. `--check` viser, hvad der ligger hvor.

## Sådan virker det

- **Auto** (`TNE_AUTO` = 1, standard): ni trin à 10 s styrer kommandoerne, og forløbet gentages.
- **Manuelt** (`TNE_AUTO` = 0): du skriver kommandoerne `TNE_CMD_*` fra SCADA.
- **Tilbagemeldinger** kommer, som en rigtig PLC ville give dem: pumpen 2 s efter kommandoen, V1 og V2 med 2 s gangtid begge veje (så de står i den gamle position, til de er nået frem), V3 og motorventilen straks.
- **Alarm:** er pumpen kommanderet uden tilbagemelding i 4 s, låser `TNE_ALARM` til kvittering. Ret fejlen, vent til pumpen kører, og skriv `TNE_KVIT` = 1.

| Trin | Pumpe | V1 | V2 | V3 | Motorv. | Lampe | Hvad du ser |
|---|---|---|---|---|---|---|---|
| 0 | fra | A | A | A | lukket | fra | alt står |
| 1 | til | A | B | A | | | flow gennem tanken, ca. 67 l/min |
| 2 | til | A | A | B | | | ca. 47 l/min |
| 3 | til | B | A | B | | | ca. 56 l/min |
| 4 | til | B | B | A | | | ca. 67 l/min |
| 5 | til | A | A | A | | | pumpen kører, intet flow gennem tanken |
| 6 | til | A | B | A | åben | til | motorventil og lampe |
| 7 | til, **uden tilbagemelding** | | | | | | pumpealarm, status *Fejl* |
| 8 | fra | | | | | til | alarmen står, til trin 0 kvitterer |

Flowtallene er dem, SCADA'ens egen flowberegning gav for tegningens rør og ventiler, da jeg målte dem (66,7, 46,8 og 55,7 l/min). De afhænger af pumpens kapacitet og ventilernes opsætning.

## Tags (kilde `logic:<N>:<navn>`)

Skrivbare i SCADA: `TNE_AUTO`, `TNE_CMD_*`, `TNE_FEJL`, `TNE_KVIT`, `TNE_RATE`. Resten er kun til læsning.

| Tag | Type | Bruges til |
|---|---|---|
| `TNE_AUTO` | BOOL, skriv | auto/manuel |
| `TNE_CMD_PUMPE` `TNE_CMD_V1` `TNE_CMD_V2` `TNE_CMD_V3` `TNE_CMD_MV` `TNE_CMD_LAMPE` | BOOL, skriv | kommandoer. Ventiler: 0 = A → AB, 1 = B → AB |
| `TNE_FEJL` | BOOL, skriv | 1 = pumpen melder ikke tilbage (fejlinjektion) |
| `TNE_KVIT` | BOOL, skriv | kvitterer pumpealarmen (nulstiller sig selv) |
| `TNE_RATE` | REAL, skriv, 1,0 | pumpens flow-rate 0,00–1,00 (hvis den bruger et tag) |
| `TNE_FB_PUMPE` `TNE_FB_V1` `TNE_FB_V2` `TNE_FB_V3` `TNE_FB_MV` | BOOL | tilbagemeldinger |
| `TNE_STATUS` | INT | 0 Stop, 1 Starter, 2 Kører, 3 Fejl, 4 Stopper. Til *Tekst pr. værdi* |
| `TNE_TXT` | STRING | samme som tekst. Til et statusfelt |
| `TNE_TRIN` | INT | aktuelt trin 0–8 |
| `TNE_ALARM` | BOOL | pumpealarm (låst, kvitteres med `TNE_KVIT`) |
| `TNE_TRYK_HOEJ` | BOOL | højt tryk, slår til over 5,5 og fra under 5,0 |
| `TNE_TEMP` | REAL | 10–90, glat sinus på ca. 63 s |
| `TNE_TRYK` | REAL | 1–6 bar, sinus på ca. 21 s |
| `TNE_NIVEAU` | REAL | 0–100 %, stiger med 2 pr. sekund, når pumpen kører, og falder med 1 ellers |
| `TNE_FLOW` | REAL | målt flow, ca. 50–70 l/min, når pumpen kører, ellers 0 |

## Bind tegningen til de nye tags

I guiden for hvert symbol (skift tagget i trin 2, og vælg kilden i trin 4):

| Symbol | Tags |
|---|---|
| Pumpe (`pumpe_2`) | tag `TNE_CMD_PUMPE`, tilbagemelding `TNE_FB_PUMPE`. Flow-rate følger positionen, eller vælg `TNE_RATE` |
| 3-vejs motorventil 5 (`svg_10`) | `TNE_CMD_V1` / `TNE_FB_V1` |
| 3-vejs motorventil 4 (`svg_32`) | `TNE_CMD_V2` / `TNE_FB_V2`. Kontaktplanen er i dag omvendt (1 = A): sæt den til 0 = A, 1 = B |
| 3-vejs motorventil 3 (`trevejs_motorventil_ab`) | `TNE_CMD_V3` / `TNE_FB_V3` |
| Motorventil | `TNE_CMD_MV` / `TNE_FB_MV` |
| Lampe | `TNE_CMD_LAMPE` |
| Statusfelt | tekst pr. værdi på `TNE_STATUS` (0 Stop, 1 Starter, 2 Kører, 3 Fejl, 4 Stopper) |
| Statusfelt 2 | `TNE_TXT` |
| Tank | niveau-animation på `TNE_NIVEAU`, og målt flow `TNE_FLOW` (lavt 0, højt 70) |
| Farve- og blink-animationer | `TNE_TEMP` og `TNE_TRYK` med grænser, `TNE_ALARM` og `TNE_TRYK_HOEJ` til blink |

Alarmer: opret SCADA-alarmer på `TNE_ALARM` og `TNE_TRYK_HOEJ`. Trends: `TNE_TEMP`, `TNE_TRYK`, `TNE_NIVEAU` og `TNE_FLOW`.
