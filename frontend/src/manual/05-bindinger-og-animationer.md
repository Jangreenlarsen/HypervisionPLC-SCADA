# Bindinger og animationer

En **binding** knytter et element i en tegning til et **tag**, og en **animation** bestemmer, hvad elementet gør, når tagget ændrer sig. Siden **Bindinger** (rollen tekniker) er stedet at gøre det.

## Siden Bindinger

![Bindinger: tegningen til venstre, det valgte elements binding (tag og animation) til højre og listen over symboler og bundne elementer](/manual/bindinger.png)

Til venstre ser du tegningen, til højre en liste over **symboler og bundne** elementer. Klik et element i tegningen — eller i listen — for at vælge det. Listen viser som standard kun navngivne symboler og elementer med bindinger; afkryds **Vis alle elementer** for at se resten. Søg med feltet øverst.

For det valgte element ser du dets bindinger. **Tilføj binding** laver en ny; **Fjern binding** sletter den. Du kan give ét element flere animationer (fx farve **og** blink).

### Automatisk binding

Hedder et element det samme som et tag (id eller label), bindes det **automatisk**, så du ikke behøver gøre noget. Tryk **Tilpas** for at ændre den automatiske binding eller give elementet flere animationer.

## Animationstyper

| Animation | Hvad den gør | Typisk brug |
| --- | --- | --- |
| **Farve** (*fill*) | Fyldfarven følger værdien: til/fra → to farver; tal → farve efter grænser (fx grøn, orange, rød) | Pumpe kører, temperatur for høj |
| **Stregfarve** (*stroke*) | Samme for omridset/stregen | Rør, ramme |
| **Synlig** | Elementet vises eller skjules | Lampe, advarselsikon |
| **Blink** | Elementet blinker (langsom 0,5 Hz, normal 1 Hz, hurtig 2 Hz) | Alarm |
| **Niveau** | En rektangel fyldes fra bunden efter min/max (kan vende) | Tank, søjle |
| **Gennemsigtighed** | Elementet bliver mere eller mindre synligt efter værdien | Fade |
| **Tekst** | Viser tagets værdi som tekst, med decimaler, enhed og evt. **beregning** | Temperatur, tæller |
| **Drej** | Elementet drejes en vinkel efter værdien (eller efter position) | Viser på manometer, omskifterstilling |
| **Flyt** | Elementet forskydes dx/dy efter værdien | Skyder, vippekontakt |
| **Roterer** | Elementet roterer kontinuerligt | Pumpehjul, blæser |
| **Løbelys** | Et lysende mønster løber langs røret og viser strømning og retning. Lysstykkernes længde og fart er de samme, uanset hvordan røret er strakt eller skaleret. Rør, bøjninger og T-stykker, der hænger sammen og bruger samme tag, kører som **ét sammenhængende lys** i samme retning (se nedenfor) | Rør med flow |

For til/fra-tags vælger du farver for **Til** og **Fra**. For tal-tags vælger du en **basisfarve** og **grænser** (*værdi og farve*). Et tal-tag kan også styre Blink, Synlig og Roterer med "aktiv når ≥ en grænse".

### Tekst: decimaler og beregning

I tekst-animationen kan du styre, hvordan tallet vises:

- **Decimaler**: antal decimaler. Tom = tagets egen indstilling; 0 = hele tal.
- **Enhed**: vis tagets enhed efter tallet eller ej.
- **Beregning**: simpel matematik på værdien, før den vises. Skriv fx `x / 10` — så vises registerværdien 128 som 12,8. Variablen hedder `x` (eller `værdi`/`parameter`). Du kan bruge `+ − * / %`, parenteser og funktionerne `abs`, `round`, `floor`, `ceil`, `sqrt`, `min` og `max` (flere værdier adskilles med semikolon: `min(x; 100)`). Tal skrives med komma eller punktum.

| Beregning | Værdi 128 giver |
| --- | --- |
| `x / 10` | 12,8 |
| `x * 1,8 + 32` (°C → °F) | 262,4 |
| `round(x / 10)` | 13 |
| `max(x - 100; 0)` | 28 |

Er udtrykket ugyldigt, får du en forklaring med det samme, og det kan ikke gemmes. Division med nul vises som **—**. Decimaler og enhed gælder resultatet.

## Klik-handlinger

Et element kan også **betjenes** fra Overview. Vælg en klik-handling i stedet for en visning:

| Handling | Resultat |
| --- | --- |
| **Skriv værdi** | Klik åbner en dialog, hvor operatøren indtaster en værdi (setpunkt) |
| **Skift til/fra** | Klik skifter et til/fra-tag |
| **Puls** | Klik sætter tagget Til en kort tid og så Fra igen |
| **Vælg position** | Klik åbner et valg mellem faste værdier |
| **Gå til tegning** | Klik hopper til en anden tegning |

Tagget skal være **skrivbart** (afkrydset *Betjening* under Tags), og operatøren skal have rollen operatør. Skriveadgang kan også indskrænkes pr. tegning og pr. element.

## Symboler med bindinger

![Et valgt symbol under Bindinger med knappen Opsæt symbol (6 trin) og feltet Forklaring](/manual/bindinger-symbol.png)

For symboler fra biblioteket sættes alt op i **guiden** (se næste kapitel). Vælg symbolet i listen og tryk **Opsæt symbol (6 trin)** — eller **Ret symbol**, hvis det allerede er sat op. Her kan du også skrive en **Forklaring**, som vises som tooltip på Overview. Er et symbol sat op med guiden, bruges symbolets egne bindinger ikke.

## Forsvundne elementer

Fjerner en ny version et element, der havde bindinger, vises det under **Forsvundne elementer**, og du kan **Fjerne bindinger** for dem.

### Løbelys over flere rør

Løbelys på flere dele, hvis ender rører hinanden (inden for ca. en rørbredde), og som har **samme tag** (og samme retnings-tag og tilstand), kører som **ét sammenhængende forløb**: lys og mørke fortsætter hen over samlingerne, og alle delene kører samme vej. Det er ligegyldigt, hvilken vej de enkelte rør er tegnet — retningen bestemmes af flertallet af delene. Kører hele forløbet den forkerte vej, så sæt **Vend retning** på alle delene (fx med *Opsæt de valgte samlet* i Tegn). Har delene forskellig lyslængde eller fart, bruger hele forløbet den, flest dele har. Et T-stykkes gennemløb og afgrening indgår hver for sig; et T-stykke med et valgt rør (*krydsning*) beholder sine egne retninger.
