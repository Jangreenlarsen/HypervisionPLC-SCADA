# Eksempler trin for trin

Hvert eksempel følger samme forløb som resten af manualen. De forudsætter en PLC under **PLC'er** og de nævnte **tags** under **Tags** (se *PLC'er og tags*). Alle navne er eksempler — brug dine egne.

## 1. Vis og betjen en pumpe

![Eksempel 1: en pumpe på Overview — farven viser, om pumpen kører, og et klik åbner betjeningen](/manual/eksempel-pumpe.png)

**Mål:** en pumpe på tegningen, der er grøn, når den kører, og som operatøren kan starte og stoppe.

1. **Tags:** `Pumpe1_Start` (`plc1:coil:0`, *Betjening* sat) og `Pumpe1_Drift` (`plc1:di:0`, tilbagemelding).
2. **Tegn:** vælg *— Ny tegning —*, indsæt symbolet **Pumpe** (kategorien *Proces og visning*), giv det navnet *Pumpe 1*, skriv et navn til tegningen og tryk **Gem og udgiv**.
3. Vælg pumpen og tryk **Opsæt symbol (6 trin)**.
4. **Trin 1:** vælg **Interaktiv betjening**.
5. **Trin 2:** ved *S1* vælges **Kommando** `Pumpe1_Start` og **Tilbagemelding** `Pumpe1_Drift`.
6. **Trin 3:** to positioner, *Stop* og *Start*. Planen for S1: *Stop* = Fra, *Start* = Til.
7. **Trin 4:** tilføj en animation: del *Pumpehus*, type **Farve**, kilde **symbolets position**, farve grå ved *Stop* og grøn ved *Start*. Tilføj evt. **Roterer** på *Løbehjul* kun ved *Start*.
8. **Trin 5:** sæt hak ved **Operatøren skal bekræfte**, hvis ønsket.
9. **Trin 6:** kontrollér, at **Live** viser pumpens aktuelle tilstand og at positionen *fundet* stemmer. Tryk **Gem**.
10. Åbn **Overview**, vælg tegningen og klik pumpen. Vælg *Start* — pumpen skifter farve, når PLC'en har bekræftet.

## 2. Niveau i en tank med tal ved siden af

![Eksempel 2: en tank, hvis fyld følger niveauet, med et statusfelt ved siden af](/manual/eksempel-tank.png)

**Mål:** en tank der fyldes efter niveauet, og et felt der viser procenten.

1. **Tag:** `Tank_Niveau` (`plc1:hr:11`, enhed *%*, *Min* 0, *Max* 100).
2. **Tegn:** indsæt symbolet **Tank** og et **Værdifelt**. Navngiv dem.
3. Opsæt **Tank** med guiden: trin 1 **Kun passiv visning**; trin 4: animation, del *Fyld*, type **Niveau**, kilde *et tag* `Tank_Niveau`, min 0, max 100.
4. Opsæt **Værdifelt**: **Kun passiv visning**; animation på *Værdi*, type **Værdi/Tekst**, kilde `Tank_Niveau`, 1 decimal.

## 3. 3-vejs motorventil (AB → A / AB → B)

**Mål:** vis om flowet går AB → A eller AB → B, styret af ét til/fra-signal.

1. **Tag:** `Ventil_Retning` (`plc1:di:7`). Til = AB → A, Fra = AB → B.
2. **Tegn:** indsæt **3-vejs motorventil** (eller varianten med *AB i midten*). Gem og udgiv.
3. **Opsæt symbol (6 trin)** → trin 4 → **Hurtig opsætning**: vælg `Ventil_Retning` og tryk **Opret animationer**.
4. Resultatet: *Port A* grøn og *Port B* hvid ved **Til**; omvendt ved **Fra**. *Port AB* er altid grøn.
5. Skal operatøren kunne skifte ventilen, så brug i stedet **Interaktiv betjening** i trin 1 med et skrivbart tag (to positioner, *AB → A* og *AB → B*).

## 4. Logikblok: lys i røret, når pumpen kører og ventilen er åben

**Mål:** et rør viser strømning, kun når **både** pumpen kører og ventilen er åben.

1. **Tags:** `Pumpe1_Drift` (`plc1:di:0`) og `Ventil1_Aaben` (`plc1:di:2`).
2. Opsæt røret med guiden (**Kun passiv visning**). I trin 4, **Logik**: tryk **+ Logikblok**, vælg **AND**, første indgang `Pumpe1_Drift`, anden indgang `Ventil1_Aaben`. Giv blokken navnet *Pumpe og ventil*.
3. **Animationer:** tilføj en animation: del *Rør*, type **Løbelys**, kilde **en logikblok** → *L1 – Pumpe og ventil*.
4. Gem. Røret lyser nu kun, når begge betingelser er sande.
5. **Variant:** vil du også have lys, når *nødkørsel* er sat, lav blok **L2 = OR(L1, Nødkørsel)** og brug L2.
6. **Variant:** brug **NOT** på en indgang for "ventil **ikke** lukket", eller en tal-indgang som `Tank_Temp ≥ 60`.

## 5. Setpunkt med beregning

**Mål:** operatøren indtaster en ønsket temperatur, som PLC'en gemmer i et register med én decimal for meget.

1. **Tag:** `Stue_Setpunkt` (`plc1:hr:20`, *Betjening* sat, *Min* 5, *Max* 30). PLC'en gemmer 215 for 21,5 °C.
2. **Tegn:** indsæt **Setpunkt-felt**. Opsæt det med guiden: **trin 1** vælg **Setpunkt**; **trin 2** vælg det register, der skrives: `Stue_Setpunkt`.
3. Vil du i stedet bare vise værdien som tekst: **Bindinger**, vælg elementet, animation **Tekst**, **Beregning** `x / 10`, **Decimaler** 1, enhed °C — så vises 215 som *21,5 °C*.
4. På Overview skriver operatøren fx 22; serveren tjekker mod min/max og afviser 40 med en forklaring.

## 6. Alarm ved høj temperatur — og kurve

**Mål:** alarm, når temperaturen er over 70 °C, og en kurve over de seneste timer.

1. **Tags → Redigér** `Tank_Temp` (`plc1:hr:10`, *Skala* 0,1, *Enhed* °C).
2. Under **Alarmer**: **H (høj)** = 65, **HH (høj-høj)** = 70, **Dødbånd** 2, **Forsinkelse** 5 s.
3. Sæt hak i **Historik (trends)**.
4. **Alarmer** viser alarmen, når grænsen er overskredet, og klokken i toppen skifter farve. Tryk **Kvittér**.
5. **Trends:** vælg `Tank_Temp` og **8 timer** for at se forløbet.

## 7. Ugeprogram: komfort og nedsat

Se eksemplet i *Ugeprogrammer*. Kort: opret **+ Nyt ugeprogram**, vælg tagget, læg perioder ind for hverdage og weekend, sæt **Uden for perioderne**, tilføj en **undtagelse** for ferie, og tryk **Vis forhåndsvisning** før du gemmer.

## 8. Omskifter Hånd / 0 / Auto

**Mål:** en omskifter, hvor operatøren vælger driftsform, som PLC'en gemmer i et register.

1. **Tags:** `Pumpe1_Mode` (`plc1:hr:30`, *Betjening* sat, *Min* 0, *Max* 2) og evt. `Pumpe1_Mode_fb` (`plc1:hr:32`) som tilbagemelding.
2. **Tegn:** indsæt **Omskifter Hånd/0/Auto** (kategorien *Betjening*).
3. **Guiden:** trin 1 **Interaktiv betjening**; trin 2 ét signal med kommando `Pumpe1_Mode` og tilbagemelding `Pumpe1_Mode_fb`; trin 3 skabelon **A** giver værdierne 0, 1, 2 til positionerne *Hånd*, *0*, *Auto* — ret dem, hvis PLC'en bruger andre tal.
4. **Trin 5:** sæt **nøglelås** på *Hånd*, så kun en operatør med koden kan sætte pumpen i håndkørsel.
5. **Trin 4:** animationen **Drej** på *Greb* roterer omskifteren til positionen.

## 9. Eksternt Modbus-udstyr (RS485)

**Mål:** læs en temperaturføler, der sidder på PLC'ens RS485-bus.

1. Under **Tags → Nyt tag**: **Kilde** `plc1:rtu:3:hr:0` (slave 3, holdingregister 0) — eller brug **Foreslå tags fra PLC**.
2. Giv tagget navn, skala og enhed, som et almindeligt tag. Det bruges nu i bindinger, alarmer og trends som alle andre.
3. Læsning af eksternt udstyr sker via PLC'en og kan tage et øjeblik; værdier der ikke kan læses, vises som —.

## 10. Opdatér SCADA'en uden SSH

1. Byg pakken: `sh deploy/make-package.sh`.
2. **System › Opdatering** → vælg filen → kontrollér version og kontrolsum.
3. **Installér og genstart** → bekræft. Siden følger forløbet; svarer den nye version ikke, rulles der automatisk tilbage.

## 11. Sæt op med en logikblok, der bruges i flere symboler

1. Lav blokken (fx *Anlæg klar* = AND af tre tags) i det **første** symbol, som du alligevel sætter op.
2. I de **andre** symboler på samme tegning vælger du animationens kilde **en logikblok** → gruppen **Andre symboler**.
3. Vil du ændre betingelsen, ændrer du den ét sted. Blokken kan ikke fjernes, så længe andre symboler bruger den — systemet siger hvilke.
