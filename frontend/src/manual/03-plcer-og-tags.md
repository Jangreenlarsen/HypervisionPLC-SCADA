# PLC'er og tags

Du skal bruge en **PLC** og nogle **tags**, før en tegning kan vise noget. Begge dele opsættes af en tekniker eller admin under **Opsætning**.

## PLC'er

![Siden PLC'er med de tilsluttede PLC'er og deres status](/manual/plcer.png)

Siden **PLC'er** lister de HypervisionPLC-enheder, SCADA'en henter data fra. Tryk **Tilføj PLC** og udfyld:

| Felt | Betydning |
| --- | --- |
| **Nøgle** | Et kort navn uden mellemrum, fx `plc1`. Bruges i tag-kilder (`plc1:coil:0`) |
| **Navn** | Visningsnavn |
| **Adresse** | PLC'ens adresse, fx `http://10.1.1.30` |
| **Bruger** og **Adgangskode** | PLC'ens API-bruger. Adgangskoden gemmes kun på serveren og vises **aldrig** igen — du kan kun sætte en ny |

Statusen (*ok*, *ikke tilgængelig*) vises ud for hver PLC. SCADA'en bruger PLC'ens **REST-API** og **SSE** (en push-strøm med ændringer), så værdier opdateres hurtigt uden at belaste PLC'en.

**Eksterne registre** (RS485-slaver og expansion boards) kommer også via SSE, når PLC'ens firmware understøtter det (FEAT-447): en ny værdi i PLC'ens Modbus-cache vises straks. SCADA'en spørger desuden PLC'en hvert 2. sekund, så PLC'en også læser de registre, ST-programmerne ikke selv læser. Under **PLC'er** står der *eksterne registre via SSE: RS485 N, expansion boards M* — antallet af modtagne ændringer fra hver slags.

## Tags

![Siden Tags: alle tags med kilde, værdi og knapper til at redigere](/manual/tags.png)

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

![Redigér tag: kilde, skala, betjening, historik, energi og alarmer](/manual/tag-redigeer.png)

| Felt | Hvad det gør |
| --- | --- |
| **Navn** | Tagets navn, fx `Pumpe1_Drift`. Bogstaver, tal og `_`; må ikke begynde med et tal; højst 64 tegn. Er et element i en tegning navngivet som et tag, bindes det automatisk |
| **Kilde** | Se ovenfor |
| **Enhed** | Vises efter værdien (°C, %, bar …) |
| **Skala** og **Offset** | Værdien omregnes `råværdi × skala + offset`. Fx et register med 215 for 21,5 °C → skala 0,1 |
| **Decimaler** | Antal decimaler der vises (tom = automatisk) |
| **Min** og **Max** (teknisk enhed) | Det tilladte område. Setpunkter uden for området afvises af serveren |
| **Skrivbar fra Overview** (under *Betjening*) | Sæt hak for at tagget må **skrives** fra Overview. Coil, hr og ST-variabler (`logic`/`global`) kan skrives — ST-variabler kræver PLC-firmware v7.9.68.141 eller nyere. Er variablen i PLC'en **bundet som input** (Input/Begge) til et register, skriver SCADA automatisk det register (HR eller coil), variablen læser fra — kun en binding til et digitalt input (DI) kan ikke skrives. En variabel, som programmet selv tildeler hver cyklus, kan ikke holdes udefra. ir og di er indgange og kan kun læses |
| **Kræv bekræftelse ved skrivning** | Operatøren skal bekræfte i en dialog, før der skrives |
| **Beskrivelse** | Fri tekst |

### Alarmer på et tag

Under **Alarmer** bestemmer du, hvornår tagget giver en alarm. Et tag har **enten grænser** (tal) **eller en til/fra-alarm** (til/fra-værdier) — ikke begge.

| Felt | Betydning |
|---|---|
| **HH (høj-høj)** | Alarm når værdien er **≥ HH**. Prioritet **høj** |
| **H (høj)** | Alarm når værdien er **≥ H**. Prioritet **medium** |
| **L (lav)** | Alarm når værdien er **≤ L**. Prioritet **medium** |
| **LL (lav-lav)** | Alarm når værdien er **≤ LL**. Prioritet **høj** |
| **Dødbånd** | Hvor langt værdien skal tilbage, før en grænsealarm **ophører** — så alarmen ikke svinger til og fra, når værdien ligger og vipper ved grænsen |
| **Forsinkelse (s)** | Hvor længe betingelsen skal holde, før alarmen **udløses** (0 = med det samme). Korte udsving giver så ingen alarm |
| **Til/fra-alarm** | Kun for til/fra-tags: alarm **når sand** (Til) eller **når falsk** (Fra). Prioritet **høj** |

Grænserne er i tagets **tekniske enhed** (efter skalering), og tomt felt betyder "ingen grænse". De skal stige: LL ≤ L ≤ H ≤ HH. Du behøver ikke udfylde alle — fx kun **H** og **HH**.

**Sådan opfører en grænsealarm sig** (eksempel: H = 90, HH = 100, dødbånd 2, forsinkelse 5 s):

- Værdien når **90** og bliver der i mindst 5 s → alarm **H** (medium).
- Den stiger til **100** → alarmen skifter til **HH** (høj) og bliver **ukvitteret igen**, også hvis H var kvitteret.
- Den falder til 99 → stadig **HH** (den skal under 100 − 2 = **98**, før den går tilbage til H).
- Den falder til 89 → stadig **H**; først under **88** ophører alarmen.
- Én alarm pr. retning: høj (H/HH) og lav (L/LL) er hver sin alarm.

Prioriteten følger niveauet og kan ikke vælges. Mister PLC'en forbindelsen, bevares tagets alarmer som de er (en kommunikationsfejl rydder ikke en alarm — den giver sin egen kommunikationsalarm). Alarmer vises og kvitteres under *Drift › Alarmer*; i symbolguiden kan alarmen også sættes op (trin 6) og styre en animation (fx blinke ved en ukvitteret alarm), se *Symboler og guiden › Alarmer i guiden*.

### Historik (trends)

Hak i **Historik (trends)** gemmer tagets værdi over tid. **Højst én værdi pr. (s)** begrænser, hvor ofte der gemmes (en ændring gemmes altid, plus en periodisk "stadig i live"). Se *Drift › Trends*.

### Energi

Hak i **Energi (til energirapporten)** og vælg **Tæller** eller **Effekt**. **Omregning til kWh** er faktoren, der ganges på. Se *Drift › Energi*.

## Eksempel: opret tags til en pumpe

| Navn | Kilde | Betjening | Bemærkning |
| --- | --- | --- | --- |
| `Pumpe1_Start` | `plc1:coil:0` | ja (skrivbar) | Kommando start/stop |
| `Pumpe1_Drift` | `plc1:di:0` | nej | Tilbagemelding: kører |
| `Pumpe1_Fejl` | `plc1:di:1` | nej | Fejl — kan have en til/fra-alarm |
| `Tank_Temp` | `plc1:hr:10` | nej | Skala 0,1, enhed °C, alarm H = 70 |
