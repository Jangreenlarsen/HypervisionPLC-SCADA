# Symbolstandard — konfiguration, visning og betjening

Besluttet af Jan 2026-10-12. Gælder for **alle** symboler i symbolbiblioteket. Interaktiv prototype:
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
| 5 Betjening | Bekræftelse; skrivemåde pr. signal: til/fra-signaler altid "sæt", registre "sæt værdi" eller "puls" (pulslængde + påkrævet hvileværdi, der ikke må være en positions værdi) |
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

Står flere animationer på samme del, vinder den nederste (rækkefølgen ændres med ▲▼).

## 5. Tilstandsmærke og betjening på Overview

Alle symboler med positioner viser samme mærke: ✓ Bekræftet, … Venter, ! Afvigelse (med skygge af
PLC'ens position), ? Ukendt (kommunikationsfejl eller ingen entydig position). Betjening sker i en
dialog der viser præcis hvilke tags der skrives; signaler der går mod 0/fra skrives først
(break-before-make). Afvigelser kan kvitteres ved at acceptere PLC'ens position (der skrives intet).

## 6. Datamodel (forslag)

`symbol_config` pr. (tegning, element): `type`, `positions[]` (label, angle), `signals[]` (id, tag, fb,
write, ms, rest), `planes[]` (signal, values[] med `null` = røres ikke), `fault`, `display`, `validate_s`,
`alarm`, `confirm`, `anims[]` (part, type, src, params, only[]). Den lokale tilstand (sidst valgt, af hvem,
hvornår) gemmes i `symbol_state`. Afledte værdier (position, tilstand) lægges i live-cachen, så
WebSocket-protokollen er uændret.
