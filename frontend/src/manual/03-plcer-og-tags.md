# PLC'er og tags

Du skal bruge en **PLC** og nogle **tags**, før en tegning kan vise noget. Begge dele opsættes af en tekniker eller admin under **Opsætning**.

## PLC'er

Siden **PLC'er** lister de HypervisionPLC-enheder, SCADA'en henter data fra. Tryk **Tilføj PLC** og udfyld:

| Felt | Betydning |
| --- | --- |
| **Nøgle** | Et kort navn uden mellemrum, fx `plc1`. Bruges i tag-kilder (`plc1:coil:0`) |
| **Navn** | Visningsnavn |
| **Adresse** | PLC'ens adresse, fx `http://10.1.1.30` |
| **Bruger** og **Adgangskode** | PLC'ens API-bruger. Adgangskoden gemmes kun på serveren og vises **aldrig** igen — du kan kun sætte en ny |

Statusen (*ok*, *ikke tilgængelig*) vises ud for hver PLC. SCADA'en bruger PLC'ens **REST-API** og **SSE** (en push-strøm med ændringer), så værdier opdateres hurtigt uden at belaste PLC'en.

## Tags

Et **tag** er en navngivet værdi. Siden **Tags** viser dem alle. **Nyt tag** opretter et; **Redigér** ændrer det; **Slet** fjerner det — men et tag, der bruges af en binding, et symbol, et ugeprogram eller en alarm, kan ikke slettes, før det er frigjort, og systemet siger hvor det bruges.

### Kilde

Feltet **Kilde** peger på værdien i PLC'en: `plc1:<type>:<adresse>`.

| Type | Betydning | Eksempel |
| --- | --- | --- |
| `coil` | Udgang (til/fra, kan skrives) | `plc1:coil:0` |
| `di` | Indgang (til/fra, kun læsning) | `plc1:di:7` |
| `hr` | Holdingregister (tal, kan skrives) | `plc1:hr:10` |
| `ir` | Inputregister (tal, kun læsning) | `plc1:ir:3` |
| `logic` | Variabel i PLC'ens program (ST) | vælges med **Hent ST-variabler** |
| `rtu` | Eksternt Modbus-udstyr på PLC'ens RS485 | `plc1:rtu:<slave>:<type>:<adresse>` |
| `mbx` | Expansion board med kanaler A–H | `plc1:mbx:<board>:<kanal>:<slave>:<type>:<adresse>` |

Et tal kan have en **datatype** til sidst (fx `:float`) hvis det fylder mere end ét register. Knappen **Foreslå tags fra PLC** henter forslag fra PLC'en, og du vælger, hvilke der skal oprettes med **Importér valgte**.

> Eksternt udstyr (rtu/mbx) læses via PLC'en. Læsning og skrivning kan tage et øjeblik længere end PLC'ens egne registre.

### Felter

| Felt | Hvad det gør |
| --- | --- |
| **Navn** | Tagets navn, fx `Pumpe1_Drift`. Bogstaver, tal og `_`; må ikke begynde med et tal; højst 64 tegn. Er et element i en tegning navngivet som et tag, bindes det automatisk |
| **Kilde** | Se ovenfor |
| **Enhed** | Vises efter værdien (°C, %, bar …) |
| **Skala** og **Offset** | Værdien omregnes `råværdi × skala + offset`. Fx et register med 215 for 21,5 °C → skala 0,1 |
| **Decimaler** | Antal decimaler der vises (tom = automatisk) |
| **Min** og **Max** (teknisk enhed) | Det tilladte område. Setpunkter uden for området afvises af serveren |
| **Betjening** | Sæt hak for at tagget må **skrives** fra Overview. Kun coil og hr kan skrives |
| **Beskrivelse** | Fri tekst |

### Alarmer på et tag

Under **Alarmer** sætter du grænser: **LL**, **L**, **H**, **HH** for tal; **Til/fra-alarm** for til/fra-tags. Hver alarm har prioritet, **Dødbånd** og **Forsinkelse (s)**. Se *Drift › Alarmer*.

### Historik (trends)

Hak i **Historik (trends)** gemmer tagets værdi over tid. **Højst én værdi pr. (s)** begrænser, hvor ofte der gemmes (en ændring gemmes altid, plus en periodisk "stadig i live"). Se *Drift › Trends*.

### Energi

Hak i **Energi (til energirapporten)** og vælg **Tæller** eller **Effekt**. **Omregning til kWh** er faktoren, der ganges på. Se *Drift › Energi*.

## Eksempel: opret tags til en pumpe

| Navn | Kilde | Betjening | Bemærkning |
| --- | --- | --- | --- |
| `Pumpe1_Start` | `plc1:coil:0` | ja | Kommando start/stop |
| `Pumpe1_Drift` | `plc1:di:0` | nej | Tilbagemelding: kører |
| `Pumpe1_Fejl` | `plc1:di:1` | nej | Fejl — kan have en til/fra-alarm |
| `Tank_Temp` | `plc1:hr:10` | nej | Skala 0,1, enhed °C, alarm H = 70 |
