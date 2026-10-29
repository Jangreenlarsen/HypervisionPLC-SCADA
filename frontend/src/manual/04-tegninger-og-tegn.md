# Tegninger og Tegn

En **tegning** er et SVG-billede af anlægget. Du kan **uploade** en tegning lavet i et andet program (fx Inkscape) eller **tegne** den i systemets egen editor. Begge dele ligger under **Opsætning** (kræver rollen tekniker).

## Tegninger

![Siden Tegninger: upload, listen over tegninger og deres versioner](/manual/tegninger.png)

Siden **Tegninger** er listen over alle tegninger.

- **Upload tegning**: vælg en SVG-fil (højst 5 MB), giv den et **navn** og evt. en **kommentar**. Serveren renser filen (scripts og andet farligt fjernes) og viser en rapport over, hvad der blev fjernet.
- **Versioner**: hver gang du uploader eller gemmer, opstår en ny **version**. **Versioner** viser listen; **Gør aktiv** vælger, hvilken version Overview viser. Du kan derfor forberede en ny version uden at brugerne ser den, og gå tilbage, hvis noget går galt. **Upload ny version** lægger en ny version til en eksisterende tegning.
- **Gør start-tegning**: Overview åbner med denne tegning. **Fjern** start-tegningen, og Overview åbner med den første i listen.
- **Deaktivér / Aktivér**: gør tegningen **offline** — den vises grå på Overview med beskeden *Tegningen er deaktiveret*, uden live-værdier og uden betjening (heller ikke fra panelet), og symbolernes positions-overvågning og afvigelsesalarmer stopper. Tags, som **kun** deaktiverede tegninger bruger, holder op med at blive pollet (mindre trafik til PLC'en). Tags med **alarm, trend, energi eller ugeprogram** pollas stadig — alarmer slås aldrig fra, fordi en tegning er skjult. Tegning, versioner og opsætning bevares; **Aktivér** henter den online igen. Kun teknikere og admin kan deaktivere.
- **Slet**: sletter tegningen med alle versioner og bindinger. Før du bekræfter, viser systemet **hvad det rammer**: antal versioner og bindinger, andre tegninger med en "gå til"-knap hertil (de holder op med at virke), om det er start-tegningen, og hvilke brugere der har adgang til den.

> Bindinger følger tegningens **element-id'er**. Ændrer en ny version et elements id, mister det sin binding; **Bindinger** viser *Forsvundne elementer*, som du kan rydde op i.

![Versioner af en tegning: Gør aktiv, upload ny version og visning af selve SVG'en](/manual/tegninger-versioner.png)

## Tegn

![Tegn: editoren til venstre og det valgte element med navn, symboler og Gem-knapper til højre](/manual/tegn.png)

**Tegn** er en indbygget tegneeditor (SVG-Edit). Brug den til at tegne rør, tanke og tekst, eller til at indsætte færdige **symboler** fra biblioteket.

### Sådan tegner du

1. Vælg en eksisterende tegning (og version) i rullelisterne øverst, eller start en ny (**— Ny tegning —**). Står du på en tegning i **Overview**, åbner menupunktet **Tegn** (og **Bindinger**) direkte den tegning.
2. Tegn med værktøjerne i editoren: linjer, rektangler, cirkler, tekst, farver og lag. Peg på et værktøj for at se, hvad det hedder (og dets genvejstast); **linjen over tegneområdet** fortæller, hvordan det valgte værktøj bruges (fx *Rektangel: træk for at tegne · Shift = kvadrat · Esc = tilbage til Vælg*).
3. Til højre ser du **Valgt element**. Giv det et **Navn**, hvis det skal være et symbol, der senere kan sættes op med guiden. **Avanceret** viser elementets tekniske **id**.
4. Tryk **Gem kladde** (gemmer en ny version, men viser den ikke endnu) eller **Gem og udgiv** (gemmer og gør den aktiv). En ny tegning skal have et navn.
5. **Slet tegning** fjerner hele tegningen (med samme oversigt over, hvad det rammer).
6. **Bindinger** åbner bindingsiden for tegningen.

Er der ændringer, du ikke har gemt, spørger systemet, før de kasseres.

**Tegningens størrelse:** knappen **Størrelse: 1200 × 700** øverst viser og ændrer tegningens bredde og højde. Vælg et **fast valg** (fx *Full HD-skærm 1920 × 1080* eller *Panel 1280 × 800*) eller skriv bredde og højde (100–10000), og tryk **Brug størrelsen**. **Tilpas til indholdet** flytter tegningen op i hjørnet og gør den præcis stor nok med den valgte margen. En baggrund, der fyldte hele tegningen, følger med. **Ctrl+Z** fortryder; gem med *Gem kladde* / *Gem og udgiv*. Nye tegninger starter på 1200 × 700, og Overview skalerer altid tegningen til skærmen.

### Tegnehjælp: gitter, fang og rotation

Under værktøjslinjen i Tegn står rækken **Tegnehjælp**:

- **Vis gitter** viser et net **ovenpå** tegningen (det ændrer ikke tegningen). Linjerne ligger med den valgte **gitterafstand** (5, 10, 20, 25 eller 50 enheder), og hver 5. linje er kraftigere. Gitteret følger zoom og rulning og flugter med linealerne.
- **Fang til gitter** lægger objekter på gitteret: når du flytter, indsætter, duplikerer eller sætter et symbol ind, flyttes objektets **øverste venstre hjørne** til nærmeste gitterpunkt. Kopier havner dermed på samme gitter som originalen, og når du tegner nye figurer, følger de også gitteret.
- **Fang til objekter**: slipper du et objekt tæt på et andet (inden for ca. 8 pixel på skærmen), lægger det sig **kant mod kant** eller **midte mod midte** med det nærmeste objekt. Det virker, når du **flytter** et eksisterende objekt (ikke mens du tegner et nyt), og fangen kan fortrydes med **Ctrl+Z**. Små justeringer med piletasterne fanges ikke.
- **Skalér symmetrisk**: trækker du i et hjørne for at ændre størrelsen, ændres bredde og højde i samme forhold, så symbolet ikke bliver fladt eller strakt. Hold **Shift** nede for at skalere frit (uden indstillingen er det omvendt: Shift giver symmetrisk skalering). Huskes i browseren.
- **Rotation** sker i **15°-trin**. Hold **Shift** nede, mens du drejer, for at rotere **frit**.

Indstillingerne huskes i din browser.

![Tegn med Tegnehjælp: gitter vist, fang til gitter og fang til objekter slået til](/manual/tegn-gitter.png)

### Farver på de valgte symboler

Vælg et eller flere symboler (hold **Shift** nede, eller træk en ramme), så viser panelet *Valgt element* feltet **Farver** med de farver, markeringen bruger (fx rørenes grå). Tryk på en farve og vælg en ny — så skiftes den farve i **alle** de valgte symboler på én gang, både fyld og streg. De andre farver røres ikke. **Ctrl+Z** fortryder skiftet i ét trin, og ændringen gemmes med **Gem kladde** / **Gem og udgiv**.

> Farven her er symbolets **grundfarve** i tegningen. Har symbolet en animation (fx *Farve* eller *Løbelys*), bestemmer animationen farven på Overview, når den er aktiv.

### Grupper af symboler

Vælg flere symboler i tegningen og tryk **Gem markering som gruppe** i sektionen **Grupper** (symbollisten til højre). Giv gruppen et navn og en art: **Funktionsgrupper** er en del af anlægget med en funktion, fx *Fyr uden akku-tank*; **Udvalg** er et frit udvalg, fx 3-vejs ventil, rør og akkutank. Tryk på gruppens navn for at markere alle dens symboler igen. Under **⋯** kan du tilføje eller fjerne de valgte, sætte gruppen til de valgte, omdøbe, flytte den mellem de to arter eller slette den (symbolerne slettes ikke).

Samme symbol må gerne være med i flere grupper. Er det valgte symbol med i grupper, står de nævnt under listen — og øverst i **Opsæt symbol**. Gem tegningen før du laver grupper.

**Animationer på en gruppe:** under **⋯ › Animationer …** (eller på siden Bindinger, når du har valgt en gruppe) sætter du animationer op for hvert symbol i gruppen — fx farver alle gruppens rør, når *Fyr kører*. Gruppens animationer gælder **ud over** symbolets egne og andre gruppers; er et rør med i flere grupper, har det altså sine egne animationer plus én opsætning pr. gruppe. Hver gruppe har sin egen farve. I dialogen (og i symbolguiden, trin 4) vises de andre ejeres animationer skrivebeskyttet i deres farver, så du kan se, hvad du ikke skal ændre. Flere animationer af samme slags på samme del: den øverste *aktive* vinder; uden "passiv" vinder den sidste, og gruppernes kommer efter symbolets egne. **Samme animation til alle:** fanen **Alle medlemmer** i dialogen sætter samme animationer op på hele gruppen i ét hug — tilføjet til eller i stedet for symbolernes egne gruppe-animationer. De anvendes på *Hele symbolet*; animationer på enkelte dele sætter du op pr. symbol. Symboler, hvor animationen ikke kan bruges, kan springes over (de listes bagefter).

Fjerner du et symbol fra gruppen, fjernes gruppens animationer på det også. Tags, der bruges af en gruppe, kan ikke slettes. På siden **Bindinger** kan du vælge en gruppe over symbollisten for kun at se dens symboler.

### Erstat tegnede dele med symboler

Har du en tegning, hvor pumper, ventiler og etiketter er tegnet som almindelige figurer, kan du **erstatte dem med symboler fra biblioteket**, så de kan sættes op med guiden:

1. **Opløs en stor gruppe først:** er hele tegningen samlet i én gruppe, så vælg gruppen og tryk **Opløs gruppen** — så kan delene vælges enkeltvis.
2. Vælg den tegnede del (fx en pumpe eller en etiket) og tryk **Erstat med symbol …**.
3. Systemet foreslår symboler ud fra delens form (fx *Statusfelt* til en afrundet etiket, *Pumpe* til en cirkel med trekant). Du kan også søge i hele biblioteket.
4. Vælg symbolet og tilret indstillingerne: **navn**, **behold delens id** (så bindinger på selve delen følger med), **overtag teksten** (en etiket beholder sin tekst) og **stræk til at fylde**.
5. Under **Andre dele af samme slags** kan du erstatte **alle lignende** på én gang — enten kun dem med samme størrelse eller alle af samme slags uanset størrelse (fx etiketter med forskellig tekstlængde).
6. **Flere løse dele?** Er symbolet tegnet af flere figurer (fx en ventil af trekanter, en prik og en motorcirkel), så marker dem alle og tryk **Erstat markeringen med symbol …** — så erstattes de samlet af ét symbol (tag også bogstaverne med, hvis symbolet selv har dem). **Spejlvend vandret** bruges, hvis den tegnede ventil vender omvendt; symbolets bogstaver spejles ikke.
7. Tryk **Erstat**. Symbolet får samme **midte, størrelse og drejning** som den gamle del. **Ctrl+Z** fortryder hele erstatningen i ét trin.
8. Tryk **Gem kladde**. Så er resultatet en ny version, og **Overview viser stadig den gamle**, til du udgiver den nye.

**Opdatér gamle symboler:** er et symbol fra biblioteket kommet i en ny udgave (fx pumpen med retningspil), så vælg et af de gamle og tryk **Erstat med symbol …** — forslaget er den nyeste udgave af samme symbol. Med **Behold delens id** (standard) beholder symbolet sit navn, sin placering, drejning og størrelse og sin opsætning (animationer på *Hele symbolet*; animationer på de gamle dele skal sættes op igen). Vælg **Også de N lignende** for at opdatere alle symboler af samme slags på én gang — hver beholder sit eget navn.

![Erstat med symbol: forslag ud fra delens form, indstillinger og valg om at erstatte alle lignende](/manual/tegn-erstat.png)

> **Retning og akse:** for en **pumpe** og en **kontraventil** aflæser systemet, hvilken vej den tegnede trekant peger, og drejer symbolet, så det peger samme vej. For en **ventil** tegnet som to trekanter aflæses, om den står **vandret eller lodret**, og ventilsymbolet drejes tilsvarende (valgene *Drej symbolet …* i dialogen). For andre symboler er retningen tegnet ind i den gamle del og kan ikke aflæses sikkert — kontrollér og drej dem efter erstatning (**Shift** giver fri rotation). Bindinger på **underelementer** i den gamle del følger ikke med; dialogen advarer, hvis der er nogen.

### Symbolbiblioteket

![Symbolbiblioteket i Tegn, sorteret i kategorier med søgning](/manual/tegn-symboler.png)

Under tegneområdet finder du **symbolbiblioteket**, sorteret i kategorier (*Betjening*, *Proces og visning*, *Rør og VVS*, *Elektrisk*, *Solcelleanlæg*). Søg efter et symbol (fx *bøjning* eller *kontaktor*), og tryk på det for at sætte det ind midt på tegningen; flyt og tilpas det bagefter. Hvert indsat symbol får et **navn** (fx *Pumpe 2*), som du kan ændre.

**Mine symboler**: de symboler du bruger mest, kan du samle i en egen sektion øverst i biblioteket. Tryk **☆** i hjørnet af et symbol for at lægge det i *Mine symboler* (stjernen bliver fyldt **★**); tryk igen for at tage det ud. Inde i *Mine symboler* flytter **◀** og **▶** et symbol frem eller tilbage, så du kan ordne dem som du vil. Listen gemmes på serveren for din bruger, så den følger dig til en anden pc eller browser; søgefeltet gælder også her. Plads til højst 60 symboler.

**Navne skal være unikke.** Har flere symboler samme navn (fx gamle kopier), viser Tegn en advarsel med knappen **Giv dem unikke navne**: det første beholder sit navn, de andre får det næste ledige nummer (fx *Bøjning 90° 6* → *Bøjning 90° 8*). Det kan fortrydes med **Ctrl+Z** og gemmes med *Gem kladde* / *Gem og udgiv*. Opsætninger og bindinger følger elementet, ikke navnet, så de berøres ikke.

Et nyindsat symbol skal **sættes op**: vælg symbolet og tryk **Opsæt symbol (6 trin)**. Tegningen gemmes og udgives først (du bliver spurgt), fordi guiden arbejder på den aktive version. Se *Symboler og guiden*.

**Felter med tekst** (*Statusfelt*, *Værdifelt*, *Auto/Manuel*): træk i et sidegreb for at gøre feltet bredere (eller højere), så der er plads til mere tekst — teksten bliver ikke strakt, men beholder sin størrelse (midterstillet tekst følger midten), og et statusfelt beholder sine runde ender. Ret selve teksten ved at dobbeltklikke på den.

**Genveje** (kategorien *Genveje*): knapperne **Gå til Alarmer**, **Gå til Trends** og **Gå til Energi**. Et klik på dem i Overview åbner siden. Alarmknappen viser et mærke med **antallet af aktive alarmer** — orange når de er kvitteret, rødt og blinkende når der er ukvitterede (mærket er skjult uden alarmer). Genvejene skal ikke sættes op. På et driftpanel åbner *Gå til Alarmer* (med kvittering) og *Gå til Trends* siderne uden menu — med *Tilbage* til tegningen; *Gå til Energi* åbnes ikke. Trends viser kun de trends, der er sat op i panelbrugerens tegninger.

**Omskifter med egne positioner**: under *Betjening* kan du skrive positionernes navne (2–8, adskilt med komma, fx *Hånd, 0, Auto*) og indsætte en omskifter med lige det antal positioner.

> Rør og fittings (bøjninger, T-stykker, kryds) er tegnet i samme tykkelse, så de passer sammen. Brug **Løbelys** på rør for at vise strømning. T-stykker og kryds består af selvstændige rør, så hvert rør kan få sit eget løbelys; et ældre T-stykke/kryds (én sti) deles med **Del i rør** i panelet *Valgt element*.
