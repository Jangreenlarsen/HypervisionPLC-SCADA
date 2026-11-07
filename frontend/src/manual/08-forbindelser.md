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

Et rør sættes op som et symbol: vælg røret, og tryk **Opsæt symbol (6 trin) …** under *Valgt element*. Har røret intet navn, foreslås et (fx *Rør 1*), som du kan rette, før guiden åbnes. Du kan også skrive navnet i feltet **Navn** først. I trin 4 tilføjer du fx **Løbelys** (strømning langs røret — retningen er rørets tegneretning, fra start til slut, og kan vendes) eller **Farve**. Løbelyset følger hele røret gennem knæk og bøjninger.

Et **T-stykke** er et biblioteks-symbol med tre ben (*tilløb 1*, *tilløb 2* og *midte*): sæt det op med **Opsæt symbol**, og giv hvert ben sit eget løbelys. Samme opsætning på flere rør: **Kopiér opsætning** og **Indsæt opsætning**.

## Signalveje: løbelys på en hel rørvej på én gang

En **signalvej** sætter løbelys på *alle* rør mellem to symboler, fx fra kedlen til radiatorerne, styret af ventilerne og pumperne undervejs. Du skal ikke sætte hvert rør, hver bøjning og hvert T-stykke op for sig.

Åbn sektionen **Signalveje** i panelet til højre (rollen tekniker), og tryk **Ny signalvej …**. Tegningen gemmes og udgives først, hvis den har ændringer.

1. **Start og slut:** tryk **Vælg på tegningen**, klik på startsymbolet og derefter på slutsymbolet — så findes vejen af sig selv. Klikker du på et rør, en tekst eller en visning, står der, hvorfor det ikke kan bruges; **Esc** eller **Afbryd valg** stopper. Du kan også vælge i listerne (eller vælge symbolet og trykke **← valgt**) og trykke **Find vej**.
2. **Vejen:** vejen markeres med **orange** i tegningen. Er der flere veje (fx en omløbsledning), kan du vælge mellem op til tre. Vejen findes ud fra, hvordan delene hænger sammen:
   - rør, der sidder fast i symbolerne;
   - symboler, hvis tilslutningspunkter rører hinanden;
   - et rør, der ender midt på et andet (en afgrening uden T-stykke).

   Vejen går aldrig gennem statusfelter, knapper eller løse tekster.
3. **Hvornår går der flow?** For hver ventil, 3-vejsventil, pumpe og kontakt på vejen vælger du et tag og hvornår:
   - et til/fra-tag: *når tagget er til* eller *fra*;
   - et tal-tag: en sammenligning som ≥ 50.

   Symbolets egne tags (fra dets opsætning) står øverst og foreslås. Vælg *ingen betingelse*, hvis symbolet ikke skal tælle med. Alle betingelser skal være opfyldt (OG). Bøjninger, T-stykker og kontraventiler spørges der ikke om.

   **Forklar med egne ord:** er hjælperen slået til (*System › Hjælper (LLM)*), kan du i stedet skrive, hvornår der går flow, fx *"når pumpe 5 kører og AVTB står åben"*, og trykke **Udfyld med hjælperen**.
   - Hjælperen får kun symbolerne på vejen og en kort liste af tags (navn, type og beskrivelse) og udfylder svarene som forslag, mærket **forslag**.
   - Hvert forslag kontrolleres, før det vises: tagget skal findes, og et tal-tag skal have en sammenligning.
   - Forslag, der ikke holder, udfyldes ikke, og de symboler står under *Ikke udfyldt af hjælperen*.
   - Det tager typisk 1–3 minutter; **Stop** afbryder.
   - Tjek forslagene, før du gemmer. Intet gemmes, før du trykker **Gem signalvej**.
4. **Navn og udseende:** giv signalvejen et navn, vælg lysfarve og fart, og tryk **Gem signalvej**.

Når du gemmer, lægges betingelsen som en logikblok (*Signalvej: <navn>*) på vejens første rør, og hvert rør på vejen får et løbelys i vejens retning. Er et rør tegnet "baglæns", vendes lyset automatisk. Rørenes øvrige opsætning, fx en farve-animation, bevares. Har et rør allerede løbelys, spørger Tegn, om det skal erstattes. Et rør kan kun høre til én signalvej ad gangen.

Under **Signalveje** står de gemte signalveje med **Ret** og **Slet**. *Slet* fjerner løbelyset og betingelsen igen og intet andet. Mangler dele af en vej, fordi rør er slettet eller tegnet om, står der en advarsel. Tryk **Ret** og **Find vej** igen.

> Finder Tegn ingen vej, så tjek, at rørene sidder fast (grønne ender, når røret er valgt), og at rørene rører hinanden, hvor de mødes.

## Tilslutningspunkter (siden Symboler)

På siden **Symboler** (rollen tekniker, under **Opsætning**), fanen **Tilslutningspunkter**, kan du rette tilslutningspunkterne for et symbol i biblioteket — også egne symboler:

- Vælg symbolet i listen. Symboler med rettede punkter er mærket **rettet**.
- **Klik** for at tilføje et punkt — det fanger til rørender og kantmidter. **Træk** et punkt for at flytte det. **Højreklik** eller **Delete** fjerner det valgte.
- **Gem punkter** gemmer. **Brug de automatiske** går tilbage til de automatisk fundne.

**Genvej fra Tegn:** vælg et bibliotekssymbol og tryk **Ret tilslutningspunkter …** under *Valgt element* (eller linket øverst i *Symboler*). Symbol-editoren åbner på symbolet, og **← Tilbage til "<tegning>"** fører dig tilbage. Har tegningen ændringer, der ikke er gemt, spørger Tegn først — gem med *Gem kladde*, før du skifter.

> Ændringen gælder **symboler, du indsætter fremover**. Symboler, der allerede står i en tegning, beholder deres punkter — så eksisterende rør flytter sig ikke.
