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

## Hvorfor kan jeg ikke lave en simpel binding på et symbol? Hvor er "Konvertér alle" og "Foreslå ud fra symbolet"?
<!-- kilde: 10-symboler-og-guiden#m3-flere-animationer-paa-samme-del-aktiv-passiv-og-standard sha:854bbabd -->
Siden v5.1.0 er der kun én måde at sætte et symbol op på: guiden (Bindinger › Opsæt symbol). Simple bindinger på et symbol og dets dele kan ikke laves — kun *Gå til tegning* på selve symbolet. Den gamle model (og dermed "Konvertér alle" og "Foreslå ud fra symbolet") er fjernet; ved opgraderingen blev symbolerne konverteret, og dem, der ikke kunne konverteres, står i Tegn › Meddelelser.

## Hvordan definerer jeg ind, ud, fælles port og veje på et symbol (3-vejs, 4-vejs ventil)?
<!-- kilde: 08-forbindelser#m-tilslutningspunkter-siden-symboler sha:3a559475 -->
Opsætning › Symboler › fanen **Ind/ud og veje**: vælg symbolet, giv punkterne navn og rolle (Ind, Ud, Begge), markér det **fælles** punkt (AB) og ret evt. **vejene** (AB → A, AB → B; en 4-vejsventil fx P → A, P → B). Klik tilføjer et punkt, træk flytter det.

## Hvor finder jeg alle symboler på tegningen samlet (symbol-oversigt, træ, grupper)?
<!-- kilde: 07-tegn#m-symbol-oversigt-alle-symboler-t-sted sha:a6ff1f22 -->
Panelet **Symbol-oversigt** i Tegn viser alle symboler som et træ: grundsymboler og grupper på niveau 1; en gruppes medlemmer på niveau 2. Klik på navnet vælger det på tegningen; **Opsæt** åbner symbol-guiden (6 trin), **Animationer** gruppens animationer. ✓ = har en opsætning; søg eller vis kun dem, der ikke er opsat.

## Hvad er "Bind forbindelser", og hvorfor er en forbindelse orange?
<!-- kilde: 07-tegn#m-tegnehjaelp-gitter-fang-og-drejning sha:e6214945 -->
**Bind forbindelser** (i menuen **Forbindelser**, med Tjek forbindelser slået til) gemmer, hvad der hænger sammen, i tegningen — så gælder de gemte forbindelser for tjekket i stedet for afstanden. **Orange** betyder, at en gemt forbindelse er gledet fra hinanden: **Ret** flytter rør-enden tilbage, og et klik på den orange prik fjerner forbindelsen. Husk at gemme tegningen.

## Hvordan undgår jeg fejl for tilslutningspunkter eller symboler, der ikke er i brug, i Tjek forbindelser?
<!-- kilde: 07-tegn#m-tegnehjaelp-gitter-fang-og-drejning sha:e6214945 -->
Med **Tjek forbindelser** slået til: klik på den røde prik for at markere punktet som **ikke i brug** (grå stiplet ring), eller Skift+klik / **Udelad valgte fra tjekket** for at udelade et helt symbol (grå ramme med ⊘). Markeringerne gemmes med tegningen ved Gem kladde / Gem og udgiv og kan fortrydes.

## Hvordan retter jeg brudte forbindelser automatisk (rør, der ligger tæt på hinanden)?
<!-- kilde: 07-tegn#m-tegnehjaelp-gitter-fang-og-drejning sha:e6214945 -->
Slå **Tjek forbindelser** til og tryk **Ret N forbindelser**. Rør-ender, der ligger klods op ad en anden ende eller et tilslutningspunkt (højst 25 enheder), flyttes, så de sidder sammen. Symboler flyttes aldrig, og det kan fortrydes med Ctrl+Z.

## Hvordan tjekker jeg, om alle symboler og rør hænger sammen i tegningen?
<!-- kilde: 07-tegn#m-tegnehjaelp-gitter-fang-og-drejning sha:e6214945 -->
Slå **Tjek forbindelser** til i menuen **Forbindelser** øverst i Tegn. Symboler og rør, hvis tilslutningspunkter alle sidder fast, bliver grønne; dem med åbne ender bliver røde med røde prikker ved enderne (stiplet kant = intet er forbundet). Det er kun en visning.

## Hvordan kan jeg se, hvad symboler og forbindelser hedder i tegningen?
<!-- kilde: 07-tegn#m-tegnehjaelp-gitter-fang-og-drejning sha:e6214945 -->
Åbn menuen **Vis** øverst i Tegn og sæt hak under **Navne i tegningen** (symboler og/eller forbindelser). Navnene står som mærkater oven på tegningen (kun i Tegn, de gemmes ikke). Hak ved **tags** viser de PLC-tags, hvert symbol bruger (fra guiden og bindingerne), i lilla under symbolet.

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

## Hvordan viser jeg flow (løbelys) i rørene automatisk, uden at sætte hvert rør op (flowberegning, pumpe kører)?
<!-- kilde: 08-forbindelser#m-flow-i-anlaegget-systemet-beregner-det-selv sha:8acd21f9 -->
Serveren beregner selv flowet gennem de forbundne symboler. Bind forbindelserne (menuen **Forbindelser** › Tjek forbindelser › **Bind forbindelser**, og gem), sæt pumpen op i symbol-guidens trin 4 under **Flow** (Pumpe, kapacitet i l/min, flow-rate fra et tag), og alle rør i løkken får løbelys på Overview med retning og fart efter flowet (standardgruppen *Alle forbindelser*).

## Hvordan får nogle rør en anden farve eller blink efter flowet (forbindelsesgruppe)?
<!-- kilde: 08-forbindelser#m-flow-i-anlaegget-systemet-beregner-det-selv sha:8acd21f9 -->
Tryk **Flow** i værktøjslinjen i Tegn. Vælg rørene på tegningen, giv gruppen et navn og tryk **Opret af valgte**. Under **Animationer** vælger du løbelys, farve efter flow (grænser i l/min), blink ved et flow (mindst/højst) eller en fast farve. En forbindelse hører til én gruppe ad gangen.

## Hvordan bestemmer en 3-vejsventil, hvilken vej flowet går (AB → A, AB → B, register 10/20)?
<!-- kilde: 10-symboler-og-guiden#m3-flow-symbolets-rolle-i-flowberegningen sha:757a32f5 -->
Giv ventilen positioner (fx *AB → A* og *AB → B*), og lad tagget bestemme positionen i trin 3 (fx register 10 = AB → A, 20 = AB → B, eller to til/fra-signaler). I trin 4 under **Flow** sætter du hak ved den åbne vej i hver position. Flowberegningen sender så flowet den vej, og animationerne pr. position (fx portene AB og A grønne, B sort) sættes som altid i trin 4.

## Hvorfor er der intet flow i rørene (pumpe kører ikke, ingen vej, ikke bundet)?
<!-- kilde: 08-forbindelser#m-flow-i-anlaegget-systemet-beregner-det-selv sha:8acd21f9 -->
Tjek at tegningens forbindelser er bundet og gemt (Flow-vinduet siger det, hvis de ikke er), at pumpen har **Pumpe** slået til med kapacitet over 0 og en flow-rate over 0, at der er en åben vej rundt fra pumpens UD tilbage til dens IND (ventilernes åbne veje i deres position, kontraventilens retning, restriktion over 0). Beskeder fra beregningen står øverst i Flow-vinduet; kortet *Flowberegning* på Status viser fejl.

## Hvor er Slet tegning, størrelsen, versionerne og kommentarfeltet i Tegn (topmenuen)?
<!-- kilde: 07-tegn#m-skaermen sha:2c92fe88 -->
Topmenuen i Tegn har tre dele. Til venstre åbner **tegningens navn** en menu med skift af tegning, **+ Ny tegning …**, **⤢ Størrelse …**, **Bindinger →** og **Slet tegning …**; ved siden af står **versionen** (fx *v4 kladde*), hvor du åbner en anden version eller udgiver den åbne. I midten står **Vis**, **Fang**, **Forbindelser** og **Flow**. Til højre zoom, **Meddelelser**, **Gem kladde** og **Gem og udgiv** — pilen **▾** på *Gem og udgiv* åbner kommentaren til versionen.

## Hvordan ser jeg flowet i Tegn, før jeg gemmer (live, simulering, prøv pumper og ventiler uden PLC)?
<!-- kilde: 08-forbindelser#m3-se-flowet-i-tegn-live-og-simulering sha:33f535b9 -->
Tryk **Flow** i værktøjslinjen i Tegn og sæt hak i **Vis flowet på tegningen**. Flowet tegnes som blå løbelys med tal i l/min oven på tegningen, beregnet ud fra tegningen, som den ser ud lige nu (også ugemt). **Live** bruger PLC'ens værdier; **Simulering** lader dig starte/stoppe pumper, sætte rate og restriktion (0,00–1,00) og vælge ventilernes position — der skrives aldrig til PLC'en.

## Hvordan styres en 3-vejsventil, og hvordan farves dens porte efter flowet (AB og A grønne, B sort)?
<!-- kilde: 10-symboler-og-guiden#m3-flow-symbolets-rolle-i-flowberegningen sha:757a32f5 -->
Positionen styres af et tag i trin 2–3 (fx register 10 = AB → A, 20 = AB → B). I trin 4 under **Flow** sætter du hak ved den åbne vej i hver position, og **Farv portene efter de åbne veje** farver portene automatisk: porte på en åben vej får farven *åben* (grøn), de andre *lukket* (sort). Det kræver, at symboltypens punkter har en *Del* (port_a, port_b, port_ab) under Opsætning › Symboler › Ind/ud og veje. Selve flowet beregnes af serveren ud fra positionen.

## Hvordan sætter jeg restriktionen til et tal mellem 0 og 1 (ikke til/fra)?
<!-- kilde: 10-symboler-og-guiden#m3-flow-symbolets-rolle-i-flowberegningen sha:757a32f5 -->
I trin 4 under **Flow** › **Restriktion**: vælg *en fast værdi* (skyder og tal med to decimaler, 0,00 = blokeret … 1,00 = ingen) eller *et tag* med en tal-værdi, fx ventilens åbning i %, og skriv 100 i *1,00 ved*. Et til/fra-signal giver kun 0,00 eller 1,00 — guiden advarer.

## Hvordan bruger jeg en flowsensor (målt flow) i flowberegningen?
<!-- kilde: 10-symboler-og-guiden#m3-flow-symbolets-rolle-i-flowberegningen sha:757a32f5 -->
Åbn guiden for symbolet, hvor sensoren sidder, trin 4 › **Flow** › **Målt flow**, og vælg sensorens tag (l/min). Pumperne, der giver flow gennem symbolet, skaleres, så beregningen passer med målingen.

## Hvordan gør jeg et symbol til en pumpe, kilde, forbruger eller ledning for alle tegninger (flow-rolle, el-komponenter)?
<!-- kilde: 08-forbindelser#m3-ind-ud-og-veje sha:0b1d9f31 -->
Under Opsætning › Symboler › **Ind/ud og veje** vælger du symboltypens **Flow-rolle**: forbruger, pumpe/kilde (fx en strømforsyning) eller rørstykke/ledning, og et **medie** (vand l/min, luft m³/h, el A). Standard-kapacitet og standard-restriktion (0,00–1,00) gælder, når et symbol ikke har sin egen flow-opsætning i guiden.

## Hvordan får en farve-animation på et tal-tag en grænse (aktiv ved ≥ 50, ikke aktiv under)?
<!-- kilde: 10-symboler-og-guiden#m-animationer-i-guiden-trin-4 sha:f6ef6ac8 -->
I guidens trin 4 ved animationen *Farve* (eller *Streg*) med et tal-tag: skriv grænsen i **Aktiv når ≥** (fx 50). Fra 50 og op vises aktiv-farven, under 50 fra-farven. Tomt felt = aktiv, når værdien ikke er 0 (0 = fra-farven, over 0 = aktiv-farven). **+ Grænse** lægger flere farver ovenpå; aktiv-farven gælder op til den første grænse. Farverne står som en tabel med én række pr. værdiområde.

## Hvordan definerer jeg lavt og højt flow for en flowsensor og viser flowet med løbelysets fart, blink eller farve (baseline, flow-niveau)?
<!-- kilde: 10-symboler-og-guiden#m3-flow-symbolets-rolle-i-flowberegningen sha:757a32f5 -->
I guidens trin 4 › **Flow** › **Målt flow**: vælg sensorens tag og skriv **lavt flow** og **højt flow** (fx 15,1 og 16,5 l/min). Det målte flow bliver symbolets **flow-niveau** 0,00–1,00 (15,85 → 0,54). Vælg **symbolets flow-niveau** som kilde i en animation: løbelysets fart følger niveauet, blink fx ved *højst 0,1*, farve fx *Aktiv når ≥ 0,8*.

## Er flow-rate og restriktion faste værdier eller tags?
<!-- kilde: 10-symboler-og-guiden#m3-flow-symbolets-rolle-i-flowberegningen sha:757a32f5 -->
De er faste værdier for symbolet (dets fysik): skriv tallet 0,00–1,00 i trin 4 › Flow, eller træk i skyderen. Sæt hak i **styret af et tag**, hvis PLC'en skal styre værdien, og angiv hvad der er 1,00 (fx 100 for en ventils åbning i %).

## Hvordan tester jeg en tegnings tilstande uden PLC (simulator, indskyd værdier, scenarier)?
<!-- kilde: 07-tegn#m-simulator-proev-tegningens-tilstande sha:c147ad77 -->
Åbn **Opsætning › Simulator** (eller **Simulér** på Overview). Panelet viser alle variabler, tegningen bruger (tags, positioner, alarmer). Sæt hak ud for en variabel og vælg en værdi; tegningen viser resultatet med det samme — logik, symbolernes tilstand og flowet beregnes som i drift. **komm.fejl** viser en kommunikationsfejl, **Start fra live** kopierer PLC'ens værdier ind, og **Gem som …** gemmer et scenarie. Intet skrives til PLC'en.

## Hvordan definerer jeg en ventils tilstande (A igennem AB og B blokeret, 4-vejsventil A → B / C → D)?
<!-- kilde: 08-forbindelser#m3-ind-ud-og-veje sha:0b1d9f31 -->
Under Opsætning › Symboler › **Ind/ud og veje** › **Tilstande**: giv hver tilstand et navn og sæt hak ved de veje, der er åbne — kolonnen *Betyder* skriver det i ord, også de blokerede porte (fx "A igennem AB · B blokeret"). Standarder: 3-vejsventilerne *A → AB* og *B → AB*, 4-vejsventilen (porte A, B, C, D) *A → B* og *C → D*. Du kan tilføje alle de tilstande, symbolet har brug for (+ Tilstand). I guidens trin 4 › Flow vælger du så tilstanden for hver position.

## Hvordan kobler jeg en omskifters eller ventils positioner til symboltypens tilstande, og hvordan retter jeg udseendet for ét symbol?
<!-- kilde: 10-symboler-og-guiden#m3-tilstande-positioner-fra-symboltypen sha:79388783 -->
Har symboltypen tilstande, hedder guidens trin 3 **Tilstande**: vælg for hver position typens **Tilstand** (fx *A → AB* eller *Hånd*) og dens **Navn på tegningen** (fx *Varme*); **Brug typens tilstande** laver én position pr. tilstand. Udseendet (portfarver, grebets vinkel …) kommer fra typen. I trin 4 › **Tilstandenes udseende** kan du rette en værdi for kun dette symbol (markeres *afviger*); **Brug typens udseende** fjerner afvigelsen.
