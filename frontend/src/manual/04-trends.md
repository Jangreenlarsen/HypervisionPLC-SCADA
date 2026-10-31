# Trends

![Trends: valgte tags, tidsrum og kurver](/manual/trends.png)

**Trends** viser kurver over værdier gennem tiden. Kun tags, hvor **historik** er slået til, har kurver (slås til under **Tags**, eller direkte på Trends-siden med **Begynd at gemme historik**).

## Hvem ser hvad

Viewer, operatør og driftpanel kan ikke søge efter eller vælge tags frit — de ser kun de trends, der er sat op i deres tegninger (symboler og trendgrafer), og vælger mellem dem under *Symbol*. Tekniker og admin kan vælge alle tags.

## Vælg kurver

- **Symbol**: vælg et symbol fra tegningerne, så vises **alle symbolets kurver** på én gang. Har nogle af symbolets tags ikke historik, står de under listen; en tekniker kan slå dem til med **Gem historik for de …**.
- **Tags** (tekniker og admin): vælg et eller flere tags i listen (søg med feltet **Søg**). Højst **12 kurver** vises ad gangen; kurve 8–12 har samme farver som de første, men stiplet linje.
- **Graf**: ud for hvert valgt tag vælger du, hvilken graf kurven vises i. **Auto** lægger kurver med samme enhed i samme graf.

## Tidsrum

Vælg **15 min, 1 time, 8 timer, 24 timer, 7 dage**, eller **Vælg periode** for et selvvalgt interval (*Fra* og *Til*). Kurverne **opdateres live**.

## Læs kurverne

- Hver kurve har sit **navn ved højre kant** ud for sidste punkt. Ligger kurverne tæt, spredes navnene, og en **pil** peger fra navnet til kurven.
- **Værdier ved markøren**: peg på en graf, så viser en boks tidspunktet og alle kurvers værdi lige dér (også middelkurver).
- **Zoom**: træk i en graf for at zoome ind på et tidsudsnit. **🔒 Grafer låst sammen** får zoom og rulning i én graf til at gælde alle grafer. **Nulstil visning** zoomer ud til hele perioden.
- **Dobbeltklik** på en graf for at forstørre den; dobbeltklik igen for at gå tilbage. **×** fjerner grafen fra visningen.
- **Skillelinjer**: stiplede lodrette linjer ved hver **time** eller **dag** (eller *Fra*).
- **Huller** i en kurve betyder, at der ikke var kontakt til PLC'en dengang. **Udfyld huller (blinker)** udfylder dem i visningen med interpolerede punkter, der blinker, så de kan kendes fra målte data.

## Middelkurve

**Middel over** (fx *24 timer*) viser hver kurve som den **glidende middelværdi** over de seneste timer — en rolig kurve for langsomme forløb. **Egen tid …** lader dig skrive antal timer. Vælg derefter, hvad der vises: **Begge** (rå kurve og stiplet middelkurve), **Middel** eller **Rå**. Der hentes automatisk data fra før perioden med, så også kurvens første punkt er et rigtigt gennemsnit. Kun visning — de gemte data og CSV er uændrede, og til/fra-kurver røres ikke.

**Middelkurve i tegningens trendgraf**: under *Opsæt symbol › Visning* vælger en tekniker *Middelkurve* (fx over 24 timer) og om den vises *Begge* eller *Kun middel*.

## Visninger (gemte udvalg)

Vælg tags, graf-valg og tidsrum, og tryk **Gem som …** (kun tekniker/admin) — fx alle 8 temperaturfølere i en tank under navnet *Tank temp*. Visningen står bagefter i dropdownen **Visning** øverst i panelet for alle, der må se de tags.

## Navne på kurverne

Sæt flueben i **Administrér** og tryk **Navn** ud for et tag — så vises navnet (fx *Fremløbstemperatur*) i stedet for tag-navnet i listen og graferne. Tomt navn = tag-navnet. Navnet er tagets *beskrivelse*, så det ses også under **Tags**.

## Historik: gem, stop og slet

- **Begynd at gemme historik** for et tag direkte fra Trends (eller under **Tags**).
- Et tag kan **stoppes** (historikken bevares) eller dets **historik slettes**.
- Historik, der er ældre end opbevaringstiden (standard 30 dage), slettes automatisk.
- **CSV** henter de viste data til regneark — altid de rå, gemte værdier.

## Analysér data

![Trends med Analysér data slået til og to grafer over den seneste time](/manual/trends-analyse.png)

Sæt flueben i **Analysér data** for at lade siden finde uregelmæssigheder i tal-kurverne (til/fra-kurver analyseres ikke). Rådata ændres aldrig, og CSV indeholder altid alt.

- **Spike**: ét punkt langt fra sine naboer. **Urealistisk spring**: et stort trin, hvor niveauet ændrer sig. **Fastfrosset værdi**: præcis samme værdi i lang tid. **Hul i data**: usædvanlig lang tid mellem to punkter.
- Fundene får en **ring om punktet** (huller en lodret streg). Fjern fluebenet ved **Vis ringe** for at skjule ringene; knappen **Uregelmæssigheder** viser en oversigt over fundene.
- **Fastfrosset efter** bestemmer, hvor længe samme værdi skal stå, før den tæller som fastfrosset: *1 time, 6 timer* (standard), *1 døgn, 3 døgn, 7 døgn* eller *Aldrig*. En rolig føler, fx en temperatur, står stille længe — vælg en lang tid for den.
- **Skjul spikes** udfylder enkeltstående spikes ved interpolation i visningen. Spring, fastfrosne værdier og huller markeres kun.
- Under graferne står, hvor mange **procent af punkterne** der er ramt, for hver kurve og samlet (*I alt*).
