# Gennemgang af HypervisionPLC SCADA — 2026-10-12

Gennemgået: `main` @ dc0bfc1 (v0.25.1 build 0035), ca. 14.100 linjer backend, frontend og deploy.
Fundene er efterfølgende tjekket mod `dev` @ 1d2d8a8 (v0.27.0 build 0037) — de gælder stadig, og
linjehenvisningerne nedenfor passer til `dev`.

De åbne fejl er registreret i [BUGS.md](../BUGS.md) med henvisning til nummeret her (#N).

## Sammenfatning

Projektet er i god stand: lagdelingen holdes, fejlhåndteringen er gennemført, og alle tests er grønne.
De vigtigste fund handler om drift i en SCADA-kontekst — en puls der kan blive hængende, en toggle der
kan slå forkert, live-værdier der kan gå tabt — og om at login og tunge operationer blokerer
event-løkken på Pi'en.

| Kontrol | Resultat |
| --- | --- |
| Backend pytest | 269 bestået (Python 3.13) |
| Frontend vitest | 103 bestået |
| `npm run build` | OK, 299 kB JS (107 kB gzip) |
| svelte-check | 0 fejl, 0 advarsler |
| `npm audit --omit=dev` | 0 sårbarheder |

Fem fund er verificeret med en kørende test eller et script (markeret *verificeret*); resten bygger
på læsning af koden med fil og linje angivet.

## Høj prioritet

**1. Puls kan efterlade udgangen tændt ved timeout.** `operate.py:198-201`: fejler TÆND-skrivningen,
kastes fejlen uden at sende SLUK. Ved `PlcUnreachable` (timeout) kan PLC'en sagtens have udført
skrivningen — kun svaret gik tabt. Netop det scenarie, docstringen lover at forhindre.
*Forslag:* ved timeout/forbindelsesfejl på TÆND, forsøg altid SLUK (evt. efter en kort pause) og meld
en tydelig advarsel.

**2. Toggle er ikke atomisk og bruger en evt. gammel cache-værdi.** `operate.py:176-183`: den nye værdi
beregnes ud fra cachen *før* låsen tages. To operatører der trykker samtidig, skriver begge "til" i
stedet for til→fra. For SSE-dækkede adresser kan cachen desuden være op til 2 s gammel.
*Forslag:* tag låsen først, læs værdien frisk fra PLC'en (`read_bulk`), og skriv så.

**3. Tabte live-ændringer giver forkert billede på Overview** (*verificeret*). `live_cache.py:58-62`:
når en klients kø er fuld, smides den ældste delta væk. Da kun ændringer sendes, kan fx en pumpe der
skiftede til "til" stå som "fra", indtil den ændrer sig igen.
*Forslag:* flet ventende deltaer (seneste værdi pr. tag vinder) i stedet for at droppe — så er køen
altid korrekt, bare forsinket.

**4. WebSocket'en lever videre efter logout/deaktivering** (*verificeret*). `live_ws.py:56-66` tjekker
kun session ved tilslutning. En deaktiveret bruger, eller én hvis rolle/tegningsadgang er ændret, får
fortsat live-værdier og alarmer med de gamle rettigheder — selvom `update_user` netop sletter sessioner
"så det slår igennem straks".
*Forslag:* gen-validér sessionen i sender-løkken (fx hvert 10.-30. s) og ved hver subscribe; luk med
4401 når den er væk, og genberegn `visible`.

**5. Blokering af event-løkken på Pi'en.** Alt kører i én asyncio-løkke, så synkront arbejde i
`async def` standser polling, SSE og WebSocket for alle:

- Login: scrypt (~40 ms målt her, sandsynligvis 3-5× på en Pi 4) direkte i `api/auth.py:96`.
  Låsningen er pr. (bruger, IP), så skiftende brugernavne kan holde løkken optaget.
- Trend-flush og den timevise sletning af gamle samples (`trends.py:110-115`) — en stor `DELETE` på
  SD-kort kan tage sekunder.
- Backup-download, auto-backup og restore-validering (`backup.py`: `export`, `restore`) læser og
  sanerer alle SVG'er synkront.
- Hver betjening og WS-tilslutning for en begrænset bruger parser *alle* tegningers SVG to gange
  (`drawings.py:238` `_compute`, via `scope.py`).

*Forslag:* `asyncio.to_thread` for login, flush/purge og backup; cache `_compute` pr. (tegning, aktiv
version, tag-ændringstidspunkt).

## Mellem prioritet

**6. CSS fra en tegning rammer hele web-UI'et** (*verificeret*). Begge sanere (server og DOMPurify)
lader `<style>` passere, og tegningen indsættes med `innerHTML` (`canvas.ts:8`). En tekniker kan
derfor fx skjule alarmbanneret for operatører. Desuden omgås url-filteret (`svg_sanitize.py:43`) med
CSS-escapes som `\75rl(...)` og `@\69mport`. Bag nginx stopper CSP'en eksterne kald, men kører
serveren uden nginx, er der ingen CSP.
*Forslag:* render tegningen i en shadow root (eller prefix alle regler med tegningens id), afvis `\` i
CSS, og sæt CSP-headeren fra FastAPI også.

**7. Ingen alarm når en ekstern slave eller et ST-program fejler.** `alarms.py:157`: tags med kvalitet
`bad` fryses, og kommunikationsalarmen findes kun pr. PLC (`state == "error"`). En død RS485-slave
eller et ikke-kompileret ST-program giver derfor ingen alarm, og slavens grænsealarmer ligger stille.
Samme for en aktiv PLC uden adgangskode (`stopped`).
*Forslag:* en kommunikationsalarm pr. ekstern enhed (`ext_group`) og for `bad`-kvalitet efter
`comm_delay_s`.

**8. Ingen liveness-signal til browseren.** Serveren sender kun noget ved ændringer, og klienten
(`live.ts`) har ingen watchdog. På en kiosk med dårligt WiFi kan Overview vise "Live" med frosne
værdier i lang tid.
*Forslag:* send en `ping`-besked hvert ~5 s og lad klienten genforbinde efter ~15 s stilhed.

**9. Én fejlende læsning tager hele PLC'en ned.** `plc_runtime.py` `poll_once`: en `PlcApiError` på ét
bulk-område eller ét ST-program markerer *alle* PLC'ens tags som `comm_error` og starter backoff — i
modsætning til eksterne slaver, der håndteres pr. område. Kan ramme ved firmware med et andet
adresserum.
*Forslag:* samme pr.-område-håndtering som `_poll_ext`; kun forbindelsesfejl slår hele PLC'en ned.

**10. Ugeprogrammer overskriver manuel betjening efter genstart.** Tilstanden i
`ScheduleService._state` er kun i hukommelsen. Efter genstart (eller ændring af programmet) skrives den
ønskede værdi igen, selvom en operatør har overstyret den midt i perioden — uden genstart sker det
ikke. Det bør være et bevidst valg og stå i dokumentationen. **Åbent spørgsmål til Jan.**

**11. Afhængigheder er ikke låst.** `requirements.txt` bruger kun `>=x,<major`, og `install.sh`
installerer det nyeste. Testkørslen viser allerede en Starlette-deprecation (`httpx` → `httpx2` i
TestClient).
*Forslag:* en låst `requirements.lock` med hashes (pip-tools), brugt af `install.sh`.

## Mindre fund og hygiejne

| # | Fund | Sted | Forslag |
| --- | --- | --- | --- |
| 12 | WebSocket'en har intet Origin-tjek. SameSite=Strict hjælper, men andre subdomæner på laces.dk er "same-site" | `live_ws.py:57` | Afvis Origin ≠ Host før `accept()` |
| 13 | Origin-tjekket sammenligner med `Host` uden port — nginx sætter `$host`. Tilgås SCADA via ikke-standardport, afvises alle skrivninger med 403 | `main.py`, nginx-conf | Brug `$http_host` i nginx |
| 14 | `_plc_summary` laver en DB-forespørgsel pr. delta pr. klient, ikke hvert 2. s som docstringen siger | `live_ws.py:85` | Kun hvert 2. s |
| 15 | `read_bulk`/`_ext_value` laver `int(value)` uden tjek: `None` giver rå `TypeError`, decimaltal trunkeres stille | `client.py`, `plc_runtime.py` | Validér og kast `PlcApiError` |
| 16 | Dybt indlejret SVG (>~1000 niveauer) giver `RecursionError` → "Intern serverfejl" i stedet for en læsbar besked | `svg_sanitize.py` | Fang og omsæt til `SvgError` |
| 17 | `_fails`/`_locked_until` ryddes aldrig, og `LoginBody.username` har ingen makslængde | `auth.py` | Max-længde + periodisk oprydning |
| 18 | Brugernavne er case-sensitive i DB, men låsningen bruger `lower()` — "Admin" og "admin" kan oprettes som to brugere | `db.py`, `auth.py` | `COLLATE NOCASE` eller normalisér |
| 19 | Startengangsadgangskode og secrets skrives før `chmod 600` (kort vindue; data-mappen er dog 0750) | `auth.py`, `secrets.py` | `os.open(..., 0o600)` |
| 20 | Udløbne sessioner ryddes kun ved login | `db.py` | Ryd i baggrundsløkke |
| 21 | `.claude/settings.local.json` er committet med `bypassPermissions` + `Bash` tilladt — deny-listen er nem at omgå, og regel 7's "kræver accept" håndhæves ikke | repo-rod | Gitignore filen eller stram den |
| 22 | CLAUDE.md siger Python 3.11, README 3.12 — testet her på 3.13 uden problemer | docs | Ensret |

## Det der fungerer godt

- **Lagdelingen holder:** kun `backend/app/plc/` taler HTTP med PLC'en, og service-laget ser kun typede `PlcError`'er.
- **Hemmeligheder:** PLC-adgangskoder kun i `secrets.json`, audit-loggen scrubber password-felter, sessionstokens gemmes som SHA-256.
- **Adgangskontrol:** sidste-admin-beskyttelse tjekkes atomisk i én transaktion; operatørrettigheder pr. handling (v0.24.0) håndhæves i backend.
- **PLC-hensyn:** én keep-alive-forbindelse, token-bucket under PLC'ens grænse, backoff ved 429, SSE-dækning afledt af PLC'ens eget `connected`-svar.
- **Skrivninger** læses tilbage og advarer hvis et ST-program overskriver værdien.
- **Restore** er alt-eller-intet med automatisk backup først og tilbagerulning af filer.
- **Fejlbeskeder:** alle frontend-`catch` uden fejlvisning har en begrundet kommentar; pydantic-lister fladtrykkes til læsbar tekst.
- **Deploy:** systemd-hærdning (`ProtectSystem=strict` m.m.) og en stram CSP i nginx.
- **Regressionstests** til hver rettet fejl i BUGS.md.

## Foreslået rækkefølge

Sikkerhed for anlægget først, derefter korrekt visning, så ydelse. Hvert punkt er en selvstændig
bugfix (BUGS.md + PATCH-bump) efter projektets egen workflow.

1. Puls-nulstilling ved timeout (#1) og atomisk toggle (#2) — små ændringer i `operate.py`, nemme at teste mod mock-PLC'en.
2. Flet deltaer i stedet for at droppe (#3) og WS-heartbeat (#8) — begge handler om at Overview viser sandheden.
3. Gen-validér WS-session og Origin-tjek (#4, #12).
4. Flyt blokerende arbejde til tråde og cache `_compute` (#5) — mål før og efter på testserveren 10.1.1.31.
5. Alarmer for eksterne enheder (#7) og pr.-område-fejl i polling (#9).
6. Isolér tegnings-CSS (#6) og lås afhængigheder (#11).
7. Resten af tabellen ved lejlighed.
