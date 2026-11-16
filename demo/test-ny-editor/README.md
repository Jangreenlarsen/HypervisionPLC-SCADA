# Testprogram til tegningen `test_ny_editor`

Et ST-program uden fysisk I/O, der får tegningen til at leve: pumpe, tre 3-vejs ventiler, motorventil, lampe, tank, statusfelter, alarmer og analoge værdier. Programmet har sine **egne tags** (alle med præfikset `TNE_`) og rører ikke varmedemoens tags. SCADA læser og skriver variablerne direkte over PLC'ens REST API.

| Fil | Indhold |
|---|---|
| `test_ny_editor.st` | Programmet. 226 af 512 AST-noder, 34 variable, 8 af 8 timere |
| `load.py` | Indlæser det i ét Logic-nummer: `PLC_USER=… PLC_PASS=… python demo/test-ny-editor/load.py http://<plc> --logic=N` |
| `test/run.sh` | PC-test med PLC'ens egen ST-compiler og VM (`bash demo/test-ny-editor/test/run.sh`, kræver g++ og PLC-repoet) |

**Plads:** varmedemoen bruger alle fire Logic-pladser. Den 2026-11-16 er Logic1-4 på demo-PLC'en (10.1.1.34) slettet, og testprogrammet ligger i **Logic1**; tagsene hedder `logic:1:<navn>`. Varmedemoen indlæses igen med `demo/varme-plc/load.py` (kilden er uændret i repoet). `load.py` her kræver `--force`, hvis pladsen har et andet program. `--check` viser, hvad der ligger hvor.

## Sådan virker det

- **Auto** (`TNE_AUTO` = 1, standard): ni trin à 10 s styrer kommandoerne, og forløbet gentages.
- **Manuelt** (`TNE_AUTO` = 0): du skriver kommandoerne `TNE_CMD_*` fra SCADA.
- **Tilbagemeldinger** kommer, som en rigtig PLC ville give dem: pumpen 2 s efter kommandoen, V1 og V2 med 2 s gangtid begge veje (så de står i den gamle position, til de er nået frem), V3 og motorventilen straks.
- **Alarm:** er pumpen kommanderet uden tilbagemelding i 4 s, låser `TNE_ALARM` til kvittering. Ret fejlen, vent til pumpen kører, og skriv `TNE_KVIT` = 1.

| Trin | Pumpe | V1 | V2 | V3 | Motorv. | Lampe | Hvad du ser |
|---|---|---|---|---|---|---|---|
| 0 | fra | A | A | A | lukket | fra | alt står |
| 1 | til | A | B | A | åben | | flow gennem tanken |
| 2 | til | A | A | B | åben | | andet flow gennem tanken |
| 3 | til | B | A | B | åben | | |
| 4 | til | B | B | A | åben | | |
| 5 | til | A | A | A | lukket | | pumpen kører, ingen vej gennem tanken |
| 6 | til | A | B | A | åben | til | som trin 1, og lampen er tændt |
| 7 | til, **uden tilbagemelding** | | | | lukket | | pumpealarm, status *Fejl* |
| 8 | fra | | | | | til | alarmen står, til trin 0 kvitterer |

Motorventilen sidder på tankens udløb i tegningen, så der kun er flow gennem tanken, når den er åben.

Flowet regner SCADA selv ud fra pumpens kapacitet, ventilernes tilstande og de bundne forbindelser.

## Betjening på tegningen

På demoen (version 101 af `test_ny_editor`) kan kredsløbet styres fra Overview. Betjeningen kræver en bruger, der må betjene (operatør eller højere).

| Hvad | Sådan |
|---|---|
| **Auto / manuel** | Kontakten *Auto (Til) / manuel (Fra)* øverst til venstre i panelet (`TNE_AUTO`). Tryk i højre side for Til, i venstre side for Fra. I manuel holder programmet trinene og rører ikke kommandoerne |
| **Pumpe, ventiler, motorventil, lampe** | Tryk på symbolet og vælg position i dialogen. Kommandoen går til `TNE_CMD_*`, og symbolet viser tilbagemeldingen (`TNE_FB_*`). Ingen bekræftelse. Virker kun i **manuel**, for i auto skriver programmet kommandoerne igen hvert scan |
| **Pumpefejl** | Kontakten *Pumpefejl (Til = udebliver)* (`TNE_FEJL`): pumpen melder ikke tilbage, og efter ca. 4 s kommer alarmen og status *Fejl* |
| **Kvittér** | Knappen *Kvittér alarm* sender en kort puls til `TNE_KVIT`. Ret fejlen først og vent til pumpen kører igen, ellers sættes alarmen igen |

Panelets tre symboler er et bibliotekets *Vippekontakt* (to stk.) og *Trykknap (puls)* med navnene *Auto / manuel*, *Pumpefejl (ingen tilbagemelding)* og *Kvittér alarm*.

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
| Pumpe (`pumpe_2`) | tag `TNE_CMD_PUMPE`, tilbagemelding `TNE_FB_PUMPE`. Flow-rate følger positionen, eller vælg `TNE_RATE`. Symbolerne er gjort betjenelige (se ovenfor) |
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
