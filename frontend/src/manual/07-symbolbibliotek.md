<!-- GENERERET af src/lib/manualGen.test.ts ud fra symbolbiblioteket — ret ikke i hånden; kør GEN_MANUAL=1 npx vitest run src/lib/manualGen.test.ts -->
# Symbolbiblioteket

Biblioteket har **94 symboler** i 6 kategorier. Du sætter dem ind i **Tegn** og sætter dem op med **guiden i 6 trin** (se *Symboler og guiden*). Kolonnen **Kan sættes op som** viser de betjeningsformer, guiden som standard tilbyder for symbolet; **Vis alle betjeningsformer** i guidens trin 1 åbner for resten.

## Betjening (skriver til PLC)

| Symbol | Kan sættes op som | Bemærkning |
| --- | --- | --- |
| **Trykknap (puls)** | Interaktiv betjening, Trykknap (puls) | Sender en kort puls (500 ms) — fx start, stop, kvittér. Vælg et skrivbart tag |
| **Start/stop (til/fra)** | Interaktiv betjening, Trykknap (puls) | Skifter tagget til/fra med bekræftelse; lampen og teksten viser tilstanden |
| **Vippekontakt** | Interaktiv betjening, Trykknap (puls) | Til/fra uden bekræftelse — vippen flytter sig og skifter farve |
| **Omskifter Hånd/0/Auto** | Interaktiv betjening | Vælg position i en dialog (værdi 0/1/2). Andre positioner: brug "Omskifter med egne positioner" nedenfor |
| **Vippekontakt ON/OFF (klassisk)** | Interaktiv betjening | Klassisk vippekontakt — vælg position i en dialog (OFF = 0, ON = 1); grebet vipper op (ON) eller ned (OFF) |
| **Vippekontakt ON/OFF/ON (klassisk)** | Interaktiv betjening | Klassisk vippekontakt med midterstilling — OFF = 0 (midt), ON 1 = 1 (op), ON 2 = 2 (ned) |
| **Drejeomskifter 0/1** | Interaktiv betjening | Til/fra med bekræftelse — grebet drejer mellem 0 og 1 |
| **Auto/Manuel** | Interaktiv betjening | Skifter driftsform (til = AUTO) med bekræftelse |
| **Setpunkt-felt** | Setpunkt (indtastning) | Klik for at indtaste en ny værdi (min/max fra tagget) — viser den aktuelle værdi |

## Proces og visning

| Symbol | Kan sættes op som | Bemærkning |
| --- | --- | --- |
| **Statusfelt** | Kun passiv visning | Knyt til et register: farven følger værdien (Fyldfarve) — ret teksten i Tegn |
| **Pumpe** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Løbehjulet drejer, når pumpen kører (Roterer); pilen viser pumperetningen — drej symbolet for at vende den |
| **Trendgraf** | Kun passiv visning | Kurve eller søjler med historikken for 1–4 tags — opsæt i guiden (sektionen Graf) |
| **Motor** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Bind "Fyldfarve" til drift-signalet |
| **Tank** | Kun passiv visning | Bind "Niveau" på det indre rektangel |
| **Værdifelt** | Kun passiv visning | Bind "Tekst" på teksten |
| **Lampe** | Kun passiv visning | Bind "Fyldfarve" til signalet |
| **Knap** | Kun passiv visning, Interaktiv betjening, Trykknap (puls), Setpunkt (indtastning) | Bind "Klik: til/fra" eller "Klik: puls" |

## Rør og VVS

| Symbol | Kan sættes op som | Bemærkning |
| --- | --- | --- |
| **3-vejs motorventil (AB i midten)** | Kun passiv visning, Interaktiv betjening | AB nederst, A til venstre og B til højre — portene farves hver for sig (AB → A eller AB → B); opsæt med guiden |
| **Rør (vandret)** | Kun passiv visning | Træk i enderne for at forlænge |
| **Rør (lodret)** | Kun passiv visning | Træk i enderne for at forlænge |
| **Bøjning 90°** | Kun passiv visning | Rotér/spejl i Tegn for at vende den |
| **Bøjning 45°** | Kun passiv visning | Rotér/spejl i Tegn for at vende den |
| **T-stykke** | Kun passiv visning | Rotér i Tegn for at vende afgreningen. Hvert rør kan få sit eget løbelys |
| **Kryds** | Kun passiv visning | Fire rør mødes. Hvert rør kan få sit eget løbelys |
| **Reduktion** | Kun passiv visning | Overgang fra stort til lille rør |
| **Prop/endedæksel** | Kun passiv visning | Afslutning af et rør |
| **Flangesamling** | Kun passiv visning | Samling mellem to rør |
| **Strømningsretning** | Kun passiv visning | Læg på et rør; bind evt. "Synlighed" til pumpedrift |
| **Ventil (manuel)** | Kun passiv visning | Bind "Fyldfarve" til åben/lukket |
| **Kugleventil** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Bind "Fyldfarve" til åben/lukket |
| **Kontraventil** | Kun passiv visning | Tillader kun strømning i pilens retning |
| **3-vejs ventil** | Kun passiv visning | Bind "Fyldfarve" pr. port eller på hele ventilen |
| **3-vejs motorventil** | Kun passiv visning, Interaktiv betjening | Portene A, B og AB farves hver for sig (fx AB → A eller AB → B) — opsæt med guiden |
| **Motorventil** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Bind "Fyldfarve" til åben/lukket |
| **Magnetventil** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Bind "Fyldfarve" til spolen |
| **Reguleringsventil** | Kun passiv visning, Setpunkt (indtastning) | Bind "Tekst" (åbning %) i et værdifelt ved siden af |
| **Sikkerhedsventil** | Kun passiv visning | Indløb nedefra, afgang til højre |
| **Varmeveksler** | Kun passiv visning | Bind "Fyldfarve" til drift |
| **Filter/snavssamler** | Kun passiv visning | Bind "Fyldfarve" til f.eks. tilstoppet-alarm |
| **Ekspansionsbeholder** | Kun passiv visning | Bind "Tekst" (tryk) i et værdifelt ved siden af |
| **Radiator** | Kun passiv visning | Bind "Fyldfarve" til varme til/fra |
| **Ventilator/blæser** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Bind "Fyldfarve" til drift, evt. "Rotation" på rotoren |
| **Kedel/fyr** | Kun passiv visning | Sæt "Blafrer" (eller "Farve") på flammen til brænderdrift |
| **Varmepumpe** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Bind "Roterer" på rotoren og "Fyldfarve" på lampen til drift |
| **Temperatur (TT)** | Kun passiv visning, Interaktiv betjening, Trykknap (puls), Setpunkt (indtastning) | ISA-boble; værdien vises i et værdifelt |
| **Tryk (PT)** | Kun passiv visning, Interaktiv betjening, Trykknap (puls), Setpunkt (indtastning) | ISA-boble; værdien vises i et værdifelt |
| **Flow (FT)** | Kun passiv visning, Interaktiv betjening, Trykknap (puls), Setpunkt (indtastning) | ISA-boble; værdien vises i et værdifelt |
| **Niveau (LT)** | Kun passiv visning, Interaktiv betjening, Trykknap (puls), Setpunkt (indtastning) | ISA-boble; værdien vises i et værdifelt |
| **Manometer** | Kun passiv visning | Bind "Rotation" på viseren (fx min -120°, max 120°) |
| **Termometer** | Kun passiv visning | Bind "Niveau" på søjlen (min/max = måleområdet) |

## Elektrisk

| Symbol | Kan sættes op som | Bemærkning |
| --- | --- | --- |
| **Ledning (vandret)** | Kun passiv visning | Træk i enderne for at forlænge; bind "Stregfarve" til spænding |
| **Ledning (lodret)** | Kun passiv visning | Træk i enderne for at forlænge; bind "Stregfarve" til spænding |
| **Forbindelsespunkt** | Kun passiv visning | Hvor ledninger er forbundet |
| **Klemme** | Kun passiv visning | Klemmerække/tilslutning — ret nummeret i Tegn |
| **Sluttekontakt (NO)** | Kun passiv visning, Interaktiv betjening, Trykknap (puls), Setpunkt (indtastning) | Bind "Stregfarve" til kontaktens tilstand |
| **Brydekontakt (NC)** | Kun passiv visning, Interaktiv betjening, Trykknap (puls), Setpunkt (indtastning) | Bind "Stregfarve" til kontaktens tilstand |
| **Trykknap (NO)** | Kun passiv visning, Interaktiv betjening, Trykknap (puls), Setpunkt (indtastning) | Bind "Klik: puls" for at betjene fra SCADA |
| **Nødstop** | Kun passiv visning, Interaktiv betjening, Trykknap (puls), Setpunkt (indtastning) | Bind "Fyldfarve"/"Blink" til aktiveret nødstop |
| **Kontaktor 3-polet** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Bind "Stregfarve" til kontaktorens tilbagemelding |
| **Kontakt 2-polet** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Knivene lukker, når tagget er Til (guiden foreslår "Drej" på hver kniv) |
| **Kontakt 3-polet** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Knivene lukker, når tagget er Til (guiden foreslår "Drej" på hver kniv) |
| **Relæ-/kontaktorspole** | Kun passiv visning, Interaktiv betjening, Trykknap (puls), Setpunkt (indtastning) | Bind "Fyldfarve" til spolen er aktiv |
| **Sikring** | Kun passiv visning | Bind "Stregfarve"/"Blink" til sikring sprunget |
| **Automatsikring** | Kun passiv visning | Bind "Stregfarve" til slået fra |
| **Motorværn** | Kun passiv visning | Bind "Blink" til udløst motorværn |
| **Motor 3~** | Kun passiv visning | Bind "Fyldfarve" til drift |
| **Frekvensomformer** | Kun passiv visning, Interaktiv betjening, Trykknap (puls), Setpunkt (indtastning) | Bind "Tekst" (Hz) i et værdifelt ved siden af |
| **Transformer** | Kun passiv visning | Fx 400/24 V |
| **Strømforsyning** | Kun passiv visning | AC/DC, fx 230 V~ → 24 V= |
| **Jord** | Kun passiv visning | Beskyttelsesjord |
| **Signallampe** | Kun passiv visning | Bind "Fyldfarve" til lampen |
| **Modstand** | Kun passiv visning | Fx varmelegeme — bind "Fyldfarve" til til/fra |
| **Føler (nærhed)** | Kun passiv visning | Bind "Fyldfarve" til føler aktiv |
| **Hovedafbryder** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Bind "Stregfarve" til slået til/fra |
| **PLC** | Kun passiv visning | Bind "Fyldfarve" på feltet til PLC-forbindelse ok |

## Solcelleanlæg

| Symbol | Kan sættes op som | Bemærkning |
| --- | --- | --- |
| **Solcellepanel** | Kun passiv visning | Bind "Fyldfarve" til produktion, eller vis effekten i et værdifelt |
| **Solcellestreng** | Kun passiv visning | Flere paneler i serie — kopiér for flere strenge |
| **Sol/indstråling** | Kun passiv visning | Bind "Gennemsigtighed" til indstråling (W/m²) |
| **Inverter** | Kun passiv visning | DC → AC; bind "Fyldfarve" til drift/fejl |
| **Hybridinverter** | Kun passiv visning | PV + batteri + net i én enhed |
| **MPPT-regulator** | Kun passiv visning | Laderegulator mellem paneler og batteri |
| **Batteri** | Kun passiv visning | Bind "Niveau" på det indre felt til ladetilstand (SOC %) |
| **Batteribank** | Kun passiv visning | Flere battericeller i serie (elektrisk symbol) |
| **DC-afbryder** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Bind "Stregfarve" til slået til/fra |
| **AC-afbryder** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Bind "Stregfarve" til slået til/fra |
| **Overspændingsbeskyttelse** | Kun passiv visning | SPD/afleder mod jord |
| **Elmåler (kWh)** | Kun passiv visning | Bind "Tekst" på tallet til energi/effekt |
| **Elnet** | Kun passiv visning | Forsyningsnettet; bind "Stregfarve" til import/eksport |
| **Forbrug/hus** | Kun passiv visning | Husstandens forbrug — vis effekten i et værdifelt |
| **Elbillader** | Kun passiv visning, Interaktiv betjening, Trykknap (puls) | Bind "Fyldfarve" til ladning i gang |
| **Energiflow-pil** | Kun passiv visning | Bind "Synlighed" (fx kun ved eksport) eller "Fyldfarve" |

## Genveje (gå til side)

| Symbol | Kan sættes op som | Bemærkning |
| --- | --- | --- |
| **Gå til Alarmer** | Kun passiv visning | Klik i Overview åbner Alarmer; mærket viser antal aktive alarmer (rødt og blinkende når ukvitteret) |
| **Gå til Trends** | Kun passiv visning | Klik i Overview åbner Trends |
| **Gå til Energi** | Kun passiv visning | Klik i Overview åbner Energi |

> Symboler uden betjening (rør, tank, målere, lamper, solcelledele) viser kun. Rør og fittings kan få **Løbelys**, der viser strømningsretning.
