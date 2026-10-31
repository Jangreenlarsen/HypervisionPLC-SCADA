# Alarmer

![Alarmer — fanen Aktive med prioritet, tilstand (aktiv/ophørt, kvitteret af hvem) og knapperne Kvittér og Kvittér alle](/manual/alarmer.png)

Alarmklokken i topbjælken åbner siden **Alarmer**. Et **driftpanel** (uden topbjælke) åbner den med knappen *Gå til Alarmer* i tegningen og kan kvittere derfra.

## Aktive alarmer

Fanen **Aktive** viser de alarmer, der er i gang lige nu — med tag, tekst, prioritet og hvornår den kom.

## Kvittér en alarm

Tryk **Kvittér** på en alarm for at sige, at du har set den, eller **Kvittér alle**. En kvitteret alarm er **stadig aktiv**, indtil årsagen er væk — så forsvinder den fra *Aktive* og står i *Historik*. Alle kvitteringer gemmes med bruger og tidspunkt.

## Historik

![Alarmer — fanen Historik: hvornår hver alarm opstod, ophørte og blev kvitteret](/manual/alarmer-historik.png)

Fanen **Historik** viser alle tidligere alarmer med tidspunkter for **udløsning**, **kvittering** (og hvem) og **ophør**.

## Prioritet og alarmklokken

Alarmer har en **prioritet**: *lav*, *medium* eller *høj* (sættes pr. tag). Klokken i topbjælken viser antallet af aktive alarmer; den er **rød** ved høj prioritet, **orange** ved medium, og **blinker**, indtil alle er kvitteret.

## Hvor kommer alarmer fra?

- **Grænsealarmer** på tal-tags: *LL* (lav-lav), *L* (lav), *H* (høj) og *HH* (høj-høj), med **dødbånd** (så alarmen ikke svinger ved grænsen) og **forsinkelse** (værdien skal have været uden for grænsen så længe, før alarmen kommer).
- **Til/fra-alarm** på et til/fra-tag: alarm når tagget er Til (eller Fra).
- **Kommunikationsalarm**: en PLC har ikke svaret i en periode.
- **Symbolafvigelse**: et symbol, hvor den valgte position ikke svarer til PLC'ens position (vælges i guiden, trin 4).

## Opsæt alarmer

Alarmgrænser opsættes pr. tag under **Tags → Redigér → Alarmer** (se *PLC'er og tags*) — eller i symbolguidens **trin 6** for symbolets tags. Her sættes også **prioritet**, **dødbånd** og **forsinkelse**.

Eksempel: se *Alarm ved høj temperatur — og kurve* i *Eksempler trin for trin*.

## Alarmer i tegningen

De dele af et symbol, der **viser værdien** af et tag i alarm (*Værdi* og *Niveau*), får en rød markering på Overview — den **blinker**, til alarmen er kvitteret, og **lyser fast**, til den er ophørt. Dele, der blot bruger tagget til fx farve, markeres ikke.

Et symbol kan også selv vise alarmen (fx blinke ved en ukvitteret alarm) — se *Symboler og guiden*. Knappen **Gå til Alarmer** i tegningen viser antallet af aktive alarmer (se *Tegn › Symbolbiblioteket*).

> Øverst på **Alarmer**, **Trends** og **Energi** står knappen **← Tilbage til "…"**, der fører tilbage til den tegning, du sidst så i Overview (fx efter et klik på en genvej i tegningen).
