# Forbindelser (rør og ledninger)

Værktøjet **Forbindelse** (tast **O**) i *Tegn* tegner forbindelser — rør i et procesanlæg eller ledninger i en el-tegning — der altid går **vandret eller lodret** og **sidder fast** i symbolerne. Nedenfor kaldes de *rør*, men alt gælder lige så vel for ledninger.

## Tegn en forbindelse

1. Vælg **Forbindelse** (O) i værktøjslinjen. Symbolernes **tilslutningspunkter** vises som grønne prikker.
2. Klik på en grøn prik (eller et frit sted) for at starte, og klik for hvert knæk.
3. Slut på en grøn prik — så slutter røret af sig selv. Ellers: **dobbeltklik** eller **Enter**.

**Backspace** fjerner det sidste knæk, og **Esc** fortryder røret (tryk Esc igen for at gå tilbage til *Vælg*). Trykker du på selve et symbol (ikke en grøn prik), mens værktøjet er valgt, skifter Tegn til **Vælg**, så du kan flytte symbolet. Nye rør lægges bag de symboler, de forbinder.

## Tilslutningspunkter og retning

Et rør, der starter eller slutter på en grøn prik, **sidder fast**: flytter, drejer, spejler eller ændrer du størrelse på symbolet, følger røret med, og **Ctrl+Z** fortryder begge dele på én gang.

Mens du **trækker** et symbol, vises rørene, som de kommer til at ligge. De gamle rør dæmpes imens, så du kan se, hvor symbolet passer.

**Fang rør lige** (slået til som standard, ved siden af *Fang til objekter*): kommer symbolets tilslutningspunkt tæt på at flugte med rørets næste knæk, vises en **blå stiplet linje**. Slipper du, fanges symbolet, og røret står **snorlige** ud af det, uden hak. Det fanger kun inden for få skærmpunkter; flytter du længere, følger røret med med knæk som før. Hjælpelinjer vinder stadig over dette fang.

Hvert punkt har en **retning** ud af symbolet. Røret går altid et lille stykke **lige ud** af punktet, før det knækker, så det aldrig går ind gennem symbolet — også når symbolet er drejet. Mellem to sidepunkter laves et pænt Z-formet rør.

Punkterne findes automatisk ud fra symbolets **streger** (rørender på kanten; tekster som *A*, *B* og *M* tæller ikke med). Passer de ikke til et symbol, kan de rettes på siden **Symboler** (se *Tilslutningspunkter (siden Symboler)* nedenfor).

## Vælg et rør: håndtag

![Et valgt rør mellem en pumpe og et fyr: grønne ender (sidder fast) og blå håndtag midt på hvert lige stykke](../../public/manual/forbindelse-haandtag.png)

Vælg røret med **Vælg** — så får det håndtag:

- **Enderne**: **grønt** = sidder fast, **orange** = fri.
- **Midt på hvert lige stykke**: et lille **blåt** håndtag.

Er røret svært at ramme, fordi et symbol ligger ovenpå, så **Alt+klik** for at vælge det, der ligger bagved, eller vælg røret i panelet **Objekter**. I *Egenskaber* til højre står rørets **Navn**, **Bøjningsradius** og knappen **Ret forbindelsen ud**.

## Flyt dele af et rør

Træk et **blåt håndtag** på tværs for at flytte det stykke; nabostykkerne strækkes med, og rørets ender bliver siddende. Flyttes det første eller sidste stykke, indsættes et knæk, så røret stadig går lige ud af punktet.

- Trækker du et stykke **tæt på linje** med et andet stykke af røret (eller en af enderne), fanges det derhen, så hakket forsvinder, og stykkerne bliver ét.
- Flytter du bagefter et symbol, **bevares dine ændringer** — kun stykket nærmest symbolet lægges om.
- Er røret blevet rodet, så tryk **Ret forbindelsen ud** i *Egenskaber*: røret lægges om mellem sine to ender med så få knæk som muligt, og tilslutningerne bevares.

## Sæt et rør fast igen

Flytter du hele røret væk fra symbolet, slipper det (enderne bliver **orange**). Træk et ende-håndtag hen på et tilslutningspunkt (grøn prik), så sættes enden fast igen, og det sidste stykke lægges om. Slipper du et andet sted, bliver enden fri. Flytter du et helt rør, så en ende lander på et tilslutningspunkt, sættes den fast af sig selv.

**Røret følger ikke med symbolet?** Så sidder enden ikke fast. Vælg røret og se på enderne: en **orange** ende er fri. Træk den hen på symbolets grønne prik, til den bliver grøn. Et rør, der er tegnet før symbolet blev flyttet eller erstattet (*Erstat med symbol*), kan have mistet sin tilslutning på denne måde.

## Saml rør ende mod ende

Trækker du et ende-håndtag hen på **et andet rørs ende** (orange prik), lægges de to rør sammen til ét. Det samme gælder med værktøjet **Forbindelse**: start eller slut på et rørs ende for at forlænge røret. Har begge rør en opsætning (et navn), lægges de ikke sammen — så går ingen opsætning tabt.

Brug det til at rydde op i en tegning med mange korte rørstykker: ét langt rør er lettere at flytte, og et løbelys løber jævnt hele vejen. Har kun det ene rør en opsætning, beholder det samlede rør den.

## T-stykker

Starter eller slutter du et rør **midt på** et eksisterende rør (en **orange prik** viser stedet) — eller slipper et ende-håndtag dér — deles røret, og bibliotekets **T-stykke** sættes ind, drejet så gennemløbet følger røret og grenen vender mod det nye rør. Alle tre rør sidder fast i T-stykket og følger med, når du flytter det. Det oprindelige rør beholder navn og opsætning på den første halvdel; den anden halvdel er et nyt rør uden opsætning. **Ctrl+Z** fortryder røret og T-stykket samlet.

## Bøjningsradius

Vælg et rør, og skriv en **Bøjningsradius** i *Egenskaber* — så får knækkene bløde bøjninger i stedet for skarpe 90°-hjørner. Nye rør får den senest brugte radius. **0** giver skarpe hjørner igen.

Radius er i tegningens enheder (samme som X/Y). Er et lige stykke kortere end to gange radius, bliver bøjningen mindre, så røret stadig passer. Løbelys og farve følger bøjningerne.

## Løbelys og animation

Et rør sættes op som et symbol: vælg røret, og tryk **Opsæt symbol (6 trin) …** under *Valgt element*. Har røret intet navn, foreslås et (fx *Rør 1*), som du kan rette, før guiden åbnes. Du kan også skrive navnet i feltet **Navn** først. I trin 4 tilføjer du fx **Løbelys** (strømning langs røret — retningen er rørets tegneretning, fra start til slut, og kan vendes) eller **Farve**. Løbelyset følger hele røret gennem knæk og bøjninger.

Et **T-stykke** er et biblioteks-symbol med tre ben (*tilløb 1*, *tilløb 2* og *midte*): sæt det op med **Opsæt symbol**, og giv hvert ben sit eget løbelys. Samme opsætning på flere rør: **Kopiér opsætning** og **Indsæt opsætning**.

## Tilslutningspunkter (siden Symboler)

På siden **Symboler** (rollen tekniker, under **Opsætning**), fanen **Tilslutningspunkter**, kan du rette tilslutningspunkterne for et symbol i biblioteket — også egne symboler:

- Vælg symbolet i listen. Symboler med rettede punkter er mærket **rettet**.
- **Klik** for at tilføje et punkt — det fanger til rørender og kantmidter. **Træk** et punkt for at flytte det. **Højreklik** eller **Delete** fjerner det valgte.
- **Gem punkter** gemmer. **Brug de automatiske** går tilbage til de automatisk fundne.

**Genvej fra Tegn:** vælg et bibliotekssymbol og tryk **Ret tilslutningspunkter …** under *Valgt element* (eller linket øverst i *Symboler*). Symbol-editoren åbner på symbolet, og **← Tilbage til "<tegning>"** fører dig tilbage. Har tegningen ændringer, der ikke er gemt, spørger Tegn først — gem med *Gem kladde*, før du skifter.

> Ændringen gælder **symboler, du indsætter fremover**. Symboler, der allerede står i en tegning, beholder deres punkter — så eksisterende rør flytter sig ikke.

### Ind/ud og veje

![Fanen Ind/ud og veje: 3-vejsmotorventilens punkter A, B og AB med roller, det fælles punkt og vejene](../../public/manual/symbol-ind-ud.png)

Fanen **Ind/ud og veje** (samme side) beskriver, hvordan flowet løber gennem et symbol: punkternes navne, ind/ud og de veje, en ventil kan lave. Den ændrer ikke noget i tegningen, og den gælder alle tegninger med symbolet med det samme.

- **Navn:** giv hvert punkt et navn (A, B, AB, P, T …).
- **Rolle:** *Ind*, *Ud* eller *Begge*. En **pumpe** har *IND* og *UD*; en **kontraventil** også.
- **Fælles:** markér det fælles punkt på en flervejs-ventil (AB på en 3-vejsventil).
- **Del:** delens id i symbolet (fx `port_ab`), så netop den port kan få en animation.
- **Veje:** de forbindelser symbolet kan lave. De laves som standard automatisk — hvert fælles punkt parret med hvert af de andre (*AB → A*, *AB → B*) — men kan skrives selv med **+ Vej**, fx til en 4-vejsventil (*P → A*, *P → B*, *A → T*, *B → T*).
- **Klik** for at tilføje et punkt, **træk** for at flytte det, **højreklik** fjerner det. **Gem** gemmer; **Brug standarden** går tilbage. De indbyggede symboler har standarder (pumpe, kontraventil og 3-vejs ventilerne); **Start fra tilslutningspunkterne** hjælper med andre symboler.
- Ind/ud-definitionerne følger med i backup.
