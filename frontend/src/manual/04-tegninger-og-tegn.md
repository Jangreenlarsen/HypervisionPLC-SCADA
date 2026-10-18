# Tegninger og Tegn

En **tegning** er et SVG-billede af anlægget. Du kan **uploade** en tegning lavet i et andet program (fx Inkscape) eller **tegne** den i systemets egen editor. Begge dele ligger under **Opsætning** (kræver rollen tekniker).

## Tegninger

![Siden Tegninger: upload, listen over tegninger og deres versioner](/manual/tegninger.png)

Siden **Tegninger** er listen over alle tegninger.

- **Upload tegning**: vælg en SVG-fil (højst 5 MB), giv den et **navn** og evt. en **kommentar**. Serveren renser filen (scripts og andet farligt fjernes) og viser en rapport over, hvad der blev fjernet.
- **Versioner**: hver gang du uploader eller gemmer, opstår en ny **version**. **Versioner** viser listen; **Gør aktiv** vælger, hvilken version Overview viser. Du kan derfor forberede en ny version uden at brugerne ser den, og gå tilbage, hvis noget går galt. **Upload ny version** lægger en ny version til en eksisterende tegning.
- **Gør start-tegning**: Overview åbner med denne tegning. **Fjern** start-tegningen, og Overview åbner med den første i listen.
- **Slet**: sletter tegningen med alle versioner og bindinger. Før du bekræfter, viser systemet **hvad det rammer**: antal versioner og bindinger, andre tegninger med en "gå til"-knap hertil (de holder op med at virke), om det er start-tegningen, og hvilke brugere der har adgang til den.

> Bindinger følger tegningens **element-id'er**. Ændrer en ny version et elements id, mister det sin binding; **Bindinger** viser *Forsvundne elementer*, som du kan rydde op i.

![Versioner af en tegning: Gør aktiv, upload ny version og visning af selve SVG'en](/manual/tegninger-versioner.png)

## Tegn

![Tegn: editoren til venstre og det valgte element med navn, symboler og Gem-knapper til højre](/manual/tegn.png)

**Tegn** er en indbygget tegneeditor (SVG-Edit). Brug den til at tegne rør, tanke og tekst, eller til at indsætte færdige **symboler** fra biblioteket.

### Sådan tegner du

1. Vælg en eksisterende tegning (og version) i rullelisterne øverst, eller start en ny (**— Ny tegning —**).
2. Tegn med værktøjerne i editoren: linjer, rektangler, cirkler, tekst, farver og lag.
3. Til højre ser du **Valgt element**. Giv det et **Navn**, hvis det skal være et symbol, der senere kan sættes op med guiden. **Avanceret** viser elementets tekniske **id**.
4. Tryk **Gem kladde** (gemmer en ny version, men viser den ikke endnu) eller **Gem og udgiv** (gemmer og gør den aktiv). En ny tegning skal have et navn.
5. **Slet tegning** fjerner hele tegningen (med samme oversigt over, hvad det rammer).
6. **Bindinger** åbner bindingsiden for tegningen.

Er der ændringer, du ikke har gemt, spørger systemet, før de kasseres.

### Tegnehjælp: gitter, fang og rotation

Under værktøjslinjen i Tegn står rækken **Tegnehjælp**:

- **Vis gitter** viser et net **ovenpå** tegningen (det ændrer ikke tegningen). Linjerne ligger med den valgte **gitterafstand** (5, 10, 20, 25 eller 50 enheder), og hver 5. linje er kraftigere. Gitteret følger zoom og rulning og flugter med linealerne.
- **Fang til gitter** lægger objekter på gitteret: når du flytter, indsætter, duplikerer eller sætter et symbol ind, flyttes objektets **øverste venstre hjørne** til nærmeste gitterpunkt. Kopier havner dermed på samme gitter som originalen, og når du tegner nye figurer, følger de også gitteret.
- **Fang til objekter**: slipper du et objekt tæt på et andet (inden for ca. 8 pixel på skærmen), lægger det sig **kant mod kant** eller **midte mod midte** med det nærmeste objekt. Det virker, når du **flytter** et eksisterende objekt (ikke mens du tegner et nyt), og fangen kan fortrydes med **Ctrl+Z**. Små justeringer med piletasterne fanges ikke.
- **Rotation** sker i **15°-trin**. Hold **Shift** nede, mens du drejer, for at rotere **frit**.

Indstillingerne huskes i din browser.

![Tegn med Tegnehjælp: gitter vist, fang til gitter og fang til objekter slået til](/manual/tegn-gitter.png)

### Farver på de valgte symboler

Vælg et eller flere symboler (hold **Shift** nede, eller træk en ramme), så viser panelet *Valgt element* feltet **Farver** med de farver, markeringen bruger (fx rørenes grå). Tryk på en farve og vælg en ny — så skiftes den farve i **alle** de valgte symboler på én gang, både fyld og streg. De andre farver røres ikke. **Ctrl+Z** fortryder skiftet i ét trin, og ændringen gemmes med **Gem kladde** / **Gem og udgiv**.

> Farven her er symbolets **grundfarve** i tegningen. Har symbolet en animation (fx *Farve* eller *Løbelys*), bestemmer animationen farven på Overview, når den er aktiv.

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

![Erstat med symbol: forslag ud fra delens form, indstillinger og valg om at erstatte alle lignende](/manual/tegn-erstat.png)

> **Retning og akse:** for en **pumpe** og en **kontraventil** aflæser systemet, hvilken vej den tegnede trekant peger, og drejer symbolet, så det peger samme vej. For en **ventil** tegnet som to trekanter aflæses, om den står **vandret eller lodret**, og ventilsymbolet drejes tilsvarende (valgene *Drej symbolet …* i dialogen). For andre symboler er retningen tegnet ind i den gamle del og kan ikke aflæses sikkert — kontrollér og drej dem efter erstatning (**Shift** giver fri rotation). Bindinger på **underelementer** i den gamle del følger ikke med; dialogen advarer, hvis der er nogen.

### Symbolbiblioteket

![Symbolbiblioteket i Tegn, sorteret i kategorier med søgning](/manual/tegn-symboler.png)

Under tegneområdet finder du **symbolbiblioteket**, sorteret i kategorier (*Betjening*, *Proces og visning*, *Rør og VVS*, *Elektrisk*, *Solcelleanlæg*). Søg efter et symbol (fx *bøjning* eller *kontaktor*), og tryk på det for at sætte det ind midt på tegningen; flyt og tilpas det bagefter. Hvert indsat symbol får et **navn** (fx *Pumpe 2*), som du kan ændre.

Et nyindsat symbol skal **sættes op**: vælg symbolet og tryk **Opsæt symbol (6 trin)**. Tegningen gemmes og udgives først (du bliver spurgt), fordi guiden arbejder på den aktive version. Se *Symboler og guiden*.

**Felter med tekst** (*Statusfelt*, *Værdifelt*, *Auto/Manuel*): træk i et sidegreb for at gøre feltet bredere (eller højere), så der er plads til mere tekst — teksten bliver ikke strakt, men beholder sin størrelse (midterstillet tekst følger midten), og et statusfelt beholder sine runde ender. Ret selve teksten ved at dobbeltklikke på den.

**Genveje** (kategorien *Genveje*): knapperne **Gå til Alarmer**, **Gå til Trends** og **Gå til Energi**. Et klik på dem i Overview åbner siden. Alarmknappen viser et mærke med **antallet af aktive alarmer** — orange når de er kvitteret, rødt og blinkende når der er ukvitterede (mærket er skjult uden alarmer). Genvejene skal ikke sættes op. På et driftpanel (kun drifttegningen) åbnes siderne ikke.

**Omskifter med egne positioner**: under *Betjening* kan du skrive positionernes navne (2–8, adskilt med komma, fx *Hånd, 0, Auto*) og indsætte en omskifter med lige det antal positioner.

> Rør og fittings (bøjninger, T-stykker, kryds) er tegnet i samme tykkelse, så de passer sammen. Brug **Løbelys** på rør for at vise strømning. T-stykker og kryds består af selvstændige rør, så hvert rør kan få sit eget løbelys; et ældre T-stykke/kryds (én sti) deles med **Del i rør** i panelet *Valgt element*.
