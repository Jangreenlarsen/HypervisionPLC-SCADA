# Release Notes

---

## v3.1.0 — 2026-10-31 — Bedre rør

- **Bøjningsradius:** vælg et rør og skriv en radius i panelet *Egenskaber*, så får knækkene bløde bøjninger i stedet for skarpe 90°-hjørner. Nye rør får den radius, du senest har brugt.
- Rør sættes nu fast præcis ved symbolets rørender, fx spidsen på en ventil. Tekster ved symbolet (som "A", "B" og "AB") flytter ikke længere punktet.
- Drejer eller spejler du et symbol, går røret ind fra den rigtige side, og røret går altid et stykke lige ud fra symbolet, før det knækker.
- Siden *Symboler* viser de nye, mere præcise automatiske punkter.

## v3.0.0 — 2026-10-31 — Ny tegne-editor

**Tegn** har fået en ny tegne-editor, bygget til SCADA-tegninger:

- Værktøjslinje til venstre med **Fortryd/Gentag**, **Vælg**, **Rør**, **Linje**, **Rektangel**, **Ellipse**, **Sti**, **Frihånd** og **Tekst**.
- **Rør**, der går vandret eller lodret og sidder fast i symbolernes tilslutningspunkter: de følger med, når symbolet flyttes eller drejes.
- Panelet **Egenskaber** (placering, størrelse, drejning, farver, streg, skrift) og panelet **Objekter** (find og vælg elementer, også dem der ligger under andre).
- Knaplinje over det markerede (justér, fordel, rækkefølge, spejl, gruppér, dupliker, slet) og højreklikmenu.
- Træk symboler fra biblioteket ind på tegningen. Ctrl + musehjul zoomer, og mellemrum + træk flytter udsnittet.
- Ny side **Symboler**, hvor tilslutningspunkterne på bibliotekets symboler kan rettes.
- Rettet: **Skalér symmetrisk** virker nu, når du trækker i et hjørne.

Den gamle editor (SVG-Edit) er fjernet. Dine tegninger er uændrede. Værktøjerne stjerne/polygon, formbiblioteket, pipetten, billeder og linealerne findes ikke i den nye editor.

## v2.18.0 — 2026-10-31 — Ny tegne-editor: objekttræ (prøveversion)

- Panelet **Objekter** i den nye tegne-editor viser tegningens elementer med navn og type, forrest øverst. Klik vælger et element, også ét der ligger skjult under et andet. Ctrl- eller Shift-klik vælger flere, og ▲▼ flytter det valgte frem eller tilbage.

## v2.17.0 — 2026-10-30 — Ny tegne-editor: træk symboler ind på tegningen (prøveversion)

- I den nye tegne-editor (`?editor=ny`) kan du trække et symbol fra paletten til højre direkte ind på tegningen. Det lægges, hvor du slipper. Et klik på symbolet indsætter det som før.
- Rettet: rør-værktøjet ramte tilslutningspunkterne forkert efter zoom eller rulning.

## v2.16.0 — 2026-10-30 — Symbol-editor: ret tilslutningspunkterne

- Ny side **Symboler** under Opsætning (tekniker). Her kan du rette et bibliotekssymbols tilslutningspunkter, altså de grønne prikker, som rør sættes fast i: klik for at tilføje, træk for at flytte, højreklik for at fjerne. **Brug de automatiske** går tilbage til standardpunkterne.
- Ændringen gælder symboler, du indsætter fremover. Symboler, der allerede står i en tegning, beholder deres punkter.
- Punkterne er med i backup.

## v2.15.1 — 2026-10-30 — Rettelser i den nye tegne-editor

- Drejning med musen sker nu i 15°-trin igen; hold Shift for fri drejning.
- **Fortryd** og **Gentag** står nu øverst i værktøjslinjen til venstre.

## v2.15.0 — 2026-10-30 — Ny tegne-editor: rør-værktøj (prøveversion)

- Den nye tegne-editor (`?editor=ny`) har værktøjet **Rør** (tast O). Klik for start og knæk; røret går altid vandret eller lodret. Grønne prikker viser symbolernes tilslutningspunkter. Starter eller slutter røret på en prik, følger det med, når symbolet flyttes, ændrer størrelse eller drejes. Dobbeltklik eller Enter slutter røret, Backspace fjerner sidste knæk, og Esc går tilbage til Vælg.
- Nye rør lægges bag de symboler, de forbinder. Røret kan få løbelys som andre elementer: giv det et navn og sæt det op i guiden.

## v2.14.0 — 2026-10-30 — Ny tegne-editor: panel, knaplinje og højreklikmenu (prøveversion)

- I den nye tegne-editor (`?editor=ny`) viser panelet **Egenskaber** placering og størrelse (X, Y, B, H), drejning, hjørner, fyld, streg, tykkelse, synlighed og skrift for det markerede. Skriv en værdi og tryk Enter. Ctrl+Z fortryder.
- Når noget er markeret, vises en knaplinje øverst på tegnefladen: justér, fordel, læg øverst/nederst, spejl, gruppér/opløs, dupliker og slet.
- Højreklik giver en menu med klip, kopiér, indsæt, dupliker, gruppér, rækkefølge og slet.
- Tegnehjælpen (gitter, fang) og hjælpeteksten står nu i bunden af tegnefladen. Drejning sker i 15°-trin, og med Shift drejes frit.

## v2.13.0 — 2026-10-30 — Ny tegne-editor (prøveversion)

- Første del af en ny tegne-editor i **Tegn**. Den kan prøves ved at åbne Tegn med `?editor=ny` i adressen, fx `https://<server>/?editor=ny#draw`. Den har en ny værktøjslinje til venstre og fortryd/zoom i bunden. Zoom med Ctrl + musehjul, og flyt udsnittet med mellemrum eller midterknappen. Den nuværende editor er stadig standard.
- Rettet: **Vis gitter** dækker nu hele tegningen, også i tegninger uden en baggrund.

## v2.12.0 — 2026-10-30 — Tilstandsmærket kan slås fra

- I symbol-guidens trin 4 kan du fjerne hakket ved **Vis tilstandsmærke**. Så vises mærket (✓, …, !, ?) ikke ved symbolet på Overview. Afvigelsen ("PLC: …") og hængelåsen vises stadig.

## v2.11.1 — 2026-10-30 — Rettelse: "Gælder i"

- Skifter du en animations kilde fra et tag til *symbolets position*, gælder de afkrydsninger, du havde sat under *Gælder i*, ikke længere skjult. Animationen virker nu i alle positioner, som feltet viser.

## v2.11.0 — 2026-10-30 — Tegn omskifteren om fra guiden

- Ændrer du antallet af positioner på en omskifter, har guidens trin 3 nu knappen **Gem og tegn omskifteren om**. Fra *Tegn* tegnes omskifteren om med de nye positioner med det samme; fra *Bindinger* åbnes Tegn, og omskifteren tegnes om dér. Grebets vinkler følger med.

## v2.10.2 — 2026-10-30 — Rettelse: eksterne coils og registre

- Et tag fra et **expansion board** eller **RS485** blev behandlet som et tal i symbol-guiden og preview'et, også når det er en coil eller indgang. Nu vises det som Til/Fra. Preview'ets skyder bruger tagets min/max, hvis de er sat.

## v2.10.1 — 2026-10-30 — Rettelse: preview ved animationerne

- Preview'et i symbol-guiden viste et tomt billede for symboler, der står forskudt eller skaleret i tegningen. Det er rettet.

## v2.10.0 — 2026-10-30 — Preview ved animationerne

- I symbol-guidens trin 4 står et lille **preview** af symbolet ved siden af animationerne. Det følger dine indstillinger med det samme: vælg Fra/Til, træk i skyderen, skift position, eller tryk **Afspil**. Intet gemmes, og der skrives ikke til PLC'en.

## v2.9.0 — 2026-10-30 — Segment-display

- Nye symboler: **7-segment display** og **11-segment display** (kategorien *Proces og visning*). I Tegn kan du indsætte et display med **1–16 cifre** (*Display med egne cifre*).
- Displayet viser et tal-tag med animationen **Segmenter**: decimaler, beregning, højre/venstre justering, foranstillede nuller og egne farver. 11-segment viser også de fleste store bogstaver.

## v2.8.1 — 2026-10-30 — Gør et symbol passivt uden at miste opsætningen

- I trin 1 kan et interaktivt symbol gøres til *Kun passiv visning* med ét tryk, så trin og kontaktplaner bevares (kommando-tagsene bliver til tilbagemeldinger).

## v2.8.0 — 2026-10-30 — Kun passiv visning af trin

- En omskifter (eller et andet symbol med trin) kan nu sættes op som **Kun passiv visning**: symbolet viser PLC'ens trin ud fra tilbagemeldinger, uden at der skal vælges en kommando. I trin 2 er *Kommando* grå.
- Et passivt symbol kan ikke betjenes — hverken på Overview eller via API'et. Tooltip: *Kun visning — kan ikke betjenes*.

## v2.7.0 — 2026-10-29 — Tydeligere betjeningsformer og nøglelås på tegningen

- Trin 1 i symbol-guiden hedder nu **Kun passiv visning** og **Interaktiv betjening**.
- Låste positioner (nøglelås) har en lille hængelås ud for deres tekst på tegningen.

## v2.6.1 — 2026-10-29 — Rettelser i symbol-guiden

- At fjerne en position ødelægger ikke længere animationer sat til *Pr. værdi*.
- Fejl om puls og hvileværdi vises nu under trin 2, hvor felterne står.
- Guiden advarer, hvis tilbagemeldingen er samme tag som kommandoen — så kontrollerer *PLC'ens position* ikke anlægget.

## v2.6.0 — 2026-10-29 — Skalér symmetrisk

- I Tegn kan du slå **Skalér symmetrisk** til ved gitter og fang. Så ændres bredde og højde i samme forhold, når du trækker i et hjørne af et symbol. Hold Shift nede for at skalere frit.

## v2.5.2 — 2026-10-29 — Rettet opdateringspakke

- Opdateringspakkerne 2.3.0–2.5.1 indeholdt serverdelen fra versionen før, så siden bad om at genindlæse, selv om det ikke hjalp. Installér denne version.

## v2.5.1 — 2026-10-29 — Tilbagemelding på alle eller ingen signaler

- I symbol-guiden skal enten alle signaler i kontaktplanerne have en tilbagemelding, eller ingen. En blanding kan ikke gemmes. *Vis: PLC'ens position* kræver, at alle har en tilbagemelding.
- Rettet: et puls-signal med tilbagemelding bruges nu til at finde PLC'ens position (før blev positionen altid *Ukendt*).

## v2.5.0 — 2026-10-29 — PLC'ens position kræver tilbagemelding

- I symbol-guiden kan *Vis: PLC'ens position* (trin 4) kun vælges, når mindst ét signal har en tilbagemelding (trin 2). Nye symboler viser som standard den valgte position.
- Eksisterende symboler med *PLC'ens position* uden tilbagemelding virker som før, men skal have en tilbagemelding eller skiftes til *Valgt position*, næste gang de gemmes i guiden.

## v2.4.0 — 2026-10-29 — Omskifter opdaterer sig med det samme

- Tilføjer eller fjerner man positioner (kontaktplaner) på en omskifter i guiden, tegnes omskifteren nu om med det samme, når man trykker Gem. Man skal ikke længere trykke på en knap bagefter.

## v2.3.0 — 2026-10-29 — Skrivbare tags i egen farve

- Tags, som kan skrives fra Overview, vises nu i lilla i tag-listen og i tag-dropdowns, så de er nemme at skelne fra skrivebeskyttede.

## v2.2.0 — 2026-10-27 — Version i topmenuen

- Den installerede version og build står nu yderst til højre i topmenuen (også før login).

## v2.1.2 — 2026-10-27 — Præcis aflæsning i trends

- Zoomer man ind på et lille udsnit af en kurve, viser aflæsningen og y-aksen nu flere decimaler, så værdien følger kurven i stedet for at stå fast (fx 1,2756 i stedet for 1,28), og aksen har ikke længere ens tal.

## v2.1.1 — 2026-10-27 — Rettelse i trends

- Aflæsningsfeltet under en trend-graf kunne pludselig vise et stort tal (tidsstempel) i stedet for kurvens værdi. Det viser nu den rigtige værdi.

## v2.1.0 — 2026-10-27 — Advarsler om tilbagemeldinger

- Symbol-guiden advarer nu, hvis en tilbagemelding (fx et register med et statusord, et anderledes skaleret tag eller en ST-variabel) måske ikke giver de værdier, positionen genkendes ud fra. I testtrinnet vises det også ud fra den aktuelle værdi.

## v2.0.1 — 2026-10-27 — Tydeligere alarmer på tags

- Alarm-opsætningen på et tag forklarer nu forskellen på grænsealarmer (tal) og til/fra-alarm, og advarer med det samme, hvis begge er udfyldt.

## v2.0.0 — 2026-10-27 — Høj prioritet for vigtige eksterne tags

- Eksterne Modbus-tags (fx nødstop-tilbagemelding) kan sættes til **høj prioritet** under Tags, så PLC'en læser dem lige så hurtigt som sine egne. Kræver ny PLC-firmware for at have effekt. Databasen opdateres automatisk ved opdateringen.

## v1.22.2 — 2026-10-27 — Advarsel før sletning

- Sletter du et tag, der vises automatisk i en tegning, spørger SCADA nu først og fortæller hvor.

## v1.22.1 — 2026-10-27 — Intet går tabt i det stille

- Gemmer du en ny tegningsversion, hvor et symbol sat op med guiden er forsvundet, står det nu i rapporten. En gendannelse beholder symbolernes koder og fortæller, hvis et låst symbol mangler en kode.

## v1.22.0 — 2026-10-27 — Tydeligere bindinger

- Binding-editoren siger nu, når et element hører til et symbol, der er sat op med *Opsæt symbol* — simple bindinger dér bruges ikke og kan ikke længere tilføjes. *Gå til tegning* virker fortsat på symboler, der kun viser. Kan et tag ikke slettes, står der præcis hvilket element der bruger det.

## v1.21.12 — 2026-10-26 — Stærkere PIN-spærring

- Gentagne forkerte koder på et PIN-beskyttet symbol giver nu stadig længere spærring (op til en time), også efter genstart. En tekniker kan låse op ved at sætte koden igen.

## v1.21.11 — 2026-10-26 — Adgang følger tegningerne

- Fjernes et tag fra en tegning, holder brugere med adgang til netop den tegning op med at se dets værdier inden for få sekunder — også med siden åben.

## v1.21.10 — 2026-10-26 — Strammere kontrol af tegninger og navne

- Uploadede tegninger kontrolleres grundigere for skjulte henvisninger til eksterne filer, og navne/felter med usynlige linjeskift afvises.

## v1.21.9 — 2026-10-26 — Robust login

- Mange fejlede login-forsøg (fx fra et program, der gætter) kan ikke længere gøre SCADA træg. En adresse med over 20 fejlede logins på 5 minutter må vente, før den kan prøve igen.

## v1.21.8 — 2026-10-26 — Ingen huller i historikken ved kortvarige databasefejl

- Kan trend-databasen et øjeblik ikke tage imod data, gemmes målingerne nu ved næste forsøg i stedet for at gå tabt.

## v1.21.7 — 2026-10-26 — Ingen frosne skærme ved lange trends

- Når nogen åbner en lang trendperiode, eksporterer CSV eller åbner Trends, fortsætter live-værdier, alarmer og betjening nu uden pause. Den timevise oprydning i historikken er gjort langt lettere.

## v1.21.6 — 2026-10-26 — Hurtigere og mere robuste energirapporter

- Lange energirapporter (fx et år pr. dag) beregnes nu på under et sekund og får ikke længere resten af SCADA til at stå stille. En enkelt fejlmåling i en energitæller giver ikke længere et kæmpe falsk forbrug.

## v1.21.5 — 2026-10-26 — Sikrere puls

- Efter en puls prøver SCADA nu igen i op til 10 sekunder at sætte udgangen tilbage, hvis det første forsøg fejler. Lykkes det ikke, kommer der en alarm om at kontrollere udgangen.

## v1.21.4 — 2026-10-26 — Rettelse

- Retter en fejl i v1.21.3's nye rate-limit-diagnostik. Brug denne version i stedet for v1.21.3.

## v1.21.3 — 2026-10-26 — Færre falske "kommunikation tabt"

- Når en PLC kortvarigt beder SCADA om færre kald (rate-limit), beholdes værdierne nu, og der kommer ingen COMM-alarm — kun hvis det varer over et minut. PLC'er-siden viser, hvor ofte det sker. Selve årsagen er rettet i PLC-firmwaren v7.9.68.150.

## v1.21.2 — 2026-10-26 — Rolige kurver uden falske dyk

- Trendkurverne viste dybe dyk, når PLC'en kortvarigt sendte en fejlmåling (fx 0,0). Gennemsnittet i grafen tager nu højde for, hvor længe en værdi stod, så en fejlmåling på få sekunder kun giver et lille udsving. Hullerne i kurverne er perioder uden forbindelse til PLC'en.

## v1.21.1 — 2026-10-26 — Alle kurver ved markøren

- Beskedboksen ved markøren viser nu værdien for alle kurver, også når de er målt på forskellige tidspunkter (før stod der "—").

## v1.21.0 — 2026-10-26 — Middelkurve i tegningens trendgraf

- En trendgraf i tegningen kan nu vise en middelkurve (fx over 24 timer): vælg *Middelkurve* under *Opsæt symbol › Visning*, stiplet ved siden af kurven eller i stedet for den.

## v1.20.0 — 2026-10-26 — Værdier ved markøren i Trends

- Peg på en trendgraf: en beskedboks viser tidspunktet og alle kurvers værdi lige ved markøren.

## v1.19.0 — 2026-10-26 — Skift mellem middel og rå kurve

- På Trends skifter du med tre knapper mellem **Begge** (rå kurve og stiplet middel oven i hinanden), **Middel** og **Rå**.

## v1.18.1 — 2026-10-26 — Middelkurven i kontrastfarve

- Den stiplede middelkurve på Trends har nu altid en anden farve end kurven den er middel af (og end de øvrige kurver i grafen).

## v1.18.0 — 2026-10-26 — Middelkurve som stiplet linje

- På Trends vises middelværdien nu som en stiplet linje ved siden af den rå kurve i samme graf. Vælg tiden under *Middel over*; fjern *Stiplet* for at lade middelkurven erstatte den rå.

## v1.17.0 — 2026-10-26 — Middelværdi i Trends

- Ny vælger **Middel over** på Trends: vis kurverne som glidende middelværdi over fx de seneste 24 timer (eller en tid, du selv vælger). Kun visning — gemte data og CSV er uændrede.

## v1.16.3 — 2026-10-26 — Graferne tegnes efter valg af visning + Nulstil valg

- Efter valg af en visning tegnes graferne nu med det samme (fejlen er genskabt og rettet).
- Ny knap **Nulstil valg** på Trends fjerner alle valgte tags og visningen.

## v1.16.2 — 2026-10-26 — Graf tegnes straks efter valg af visning

- Efter valg af en visning tegnes graferne med det samme — du skal ikke længere vælge en periode først.

## v1.16.1 — 2026-10-26 — Visninger i Trends tegner graferne

- Valg af en gemt visning henter data først og viser graferne på én gang; manglende tags eller fejl forklares nu i stedet for at give tomme grafer.

## v1.16.0 — 2026-10-26 — Gemte trend-visninger

- På **Trends** kan du gemme et udvalg af tags (fx alle tankens temperaturfølere) som en **visning** med et navn (*Tank temp*) og vælge den igen fra en dropdown — tags, grafer og tidsrum kommer frem på én gang. Visningerne er fælles for alle brugere og med i backup.

## v1.15.0 — 2026-10-25 — Se trendgrafer stort

- Tryk på en trendgraf i tegningen for at se den stort, vælg periode, og gå tilbage til tegningen med knappen *Tilbage til tegningen* (eller Esc).

## v1.14.0 — 2026-10-25 — Gradtal for omskifterens positioner

- Når du sætter grebets drejning op pr. position på en omskifter, står tegningens gradtal nu under felterne (og er udfyldt som standard), så du ikke skal gætte inddelingen.

## v1.13.1 — 2026-10-25 — Enklere opsætning ved Pr. værdi

- Feltet *Gælder i* vises ikke længere, når en animation styres af et tag med *Pr. værdi* — det gjaldt symbolets egen position og var forvirrende dér.

## v1.13.0 — 2026-10-25 — Faste positioner fra et tag

- Med *Pr. værdi* kan du nu angive, hvilke tag-værdier der hører til hver position (fx Fra ≥ 0, Hånd ≥ 50, Auto ≥ 100). En omskifter står derfor altid i en af sine positioner — aldrig midt imellem — uanset tagets værdi.

## v1.12.1 — 2026-10-25 — Tydeligere ved afvist PLC-login

- Afviser PLC'en SCADA's bruger (forkert adgangskode, eller brugeren findes ikke på PLC'en), siger beskeden nu præcis det og hvad du skal gøre. SCADA prøver kun at logge ind igen hvert minut, så PLC'en ikke fyldes med login-fejl.

## v1.12.0 — 2026-10-25 — Animation pr. værdi fra et tag

- Styres en animation af et tag, hvis værdi er positionens nummer (0, 1, 2 …), kan du nu sætte hak i **Pr. værdi** — så får hver position sin egen vinkel/farve osv., ligesom med *symbolets position*.

## v1.11.1 — 2026-10-25 — Skift frem og tilbage mellem betjeningsformer

- I Opsæt symbol kan du nu skifte tilbage, fx fra *Positioner* til *Kun visning* — før forsvandt valget fra listen.

## v1.11.0 — 2026-10-25 — Skift position med venstre/højre-tryk

- Symboler med positioner (fx en omskifter) kan nu sættes op til at blive betjent **direkte på tegningen**: tryk på venstre side for forrige position og højre side for næste. Vælges under *Betjening* i Opsæt symbol; dialogen er stadig standard.

## v1.10.0 — 2026-10-25 — Beskeder hopper ikke længere rundt

- Beskeder på Overview (PLC-fejl, forbindelse, deaktiveret tegning m.m.) står nu i en lille pille til højre i værktøjslinjen i stedet for over tegningen. Tegningen står stille, når beskeder kommer og går. Tryk på pillen for at se dem alle.

## v1.9.2 — 2026-10-25 — Betjening af ST-variabler bundet til registre

- Symboler og tags på ST-variabler, der i PLC'en er bundet til et register (input/begge), kan nu betjenes: SCADA skriver automatisk registret, variablen læser fra. Før fik du fejlen "bound as INPUT from HR …".

## v1.9.1 — 2026-10-25 — Tydelig fejl når et tag i brug ikke kan slettes

- Prøver du at slette et tag, der er i brug, står fejlen nu lige under tagget og nævner hvilke tegninger der bruger det.

## v1.9.0 — 2026-10-25 — Kvittér PLC-fejl på Overview

- PLC-fejl øverst på Overview kan **kvitteres**, så de ikke fylder hele tiden. Er PLC'en i orden igen og fejler senere, vises den nye fejl. Kvitteringen gælder kun din browser.

## v1.8.3 — 2026-10-25 — Smallere Opsæt symbol

- Opsæt symbol-guiden er gjort smallere, så den passer i visningen uden at man skal rulle sidelæns.

## v1.8.2 — 2026-10-25 — Rettelse: skift af IP-adresse fra web

- Rettet en fejl, der gjorde, at **ingen** netværksændring (fast IP, DHCP …) kunne anvendes under System › Konfiguration — siden viste "Ugyldigt input — fallback_after: ukendt felt". Det virker nu igen.

## v1.8.1 — 2026-10-25 — Fjern signaler i Opsæt symbol

- I trin 2 kan alle signaler nu fjernes, også det sidste. Har signalet en kontaktplan med indhold, bliver du spurgt først.

## v1.8.0 — 2026-10-25 — Genstart fra web

- Under **System › Konfiguration › Genstart** kan admin genstarte SCADA-tjenesten eller hele maskinen — fx efter et skift til fast IP-adresse. Siden venter og genindlæser sig selv, når serveren er tilbage.
- Kræver, at maskinen opdateres med denne version én gang (installationen sætter hjælperen op).

## v1.7.0 — 2026-10-24 — Skriv til ST-variabler

- Tags på ST-variabler og GLOBAL_VAR kan nu gøres **skrivbare** og betjenes fra Overview (setpunkt, knapper, positioner, ugeprogrammer). Kræver at PLC'en er opdateret til firmware **v7.9.68.141** eller nyere — ellers får du en tydelig besked.
- PLC'en viser nu også variabelnavne op til 31 tegn (før 15).

## v1.6.1 — 2026-10-24 — Fulde tag-navne

- Tag-navne skæres ikke længere over i tag-valget i Opsæt symbol og gruppernes animationer.

## v1.6.0 — 2026-10-24 — Deaktivér en tegning

- På siden **Tegninger** kan du **deaktivere** en tegning: den bliver offline — grå på Overview, uden live-værdier og uden betjening. Tags, som kun den bruger, holder op med at blive pollet. **Alarmer, trend, energi og ugeprogrammer påvirkes ikke** (tags med dem pollas stadig). *Aktivér* henter tegningen online igen.

## v1.5.0 — 2026-10-24 — Hurtigvalg af brugte farver

- Ved farvefelterne i **Opsæt symbol** kan du nu vælge blandt de farver, symbolet og tegningen allerede bruger, med ét klik — så farverne holdes ens.

## v1.4.1 — 2026-10-24 — Stabilere PLC-kommunikation

- Rammes ét enkelt kald til PLC'en af en timeout, mister kun de tags, kaldet dækker, forbindelsen — resten af PLC'ens værdier bliver ved med at opdatere. Tidligere blev alle tags markeret som "kommunikation tabt".
- PLC-siden viser nu hvilket kald der fejler, og hvilke kald der er langsomst, så en vedvarende årsag kan findes.

## v1.4.0 — 2026-10-24 — Fast værdi som kilde

- *Niveau*, *Gennemsigtighed*, *Størrelse*, *Drej* og *Flyt* kan nu styres af **en fast værdi** i stedet for et tag — skriv bare et tal. Virker på symboler og på gruppernes animationer.

## v1.3.0 — 2026-10-24 — Fjern opsætning fra flere symboler

- I **Opsæt de valgte samlet** er der nu en knap, der fjerner opsætningen fra alle de valgte symboler på én gang.

## v1.2.0 — 2026-10-23 — Animation til alle i gruppen på én gang

- I **Animationer for gruppen** kan du nu vælge fanen **Alle medlemmer** og sætte samme animation op på alle gruppens symboler i ét hug (tilføje eller erstatte). Symboler, hvor animationen ikke kan bruges, kan springes over, og du får en liste over dem.

## v1.1.0 — 2026-10-23 — Se symbolets grupper i Opsæt symbol

- I **Opsæt symbol** kan du nu se, hvilke grupper symbolet er medlem af, lige under overskriften.

## v1.0.1 — 2026-10-23 — Intern oprydning

- Ingen synlige ændringer: en intern typefejl i Trends er rettet.

## v1.0.0 — 2026-10-23 — Version 1.0.0 (databaseudvidelse til symbolgrupper)

- Samme funktioner som 0.131.4. Versionsnummeret er hævet, fordi opdateringen udvider databasen (nye tabeller til symbolgrupper) — tag en backup, før du opdaterer fra en ældre version.

## v0.131.4 — 2026-10-23 — Symbolgrupper: flere rettelser
- Dialogen til gruppens animationer kan ikke længere blande to symbolers indhold, hvis du skifter hurtigt, og Escape lukker den.
- Gruppenavne skelner ikke mellem store og små bogstaver. Funktionsgrupper tæller altid før udvalg, og det fremgår af tooltippet.

## v0.131.3 — 2026-10-23 — Rettelse: flere kilder på samme del

- Rettet en fejl fra v0.131.2: når flere tags (fx to pumper) styrer samme del, vinder nu den sidste *aktive* igen, så et fælles rør med løbelys fra to pumper kører, så snart én af dem kører.
- Flytter du et forsvundet gruppemedlem til et nyt element, følger animationer på dets dele med, og du får besked om det, der ikke kunne flyttes.

## v0.131.2 — 2026-10-23 — Sikrere og tydeligere symbolgrupper

- Flere kan redigere grupper uden at overskrive hinandens ændringer.
- Gruppernes rækkefølge kan ses og ændres med ▲▼; den afgør hvem der vinder, når flere animationer rammer samme del. Når to animationer fra forskellige tags rammer samme del, vinder nu altid den sidste — ikke den, hvis tag sidst ændrede sig.
- Du får en advarsel, når en gruppes animation overlapper med symbolets egen eller en anden gruppes.
- Forsvundne gruppemedlemmer kan flyttes til det nye element (med animationerne) eller fjernes direkte i Bindinger.

## v0.131.1 — 2026-10-23 — Rettelser til symbolgrupper

- Et nyt element i tegningen kan ikke længere overtage et slettet gruppemedlems id og dets animationer.
- En logikblok, som en gruppe bruger, kan ikke fjernes ved en fejl — du får besked om hvilken gruppe der bruger den.

## v0.131.0 — 2026-10-23 — Animationer på grupper

- En gruppe af symboler (fx *Fyr uden akku-tank*) kan nu få **egne animationer** på sine symboler. De gælder ud over symbolernes egne, og et rør kan være med i flere grupper med hver sin opsætning.
- Hver gruppe har en farve. Når du redigerer et symbol, vises animationer fra grupper skrivebeskyttet i gruppens farve, så du kan se, hvad du ikke skal røre.
- Opdateringen opretter en ny tabel i databasen (skema 13); ældre backups kan stadig gendannes.

## v0.130.0 — 2026-10-23 — Grupper af symboler

- I **Tegn** kan du gemme de valgte symboler som en navngiven gruppe (fx *Fyr uden akku-tank*) og markere dem alle igen med ét klik. Et symbol kan være med i flere grupper.
- På **Bindinger** kan du vælge en gruppe for kun at se dens symboler.
- Grupperne er med i backup.
- Opdateringen opretter to nye tabeller i databasen; ældre backups kan stadig gendannes.

## v0.129.1 — 2026-10-23 — Rullepaneler i Tegn

- Rullepanelerne på tegnefladen i Tegn er nu altid synlige.

## v0.129.0 — 2026-10-23 — Coil på animationer der krævede et register

- I **Opsæt symbol › Animationer** kan du nu vælge et coil (til/fra-tag) som kilde til Niveau, Gennemsigtighed og Størrelse. Coil'et står som 0 (Fra) og 100 (Til).

## v0.128.0 — 2026-10-23 — Flyt Opsæt symbol-dialogen

- I **Opsæt symbol** kan du trække i dialogens overskrift for at flytte den rundt, fx så du kan se tegningen bagved.

## v0.127.0 — 2026-10-23 — Tydeligere markering i Bindinger

- Vælger du et symbol eller bundet element i listen, markeres det på tegningen med en lysegrøn, gennemsigtig boks.

## v0.126.1 — 2026-10-23 — Animationer virker på iPad/iPhone

- Animationerne (rotation, blink, løbelys, flamme, alarmer) vises nu også, når enheden har *Reducer bevægelse* slået til.

## v0.126.0 — 2026-10-23 — Driftpanel: tegningen fylder hele skærmen

- Driftpanelet har ikke længere en bred menu i siden. **Log ud** (og evt. valg af tegning) ligger som små knapper øverst til venstre oven på tegningen, så tegningen får hele skærmen.

## v0.125.1 — 2026-10-22 — Netværk: opdaterer sig selv

- Netværkssystemet og DHCP-klienten registreres nu løbende (hvert halve minut). Installerer du fx `dhcpcd-base` på maskinen, kan DHCP vælges på siden kort efter — uden at køre nogen installation.

## v0.125.0 — 2026-10-22 — Netværksopsætning virker også på Debian/Ubuntu-servere og ESXi-VM'er

- Netværk kan nu sættes fra **System › Konfiguration** også på maskiner med **ifupdown** (`/etc/network/interfaces`) — typisk Debian/Ubuntu-servere og virtuelle maskiner — ikke kun med NetworkManager.
- Samme sikkerhed: ændringen prøves først uden at røre filen, du bekræfter inden for 90 sekunder, og ellers vender den gamle opsætning tilbage. Filen får en sikkerhedskopi.
- Mangler maskinen en DHCP-klient, er kun *Fast IP* valgbar (siden siger det). Siden viser nu præcist, hvorfor netværksændring ikke er aktiveret.
- Efter opdateringen kører installationen automatisk og finder netværkssystemet.

## v0.124.0 — 2026-10-22 — Oprydning ved fuld disk

- Nyt kommandolinjeværktøj **`scada-maint`** (på maskinen, som root) til at rydde logfiler, gamle backups og gammel historik, når disken er ved at blive fuld — også uden at websiden kan åbnes. Det viser som standard kun, hvad der ville ske (**tørkørsel**); `--yes` udfører. `scada-maint emergency` går trin for trin og stopper, når der er plads nok. Tags, brugere og tegninger røres aldrig.
- Konfiguration-siden advarer, når der er lidt ledig plads.

## v0.123.0 — 2026-10-22 — Konfiguration: DHCP-vagt, reserve-IP og testvejledning

- Ny netværkstilstand **DHCP, fast IP først efter N fejl**: DHCP forsøges hele tiden; svarer routeren ikke i N kontroller (à 30 s), tager maskinen en fast reserve-IP i brug, og slipper den igen, når DHCP svarer. Siden viser vagtens status.
- Siden fortæller nu præcist, **hvorfor** netværksændring ikke er aktiveret (NetworkManager mangler, eller `install.sh` er ikke kørt).
- Ny testvejledning til første prøve på en rigtig Pi: `docs/TEST_PI.md`.

## v0.122.0 — 2026-10-22 — Konfiguration: flyt trend-databasen

- Under **System › Konfiguration** kan trend-historikken nu flyttes til en **anden disk** (fx en USB-SSD) for at skåne SD-kortet — mens SCADA'en kører. Historikken kopieres og kontrolleres, før den nye database tages i brug; den gamle fil bliver liggende (`trends.db.moved`).
- Mangler disken ved en genstart, starter SCADA'en alligevel (tom database i datamappen) og viser en advarsel.
- Kræver, at mappen på disken oprettes én gang med `sudo install -d -o scada -g scada -m 0750 /mnt/ssd/scada`, og at `sh deploy/install.sh` er kørt (opdaterer tjenestens skriverettigheder).

## v0.121.0 — 2026-10-22 — Konfiguration: netværk

- Under **System › Konfiguration** kan netværket nu sættes: **DHCP**, **fast IP** (IP, subnet, gateway, DNS) eller **DHCP + fast IP som sekundær**, samt værtsnavn.
- Efter **Anvend** har du 90 sekunder til at åbne siden på den nye adresse og trykke **Bekræft** — ellers gendannes den gamle opsætning automatisk, så du ikke låser dig ude.
- Kræver at `sh deploy/install.sh` køres som administrator én gang (installerer hjælperen) og NetworkManager på maskinen.

## v0.120.0 — 2026-10-22 — Konfiguration: trend-indstillinger

- Under **System › Konfiguration** kan du nu ændre **opbevaring af historik**, **skriveinterval** (skån SD-kortet med et længere interval) og **opbevaring af energi**. Ændringerne gælder straks og huskes efter genstart.

## v0.119.0 — 2026-10-22 — System › Konfiguration

- Ny side **System › Konfiguration** (admin): hvor data ligger, filstørrelser og ledig plads, **hvor meget der skrives til disken** (rækker og skrivninger, overslag pr. døgn) og netværksstatus (IP, gateway, DNS). Siden viser kun; indstilling af netværk og flytning af data kommer senere.

## v0.118.1 — 2026-10-22 — Trends: færre falske huller

- *Udfyld huller* og *Hul i data* udfyldte/markerede normale pauser (en stabil værdi gemmes kun hvert 5. minut). Nu tæller kun pauser over 15 minutter som huller; perioder hvor PLC'en ikke havde forbindelse udfyldes stadig.

## v0.118.0 — 2026-10-22 — Trends: fjern graf

- Hver graf i Trends har et **kryds** i øverste højre hjørne, som fjerner grafen fra visningen (tagsene fravælges og kan vælges igen i listen).

## v0.117.0 — 2026-10-22 — Trends: graf i fuld størrelse

- **Dobbeltklik** på en graf i Trends viser den alene i fuld størrelse. Dobbeltklik igen eller tryk Esc for at gå tilbage. Dobbeltklik zoomer ikke længere ud; brug **Nulstil visning**.

## v0.116.0 — 2026-10-22 — Trends: udfyld huller og datoer

- Nyt tilvalg **Udfyld huller (blinker)**: hvor data mangler (fx PLC uden forbindelse), tegnes en kunstig, interpoleret linje, som **blinker**, så den ikke forveksles med målte værdier. Det er kun visning — de gemte data og CSV ændres ikke. Før første og efter sidste måling udfyldes intet.
- Grafen viser nu **datoen** ved hvert døgnskift.

## v0.115.2 — 2026-10-22 — Trends: grafer med navn

- Graferne i Trends hedder nu det samme som kurverne i dem (tagnavn, fx "Kedel temp, Kedel tryk (°C)") i stedet for kun enheden.

## v0.115.1 — 2026-10-22 — Trends: uregelmæssigheder som overlay

- Når **Analysér data** er slået til, er der en knap **Uregelmæssigheder** i værktøjslinjen, som viser oversigten som et vindue oven på skærmen. Det tager ikke plads fra graferne og lukkes med ×.

## v0.115.0 — 2026-10-22 — Trends: skillelinjer

- Ny vælger **Skillelinjer** i Trends: *Fra*, *Pr. time* eller *Pr. dag* viser stiplede lodrette linjer ved hele timer eller dage i alle grafer. Ved meget lange perioder vises timelinjer ikke (for mange). Valget huskes.

## v0.114.1 — 2026-10-22 — Trends: mere plads til graferne

- Oversigten over **uregelmæssigheder** står nu i venstre side under tag-listen i stedet for under graferne, så graferne kan blive højere.

## v0.114.0 — 2026-10-22 — Trends: vælg graf pr. tag

- Ud for hvert valgt tag i Trends kan du vælge **Graf 1–8**, så du selv bestemmer, hvilke kurver der vises sammen. **Auto** giver som før én graf pr. enhed. Valget huskes.
- Kurver med forskellige enheder i samme graf deler y-akse.

## v0.113.1 — 2026-10-22 — Trends: roligere visning

- Aflæsningerne under graferne (tid og værdier) hopper ikke længere rundt, når musen flyttes hen over en graf.

## v0.113.0 — 2026-10-22 — Trends: lås graferne sammen

- Ny knap **Lås graferne sammen** i Trends: zoom og scroll i én graf flytter alle graferne til samme tidsudsnit.
- Ny knap **Nulstil visning**: zoomer alle grafer ud til hele den valgte periode.

## v0.112.0 — 2026-10-22 — Trends: scroll i tid

- I Trends kan du nu **scrolle i tid**, når du har zoomet ind: brug musehjulet over grafen, eller træk med Shift nede. Dobbeltklik zoomer ud.

## v0.111.4 — 2026-10-20 — Datakvalitet forklaret

- Manualen forklarer nu **datakvalitet**: *God*, *Kommunikationsfejl* (sidst kendte værdi), *Dårlig* (kan ikke læses) og *Ukendt* (endnu ikke modtaget), at symbolet tones ned, og at alarmer fastholdes, betjening afvises og Trends får et hul.
- I Symboltest har *Dårlig* og *Ukendt* nu ingen værdi, som i driften.

## v0.111.3 — 2026-10-20 — Størrelse, Gennemsigtighed og Niveau på til/fra

- En ny animation af typen **Størrelse**, **Gennemsigtighed** eller **Niveau** på et til/fra-signal gør nu noget synligt: Fra = mindst, Til = størst (før kunne forskellen ikke ses). Gælder symbolguiden og Symboltest. Allerede gemte opsætninger ændres ikke.
- I Symboltest følger området tagget, og et symbol der bliver større, vokser ikke længere ud af billedet.

## v0.111.2 — 2026-10-20 — Symboltest: gennemgang

- Hele Symboltest er gennemgået automatisk (alle symboler, dele, animationer og tag-arter) — ingen fejl fundet i motoren.
- En **ugyldig farvekode** afvises nu (feltet bliver rødt og viser den gældende farve); farvenavne som `red` virker.
- **Advarsel**, hvis to animationer af samme type ligger på samme del (den nederste vinder).

## v0.111.1 — 2026-10-20 — Symboltest: rettelser

- **Tekst** viser nu *Tekst ved Til/Fra* i stedet for 0/1.
- **Farve pr. position** giver hver position sin egen farve fra start, så ændringen kan ses.
- Indstillingerne slår igennem **mens du skriver**, og siden viser *✓ Anvendt* med tidspunkt og antal animationer. *Anvend igen* nulstiller og anvender alt forfra.

## v0.111.0 — 2026-10-20 — Symboltest: afspilning og fejltilstande

- **Afspil**: lad et tag løbe selv gennem sit område — til/fra skifter, et tal løber op og ned, en position går gennem alle positioner — så du kan se blink, glidning og løbelys i bevægelse. Rundetiden vælges (1–60 s).
- **Fejltilstande**: sæt et tags *kvalitet* (dårlig, ukendt, kommunikationsfejl), *værdi mangler* eller *alarm* (ukvitteret/kvitteret) og se, hvordan symbolet opfører sig.

## v0.110.0 — 2026-10-20 — Symboltest: avanceret

- **Flere tags og flere animationer på én gang**: opret simulerede tags (til/fra, tal, position) og læg animationer på delene — hver animation følger sit tag. Se fx en pumpe med roterende hjul og grøn lampe fra forskellige tags.
- **Ret indstillingerne live**: farver, grænser, vinkler, afstande, hastighed, tekster og *gælder i positionerne*.
- **Farvepaletten kan nu bruges**: i alle farvefelter vælger du direkte i bibliotekets palette, og i *Farver* kan koden kopieres.
- *Hent bibliotekets opsætning* og *Hent symbolets egne* lægger symbolets egne animationer ind som udgangspunkt.
- Rettet: *Hele symbolet* animerer nu symbolet selv (før kunne fx en farve ikke ses).

## v0.109.0 — 2026-10-20 — Trends: navne på kurverne

- Hver kurve i Trends-graferne har nu sit **navn ved højre kant**. Ligger flere kurver tæt sammen, spredes navnene, så de kan læses, og en **pil** peger fra navnet til den rigtige kurve.

## v0.108.0 — 2026-10-19 — Trends: kun opsatte trends for operatører

- **Viewer, operatør og driftpanel** kan ikke længere søge efter eller vælge tags frit i Trends. De ser kun de trends, der er sat op i deres tegninger (symboler og trendgrafer), og vælger mellem dem under *Symbol*. Tekniker og admin kan stadig vælge alle tags.

## v0.107.0 — 2026-10-19 — Trends: skjul ringene

- Under **Analysér data** kan du fjerne fluebenet ved **Vis ringe**, så cirklerne og stregerne i graferne skjules. Listen med fund og procenterne vises stadig.

## v0.106.0 — 2026-10-19 — Trends: fastfrosset efter tid

- **Analysér data** har valget **Fastfrosset efter** (1 time til 7 døgn, eller Aldrig). En værdi regnes først for fastfrosset, når den har stået uændret så længe — fx 6 timer som standard. En rolig temperaturføler ringes dermed ikke om over lange perioder, mens huller i data stadig markeres.

## v0.105.0 — 2026-10-19 — Driftpanel: Trends og alarmer

- På et **driftpanel** åbner knapperne *Gå til Alarmer* og *Gå til Trends* i tegningen nu siderne (uden menu, med Tilbage). Panelet kan **kvittere alarmer** og se trends for de tags, tegningen indeholder.

## v0.104.0 — 2026-10-19 — Trends: procent uregelmæssigheder

- **Analysér data** viser nu, hvor mange **procent af punkterne** der har uregelmæssigheder, for hver kurve og samlet for alle tal-kurver.

## v0.103.0 — 2026-10-19 — Symboltest kan mere

- **Positioner**: vælg *Position* under "Tag er" og afprøv farve, drejning, flytning, synlighed m.m. pr. position (2–8).
- **Løbelys** kan afprøves på rør og streger.
- Listen over animationer viser kun dem, den valgte del kan have.
- Ny sektion **Som i guiden**: symbolets egen opsætning fra biblioteket (fx vippekontaktens greb i Op/Midt/Ned, 3-vejs ventilens porte) med en knap pr. position.

## v0.102.0 — 2026-10-19 — Trends: spikes udfyldes

- **Skjul spikes** i Trends udfylder nu spikes med interpolerede værdier, så kurven er sammenhængende i stedet for at få huller. Gemte data og CSV ændres ikke.

## v0.101.0 — 2026-10-19 — Trends: flere kurver og dataanalyse

- Du kan nu vise **op til 12 kurver** ad gangen i Trends (før 7). Kurve 8-12 har samme farver som de første, men stiplet linje.
- Nyt tilvalg **Analysér data**: finder spikes, urealistiske spring, fastfrosne værdier og huller og sætter en ring om dem. **Skjul spikes** fjerner enkeltstående spikes fra visningen; de gemte data og CSV ændres ikke.

## v0.100.0 — 2026-10-19 — Symboltest

- Ny side **Symboltest** (tekniker, under Opsætning): afprøv ethvert biblioteksymbol uden PLC. Vælg en del og en animation, og skift mellem Til/Fra eller en skyder for at se farve, blink, drejning, flytning og niveau. Vælg lys, mørk eller skak baggrund. Intet gemmes.

## v0.99.0 — 2026-10-19 — Symbolkvalitet

- **Ventiler, motorer, lamper, varmeveksler, filter og radiator har nu navngivne dele** (fx hus, spindel, håndhjul, glas, spole), så guiden kan animere dem hver for sig. Udseendet er uændret. Symboler der allerede står i en tegning får delene ved *Erstat med symbol …*.
- Alle symbolfarver er samlet i én palette, så nye symboler holder samme stil.

## v0.98.0 — 2026-10-19 — Vippekontaktens greb pr. position

- Guidens trin 4 har nu **Grebets stilling pr. position** for vippekontakterne: vælg **Op**, **Midt (knop)** eller **Ned** for hver position, og guiden laver selv animationerne. Det virker uanset antal positioner og signaler.
- **ON/OFF** og **ON/OFF/ON** er nu bygget ens (greb og knop). Nyindsatte ON/OFF-kontakter har knoppen; ældre kan opgraderes med *Erstat med symbol …*.

## v0.97.1 — 2026-10-19 — Rettet: Drej og Flyt med til/fra-tag

- Valgte man **Drej** eller **Flyt** før tagget, og var tagget til/fra, fik animationen tal-indstillinger, så delen ikke nåede sin slutstilling. Nu får den de rigtige indstillinger uanset rækkefølgen.

## v0.97.0 — 2026-10-19 — Hastighed på Drej

- Animationen **Drej** har nu en **hastighed** — fra *Med det samme* til *Ekstra langsom (5 s)* — fx for kontaktknive og vippekontakter.

## v0.96.1 — 2026-10-19 — Vippekontakter op og ned

- De klassiske **vippekontakter** vipper nu **op og ned**: ON/OFF er op ved ON og ned ved OFF; ON/OFF/ON er op ved ON 1, ned ved ON 2 og står lige ud (en knop) ved OFF. Guiden foreslår hele opsætningen — vælg blot tagget.

## v0.96.0 — 2026-10-19 — Klassiske vippekontakter

- Nye symboler **Vippekontakt ON/OFF** og **Vippekontakt ON/OFF/ON** (klassisk model med greb og møtrik) under *Betjening*. De virker som omskifteren: klik for at vælge position, og grebet vipper til den aktive.

## v0.95.1 — 2026-10-19 — Pumpen uden prik

- Prikken midt i **pumpens** løbehjul er fjernet. Pumper, der allerede står i tegningerne, opdateres med *Erstat med symbol*.

## v0.95.0 — 2026-10-19 — Bedre trendgraf

- **Trendgrafen** følger symbolets størrelse: en større graf får finere kurver og flere diagramlinjer — teksten bliver ikke strakt.
- **Diagramlinjer** ved runde værdier og tider, med tal og klokkeslæt.
- Teksten med tagene deles på **to linjer**, så den aldrig går uden for rammen.

## v0.94.0 — 2026-10-19 — Kontakter med 2 og 3 poler

- Nye symboler **Kontakt 2-polet** og **Kontakt 3-polet** (El): knivene lukker synligt, når tagget er Til. Guiden foreslår animationen — vælg blot tagget.
- Rettet: når man valgte tagget til et forslag fra symbolbiblioteket, blev forslagets indstillinger nulstillet.

## v0.93.0 — 2026-10-19 — Trendgrafens tekst

- Teksten med tagenes navne i **Trendgraf** kan nu placeres **over** eller **under** grafen eller skjules, og have større/mindre skrift, fed og med/uden seneste værdi.
- Et tag fjernes fra grafen med **✕** i guiden.

## v0.92.0 — 2026-10-19 — Tegningens størrelse og danske tegneværktøjer

- **Tegningens størrelse** kan ændres i Tegn (knappen **Størrelse** øverst): faste valg som Full HD, egen bredde/højde, eller **Tilpas til indholdet**.
- **Tegne-editoren er nu på dansk** — værktøjer, felter og genveje — og en **hjælpelinje** over tegningen fortæller, hvordan det valgte værktøj bruges.
- Forbindelsesværktøjet er fjernet (dets forbindelser holdt ikke, når tegningen blev gemt).

## v0.91.1 — 2026-10-19 — Rettet: omskifter med flere positioner

- Får en omskifter flere positioner i guiden, end tegningen viser, kan **Tegn** nu tegne den igen med de rigtige positioner (knappen **Tegn omskifteren med N positioner**) — og grebet peger på dem.

## v0.91.0 — 2026-10-19 — Trendgraf i tegningen

- Nyt symbol **Trendgraf**: viser historikken for 1–4 tags direkte i tegningen — som **kurve** eller **søjlediagram** — over 15 minutter til 7 dage. Opsættes i symbolguiden (trin 4, *Graf*) og opdateres løbende.

## v0.90.1 — 2026-10-18 — SSE-status for expansion boards

- **PLC'er** viser nu, hvor mange ændringer der er kommet via SSE fra **RS485-slaver** og fra **expansion boards** hver for sig.

## v0.90.0 — 2026-10-18 — Eksterne registre via SSE

- Værdier fra **RS485-slaver og expansion boards** opdateres nu straks via PLC'ens SSE-strøm, når de ændrer sig i PLC'ens Modbus-cache — ikke kun ved næste poll.
- Rettet: med mange overvågede adresser blev PLC'ens input-registre 256–319 (fx ST-statistikken) kun opdateret hvert 2. sekund.

## v0.89.0 — 2026-10-18 — Systemgennemgang (2): symboler med samme navn

- **Tegn** advarer, når flere symboler har samme navn, og giver dem unikke navne med ét klik (**Giv dem unikke navne** — kan fortrydes).

## v0.88.0 — 2026-10-18 — Systemgennemgang (1): forsvundne symbolopsætninger

- **Bindinger → Forsvundne elementer** viser nu også **symbolopsætninger** på elementer, der er slettet eller har fået et nyt id. De kan **flyttes** til det rigtige element (animationer og kode følger med) eller **fjernes**.
- Rettet: beskeden efter *Flyt hertil* blev ikke vist.

## v0.87.0 — 2026-10-18 — Alarmmarkering kun på værdier

- Den røde alarmmarkering i tegningen sidder nu kun på de dele, der **viser værdien** af et tag i alarm (fx "kedel: 100,0 °C") — ikke på fx en flamme eller en pumpepil, der blot bruger samme tag.

## v0.86.0 — 2026-10-18 — Løbehjul i pumpen

- **Pumpen** har nu et **løbehjul** i stedet for trekanten. Det drejer, når pumpen kører (guiden foreslår det), mens pilen står stille og viser retningen. Gamle pumper opdateres med *Erstat med symbol*.

## v0.85.0 — 2026-10-18 — Pumpens pil og ny animation Størrelse

- **Roterer** på en pumpe drejer ikke længere **pilen** med — den viser stadig pumperetningen.
- Ny animation **Størrelse**: en del (fx pumpens pil) bliver større eller mindre efter en tag-værdi, fx 50 % ved Min og 150 % ved Max.

## v0.84.0 — 2026-10-18 — Opdatér gamle symboler

- **Erstat med symbol** på et gammelt symbol fra biblioteket foreslår nu den **nyeste udgave** (fx pumpen med pil). Navn, placering og opsætning bevares, og alle symboler af samme slags kan opdateres på én gang.
- Rettet: *Behold delens id* virkede ikke for symboler med en opsætning — de fik et nyt id og mistede opsætningen.

## v0.83.1 — 2026-10-18 — Rettet: løbelys i en ny 3-vejs ventil

- En ny **3-vejs ventil** (og andre symboler med dele uden navn) kunne arve en gammel animation, fx løbelys fra et slettet rør, når tegningen blev åbnet igen i Tegn. Det sker ikke længere.

## v0.83.0 — 2026-10-18 — Ret forsvundne bindinger

- Advarslen *Bindinger til elementer der ikke findes i denne version* forklarer nu årsagen og fører til **Bindinger → Forsvundne elementer**.
- Dér ser du, hvad bindingerne var, og kan **flytte dem til det nye element** (hvis elementet har fået et nyt id) eller **fjerne** dem — også alle på én gang.

## v0.82.1 — 2026-10-18 — Pilen inde i pumpen

- Pumpens retningspil sidder nu **inde i** symbolet (i trekanten).

## v0.82.0 — 2026-10-18 — Pil på pumpen

- **Pumpen** i symbolbiblioteket har en **pil**, der viser pumperetningen — drej symbolet for at vende den. Pilen er en egen del og kan fx farves eller blinke. Pumper, der allerede står i tegningerne, ændres ikke (sæt en ny ind eller brug *Erstat med symbol*).

## v0.81.1 — 2026-10-18 — Rettet: animation på hele symbolet

- **Roterer** og **Blafrer** på *Hele symbolet* fik symbolet til at hoppe op i hjørnet og skifte størrelse. Nu bliver symbolet på sin plads.

## v0.81.0 — 2026-10-18 — Forståelige navne

- I symbolguiden hedder dele uden navn nu fx **Ramme**, **Rektangel 2**, **Cirkel** eller **Tekst "STF"** i stedet for "svg_2".
- I **Trends** kan kurverne få et **navn** (under *Administrér* → **Navn**), som vises i stedet for tag-navnet.

## v0.80.1 — 2026-10-18 — Rettet: blafren stoppede ved alarm

- En del, der **blafrer** eller **roterer**, holdt op med at bevæge sig, når dens tag var i ukvitteret alarm (den røde alarmmarkering overtog). Nu kører begge dele.

## v0.80.0 — 2026-10-18 — Trends ud fra symbolerne

- I **Trends** kan du vælge et **symbol** — så vises alle dets kurver, uden at du skal finde tagsene selv.
- I symbolguiden (trin 6) slår du **historik** til for symbolets tags (ét klik for alle), og **Vis symbolet i Trends** åbner kurverne direkte.

## v0.79.0 — 2026-10-18 — Fra Overview til Tegn

- Står du på en tegning i **Overview**, åbner **Tegn** og **Bindinger** i menuen nu den samme tegning.

## v0.78.0 — 2026-10-18 — Mine symboler

- I **Tegn** kan du samle de symboler, du bruger mest, i en egen sektion **Mine symboler** øverst i biblioteket: tryk **☆** på et symbol, og ordn dem med **◀ ▶**. Listen følger din bruger — også på en anden pc.

## v0.77.0 — 2026-10-18 — Bredere statusfelter

- **Statusfelt**, **Værdifelt** og **Auto/Manuel** kan trækkes bredere i Tegn, så der er plads til mere tekst — teksten bliver ikke strakt, og statusfeltet beholder sine runde ender.

## v0.76.0 — 2026-10-18 — Tilbage til tegningen

- **Alarmer**, **Trends** og **Energi** har en knap **← Tilbage til "…"**, der fører tilbage til den tegning, du kom fra.

## v0.75.1 — 2026-10-18 — Symbolerne ruller for sig selv

- I **Tegn** ruller symbolbiblioteket i højre side for sig selv — tegningen og resten af siden står stille, og søgefeltet bliver stående øverst.

## v0.75.0 — 2026-10-17 — Genveje i tegningen

- Ny kategori **Genveje** i symbolbiblioteket: **Gå til Alarmer**, **Gå til Trends** og **Gå til Energi**. Et klik i Overview åbner siden.
- Alarmknappen viser **antallet af aktive alarmer** — rødt og blinkende, når der er ukvitterede.

## v0.74.1 — 2026-10-17 — Tag-alarmer forklaret

- Manualen (*PLC'er og tags › Alarmer på et tag*) forklarer nu HH/H/L/LL, dødbånd, forsinkelse og til/fra-alarm med et eksempel.
- Rettet: et tag kunne gemmes med både grænser og til/fra-alarm, og så virkede grænserne ikke. Det afvises nu med en forklaring — vælg den ene.

## v0.74.0 — 2026-10-17 — Alarmer i symbolguiden

- En animation kan styres af **en alarm** på et tag — fx en lampe der **blinker**, så længe alarmen er **ukvitteret**, eller bliver **rød**, så længe den er **aktiv**.
- Trin 6 viser **alarmerne på symbolets tags** og deres status lige nu, og du kan **rette alarmen** (grænser eller til/fra, dødbånd, forsinkelse) direkte dér.

## v0.73.0 — 2026-10-17 — Beregning i Værdi-animationen

- Guidens **Værdi** har nu **Beregning** (fx *x / 10*) og **Vis enhed** som på siden Bindinger, og viser hvordan den aktuelle værdi bliver vist (*Lige nu: 128 → 12.8 bar*).

## v0.72.0 — 2026-10-17 — Flere animationer på samme del

- En animation kan nu være **passiv**: når den ikke er aktiv, rører den ikke delen. Så kan du stable fx flere løbelys på samme rør med hver sin betingelse og hvert sit sæt farver — den **øverste aktive** vinder.
- **+ Standard** tilføjer en animation nederst, der gælder, når ingen af de andre er aktive.

## v0.71.0 (build 0109) — 2026-10-17 — Manual

- Manualen (*Bindinger og animationer*) forklarer nu løbelysets tre styringer — **Til/fra**, **Fortegn (+/−)** og **Kode 0/1/2** — samt **Omvendt** og **Retning fra**.

## v0.71.0 — 2026-10-17 — "Altid til"

- I symbolguiden kan en animation nu styres af **altid til** i stedet for et tag — fx en flamme der altid blafrer, eller et løbelys der altid kører.

## v0.70.1 — 2026-10-17 — Rettet: drejede rør i Tegn

- Et drejet rør (fx et lodret rør lavet ved at dreje et vandret) følger nu musen, hver gang du strækker det. Før voksede det for meget anden gang.

## v0.70.0 — 2026-10-17 — Flammen skifter farve

- **Blafrer** farver nu hele flammen og skifter tilfældigt mellem **tre farver**, du vælger (standard rød, orange og gul), mens den blafrer.

## v0.69.0 — 2026-10-17 — Blafrende flamme og Gem på alle trin

- Ny animation **Blafrer**: delen bliver farvet og blafrer som en flamme, mens fyret kører. Guiden foreslår den på flammen for **Kedel/fyr**.
- I symbolguiden står **Gem** nu på alle seks trin — du kan gemme, så snart der ikke er fejl.
- Rettet: et nyt element i Tegn kunne få id'et fra et slettet element og dermed "arve" dets gamle opsætning (fx løbelys på ekspansionsbeholderens streg). Nye elementer får nu aldrig et id, der stadig har en opsætning.

## v0.68.0 — 2026-10-17 — Løbelys pr. rør i T-stykker

- Et T-stykke består nu af tre rør — **Tilløbsrør 1**, **Tilløbsrør 2** og **Midterrør** (et kryds af fire) — som du kan vælge hver for sig i guiden og give hvert sit løbelys og sin retning.
- T-stykker, der allerede står i dine tegninger, deles med **Del i rør** i Tegn (vælg T-stykket; fortrydes med Ctrl+Z).

## v0.67.0 — 2026-10-17 — Løbelys følger din retning

- Den retning, du sætter på løbelyset i animationen, gælder nu altid — systemet vender ikke længere et rør efter naboerne.
- Rør, bøjninger og T-stykker synkroniseres ved de samlinger, hvor retningerne passer sammen. Kører et rør den forkerte vej, så sæt **Vend retning** på det.

## v0.66.1 — 2026-10-17 — Rettet: højreklikmenuen i Tegn

- Højreklikmenuen lukker nu, når du har valgt *Kopiér*, *Indsæt* osv. Før blev den stående, og det næste højreklik kunne ramme den gamle menu i stedet for tegningen — så blev det forkerte element kopieret, eller der skete ingenting.

## v0.66.0 — 2026-10-17 — Nyt symbol: Varmepumpe

- Symbolbiblioteket (*Rør og VVS*) har nu en **Varmepumpe**: et aggregat med ventilator, varmeveksler og driftslampe. Guiden foreslår, at ventilatoren drejer, og lampen bliver grøn, når varmepumpen kører.
- *Erstat med symbol* foreslår varmepumpen, når den tegnede del har teksten "Varme Pumpe".

## v0.65.1 — 2026-10-17 — Rettet: rør kan strækkes i begge ender

- I **Tegn** kan et lodret rør (og alle andre figurer) nu strækkes opad med det øverste midtergreb. Før flyttede grebet hele elementet, fordi drejegrebets streg lå ovenpå.

## v0.65.0 — 2026-10-17 — T-stykkets afgrening

- Løbelyset i et T-stykkes afgrening starter nu ved kanten af gennemløbet i stedet for midt inde i det, så lyset ikke tegnes hen over gennemløbet.

## v0.64.2 — 2026-10-17 — Løbelys over korte rørstykker

- Et kort rørstykke mellem fx et T-stykke og en bøjning bryder ikke længere det sammenhængende løbelys.

## v0.64.1 — 2026-10-17 — Løbelys: også over T-stykker og med forskellig lyslængde

- T-stykker indgår nu i det sammenhængende løbelys (både gennemløbet og afgreningen).
- Har delene i et forløb forskellig lyslængde eller fart, bruger hele forløbet den, flest dele har — så mønstret kan fortsætte over samlingerne.

## v0.64.0 — 2026-10-17 — Løbelys uden synlige samlinger

- Løbelys på rør, bøjninger og T-stykker, der hænger sammen og bruger samme tag, kører nu som **ét sammenhængende lys** — mønstret fortsætter hen over samlingerne i stedet for at starte forfra i hver del.
- Er et rør tegnet "baglæns", kører det nu alligevel samme vej som sine naboer. Vil du vende hele forløbet, så sæt **Vend retning** på alle delene (fx med *Opsæt de valgte samlet*).

## v0.63.3 — 2026-10-17 — Rettet: Indsæt opsætning i Firefox

- Bekræftet: *Indsæt opsætning* og alle andre spørgsmål virker nu også i Firefox.

## v0.63.2.1 — 2026-10-17 — Spørgsmål virker også i Firefox (debug)

- Spørgsmål som *"Slet …?"*, *"Kassér ændringer?"* og *"… intet navn. Fortsæt?"* vises nu i en dialog på siden i stedet for browserens egen. Firefox kunne blokere browserens dialoger, og så gjorde fx *Indsæt opsætning* ingenting.

## v0.63.2 — 2026-10-17 — Tegneeditoren holdes opdateret

- Tegneeditoren hentes nu altid i den rigtige version efter en opdatering. Er den alligevel gammel, siger **Tegn** det og beder dig genindlæse med **Ctrl+F5**.
- Går *Kopiér/Indsæt opsætning* eller *Opsæt de valgte samlet* galt, vises fejlen nu i stedet for, at der bare ingenting sker.

## v0.63.1 — 2026-10-17 — Rettelser

- Står en side åben, mens SCADA bliver opdateret, viser den nu et banner **"SCADA er opdateret … Genindlæs"**. Før kørte fanen videre med den gamle version, så nye funktioner (fx *Opsæt de valgte samlet* og navngivning ved *Indsæt opsætning*) ikke var der.
- Kopierer eller duplikerer du et symbol i Tegn, får kopien nu sit eget navn (fx *Bøjning 90° 8*) i stedet for originalens.

## v0.63.0 — 2026-10-17 — Opsæt flere symboler samlet

- Markér flere symboler i **Tegn** og tryk **Opsæt de valgte samlet**. Guiden åbner med ét af dem, og når du trykker **Gem i alle**, får alle de valgte den samme opsætning (tag og animationer).
- Har de valgte **forskellige opsætninger**, spørger systemet først, hvilken der skal være udgangspunktet.
- Kan et af symbolerne ikke få opsætningen (fx løbelys på en pumpe), står det i guiden — de andre får den alligevel.

## v0.62.0 — 2026-10-17 — Indsæt opsætning giver navne

- Indsætter du en kopieret opsætning i elementer **uden navn**, får de nu kildens navn med løbenummer — fx *varme pumpe tilgang_1*, *varme pumpe tilgang_2* … (numre der allerede er brugt, springes over) — og derefter opsætningen. Før blev de sprunget over.

## v0.61.0 — 2026-10-17 — Farver på valgte symboler

- I **Tegn** viser panelet *Valgt element* nu feltet **Farver** med de farver, de valgte symboler bruger. Vælg en ny farve for en af dem, så skiftes den i alle de valgte symboler på én gang — fx alle rør, bøjninger og T-stykker i en kreds. **Ctrl+Z** fortryder.

## v0.60.0 — 2026-10-17 — Kopiér og indsæt opsætning i Tegn

- I **Tegn** kan du vælge et symbol og trykke **Kopiér opsætning**, og derefter vælge et eller flere andre symboler og trykke **Indsæt opsætning**.
- Har et af symbolerne allerede en opsætning, spørger systemet, før den overskrives. Passer opsætningen ikke til et symbol (fx løbelys på en pumpe), får du at vide hvorfor, og de andre symboler får den stadig.

## v0.59.0 — 2026-10-17 — Samme opsætning på mange symboler

- I symbolguiden kan du nu trykke **Gem og anvend på flere …** og kopiere opsætningen (tag og animationer) til andre symboler på tegningen — fx alle rør, bøjninger og T-stykker på én gang med **Alle rør og fittings**.
- Hvert symbol får sin **egen kopi**, som du bagefter kan rette enkeltvis.
- Symboler, der allerede er sat op, springes over, medmindre du sætter hak i **Overskriv**. Resultatet viser, hvad der blev kopieret, og hvad der ikke kunne.

## v0.58.0 — 2026-10-17 — Ventiler vender rigtigt efter erstatning

- Når du erstatter en tegnet ventil (to trekanter) med et ventilsymbol, aflæser systemet om ventilen står **vandret eller lodret** og drejer symbolet tilsvarende.
- En **kontraventil** drejes, så pilen peger samme vej som den tegnede trekant.
- Bedre forslag: en ventil med greb foreslås som **manuel ventil** (før blev den fejlagtigt foreslået som motorventil); en ventil med motorcirkel som **motorventil**.

## v0.57.0 — 2026-10-16 — Erstat med symbol: ventiler tegnet af flere dele

- Er en ventil (eller et andet symbol) tegnet af **flere løse figurer**, kan du markere dem alle og trykke **Erstat markeringen med symbol …**. Systemet foreslår fx **3-vejs motorventil**.
- Nyt valg: **Spejlvend vandret** — til en ventil, der er tegnet omvendt (A og AB byttet). Bogstaverne bliver ved at vende rigtigt.
- Rettet: navne på de nye symboler fik fejlagtigt et " 2" til sidst.

## v0.56.0 — 2026-10-16 — Pumpernes retning bevares ved erstatning

- Når du erstatter en tegnet pumpe med symbolet **Pumpe**, aflæser systemet, hvilken vej den tegnede trekant peger, og **drejer symbolet, så det peger samme vej** — også når du erstatter flere pumper på én gang. Valget kan slås fra.

## v0.55.1 — 2026-10-16 — Erstat med symbol rører ikke bundne dele

- Når du erstatter **alle lignende** dele med et symbol, **springes de dele over, der har bindinger** (også på deres tekster), så ingen binding går tabt. Du får besked om hvor mange, og kan erstatte dem enkeltvis.

## v0.55.0 — 2026-10-16 — Erstat tegnede dele med symboler

- I **Tegn** kan du markere en tegnet del og trykke **Erstat med symbol …**. Systemet foreslår det rigtige symbol ud fra formen (fx statusfelt til en pille-etiket, pumpe til en cirkel med trekant), eller du søger i biblioteket.
- Symbolet får **samme placering, størrelse og drejning** som den gamle del. Teksten i en etiket kan overtages.
- Du kan erstatte **alle lignende dele på én gang** — fx alle etiketter — og et enkelt Ctrl+Z gendanner det hele.
- Er tegningen samlet i én stor gruppe, kan du **opløse gruppen** først.
- Resultatet gemmer du som en **kladde-version**; Overview viser først ændringen, når du udgiver den.

## v0.54.2 — 2026-10-16 — Løbelys og gitter rettet

- **Løbelyset** er nu uafhængigt af, hvordan du har strakt eller skaleret et rør: lysstykkernes længde og fart er de samme, uanset rørets længde.
- **Fang til gitter** lægger nu objektet på et rigtigt gitterpunkt (ikke bare i trin fra hvor det stod). Det gælder også, når du indsætter, duplikerer eller sætter et symbol ind: kopier havner på samme gitter som originalen.

## v0.54.1 — 2026-10-16

- Manualen har fået et billede af **Tegnehjælp** (gitter og fang) i Tegn.

## v0.54.0 — 2026-10-16 — Gitter og fang i Tegn

- Under værktøjslinjen i **Tegn** er der en ny række, **Tegnehjælp**:
  - **Vis gitter** — et net ovenpå tegningen (afstand 5, 10, 20, 25 eller 50), med kraftigere linje for hver 5.
  - **Fang til gitter** — objekter flyttes og tegnes i gitterets trin.
  - **Fang til objekter** — slipper du et objekt tæt på et andet, lægger det sig kant mod kant eller midte mod midte. Tryk Ctrl+Z for at fortryde fangen.
- **Rotation sker nu i 15°-trin.** Hold **Shift** nede for at rotere frit.
- Indstillingerne huskes i din browser.

## v0.53.0 — 2026-10-16 — Skærmbilleder i manualen

- Manualen har nu **29 skærmbilleder**: menuen, Overview, alarmer, kurver, tags, tegninger, Tegn, bindinger, **alle seks trin i guiden**, ugeprogrammer og System-siderne.
- Klik på et billede for at se det stort. Billedteksten står under billedet.
- Billederne kan **tages om automatisk** fra en kørende server, når skærmene ændrer sig (`npm run manual:screenshots`).

## v0.52.2 — 2026-10-16 — Manual rettet

- Et eksempel i manualen (setpunkt) pegede på et forkert trin i guiden. Rettet.

## v0.52.1 — 2026-10-16 — Bedre på telefon og tablet

- Topmenuen med **Bruger** passer nu på en smal skærm, og manualen har en kapitelvælger i stedet for en lang liste.

## v0.52.0 — 2026-10-16 — Brugermanual

- Ny side **Bruger › Manual** med en komplet brugermanual: hvordan systemet hænger sammen, roller, alle sider i menuen, tags og PLC'er, tegninger, animationer, symbolguiden i 6 trin, logikblokke, alle 85 symboler i biblioteket, ugeprogrammer, backup og opdatering — og **11 eksempler trin for trin** (pumpe, tank, 3-vejs ventil, logik, setpunkt med beregning, alarm, ugeprogram, omskifter, ekstern Modbus, opdatering).
- Du kan **søge** i hele manualen, hoppe mellem kapitler og direkte til afsnit.
- Biblioteks-kapitlet opdateres automatisk, når der kommer nye symboler.

## v0.51.1 — 2026-10-16 — Bruger-menuen til højre

- **Bruger** står nu yderst til højre i topbjælken, som du kender det fra andre programmer.

## v0.51.0 — 2026-10-16 — Ny topmenu: Drift, Opsætning, System, Bruger

- Menuen er nu fire punkter i topbjælken: **Drift**, **Opsætning**, **System** og **Bruger**. Før musen hen over et punkt, så folder menuen sig ud af sig selv, og du kan vælge siden direkte.
- **Bruger** har dit navn, **Skift adgangskode**, **Log ud** og versionen.
- På touch-skærme trykker du på punktet i stedet. Escape eller et klik udenfor lukker menuen.

## v0.50.1 — 2026-10-16 — OTA: rettelser fra afprøvningen

- Resultatet af en opdatering viser nu både version og build (fx *0.50.0 build 0072 → 0.50.0 build 0074*), og sundhedstjekket kræver den rigtige build.
- Mens en opdatering kører, skjules pakkekortet og dets knapper.

## v0.50.0 — 2026-10-16 — Opdatering direkte fra web-siden (OTA)

- Ny side **System › Opdatering** (kun admin): upload en opdateringspakke, kontrollér version og kontrolsum, og tryk **Installér og genstart**. Du behøver ikke længere SSH.
- Før opdateringen tages en backup. Svarer den nye version ikke efter genstarten, **rulles der automatisk tilbage** til den forrige. Status og log vises på siden.
- Pakken bygges med `sh deploy/make-package.sh`. Ældre versioner kan ikke installeres.
- **Første gang** skal serveren have installationen kørt som root (`sh deploy/install.sh`); derefter kan alle nye versioner komme via siden.

## v0.49.0 — 2026-10-16 — Kun relevante betjeningsformer i guiden

- I guidens **trin 1** vises nu kun de betjeningsformer, der giver mening for symbolet. En 3-vejs motorventil kan fx kun have **Kun visning** eller **Positioner**, og rør og tanke kun **Kun visning**.
- Vil du alligevel bruge en anden, så afkryds **Vis alle betjeningsformer**. Egne tegninger viser altid alle fire.

## v0.48.1 — 2026-10-16 — Hurtig opsætning: Kun visning

- Når du bruger **Hurtig opsætning** på en ny 3-vejs ventil, sættes symbolet automatisk til **Kun visning**, så guiden ikke bagefter beder om et tag at skrive til.

## v0.48.0 — 2026-10-16 — 3-vejs ventil: ét tag styrer alle tre porte

- I guidens **trin 4 (Visning)** har de to 3-vejs motorventiler en **Hurtig opsætning**: vælg det til/fra-tag, der styrer ventilen, og tryk **Opret animationer**.
- **Til** = AB → A (Port A og AB åbne), **Fra** = AB → B (Port B og AB åbne). Port AB er altid åben.
- Virker også med en indgang, du kun kan læse. Farverne kan rettes bagefter under Animationer.

## v0.47.2 — 2026-10-16 — 3-vejs motorventil: tre hvide porte

- Begge 3-vejs motorventiler er nu tegnet med tre hvide porte (A, B og AB), så det kun er animationerne, der farver dem.

## v0.47.1 — 2026-10-16 — Guiden: smallere tag-valg

- I guidens trin 2 er **Kommando** og **Tilbagemelding** ikke længere så brede, at **Skrives som** blev presset ud til højre. Det samme gælder tag-valgene ved animationerne.

## v0.47.0 — 2026-10-16 — 3-vejs motorventil med AB i midten

- Ny variant af 3-vejs motorventilen (Rør og VVS): **AB nederst**, A til venstre og B til højre, motoren øverst. Samme opsætning som den første variant: positionerne AB → A og AB → B med farve pr. port.

## v0.46.0 — 2026-10-16 — 3-vejs motorventil og logikblok som retning

- Nyt symbol i biblioteket (Rør og VVS): **3-vejs motorventil** med portene A, B og AB og en motor. Hver port kan farves for sig.
- Når du opsætter det med guiden, får du et forslag med to positioner: **AB → A** og **AB → B**. AB er altid åben, og enten A eller B er åben. Vælg tagget under trin 2, og ret farverne i trin 4, hvis du vil.
- Et løbelys' **Retning fra** kan nu også være en **logikblok**, ikke kun et tag.

## v0.45.0 — 2026-10-16 — Logikblokke kan bruges i andre symboler

- En logikblok, du har lavet i ét symbol, kan nu vælges som **kilde** i animationer i **andre symboler på samme tegning** — og som indgang i deres egne logikblokke. Valglisterne har grupperne *Dette symbol* og *Andre symboler*.
- Fx: lav blokken *Pumpe kører og ventil åben* i pumpe-symbolet, og lad rørene og en lampe i andre symboler bruge den.
- Du kan ikke fjerne en blok (eller hele symbolets konfiguration), mens et andet symbol bruger den — fjern henvisningen dér først. Blokke der henviser til hinanden i ring afvises.

## v0.44.0 — 2026-10-16 — Logikblokke: animationer der afhænger af flere tags

- I guidens **trin 4 (Visning)** kan du lave **logikblokke**: AND eller OR over op til 4 indgange, med NOT på hver indgang og på resultatet. Eksempel: *pumpe kører (coils0) OG ventil åben (input0)*.
- En indgang kan være et til/fra-tag, et tal-tag sammenlignet med en grænse (≥, ≤, =) eller en anden blok **over** den — så kan du bygge flere niveauer.
- Vælg blokken som **kilde** i en animation ("en logikblok"). Så er animationen aktiv, når betingelsen er opfyldt.
- Er et tag ukendt (fx kommunikationsfejl), men en anden indgang allerede afgør resultatet, bruges det (AND med en Fra giver Fra). Ellers er resultatet ukendt, og delen vises som tegnet.
- **Trin 6 (Test og gem)** viser hver blok og dens værdi lige nu.

## v0.43.0 — 2026-10-16 — Symboler opsættes med guiden i 6 trin

- I **Tegn**: giv et symbol et navn, og tryk **Opsæt symbol (6 trin)**. Nyindsatte symboler opfordrer til det. Tegningen gemmes og udgives først (du bliver spurgt).
- Under **Bindinger**: sektionen **Symbol** har nu guiden som den primære måde at sætte tag, positioner, animationer og nøglelås op på. Den gamle "vælg ét tag til hele symbolet" er væk; **Forklaring** er stadig der.

## v0.42.0 — 2026-10-16 — Slet tegning også fra Tegn

- Knappen **Slet tegning** findes nu også i **Tegn** (ved siden af Gem), ud over på siden **Tegninger**.
- Før sletningen vises, hvad den rammer: antal versioner og bindinger, andre tegninger med en "gå til"-knap hertil (de holder op med at virke), om det er start-tegningen, og hvilke brugere der har adgang til den.

## v0.41.0 — 2026-10-16 — Beregning på tekst-felter

- Tekst-animationen under **Bindinger** har fået feltet **Beregning**, så værdien kan regnes om, før den vises. Fx `x / 10` viser registerværdien 128 som 12,8. `x` er tagets værdi.
- Du kan bruge + − * / %, parenteser og få funktioner (`round`, `abs`, `min`, `max` …), fx `x * 1,8 + 32` eller `round(x / 10)`.
- **Decimaler** og **enhed** gælder resultatet af beregningen.
- Skriver du en ugyldig formel, får du en forklaring med det samme, og den kan ikke gemmes. Deler du med 0, vises et tankestreg.

## v0.40.0 — 2026-10-14 — Ny hovedmenu

- Menuen foroven er nu én smal bjælke: **Menu**, hvor du er (fx "Drift › Overview"), antal alarmer og dit brugernavn.
- **Menu** folder siderne ud over tegningen, delt i **Drift**, **Opsætning** og **System**, plus skift adgangskode og log ud. Tegningen bliver ikke skubbet ned og får dermed mere plads end før.
- Menuen lukker når du vælger en side, trykker Escape eller klikker ved siden af.

## v0.39.0 — 2026-10-14 — Ny rolle: Driftpanel

- Under **Brugere** kan en bruger nu få rollen **panel** (Driftpanel) — tænkt til en skærm i produktionen.
- Et driftpanel viser kun drifttegningen: ingen menu foroven, kun **Log ud** i en smal kolonne i venstre side. Har brugeren adgang til flere tegninger, står de som knapper under Log ud; begrænses brugeren til én tegning, er der kun Log ud.
- Driftpanelet kan betjene og kvittere alarmer som en operatør — og kan som operatører begrænses til udvalgte tegninger.

## v0.38.1 — 2026-10-13 — Rettelser i symbolguiden og Konvertér alle

- Symboler med "Gå til tegning" eller betjening på en del af symbolet konverteres ikke længere automatisk — de står som "kræver manuel handling", så linket eller betjeningen ikke forsvinder.
- Konverterede setpunkter beder kun om bekræftelse hvis tagget gør det, som før.
- Guiden fortsætter med at kontrollere efter en fejl ved gem, og Gem kan ikke trykkes før den seneste ændring er kontrolleret.

## v0.38.0 — 2026-10-13 — Symbolstandard, del 8: konvertér alle symboler

- Under **Tegninger** er der nu et panel **Symbolstandard: konvertér alle**. **Tør-kørsel** viser for hvert symbol om det kan konverteres til den nye standard, og hvorfor ikke hvis det ikke kan — uden at gemme noget.
- **Konvertér N symboler** sætter derefter de symboler op der kan. Hvert symbol kan fortrydes i guiden med **Fjern konfiguration**.
- Den gamle måde (ét tag pr. symbol) virker stadig side om side med den nye.

## v0.37.0 — 2026-10-13 — Symbolstandard, del 7: koden til nøglelåsen

- Koden til et symbols låste positioner kan skiftes og fjernes i guiden (trin 5). Koden vises aldrig igen efter den er gemt, og den står ikke i loggen eller i backuppen.
- Har en operatør tastet forkert kode for mange gange, ophæves spærringen når teknikeren sætter koden igen.
- Mangler et symbol sin kode (fx efter gendannelse af en backup), siger guiden det — og de låste positioner kan ikke vælges, før en ny kode er sat.

## v0.36.0 — 2026-10-13 — Symbolstandard, del 6: guiden

- Under **Bindinger** har grupper og symboler nu knappen **Opsæt symbol (guide)**. Guiden fører gennem 6 trin: hvordan symbolet betjenes, hvilke signaler det skriver, kontaktplanerne (med skabeloner og eksemplet "7-trins vælger"), animationerne, betjening og nøglelås, og til sidst live-værdier og hvad hvert positionsskift vil skrive.
- Fejl vises ved det trin de hører til, og symbolet kan først gemmes når alt er i orden.
- Har symbolet bindinger fra før, foreslår guiden en opsætning ud fra dem (**Foreslå ud fra symbolet**). Når symbolet er gemt i guiden, bruges de gamle bindinger ikke længere; **Fjern konfiguration** giver dem tilbage.

## v0.35.0 — 2026-10-13 — Symbolstandard, del 4–5: symbolerne på Overview

- Symboler sat op efter den nye standard vises og betjenes nu på Overview:
  - et mærke viser om positionen er **Bekræftet**, **Venter**, i **Afvigelse** eller **Ukendt** — ved afvigelse står PLC'ens position under symbolet;
  - en vippekontakt eller start/stop uden bekræftelse skifter med ét klik; andre symboler åbner en dialog med positionerne og viser hvilke signaler der skrives;
  - låste positioner har en hængelås og kræver koden;
  - en afvigelse kan accepteres direkte i dialogen;
  - trykknapper og setpunkt-felter virker som før.
- Animationerne kan styres af symbolets position (farve, tekst, vinkel, flyt, løbelys pr. position), kan begrænses til udvalgte positioner, kan blinke langsomt/normalt/hurtigt i takt, og kan rotere. Greb og vipper glider til den nye position.
- Alarmlisten viser niveauet Lav/Medium/Høj for symbolernes afvigelser.
- Selve opsætningen (guiden under Bindinger) kommer i næste del.

## v0.34.0 — 2026-10-13 — Symbolstandard, del 3: betjening af symboler

- Serveren kan nu betjene symboler efter den nye standard: et skift skriver kun de signaler der skal ændres, og det der skal slukkes, slukkes før noget tændes.
- Fejler en skrivning midt i et skift, stopper det — og beskeden siger præcis hvad der er skrevet, hvad der er usikkert (intet svar fra PLC'en), og hvad der ikke er skrevet.
- Puls med hvileværdi, fejl/låst-signal der blokerer betjening, nøglelås med 4-cifret kode (3 forkerte koder spærrer i 60 s), og "acceptér PLC'ens position" ved en afvigelse.
- Skærmbillederne til det kommer i næste del.

## v0.33.0 — 2026-10-13 — Symbolstandard, del 2: serveren kender symbolernes position

- Serveren finder nu selv hvilken position et symbol står i ud fra PLC'ens tilbagemeldinger, og om den er Bekræftet, Venter, Afvigelse eller Ukendt — også for omskiftere med flere signaler (fx 7 positioner på 3 bits).
- Står et symbol i "Lokal" visning, og PLC'en ikke følger med inden for valideringstiden, kommer der en alarm med det niveau teknikeren har valgt (Lav, Medium eller Høj). Alarmlisten sorteres Høj → Medium → Lav.
- Sidst valgte position huskes også efter genstart af serveren.

## v0.32.0 — 2026-10-13 — Symbolstandard, del 1: serveren kan gemme og kontrollere symboler

- Første del af den nye symbolstandard: serveren kan nu gemme en samlet opsætning pr. symbol (positioner, signaler, kontaktplaner, visning, alarmniveau, nøglelås og animationer) og kontrollerer den efter de samme regler som prototypen — med en præcis fejlbesked pr. trin.
- Koden til en nøglelås gemmes kun krypteret og kommer aldrig med i backup; efter en gendannelse skal en tekniker sætte en ny kode.
- Indsatte symboler husker nu deres type og deres dele, så guiden kan kende dem igen.
- Der er endnu ingen skærmbilleder til det — de kommer i de næste dele. Eksisterende tegninger virker som før.

## v0.31.4 — 2026-10-13 — Ændrede rettigheder slår igennem på åbne skærme

- Logges en bruger ud, deaktiveres, eller ændres rollen, lukkes åbne Overview-skærme for brugeren inden for 10 sekunder og viser login. Før fortsatte de med at vise live-data.
- Ændres en brugers tegningsadgang, opdateres åbne skærme med det samme brugeren nu må se.

## v0.31.3 — 2026-10-13 — Overview viser altid den rigtige værdi

- På en langsom forbindelse (fx en skærm på et svagt net) kunne en ændring gå tabt, så fx en pumpe stod som stoppet selvom den kørte. Nu samles ventende ændringer, så skærmen kan blive lidt forsinket, men aldrig viser en forkert værdi.

## v0.31.2 — 2026-10-13 — Til/fra-knapper skifter altid korrekt

- Trykker to operatører på samme til/fra-knap samtidig, skifter den nu til og derefter fra igen — før kunne begge tryk give "til".
- En til/fra-knap går altid ud fra den værdi PLC'en har lige nu, også hvis visningen endnu ikke er opdateret.

## v0.31.1 — 2026-10-13 — Puls efterlader aldrig udgangen tændt

- Hvis PLC'en ikke når at svare på en puls (fx ustabilt net), sætter serveren nu alligevel udgangen til fra, så den ikke kan blive stående tændt. Operatøren får besked om, at pulsen ikke kunne bekræftes.

## v0.31.0 — 2026-10-13 — Løbelys kan køre begge veje fra to signaler

- Løbelys har fået **"Retning styres af"**: vælg et ekstra til/fra-tag der bestemmer retningen (Fra = som valgt, Til = modsat). Så kan én animation køre begge veje, når PLC'en har start/stop og retning som to separate signaler.
- Virker sammen med alle måder at styre løbelyset på og med T-stykker og kryds. Er retningen ukendt (fx kommunikationsfejl), står lyset stille.

## v0.30.0 — 2026-10-13 — Løbelys i T-stykker og kryds

- Løbelys på et **T-stykke** eller **kryds** kan nu sættes pr. rør: vælg ét af rørene (venstre, højre, op eller ned — som det ses på skærmen, også når symbolet er drejet) og om det løber **ind i** eller **ud af** krydset. De øvrige rør løber automatisk den modsatte vej.
- Tagget styrer stadig start/stop, og "tilbage" (fx kode 2) vender hele mønstret.

## v0.29.0 — 2026-10-13 — Løbelys i rør

- Ny animation **Løbelys** under Bindinger: to farver løber langs et rør eller en streg, så man kan se flowet. Virker på lige rør, bøjninger, T-stykker, kryds og tegnede streger.
- Tagget styrer **start/stop og retning** på en af tre måder: *Til/fra* (kører når til, fast retning), *Fortegn* (over 0 frem, under 0 tilbage, 0 stop — fx en frekvensomformers hastighed) eller *Kode* (0 stop, 1 frem, 2 tilbage).
- Farver, hastighed og streglængde kan vælges, og retningen kan vendes, hvis røret er tegnet "baglæns".
- Lyset står stille ved stop og ved kommunikationsfejl, så der aldrig vises flow der ikke er der.

## v0.28.2 — 2026-10-13 — Lige lange ben på rørdelene

- **Bøjning 45°** har nu to lige lange ben (45), ligesom Bøjning 90°, T-stykke og kryds. Bøjninger der allerede ligger i en tegning, ændres ikke.

## v0.28.1 — 2026-10-13 — Rør og fittings ser ens ud

- I **Tegn** vises rør, bøjninger, T-stykke, kryds og de øvrige rørdele nu i samme målestok, så rørene ser lige tykke ud.
- **Bøjning 45°** er nu rund som Bøjning 90°.
- Nye lige rør er 90 lange som udgangspunkt (som T-stykke og kryds) — træk i enderne for at forlænge. Rør der allerede ligger i en tegning, ændres ikke.

## v0.28.0 — 2026-10-13 — Trykknappen ligner en trykknap

- Symbolet **Trykknap (puls)** under Betjening ser nu ud som en rigtig tavle-trykknap: rund knap i en metalkrave på en frontplade, med et skilt under (teksten "Start" kan rettes i Tegn). Knappen lyser grøn mens pulsen sendes. Trykknapper der allerede ligger i en tegning, skal indsættes igen for at få det nye udseende.

## v0.27.1 — 2026-10-13 — Elmåleren har plads til 5 cifre

- Elmåler-symbolet er gjort bredere, så displayet kan vise fx **12345.6 kWh**. Elmålere, der allerede ligger i en tegning, skal indsættes igen for at få den nye bredde.

## v0.27.0 — 2026-10-09 — Al symbol-opsætning samlet under Bindinger

- **Tegn** bruges nu kun til at tegne og give symbolet et **navn** (navnet skal være unikt; nye symboler får selv et navn). Tag og forklaring sættes ikke længere dér.
- **Bindinger** er det ene sted, hvor symboler sættes op:
  - Listen viser kun dine navngivne symboler og det, der allerede er bundet. **Vis alle elementer** viser resten.
  - Vælg et symbol, og vælg et **tag**. Så sættes symbolets klik og visning op automatisk. **Fjern tag** nulstiller det.
  - Skriv en **forklaring**, som vises som tooltip på Overview. Den kan ændres uden at gemme en ny tegningsversion.
- Fra Tegn åbner **Konfigurér under Bindinger** symbolet direkte.

## v0.26.0 — 2026-10-09 — Ryddeligere symboler: træ, navn og forklaring

- **Bindinger:** elementlisten er nu et træ. Et symbols dele (fx lampe, vippe og tekst i en vippekontakt) står indrykket under symbolet, som kan foldes sammen. Symbolerne vises med deres navn i fed. Søgefeltet finder også navne og forklaringer.
- **Navn og forklaring på symboler:** i **Tegn** kan du give det valgte element et navn (fx "Ventilator stue") og en forklaring (fx hvad den gør, og hvem der må betjene den).
  - Indsatte symboler får deres navn automatisk (Vippekontakt, Omskifter …).
  - Forklaringen vises i Bindinger og som tooltip, når man holder musen over symbolet på Overview.
- Det valgte element i Bindinger viser, hvilket symbol det er en del af, med et link til symbolet.

## v0.25.1 — 2026-10-09 — Eksterne tags følger ikke længere PLC'ens egne registre

- Et tag på en ekstern enhed, fx `plc1:mbx:1:D:1:coil:0`, skiftede også, når PLC'ens egen coil med samme nummer ændrede sig. Nu viser det kun værdien fra den eksterne enhed.

---

## v0.25.0 — 2026-10-09 — Tags fra eksterne Modbus-enheder

- Tags kan nu også hente værdier fra enheder, PLC'en taler med. Det kræver PLC-firmware 7.9.68.123 eller nyere.
  - **Extern (RS485):** fx `plc1:rtu:90:hr:0` = slave 90, HR 0.
  - **Expansion board:** fx `plc1:mbx:1:D:1:coil:0` = board 1, kanal D, slave 1, coil 0.
- De vises med et mærke i tag-listen, og alarmer, trends, energi, betjening og ugeprogrammer virker på dem som på alle andre tags.
- Eksterne værdier hentes hvert 2. sekund. En enhed, der ikke svarer, markeres som fejl på sine egne tags. Resten af PLC'en kører videre.
- Skrivning til eksterne enheder bekræftes, og værdien læses tilbage.
- SCADA'en får nu flere af PLC'ens egne registre direkte via SSE (HR op til 255, IR op til 319), så der skal polles mindre.

## v0.24.0 — 2026-10-09 — Omskifter med valgfrie positioner

- I **Tegn → Betjening** kan du indsætte en omskifter med 2–8 positioner. Skriv navnene adskilt med komma, fx "Hånd, 0, Auto" eller "1, 2, 3, 4". Der findes også en færdig omskifter med Hånd/0/Auto.
- Når du vælger et skrivbart tag, virker omskifteren med det samme på Overview:
  - Et klik viser én knap pr. position, og den aktive er markeret.
  - Den valgte positions værdi (0, 1, 2 …) skrives til PLC'en.
  - Grebet drejer til positionen.
- Positionernes værdier og navne kan rettes under **Bindinger** ("Klik: vælg position").
- **Sikkerhed:** operatører kan nu kun det, tegningen giver lov til.
  - En til/fra-knap giver ikke ret til at skrive vilkårlige værdier.
  - En omskifter kan kun skrive sine egne positioner.

## v0.23.1 — 2026-10-08

- Fejlbeskeder viser tal pænt, fx "over maksimum 100" i stedet for "100.0".

## v0.23.0 — 2026-10-08 — Fast redigeringspanel under Tags

- Når du redigerer et tag, står redigeringspanelet nu fast øverst, mens du scroller i listen. Gem og Annullér er altid synlige, og det tag du redigerer, er markeret i listen.

## v0.22.0 — 2026-10-08 — Ugeprogrammer

- Ny side **Ugeprogrammer** (tekniker og admin). Et program styrer ét skrivbart tag efter et ugeskema, fx "Hverdage 06:00–22:00 = 21 °C, ellers 17 °C" eller "Pumpe Til om natten".
- **Undtagelser** som ferie og helligdage gælder hele dage og erstatter ugeplanen.
- **Skrivning:** sker ved hvert skift og kun hvis værdien ikke allerede er sat. En manuel ændring holder derfor til næste skift.
  - Alle skrivninger står i loggen som "ugeprogram:<navn>".
  - Svarer PLC'en ikke, vises fejlen, og der prøves igen.
- **Forhåndsvisning:** viser ugen og næste skift, mens du redigerer.
- Tider følger dansk tid året rundt.
- **Beskyttelse:** et tag, der bruges i et ugeprogram, kan ikke slettes eller gøres ikke-skrivbart.
- **Backup:** ugeprogrammer kommer med.
- **Trend-CSV:** tidspunkterne er nu altid dansk tid.

## v0.21.0 — 2026-10-08 — Energirapporter

- Ny side **Energi**: forbrug og produktion i kWh pr. dag, uge eller måned, som søjlediagram og tabel med I alt. Kan hentes som CSV til Excel.
- Under **Tags → Redigér** markeres et tag som energi:
  - **Tæller** passer til fx en kWh-måler. Nulstilles måleren, regnes det med.
  - **Effekt** passer til fx W eller kW og regnes om til kWh over tid.
  - Historik skal være slået til for tagget.
- Energi-tags gemmes i 400 dage (anden historik i 30), så der kan laves måneds- og årsoversigter.
- Perioderne følger dansk tid, også ved skift til og fra sommertid.

## v0.20.1 — 2026-10-08

- Indlæsning af historik viser nu den rigtige fejlbesked (fx "Du er ikke logget ind") i stedet for "Bad Gateway".

## v0.20.0 — 2026-10-08 — Backup af trend-historik

- Under **Backup** kan trend-historikken hentes som en komprimeret fil. Det sker uden at opsamlingen stopper.
- **Indlæs historik** fletter en fil ind i den nuværende historik. Nye værdier tilføjes, og intet overskrives eller slettes. Det kan fx bruges, når der flyttes til en ny server.
- Den automatiske backup tager nu også et øjebliksbillede af historikken. De seneste 2 gemmes og kan hentes fra listen over backups på serveren.

## v0.19.0 — 2026-10-08 — Betjeningssymboler

- Ny sektion **Betjening** i Tegn: trykknap (puls), start/stop, vippekontakt, drejeomskifter 0/1, auto/manuel og setpunkt-felt.
- Indsæt symbolet og vælg et skrivbart tag. Når tegningen er gemt, virker symbolet med det samme på Overview, uden opsætning under Bindinger:
  - Klik skriver til PLC'en.
  - Lampe, vippe, greb og tekst viser tilstanden.
- Tags der ikke er skrivbare, kan ikke vælges til betjeningssymboler. Operatører kan betjene symbolerne i de tegninger, de har adgang til.

## v0.18.1 — 2026-10-08 — Stop og slet historik

- På **Trends** har tekniker og admin fået fluebenet **Administrér**. Det viser knapper ud for hvert tag:
  - **Gem** og **Stop** slår historikken til og fra. Ved Stop bevares det gemte, så det stadig kan vises.
  - **Slet** fjerner tagets gemte værdier, efter du har bekræftet det.
- Ændringer gælder med det samme: "Stop" stopper opsamlingen straks, og "Gem" begynder straks.

## v0.18.0 — 2026-10-08 — Zoom på Overview og start-tegning

- **Zoom og panorering på Overview:** brug musehjulet eller knapperne − / + og træk for at flytte rundt. På mobil og tablet zoomer man med to fingre, og **Tilpas** viser hele tegningen igen. Når man trækker hen over en knap i tegningen, betjenes den ikke. Det gør den kun ved et almindeligt klik.
- **Start-tegning:** under **Tegninger** kan en tekniker eller admin trykke **Gør til start**. Overview åbner så med den tegning for alle, der har adgang til den. Skifter man selv tegning, huskes den, så længe fanen er åben.

## v0.17.0 — 2026-10-08 — Animation "Flyt"

- Ny animation **Flyt** under Bindinger. Ved min står elementet, hvor det er tegnet, og ved max er det flyttet "Flyt X/Y" i tegningens enheder. Det passer fx til spjæld, glidere, cylindre og niveauflydere.
- Flyt kan kombineres med Rotation på samme element.

## v0.16.0 — 2026-10-08 — Symboler til solcelleanlæg

- Ny sektion **Solcelleanlæg** i Tegn med solcellepanel og -streng, sol, inverter, hybridinverter, MPPT-regulator, batteri og batteribank, DC- og AC-afbryder, overspændingsbeskyttelse, elmåler, elnet, forbrug/hus, elbillader og energiflow-pil.
- Batteriets indre felt kan bindes til **Niveau**, så det viser ladetilstanden. Solen kan bindes til **Gennemsigtighed** efter indstrålingen, og elmålerens tal kan bindes til **Tekst**.

## v0.15.0 — 2026-10-08 — Flere symboler: VVS og el

- **Tegn** har nu 59 symboler i tre sektioner med søgefelt. Hver sektion kan klappes sammen.
- **Rør og VVS:**
  - Rør og fittings: bøjninger på 90° og 45°, T-stykke, kryds, reduktion, prop, flange og strømningspil.
  - Ventiler: kugle-, kontra-, 3-vejs-, motor-, magnet-, regulerings- og sikkerhedsventil.
  - Komponenter: varmeveksler, filter, ekspansionsbeholder, radiator, ventilator og kedel.
  - Måleinstrumenter: TT/PT/FT/LT, manometer og termometer.
- **Elektrisk (ny sektion):** ledninger, kontakter, trykknap, nødstop, kontaktor, relæspole, sikring, automatsikring, motorværn, motor 3~, frekvensomformer, transformer, strømforsyning, jord, signallampe, modstand, føler, hovedafbryder og PLC.
- Brug SVG-Edits rotation eller spejling til at vende en bøjning eller et T-stykke. Manometerets viser kan animeres med **Rotation**, og termometerets søjle med **Niveau**.

## v0.14.2 — 2026-10-08 — Alle sider fylder skærmen

- Siderne er ikke længere låst til en smal kolonne på store skærme. Alle sider bruger nu hele bredden.
- **Bindinger:** Tegningen fylder den ledige højde, og sidepanelet er smallere, så tegningen bliver større.
- **Tegn:** Tegne-editoren fylder højden ned til bunden af vinduet og viser altid hele værktøjslinjen.
- **Trends:** Graferne deler den ledige højde mellem sig, og tag-listen går ned til bunden af vinduet, så siden ikke skal scrolles.
- Alt følger med, når vinduet ændres, eller du zoomer i browseren.

## v0.14.1 — 2026-10-08 — Overview fylder skærmen

- Tegningen på Overview tilpasser sig nu browservinduet. Den bruger hele bredden på store skærme og passer i højden på lave skærme, så siden ikke skal scrolles.
- Størrelsen følger med, når vinduet ændres, når du zoomer i browseren (Ctrl + / −), og når menuen fylder to linjer.

## v0.14.0 — 2026-10-08 — Flere animationer i én binding

- Under **Bindinger** samler en binding nu ét tag med en eller flere animationer, fx tekst + blink på `test01`. Hver animation har sine egne indstillinger.
- **+ Animation** tilføjer endnu en animation på samme tag og foreslår en, der ikke allerede er brugt. **×** fjerner én animation, og **Fjern binding** fjerner det hele.
- Et automatisk bundet element beholder sin binding, når du tilføjer mere. Tidligere kunne den forsvinde, når man gemte.

## v0.13.2 — 2026-10-08 — Trends: slå historik til direkte

- Gemmer intet tag historik endnu, forklarer Trends-siden nu, hvorfor alle tags er grå.
- Tekniker og admin kan trykke **Gem historik** ud for et tag direkte på Trends-siden. Tagget bliver valgt med det samme, og kurven fyldes op derfra.
- Den første måling vises som en prik i stedet for en tom graf. Det samme gælder en enkelt måling mellem to perioder uden forbindelse.

## v0.13.1 — 2026-10-08 — Renere serverlog

- Serveren skriver ikke længere fejlmeldingen "Task was destroyed but it is pending!" i loggen, hver gang en browser skifter side eller lukker. Meldingen var harmløs, men gjorde det svært at se de rigtige fejl.

## v0.13.0 — 2026-10-08 — Tekst før og efter værdien

- Tekst-bindinger under **Bindinger** har fået felterne **Tekst før** og **Tekst efter**. Fx giver "Tank : " + værdien + " liter" teksten "Tank : 1002 liter" i tegningen. Fjern fluebenet i "Vis enhed", hvis tagets egen enhed ikke skal med.
- Linjen "Vises som:" viser resultatet med tagets aktuelle værdi, og tegningen opdateres med det samme, inden du gemmer.
- Mangler værdien, vises fx "Tank : — liter", så teksten ikke springer.

## v0.12.0 — 2026-10-08 — Trends

- Under **Tags** kan historik slås til pr. tag, med et minimumsinterval mellem gemte værdier. Til/fra-signaler gemmes ved hvert skift.
- Ny side **Trends**: vælg op til 7 tags og en periode (15 min til 30 dage eller selvvalgt). Tags med samme enhed vises i samme graf; til/fra-signaler vises som trin.
- Graferne opdateres live for perioder op til 24 timer. Træk vandret for at zoome, dobbeltklik for at zoome ud.
- Brud i en kurve betyder, at der ikke var en gyldig værdi, fx fordi PLC'en ikke svarede.
- **CSV**-knappen henter de rå værdier, klar til dansk Excel.
- Historik gemmes på serveren i 30 dage (kan ændres med `SCADA_TREND_DAYS`). Backup indeholder opsætningen pr. tag, men ikke selve historikken.
- Brugere med adgang til udvalgte tegninger ser kun trends for de tags, der hører til.

## v0.11.0 — 2026-10-08 — Alarmer

- Under **Tags** kan hvert tag få alarmgrænser: HH, H, L og LL med dødbånd (så alarmen ikke blafrer) og forsinkelse — eller en alarm når et til/fra-signal er aktivt.
- SCADA'en giver også alarm, hvis en PLC holder op med at svare.
- Alarmklokken i toppen viser antal aktive og nye alarmer og blinker, indtil de er kvitteret.
- Ny side **Alarmer** med aktive alarmer og historik. Operatører kvitterer enkeltvis eller alle på én gang; det registreres hvem der kvitterede.
- I tegningerne blinker elementer rødt, når deres tag er i alarm.
- Aktive alarmer overlever en genstart af serveren, og brugere med adgang til udvalgte tegninger ser kun de alarmer der hører til.

## v0.10.0 — 2026-10-08 — Tegne-editor

- Ny side **Tegn** (tekniker og admin): tegn og ret tegninger direkte i SCADA'en med en fuld tegne-editor (SVG-Edit) — figurer, tekst, linjer, lag, farver, fortryd.
- Symbolbibliotek i ISA-101-stil: pumpe, motor, ventil, tank, værdifelt, lampe, knap og rør.
- Vælg et element og et tag i samme dropdown som under Bindinger — så bindes elementet automatisk.
- **Gem kladde** gemmer en ny version uden at ændre det operatørerne ser; **Gem og udgiv** gør den aktiv. Ældre versioner kan åbnes og udgives igen.

## v0.9.0 — 2026-10-08 — Adgang pr. tegning

- Under **Brugere** kan en viewer eller operatør begrænses til udvalgte tegninger. Brugeren ser så kun de tegninger på Overview, kun de tags der vises i dem, og kan kun betjene det der kan klikkes på i dem.
- Operatører kan generelt kun betjene tags der er sat op med en klik-handling i en tegning de har adgang til.
- Eksisterende brugere har som før adgang til alle tegninger.

## v0.8.1 — 2026-10-08 — Hurtig live-opdatering bekræftet

- Rettelsen fra v0.7.0.1 er bekræftet i drift: alle PLC-udgange og -indgange (fx DO2) opdateres nu lige så hurtigt som DO1.

## v0.8.0 — 2026-10-08 — Backup og gendannelse

- Ny side **Backup** (kun admin): hent en backup af hele opsætningen — PLC-forbindelser, tags, alle tegninger og bindinger — som én fil.
- Gendan en backup: du ser først hvad filen indeholder og skal bekræfte. Er der fejl i filen, ændres intet, og du får en liste over fejlene.
- Før hver gendannelse gemmes den nuværende opsætning automatisk på serveren, og serveren tager desuden en backup hvert døgn (de seneste 7 gemmes).
- Backuppen indeholder ikke adgangskoder eller brugere. Efter gendannelse på en ny server skal PLC-adgangskoderne indtastes igen — siden viser hvilke.
- Rettelsen af den langsomme SSE-opdatering fra v0.7.0.1 er med; den afventer stadig bekræftelse.

## v0.7.0.1 — 2026-10-08 — Fejlsøgning: hurtigere live-opdatering

- Live-værdier fra PLC'en opdateres nu hurtigt igen: SSE-strømmen overvågede kun én adresse pr. type, og ST-variabler blev kun hentet hvert 2. sekund. Nu leverer SSE alle ønskede adresser, og alt andet hentes hvert ½ sekund.
- PLC-siden viser hvor mange adresser SSE dækker.
- Afventer bekræftelse fra drift.

## v0.7.0 — 2026-10-08 — Betjening fra Overview

- Operatører kan nu betjene anlægget direkte i tegningen: klik på et element for at indtaste et setpunkt, slå noget til/fra eller sende en puls. Klik kan også åbne en anden tegning.
- Setpunkter tjekkes mod min/max, og der bedes om bekræftelse, hvor tagget er sat op til det.
- Efter hver skrivning læses værdien tilbage fra PLC'en. Har PLC'ens eget program overskrevet den, får operatøren besked i stedet for en falsk bekræftelse.
- Pulser nulstilles af serveren, selv hvis browseren lukkes.
- Under **Tags** kan et tag gøres skrivbart (kun holding registers og coils) med min/max og bekræftelse.
- I binding-editoren vælges tags nu fra en dropdown-liste.
- Ny side **Log**: hvem skrev hvad til PLC'en, og hvem ændrede opsætningen — også afviste forsøg.
- Roller: viewer kan se, operatør kan betjene, tekniker kan konfigurere, admin styrer PLC'er og brugere.

## v0.6.0 — 2026-10-08 — Binding-editor

- Ny side **Bindinger** (tekniker og admin): klik på et element i tegningen og vælg hvilket tag det skal vise, og hvordan — tekst, farve (også med grænseværdier), synlighed, blink, niveau i en tank, rotation eller gennemsigtighed.
- Ændringer vises live på tegningen med rigtige værdier, før du gemmer.
- Automatiske bindinger (id = tag-navn) kan tilpasses med ét klik.
- Bindinger til elementer, der er forsvundet i en ny version af tegningen, vises samlet og kan fjernes.

## v0.5.0 — 2026-10-07 — HTTPS

- SCADA'en kan nu nås krypteret på `https://scada.laces.dk` / `https://10.1.1.31` via nginx. Almindelig `http://` sendes automatisk videre til HTTPS.
- Certifikatet er indtil videre selvsigneret, så browseren viser en advarsel første gang. Godkend det én gang (eller installér certifikatet som betroet). Senere skiftes det til Let's Encrypt uden andre ændringer.
- Login-cookien sendes kun over HTTPS.

## v0.4.0 — 2026-10-07 — Login og brugerroller

- SCADA'en kræver nu login. Første gang oprettes brugeren `admin` med en engangsadgangskode i `/var/lib/hypervisionplc-scada/initial-admin-password.txt`, som skal skiftes ved første login.
- Fire roller: **viewer** (ser Overview, tegninger og tags), **operatør** (forberedt til betjening), **tekniker/engineer** (tegninger, tags, bindinger) og **admin** (PLC-forbindelser og brugere).
- Admin kan oprette, deaktivere og slette brugere og give nye midlertidige adgangskoder. Den sidste administrator kan ikke fjernes.
- Efter 5 forkerte login-forsøg spærres i 1 minut.
- Serveren lytter fortsat kun på localhost, indtil TLS (nginx + Let's Encrypt) er sat op.

**Næste skridt**: TLS for scada.laces.dk (nginx + certbot med deSEC), derefter fase 3 — binding-editor.

## v0.3.0 — 2026-10-07 — Overview med live SVG-tegninger

- Ny brugerflade i browseren: **Overview**, **Tegninger**, **Tags** og **PLC'er**.
- Upload SVG-tegninger (fx fra Inkscape). Farlige elementer som scripts fjernes automatisk, og du får en rapport over hvad der blev fjernet. Nye versioner kan uploades, og en ældre version kan gøres aktiv igen.
- Elementer hvis id (eller Inkscape-label) er lig et tag-navn bindes automatisk: tekst viser værdien med enhed, figurer bliver grønne når signalet er aktivt.
- Værdierne opdateres live. Mister SCADA'en forbindelsen til en PLC, bliver værdierne tydeligt nedtonet og PLC'ens fejlbesked vises øverst.
- Tags kan oprettes og foreslås fra PLC'ens ST-variabler direkte i brugerfladen; PLC-forbindelser kan tilføjes og overvåges (status, SSE, kald pr. cyklus).
- Endnu intet login — serveren lytter derfor stadig kun på localhost.

**Næste skridt**: Fase 3 — binding-editor (klik på et element og vælg tag + animation).

## v0.2.0 — 2026-10-07 — SCADA-serveren taler med PLC'en

- SCADA-serveren kan forbinde til en eller flere HypervisionPLC'er via REST og holde live-værdier opdateret: bulk-polling, og PLC'ens SSE-strøm som hurtig supplement når den er ledig.
- Tags kan oprettes med kilder som `plc1:hr:100:real`, `plc1:coil:5` eller navngivne ST-variabler (`plc1:logic:1:Niveau`) med skalering og enhed — og foreslås automatisk ud fra PLC'ens ST-programmer.
- PLC-adgangskoder gemmes kun på serveren og vises aldrig.
- Mock-PLC til test uden hardware, og installationsscript + systemd-service til Debian/Raspberry Pi.
- Endnu ingen brugerflade og intet login — API'et lytter derfor kun på localhost som standard.

**Næste skridt**: Fase 2 — SVG-upload og Overview-board med live-værdier.

## v0.1.0 — 2026-10-07 — Projektinitialisering

Projektstruktur, research og arkitektur for HypervisionPLC SCADA er på plads. Der er endnu ingen kørende kode.

**Næste skridt**: Fase 1 — backend-skelet, mock-PLC og PLC-klient (login, bulk-poll, SSE) med tag-model.
