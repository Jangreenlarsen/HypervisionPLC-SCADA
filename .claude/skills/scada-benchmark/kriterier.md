# Kriterier for SCADA/HMI-benchmark

**Kriterie-version: 1** (2026-11-23). Ændres listen (ID tilføjes, fjernes eller ændrer betydning), hæves versionen, og rapporten skriver at tidsserien er brudt for de berørte ID'er. Kriterier ændres aldrig midt i en analyse.

Referencer for hvad branchen forventer (principper, ikke paragrafcitater — ved tvivl om en detalje i en standard, skriv "sædvane" i stedet for at citere): ISA-101 (HMI), ISA-18.2 / IEC 62682 og EEMUA 191 (alarmstyring), IEC 62443 (OT-cybersikkerhed), ISA-5.1 / ISO 14617 (symboler), ISO 11064 / ISO 9241 (ergonomi), WCAG 2.2 (tilgængelighed), NIS2 (EU-krav til kritisk infrastruktur).

## Skala

| Værdi | Betydning |
|---|---|
| **2** Opfyldt | "Opfyldt når" er opfyldt og kan påvises (kode, test, dokumentation eller set i UI). |
| **1** Delvist | Noget af det, kun i dele af systemet, eller uden test. |
| **0** Mangler | Ikke til stede. |
| **U** Ukendt | Kunne ikke påvises inden for analysen. Tæller som 0 i score, men markeres. |
| **–** Ikke relevant | Kun med skriftlig begrundelse ud fra projektets faste ramme (CLAUDE.md). Tæller ikke med i nævneren. |

**Prioritet**: **K** = forventes af enhver driftsklar SCADA · **V** = forventes af en moden løsning · **N** = differentiator.

**Evidens er obligatorisk**: fil:linje, testnavn, dokument eller "set i UI (rute, bredde)". En vurdering uden evidens er U.

## A. HMI-design (ISA-101)

| ID | Pri | Kriterium | Opfyldt når |
|---|---|---|---|
| A1 | K | Hierarki af billeder | Overblik → område → detalje/diagnostik kan nås, og navigationen er konsistent |
| A2 | V | Dæmpet palet, farve til afvigelser | Normaltilstand er neutral; farve (rød/gul osv.) er forbeholdt alarm og afvigelse |
| A3 | V | Farve er ikke eneste bærer | Tilstand kan aflæses uden farve (form, tekst, ikon, placering) |
| A4 | K | Standardiseret symbolbibliotek | Genbrugelige symboler (pumpe, ventil, tank, instrument) med ens opførsel og tilstandsvisning |
| A5 | V | Analoge værdier i kontekst | Værdi vises med enhed, decimaler og område/grænse eller trendindikator, ikke kun et tal |
| A6 | K | Fast ramme | Alarmstatus, bruger, tid og forbindelsesstatus er altid synlige |
| A7 | K | Udstyrstilstand tydelig | Kørende/stoppet/fejl/manuel/auto kan skelnes pr. udstyr |
| A8 | K | Forældede data synlige | Mistet forbindelse eller gamle værdier vises tydeligt (ikke bare sidste værdi) |
| A9 | V | Styring i faceplate/dialog | Betjening sker i en konsistent dialog, ikke spredt på tegningen |
| A10 | N | Begrænset informationstæthed | Billeder er læsbare uden overfyldning; zoom/pan eller opdeling findes |
| A11 | V | Egne tegninger uden programmering | Anlægstegning kan importeres/redigeres og bindes til tags af teknikeren |
| A12 | V | Enheder og indgange | Fungerer på touch, kiosk og smal skærm; mørk/lys visning eller natdrift |

## B. Alarmstyring (ISA-18.2 / IEC 62682 / EEMUA 191)

| ID | Pri | Kriterium | Opfyldt når |
|---|---|---|---|
| B1 | K | Alarmprioriteter | Mindst 3 niveauer med forskellig visning |
| B2 | K | Alarm-livscyklus | Tilstandene aktiv/uanerkendt, aktiv/anerkendt, retur/uanerkendt og normal |
| B3 | K | Anerkendelse | Registrerer bruger og tidspunkt |
| B4 | K | Alarmhistorik | Søgbar/filtrerbar log, og den kan eksporteres |
| B5 | V | Shelving/undertrykkelse | Midlertidig undertrykkelse med begrundelse, varighed og audit |
| B6 | V | Rationalisering | Pr. alarm er konsekvens, handling og svartid dokumenteret eller kan angives |
| B7 | V | Alarmflod og KPI | Alarmrate, stående alarmer og top-N-hyppigste kan ses |
| B8 | K | Chatter-håndtering | Deadband/forsinkelse/hysterese findes, så en alarm ikke flimrer |
| B9 | V | Signalering | Visuel og evt. lydsignal; uanerkendte skiller sig ud |
| B10 | V | Ændringsstyring af grænser | Ændring af alarmgrænser logges med hvem, hvad og hvornår |
| B11 | V | Notifikation og eskalering | Alarmer kan sendes ud (mail/SMS/push), evt. med eskalering |

## C. Styring og operatørhandlinger

| ID | Pri | Kriterium | Opfyldt når |
|---|---|---|---|
| C1 | K | Rollebaseret adgang | Roller håndhæves i backend, ikke kun skjult i UI |
| C2 | K | Bekræftelse og grænsekontrol | Kritiske kommandoer og setpunkter kræver bekræftelse; værdier kontrolleres mod grænser |
| C3 | K | Audit af skrivninger | Hver skrivning logges: hvem, hvad, gammel/ny værdi, tid, resultat |
| C4 | V | Manuel/auto og interlocks | Driftsart og blokeringer er synlige, og forbudte handlinger afvises |
| C5 | V | Skrive-konflikter | Samtidige modstridende skrivninger håndteres (rækkefølge/prioritet/afvisning) |
| C6 | N | Lokal/fjern | Mulighed for at spærre fjernstyring |
| C7 | V | Tidsplaner | Ugeplaner/skemalagte handlinger med oversigt og audit |
| C8 | V | Feedback på kommando | Brugeren ser om en kommando blev udført, afvist eller timede ud, med specifik fejl |

## D. Data, trends og integration

| ID | Pri | Kriterium | Opfyldt når |
|---|---|---|---|
| D1 | K | Historiske trends | Flere kurver, zoom, valgfri periode |
| D2 | V | Opbevaring | Lagring med defineret opbevaringstid og nedsampling, så disken ikke løber over |
| D3 | V | Eksport | Trend- og loggdata kan eksporteres (fx CSV) |
| D4 | K | Datakvalitet | Værdier har tidsstempel/kvalitet, og dårlig kvalitet vises |
| D5 | N | Rapporter | Drift-/energi-/tællerrapporter |
| D6 | V | Åbne grænseflader | Dokumenteret API eller protokol til andre systemer (northbound) |
| D7 | K | Tagmodel | Tags med enhed, skalering, grænser og beskrivelse; virtuelle/beregnede tags er en fordel |

## E. Cybersikkerhed (IEC 62443 / NIS2)

| ID | Pri | Kriterium | Opfyldt når |
|---|---|---|---|
| E1 | K | Autentificering | Individuelle konti, hashede adgangskoder, politik, lockout/brute-force-beskyttelse |
| E2 | K | Sessioner | Timeout, httponly/samesite/secure-cookies, afmelding ugyldiggør |
| E3 | K | Transportkryptering | TLS med certifikathåndtering (selvsigneret eller ægte) |
| E4 | K | Hemmeligheder | Adgangskoder/tokens til PLC ligger uden for git, vises aldrig til klienten |
| E5 | K | Mindste rettighed | Tjenesten kører uprivilegeret med hærdet service-enhed |
| E6 | K | Netværksafgrænsning | Kun SCADA-serveren taler med PLC'en; ingen direkte vej fra browser |
| E7 | V | Sikkerhedslog | Login, fejlede login, rettighedsændringer og konfigurationsændringer logges |
| E8 | V | Sikker opdatering | Opdateringspakke kontrolleres (hash/signatur), tager backup, ruller tilbage |
| E9 | V | Afhængigheder | Licenskontrol og sårbarhedsscanning eller SBOM |
| E10 | K | Inputvalidering | Validering af input, CSRF-forsvar, sanering af uploadet SVG/HTML |
| E11 | V | Trusselsmodel og patch-proces | Dokumenteret risikovurdering og procedure for sikkerhedsopdateringer |
| E12 | N | Flerfaktor | MFA eller tilsvarende for admin |

## F. Pålidelighed og drift

| ID | Pri | Kriterium | Opfyldt når |
|---|---|---|---|
| F1 | K | Genstart efter strømtab | Starter selv, uden manuel handling, med korrekt tilstand |
| F2 | K | Kommunikationsfejl | Timeout, retry og tydelig forbindelsesstatus til PLC; ingen hængende UI |
| F3 | K | Backup/restore | Konfiguration og tegninger kan sikkerhedskopieres og gendannes, og det er afprøvet |
| F4 | V | Selvovervågning | Health, metrics og logfiler for SCADA-serveren selv |
| F5 | N | Redundans | Failover eller en begrundet afgrænsning (enkeltenhed) |
| F6 | V | Kapacitet på målplatform | Antal tags/brugere/opdateringsrate er målt eller begrænset på den faktiske hardware |
| F7 | V | Tidssynkronisering | NTP eller tilsvarende; tidsstempler er pålidelige |
| F8 | V | Opdatering og release | Versionering, kontrolleret udrulning, ingen datatab |
| F9 | V | Katastrofegendannelse | Dokumenteret og øvet procedure |

## G. Konfiguration og vedligehold

| ID | Pri | Kriterium | Opfyldt når |
|---|---|---|---|
| G1 | K | Flere PLC'er | Mere end én enhed kan tilsluttes og adskilles |
| G2 | V | Konfiguration som data | Import/eksport og versionering af tegninger og opsætning |
| G3 | K | Automatiske tests | Testsuiter og mock-PLC kører og dækker kritisk logik |
| G4 | V | Dokumentation | Brugermanual, administratorvejledning og API-reference, evt. hjælp i UI |
| G5 | V | Lokalisering | Sprog, enheder og dato/tal-format |
| G6 | V | Tilgængelighed | Kontrast, tastaturbetjening og læsbar tekst (WCAG) |
| G7 | V | Sporbarhed | Changelog/udgivelsesnoter og kendte fejl er ført |
