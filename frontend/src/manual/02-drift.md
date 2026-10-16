# Drift

Under **Drift** ser og betjener du anlægget. Siderne er **Overview**, **Alarmer**, **Trends** og **Energi**.

## Overview

Overview viser en tegning af anlægget med live-værdier. Øverst vælger du **tegning**; en tegning kan være sat som **start-tegning** (se *Tegninger og Tegn*), og den åbner Overview først.

### Hvad du ser

- **Farver og former** ændrer sig efter værdierne: en pumpe er grøn, når den kører; en tank fyldes; en lampe blinker ved alarm; røret kan vise strømningsretning med løbelys.
- **Tal og tekst** viser tagets værdi, med den enhed og det antal decimaler teknikeren har valgt (fx *21,5 °C*).
- **Statuschips** øverst viser, om forbindelsen til serveren er **Live**, og om hver PLC svarer (*HypervisionPLC 10.1.1.30: ok · SSE*). Er forbindelsen væk, vises det tydeligt, og værdierne er ikke friske.
- Værdier uden kontakt til PLC'en vises som **—** eller som tegnet, så du aldrig ser en gammel værdi som om den var ny.

### Zoom og flyt

Brug **musehjulet**, **knib** på en touch-skærm eller knapperne **−**, **+** og **Tilpas** (tilpasser tegningen til vinduet). Træk i tegningen for at flytte rundt. Zoomniveauet vises som procent.

### Betjening

Elementer, der kan betjenes, reagerer på klik/tryk. Hvad der sker, afhænger af opsætningen:

| Betjening | Sådan gør du |
| --- | --- |
| **Til/fra-knap** (start/stop, vippekontakt) | Klik. Tagget skifter, og du ser resultatet, når PLC'en har bekræftet |
| **Position** (omskifter Hånd/0/Auto, ventil Åben/Lukket) | Klik symbolet, vælg den ønskede **position** i dialogen |
| **Trykknap** | Tryk. Tagget sættes Til en kort, fast tid og nulstilles igen af serveren — også hvis din browser lukker undervejs |
| **Setpunkt** | Klik feltet, skriv den nye værdi, bekræft. Serveren afviser værdier uden for tagets min/max og viser præcis hvorfor |
| **Gå til tegning** | Klik og du hopper til en anden tegning |

Er symbolet sat til at kræve **bekræftelse**, får du en dialog, hvor du skal bekræfte. Er en position **låst med kode**, skal du indtaste den firecifrede kode. Efter en skrivning vises en lille besked (*toast*) med resultatet; trykker du **OK** forsvinder den.

Et symbol kan vise tre tilstande efter en positionsændring: **bekræftet** (PLC'en har samme position), **afventer** (valideringstiden løber) og **afvigelse** (PLC'en viser noget andet — der kan komme en alarm).

> Betjening kræver rollen **Operatør** eller højere, og at tegningen er sat op til det af en tekniker. Ser du ingen dialog, når du klikker, er elementet kun til visning.

## Alarmer

Alarmklokken i topbjælken åbner siden **Alarmer**. Den har to faner:

- **Aktive** — alarmer, der er i gang lige nu. Tryk **Kvittér** på en alarm for at sige, at du har set den, eller **Kvittér alle**. En kvitteret alarm er stadig aktiv, indtil årsagen er væk.
- **Historik** — alle tidligere alarmer med tidspunkter for udløsning, kvittering og ophør.

Alarmer har en **prioritet** (lav, medium, høj). Klokken i toppen er rød ved høj prioritet, orange ved medium, og blinker, indtil alle er kvitteret.

### Hvor kommer alarmer fra?

- **Grænsealarmer** på tal-tags: *LL* (lav-lav), *L* (lav), *H* (høj) og *HH* (høj-høj), med **dødbånd** (så alarmen ikke svinger ved grænsen) og **forsinkelse** (værdien skal have været uden for grænsen så længe).
- **Til/fra-alarm** på et til/fra-tag: alarm når tagget er Til (eller Fra).
- **Kommunikationsalarm**: en PLC har ikke svaret i en periode.
- **Symbolafvigelse**: et symbol, hvor den valgte position ikke svarer til PLC'ens position (vælges i guiden, trin 4).

Alarmgrænser opsættes pr. tag under **Tags** (se *PLC'er og tags*).

## Trends

**Trends** viser kurver over værdier gennem tiden. Kun tags, hvor **historik** er slået til, har kurver (slås til under **Tags**, eller direkte på Trends-siden med **Begynd at gemme historik**).

- Vælg et eller flere **tags** i listen (søg med feltet **Søg**).
- Vælg tidsrum: **15 min, 1 time, 8 timer, 24 timer, 7 dage**, eller **Vælg periode** for et selvvalgt interval.
- Kurverne **opdateres live**. Peg på kurven for at se værdi og tidspunkt. Du kan **hente data som CSV** til regneark.
- Et tag kan **stoppes** (historikken bevares) eller dets **historik slettes**. Historik, der er ældre end opbevaringstiden (standard 30 dage), slettes automatisk.
- Hullerne i en kurve betyder, at der ikke var kontakt til PLC'en dengang.

## Energi

**Energi** viser forbrug og produktion for tags, der er markeret som **energi-tags** under **Tags → Redigér → Energi**:

- **Tæller** (fx en kWh-måler, hvis værdi bare stiger): rapporten viser forskellen mellem start og slut af perioden.
- **Effekt** (fx kW): rapporten integrerer effekten over tid.
- Feltet **Omregning til kWh** ganges på værdien, hvis måleren leverer en anden enhed.

Vælg **Dag**, **Uge** eller **Måned** (seneste 12 måneder). Den igangværende periode er markeret og ikke afsluttet. Energidata gemmes i et antal dage; tidszonen er dansk tid.
