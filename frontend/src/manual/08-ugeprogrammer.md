# Ugeprogrammer

Et **ugeprogram** skriver automatisk en værdi til et tag på bestemte tidspunkter hver uge — fx *komforttemperatur kl. 6–22 på hverdage, nedsat resten af tiden*, eller *tænd belysningen om aftenen*. Siden **Ugeprogrammer** (rollen tekniker) ligger under **Opsætning**.

## Opret et ugeprogram

Tryk **+ Nyt ugeprogram** og udfyld:

| Felt | Betydning |
| --- | --- |
| **Navn** | Fx *Komfort stue* |
| **Note** | Fri tekst |
| **Tag (skal være skrivbart)** | Det tag der skrives til. Er det et tal-tag, vises dets tilladte område under feltet |
| **Perioder** | Hver periode har **dage** (mandag–søndag, tryk for at vælge), **Fra** og **Til** (tid, `TT:MM`) og en **Værdi** |
| **Uden for perioderne** | Værdien resten af tiden. **Tom = rør ikke tagget** uden for perioderne |
| **Undtagelser** | Fx ferie og helligdage: **Fra dato** og **Til dato** og en værdi. Gælder hele dage og **erstatter ugeplanen**. Tom værdi = værdien *uden for perioderne* |

Tiderne er **dansk tid**. En periode som `22:00–06:00` går over midnat. Bruger du `24:00` som slut, gælder perioden til midnat. **Overlapper perioder, gælder den nederste.**

Tryk **Vis forhåndsvisning** for at se ugen som en oversigt, og hvad værdien er **lige nu**, før du gemmer.

## Sådan skriver et ugeprogram

Programmet skriver **ved hvert skift** (når en periode starter eller slutter) — og **kun hvis værdien ikke allerede er sat**. Derfor holder en manuel ændring, du selv laver fra Overview, helt til næste skift. Kan PLC'en ikke nås, prøver programmet igen lidt senere, og fejlen vises ved programmet (*Kunne ikke skrive … prøver igen om lidt*). Skrivningerne står i **Log**.

Et ugeprogram kan **slås fra** og **redigeres** uden at slettes. Et tag, der bruges af et ugeprogram, kan ikke slettes.

## Eksempel: komfort på hverdage

| Felt | Værdi |
| --- | --- |
| Tag | `Stue_Setpunkt` (register, 0–30 °C) |
| Periode 1 | Man–Fre, 06:00–22:00, værdi 21 |
| Periode 2 | Lør–Søn, 08:00–23:00, værdi 21 |
| Uden for perioderne | 17 |
| Undtagelse | Fra 20.12 til 02.01, værdi 17 |
