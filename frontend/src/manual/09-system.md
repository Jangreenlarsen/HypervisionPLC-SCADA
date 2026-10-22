# System

Under **System** ligger Log, Brugere, Backup, Opdatering og Konfiguration. **Log** kræver rollen tekniker; de øvrige kræver **admin**.

## Log

![Log: tidspunkt, bruger, handling og resultat — med filter øverst](/manual/log.png)

**Log** er systemets revisionsspor: **alle skrivninger til PLC'erne og alle ændringer af konfigurationen** — også afviste forsøg. Hver linje viser tidspunkt, bruger, handling, hvad den gjaldt og om det lykkedes. Brug filtrene (*Alt*, *Skrivninger*, *Til/fra*, *Pulser* og flere) til at indsnævre, og **Opdatér** for at hente nyt. Loggen kan ikke redigeres.

## Brugere

![Brugere: roller, tegningsadgang, aktivér/deaktivér og oprettelse af en ny bruger](/manual/brugere.png)

**Brugere** (admin) styrer, hvem der må hvad.

- **Ny bruger**: **Brugernavn**, **Rolle** og en **Midlertidig adgangskode** (mindst 10 tegn). Brugeren skal vælge sin egen adgangskode ved første login.
- **Ny adgangskode** nulstiller en brugers adgangskode (en ny midlertidig).
- **Deaktivér/aktivér** spærrer eller åbner kontoen uden at slette den.
- **Slet** fjerner brugeren.
- **Tegningsadgang**: for viewer, operatør og driftpanel kan du vælge, hvilke **tegninger** brugeren ser. Så ser brugeren kun de valgte tegninger på Overview, kun de tags der vises i dem (i Trends kun de trends, der er sat op i tegningerne), og kan kun betjene klik-handlinger i dem. Vælges ingen tegninger, ser brugeren ikke noget (systemet advarer). Tekniker og admin ser altid alle tegninger.

> Systemet tillader **ikke**, at den sidste aktive administrator slettes, nedgraderes eller deaktiveres — så ingen kan låse sig ude. Reglerne håndhæves af serveren.

## Backup

![Backup: hent og gendan opsætningen, trend-historik og backup på serveren](/manual/backup.png)

**Backup** (admin) beskytter din opsætning.

- **Hent backup** henter en fil med PLC-forbindelser, tags, alle tegninger (med alle versioner), bindinger, symbolopsætninger og ugeprogrammer. Den indeholder **ikke** PLC-adgangskoder, brugere eller koder til nøglelås.
- **Gendan backup**: vælg en backupfil. Systemet viser først, hvad den indeholder (hvem, hvornår, antal tags/tegninger …). Gendannelse **erstatter** den nuværende opsætning efter en bekræftelse; brugere bevares. Der gemmes automatisk en backup af den nuværende tilstand først. PLC'er uden adgangskode skal have den sat igen under **PLC'er**.
- **Automatiske backup** tages på serveren hvert døgn, og de seneste 7 gemmes (de kan hentes fra listen). Der tages også en backup **før en gendannelse** og **før en opdatering**.
- **Trend-historik**: **hent historik** giver et øjebliksbillede af alle gemte kurver, og **flet historik** indlæser en historikfil og sætter den ind (eksisterende værdier bevares).

## Opdatering

![Opdatering: installeret version og upload af en ny pakke](/manual/opdatering.png)

**Opdatering** (admin) installerer en ny version af SCADA'en direkte fra websiden — uden SSH.

1. Byg en **opdateringspakke** på udviklingsmaskinen med `sh deploy/make-package.sh`.
2. **Upload** pakken. Serveren kontrollerer den (kun sikre filer, gyldigt versionsnummer, de nødvendige filer) og viser **version**, størrelse og **kontrolsum**.
3. Tryk **Installér og genstart** og bekræft. Der tages en **backup**, programmet installeres, og serveren **genstarter**. Siden følger forløbet gennem genstarten.
4. Svarer den nye version ikke, **rulles der automatisk tilbage** til den forrige, og du får besked.

| Pakken er … | Så … |
| --- | --- |
| **Nyere** | kan installeres |
| **Samme version** | kan geninstalleres, hvis du sætter hak |
| **Ældre** | afvises — databasen kan være opgraderet |

**Kassér pakken** fjerner en klargjort pakke. Under en opdatering kan intet andet ændres. Loggen fra den seneste opdatering ligger nederst på siden. Kontrolsummen beskytter mod beskadigelse, men en administrator kan via en opdatering i praksis køre kode på serveren — kun betroede personer bør være admin.

> Første gang skal serveren have installationen kørt som administrator på serveren (`sh deploy/install.sh`); derefter kan alle nye versioner komme via siden.

## Konfiguration

**Konfiguration** (admin) viser, hvor data ligger, hvor meget plads de fylder, og hvor meget der skrives til disken.

- **Lagring**: datamappens placering, størrelsen på databaserne og mapperne, og ledig plads på disken.
- **Trend-historik og skrivning**: antal gemte værdier, hvor længe de opbevares, og hvor mange rækker og skrivninger der er sket siden tjenesten startede (med et overslag pr. døgn efter 10 minutters drift). Det er nyttigt, hvis datamappen ligger på et SD-kort.
- **Netværk**: værtsnavn, netkort med link, MAC og IPv4-adresser, gateway og DNS.

Under trend-historikken kan du ændre tre **indstillinger**; de gemmes og gælder **straks**, uden genstart:

| Indstilling | Betydning | Grænser |
| --- | --- | --- |
| **Opbevaring af historik** | Hvor mange dage trend-værdier gemmes; ældre slettes hver time | 1–365 dage |
| **Skriveinterval** | Hvor ofte nye værdier skrives samlet til disken. Længere interval = færre skrivninger (skåner SD-kortet), men ved strømsvigt kan op til så mange sekunder gå tabt | 1–300 s |
| **Opbevaring af energi** | Hvor længe energi-tags gemmes (til måneds- og årsrapporter); må ikke være kortere end historikken | 30–3650 dage |

Forkerte værdier afvises med en besked. Ændringen skrives i auditloggen.

#### Flyt trend-databasen til en anden disk

For at skåne SD-kortet kan historikken ligge på en **USB-SSD**:

1. Monter disken (fx på `/mnt/ssd`) og opret en mappe til SCADA'en **én gang på maskinen**: `sudo install -d -o scada -g scada -m 0750 /mnt/ssd/scada`.
2. Skriv mappen i feltet **Flyt til mappe** og tryk **Flyt databasen**. Kun mapper under `/mnt` eller `/media` på en **anden disk** end den nuværende kan vælges.
3. Historikken kopieres og **kontrolleres** (samme antal værdier), og først derefter tages den nye database i brug — mens SCADA'en kører. Trends står stille et øjeblik. Fejler noget, er den gamle database uændret.
4. Den gamle fil bliver liggende som `trends.db.moved`, til du selv sletter den.

**Tilbage til datamappen** flytter den den anden vej. Mangler disken ved en genstart, starter SCADA'en alligevel — med en tom database i datamappen og en advarsel på siden; historikken på disken er urørt og kommer tilbage, når disken er monteret og du flytter databasen dertil igen.

### Netværksopsætning

Nederst på siden kan du sætte maskinens netværk. Vælg **netkort** og **tilstand**:

| Tilstand | Betydning |
| --- | --- |
| **DHCP** | Adressen kommer fra routeren (kan ændre sig) |
| **Fast IP** | Du angiver **IP-adresse**, **subnet** (præfiks, fx 24 = 255.255.255.0), evt. **gateway**, **DNS** og **værtsnavn** |
| **DHCP + fast IP som sekundær** | Maskinen får en adresse fra routeren **og** altid den faste adresse ved siden af — så kan siden altid nås på den faste adresse |
| **DHCP, fast IP først efter N fejl** | DHCP forsøges hele tiden. Svarer routeren ikke i **N kontroller** (à 30 sekunder, standard 5), tager maskinen den faste **reserve-IP** i brug, og slipper den igen, så snart DHCP svarer. Reserve-IP'en er midlertidig: efter en genstart starter maskinen forfra med ren DHCP |

I tilstandene med DHCP viser siden **DHCP-vagtens** status (*DHCP svarer*, *ingen DHCP-svar — 2 af 5 kontroller*, *kører på reserve-IP*). Er kablet ude, tælles det ikke som en DHCP-fejl.

Alle felter kontrolleres (gyldig adresse, gateway i samme subnet, højst 3 DNS-servere …), og en forkert værdi afvises med en besked, før noget ændres.

**Sådan undgår du at låse dig ude:** Tryk **Anvend**, og bekræft i dialogen. Opsætningen sættes i kraft med det samme, og du har derefter **90 sekunder** til at åbne siden på den **nye adresse** og trykke **Bekræft**. Gør du ikke det — eller trykker du **Fortryd nu** — gendannes den gamle opsætning automatisk. Hele forløbet står i auditloggen.

> Kræver NetworkManager (standard på Raspberry Pi OS Bookworm) og at `sh deploy/install.sh` er kørt som administrator på serveren (en OTA-opdatering gør det automatisk). Mangler det, viser siden en besked, der siger **hvilket** af de to der mangler, i stedet for formularen.

Flytning af hele datamappen (databasen med tags, tegninger og brugere) understøttes ikke; det er trend-databasen, der fylder og skriver mest.

## Bruger

Under **Bruger** i topmenuen ser du dit navn og din rolle, kan **Skifte adgangskode**, åbne **Manual** og **Logge ud**. Versionen af programmet står nederst i menuen.
