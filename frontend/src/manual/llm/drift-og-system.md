<!--
Tillæg til hjælperens LLM-manual (vises IKKE i Manual-siden) — se llm/tegn.md og manual_compiler.py.
-->
# Tillæg: Drift, tags og system

## Hvordan vedligeholder jeg serveren fra kommandolinjen (scada-tool, serveren starter ikke, opdatering hænger, glemt adgangskode)?
<!-- kilde: 13-system#m-server-vaerktoejskassen-scada-tool sha:5a6955c8 -->
På serveren (SSH, root) findes **`scada-tool`**: `status` (overblik), `check` (diagnose: hvorfor starter serveren ikke), `logs [--fejl] [-f]`, `start|stop|restart`, `update status|reset|apply FIL.tar|rollback` (`reset` rydder en opdatering, der står fast som "i gang"), `backup list|create|restore FIL.db`, `user reset NAVN` (nulstil en adgangskode) og `config`. Ændringer spørger først og logges.

## Hvordan kvitterer jeg en alarm (acknowledge, bekræft alarm, klokken blinker)?
<!-- kilde: 03-alarmer#m-kvitt-r-en-alarm sha:dd8861a0 -->
Åbn **Alarmer** (klik på alarmklokken) og tryk **Kvittér** ud for alarmen eller **Kvittér alle**. Det kræver rollen operatør. En kvitteret alarm står stadig som aktiv, til årsagen er væk.

## Værdien er grå, svag eller tonet ned — hvorfor (dårlig kvalitet, kommunikationsfejl, gammel værdi)?
<!-- kilde: 02-drift#m3-naar-vaerdien-ikke-er-frisk-datakvalitet sha:f28f806f -->
Værdien er ikke frisk: der er kommunikationsfejl til PLC'en, tagget kan ikke læses (dårlig), eller der er endnu ingen værdi (ukendt). Symbolet tones ned, og betjening afvises, til værdien er god igen. Tjek PLC'en under **System › Status**.

## Hvordan sletter jeg flere tags på én gang (fjern tags, oprydning)?
<!-- kilde: 05-plcer-og-tags#m-tags sha:23ece453 -->
Under **Tags**: afkryds tagsene (Shift-klik vælger et interval, **Vælg alle** vælger alle viste) og tryk **Slet valgte (N)**. Du ser, hvor tagsene bruges, og bekræfter; der tages backup først. Et enkelt tag slettes med **Slet** i rækken.

## Hvordan sætter jeg en alarmgrænse på et tag (høj temperatur, H, HH, L, LL, hysterese, dødbånd)?
<!-- kilde: 05-plcer-og-tags#m3-alarmer-paa-et-tag sha:3da5e9b1 -->
Under **Tags**: tryk **Redigér** ved tagget og udfyld **H**/**HH** (høj) eller **L**/**LL** (lav). **Dødbånd** er alarmens hysterese: hvor langt værdien skal tilbage, før alarmen ophører. **Forsinkelse** er hvor længe grænsen skal være overskredet. Prioriteten følger niveauet (HH/LL høj, H/L medium).

## Hvordan opretter jeg en ny bruger (ny konto, login til en kollega)?
<!-- kilde: 13-system#m-brugere sha:b7af828c -->
Som admin: **System › Brugere**, udfyld **Brugernavn**, vælg **Rolle** og en **midlertidig adgangskode** (mindst 10 tegn), og opret. Brugeren vælger sin egen adgangskode ved første login. Viewer, operatør og driftpanel kan begrænses til udvalgte tegninger.

## Hvordan skifter jeg min egen adgangskode?
<!-- kilde: 13-system#m-bruger sha:72754ae5 -->
Klik **Bruger** i topmenuen og vælg **Skift adgangskode**. Skriv den nuværende og den nye to gange (mindst 10 tegn) og tryk **Gem**.

## Hvordan tager jeg en backup, og hvordan gendanner jeg?
<!-- kilde: 13-system#m-backup sha:309ace81 -->
Som admin: **System › Backup**. **Hent backup** gemmer opsætningen som en fil; **Gendan backup** indlæser en fil (den nuværende tilstand gemmes først). Automatisk backup og eksterne destinationer (SFTP, SMB, NFS …) sættes op samme sted; **Kør backup nu** starter en med det samme.

## Hvordan opdaterer jeg SCADA'en til en ny version?
<!-- kilde: 13-system#m-opdatering sha:68f556d8 -->
Som admin: **System › Opdatering**. **Upload** opdateringspakken (`scada-<version>-b<build>.tar`), tjek version og kontrolsum, og tryk **Installér og genstart**. Serveren tager backup først, genstarter og ruller selv tilbage, hvis den nye version ikke svarer.

## Hvordan genstarter jeg serveren eller tjenesten?
<!-- kilde: 13-system#m3-genstart sha:61355bab -->
Som admin: nederst på **System › Konfiguration**, sektionen **Genstart**: **Genstart SCADA-tjenesten** (kun programmet) eller **Genstart maskinen** (hele maskinen, 1–2 minutter). Fra kommandolinjen: `sudo systemctl restart hypervisionplc-scada` eller `sudo reboot`.

## Disken er fuld — hvad gør jeg?
<!-- kilde: 13-system#m3-fuld-disk-scada-maint sha:5d386e12 -->
Se **System › Status** (ledig disk). Ryd op på maskinen som root med `scada-maint`: `scada-maint status` viser hvad der fylder, `scada-maint emergency` rydder trin for trin, til der er plads nok (logfiler, gamle backups, gammel trend-historik). Trend-databasen kan også flyttes til en anden disk (*System › Konfiguration*).

## Hvordan vælger og installerer jeg en model til hjælperen (LLM)?
<!-- kilde: 13-system#m-hjaelper-llm sha:193192b2 -->
Som admin: **System › Hjælper (LLM)**. Vælg hardwareprofil, og tryk **Hent og installér** ved en variant: *Hurtig*, *Standard* (anbefalet) eller *Stor* (kræver 16 GB RAM). Uden internet installeres en samlet LLM-pakke med **Vælg LLM-pakke …**. På Raspberry Pi 5 findes Hurtig og Standard; de kræver Raspberry Pi OS 13 "Trixie".

## Hvordan ser jeg, hvem der har ændret noget eller skrevet til PLC'en (revisionsspor, audit, hvem gjorde hvad)?
<!-- kilde: 13-system#m-log sha:cdf6c0de -->
Åbn **System › Log** (tekniker og admin). Loggen viser alle skrivninger til PLC'erne og alle ændringer af opsætningen — også afviste forsøg — med tidspunkt, bruger, handling og resultat. Filtrér med *Skrivninger*, *Til/fra*, *Pulser* m.fl. Alarmkvitteringer står under **Alarmer › Historik**.

## Hvordan importerer eller henter jeg mange tags på én gang (hent tags fra PLC'en)?
<!-- kilde: 05-plcer-og-tags#m-tags sha:23ece453 -->
Under **Tags**: tryk **Foreslå tags fra PLC**. SCADA'en henter PLC'ens variabler som forslag; afkryds dem, du vil have, og tryk **Importér valgte**. En hel opsætning med tags flyttes mellem servere med **System › Backup** (hent og gendan).

## Hvordan begrænser jeg en operatør til én eller få tegninger (tegningsadgang, kun se én tegning)?
<!-- kilde: 13-system#m-brugere sha:b7af828c -->
Som admin: **System › Brugere**, vælg **Tegningsadgang** for brugeren (viewer, operatør eller driftpanel) og sæt hak ved de tegninger, brugeren må se. Brugeren ser så kun de tegninger og deres tags og kan kun betjene dér. Tekniker og admin ser altid alle tegninger.
