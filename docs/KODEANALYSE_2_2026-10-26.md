# Kodeanalyse 2 — sikkerhed, adgangskontrol og dataintegritet (26.10.2026)

**Ny vinkel:** Den første analyse samme dag ([KODEANALYSE_2026-10-26.md](KODEANALYSE_2026-10-26.md)) så på drift og robusthed (polling, trends, energi, puls). Denne ser på, om SCADA-backend holder over for brugere, der vil (eller kommer til at) gøre noget, de ikke må: adgangskontrol på alle endpoints, synlighed (tegninger/tags), CSRF, login og PIN, hemmeligheder, filstier, SVG-upload og dataintegritet.
**Version:** v1.21.8 (build 0243). **Metode:** som før: fase 1 bred gennemgang (kortlægning af alle routes + læsning), fase 2 verifikation med test mod koden eller måling på testserveren 10.1.1.31 (x86-VM, 2 kerner — en Pi 4 er langsommere). Ingen kode er ændret.

> Målingen af login (G1) sendte 40 fejlede login-forsøg med opdigtede brugernavne (`analyse-…`) til testserveren — de står i audit-loggen som fejlede logins fra min PC. Ingen rigtige konti blev spærret.

---

## Konklusion

Grundlaget holder: alle endpoints har det rigtige rollekrav, synlighed håndhæves i backend (også i WebSocket og trends/alarmer/energi), CSRF er dækket to gange, hemmeligheder kommer ikke i svar eller backup, filstier er beskyttet, sidste admin kan ikke fjernes, og SVG-rensningen stopper alle kendte script-vektorer. Der er **ét reelt fund** (G1) og fire små.

## Fase 1 — oversigt

| # | Fund | Alvor | Verificeret |
|---|------|-------|-------------|
| G1 | Fejlede login-forsøg (uden at være logget ind) kan holde serverens event-loop optaget — scrypt kører synkront | **Mellem-høj** | Måling: `/api/health` 24 ms → median 235 ms ved 13 forsøg/s |
| G2 | CSS med escape-tegn (`@\69mport`, `u\72l(`) slipper forbi SVG-rensningen | Lav (CSP i nginx blokerer) | Test mod koden |
| G3 | PIN-spærringen bliver ikke længere ved gentagne fejl og nulstilles ved genstart | Lav | Læst + beregnet |
| G4 | WebSocket: synligheden genberegnes kun ved ændret rolle/tegningsadgang, ikke når et tag fjernes fra en tegning | Lav | Læst i koden |
| G5 | Filnavne/id'er valideres med `^…$` — `$` godtager et afsluttende linjeskift | Hygiejne | Læst i koden |

**Tjekket uden fund:**
- **Rollekrav:** alle ~150 routes; de eneste uden eget krav er login/logout/`me`/`health` (som de skal) og ugeprogrammer (krav på routeren: tekniker).
- **Synlighed:** `/api/tags`, `/api/live`, trends, alarmer, energi og WebSocket filtrerer efter brugerens tegninger; WebSocket genvaliderer sessionen løbende og lukker ved udløbet session.
- **CSRF:** session-cookie `HttpOnly` + `SameSite=Strict`, og en middleware afviser ændrende `/api/`-kald fra en anden origin.
- **Login:** samme svartid for kendt og ukendt bruger (dummy-hash); spærring efter 5 fejl pr. (bruger, IP); IP tages kun fra `X-Real-IP`, når kaldet kommer fra nginx (127.0.0.1); deaktivering og rolleskift slår straks igennem (sessioner slettes).
- **Sidste admin:** kan hverken slettes, deaktiveres eller nedgraderes (tjekket i samme databasetransaktion).
- **Hemmeligheder:** PLC-adgangskoder ligger i `secrets.json`, API'er svarer kun `has_password`; backup indeholder hverken brugere, hashes, sessioner, PIN-hashes eller PLC-hemmeligheder.
- **Filstier:** backup-filnavne og tegnings-id'er valideres med strenge mønstre før brug.
- **SVG:** hvidliste af elementer, ingen `on*`, ingen ekstern `href`, `javascript:`/`data:` (også med indlejrede tabulatorer), ingen `foreignObject`/SMIL, DTD/XXE afvist (defusedxml). Tegningsfilen serveres med egen CSP.
- **Indstillinger:** skrives under lås og atomisk; delte data (trend-visninger, paletter) er én nøgle pr. post, så samtidige ændringer ikke overskriver hinanden.

---

## Fase 2 — detaljer

### G1 · Login-forsøg kan holde serveren optaget (Mellem-høj)

**Hvor:** `api/auth.py` `login()` → `services/auth.py` `login()` → `verify_password()` (scrypt, n=2¹⁴, r=8). Kører synkront i den async-handler — også for ukendte brugere (bevidst, så svartiden ikke afslører, om brugeren findes). Samme mønster i `change_password()` og symbolernes PIN (`symbol_operate._check_pin`).

**Bevis (testserveren):** 4 forbindelser sendte 40 fejlede logins med tilfældige brugernavne — 13 forsøg/s. Imens steg svartiden for `/api/health` fra højst 24 ms til **median 235 ms, højst 347 ms**: event-loopet var næsten konstant optaget af scrypt. PLC-polling, SSE, alarmer, ugeprogrammer og live-værdier venter på samme måde. Spærringen pr. (brugernavn, IP) hjælper ikke, når brugernavnet skifter.

**Konsekvens:** Enhver, der kan nå login-siden (uden konto), kan med få samtidige forbindelser gøre SCADA træg eller "frosset" — på en Pi med færre forsøg. Ingen data kompromitteres, men driftsbilledet bliver upålideligt.

**Forslag:**
1. Kør `verify_password` (login, skift adgangskode, PIN) i `asyncio.to_thread` — `hashlib.scrypt` frigiver GIL'en, så event-loopet kører videre.
2. Begræns samtidigheden (fx højst 2 verifikationer ad gangen) og antal fejlede login-forsøg **pr. IP på tværs af brugernavne** (fx 20 pr. 5 min → 429 uden at beregne scrypt).
3. Evt. også `limit_req` for `/api/auth/login` i nginx-konfigurationen.

*Omfang: lille.*

### G2 · CSS-escapes slipper forbi SVG-rensningen (Lav)

**Hvor:** `services/svg_sanitize.py` `_clean_css()`: regulære udtryk for `@import` og `url(`.

**Bevis:** `<style>@\69mport "http://evil/x.css";</style>`, `<style>rect{fill:u\72l(http://evil/t.png)}</style>` og `style="fill:u\72l(http://evil/t)"` kommer uændret igennem. Browseren afkoder `\69` = `i` og `\72` = `r`, så det er `@import`/`url(` til en ekstern adresse.

**Konsekvens:** Kan ikke køre JavaScript, men kan hente ekstern CSS (fx skjule/ændre elementer i brugerfladen) og afsløre seerens IP. **Afværget i drift:** nginx sætter `Content-Security-Policy … style-src 'self' 'unsafe-inline'; img-src 'self' data:`, som blokerer de eksterne hentninger. Kun åbent, hvis backend køres uden nginx. Kræver desuden teknikerrolle (upload) eller en ondsindet SVG fra en tredjepart.

**Forslag:** afkod CSS-escapes (`\hex` og `\tegn`) før kontrollen i `_clean_css()` — eller fjern escapes helt i CSS fra tegninger. *Omfang: meget lille.*

### G3 · PIN-spærring (Lav)

**Hvor:** `services/symbol_operate.py` `_check_pin()`: 3 forkerte → 60 s spærring pr. (tegning, symbol, bruger), i hukommelsen.

**Beregning:** en firecifret kode (10.000 muligheder) med 3 forsøg pr. minut kan gennemprøves på ~55 timer (gennemsnit ~28) af én bruger — hurtigere med flere konti, og spærringen nulstilles ved genstart. PIN'en er en ekstra sikring for brugere, der allerede er logget ind, så risikoen er lav, men spærringen gør ikke det, man forventer.

**Forslag:** stigende spærring pr. symbol (på tværs af brugere), fx 1 → 5 → 15 → 60 min, med alarm/hændelse ved gentagne fejl; evt. gemt i databasen, så genstart ikke nulstiller den. *Omfang: lille.*

### G4 · WebSocket-synlighed følger ikke ændrede tegninger (Lav)

**Hvor:** `api/live_ws.py` `revalidate()`: `visible` genberegnes kun, når brugerens rolle eller tegningsliste ændres.

**Konsekvens:** Fjernes et tag fra en tegning (eller en tegning udgår), kan en begrænset bruger med åben side blive ved med at modtage dets live-værdier, til siden genindlæses. Kun live-værdier for tags, brugeren lige har haft adgang til.

**Forslag:** genberegn `visible` ved hver genvalidering (billigt) eller ved et "tegninger ændret"-signal. *Omfang: meget lille.*

### G5 · `$` i valideringsmønstre (Hygiejne)

**Hvor:** `_BACKUP_NAME`, `_DRAWING_ID` (services/backup.py), `_SAFE_ID` (storage/files.py) m.fl. bruger `^…$` med `.match()`. I Python godtager `$` et afsluttende `\n`.

**Konsekvens:** Ingen sti-traversering mulig (kun et linjeskift kan slippe med), så ingen reel effekt — men mønstrene er mindre stramme end tilsigtet. **Forslag:** `fullmatch()` eller `\Z`.

### Bemærkning · Ødelagt indstillingsfil

`sysconfig.save_section()` læser filen, ændrer ét afsnit og skriver den atomisk. Er filen allerede ødelagt (ikke gyldig JSON), startes der fra en tom fil, og de øvrige afsnit går tabt ved næste gem. Sjældent (filen skrives atomisk); evt. gem en kopi af den ødelagte fil, før den overskrives.

---

## Status (26.10.2026)

Alle fund er rettet med tests: G1 i v1.21.9, G2 + G5 i v1.21.10, G4 i v1.21.11 og G3 i v1.21.12 (se BUGS.md). Bemærkningen om en ødelagt indstillingsfil er ikke ændret.

## Anbefalet rækkefølge

1. **G1** (login/PIN i tråd + begrænsning pr. IP) — det eneste fund med reel driftsbetydning.
2. **G2 + G5** (små hærdninger af validering).
3. **G4**, **G3**.
