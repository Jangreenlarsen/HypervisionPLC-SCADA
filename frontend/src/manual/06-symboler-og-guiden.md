# Symboler og guiden i 6 trin

Alle symboler i biblioteket sættes op på samme måde: med **guiden i 6 trin**. Du åbner den fra **Tegn** (vælg symbolet, **Opsæt symbol (6 trin)**) eller fra **Bindinger** (vælg symbolet, **Opsæt symbol**/**Ret symbol**). Intet gemmes, før du trykker **Gem** i trin 6. En rød prik ved et trin betyder, at det har en fejl; serveren kontrollerer hele opsætningen løbende og forklarer præcis, hvad der mangler.

## De seks trin

| Trin | Hvad du gør |
| --- | --- |
| **1. Symbol** | Vælg **betjeningsform** (se nedenfor). Kun de former, der giver mening for symbolet, vises; **Vis alle betjeningsformer** åbner for resten. Knappen *Foreslå ud fra symbolet* henter et forslag ud fra de gamle bindinger |
| **2. Signaler** | Vælg de tags symbolet skriver (**Kommando**) og evt. læser tilbage (**Tilbagemelding**). **Skrives som**: *Sæt* (til/fra eller værdi) eller *Puls* (kort impuls med en fast **hvile**-værdi bagefter). Et valgfrit **Fejlsignal** spærrer betjeningen, når det er Til |
| **3. Kontakter** | Kun for positioner. Et **kontaktdiagram** fortæller, hvad hver position sætter: hver *plan* styrer ét signal, og hver celle er *Til*, *Fra*, *røres ikke* (til/fra) eller en **værdi** (register). Skabeloner A–D laver typiske mønstre: A = tallet 0,1,2 …; B = ét signal pr. position; C = bit-mønster; D = tal omsat til binære signaler |
| **4. Visning** | **Vis**: *PLC'ens position* (tilbagemeldingen — kræver en tilbagemelding på alle signaler i kontaktplanerne) eller *valgt position* (standard for nye symboler). **Tid til at bekræfte**: hvor længe PLC'en må om at følge efter. **Alarm ved afvigelse/fejl**. Her laver du også **logikblokke** og **animationer** |
| **5. Betjening** | **Operatøren skal bekræfte** før der skrives. **Pulslængde** (trykknapper). **Nøglelås**: vælg hvilke positioner der kræver en **kode** (4 cifre) |
| **6. Test og gem** | Se **live** værdier for signalerne og hvilken position PLC'en står på lige nu. En **skriveplan** viser præcis, hvad hver position vil skrive. Advarsler vises; **Gem** er kun muligt uden fejl |

![Trin 1 — Symbol: vælg betjeningsform](/manual/guide-1.png)

![Trin 2 — Signaler: kommando, tilbagemelding og hvordan der skrives](/manual/guide-2.png)

![Trin 3 — Kontakter: hvad hver position sætter (kontaktdiagrammet)](/manual/guide-3.png)

![Trin 4 — Visning: hurtig opsætning, logikblokke og animationer](/manual/guide-4.png)

![Trin 5 — Betjening: bekræftelse og nøglelås](/manual/guide-5.png)

![Trin 6 — Test og gem: live-værdier, fundet position og skriveplan](/manual/guide-6.png)

## Betjeningsformer

![Trin 1 med alle fire betjeningsformer vist: Kun passiv visning, Interaktiv betjening, Trykknap og Setpunkt](/manual/guide-former.png)

| Form | Hvad den gør | Eksempel |
| --- | --- | --- |
| **Kun passiv visning** | Symbolet viser, men betjenes ikke. Har symbolet trin (fx en omskifter), kan du slå *Symbolet har trin* til, så PLC'ens trin vises ud fra tilbagemeldinger | Lampe, tank, rør, 3-vejs ventil styret af én indgang; en omskifter, der kun viser PLC'ens trin |
| **Interaktiv betjening** | 2–8 navngivne positioner; hver sætter et mønster af signaler | Omskifter *Hånd/0/Auto*, ventil *Åben/Lukket*, pumpe *Stop/Start* |
| **Trykknap (puls)** | Et til/fra-tag sættes Til i en fast tid (100–10000 ms), derefter Fra | Start-knap, kvittering |
| **Setpunkt** | Operatøren indtaster en værdi i et skrivbart tal-tag | Ønsket temperatur |

## Kun passiv visning af trin (omskifter, der ikke kan betjenes)

Vil du blot **se**, hvilket trin en omskifter (eller anden positions-symbol) står i, vælg **Kun passiv visning** i trin 1 og sæt hak ved **Symbolet har trin (positioner)**. Så gælder:

- **Trin 2:** kolonnen *Kommando* er **grå** — den bruges ikke, og der skal ikke vælges et skrivbart tag. Vælg kun en **tilbagemelding** til hvert signal (kræves; det kan være et tag, du kun kan læse).
- **Trin 3:** kontaktplanerne beskriver, hvilket mønster tilbagemeldingerne har i hvert trin — præcis som ved betjening. Positionerne navngives som sædvanligt.
- **Trin 4:** symbolet viser altid *PLC'ens position*; der er ingen alarm for afvigelse (der er intet valgt at afvige fra).
- **Trin 5:** intet at betjene — ingen bekræftelse og ingen nøglelås.
- **På Overview** kan symbolet ikke klikkes, og tooltip'en siger *Kun visning — kan ikke betjenes*. Serveren afviser også betjening, hvis nogen forsøger via API'et.

Har symbolet allerede en interaktiv opsætning, tryk **Gør til kun passiv visning (behold trin og kontaktplaner)** under *Interaktiv betjening* i trin 1 — så bliver kommando-tagsene til tilbagemeldinger, og positioner og kontaktplaner bevares.

Skifter du tilbage til *Interaktiv betjening*, skal du vælge kommando-tags igen (tilbagemeldingerne bevares).

## Positioner og kontaktplaner

**Omskifterens tegning følger positionerne:** ændrer du antallet af positioner (eller navnene) på en omskifter, viser guiden i trin 3, at tegningen har andre positioner, og knappen **Gem og tegn omskifteren om**. Den gemmer opsætningen og tegner omskifteren om med de nye positioner, så navnene og grebets vinkler passer. Åbnede du guiden fra *Bindinger*, åbnes *Tegn* med omskifteren valgt, og den tegnes om dér; tegningen gemmes og udgives automatisk.


![Trin 3 for en omskifter med 8 positioner: kontaktplaner for fem signaler og de aktive signaler pr. position](/manual/guide-kontaktplan.png)

**Omskifterens tegning følger positionerne:** giver du en omskifter fra biblioteket flere positioner (eller andre navne) i guiden, end der står rundt om grebet i tegningen, så vælg omskifteren i **Tegn** — der står *Tegningen viser 3 positioner …* med knappen **Tegn omskifteren med N positioner**. Den tegner omskifteren igen med guidens navne (samme navn, placering og opsætning), gemmer og udgiver tegningen (du bliver spurgt), og retter grebets vinkel pr. position, så det peger på navnene.

Et symbol med positioner skal vide, hvilken position PLC'en **står i** (tilbagemelding), og hvad der skal **skrives** for at skifte. Det beskrives i kontaktdiagrammet:

- **Rækker** er *planer*; hver styrer ét signal. **Kolonner** er positioner.
- Eksempel — en 3-trins vælger med ét register `Mode`: position *Hånd* = 0, *0* = 1, *Auto* = 2 (skabelon A).
- Eksempel — en 7-trins vælger, der skriver tallet 1–7 som tre bit på tre coils (skabelon D, "dec → bin").
- To positioner må ikke have samme mønster, ellers kan systemet ikke skille dem ad.

Er en **tilbagemelding** valgt for et signal, læses PLC'ens position derfra; ellers bruges kommandoen. Enten har alle signaler i kontaktplanerne en tilbagemelding, eller ingen — en blanding afvises. *Vis: PLC'ens position* kræver, at alle har. Et puls-signal bruges også til at finde positionen, når det har en tilbagemelding. En position **fundet** i PLC'en vises som en lille tilstand (*bekræftet*, *afventer*, *afvigelse*, *ukendt*).

## Animationer i guiden (trin 4)

![En animation i trin 4: grebet drejer efter symbolets position, med en vinkel pr. position og tegningens vinkler](/manual/guide-animation.png)

Hver animation vælger en **del** af symbolet (*Port A*, *Løbehjul*, *Hele symbolet* …; dele uden et navn fra biblioteket vises efter deres form, fx *Ramme*, *Rektangel 2*, *Cirkel* eller *Tekst "STF"*, med det tekniske id i parentes), en **type** (*Farve, Blink, Synlig, Roterer, Blafrer, Niveau, Gennemsigtighed, Størrelse, Værdi, Drej, Flyt, Løbelys*) og en **kilde**:

- **symbolets position** — farve, vinkel, forskydning osv. vælges **pr. position**
- **et tag** — til/fra eller tal
- **en logikblok** — se nedenfor

**Vippekontakter** (ON/OFF og ON/OFF/ON) har øverst i trin 4 tabellen **Grebets stilling pr. position**: vælg **Op**, **Midt (knop)** eller **Ned** for hver position. *Midt* er den klassiske midterstilling set forfra — grebet peger lige ud mod dig, så kun knoppen ses. Guiden laver selv grebets og knoppens animationer (Drej og Synlig) ud fra tabellen; dine øvrige animationer og en valgt hastighed bevares. Er grebets animationer sat op på en anden måde, står der en note — et valg i tabellen erstatter dem.

**Drej** har en **Hastighed**: *Med det samme*, *Hurtig (0,2 s)*, *Normal (0,4 s)*, *Langsom (1 s)*, *Meget langsom (2 s)* eller *Ekstra langsom (5 s)* — hvor hurtigt delen drejer til den nye vinkel (fx en kontaktkniv eller en vippekontakt). Uden valg drejer den glidende, når den følger positionen, og med det samme, når den følger et tag. Glidende kræver, at delen ikke selv er drejet eller flyttet i tegningen — ellers drejer den med det samme.

**Størrelse** (tal-tag) gør delen større eller mindre om sin egen midte efter værdien: ved **Min** har den *Størrelse ved min* (fx 50 %), ved **Max** *ved max* (fx 150 %), og imellem glidende. Fx pumpens **Pil**, så den vokser med flowet. Uden gyldig værdi vises delen i sin tegnede størrelse.

**Trendgraf** (symbolet *Trendgraf* under *Proces og visning*): viser historikken for **1–4 tags** inde i symbolets ramme på Overview. I trin 4, sektionen **Graf**, vælger du tagsene, **perioden** (15 min, 1 time, 8 timer, 24 timer eller 7 dage), **Kurve** eller **Søjler** (og antal søjler — hver søjle er gennemsnittet i sit tidsrum), og evt. en fast **Y-akse** (tomt = automatisk) og en **titel**. Hvert tag står i sin farve med den seneste værdi — under **Tekst med tagene** vælger du **Placering** (over grafen, under grafen eller skjult), **Størrelse** (lille–meget stor), **Fed** og **Vis seneste værdi**. Et tag fjernes fra grafen med **✕** ud for det (eller ved at vælge *— ingen —*). Grafen opdateres løbende. Tagsene skal **gemme historik** — slå det til i trin 6 (afsnittet *Historik*); ellers står der *Ingen historik i perioden*. Gør symbolet større i Tegn for en større graf: grafen tegnes i den størrelse, symbolet har i tegningen — en større graf får **finere kurver**, **flere diagramlinjer** (vandrette ved runde værdier, lodrette ved runde tider) og mere plads, mens teksten kun vokser lidt. Er teksten med tagene for lang til én linje, deles den på **to linjer** (og gøres mindre, hvis det ikke er nok), så den altid holder sig inden for rammen.

**Pumpen** har et **Løbehjul** og en **Pil**. Guiden foreslår *Roterer* på løbehjulet, så det drejer, når pumpen kører; pilen står stille og viser pumperetningen (også hvis *Roterer* sættes på hele pumpen). Ældre pumper med en trekant opdateres med *Erstat med symbol* — sæt derefter *Roterer* på løbehjulet.

Står flere animationer på samme del, **vinder den nederste** (▲▼ ændrer rækkefølgen). Animationer kan også begrænses til bestemte positioner (**Gælder i**).

### Preview ved animationerne

![Preview ved animationerne: omskifteren tegnet lille, med en knap pr. position, Afspil og Nulstil](/manual/guide-preview.png)

Ved siden af animationerne i trin 4 står et lille **preview** af symbolet. Det viser alle animationerne samtidig, præcis som på Overview (også aktiv/passiv og "gælder i positionerne"), og opdaterer sig, hver gang du ændrer noget.

Under billedet er der en kontrol pr. kilde: **Fra / Til** for et til/fra-tag, en logikblok eller en alarm, en **skyder** for et tal-tag (området følger animationens Min/Max), og en **knap pr. position** for symbolets position. **Afspil** lader alle kilder løbe gennem deres værdier; **Nulstil** stiller dem tilbage. Animationer, der endnu ikke har en kilde, vises ikke, og preview'et siger, hvor mange der mangler.

Preview'et er kun til at se på: det gemmer ikke noget, og der skrives intet til PLC'en.

### Logikblokke (betingelser på flere tags)

![Sektionen Logik i trin 4 med en ny logikblok (AND/OR, NOT og op til 4 indgange)](/manual/guide-logik.png)

Vil du have en animation, der kun er aktiv, når **flere ting er sande** — fx *pumpen kører OG ventilen er åben* — laver du en **logikblok** i trin 4, sektionen **Logik**:

- En blok er **AND** (alle skal være Til) eller **OR** (mindst én Til) over **1–4 indgange**.
- Hver indgang kan have **NOT** (vendt), og hele blokken kan have **NOT på resultatet** (NAND/NOR).
- En indgang kan være et **til/fra-tag**, et **tal-tag** sammenlignet med en grænse (**≥**, **≤**, **=**) eller en **anden blok**. En blok kan kun bruge blokke *over* sig, så der aldrig opstår løkker; på den måde kan du bygge flere niveauer.
- En blok kan også bruge **blokke fra andre symboler på samme tegning** (gruppen *Andre symboler* i valglisten). Så kan du lave blokken ét sted og bruge den mange steder. En blok, andre symboler bruger, kan ikke fjernes, før de henvisninger er fjernet.
- **Ukendt værdi** (fx kommunikationsfejl): en afgørende indgang vinder alligevel (AND med en *Fra* er *Fra*, OR med en *Til* er *Til*). Ellers er resultatet *ukendt*, og delen vises som tegnet.
- Vælg blokken som **kilde** i en animation (*en logikblok*), eller som **Retning fra** for et løbelys.
- Trin 6 viser hver blok og dens værdi lige nu.

## Betjening på tegningen: dialog eller venstre/højre

![Trin 5 for en omskifter med Interaktiv betjening (venstre/højre side) valgt](/manual/guide-interaktiv.png)

Har symbolet **positioner**, vælger du i trin 5 (*Betjening*), hvordan operatøren skifter position:

- **Dialog** (standard): et tryk åbner en boks, hvor positionen vælges.
- **Interaktiv**: tryk på symbolets **venstre side** for at gå til forrige position og på **højre side** for næste — praktisk til en omskifter med mange positioner. Der er ingen dialog; musemarkøren bliver til en venstre/højre-pil over symbolet. I første/sidste position får operatøren besked om, at der ikke er flere (der gås ikke rundt).

Bekræftelse og nøglelås gælder uændret: kræver positionen bekræftelse eller kode, åbnes dialogen med den valgte position, så den kan bekræftes eller låses op. Hurtige tryk, før PLC'en har svaret, tæller videre fra den position, der sidst blev bestilt. Kendes den viste position ikke endnu (ingen tilbagemelding), åbnes dialogen i stedet.

## Nøglelås

![Trin 5 med nøglelås: positionen Til er låst, og koden kræves også for at forlade den](/manual/guide-noeglelaas.png)

I trin 5 kan du vælge de **positioner**, der kræver en **kode** (4 cifre). Operatøren skal indtaste koden, før den position kan vælges; **Koden kræves også for at forlade en låst position** er valgfrit. Koden gemmes kun som hash på serveren, vises aldrig igen og kommer ikke med i backup — efter en gendannelse skal den sættes igen. **Fjern kode** sletter den.

På tegningen står en lille **hængelås** ud for teksten for hver låst position (fx ved *Auto* på en omskifter), og i betjeningsdialogen står 🔒 ved de låste positioner. Hængelåsen ved teksten kommer kun, når symbolet har en tekst med præcis positionens navn.

![Omskifter på Overview: position 4 er låst og har en lille hængelås ved teksten; den stiplede ramme og "PLC: Fra" viser, at PLC'en står i en anden position](/manual/drift-laas.png)

## Hurtig opsætning: 3-vejs ventil

![Hurtig opsætning af en 3-vejs ventil: vælg til/fra-tagget og tryk Opret animationer](/manual/guide-hurtig.png)

De to **3-vejs motorventiler** har en **Hurtig opsætning** øverst i trin 4: vælg det **til/fra-tag**, der styrer ventilen, og tryk **Opret animationer**. Så får du tre farve-animationer: **Til** = AB → A (Port A og AB åbne), **Fra** = AB → B (Port B og AB åbne); **Port AB** er altid åben. Virker også med en indgang, du kun kan læse. Er der intet skrivbart tag valgt, sættes symbolet til *Kun passiv visning*.

Skal ventilen **betjenes** (skifte mellem AB → A og AB → B), vælg **Interaktiv betjening** i trin 1: guiden foreslår to positioner, **AB → A** og **AB → B**, med farve pr. port.

## Ret og fjern en opsætning

**Hurtigvalg af farver:** ved hvert farvefelt står små farveknapper med de farver, der allerede bruges — først animationernes egne, så symbolets tegnede farver og tegningens øvrige. Klik på en for at bruge den; den almindelige farvevælger ved siden af kan stadig bruges til nye farver.

**Grebets vinkler på en omskifter:** bibliotekets omskiftere har navnene tegnet rundt om grebet i faste vinkler (fx 3 positioner: −45°, 0°, 45°; 4 positioner: −67,5°, −22,5°, 22,5°, 67,5°). Vælger du *Drej* pr. position på grebet, er vinklerne udfyldt med tegningens vinkler, og under felterne står **Tegningens vinkler** med en knap *Brug tegningens vinkler*, hvis du har ændret dem. Viser tegningen et andet antal positioner end opsætningen, står der en besked om at tegne omskifteren igen i Tegn.

**Et tag med positionens nummer (pr. værdi):** har symbolet positioner, og styres en animation af *et tag*, kan du sætte hak i **Pr. værdi**. Så læses tagets værdi som positionens nummer (0 = første position, 1 = anden …), og animationen får én værdi pr. position — præcis som med *symbolets position* (fx greb-vinkel −45° / 0° / 45° på en 3-trins omskifter). Brug det, når PLC'en selv har et register med den aktuelle tilstand. Uden hak bruges tagets værdi som et tal mellem Min og Max.

Med hak i *Pr. værdi* vises linjen **Tagets værdi → position**, hvor du afgrænser, hvilke værdier der hører til hver position: en *fra-værdi* pr. position (stigende, standard 0, 1, 2 …). Positionen er den sidste, hvis fra-værdi tagget har nået — fx *Fra ≥ 0, Hånd ≥ 50, Auto ≥ 100*: 0–49 giver Fra, 50–99 Hånd og 100 og derover Auto. Ligger værdien under den første fra-værdi, er der ingen position (delen vises som tegnet). Knappen står derfor aldrig midt imellem to positioner, uanset hvilken værdi tagget har.

En animation kan også styres af **altid til** (i stedet for et tag): så er den altid aktiv — fx en flamme der altid blafrer, eller et løbelys der altid kører. (Ikke for *Niveau*, *Gennemsigtighed*, *Størrelse*, *Drej*, *Flyt* og *Værdi*, som skal have et tal.)

Tal-animationerne — *Niveau*, *Gennemsigtighed*, *Størrelse*, *Drej* og *Flyt* — kan i stedet styres af **en fast værdi**: skriv et tal, og animationen bruger det, som om et tag havde den værdi (området er stadig *Min–Max* i parametrene). Fx *Størrelse* 50 med Min 0 / Max 100 giver halv størrelse mellem de to yderværdier. Det virker både på symbolet og på gruppernes animationer (fx lad alle rør i en gruppe være halvt gennemsigtige). En fast værdi er ikke et tag: den læses ikke fra PLC'en og kan ikke give kommunikationsfejl.

### Alarmer i guiden

**Alarm som kilde:** under *styres af* kan en animation styres af **en alarm**: vælg **er aktiv** (alarmen er i gang) eller **er ukvitteret** (ingen har kvitteret den endnu — også efter den er ophørt), og tagget. Fx lader du en lampe **blinke**, så længe en alarm er ukvitteret, og **farve** den rød, så længe den er aktiv. Har tagget ingen alarm endnu, får du en advarsel.

**Alarmer på symbolets tags (trin 6):** en tabel viser hvert tag, symbolet bruger, med dets alarmopsætning (fx *H 80 · HH 90 bar* eller *når Til*) og status lige nu (*Ingen alarm*, *Aktiv — ukvitteret*, *Aktiv — kvitteret*, *Ophørt — ukvitteret*). Med **Ret alarm** sætter du alarmen direkte her: grænser **HH/H/L/LL** og **Dødbånd** for tal-tags, **Alarm når Til / når Fra** for til/fra-tags, og **Forsinkelse**. Alarmen gælder tagget overalt — det er den samme som under *Tags*.

**Historik (Trends) (trin 6):** under alarmerne ser du, om hvert af symbolets tags **gemmer historik**. Sæt flueben ud for et tag, eller tryk **Gem historik for alle** — så gemmer serveren værdierne fra nu af (højst hvert 10. sekund som standard; intervallet ændres under *Tags*). Historikken gælder tagget overalt. **Vis symbolet i Trends** åbner Trends i en ny fane med alle symbolets kurver.

### Segment-display

![Et 11-segment display i Symboltest: tallet 73 vist på de to højre cifre, de øvrige segmenter står slukket](/manual/display-symboltest.png)

Et **7-segment display** eller **11-segment display** (kategorien *Proces og visning*, eller *Display med egne cifre* i Tegn: 1–16 cifre) viser et tal-tag som lysende segmenter. Vælg **Kun passiv visning** i trin 1; guiden foreslår én animation, **Segmenter**, på *Hele symbolet*. I trin 4 vælger du **tallet** (et tal-tag) og:

- **Decimaler** og **Beregning** (fx `x / 10`) — som under *Værdi*. Tagets egne decimaler bruges, hvis du lader feltet stå tomt.
- **Justering:** højre (standard) eller venstre.
- **Foranstillede nuller:** fylder op med nuller foran tallet (0042), fortegnet står forrest.
- **Tændt** og **Slukket**: farverne på segmenterne.

Decimalpunktet bruger ikke et ciffer: *12,3* på et display med 4 cifre viser `_ 1 2. 3`. Er tallet for langt til cifrene, vises en bindestreg i alle cifre; en ukendt værdi (fx kommunikationsfejl) vises som én bindestreg. Et til/fra-tag vises som 1 eller 0.

**11-segment** kan vise tallene og bogstaverne A, C, D, E, F, G, H, I, J, L, O, P, S, T, U, Y og Z (små bogstaver vises som store). **7-segment** viser tal og de bogstaver, et 7-segment kan lave (fx A, b, C, d, E, F, H, L, n, o, P, r, S, t, U). Andre tegn står slukket.

### Værdi: decimaler, tekst før/efter, beregning og enhed

Animationen **Værdi** skriver taggets værdi i en tekst-del. For et tal-tag har den felterne:

- **Decimaler**: antal decimaler (tallet rundes af). Tom = tagets egen indstilling; 0 = hele tal.
- **Før** og **Efter**: fast tekst foran og efter tallet, fx *Tryk: * og * liter* (skriv selv mellemrummene).
- **Beregning**: simpel matematik på værdien, før den vises — fx *x / 10*, så registerværdien 128 vises som 12,8. Samme regler som på siden *Bindinger* (se *Bindinger og animationer › Tekst: decimaler og beregning*). En ugyldig beregning vises med det samme med rødt.
- **Vis enhed**: tagets enhed (fra *Tags*) efter tallet — før *Efter*-teksten.

Ved siden af står **Lige nu**: taggets aktuelle værdi og hvordan den vil blive vist (fx *128 → Tryk: 12.8 bar*). For et til/fra-tag skriver du i stedet teksten for **Til** og **Fra**.

### Flere animationer på samme del: aktiv/passiv og standard

Hver animation af typen *Farve, Stregfarve, Blink, Synlig, Roterer, Blafrer* eller *Løbelys* har valget **Når den ikke er aktiv**:

- **vis fra-tilstand** (aktiv/ikke aktiv — som før): når betingelsen ikke er opfyldt, viser animationen sin fra-tilstand (fx rørfarven eller farven for *Fra*).
- **gør ingenting (passiv)** (aktiv/passiv): når betingelsen ikke er opfyldt, rører animationen ikke delen — så kan en anden animation bestemme.

Står der flere animationer af samme slags på samme del (fx tre løbelys på samme rør), og er mindst én af dem passiv, vinder den **øverste aktive** (en med *vis fra-tilstand* tæller altid som aktiv). Er ingen aktive, vises delen som tegnet. Ordn dem med ▲▼. *Farve* og *Blafrer* tæller som samme slags (de bestemmer begge fyldfarven).

**+ Standard** tilføjer en animation nederst, der styres af *altid til* — den gælder, når ingen af de passive over den er aktive.

> Eksempel: løbelys på et rør — **rødt** når *Tilstand A* er Til (passiv), **grønt** når *Tilstand B* er Til (passiv), og som **standard** blåt. Er både A og B Til, vises rødt (A står øverst).

**Gem** står på alle seks trin og kan bruges, så snart opsætningen er uden fejl. **Blafrer** får delen til at blafre som en flamme og skifter tilfældigt mellem tre farver, du vælger (standard rød, orange og gul), mens kilden er aktiv — guiden foreslår den på fyrets flamme.

**Ret symbol** åbner guiden med den gemte opsætning. **Fjern konfiguration** sletter den (symbolets gamle bindinger gælder så igen). Et tag, der bruges af et symbol, kan ikke slettes under **Tags**.

### Opsæt flere symboler samlet

Vil du redigere opsætningen for mange symboler på én gang (fx alle rør i en kreds), så markér dem i **Tegn** (hold **Shift** nede, eller træk en ramme) og tryk **Opsæt de valgte samlet**:

1. Tegningen gemmes og udgives først, hvis den har ændringer.
2. Har de valgte **forskellige opsætninger**, vælger du, hvilken der er **udgangspunktet** — dialogen viser hver opsætning og hvilke symboler, der har den. Har de samme opsætning (eller ingen), springes spørgsmålet over.
3. Guiden åbner med udgangspunktet. Ret tag og animationer som for ét symbol.
4. Tryk **Gem i alle**. Alle de valgte får opsætningen (deres tidligere opsætning erstattes). Kunne et symbol ikke få den (fx løbelys på en pumpe uden streger), står det i guiden, og de andre har fået den.

Markerede elementer **uden navn** får udgangspunktets navn med løbenummer (fx *Rør 1_1*). Nøglelåsen og dens kode kopieres ikke.

### Samme opsætning på flere symboler

Skal mange symboler have samme opsætning (fx løbelys på alle rør, bøjninger og T-stykker i en kreds), så sæt **ét** af dem op og tryk **Gem og anvend på flere …** nederst i guiden. Opsætningen gemmes først, og derefter vælger du, hvilke symboler den skal kopieres til:

- **Søg** efter navn eller type, eller brug **Alle af samme type**, **Alle rør og fittings** eller **Vælg viste**.
- Symboler, der allerede er sat op, er mærket *har opsætning* og **springes over**, medmindre du sætter hak i **Overskriv**.
- Tryk **Kopiér til …**. Resultatet viser for hvert symbol, om det blev kopieret, sprunget over eller gav en fejl (fx løbelys på et symbol uden streger).

**Kopiér og indsæt i Tegn:** du kan også gøre det direkte på tegningen. Vælg det symbol, der er sat op, og tryk **Kopiér opsætning** i panelet *Valgt element*. Vælg derefter et eller flere andre symboler (hold **Shift** nede, eller træk en ramme) og tryk **Indsæt opsætning**. Har et af dem allerede en opsætning, spørger systemet, før den overskrives. Har tegningen ændringer, der ikke er gemt, gemmes og udgives den først. Har nogle af de valgte elementer **intet navn**, får de kildens navn med løbenummer — fx *varme pumpe tilgang_1*, *varme pumpe tilgang_2* … i tegningens rækkefølge (numre der allerede er brugt, springes over) — og derefter opsætningen. Du kan omdøbe dem bagefter.

Hvert symbol får sin **egen kopi** — du kan bagefter rette det enkelte symbol i guiden uden at røre de andre. Animationer på en bestemt del af symbolet følger kun med, hvis det andet symbol har en del med samme navn; **nøglelåsen** og dens kode kopieres ikke.


## Symboltest

![Symboltest: vælg et symbol, simulér tags og afprøv animationerne uden PLC](/manual/symboltest.png)

Siden **Symboltest** (rollen tekniker, under **Opsætning**) afprøver et biblioteksymbol uden PLC — med samme animationskode som Overview, så det du ser her, er det du får i tegningen. Intet gemmes.

1. **Vælg symbolet** i gitteret. Findes der en opsætning i biblioteket (fx vippekontakt, 3-vejs ventil, pumpe), er den lagt ind som udgangspunkt.
2. **Tags** (simulerede værdier): opret tags af arten *Til/fra*, *Tal* (med område og enhed) eller *Position* (2–8 positioner, evt. med navne). Skift værdi med knapperne eller skyderen. Flere tags kan bruges samtidig.
3. **Animationer**: tryk *Tilføj animation*, og vælg **del**, **animation** (kun dem delen kan have, også *Løbelys* på rør) og hvilket **tag** den følger. Flere animationer kan ligge på samme symbol, hver med sit tag — fx en pumpe med roterende hjul og en lampe fra to forskellige tags.
4. **Indstillinger**: under hver animation kan du rette parametrene live — ændringerne slår igennem, mens du skriver, og linjen *✓ Anvendt* under symbolet viser tidspunkt og antal anvendte animationer (*Anvend igen* nulstiller og anvender alt forfra) — farver (til/fra, pr. position eller efter grænser), blinkhastighed, flammens farver, vinkler, flytning, niveau, tekster, retnings-tag til løbelys og *Gælder kun i positioner*. Farvefelterne har **bibliotekets palette**: tryk på farveprøven for at vælge en palettefarve, eller brug farvevælgeren/koden.
5. **Afspil og fejltilstande** (pr. tag): *Afspil – Løbende* lader tagget løbe selv gennem sit område (til/fra skifter, et tal løber op og ned, en position går gennem alle positioner; *Runde* er sekunder pr. omgang) — så du ser blink, glidning og løbelys i bevægelse; *Stop afspilning* standser. *Kvalitet* (*God*, *Dårlig*, *Ukendt*, *Kommunikationsfejl* — se *Drift › Datakvalitet*), *Værdi mangler* og *Alarm* viser, hvordan symbolet ser ud ved fejl og alarm: ved *Kommunikationsfejl* beholder symbolet den sidst kendte værdi, ved *Dårlig* og *Ukendt* er der ingen værdi (som i driften), og alle tre tones ned (alarmmarkeringen vises, som i Overview, kun på dele der viser tagget som tekst eller niveau).
6. **Hent bibliotekets opsætning** lægger symbolets guide-opsætning ind (fx vippekontaktens greb pr. position); **Hent symbolets egne** lægger de animationer ind, symbolet selv erklærer. *Nulstil* fjerner animationerne.
7. Skift **baggrund** (lys, mørk, skak) for kontrasten, og brug **størrelsen** til at se detaljer. Under **Farver** kan du klikke på en palettefarve for at se og kopiere koden.
