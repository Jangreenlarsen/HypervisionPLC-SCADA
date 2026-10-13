# Symbolstandard — konfiguration, visning og betjening

**Status: vedtaget design** — besluttet af Jan 2026-10-12. Gælder for **alle** symboler i symbolbiblioteket, og al ny kode for symboler, bindinger og betjening skal følge det. Interaktiv prototype:
[docs/prototyper/symbolguide.html](prototyper/symbolguide.html) (åbn i en browser — PLC'en er simuleret).

Erstatter den nuværende model (v0.27.0), hvor ét tag pr. symbol danner bindinger for alle dele.

## 1. Et symbol

Hvert symbol i biblioteket beskriver:

| Egenskab | Indhold | Eksempel (pumpe) |
| --- | --- | --- |
| Dele | Navngivne dele animationer kan virke på | Baggrund, Pumpehus, Løbehjul, Ramme |
| Betjeningsform | Positioner (2–8 navngivne), Trykknap, Setpunkt eller kun visning | Positioner: Stop, Start |
| Særlige dele | Hvilke dele der kan rotere, vise niveau eller vise en værdi | Løbehjul kan rotere |

Symboler med positioner, trykknapper og setpunkter kan betjenes; øvrige symboler (tank, lampe, værdifelt) viser kun.

**Betjeningsformer** (vedtaget 2026-10-13):

- **Positioner** — 2–8 positioner, signaler og kontaktplaner (trin 2–3). Omskifter, start/stop, ventil.
- **Trykknap** — ét til/fra-tag sættes til 1 i N ms (100–10000, standard 500) og derefter 0; serveren nulstiller, også hvis browseren lukkes. Ingen position at vise, så intet tilstandsmærke; knappen kan lyse via en animation fra tagget.
- **Setpunkt** — operatøren indtaster en værdi til ét skrivbart tal-tag; backend afviser værdier uden for tagets min/max (ellers datatypens område) og viser den specifikke fejl. Feltet viser tagets aktuelle værdi.
- **Kun visning** — ingen betjening.
Biblioteket i prototypen: omskifter, start/stop, pumpe, motorventil, tank, lampe.

## 2. Guiden — samme 6 trin for alle symboler

Åbnes ved at klikke symbolet under Bindinger. Intet gemmes før trin 6. Trin 2 og 3 springes over
for andet end Positioner, trin 5 for Kun visning. Trykknap og Setpunkt vælger deres ene tag i trin 1.

| Trin | Indhold |
| --- | --- |
| 1 Symbol | Navn, type, dele, betjeningsform (og tag for Trykknap/Setpunkt). Omskifteren kan indlæse eksemplet "7-trins vælger, dec → bin" |
| 2 Signaler | Puljen af signaler symbolet bruger: kommando-tag (skrivbart) og valgfrit tilbagemeldings-tag. Viser hvilken plan der bruger hvert signal. Fejl/låst-tag (valgfrit) blokerer betjening |
| 3 Kontakter | Kontaktdiagram: kontaktplaner (rækker, 1–8) × positioner (kolonner). Hver plan styrer ét signal; cellen er Til/Fra/røres ikke (til/fra-signal) eller en værdi (register). Række "Aktive signaler" viser hvad hver position sætter. Skabeloner: A ét register, B ét signal pr. position, C bitmaske, D dec → bin |
| 4 Visning | Positionen følger Remote (PLC'ens tilbagemelding) eller Lokal (sidst valgte, valideret af PLC'en efter N s; afvigelse kan give alarm med valgt niveau: Nej / Lav / Medium (standard) / Høj). Vinkel pr. position (omskifter). **Animationer** (afsnit 4) |
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
- **Type** — Farve, Blink, Synlig, Drej, Flyt, og hvor delen tillader det Roterer, Niveau og Værdi.
  - **Drej**: delen drejes om sit centrum til en vinkel pr. position, eller lineært efter et tal-tag (min/max → vinkel fra/til). Fx omskiftergreb og manometerviser.
  - **Flyt**: delen forskydes dx/dy pr. position, eller lineært efter et tal-tag. Fx vippekontaktens greb.
- **Styres af** — symbolets position eller et hvilket som helst tag.
- **Parametre** efter kilden: til/fra-tag → farve for Til/Fra eller "når Til/Fra"; tal-tag → farve efter stigende grænser + "ellers", eller "når ≥ X"; Niveau → min/max; Værdi → enhed og decimaler; position → farve pr. position eller udvalgte positioner.
- **Gælder i positionerne** (kun symboler med positioner) — animationen virker kun i de afkrydsede positioner.

**Blinkfrekvens** vælges pr. blink-animation: Langsom (0,5 Hz), Normal (1 Hz, standard) eller Hurtig (2 Hz). Alle blink med samme frekvens kører i takt på tværs af symboler. Anbefaling (ISA-101): hurtigt blink til fejl og ukvitterede alarmer, langsomt til advarsler og tilstande der kræver opmærksomhed. Ved "reduceret bevægelse" i browseren vises blink som halv gennemsigtighed i stedet.

**Flyt og Drej glider** til den nye position (0,4 s) i stedet for at hoppe, så man kan se skiftet ske — fx vippekontaktens greb der skifter side. Overview opdaterer symbolet på stedet, så bevægelsen og igangværende blink ikke genstartes. Ved "reduceret bevægelse" springes glidningen over.

Står flere animationer på samme del, vinder den nederste (rækkefølgen ændres med ▲▼).

## 5. Tilstandsmærke og betjening på Overview

Alle symboler med positioner viser samme mærke: ✓ Bekræftet, … Venter, ! Afvigelse (med skygge af
PLC'ens position), ? Ukendt (kommunikationsfejl eller ingen entydig position). Betjening sker i en
dialog der viser præcis hvilke tags der skrives; signaler der går mod 0/fra skrives først
(break-before-make). Afvigelser kan kvitteres ved at acceptere PLC'ens position (der skrives intet).

**Alarmniveau**: Afvigelsesalarmen har det niveau teknikeren har valgt i trin 4 (Lav, Medium, Høj). Alarmlisten sorteres efter niveau (Høj øverst) og viser niveauet med farve. Bemærk: backend kender i dag kun high/medium — `low` skal tilføjes når standarden implementeres.

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
`alarm` ('' | low | medium | high), `op` (positions | pulse | entry | view), `pulse_ms`, `entry_tag`, `confirm`, `lock` (positions[], pin_hash, leave), `anims[]` (part, type, src, params, only[]). Den lokale tilstand (sidst valgt, af hvem,
hvornår) gemmes i `symbol_state`. Afledte værdier (position, tilstand) lægges i live-cachen, så
WebSocket-protokollen er uændret.

## 7. Test mod symbolbiblioteket i dag (2026-10-13)

Alle 82 symboler i `frontend/src/lib/symbols.ts` er importeret i prototypen (faneblad "Symbolbiblioteket
i dag"). Deres eksisterende `data-hv-auto`/`data-hv-part` oversættes automatisk til den nye model:

| I dag | I den nye model |
| --- | --- |
| `click:toggle` | 2 positioner (navne fra `true_text`/`false_text`), ét til/fra-signal, én kontaktplan |
| `click:select` | Positioner og værdier fra symbolet, ét register, én kontaktplan |
| `click:pulse` | Betjeningsform Trykknap |
| `click:write` | Betjeningsform Setpunkt |
| `fill` på en del | Farve pr. position (eller efter tagget) |
| `text` på en del | Værdi: positionens navn (eller tagværdien) |
| `move` / `rotate` på en del | Flyt / Drej pr. position eller efter tagget |
| Ingen bindinger (75 visningssymboler) | Kun visning; animationer foreslås ud fra navngivne dele (`fyld`/`soejle` → Niveau, `rotor` → Roterer, `flamme` → Synlig, `viser` → Drej, `vaerdi` → Værdi), ellers Farve på hele symbolet |

**Resultat:** 76 af 82 passede direkte; de sidste 6 dækkes af de fire tilføjelser nedenfor, som nu er en del af standarden (beskrevet i afsnit 1 og 4), så alle 82 passer. 63 symboler har ingen navngivne
dele, så kun hele symbolet kan animeres; det er nok til farve/blink/synlig, men giver fx ikke mulighed
for at farve en pumpes løbehjul for sig.

### Tilføjelser — vedtaget af Jan 2026-10-13

1. **Drej** (animation): delen drejes om sit centrum til en vinkel pr. position eller lineært efter et tal-tag (min/max → vinkel). Bruges af Omskifter Hånd/0/Auto, Drejeomskifter 0/1 og Manometer.
2. **Flyt** (animation): delen forskydes dx/dy pr. position eller efter et tag. Bruges af Vippekontakt.
3. **Trykknap** (betjeningsform): ét til/fra-tag sættes til 1 i N ms og derefter 0 (serveren nulstiller). Standarden siger i dag at til/fra-signaler altid "sættes", så en puls-trykknap kan ikke laves. Bruges af Trykknap (puls).
4. **Setpunkt** (betjeningsform): fri indtastning af en værdi til ét tal-tag inden for tagets min/max — passer ikke i positionsmodellen. Bruges af Setpunkt-felt.

Prototypen har alle fire med. Trin 1 har for importerede symboler et valg
"Betjening" (kun visning / positioner / trykknap / setpunkt), så også et visningssymbol som "Knap" kan
gøres betjenbart.

Under testen viste Elmåler (kWh) sig at være for smal til 5 cifre; symbolet er rettet i v0.27.1 (hus 130, display 110).
