<!-- GENERERET af src/lib/manualGen.test.ts ud fra symbolbiblioteket — ret ikke i hånden; kør GEN_MANUAL=1 npx vitest run src/lib/manualGen.test.ts -->
# Symbolbiblioteket

Biblioteket har **89 symboler** i 6 kategorier. Du sætter dem ind i **Tegn** og sætter dem op med **guiden i 6 trin** (se *Symboler og guiden*). Kolonnen **Kan sættes op som** viser de betjeningsformer, guiden som standard tilbyder for symbolet; **Vis alle betjeningsformer** i guidens trin 1 åbner for resten.

## Betjening (skriver til PLC)

| Symbol | Kan sættes op som | Bemærkning |
| --- | --- | --- |
| **Trykknap (puls)** | Positioner, Trykknap (puls) | Sender en kort puls (500 ms) — fx start, stop, kvittér. Vælg et skrivbart tag |
| **Start/stop (til/fra)** | Positioner, Trykknap (puls) | Skifter tagget til/fra med bekræftelse; lampen og teksten viser tilstanden |
| **Vippekontakt** | Positioner, Trykknap (puls) | Til/fra uden bekræftelse — vippen flytter sig og skifter farve |
| **Omskifter Hånd/0/Auto** | Positioner | Vælg position i en dialog (værdi 0/1/2). Andre positioner: brug "Omskifter med egne positioner" nedenfor |
| **Drejeomskifter 0/1** | Positioner | Til/fra med bekræftelse — grebet drejer mellem 0 og 1 |
| **Auto/Manuel** | Positioner | Skifter driftsform (til = AUTO) med bekræftelse |
| **Setpunkt-felt** | Setpunkt (indtastning) | Klik for at indtaste en ny værdi (min/max fra tagget) — viser den aktuelle værdi |

## Proces og visning

| Symbol | Kan sættes op som | Bemærkning |
| --- | --- | --- |
| **Statusfelt** | Kun visning | Knyt til et register: farven følger værdien (Fyldfarve) — ret teksten i Tegn |
| **Pumpe** | Kun visning, Positioner, Trykknap (puls) | Løbehjulet drejer, når pumpen kører (Roterer); pilen viser pumperetningen — drej symbolet for at vende den |
| **Motor** | Kun visning, Positioner, Trykknap (puls) | Bind "Fyldfarve" til drift-signalet |
| **Tank** | Kun visning | Bind "Niveau" på det indre rektangel |
| **Værdifelt** | Kun visning | Bind "Tekst" på teksten |
| **Lampe** | Kun visning | Bind "Fyldfarve" til signalet |
| **Knap** | Kun visning, Positioner, Trykknap (puls), Setpunkt (indtastning) | Bind "Klik: til/fra" eller "Klik: puls" |

## Rør og VVS

| Symbol | Kan sættes op som | Bemærkning |
| --- | --- | --- |
| **3-vejs motorventil (AB i midten)** | Kun visning, Positioner | AB nederst, A til venstre og B til højre — portene farves hver for sig (AB → A eller AB → B); opsæt med guiden |
| **Rør (vandret)** | Kun visning | Træk i enderne for at forlænge |
| **Rør (lodret)** | Kun visning | Træk i enderne for at forlænge |
| **Bøjning 90°** | Kun visning | Rotér/spejl i Tegn for at vende den |
| **Bøjning 45°** | Kun visning | Rotér/spejl i Tegn for at vende den |
| **T-stykke** | Kun visning | Rotér i Tegn for at vende afgreningen. Hvert rør kan få sit eget løbelys |
| **Kryds** | Kun visning | Fire rør mødes. Hvert rør kan få sit eget løbelys |
| **Reduktion** | Kun visning | Overgang fra stort til lille rør |
| **Prop/endedæksel** | Kun visning | Afslutning af et rør |
| **Flangesamling** | Kun visning | Samling mellem to rør |
| **Strømningsretning** | Kun visning | Læg på et rør; bind evt. "Synlighed" til pumpedrift |
| **Ventil (manuel)** | Kun visning | Bind "Fyldfarve" til åben/lukket |
| **Kugleventil** | Kun visning, Positioner, Trykknap (puls) | Bind "Fyldfarve" til åben/lukket |
| **Kontraventil** | Kun visning | Tillader kun strømning i pilens retning |
| **3-vejs ventil** | Kun visning | Bind "Fyldfarve" pr. port eller på hele ventilen |
| **3-vejs motorventil** | Kun visning, Positioner | Portene A, B og AB farves hver for sig (fx AB → A eller AB → B) — opsæt med guiden |
| **Motorventil** | Kun visning, Positioner, Trykknap (puls) | Bind "Fyldfarve" til åben/lukket |
| **Magnetventil** | Kun visning, Positioner, Trykknap (puls) | Bind "Fyldfarve" til spolen |
| **Reguleringsventil** | Kun visning, Setpunkt (indtastning) | Bind "Tekst" (åbning %) i et værdifelt ved siden af |
| **Sikkerhedsventil** | Kun visning | Indløb nedefra, afgang til højre |
| **Varmeveksler** | Kun visning | Bind "Fyldfarve" til drift |
| **Filter/snavssamler** | Kun visning | Bind "Fyldfarve" til f.eks. tilstoppet-alarm |
| **Ekspansionsbeholder** | Kun visning | Bind "Tekst" (tryk) i et værdifelt ved siden af |
| **Radiator** | Kun visning | Bind "Fyldfarve" til varme til/fra |
| **Ventilator/blæser** | Kun visning, Positioner, Trykknap (puls) | Bind "Fyldfarve" til drift, evt. "Rotation" på rotoren |
| **Kedel/fyr** | Kun visning | Sæt "Blafrer" (eller "Farve") på flammen til brænderdrift |
| **Varmepumpe** | Kun visning, Positioner, Trykknap (puls) | Bind "Roterer" på rotoren og "Fyldfarve" på lampen til drift |
| **Temperatur (TT)** | Kun visning, Positioner, Trykknap (puls), Setpunkt (indtastning) | ISA-boble; værdien vises i et værdifelt |
| **Tryk (PT)** | Kun visning, Positioner, Trykknap (puls), Setpunkt (indtastning) | ISA-boble; værdien vises i et værdifelt |
| **Flow (FT)** | Kun visning, Positioner, Trykknap (puls), Setpunkt (indtastning) | ISA-boble; værdien vises i et værdifelt |
| **Niveau (LT)** | Kun visning, Positioner, Trykknap (puls), Setpunkt (indtastning) | ISA-boble; værdien vises i et værdifelt |
| **Manometer** | Kun visning | Bind "Rotation" på viseren (fx min -120°, max 120°) |
| **Termometer** | Kun visning | Bind "Niveau" på søjlen (min/max = måleområdet) |

## Elektrisk

| Symbol | Kan sættes op som | Bemærkning |
| --- | --- | --- |
| **Ledning (vandret)** | Kun visning | Træk i enderne for at forlænge; bind "Stregfarve" til spænding |
| **Ledning (lodret)** | Kun visning | Træk i enderne for at forlænge; bind "Stregfarve" til spænding |
| **Forbindelsespunkt** | Kun visning | Hvor ledninger er forbundet |
| **Klemme** | Kun visning | Klemmerække/tilslutning — ret nummeret i Tegn |
| **Sluttekontakt (NO)** | Kun visning, Positioner, Trykknap (puls), Setpunkt (indtastning) | Bind "Stregfarve" til kontaktens tilstand |
| **Brydekontakt (NC)** | Kun visning, Positioner, Trykknap (puls), Setpunkt (indtastning) | Bind "Stregfarve" til kontaktens tilstand |
| **Trykknap (NO)** | Kun visning, Positioner, Trykknap (puls), Setpunkt (indtastning) | Bind "Klik: puls" for at betjene fra SCADA |
| **Nødstop** | Kun visning, Positioner, Trykknap (puls), Setpunkt (indtastning) | Bind "Fyldfarve"/"Blink" til aktiveret nødstop |
| **Kontaktor 3-polet** | Kun visning, Positioner, Trykknap (puls) | Bind "Stregfarve" til kontaktorens tilbagemelding |
| **Relæ-/kontaktorspole** | Kun visning, Positioner, Trykknap (puls), Setpunkt (indtastning) | Bind "Fyldfarve" til spolen er aktiv |
| **Sikring** | Kun visning | Bind "Stregfarve"/"Blink" til sikring sprunget |
| **Automatsikring** | Kun visning | Bind "Stregfarve" til slået fra |
| **Motorværn** | Kun visning | Bind "Blink" til udløst motorværn |
| **Motor 3~** | Kun visning | Bind "Fyldfarve" til drift |
| **Frekvensomformer** | Kun visning, Positioner, Trykknap (puls), Setpunkt (indtastning) | Bind "Tekst" (Hz) i et værdifelt ved siden af |
| **Transformer** | Kun visning | Fx 400/24 V |
| **Strømforsyning** | Kun visning | AC/DC, fx 230 V~ → 24 V= |
| **Jord** | Kun visning | Beskyttelsesjord |
| **Signallampe** | Kun visning | Bind "Fyldfarve" til lampen |
| **Modstand** | Kun visning | Fx varmelegeme — bind "Fyldfarve" til til/fra |
| **Føler (nærhed)** | Kun visning | Bind "Fyldfarve" til føler aktiv |
| **Hovedafbryder** | Kun visning, Positioner, Trykknap (puls) | Bind "Stregfarve" til slået til/fra |
| **PLC** | Kun visning | Bind "Fyldfarve" på feltet til PLC-forbindelse ok |

## Solcelleanlæg

| Symbol | Kan sættes op som | Bemærkning |
| --- | --- | --- |
| **Solcellepanel** | Kun visning | Bind "Fyldfarve" til produktion, eller vis effekten i et værdifelt |
| **Solcellestreng** | Kun visning | Flere paneler i serie — kopiér for flere strenge |
| **Sol/indstråling** | Kun visning | Bind "Gennemsigtighed" til indstråling (W/m²) |
| **Inverter** | Kun visning | DC → AC; bind "Fyldfarve" til drift/fejl |
| **Hybridinverter** | Kun visning | PV + batteri + net i én enhed |
| **MPPT-regulator** | Kun visning | Laderegulator mellem paneler og batteri |
| **Batteri** | Kun visning | Bind "Niveau" på det indre felt til ladetilstand (SOC %) |
| **Batteribank** | Kun visning | Flere battericeller i serie (elektrisk symbol) |
| **DC-afbryder** | Kun visning, Positioner, Trykknap (puls) | Bind "Stregfarve" til slået til/fra |
| **AC-afbryder** | Kun visning, Positioner, Trykknap (puls) | Bind "Stregfarve" til slået til/fra |
| **Overspændingsbeskyttelse** | Kun visning | SPD/afleder mod jord |
| **Elmåler (kWh)** | Kun visning | Bind "Tekst" på tallet til energi/effekt |
| **Elnet** | Kun visning | Forsyningsnettet; bind "Stregfarve" til import/eksport |
| **Forbrug/hus** | Kun visning | Husstandens forbrug — vis effekten i et værdifelt |
| **Elbillader** | Kun visning, Positioner, Trykknap (puls) | Bind "Fyldfarve" til ladning i gang |
| **Energiflow-pil** | Kun visning | Bind "Synlighed" (fx kun ved eksport) eller "Fyldfarve" |

## Genveje (gå til side)

| Symbol | Kan sættes op som | Bemærkning |
| --- | --- | --- |
| **Gå til Alarmer** | Kun visning | Klik i Overview åbner Alarmer; mærket viser antal aktive alarmer (rødt og blinkende når ukvitteret) |
| **Gå til Trends** | Kun visning | Klik i Overview åbner Trends |
| **Gå til Energi** | Kun visning | Klik i Overview åbner Energi |

> Symboler uden betjening (rør, tank, målere, lamper, solcelledele) viser kun. Rør og fittings kan få **Løbelys**, der viser strømningsretning.
