# Analyse: tilstande, positioner og den 6-trins symbolopsætning — 2026-11-13

Jan (2026-11-13), efter ventiltilstandene i v6.6.0: "Analysér hvordan det fungerer sammen med vores 6-trins symbolopsætning med fx en omskifter også, eller om vi skal gentænke det design også."

## 1. Sådan er det i dag

To niveauer:

**Symboltypen.** Den sættes op én gang og gælder alle tegninger:
- **Opsætning › Symboler**: tilslutningspunkter, *Ind/ud og veje*, flow-rolle og — siden v6.6.0 — **tilstande** (navn og åbne veje, fx *A → AB* = "A igennem AB · B blokeret").
- **Bibliotekets forslag:** delenes animationer (`data-hv-part`). En omskifter tegnes ud fra sine positioner (`selectorSymbol`).

**Symbolet i tegningen.** Det sættes op i guiden, de 6 trin:

| Trin | Indhold |
|---|---|
| 1 Symbol | Betjeningsform: kun visning, interaktiv (positioner), trykknap, setpunkt; *passiv* (kun tilbagemelding) |
| 2 Signaler | PLC'ens tags: kommando og tilbagemelding pr. signal |
| 3 Kontakter | **Positionerne** (navne) og **kontaktplanerne** (hvilken værdi hvert signal har i hver position) |
| 4 Visning | **Animationerne** pr. del (farve, vinkel, synlig … pr. position eller efter et tag), og **Flow** (pumpe, restriktion, målt flow, **tilstand pr. position**, portfarver) |
| 5 Betjening | Bekræftelse, nøglelås, klik (dialog eller venstre/højre) |
| 6 Test og gem | Symboltest og gem |

## 2. Problemet: samme ting tre steder

For et symbol med positioner beskrives *det samme* med tre begreber:

1. **Position** (trin 3, pr. symbol): hvad PLC'en og operatøren ser, fx *Varme*.
2. **Tilstand** (symboltypen, v6.6.0): hvad symbolet *gør*, fx A igennem AB.
3. **Udseende pr. position** (trin 4, pr. symbol): farve, vinkel eller synlig pr. position. Portfarverne er afledt af tilstanden.

**Eksempel — 3-vejsventil** (to positioner fra ét register, 10 og 20):

- trin 2: register-tagget;
- trin 3: positionerne *A → AB* og *B → AB*, og kontaktplanen 10/20;
- trin 4 › Flow: tilstanden pr. position (samme navne igen);
- trin 4 › Animationer: farver pr. port pr. position (nu dækket af portfarverne).

→ Navnet *A → AB* skrives to steder, og sammenhængen *position ↔ tilstand ↔ udseende* står kun i hovedet på den, der sætter op.

**Eksempel — omskifter Hånd/0/Auto** (ét register med værdierne 0/1/2):

- trin 3: positionerne *Hånd*, *0*, *Auto* og kontaktplanen 0/1/2;
- trin 4: grebets vinkel pr. position. Guiden laver den, og omskifteren tegnes om, hvis antallet af positioner ændres.

Der er intet flow, men positionerne *er* omskifterens tilstande. Tilstandene i v6.6.0 hjælper ikke omskifteren, fordi de kun kender flow (veje).

**Konklusion:** v6.6.0 løser *ventilens* forståelighed, men tilføjer et tredje begreb ved siden af positioner og udseende. Guiden er bygget omkring *positioner* (pr. symbol). Det naturlige begreb for brugeren er *tilstande* (hvad symbolet kan være), og de hører til **symboltypen**.

## 3. Alternativer

**A. Behold designet og poler det** (lille).
- Trin 3 viser tilstandens betydning ved hver position, og en ny position får typens tilstande som standard.
- + Ingen risiko, intet nyt at lære.
- − Begreberne forbliver delt. Omskifteren har stadig ingen definition, og udseendet sættes stadig pr. symbol.

**B. Tilstande som det fælles begreb på symboltypen** (anbefalet). En symboltype definerer sine **tilstande** én gang. Hver tilstand har:
- navn og betydning, fx *Hånd* eller *A → AB*;
- **flow** (åbne veje), hvis typen har veje;
- **standard-udseende** pr. del, fx grebets vinkel, portfarver, lampen tændt, delen synlig.

Guiden bliver så:

| Trin | Indhold |
|---|---|
| 1 Symbol | Betjeningsform (uændret) |
| 2 Signaler | PLC-tags (uændret) |
| 3 **Tilstande** | Én tabel: typens tilstande som rækker, og for hver: **PLC-værdi** (kontaktplanen, fx register = 10), om den bruges (fravælg en), og evt. et andet navn på denne tegning. Betydningen står ved siden af |
| 4 Visning | Kun **ekstra** animationer. Tilstandenes udseende kommer fra typen og kan rettes pr. symbol. Flow uden tilstandstabel (den er flyttet til trin 3) |
| 5–6 | Uændret |

- Omskifteren: typen *Omskifter Hånd/0/Auto* har tilstandene Hånd, 0, Auto med grebets vinkel. *Omskifter med egne positioner* definerer sine tilstande i guiden (som i dag) eller i symbol-editoren.
- 3-vejsventilen: tilstandene *A → AB* og *B → AB* med åbne veje og portfarver. I guiden skriver man kun 10 og 20.
- 4-vejsventilen: *A → B* og *C → D*. Man kan tilføje alle de tilstande, man har brug for, på typen.
- \+ Ét begreb, defineret ét sted. Guiden bliver kortere for de almindelige symboler, og udseendet er ens på alle tegninger. Symbolernes bibliotek kan leveres med tilstande, også el-komponenter.
- − Større ombygning af trin 3 og 4 og symbol-editoren. Eksisterende opsætninger skal fortsat virke.

**C. Alt pr. symbol i guiden** (ingen typedefinitioner).
- \+ Fleksibelt.
- − Hver ventil sættes op forfra. Det er det, Jan har oplevet som uforståeligt.

## 4. Anbefaling: B

**Data, additivt og uden migrering af gamle opsætninger:**
- Symboltypens definition: `states: [{name, open, look: {del: {anim, værdi}}}]`. `open` findes allerede.
- Symbolets opsætning: `positions[j].state` (navnet på typens tilstand). Positioner uden tilstand er **egne positioner** og virker præcis som i dag.

**Afledte bindinger** (som portfarverne i v6.3.0): tilstandens udseende bliver til bindinger pr. position, og aldrig oven på en animation, symbolet selv har på delen.

**Betjening og PLC er uændret:** kontaktplaner, tilbagemelding, nøglelås og validering arbejder stadig på positionerne. En position er bare knyttet til en tilstand.

**Symbol-editoren** får *Tilstande* for alle typer, også dem uden veje. Hver tilstand får udseende pr. del (vælg del → farve/vinkel/synlig, med forhåndsvisning).

## 5. Risici og åbne spørgsmål

- **Tilbagemeldinger og "afviger".** Uændret, fordi de hører til positionerne.
- **Omskifterens omtegning** (antal positioner ≠ tegningen). Typens tilstande bestemmer antallet, og ellers som i dag.
- **Spørgsmål til Jan:**
  - Skal en tilstands **navn** kunne være forskelligt fra tegning til tegning (fx *A → AB* hedder *Varme* på én tegning)? Forslag: ja, som et visningsnavn pr. symbol.
  - Skal **standard-udseendet** kunne rettes pr. symbol, eller altid følge typen? Forslag: følge typen, med mulighed for at tilsidesætte.
