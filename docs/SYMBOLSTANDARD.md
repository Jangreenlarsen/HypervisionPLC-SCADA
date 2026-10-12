# Symbolstandard — konfiguration, visning og betjening

**Status: vedtaget design** — besluttet af Jan 2026-10-12. Gælder for **alle** symboler i symbolbiblioteket, og al ny kode for symboler, bindinger og betjening skal følge det. Interaktiv prototype:
[docs/prototyper/symbolguide.html](prototyper/symbolguide.html) (åbn i en browser — PLC'en er simuleret).

Erstatter den nuværende model (v0.27.0), hvor ét tag pr. symbol danner bindinger for alle dele.

## 1. Et symbol

Hvert symbol i biblioteket beskriver:

| Egenskab | Indhold | Eksempel (pumpe) |
| --- | --- | --- |
| Dele | Navngivne dele animationer kan virke på | Baggrund, Pumpehus, Løbehjul, Ramme |
| Positioner | 0 eller 2–8 navngivne positioner. 0 = kun visning | Stop, Start |
| Særlige dele | Hvilke dele der kan rotere, vise niveau eller vise en værdi | Løbehjul kan rotere |

Symboler med positioner kan betjenes; symboler uden positioner (tank, lampe, værdifelt) viser kun.
Biblioteket i prototypen: omskifter, start/stop, pumpe, motorventil, tank, lampe.

## 2. Guiden — samme 6 trin for alle symboler

Åbnes ved at klikke symbolet under Bindinger. Intet gemmes før trin 6. Trin 2, 3 og 5 springes over
for symboler uden positioner.

| Trin | Indhold |
| --- | --- |
| 1 Symbol | Navn, type, dele. Omskifteren kan indlæse eksemplet "7-trins vælger, dec → bin" |
| 2 Signaler | Puljen af signaler symbolet bruger: kommando-tag (skrivbart) og valgfrit tilbagemeldings-tag. Viser hvilken plan der bruger hvert signal. Fejl/låst-tag (valgfrit) blokerer betjening |
| 3 Kontakter | Kontaktdiagram: kontaktplaner (rækker, 1–8) × positioner (kolonner). Hver plan styrer ét signal; cellen er Til/Fra/røres ikke (til/fra-signal) eller en værdi (register). Række "Aktive signaler" viser hvad hver position sætter. Skabeloner: A ét register, B ét signal pr. position, C bitmaske, D dec → bin |
| 4 Visning | Positionen følger Remote (PLC'ens tilbagemelding) eller Lokal (sidst valgte, valideret af PLC'en efter N s; afvigelse kan give alarm). Vinkel pr. position (omskifter). **Animationer** (afsnit 4) |
| 5 Betjening | Bekræftelse til/fra pr. symbol og nøglelås (se afsnit 5); skrivemåde pr. signal: til/fra-signaler altid "sæt", registre "sæt værdi" eller "puls" (pulslængde + påkrævet hvileværdi, der ikke må være en positions værdi) |
| 6 Test og gem | Live-værdier pr. signal, fundet position, advarsler, oversigt over det der gemmes |

## 3. Validering (backend håndhæver; guiden viser det live)

- Kommando-tags skal være skrivbare; samme tag må ikke bruges af to signaler; tilbagemelding skal have samme type som kommandoen.
- Ét signal pr. kontaktplan; to positioner må ikke have samme kontaktmønster (planer med puls tæller ikke med).
- Register-værdier tjekkes mod tagets min/max hvis de er sat, ellers hele datatypens område (uint 0–65535, int −32768–32767).
- Puls: 100–10000 ms; hvileværdi påkrævet, heltal, inden for området og forskellig fra positionernes værdier. Mindst én plan skal "sætte" (ellers kan positionen ikke aflæses).
- Advarsler (blokerer ikke): signal der ikke bruges, celler der "røres ikke", animation der ikke gælder i nogen position.

## 4. Animationer

Et symbol kan have vilkårligt mange animationer (prototypen: 12). Hver animation har:

- **Del** — en af symbolets dele.
- **Type** — Farve, Blink, Synlig, og hvor delen tillader det Roterer, Niveau og Værdi.
- **Styres af** — symbolets position eller et hvilket som helst tag.
- **Parametre** efter kilden: til/fra-tag → farve for Til/Fra eller "når Til/Fra"; tal-tag → farve efter stigende grænser + "ellers", eller "når ≥ X"; Niveau → min/max; Værdi → enhed og decimaler; position → farve pr. position eller udvalgte positioner.
- **Gælder i positionerne** (kun symboler med positioner) — animationen virker kun i de afkrydsede positioner.

**Blinkfrekvens** vælges pr. blink-animation: Langsom (0,5 Hz), Normal (1 Hz, standard) eller Hurtig (2 Hz). Alle blink med samme frekvens kører i takt på tværs af symboler. Anbefaling (ISA-101): hurtigt blink til fejl og ukvitterede alarmer, langsomt til advarsler og tilstande der kræver opmærksomhed. Ved "reduceret bevægelse" i browseren vises blink som halv gennemsigtighed i stedet.

Står flere animationer på samme del, vinder den nederste (rækkefølgen ændres med ▲▼).

## 5. Tilstandsmærke og betjening på Overview

Alle symboler med positioner viser samme mærke: ✓ Bekræftet, … Venter, ! Afvigelse (med skygge af
PLC'ens position), ? Ukendt (kommunikationsfejl eller ingen entydig position). Betjening sker i en
dialog der viser præcis hvilke tags der skrives; signaler der går mod 0/fra skrives først
(break-before-make). Afvigelser kan kvitteres ved at acceptere PLC'ens position (der skrives intet).

**Bekræftelse kan fravælges pr. symbol** (trin 5). Et klik på symbolet på Overview betjener det:

| Bekræftelse | 2 positioner (start/stop, pumpe, ventil) | Flere positioner (omskifter) |
| --- | --- | --- |
| Til (standard) | Dialog → vælg → "Skift til …" | Dialog → vælg → "Skift til …" |
| Fra | Ét klik skifter straks til den anden position | Dialog med positionerne; et klik på en position skifter straks |

Alle skift logges i audit-loggen, og rettigheder, Fejl/låst og validering gælder uanset valget.

**Nøglelås** (trin 5) — som en nøgleomskifter:

- Teknikeren vælger hvilke positioner der er låst og sætter en 4-cifret kode for symbolet. Valgfrit: koden kræves også for at forlade en låst position.
- Vælger operatøren en låst position, beder dialogen om koden ("Lås op og skift til …") — også når bekræftelse er fravalgt; koden erstatter så bekræftelsen.
- Låste positioner har en hængelås i dialogen, og symbolet viser en hængelås når det står i en låst position.
- Koden gemmes som scrypt-hash i backend, kontrolleres kun i backend og sendes aldrig til browseren (CLAUDE.md regel 6). Kun teknikere/admin kan sætte den (skriv-kun, som PLC-adgangskoder).
- 3 forkerte koder spærrer betjening af symbolet i 60 s (pr. symbol og bruger). Audit-loggen registrerer oplåsning og forkerte forsøg — aldrig selve koden.

## 6. Datamodel (forslag)

`symbol_config` pr. (tegning, element): `type`, `positions[]` (label, angle), `signals[]` (id, tag, fb,
write, ms, rest), `planes[]` (signal, values[] med `null` = røres ikke), `fault`, `display`, `validate_s`,
`alarm`, `confirm`, `lock` (positions[], pin_hash, leave), `anims[]` (part, type, src, params, only[]). Den lokale tilstand (sidst valgt, af hvem,
hvornår) gemmes i `symbol_state`. Afledte værdier (position, tilstand) lægges i live-cachen, så
WebSocket-protokollen er uændret.
