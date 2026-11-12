# Analyse: virtuelle tags og styring af signalveje — skal systemet designes omkring dem?

2026-11-12. Spørgsmål fra Jan: (1) signalvejen som **virtuelt tag**, også til at *skrive* til i trin 2 (Signaler) i symbol-guiden, så andre symboler kan styre en signalvej; (2) overalt, hvor et PLC-tag bruges til at sætte en værdi, skal et virtuelt tag kunne bruges; (3) PLC-tags skal også kunne styre en signalvej **direkte** — evt. med et særligt symbol; (4) skal vi designe systemet omkring det fremover?

## Kort svar
**Ja — men som en ren, lille abstraktion, ikke som en ny motor.** Det, der mangler, er ikke "et virtuelt tag til signalvejen", men en **fælles model for signaler** med tre slags, hvor de to nye bygger på det, der allerede findes (live-cachen og pseudo-tags). Et *særligt symbol* til at styre en signalvej er **ikke nødvendigt**: de symboler, vi allerede har (vælger, trykknap, setpunkt), kan styre en signalvej, når de må skrive til en **intern variabel**, som vejen læser i sine betingelser. Det er i tråd med, hvordan resten af tegningen bygges.

## 1. Hvad vi har i dag
| Hvad | Hvor | Kan læses i | Kan skrives |
| --- | --- | --- | --- |
| **PLC-tags** (`plc1:coil:1` …) | tags-tabellen, PLC-klienten | animationer, logik, alarmer, trends, ugeprogram, vejbetingelser | ja, via PLC'en (audit, bekræftelse, lås) |
| **Afledte signaler** (pseudo-tags) | `sym:<tegning>:<symbol>:pos/logic:L1`, `path:<tegning>:<id>:<grene>` — beregnes i `symbol_runtime`, ligger i live-cachen | kun **animationer og logikblokke** (kilde-vælgerne i guiden) — ikke alarmer, trends, ugeprogram, Tags-siden | nej |
| **Interne variable** | findes ikke | — | — |

Konsekvens: en signalvejs tilstand kan kun bruges i animationer/logik. Og en vej kan kun styres af **PLC-tags** (betingelserne) — der er intet, et symbol i tegningen kan skrive til, som ikke ender i PLC'en.

## 2. Modellen: tre slags signaler, ét interface
1. **PLC-tags** (ekstern, læs/skriv) — som i dag.
2. **Afledte signaler** (beregnet af SCADA, **kun læs**): symbolets position/tilstand, logikblokke, **signalvejens tilstand**. Findes allerede som pseudo-tags; de skal blot gøres **valgbare overalt, hvor et tag kan læses** (alarmer, trends, ugeprogram-betingelser, Tags-siden som skrivebeskyttet) og have et **stabilt id** (ikke vejens navn — et omdøbt navn må ikke bryde henvisninger; navnet er kun visning).
3. **Interne variable** (HMI-variable, SCADA-ejet, **læs/skriv**): en navngiven bool/tal med en værdi, SCADA husker (og gemmer i databasen, så den overlever genstart). Skrives af symboler (trin 2 *Signaler* → kommando-tag), og læses som alle andre tags — også af en signalvejs betingelser. **Dette er det virtuelle tag, Jan efterspørger.**

Fælles interface: en **signalreference** (streng) + **picker**, der viser tre grupper (*PLC-tags / Beregnede signaler / Interne variable*), med forskellig farve (som skrivbare tags i dag er lilla). Alt, der læser et tag, accepterer alle tre; alt, der *skriver*, accepterer PLC-tags og interne variable.

## 3. Sådan styres en signalvej (de tre ønsker)
- **Fra andre symboler:** en trykknap/vælger skriver en intern variabel `Vej_Kedel_Til`; vejen har betingelsen *Vej_Kedel_Til = Til* (eller *OG*/*ELLER* med PLC-tags). Ingen ny mekanisme i vejen — kun at betingelsens kilde-vælger også viser interne variable.
- **Fra PLC-tags direkte:** virker allerede (betingelsernes `src` er et PLC-tag). Ønsket om "direkte" dækkes af, at **vejens betingelser** kan være en blandning af PLC-tags og interne variable.
- **Særligt symbol?** Nej. Tegningen bygges af symboler, der får tags/signaler i guiden (trin 2). En vælger (*Auto / Til / Fra*) eller en trykknap, som skriver en intern variabel, **er** vejens betjening. Hvis vi vil gøre det let, kan vi senere tilføje en **hjælper** i vejens guide: *"Lav en betjening til vejen"* — opretter variablen og lægger en vælger i tegningen færdigopsat. Det er en genvej, ikke en ny symboltype.
- **Signalvejen selv som betjent symbol:** vejens symbol (v5.4) er "kun visning". Med interne variable kan det senere udvides med positionerne *Auto / Til / Fra* (kommando skrives til en intern variabel). Samme guide, ingen særregler — men først når fase 2 findes.

## 4. Hvad det kræver (omfang)
| Del | Ændring | Omfang |
| --- | --- | --- |
| Interne variable | tags-tabellen får en kilde `int:bool` / `int:real` (ingen PLC); værdi i databasen + live-cachen; skrivevej i `operate`-laget uden PLC-kald, men **med audit, rettigheder pr. tegning og bekræftelse/lås** som andre skrivninger; oprettes og slettes på Tags-siden | mellem |
| Afledte signaler overalt | registrér `sym:…`/`path:…` som skrivebeskyttede "tags" med stabilt id i tag-registret (opslag på præfiks); pickers i alarmer/trends/ugeprogram/guide viser gruppen *Beregnede signaler* | mellem |
| Pickers | `TagSelect` får tre grupper + filter for læs/skriv | lille |
| Backup, adgang, trends | definitioner og værdier i backup; adgang pr. tegning via `tags_for_drawing`; trend/alarm virker uændret, fordi de læser live-cachen | lille–mellem |
| Signalvej | betingelsernes kilde-vælger accepterer interne variable (validering i `signal_paths/service.py`) | lille |

Det rører **ikke** PLC-laget (`backend/app/plc/` er stadig den eneste, der taler HTTP til en PLC) og ikke live-motoren — de nye signaler bruger de eksisterende mekanismer (live-cache, WebSocket-udsendelse, audit).

## 5. Risici og grænser (vigtigt)
1. **Procesikkerhed:** SCADA er HMI, ikke styring. Interne variable må kun påvirke **visning og betingelser i SCADA** — de må **aldrig automatisk skrive til en PLC** (fx "når vejen er aktiv, sæt en udgang"). Det ville gøre SCADA til en blød PLC med forsinkelse, genstartsrisiko og uden PLC'ens sikkerhedsmekanismer. Skal noget i PLC'en styres, skal det skrives af en **bruger** (symbol med bekræftelse), eller bygges i PLC'ens logik. Hvis vi nogensinde vil have regler, der skriver til PLC'en, skal det være en særskilt, bevidst funktion med egen analyse.
2. **Tilstand ved genstart:** en intern variabel kan komme tilbage med sin sidste værdi (fx *Til*) efter strømsvigt. Hver variabel skal have en **startværdi-politik** (husk / nulstil til X) og vises tydeligt (ikke skjult tilstand).
3. **Flere brugere:** to operatører kan skrive samtidig — sidste skrivning vinder; audit viser hvem. For *tal* der ændres relativt (tæller) er det en risiko, men vi har ingen relative skrivninger.
4. **Forsvundne henstillinger:** slettes en intern variabel eller en vej, som andre bruger, skal sletningen afvises med en liste (samme mønster som for tags og logikblokke i dag).
5. **Navne vs. id:** henvis altid med id; vis navne. (Ellers brækker en omdøbning vejene — præcis det problem, vi lige har løst for elementer med unikke navne.)
6. **Skjult kompleksitet:** jo mere logik i signaler, jo sværere er det at fejlfinde. Derfor **ét sted at se hvem der læser/skriver et signal** (brugsliste, som Tags-siden har for tags i dag) og *Tegn › Symbol-oversigt* som indgang.

## 6. Anbefalet rækkefølge
1. **Fase 1 — Beregnede signaler overalt** (lille risiko): gør `sym:`/`path:` valgbare i alarmer, trends, ugeprogram og Tags-siden (skrivebeskyttet), med stabilt id. *Signalvejen er nu et "virtuelt tag" at læse.*
2. **Fase 2 — Interne variable** (kernen i Jans ønske): oprettes på Tags-siden; vælges som *kommando* i symbolernes trin 2 og som betingelse i en signalvej. *Nu kan en knap styre en vej.*
3. **Fase 3 — Betjening af selve vejen:** *Auto/Til/Fra* på vejens symbol og hjælperen *"Lav en betjening til vejen"*.
4. **Ikke nu:** SCADA-regler, der skriver til PLC'en (se risiko 1).

## 7. Skal vi designe systemet omkring det?
**Ja, som et princip:** *"Alt, en tegning læser eller skriver, er et signal med et stabilt id; der er tre slags (PLC / beregnet / intern); pickers og validering behandler dem ens."* Det er et lille, afgrænset skift, som gør den næste års funktioner (vejstyring, interlocks i visningen, scenarier, test uden PLC) til **tilføjelser**, ikke ombygninger — og det passer til, at systemet allerede har live-cache og pseudo-tags. Det vi **ikke** gør, er at flytte styring ind i SCADA.

## Beslutninger, vi har brug for fra Jan
1. Er modellen med tre slags signaler (og reglen om *aldrig automatisk skrivning til PLC*) det, du vil?
2. Er det rigtigt, at du **ikke** ønsker et særligt symbol, men at en vælger/trykknap skriver en intern variabel, som vejen læser? (Hjælperen *"Lav en betjening til vejen"* kan komme senere.)
3. Skal en intern variabel **huske sin værdi** efter genstart som standard — eller starte i en fast startværdi (fx *Fra*)? (Forslag: valgfrit pr. variabel, standard *start i Fra/0*, så en genstart aldrig sætter en vej til *Til*.)
4. Start med **fase 1** (beregnede signaler overalt) eller direkte med **fase 2** (interne variable)?
