# Symboler og guiden i 6 trin

Alle symboler i biblioteket sættes op på samme måde: med **guiden i 6 trin**. Du åbner den fra **Tegn** (vælg symbolet, **Opsæt symbol (6 trin)**) eller fra **Bindinger** (vælg symbolet, **Opsæt symbol**/**Ret symbol**). Intet gemmes, før du trykker **Gem** i trin 6. En rød prik ved et trin betyder, at det har en fejl; serveren kontrollerer hele opsætningen løbende og forklarer præcis, hvad der mangler.

## De seks trin

| Trin | Hvad du gør |
| --- | --- |
| **1. Symbol** | Vælg **betjeningsform** (se nedenfor). Kun de former, der giver mening for symbolet, vises; **Vis alle betjeningsformer** åbner for resten. Knappen *Foreslå ud fra symbolet* henter et forslag ud fra de gamle bindinger |
| **2. Signaler** | Vælg de tags symbolet skriver (**Kommando**) og evt. læser tilbage (**Tilbagemelding**). **Skrives som**: *Sæt* (til/fra eller værdi) eller *Puls* (kort impuls med en fast **hvile**-værdi bagefter). Et valgfrit **Fejlsignal** spærrer betjeningen, når det er Til |
| **3. Kontakter** | Kun for positioner. Et **kontaktdiagram** fortæller, hvad hver position sætter: hver *plan* styrer ét signal, og hver celle er *Til*, *Fra*, *røres ikke* (til/fra) eller en **værdi** (register). Skabeloner A–D laver typiske mønstre: A = tallet 0,1,2 …; B = ét signal pr. position; C = bit-mønster; D = tal omsat til binære signaler |
| **4. Visning** | **Vis**: *PLC'ens position* (tilbagemeldingen) eller *valgt position*. **Tid til at bekræfte**: hvor længe PLC'en må om at følge efter. **Alarm ved afvigelse/fejl**. Her laver du også **logikblokke** og **animationer** |
| **5. Betjening** | **Operatøren skal bekræfte** før der skrives. **Pulslængde** (trykknapper). **Nøglelås**: vælg hvilke positioner der kræver en **kode** (4 cifre) |
| **6. Test og gem** | Se **live** værdier for signalerne og hvilken position PLC'en står på lige nu. En **skriveplan** viser præcis, hvad hver position vil skrive. Advarsler vises; **Gem** er kun muligt uden fejl |

![Trin 1 — Symbol: vælg betjeningsform](/manual/guide-1.png)

![Trin 2 — Signaler: kommando, tilbagemelding og hvordan der skrives](/manual/guide-2.png)

![Trin 3 — Kontakter: hvad hver position sætter (kontaktdiagrammet)](/manual/guide-3.png)

![Trin 4 — Visning: hurtig opsætning, logikblokke og animationer](/manual/guide-4.png)

![Trin 5 — Betjening: bekræftelse og nøglelås](/manual/guide-5.png)

![Trin 6 — Test og gem: live-værdier, fundet position og skriveplan](/manual/guide-6.png)

## Betjeningsformer

| Form | Hvad den gør | Eksempel |
| --- | --- | --- |
| **Kun visning** | Symbolet viser, men betjenes ikke | Lampe, tank, rør, 3-vejs ventil styret af én indgang |
| **Positioner** | 2–8 navngivne positioner; hver sætter et mønster af signaler | Omskifter *Hånd/0/Auto*, ventil *Åben/Lukket*, pumpe *Stop/Start* |
| **Trykknap (puls)** | Et til/fra-tag sættes Til i en fast tid (100–10000 ms), derefter Fra | Start-knap, kvittering |
| **Setpunkt** | Operatøren indtaster en værdi i et skrivbart tal-tag | Ønsket temperatur |

## Positioner og kontaktplaner

Et symbol med positioner skal vide, hvilken position PLC'en **står i** (tilbagemelding), og hvad der skal **skrives** for at skifte. Det beskrives i kontaktdiagrammet:

- **Rækker** er *planer*; hver styrer ét signal. **Kolonner** er positioner.
- Eksempel — en 3-trins vælger med ét register `Mode`: position *Hånd* = 0, *0* = 1, *Auto* = 2 (skabelon A).
- Eksempel — en 7-trins vælger, der skriver tallet 1–7 som tre bit på tre coils (skabelon D, "dec → bin").
- To positioner må ikke have samme mønster, ellers kan systemet ikke skille dem ad.

Er en **tilbagemelding** valgt for et signal, læses PLC'ens position derfra; ellers bruges kommandoen. En position **fundet** i PLC'en vises som en lille tilstand (*bekræftet*, *afventer*, *afvigelse*, *ukendt*).

## Animationer i guiden (trin 4)

Hver animation vælger en **del** af symbolet (*Port A*, *Løbehjul*, *Hele symbolet* …), en **type** (*Farve, Blink, Synlig, Roterer, Niveau, Gennemsigtighed, Værdi, Drej, Flyt, Løbelys*) og en **kilde**:

- **symbolets position** — farve, vinkel, forskydning osv. vælges **pr. position**
- **et tag** — til/fra eller tal
- **en logikblok** — se nedenfor

Står flere animationer på samme del, **vinder den nederste** (▲▼ ændrer rækkefølgen). Animationer kan også begrænses til bestemte positioner (**Gælder i**).

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

## Nøglelås

I trin 5 kan du vælge de **positioner**, der kræver en **kode** (4 cifre). Operatøren skal indtaste koden, før den position kan vælges; **Koden kræves også for at forlade en låst position** er valgfrit. Koden gemmes kun som hash på serveren, vises aldrig igen og kommer ikke med i backup — efter en gendannelse skal den sættes igen. **Fjern kode** sletter den.

## Hurtig opsætning: 3-vejs ventil

![Hurtig opsætning af en 3-vejs ventil: vælg til/fra-tagget og tryk Opret animationer](/manual/guide-hurtig.png)

De to **3-vejs motorventiler** har en **Hurtig opsætning** øverst i trin 4: vælg det **til/fra-tag**, der styrer ventilen, og tryk **Opret animationer**. Så får du tre farve-animationer: **Til** = AB → A (Port A og AB åbne), **Fra** = AB → B (Port B og AB åbne); **Port AB** er altid åben. Virker også med en indgang, du kun kan læse. Er der intet skrivbart tag valgt, sættes symbolet til *Kun visning*.

Skal ventilen **betjenes** (skifte mellem AB → A og AB → B), vælg **Positioner** i trin 1: guiden foreslår to positioner, **AB → A** og **AB → B**, med farve pr. port.

## Ret og fjern en opsætning

**Ret symbol** åbner guiden med den gemte opsætning. **Fjern konfiguration** sletter den (symbolets gamle bindinger gælder så igen). Et tag, der bruges af et symbol, kan ikke slettes under **Tags**.
