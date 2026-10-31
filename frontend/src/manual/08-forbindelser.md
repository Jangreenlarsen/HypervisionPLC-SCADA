# Forbindelser (rør og ledninger)

Værktøjet **Forbindelse** (tast **O**) i *Tegn* tegner forbindelser — rør i et procesanlæg eller ledninger i en el-tegning — der altid går **vandret eller lodret** og **sidder fast** i symbolerne. Nedenfor kaldes de *rør*, men alt gælder lige så vel for ledninger.

## Tegn en forbindelse

1. Vælg **Forbindelse** (O) i værktøjslinjen. Symbolernes **tilslutningspunkter** vises som grønne prikker.
2. Klik på en grøn prik (eller et frit sted) for at starte, og klik for hvert knæk.
3. Slut på en grøn prik — så slutter røret af sig selv. Ellers: **dobbeltklik** eller **Enter**.

**Backspace** fjerner det sidste knæk, og **Esc** fortryder røret (tryk Esc igen for at gå tilbage til *Vælg*). Trykker du på selve et symbol (ikke en grøn prik), mens værktøjet er valgt, skifter Tegn til **Vælg**, så du kan flytte symbolet. Nye rør lægges bag de symboler, de forbinder.

## Tilslutningspunkter og retning

Et rør, der starter eller slutter på en grøn prik, **sidder fast**: flytter, drejer, spejler eller ændrer du størrelse på symbolet, følger røret med — og **Ctrl+Z** fortryder begge dele på én gang.

Hvert punkt har en **retning** ud af symbolet. Røret går altid et lille stykke **lige ud** af punktet, før det knækker, så det aldrig går ind gennem symbolet — også når symbolet er drejet. Mellem to sidepunkter laves et pænt Z-formet rør.

Punkterne findes automatisk ud fra symbolets **streger** (rørender på kanten; tekster som *A*, *B* og *M* tæller ikke med). Passer de ikke til et symbol, kan de rettes på siden **Symboler** (se *Tilslutningspunkter (siden Symboler)* nedenfor).

## Vælg et rør: håndtag

Vælg røret med **Vælg** — så får det håndtag:

- **Enderne**: **grønt** = sidder fast, **orange** = fri.
- **Midt på hvert lige stykke**: et lille **blåt** håndtag.

## Flyt dele af et rør

Træk et **blåt håndtag** på tværs for at flytte det stykke; nabostykkerne strækkes med, og rørets ender bliver siddende. Flyttes det første eller sidste stykke, indsættes et knæk, så røret stadig går lige ud af punktet.

- Trækker du et stykke **tæt på linje** med et andet stykke af røret (eller en af enderne), fanges det derhen, så hakket forsvinder, og stykkerne bliver ét.
- Flytter du bagefter et symbol, **bevares dine ændringer** — kun stykket nærmest symbolet lægges om.
- Er røret blevet rodet, så tryk **Ret forbindelsen ud** i *Egenskaber*: røret lægges om mellem sine to ender med så få knæk som muligt, og tilslutningerne bevares.

## Sæt et rør fast igen

Flytter du hele røret væk fra symbolet, slipper det (enderne bliver **orange**). Træk et ende-håndtag hen på et tilslutningspunkt (grøn prik), så sættes enden fast igen, og det sidste stykke lægges om. Slipper du et andet sted, bliver enden fri. Flytter du et helt rør, så en ende lander på et tilslutningspunkt, sættes den fast af sig selv.

## Saml rør ende mod ende

Trækker du et ende-håndtag hen på **et andet rørs ende** (orange prik), lægges de to rør sammen til ét. Det samme gælder med værktøjet **Forbindelse**: start eller slut på et rørs ende for at forlænge røret. Har begge rør en opsætning (et navn), lægges de ikke sammen — så går ingen opsætning tabt.

## T-stykker

Starter eller slutter du et rør **midt på** et eksisterende rør (en **orange prik** viser stedet) — eller slipper et ende-håndtag dér — deles røret, og bibliotekets **T-stykke** sættes ind, drejet så gennemløbet følger røret og grenen vender mod det nye rør. Alle tre rør sidder fast i T-stykket og følger med, når du flytter det. Det oprindelige rør beholder navn og opsætning på den første halvdel; den anden halvdel er et nyt rør uden opsætning. **Ctrl+Z** fortryder røret og T-stykket samlet.

## Bøjningsradius

Vælg et rør, og skriv en **Bøjningsradius** i *Egenskaber* — så får knækkene bløde bøjninger i stedet for skarpe 90°-hjørner. Nye rør får den senest brugte radius.

## Løbelys og animation

Et rør sættes op som et symbol: vælg røret, giv det et **Navn** under *Valgt element*, og tryk **Opsæt symbol (6 trin)**. I trin 4 tilføjer du fx **Løbelys** (strømning langs røret — retningen er rørets tegneretning, fra start til slut, og kan vendes) eller **Farve**. Løbelyset følger hele røret gennem knæk og bøjninger.

Et **T-stykke** er et biblioteks-symbol med tre ben (*tilløb 1*, *tilløb 2* og *midte*): sæt det op med **Opsæt symbol**, og giv hvert ben sit eget løbelys. Samme opsætning på flere rør: **Kopiér opsætning** og **Indsæt opsætning**.

## Tilslutningspunkter (siden Symboler)

På siden **Symboler** (rollen tekniker, under **Opsætning**) kan du rette tilslutningspunkterne for et symbol i biblioteket:

- Vælg symbolet i listen. Symboler med rettede punkter er mærket **rettet**.
- **Klik** for at tilføje et punkt — det fanger til rørender og kantmidter. **Træk** et punkt for at flytte det. **Højreklik** eller **Delete** fjerner det valgte.
- **Gem punkter** gemmer. **Brug de automatiske** går tilbage til de automatisk fundne.

**Genvej fra Tegn:** vælg et bibliotekssymbol og tryk **Ret tilslutningspunkter …** under *Valgt element* (eller linket øverst i *Symboler*). Symbol-editoren åbner på symbolet, og **← Tilbage til "<tegning>"** fører dig tilbage. Har tegningen ændringer, der ikke er gemt, spørger Tegn først — gem med *Gem kladde*, før du skifter.

> Ændringen gælder **symboler, du indsætter fremover**. Symboler, der allerede står i en tegning, beholder deres punkter — så eksisterende rør flytter sig ikke.
