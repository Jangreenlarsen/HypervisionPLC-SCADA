<!--
Tillæg til hjælperens LLM-manual (vises IKKE i Manual-siden). Hvert afsnit er et spørgsmål, som folk stiller det, og et
kort svar. Kilde-linjen binder svaret til et afsnit i den store manual; ændres det afsnit, fejler testen
(test_manual_compiler.py), indtil tillægget er tjekket og `python -m app.services.manual_compiler --sync` er kørt.
Se backend/app/services/manual_compiler.py.
-->
# Tillæg: Tegn og forbindelser

## Hvordan vælger jeg et symbol, der ligger bag et andet (skjult under, forrest, bagved)?
<!-- kilde: 07-tegn#m-vaelg-flyt-og-mark-r sha:e38a0f77 -->
I Tegn: hold **Alt** nede og klik på stedet. Så vælges det element, der ligger bagved det forreste; Alt+klik igen går et lag længere ned. Træk derefter uden Alt for at flytte det valgte — det forreste bliver liggende. Et klik uden at trække vælger det forreste igen. Du kan også vælge elementet i panelet **Objekter** til højre (forrest øverst).

## Hvordan flytter jeg et symbol forrest eller bagerst (rækkefølge, lag, frem, tilbage)?
<!-- kilde: 07-tegn#m-panelet-til-hoejre sha:45bfca2f -->
Vælg symbolet og brug knaplinjen over det markerede (*ét trin frem/tilbage*, *læg øverst/nederst*), tasterne **Ctrl+]** og **Ctrl+[**, eller **▲▼** i panelet **Objekter**. Højreklik har også *rækkefølge*.

## Røret følger ikke med, når jeg flytter symbolet (røret er løsnet, sidder ikke fast)
<!-- kilde: 08-forbindelser#m-saet-et-roer-fast-igen sha:9b3bb33a -->
Enden sidder ikke fast. Vælg røret: en **orange** ende er fri, en **grøn** sidder fast. Træk den orange ende hen på symbolets grønne tilslutningspunkt, så sættes den fast, og røret følger med fremover.

## Hvordan tegner jeg et rør eller en ledning mellem to symboler (forbindelse, streg, kabel)?
<!-- kilde: 08-forbindelser#m-tegn-en-forbindelse sha:ab91e500 -->
I Tegn: vælg værktøjet **Forbindelse** (tast **O**). Klik på det første symbols grønne prik, klik for hvert knæk, og slut på det andet symbols grønne prik. Røret går vandret og lodret og sidder fast i begge symboler.

## Hvordan får jeg rør og symbol til at flugte, så røret står helt lige (snap, fang, alignment)?
<!-- kilde: 08-forbindelser#m-tilslutningspunkter-og-retning sha:9a691cf8 -->
Slå **Fang rør lige** til (standard). Træk symbolet: når tilslutningspunktet næsten flugter med røret, vises en blå stiplet linje; slip, så fanges symbolet, og røret står snorlige. Rørene vises i deres nye forløb, mens du trækker.

## Hvordan sætter jeg løbelys på mange rør på én gang (flow fra kedel til radiator, signalvej)?
<!-- kilde: 08-forbindelser#m-signalveje-loebelys-paa-en-hel-roervej-paa-n-gang sha:ea6594c3 -->
Brug en **signalvej**: i Tegn, panelet **Signalveje**, tryk **Ny signalvej …**, **Vælg på tegningen**, klik på start- og slutsymbolet. Vejen vises i tegningen med det samme. Tryk **Brug denne vej →**, vælg for hver ventil og pumpe hvornår der går flow, giv vejen et navn og tryk **Gem signalvej**.

## Ændrer en signalvej symbolernes opsætning (logikblokke, animationer)? Kan et rør høre til flere signalveje?
<!-- kilde: 08-forbindelser#m-signalveje-loebelys-paa-en-hel-roervej-paa-n-gang sha:ea6594c3 -->
Nej (siden v5.0.0). En signalvej gemmes som sit eget objekt, og serveren regner selv, hvornår hver gren er aktiv. Symbolernes egen opsætning røres ikke, så Ret og Slet påvirker kun vejen. Et rør kan godt høre til flere signalveje; har en del flere animationer af samme slags, vinder den aktive.

## Hvorfor kan jeg ikke lave en simpel binding på et symbol? Hvor er "Konvertér alle" og "Foreslå ud fra symbolet"?
<!-- kilde: 10-symboler-og-guiden#m3-flere-animationer-paa-samme-del-aktiv-passiv-og-standard sha:854bbabd -->
Siden v5.1.0 er der kun én måde at sætte et symbol op på: guiden (Bindinger › Opsæt symbol). Simple bindinger på et symbol og dets dele kan ikke laves — kun *Gå til tegning* på selve symbolet. Den gamle model (og dermed "Konvertér alle" og "Foreslå ud fra symbolet") er fjernet; ved opgraderingen blev symbolerne konverteret, og dem, der ikke kunne konverteres, står i Tegn › Meddelelser.

## Hvordan deler jeg en signalvej i flere grene (T-kryds, flere radiatorer, flere slutpunkter)?
<!-- kilde: 08-forbindelser#m-signalveje-loebelys-paa-en-hel-roervej-paa-n-gang sha:ea6594c3 -->
I signalvej-guiden: vælg start og første slutpunkt, tryk **+ Slutpunkt** (højst 4) og klik på det næste slutsymbol, eller vælg i listen *Flere slutpunkter*. Hver gren får sin egen farve i tegningen. Inden for en gren skal alle betingelser være opfyldt; et fælles stykke lyser, når mindst én gren er aktiv.

## Hvordan vælger jeg, hvilken vej signalet tager gennem en 3-vejsventil (AB → A eller AB → B)?
<!-- kilde: 08-forbindelser#m-signalveje-loebelys-paa-en-hel-roervej-paa-n-gang sha:ea6594c3 -->
I signalvej-guidens trin 2 står der en rullemenu ved hver 3-vejsventil på vejen: *automatisk*, *AB → A* eller *AB → B*. Vælger du en vej, beregnes signalvejen forfra med det samme, og tegningen viser den nye vej. I trin 3 får ventilen ét spørgsmål pr. vej (typisk dens position).

## Hvordan bestemmer pumpen retningen på en signalvej (ind og ud, flowretning)?
<!-- kilde: 08-forbindelser#m-signalveje-loebelys-paa-en-hel-roervej-paa-n-gang sha:ea6594c3 -->
Sidder en pumpe eller kontraventil på signalvejen, løber flowet fra dens udgang mod resten, uanset hvilket symbol du valgte som start (guiden skriver "Vejen er vendt, så flowet følger …"). Ind/ud-punkterne på symbolerne kan rettes under **Opsætning › Symboler › Ind/ud og veje**.

## Hvordan definerer jeg ind, ud, fælles port og veje på et symbol (3-vejs, 4-vejs ventil)?
<!-- kilde: 08-forbindelser#m-tilslutningspunkter-siden-symboler sha:74cfc3e7 -->
Opsætning › Symboler › fanen **Ind/ud og veje**: vælg symbolet, giv punkterne navn og rolle (Ind, Ud, Begge), markér det **fælles** punkt (AB) og ret evt. **vejene** (AB → A, AB → B; en 4-vejsventil fx P → A, P → B). Klik tilføjer et punkt, træk flytter det. Det bruges kun af signalveje.

## Hvor finder jeg alle symboler på tegningen samlet (symbol-oversigt, træ, grupper, signalveje)?
<!-- kilde: 07-tegn#m-symbol-oversigt-alle-symboler-t-sted sha:61803b59 -->
Panelet **Symbol-oversigt** i Tegn viser alle symboler som et træ: grundsymboler, signalveje og grupper på niveau 1; en vejs elementer og en gruppes medlemmer på niveau 2. Klik på navnet vælger det på tegningen; **Opsæt** åbner symbol-guiden (6 trin), **Animationer** gruppens animationer. ✓ = har en opsætning; søg eller vis kun dem, der ikke er opsat.

## Hvordan retter jeg en signalvej som et symbol (egne animationer, flere elementer, signalvejen som kilde)?
<!-- kilde: 08-forbindelser#m-signalveje-loebelys-paa-en-hel-roervej-paa-n-gang sha:ea6594c3 -->
Tryk **Ret som symbol** ved den gemte signalvej (Tegn › Signalveje). Vejen åbner i symbol-guiden med alle vejens elementer som dele; i trin 4 står **alle vejens animationer som almindelige animationer** (løbelys, farve, blink — også en 3-vejs ventils porte): skift type, kilde (tag, betingelse/logikblok, altid til, eller selve signalvejen), farve, hastighed og retning, slet og tilføj, ét element ad gangen med *Vis animationer for*. Fluebenet *Følger vejens udseende* betyder, at vejen genskaber animationen, når den gemmes igen — fjern det for at beholde dine ændringer. Dine egne animationer røres aldrig. En signalvej kan kun vises, ikke betjenes. I andre symbolers animationer og logik kan du vælge *en signalvej* som kilde.

## Hvordan vælger jeg, hvilke animationer en signalvej skal give (farve, blink, løbelys, roterer)?
<!-- kilde: 08-forbindelser#m-signalveje-loebelys-paa-en-hel-roervej-paa-n-gang sha:ea6594c3 -->
I signalvej-guidens trin 4 (**Udseende**) står der et kort for hver slags element på vejen. Sæt hak ved **Løbelys** (rør), **Farve**, **Stregfarve**, **Blink**, **Vises kun når vejen er aktiv** eller **Roterer** (pumper), og vælg farve og del. På en 3-vejsventil gælder animationen som standard kun portene i den vej, signalvejen bruger.

## Hvordan ændrer jeg en signalvej ved at klikke i tegningen (gå via, skift 3-vejsventil)?
<!-- kilde: 08-forbindelser#m-signalveje-loebelys-paa-en-hel-roervej-paa-n-gang sha:ea6594c3 -->
Mens trin 2 i signalvej-guiden er åbent, klik på et rør eller symbol uden for vejen for at lade vejen gå via det (klik igen fjerner det). Klik på en 3-vejsventil på vejen for at skifte dens vej (automatisk, AB → A, AB → B). *Færdig* eller Esc slår klik-tilstanden fra. Via kan også vælges i trin 1 (*Gå via*).

## Hvad er "Bind forbindelser", og hvorfor er en forbindelse orange?
<!-- kilde: 07-tegn#m-tegnehjaelp-gitter-fang-og-drejning sha:689a6f90 -->
**Bind forbindelser** (ved Tjek forbindelser) gemmer, hvad der hænger sammen, i tegningen — så gælder de gemte forbindelser for signalveje og tjekket i stedet for afstanden. **Orange** betyder, at en gemt forbindelse er gledet fra hinanden: **Ret** flytter rør-enden tilbage, og et klik på den orange prik fjerner forbindelsen. Husk at gemme tegningen.

## Hvordan undgår jeg fejl for tilslutningspunkter eller symboler, der ikke er i brug, i Tjek forbindelser?
<!-- kilde: 07-tegn#m-tegnehjaelp-gitter-fang-og-drejning sha:689a6f90 -->
Med **Tjek forbindelser** slået til: klik på den røde prik for at markere punktet som **ikke i brug** (grå stiplet ring), eller Skift+klik / **Udelad valgte fra tjekket** for at udelade et helt symbol (grå ramme med ⊘). Markeringerne gemmes med tegningen ved Gem kladde / Gem og udgiv og kan fortrydes.

## Hvordan retter jeg brudte forbindelser automatisk (rør, der ligger tæt på hinanden)?
<!-- kilde: 07-tegn#m-tegnehjaelp-gitter-fang-og-drejning sha:689a6f90 -->
Slå **Tjek forbindelser** til og tryk **Ret N forbindelser**. Rør-ender, der ligger klods op ad en anden ende eller et tilslutningspunkt (højst 25 enheder), flyttes, så de sidder sammen. Symboler flyttes aldrig, og det kan fortrydes med Ctrl+Z.

## Hvordan tjekker jeg, om alle symboler og rør hænger sammen i tegningen?
<!-- kilde: 07-tegn#m-tegnehjaelp-gitter-fang-og-drejning sha:689a6f90 -->
Slå **Tjek forbindelser** til i menuen **Vis** øverst i Tegn. Symboler og rør, hvis tilslutningspunkter alle sidder fast, bliver grønne; dem med åbne ender bliver røde med røde prikker ved enderne (stiplet kant = intet er forbundet). Det er kun en visning.

## Hvordan kan jeg se, hvad symboler, forbindelser og signalveje hedder i tegningen?
<!-- kilde: 07-tegn#m-tegnehjaelp-gitter-fang-og-drejning sha:689a6f90 -->
Åbn menuen **Vis** øverst i Tegn og sæt hak under **Navne i tegningen** (symboler, forbindelser og/eller signalveje). Navnene står som mærkater oven på tegningen (kun i Tegn, de gemmes ikke).

## Hvordan vender jeg flowets retning i en signalvej?
<!-- kilde: 08-forbindelser#m-signalveje-loebelys-paa-en-hel-roervej-paa-n-gang sha:ea6594c3 -->
Tryk **⇄ Vend flowet** under grenen i signalvej-guidens trin 2. Løbelyset vender med det samme, og valget gemmes med signalvejen. Ellers følger retningen pumpen eller kontraventilen på vejen.

## Hvorfor finder signalvejen ikke en vej (ingen sammenhængende vej, tynde streger)?
<!-- kilde: 08-forbindelser#m-signalveje-loebelys-paa-en-hel-roervej-paa-n-gang sha:ea6594c3 -->
Tjek at rørene sidder fast i symbolerne (grønne ender), at de rører hinanden, hvor de mødes, og at de er tykke nok: tynde streger (under 5 bred) og stiplede streger regnes som føler- og signallinjer og er ikke rør. Med en 3-vejsventil: prøv *automatisk* eller en anden vej.

## Hvordan laver jeg en betingelse med flere tags (pumpe kører OG ventil åben, AND, OR)?
<!-- kilde: 10-symboler-og-guiden#m3-logikblokke-betingelser-paa-flere-tags sha:4f18a3d4 -->
Lav en **logikblok** i symbolguidens trin **4. Visning**, sektionen **Logik**: tryk **+ Logikblok**, vælg AND eller OR, vælg tags i indgangene (evt. NOT eller en sammenligning som ≥ 60), og vælg blokken som kilde i en animation (*styres af: en logikblok*). Trin 6 viser blokkens værdi live.

## Hvordan gemmer jeg noget, jeg har tegnet, som et symbol i biblioteket?
<!-- kilde: 07-tegn#m-egne-symboler-gem-et-objekt-som-symbol sha:3cf7bab6 -->
Vælg det tegnede (gruppér løse dele med **Ctrl+G** og vælg gruppen), og tryk **Gem som symbol i biblioteket …** under *Valgt element*. Giv det et navn, evt. en forklaring, vælg sektion (standard *Egne symboler*) og tryk **Gem i biblioteket**. Det kræver rollen tekniker.

## Hvordan retter jeg grafikken på et symbol i biblioteket (redigér symbol)?
<!-- kilde: 07-tegn#m-import-r-svg-symboler-og-organis-r-biblioteket sha:5edc84fb -->
Gå til **Opsætning › Symboler › Bibliotek** og tryk **Redigér** ved symbolet. Symbolet åbnes i Tegn i en arbejdstegning; ret det og tryk **Gem i biblioteket**. Et eget symbol får en ny version; et indbygget gemmes som en kopi "… (egen)".

## Hvordan laver jeg en knap, der giver en kort impuls (trykknap, puls, start-knap, kvittér-knap)?
<!-- kilde: 10-symboler-og-guiden#m-betjeningsformer sha:f09a7b7a -->
Sæt symbolet op med guiden og vælg betjeningsformen **Trykknap (puls)** i trin 1. Vælg tagget i trin 2, og sæt pulslængden (100–10000 ms) i trin 5. Tagget sættes Til i den tid og derefter Fra af serveren.

## Hvordan grupperer jeg flere elementer, eller opløser en gruppe?
<!-- kilde: 07-tegn#m-taster sha:ebdc04b0 -->
Vælg elementerne (Shift+klik eller træk en ramme) og tryk **Ctrl+G** eller **Gruppér** i knaplinjen over det markerede. **Ctrl+Shift+G** eller **Opløs** deler gruppen igen. Grupper af symboler, der bruges igen og igen, gemmes under *Grupper af symboler*.
