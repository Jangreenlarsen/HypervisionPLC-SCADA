# Drift

Under **Drift** ser og betjener du anlægget. Siderne er **Overview**, **Alarmer**, **Trends** og **Energi**.

## Overview

![Overview: en tegning med live-værdier, zoomknapper og status for forbindelsen til PLC'en](/manual/overview.png)

Overview viser en tegning af anlægget med live-værdier. Øverst vælger du **tegning**; en tegning kan være sat som **start-tegning** (se *Tegninger og Tegn*), og den åbner Overview først.

### Hvad du ser

- **Farver og former** ændrer sig efter værdierne: en pumpe er grøn, når den kører; en tank fyldes; en lampe blinker ved alarm; røret kan vise strømningsretning med løbelys.
- **Tal og tekst** viser tagets værdi, med den enhed og det antal decimaler teknikeren har valgt (fx *21,5 °C*).
- **Statuschips** øverst viser, om forbindelsen til serveren er **Live**, og om hver PLC svarer (*HypervisionPLC 10.1.1.30: ok · SSE*). Er forbindelsen væk, vises det tydeligt, og værdierne er ikke friske.
- Værdier uden kontakt til PLC'en vises som **—** eller som tegnet, så du aldrig ser en gammel værdi som om den var ny.

### Når værdien ikke er frisk (datakvalitet)

Hver værdi har en **kvalitet**. Er den ikke *god*, tones symbolet **ned** (kun ca. en tredjedel synligt og gråt), så en gammel eller manglende værdi aldrig ligner en gyldig.

| Kvalitet | Hvad der er sket | Værdien |
| --- | --- | --- |
| **God** | Frisk værdi læst fra PLC'en | Vises normalt |
| **Kommunikationsfejl** | Forbindelsen til PLC'en fejlede (netværk, PLC slukket) | Den **sidst kendte** værdi — den er ikke ny |
| **Dårlig** | PLC'en svarer, men tagget kan ikke læses: en ST-variabel findes ikke eller programmet er ikke kompileret, eller en ekstern enhed (RS485-slave, expansion board) svarer ikke | Ingen værdi — vises som **—** eller som tegnet |
| **Ukendt** | Der er endnu ikke modtaget nogen værdi (lige efter opstart, eller der ventes på første svar) | Ingen værdi |

Så længe kvaliteten ikke er god, gælder desuden: **alarmer for tagget fastholdes uændret** (en kommunikationsfejl udløser eller rydder ikke tagets alarmer), **betjening afvises** med *Ingen forbindelse … intet er skrevet*, og **Trends** får et hul i kurven. Teknikere kan se symbolet i hver tilstand i *Symboltest*.

**Trendgrafer i tegningen:** tryk på en trendgraf for at se den i **stor udgave** (musemarkøren bliver et forstørrelsesglas). Vælg periode øverst (15 min … 7 dage); grafen opdateres af sig selv. **← Tilbage til tegningen**, Esc eller et klik uden for vinduet fører tilbage.

**Beskeder og PLC-fejl:** fejl, advarsler og beskeder (fx *PLC … : kommunikation tabt*, *Tegningen er deaktiveret*, forsvundne bindinger) står i en fast plads yderst til højre i værktøjslinjen over tegningen — som en lille pille med den alvorligste besked og et tal, hvis der er flere (*+2*). Tegningen flytter sig derfor aldrig, når en besked kommer og går. Tryk på pillen for at se alle beskederne; en PLC-fejl kan **kvitteres** (knappen *Kvittér*), og kommer så først frem igen, når PLC'en har været i orden og fejler på ny. Kvitteringen gælder kun din browser; PLC'ens status i værktøjslinjen og alarmerne ændres ikke. På driftpanelet (uden værktøjslinje) ligger pillen øverst til højre oven på tegningen.

### Zoom og flyt

Brug **musehjulet**, **knib** på en touch-skærm eller knapperne **−**, **+** og **Tilpas** (tilpasser tegningen til vinduet). Træk i tegningen for at flytte rundt. Zoomniveauet vises som procent.

### Betjening

![Betjeningsdialogen for en omskifter: den låste position har 🔒, og koden skal indtastes, før der skiftes](/manual/drift-dialog.png)

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

## Alarmer og Trends

Alarmer og kurver har hver sit kapitel: se *Alarmer* og *Trends*.

## Energi

![Energi: forbrug pr. dag for et energi-tag, med tabel under søjlerne](/manual/energi.png)

**Energi** viser forbrug og produktion for tags, der er markeret som **energi-tags** under **Tags → Redigér → Energi**:

- **Tæller** (fx en kWh-måler, hvis værdi bare stiger): rapporten viser forskellen mellem start og slut af perioden.
- **Effekt** (fx kW): rapporten integrerer effekten over tid.
- Feltet **Omregning til kWh** ganges på værdien, hvis måleren leverer en anden enhed.

Vælg **Dag**, **Uge** eller **Måned** (seneste 12 måneder). Den igangværende periode er markeret og ikke afsluttet. Energidata gemmes i et antal dage; tidszonen er dansk tid.
