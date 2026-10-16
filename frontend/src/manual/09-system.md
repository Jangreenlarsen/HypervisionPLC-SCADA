# System

Under **System** ligger Log, Brugere, Backup og Opdatering. **Log** kræver rollen tekniker; de øvrige kræver **admin**.

## Log

**Log** er systemets revisionsspor: **alle skrivninger til PLC'erne og alle ændringer af konfigurationen** — også afviste forsøg. Hver linje viser tidspunkt, bruger, handling, hvad den gjaldt og om det lykkedes. Brug filtrene (*Alt*, *Skrivninger*, *Til/fra*, *Pulser* og flere) til at indsnævre, og **Opdatér** for at hente nyt. Loggen kan ikke redigeres.

## Brugere

**Brugere** (admin) styrer, hvem der må hvad.

- **Ny bruger**: **Brugernavn**, **Rolle** og en **Midlertidig adgangskode** (mindst 10 tegn). Brugeren skal vælge sin egen adgangskode ved første login.
- **Ny adgangskode** nulstiller en brugers adgangskode (en ny midlertidig).
- **Deaktivér/aktivér** spærrer eller åbner kontoen uden at slette den.
- **Slet** fjerner brugeren.
- **Tegningsadgang**: for viewer, operatør og driftpanel kan du vælge, hvilke **tegninger** brugeren ser. Så ser brugeren kun de valgte tegninger på Overview, kun de tags der vises i dem, og kan kun betjene klik-handlinger i dem. Vælges ingen tegninger, ser brugeren ikke noget (systemet advarer). Tekniker og admin ser altid alle tegninger.

> Systemet tillader **ikke**, at den sidste aktive administrator slettes, nedgraderes eller deaktiveres — så ingen kan låse sig ude. Reglerne håndhæves af serveren.

## Backup

**Backup** (admin) beskytter din opsætning.

- **Hent backup** henter en fil med PLC-forbindelser, tags, alle tegninger (med alle versioner), bindinger, symbolopsætninger og ugeprogrammer. Den indeholder **ikke** PLC-adgangskoder, brugere eller koder til nøglelås.
- **Gendan backup**: vælg en backupfil. Systemet viser først, hvad den indeholder (hvem, hvornår, antal tags/tegninger …). Gendannelse **erstatter** den nuværende opsætning efter en bekræftelse; brugere bevares. Der gemmes automatisk en backup af den nuværende tilstand først. PLC'er uden adgangskode skal have den sat igen under **PLC'er**.
- **Automatiske backup** tages på serveren hvert døgn, og de seneste 7 gemmes (de kan hentes fra listen). Der tages også en backup **før en gendannelse** og **før en opdatering**.
- **Trend-historik**: **hent historik** giver et øjebliksbillede af alle gemte kurver, og **flet historik** indlæser en historikfil og sætter den ind (eksisterende værdier bevares).

## Opdatering

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

## Bruger

Under **Bruger** i topmenuen ser du dit navn og din rolle, kan **Skifte adgangskode**, åbne **Manual** og **Logge ud**. Versionen af programmet står nederst i menuen.
