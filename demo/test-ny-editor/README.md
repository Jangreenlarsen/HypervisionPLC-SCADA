# Testprogram til tegningen `test_ny_editor`

Et ST-program uden fysisk I/O, der får tegningen til at leve: hovedpumpe og reservepumpe, tre 3-vejs ventiler, motorventil, lampe, tank, tekstfelter, alarmer og analoge værdier. Programmet har et scenarie, hvor hovedpumpen dør, og reservepumpen overtager. Programmet har sine **egne tags** (alle med præfikset `TNE_`) og rører ikke varmedemoens tags. SCADA læser og skriver variablerne direkte over PLC'ens REST API.

| Fil | Indhold |
|---|---|
| `test_ny_editor.st` | Programmet. 356 af 512 AST-noder, 42 variable, 6 af 8 timere |
| `load.py` | Indlæser det i ét Logic-nummer: `PLC_USER=… PLC_PASS=… python demo/test-ny-editor/load.py http://<plc> --logic=N` |
| `test/run.sh` | PC-test med PLC'ens egen ST-compiler og VM (`bash demo/test-ny-editor/test/run.sh`, kræver g++ og PLC-repoet) |

**Plads:** varmedemoen bruger alle fire Logic-pladser. Den 2026-11-16 er Logic1-4 på demo-PLC'en (10.1.1.34) slettet, og testprogrammet ligger i **Logic1**; tagsene hedder `logic:1:<navn>`. Varmedemoen indlæses igen med `demo/varme-plc/load.py` (kilden er uændret i repoet). `load.py` her kræver `--force`, hvis pladsen har et andet program. `--check` viser, hvad der ligger hvor.

## Sådan virker det

- **Auto** (`TNE_AUTO` = 1, standard): tolv trin à 10 s styrer kommandoerne, og forløbet gentages.
- **Manuelt** (`TNE_AUTO` = 0): du skriver kommandoerne `TNE_CMD_*` fra SCADA.
- **Tilbagemeldinger** kommer, som en rigtig PLC ville give dem: pumperne 2 s efter kommandoen, V1 og V2 med en gangtid på 2-4 s (de står i den gamle position, til de er nået frem), V3 og motorventilen straks.
- **Hovedpumpe og reservepumpe** står parallelt. Er hovedpumpen kommanderet uden tilbagemelding i 4 s, låser `TNE_ALARM`, og **reservepumpen starter af sig selv** (hvis `TNE_RESERVE` = 1). Den stopper igen, når alarmen kvitteres, og hovedpumpen kører. Reservepumpen kan også køres alene med `TNE_CMD_PUMPE2`.
- **Alarm:** ret fejlen, vent til hovedpumpen kører igen, og skriv `TNE_KVIT` = 1. Kvitterer du, mens fejlen stadig er der, sættes alarmen igen.

| Trin | Pumpe | V1 | V2 | V3 | Motorv. | Hvad du ser |
|---|---|---|---|---|---|---|
| 0 | fra | A | A | A | lukket | alt står |
| 1 | til | A | B | A | åben | flow gennem tanken |
| 2 | til | A | A | B | åben | andet flow gennem tanken |
| 3 | til | B | A | B | åben | |
| 4 | til | B | B | A | åben | |
| 5 | til | A | A | A | lukket | pumpen kører, ingen vej gennem tanken |
| 6 | til | A | B | A | åben | som trin 1, og lampen er tændt |
| 7 | til, **hovedpumpen dør** | | B | | åben | ingen tilbagemelding, alarm efter 4 s, **reserven starter** |
| 8 | (hovedpumpen er stadig død) | | B | | åben | reservepumpen kører, scenarie *Reserven har overtaget* |
| 9 | til, hovedpumpen er repareret | | B | | åben | hovedpumpen kører igen, men alarmen står, så reserven bliver |
| 10 | til, **kvittering** | | B | | åben | alarmen kvitteres, reserven stopper, hovedpumpen kører |
| 11 | fra | | | | | lampen er tændt, til trin 0 |

Motorventilen sidder på tankens udløb i tegningen, så der kun er flow gennem tanken, når den er åben. Flowet regner SCADA selv ud fra pumpens kapacitet, ventilernes tilstande og de bundne forbindelser.

## Tekstfelter på tegningen

Fire statusfelter forklarer tilstanden. De viser en tekst og skifter farve efter værdien (*Tekst pr. værdi*, højst 5 pr. felt):

| Felt | Tag | Tekster |
|---|---|---|
| **System** | `TNE_SYSTEM` | Stoppet, Normal drift (hovedpumpen), Reserve kører (hovedpumpe fejl), FEJL: ingen pumpe kører, Starter … |
| **Hovedpumpe** | `TNE_STATUS` | Stoppet, Starter …, Kører, Fejl (ingen tilbagemelding), Stopper |
| **Reservepumpe** | `TNE_STATUS2` | som hovedpumpen |
| **Scenarie** | `TNE_SCEN` | Standby, Normal drift (ventilprøver), Hovedpumpen fejler, Reserven har overtaget, Hovedpumpe kvitteret |

## Betjening på tegningen

På demoen (version 104 af `test_ny_editor`) kan kredsløbet styres fra Overview. Betjeningen kræver en bruger, der må betjene (operatør eller højere).

| Hvad | Sådan |
|---|---|
| **Auto / manuel** | Kontakten *Auto (Til) / manuel (Fra)* øverst til venstre i panelet (`TNE_AUTO`). Tryk i højre side for Til, i venstre side for Fra. I manuel holder programmet trinene og rører ikke kommandoerne |
| **Pumpe, ventiler, motorventil, lampe** | Tryk på symbolet og vælg position i dialogen. Kommandoen går til `TNE_CMD_*`, og symbolet viser tilbagemeldingen (`TNE_FB_*`). Ingen bekræftelse. Virker kun i **manuel**, for i auto skriver programmet kommandoerne igen hvert scan |
| **Hovedpumpe fejl** | Kontakten *Hovedpumpe fejl (Til)* (`TNE_FEJL`): hovedpumpen melder ikke tilbage, og efter ca. 4 s kommer alarmen, status *Fejl*, og reservepumpen overtager |
| **Reserve auto** | Kontakten *Reserve auto (Til)* (`TNE_RESERVE`): Til = reservepumpen overtager af sig selv. Fra = ingen overtagelse, så systemet står med *Ingen pumpe kører* |
| **Reserve fejl** | Kontakten *Reserve fejl (Til)* (`TNE_FEJL2`): reservepumpen melder heller ikke tilbage. Er begge pumper fejlbehæftede, står systemet med *FEJL: ingen pumpe kører* |
| **Kvittér** | Knappen *Kvittér alarmer* sender en kort puls til `TNE_KVIT`. Ret fejlen først og vent til pumpen kører igen, ellers sættes alarmen igen |

Panelets symboler er bibliotekets *Vippekontakt* (fire stk.) og *Trykknap (puls)*. De er udeladt fra *Tjek forbindelser*, fordi de ikke har rør. Reservepumpen (`svg_94`, *Pumpe Sekundær*) er gjort betjenelig som hovedpumpen.

## Tags (kilde `logic:<N>:<navn>`)

Skrivbare i SCADA: `TNE_AUTO`, `TNE_CMD_*`, `TNE_FEJL`, `TNE_KVIT`, `TNE_RATE`. Resten er kun til læsning.

| Tag | Type | Bruges til |
|---|---|---|
| `TNE_AUTO` | BOOL, skriv | auto/manuel |
| `TNE_CMD_PUMPE` `TNE_CMD_PUMPE2` `TNE_CMD_V1` `TNE_CMD_V2` `TNE_CMD_V3` `TNE_CMD_MV` `TNE_CMD_LAMPE` | BOOL, skriv | kommandoer (`..PUMPE2` = reservepumpen). Ventiler: 0 = A → AB, 1 = B → AB |
| `TNE_RESERVE` | BOOL, skriv, 1 | reservepumpen overtager automatisk |
| `TNE_FEJL` `TNE_FEJL2` | BOOL, skriv | 1 = hovedpumpen / reservepumpen melder ikke tilbage (fejlinjektion) |
| `TNE_KVIT` | BOOL, skriv | kvitterer pumpealarmen (nulstiller sig selv) |
| `TNE_RATE` | REAL, skriv, 1,0 | pumpens flow-rate 0,00–1,00 (hvis den bruger et tag) |
| `TNE_FB_PUMPE` `TNE_FB_PUMPE2` `TNE_FB_V1` `TNE_FB_V2` `TNE_FB_V3` `TNE_FB_MV` | BOOL | tilbagemeldinger |
| `TNE_STATUS` `TNE_STATUS2` | INT | hovedpumpens og reservepumpens status: 0 Stop, 1 Starter, 2 Kører, 3 Fejl, 4 Stopper |
| `TNE_SYSTEM` | INT | 0 Stoppet, 1 Normal drift, 2 Reserve overtager, 3 Ingen pumpe, 4 Starter |
| `TNE_SCEN` | INT | scenarie: 0 Standby, 1 Normal drift, 2 Hovedpumpen fejler, 3 Reserven overtaget, 4 Kvitteret |
| `TNE_TXT` | STRING | samme som tekst. Til et statusfelt |
| `TNE_TRIN` | INT | aktuelt trin 0–11 |
| `TNE_ALARM` `TNE_ALARM2` | BOOL | hovedpumpens og reservepumpens alarm (låst, kvitteres med `TNE_KVIT`) |
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
