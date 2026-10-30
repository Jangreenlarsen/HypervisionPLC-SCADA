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

![System › Konfiguration: lagring, trend-historik, netværk og genstart](/manual/konfiguration.png)

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

![Netværk: netkort, fast IP eller DHCP, gateway, DNS og værtsnavn](/manual/netvaerk.png)

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

> **Understøttede netværkssystemer:** *NetworkManager* (Raspberry Pi OS) og *ifupdown* (`/etc/network/interfaces` — Debian/Ubuntu-servere og VM'er, fx på en ESXi-server). Installationen (`sh deploy/install.sh`, som en OTA-opdatering også kører) finder selv ud af hvilket, og siden viser det. Mangler begge, eller er installationen ikke kørt, viser siden en besked, der siger **hvad** der mangler, i stedet for formularen.
>
> **ifupdown:** ændringen prøves uden at røre `/etc/network/interfaces`, og filen skrives først, når du har bekræftet (der laves en sikkerhedskopi `interfaces.hypervision-bak-…`; de 3 nyeste beholdes). Kun netkortets egen `iface`-blok i hovedfilen ændres — står den i `interfaces.d`, afvises ændringen. **DHCP** kræver DHCP-klienten **dhcpcd** (`apt install dhcpcd-base`): den prøver uden ende og giver adresserne en levetid, som DHCP-vagten bruger. Mangler den, er kun *Fast IP* valgbar. Egen DNS i DHCP-tilstandene kan blive overskrevet af DHCP-klienten ved næste fornyelse — brug *Fast IP*, hvis DNS skal ligge fast. DNS skrives i `/etc/resolv.conf`, hvis den er en almindelig fil (er den et symlink, styrer systemet den selv, og den røres ikke).

Flytning af hele datamappen (databasen med tags, tegninger og brugere) understøttes ikke; det er trend-databasen, der fylder og skriver mest.

### Genstart

Nederst på **System › Konfiguration** er sektionen **Genstart** (kun admin):

- **Genstart SCADA-tjenesten**: kun programmet genstartes (fx efter en ændring i opsætningen). Siden er væk i et øjeblik; maskinen og PLC'erne røres ikke.
- **Genstart maskinen**: hele maskinen starter forfra — fx efter et skift til **fast IP-adresse** eller et systemopdatering. Siden er utilgængelig i ca. 1–2 minutter. Har du ændret IP-adressen, skal du åbne den **nye** adresse bagefter.

Du bliver bedt om at bekræfte. Bagefter venter siden på serveren og genindlæser sig selv, når den svarer igen. Tags, tegninger og brugere ligger i databasen og bevares. Bestillingen står i auditloggen.

Genstart fra web kræver, at maskinen er opdateret med en version, der har den (installationen sætter en lille hjælper op, ligesom for netværk). Står der *ikke installeret*, så opdatér under **System › Opdatering** — eller genstart fra kommandolinjen med `sudo systemctl restart hypervisionplc-scada` / `sudo reboot`.

### Fuld disk: `scada-maint`

Er disken ved at blive fuld, kan du rydde op **på maskinen** — også selv om websiden ikke kan åbnes. Kør som root (`su -c '…'` eller `sudo`):

| Kommando | Hvad den gør |
| --- | --- |
| `scada-maint status` | Viser ledig plads og hvad der fylder (databaser, backups, logfiler, systemjournal) |
| `scada-maint logs` | Tømmer SCADA'ens logfiler og begrænser systemjournalen (`--journal-size 100M`) |
| `scada-maint backups --keep 2 [--moved]` | Sletter gamle backups (beholder de 2 nyeste af hver slags) og evt. `trends.db.moved` |
| `scada-maint trends --keep-days 14 [--shrink]` | Sletter trend-værdier ældre end 14 dage (energi-tags beholdes længere). `--shrink` gør filen mindre (kræver plads) |
| `scada-maint history --audit-days 90 --alarm-days 90` | Trimmer auditloggen og alarmhistorikken |
| `scada-maint trends-reset [--archive MAPPE]` | Nødløsning: sletter **hele** trend-historikken (evt. først en komprimeret kopi) |
| `scada-maint emergency` | Går trin for trin gennem ovenstående, fra det mindst til det mest indgribende, og **stopper, så snart der er plads nok** |

**Alle kommandoer er tørkørsel** (viser hvad der ville ske og hvor meget plads det giver), indtil du tilføjer **`--yes`**. Tags, brugere, tegninger, bindinger og opsætning slettes **aldrig** — kun logfiler, gamle backups og historik. Hvert skridt skrives i systemloggen.

> Er disken *helt* fuld, kan databasen ikke skrive selv en sletning. Start da med `scada-maint logs --yes` og `scada-maint backups --keep 1 --yes` (de frigør plads uden at skrive i databasen), eller gå direkte til `trends-reset`.

## Bruger

Under **Bruger** i topmenuen ser du dit navn og din rolle, kan **Skifte adgangskode**, åbne **Manual** og **Logge ud**. Versionen af programmet står nederst i menuen.
