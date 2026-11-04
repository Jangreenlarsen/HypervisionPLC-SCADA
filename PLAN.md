# Plan: System › Certifikater (v3.25.0) — 2026-11-04

**Besluttet (Jan, 2026-11-04):** én side, hvor alt med nginx' TLS-certifikat kan konfigureres: selvsigneret, CSR + indlæsning af det signerede certifikat, import af PKCS#12 (og PEM), Let's Encrypt med **både HTTP-01 og DNS-01 (deSEC)**. Selvsigneret er som standard gyldigt i 825 dage. Styring via integrationer rykkes til 3.26 og MQTT til 3.27.

**Mål:** en admin kan skifte certifikat uden SSH, uden at kunne låse sig ude, og uden at en privat nøgle eller adgangskode nogensinde når browseren, loggen eller git.

## Arkitektur (valgt)
- **Kryptografi i tjenesten** med `cryptography` (findes allerede): nøgle, CSR, selvsigneret, parsing af PKCS#12/PEM og kontrol af parret. Alternativet var at lade root-hjælperen køre `openssl` med brugerinput; det er sværere at validere og giver dårligere fejltekster.
- **Installation altid via root-hjælper** `deploy/apply-tls.sh` (.path-unit som power/config/backupmount): tjenesten lægger et færdigt par (`fullchain.pem` + `privkey.pem`, 0600) i `data/config/tls-request/`. Hjælperen flytter det ind i en root-mappe, afviser symlinks og kalder den eksisterende installationslogik fra `cert-deploy.sh`: kontrol af parret, `.prev`/`.selfsigned`, `nginx -t`, **gendannelse ved fejl**, reload og `cert.json`. `cert-deploy.sh` udvides med `install-dir <mappe>`, så der kun er én installationsvej.
- **Let's Encrypt** via `hypervision-letsencrypt`, som udvides med `--method http|dns`. HTTP-01 bruger `certbot --webroot`: nginx' port-80-server får `location /.well-known/acme-challenge/` (webroot `/var/lib/hypervisionplc-scada-acme`) foran redirecten. DNS-01 bruger deSEC som i dag. Udstedelsen kører i baggrunden; status og log ligger i state-mappen, og siden følger med. Fornyelse sker af `certbot.timer` + deploy-hook, som i dag.

## Siden (System › Certifikater, kun admin)
1. **Aktuelt certifikat:** type (selvsigneret / Let's Encrypt / importeret / CA-signeret), emne, SAN-navne, udsteder, gyldighed, SHA-256-fingeraftryk og en advarsel, hvis den adresse, siden åbnes på, ikke står i SAN. Det offentlige certifikat kan hentes som PEM. Knapper: **Gendan forrige** og **Gå tilbage til selvsigneret**.
2. **Selvsigneret:** CN, SAN-navne (forudfyldt med værtsnavn og IP'er), gyldighed (standard 825 dage, 1–3650), nøgletype (EC P-256 som standard, RSA 2048/4096).
3. **CSR:** CN, O, OU, L, ST, C, e-mail, SAN-navne og nøgletype. **Hent CSR** (.csr). Den ventende nøgle gemmes på Pi'en (0600, skriv-kun) til det signerede certifikat lægges ind (PEM, kæde valgfri). Kontrollér, at det passer til den ventende nøgle, og installér. Den ventende CSR kan annulleres.
4. **Import:** PKCS#12 (.p12/.pfx + adgangskode) eller PEM (certifikat + kæde + nøgle, evt. krypteret nøgle + adgangskode). Kontrollér: nøglen passer, certifikatet er gyldigt nu, kæden sorteres (leaf først), advar ved ukendt værtsnavn eller kort restlevetid. Højst 64 KB, aldrig gemt ud over installationen.
5. **Let's Encrypt:** metode (HTTP-01 / DNS-01 deSEC), værtsnavn, e-mail, deSEC-token (skriv-kun) + zone/navn ved DNS-01. **Test (staging)** og **Udsted**, plus status for seneste udstedelse og fornyelse. Forudsætninger vises: HTTP-01 kræver port 80 udefra, DNS-01 kræver CNAME `_acme-challenge.<navn>`.

## Sikkerhed
- Kun admin. Alle handlinger skrives i auditloggen (uden nøgler og adgangskoder). Private nøgler, PKCS#12-adgangskoder og deSEC-token returneres aldrig og logges aldrig; fejltekster renses.
- **Ingen lockout:** `nginx -t` + automatisk gendannelse findes allerede. Siden advarer, før der skiftes til et certifikat, hvis navn ikke passer til den adresse, man står på. HSTS slås ikke til.
- Root-hjælperen validerer alt igen (PEM-form, størrelse, parret). Den kører aldrig brugerinput som argumenter.
- Reviewer-agenten gennemgår ændringen før commit.

## Observability
Log pr. handling. `/metrics`: `scada_tls_operations_total{action,result}` (+ de eksisterende `scada_tls_cert_*`). Status: certifikatkortet viser typen, og en fejlet LE-fornyelse vises som Status-problem og SYS-alarm.

## Berørte filer
- **Backend:** `services/tls_admin.py` (ny), `api/tls.py` (ny), `main.py`, `services/health.py`, `services/metrics.py`, tests `test_tls_admin.py`.
- **Deploy:** `apply-tls.sh` (ny) + `hypervisionplc-scada-tls.{path,service}`, `cert-deploy.sh` (install-dir), `tls-letsencrypt.sh` (HTTP-01, ikke-interaktiv brug fra hjælperen), `nginx-hypervisionplc-scada.conf` (acme-location), `install.sh`.
- **Frontend:** `pages/Certificates.svelte`, `lib/certificates.ts` (+ test), menu og route i `App.svelte`, manual `13-system.md`.

## Risici
- Forkert nginx-konfiguration ved HTTP-01 kan bryde port 80. Mod det står `nginx -t` og at kun én `location` tilføjes.
- Kan ikke testes fuldt mod Let's Encrypt, før Pi'en er public; afprøves med `--dry-run` mod staging, når DNS/porte er klar.
- Lang opgave: implementeres i to commits. (a) Side + selvsigneret/CSR/import + hjælper. (b) Let's Encrypt-delen.

---

# Plan: backup-destinationer + tidsplan (v3.23.0) — 2026-11-04

**Besluttet (Jan, 2026-11-04):** flere destinationer · indhold = konfiguration + trend-snapshot · "intern" = netværksshare (SMB/NFS) · paramiko (LGPL-2.1) godkendt til SFTP/SCP · samlet **scheduler** for backup. Styring via integrationer (tidl. 3.23) rykkes til 3.24, MQTT til 3.25.

**Mål:** System › Backup får en liste over destinationer (metode, adresse, mappe, login, hvad der sendes, hvor mange der beholdes) og én samlet tidsplan, der laver den lokale backup og sender den videre. Fejl ses på siden, på Status, i `/metrics` og som SYS-alarm.

## Trin
1. **Tidsplan (scheduler)** `services/backup_scheduler.py`: erstatter `auto_backup_loop` (fast interval fra `SCADA_BACKUP_HOURS`). Plan gemt i DB: *hver N. time* / *dagligt kl. HH:MM* / *ugentligt (dage + kl.)*; standard = nuværende (24 t), så intet ændrer sig ved opgradering. Næste kørsel vises; "Kør nu"-knap. Én kørsel ad gangen (lås); en kørsel, der er gået glip af (slukket Pi), tages ved opstart + 5 min.
2. **Destinationer** (tabel `backup_targets`; hemmeligheder i `secrets.json`, skriv-kun):
   - **SFTP / SCP** (paramiko): adgangskode eller SSH-nøgle (nøglen genereres på Pi'en; kun den offentlige del vises, så den kan lægges i `authorized_keys`). Værtsnøgle fastlåses ved "Test forbindelse" (TOFU), ændret nøgle = fejl.
   - **FTP / FTPS** (stdlib `ftplib`, FTPS = eksplicit TLS, standard med certifikattjek).
   - **HTTPS** (httpx, `PUT` eller `POST` multipart til en URL, valgfri Bearer/Basic) — fx Nextcloud/WebDAV eller egen modtager.
   - **SMB** (Windows-share/NAS) — se spørgsmål nedenfor. **NFS**: monteres af root-helperen (`/usr/local/sbin/hypervision-backup-mount`, fast mountpunkt `/mnt/hv-backup/<id>`, kun `nfs`, ingen vilkårlige options) og afmonteres efter kørslen.
   - Pr. destination: til/fra, hvad der sendes (konfig, trend), *behold N* (oprydning af egne filer på fjernsiden efter navnemønster), timeout, "Test forbindelse" (skriver og sletter en lille testfil).
3. **Afsendelse:** efter lokal backup sendes filerne til hver destination parallelt i tråde (event-loopet blokeres ikke); skriv til `navn.part` → omdøb (ingen halve filer); SHA256 i filnavn/sidecar; 2 genforsøg. Resultat pr. destination (tid, størrelse, fejltekst uden hemmeligheder) gemmes og vises.
4. **Observability:** log med kontekst (destination, metode, fil, varighed), tællere `scada_backup_runs_total{result}`, `scada_backup_upload_total{target,result}`, `scada_backup_last_success_timestamp{target}`; Status-kort; SYS-alarm `sys:backup-target` når en destination fejler to kørsler i træk (ophører ved næste succes). Audit ved ændring af destinationer (uden hemmeligheder).
5. **UI** `pages/Backup.svelte` (+ `lib/backupTargets.ts` med tests): tidsplan, destinationsliste, formular pr. metode, test-knap, seneste resultater.
6. **Deploy:** `install.sh` (paramiko via pip i venv; `nfs-common` + sudoers-linje for mount-helper), manual-afsnit, CHANGELOG/RELEASE_NOTES/FEATURES.

## Risici
- Store trend-snapshots over langsom forbindelse → upload i tråd med timeout, måles på Pi'en.
- Hemmeligheder (adgangskoder, SSH-nøgle) må aldrig nå browser/log → skriv-kun, `_safe_error`.
- NFS kræver root → smal helper, kun faste mountpunkter, reviewer.
- Berørte filer: `services/backup.py`, ny `services/backup_targets.py` + `backup_scheduler.py`, `api/backup.py`, `storage/db.py`, `main.py`, `services/metrics.py`, `services/health*.py`, `deploy/install.sh` + ny helper, frontend Backup-side.

---

# Plan: integrationsmodel (Node-RED, Home Assistant, tredjepart) — 2026-11-03

**Besluttet (Jan):** retning **C** (kerne-API + adaptere) · kun læs først (skriv = trin 3, valgfrit) · `aiomqtt` ved trin 4 · afgrænsning pr. nøgle. Fuldt design: [docs/INTEGRATION_DESIGN.md](docs/INTEGRATION_DESIGN.md).

**Trin:** 3.21 nøgler + læse-API (`/api/v1/integration/{info,points,values,history,alarms,openapi.json}`, side *System › Integrationer*, hastighedsgrænse, audit, `/metrics`) → 3.22 SSE-strøm → 3.23 styring (valgfri, gennem betjeningstjenesten) → 3.24 MQTT + Home Assistant Discovery.

**Sikkerhedsprincipper:** nøgler genereres i browseren og gemmes kun som SHA-256 (serveren returnerer aldrig værdien); en nøgle er en egen principal, der aldrig kan bruge admin-/konfigurations-API'et eller en session; integrationer læser kun fra live-cachen (aldrig PLC'en direkte).

---

# Plan: alarmnotifikation (webhook + e-mail) — 2026-11-03

**Status:** i gang. **Beslutninger (Jan, 2026-11-03):** kanaler **webhook + e-mail** · beskeder for **høj prioritet, ny og ophørt** · merge til main gjort (v3.18.1).

**Hvorfor:** SCADA kan i dag kun vise alarmer på siden. Ingen får besked, når en PLC mister forbindelsen, strømforsyningen er for svag (SYS-alarm), eller en høj-prioritets-alarm rejses, og det var den største mangel i sammenligningen med andre SCADA-systemer. Webhook'en er samtidig første skridt mod integrationsmodellen (Node-RED, Home Assistant, ntfy, Slack/Teams m.fl.).

## Opbygning
1. **Kilde:** `AlarmService._event` (det ene sted alle hændelser går igennem) kalder registrerede lyttere; notifikation reagerer på `raise` (også eskalering) og `clear`. `sys:notify` (selve notifikationsfejlen) og `ack` giver aldrig besked (ingen løkke).
2. **`services/notifier.py`** — kø + arbejdsopgave: hændelser samles i **ét parti pr. `batch_s`** (standard 20 s, 5–300; stormbeskyttelse: højst 20 alarmer pr. besked, resten som "+N flere"), filtreres på **mindste prioritet** (standard høj) og "send også når den ophører", og sendes til de slåede-til kanaler. **Forsøg igen** 3 gange (5 s, 30 s, 120 s); hukommelse for de seneste 50 afsendelser (kanal, resultat, fejltekst — aldrig hemmeligheder) til siden; tællere til `/metrics`; struktureret log.
3. **Webhook:** `POST` JSON `{type, event, time, instance, version, alarms:[{key, tag, plc, kind, level, priority, state, message, raised_at}]}`; valgfri `Authorization: Bearer <token>`; 10 s timeout; kun `http`/`https`. **Adressen er en hemmelighed** (Home Assistant-webhook-id, ntfy-emne, Slack-URL): skriv-kun, API'et viser kun værten og "sat".
4. **E-mail:** stdlib `smtplib` i en tråd (ingen ny afhængighed); STARTTLS (standard) / SSL / ingen; fra/til (flere modtagere); dansk emne og tekst; adgangskode skriv-kun i `secrets.json`.
5. **API (`api/notifications.py`, kun admin):** `GET /api/system/notifications` (konfiguration uden hemmeligheder + seneste afsendelser), `PUT` (validering; hemmeligheder kun hvis felterne er udfyldt; eksplicit "fjern"), `POST /test` (sender en prøvebesked til hver slået-til kanal og svarer med den præcise fejl pr. kanal). Alt i audit-loggen uden værdier.
6. **Frontend:** siden **System › Notifikationer** (admin).
7. **Observability:** mislykkede afsendelser i række → problem `notify` på Status + SYS-alarm; `scada_notifications_sent_total{channel}`, `scada_notifications_failed_total{channel}`, `scada_notification_queue` i `/metrics`.
8. **Tests:** batching/filter/retry/formater, ingen hemmeligheder i svar/log/audit, httpx mock-transport og falsk SMTP, API-adgang (kun admin), validering, frontend-hjælpefunktion. Reviewer før commit.

## Version og lag
MINOR: `3.19.0`. Ingen skemaændring (konfiguration i `<data>/config/settings.json` via `sysconfig`, hemmeligheder i `secrets.json`). Lag: service-laget; udgående HTTP til en *ekstern* adresse (ikke en PLC) kræver en dokumenteret undtagelse i ARCHITECTURE.md (som OTA fra GitHub).

## Risici
- **Alarmstorm** → parti + loft pr. besked. **Ingen besked er garanteret** (netværk nede): derfor forsøg igen, status på siden og alarm ved gentagne fejl. **Hemmeligheder** i URL → skriv-kun. **SSRF**: kun admin kan sætte adressen, og kun http/https; LAN-adresser er tilladt (Node-RED).

---

# Plan: Let's Encrypt-certifikat på Pi'en (TLS trin 2) — 2026-11-03

**Status:** værktøjet er bygget og installeret (v3.17.0), men **udstedelsen er parkeret** (Jan, 2026-11-03: "vi venter til vi er helt klar med at gå public"). Bemærk: movie.laces.dk bruger HTTP-01 (offentlig A-record + port 80/443 til proxy-VM'en, `certbot --nginx`) og har ingen deSEC-konto; når SCADA går public, vælges metoden igen (HTTP-01 eller DNS-01 via deSEC).

**Beslutninger (Jan, 2026-11-03):** hostnavn **scada.laces.dk** · DNS-01 via **deSEC** (one.com har intet API → CNAME-delegering) · værktøj **certbot** (Jans valg frem for lego). Tjekket: Raspberry Pi OS Trixie har `certbot` 4.0.0 (Apache-2.0) som apt-pakke; `certbot.timer` fornyer automatisk. **Rettelse (2026-11-03):** Debians `python3-certbot-dns-desec` er version **1.2.1**, som IKKE følger CNAME'er (kun den nyere PyPI-version 1.3.2 gør) — derfor bruges pluginet ikke; i stedet en lille `--manual-auth-hook` (`deploy/desec-acme-hook.sh`, curl mod deSEC's API) der skriver TXT-posten i den zone, CNAME'en peger på. Ingen pip, ingen plugin-afhængighed. Fundet af reviewer; bekræftet ved at hente pakken fra Pi'ens apt og læse koden.

**Udgangspunkt:** Pi'en (10.1.1.33, Trixie, armv7, NTP i sync) kører nginx med TLS og et **selvsigneret** certifikat i `/etc/hypervisionplc-scada/tls/{fullchain,privkey}.pem` (nginx peger dér; ændres ikke).

## Hvordan det virker
Let's Encrypt kan ikke nå Pi'en (privat adresse), så ejerskab bevises med en **DNS-01**-udfordring: certbot (deSEC-pluginet) sætter en TXT-post `_acme-challenge.scada.laces.dk`. Fordi one.com ikke har et API, er den post en **CNAME** hos one.com til en zone, vi selv styrer hos **deSEC** (gratis, har API). pluginet følger CNAME'en og skriver TXT-posten i deSEC med et token. Certifikatet gælder 90 dage og fornyes automatisk.

## Trin
1. **`deploy/tls-letsencrypt.sh`** (ny, root): `install` (apt: `certbot curl`), `set-token`, `set-target <zone>`, `issue <hostnavn> <e-mail> [--dry-run]`, `status`, `renew-test`. `--dry-run` kører hele DNS-forløbet mod **Let's Encrypts staging** uden at gemme noget (og uden at røre nginx) — det er testen, før der udstedes rigtigt. Rigtig udstedelse: `certbot certonly --manual --preferred-challenges dns --manual-auth-hook "desec-acme-hook.sh auth" --manual-cleanup-hook "desec-acme-hook.sh cleanup" --cert-name hypervision-scada -d <hostnavn> --deploy-hook <deploy-hook>`.
2. **Deploy-hook** `deploy/cert-deploy.sh` (kører som root efter udstedelse OG hver fornyelse, gemt i certbots fornyelsesopsætning): kopierer `fullchain.pem`/`privkey.pem` fra `/etc/letsencrypt/live/hypervision-scada/` til nginx-stierne **atomisk** (midlertidig fil → `mv`), `nginx -t`, derefter `systemctl reload nginx`; slår `nginx -t` fejl, gendannes det forrige certifikat — **ingen lockout** (det selvsignerede er tidligere kopieret til `*.selfsigned`).
3. **Hemmeligheder:** deSEC-tokenet ligger i `/etc/hypervisionplc-scada/letsencrypt/desec.ini` (`dns_desec_token = …`, root, 0600, **uden for git**), aldrig i logs, web-API eller backup. Scriptet læser det fra stdin (ikke fra kommandolinjen).
4. **Fornyelse:** Debians `certbot.timer` (to gange i døgnet) kører `certbot renew`; deploy-hooken sørger for nginx. Ingen egen timer.
5. **System › Status (observability):** kort *Certifikat* — udsteder, udløb, dage tilbage; selvsigneret markeres; **gul under 21 dage, rød under 7**; `scada_tls_cert_expiry_seconds` i `/metrics`. Tjenesten (brugeren `scada`) kan ikke læse certifikatmappen (root 0750), så hooken/`install.sh` skriver **metadata** (udsteder, emne, udløb, selvsigneret, fingeraftryk) til `/var/lib/hypervisionplc-scada-net/cert.json` (root-ejet, 0644), og backend regner dage tilbage ved hver aflæsning. Fanger en fornyelse, der er stoppet.
6. **HSTS** slås først til efter et gyldigt LE-certifikat (nginx-konfigurationens egen regel): valgfrit trin bagefter.
7. **Dokumentation:** `docs/TLS_LETSENCRYPT.md` (deSEC + one.com trin for trin, fejlsøgning), manualafsnit, `README.md`, `FEATURES.md`.
8. **Tests:** scripts med falsk `certbot`/`nginx`/`openssl`/`apt-get`: atomisk udskiftning, gendannelse ved fejlet `nginx -t`, token aldrig i log, hook idempotent; backend: udløbs-parsing + grænser, metrics-linje. **Prøves på Pi'en:** først `--dry-run` (staging), derefter produktion.

## Versionering og lag
MINOR (ny funktion): `3.17.0`. Ingen skemaændring. Lag: shell-scripts + systemd uden for programmappen (som netværkshjælperen); `services/health.py` får certifikat-læsningen (ingen PLC-kald). Ny afhængighed: **certbot** (Apache-2.0, apt-pakke; AGPL-kompatibel) — valgt af Jan; plus `curl` (allerede installeret).

## Risici
- **DNS/CNAME forkert** → udstedelse fejler (selvsigneret certifikat bevares; fejlen vises i scriptets udskrift og logfil).
- **Let's Encrypts rate-limits** (5 fejl/time/navn, 50 certifikater/uge) → derfor `--dry-run` (staging) først.
- **Navnet skal pege på Pi'en** for brugerne: `scada.laces.dk` → 10.1.1.33 i jeres interne DNS (eller en A-post til den private adresse hos one.com). Uden det virker certifikatet, men browseren finder ikke navnet.
- **deSEC-forløbet** (TXT-post i zonen, 45 s ventetid, Let's Encrypt følger CNAME'en) kan kun bevises med `--dry-run` på Pi'en med en rigtig deSEC-konto — det er første trin, når tokenet er der.
- **Pi'ens tid** skal være rigtig (NTP) — ellers afvises certifikatet.

## Dit bidrag (det kan jeg ikke gøre for dig)
1. Opret en gratis **deSEC**-konto (desec.io), opret en zone (fx `scada-laces.dedyn.io`) og et **token** (kun til DNS-ændringer).
2. Hos **one.com**: opret CNAME `_acme-challenge.scada.laces.dk` → `_acme-challenge.scada.laces.dk.scada-laces.dedyn.io` (det præcise navn får du af `docs/TLS_LETSENCRYPT.md`, når den er skrevet).
3. Sørg for, at `scada.laces.dk` peger på 10.1.1.33 i jeres DNS.
4. Giv mig tokenet **på Pi'en** (jeg beder om det, når scriptet er klart; det skal aldrig i chatten eller git).

---

# Plan: oprydning, MQTT/direkte board-adgang og observability (2026-11-01)

**Status:** udkast — afventer Jans valg (se "Beslutninger" nederst). Ingen kode ændret.

## Del A — Punkt 3: ryd op i åbne fejl og gamle `in-progress`

**Hvorfor:** `FEATURES.md` har ~20 punkter, der stadig står som `in-progress` (v0.27–v0.58), og `BUGS.md` har 7 åbne punkter. Det skjuler, hvad der reelt mangler, og de åbne fejl rammer drift (alarm der udebliver, tab af ugemte ændringer).

### A1. Åbne fejl (rækkefølge efter værdi/risiko)
| # | Fejl (BUGS.md) | Foreslået løsning | Størrelse |
|---|---|---|---|
| 1 | v0.27.0 #7: ingen alarm ved `bad`-kvalitet (ekstern slave / ST) eller PLC `stopped` uden adgangskode | `alarms.evaluate` udvides med kommunikationsalarm pr. kilde (PLC / rtu / mbx) | M |
| 2 | v0.27.0 #9: én `PlcApiError` på ét område markerer ALLE PLC'ens tags `comm_error` | `poll_once` markerer kun tags i det område/program, der fejlede | M |
| 3 | v0.27.0 #18: "Admin" og "admin" kan være to brugere | unikt indeks på `lower(username)` + håndtering af eksisterende dubletter; test | S (skema — tjek MAJOR-reglen) |
| 4 | v0.27.0 #13: Origin-tjek sammenligner med `Host` uden port | sammenlign host + port korrekt bag nginx | S |
| 5 | v0.27.0 #15: `None`/decimaltal fra PLC giver rå `TypeError`/stille trunkering | validér i `read_bulk`/`_ext_value` → `PlcApiError` | S |
| 6 | v0.27.0 #16: dybt indlejret SVG → `RecursionError` | dybdegrænse i `svg_sanitize` med læsbar fejl | S |
| 7 | v3.7.0: Tegn mister ugemte ændringer ved sidenavigation | fælles "forlad siden"-vagt i `App.svelte`, som Tegn tilmelder sig | S–M |
| 8 | v0.131.4: `_compute` ikke cachet | **mål først på Pi 4** (event-loop-lag fra Del C); cache kun hvis målingen viser behov | afventer måling |

Hver rettelse: registreres i BUGS.md med løsning, test i faktisk kontekst, PATCH-bump, CHANGELOG/RELEASE_NOTES, OTA-pakke. #1–#2 berører PLC-læsning/alarmer → `reviewer` før commit.

### A2. Gamle `in-progress`-punkter
Koden er leveret og senere versioner bygger ovenpå, men "afventer Jans test" er aldrig lukket. Kun Jan kan bekræfte, at de virker. Forslag: en kort tjekliste (pr. punkt: hvor i UI'et, hvad skal ses) som Jan krydser af; bekræftede → `done`, resten → BUGS.md. Docs-only commit (ingen versionsbump).

### A3. Den gamle bindingsmodel (symbolstandard fase 8)
Funktionsanalysen (27.10) viser, at simple bindinger stadig kan noget, wizarden ikke kan (frit element uden symbol, `click:goto` på ikke-symboler). Alternativer:
- **A. Behold begge, markér simple bindinger som "enkel tilstand"** — ingen migration, mindst risiko. *Anbefalet.*
- B. Migrér simple bindinger automatisk til symbolopsætning — stort, skema-/MAJOR-ændring, risiko for tabt opførsel.
- C. Fjern simple bindinger — bryder eksisterende tegninger. Frarådes.
Beslutningen noteres i FEATURES.md, og punktet lukkes.

### A4. Repo
`scada-*.tar` er git-ignoreret (0 sporede) og roder kun lokalt. Forslag: behold de seneste 3 i roden, flyt resten til et ignoreret arkiv — sletning kræver Jans accept.

---

## Del B — Punkt 5: MQTT og direkte adgang til expansion board

### B1. Direkte adgang til expansion board uden om PLC'en — vurdering
Fundet i PLC-dokumentationen (`docs/expansion/PLC_INTEGRATION_MANUAL.md`, `docs/manual/06_Modbus_Interface.md`):

| Vej | Kan SCADA bruge den? |
|---|---|
| **Modbus TCP (port 502/503)** — boardets data-plan | **Nej.** Boardet accepterer KUN forbindelser fra ÉN fast IP (`plc_ip`). Sættes den til SCADA, mister PLC'en sine boards; SCADA fra en anden IP afvises. Ingen protokol-auth. |
| **Board-REST (port 8080)**: `/api/status`, `/api/channels`, `/read`, `/write` | Teknisk ja (ikke begrænset af `plc_ip`, kræver Bearer/Basic), men `/read`/`/write` er **ad-hoc diagnostik, "ikke til høj-frekvent drift"**: én synkron RTU-transaktion på samme RS485-bus som PLC'ens ST-logik bruger, uden at PLC'en ved det → forstyrrer timing og kan give timeouts i ST-programmer. |
| **PLC'ens `/api/ext/mbx/...`** (som i dag) | Ja — PLC'en styrer busadgang, prioritet (`prio=high`) og rate-budget. |

**Hvad ville direkte adgang give?** (1) Ingen belastning af PLC'ens 32/48-posters ext-cache og ≤5 req/s-budget; (2) boardets sundhed/kanalstatistik uafhængigt af PLC'en; (3) data selv hvis PLC'en er nede.
**Hvad koster det?** Bryder projektets faste ramme (CLAUDE.md: al PLC-kommunikation kun via PLC'ens REST API; ARCHITECTURE princip 2), board-token skal ligge i SCADA, og busdeling sker uden koordinering.

**Anbefaling: ingen direkte busadgang.** Dæk behovene inden for rammen:
1. **Boardets sundhed** findes allerede i PLC'ens `/api/metrics` (`expansion_board_online{board}`, `mbx_channel_requests_total/_ok/_timeouts/_errors/_last_ok_age_ms`). SCADA henter og viser dem (Del C4). Det dækker "er boardet oppe, og hvor mange timeouts".
2. **Cache-presset**: bed PLC-teamet om (a) større ext-cache eller (b) et bulk-endpoint for flere eksterne adresser (jf. HYPERVISIONPLC_ANALYSE §7). Det er en PLC-ændring, ikke en SCADA-omgåelse.
3. **Hvis Jan alligevel vil have det:** kun en snæver, **skrivebeskyttet undtagelse**: `GET /api/status` på boardets REST (ingen busaktivitet) til sundhedstjek, i PLC-klient-laget som en ny `board_client`, token i `secrets.json`, undtagelsen dokumenteret i ARCHITECTURE.md. Aldrig `/read`, `/write` eller Modbus TCP. Kræver Jans eksplicitte accept, fordi det ændrer den faste ramme.

### B2. MQTT-udgang — hvorfor og hvad opnår vi
**Hvorfor:** SCADA er i dag en lukket ø — andre systemer skal polle web-API'et eller læse CSV. MQTT lader SCADA *skubbe* værdier og alarmer ud til en mægler (Mosquitto/EMQX), som Home Assistant, Node-RED, Grafana (via Telegraf), BMS og sky kan abonnere på.

**Hvad opnår vi:** integration uden ekstra belastning af SCADA/PLC; fælles datakilde til dashboards og langtidshistorik uden for Pi'ens SQLite; alarmer videre til andre notifikationssystemer (delvis løsning på den manglende notifikation); Home Assistant-autodiscovery.

**Afgrænsning (første version): kun udgående og kun læsning.**
- Publicér tag-værdier (kun tags valgt til MQTT), alarmtilstand og SCADA/PLC-status. Topic `hvscada/<anlæg>/<plc>/<tag>` (JSON `{v, q, ts, unit}`), retained + LWT (`online/offline`).
- **Ingen indgående skrivning.** En skrivning via MQTT skulle gennem betjeningstjenesten (min/max, tilbagelæsning, audit, rolle) — udskydes til en senere fase med eget design.
- Lag: ny `services/mqtt_publisher.py` abonnerer på `live_cache` (ingen PLC-kald; lag-reglen overholdes). Konfiguration under System › MQTT (admin). Mægler-adgangskode i `secrets.json`; API'et returnerer kun `has_password`. TLS til mægler. Audit på konfigurationsændringer. Begrænset publiceringsrate (ændring + keepalive, som trends).
- **Ny afhængighed — skal godkendes:** forslag `paho-mqtt` (dual EPL-2.0 / EDL-1.0 = BSD-3; vælg EDL-1.0) eller `aiomqtt` (BSD-3, bygger på paho). Licens tjekkes før tilføjelse.
- Test: mock-mægler, fejl/genopkobling, ingen hemmeligheder i log, kun valgte tags publiceres. Bemærk: adgang pr. tegning gælder GUI; MQTT er en system-integration og følger en eksplicit tag-liste.

**Risici:** data forlader SCADA (mitigeres af eksplicit tag-liste + TLS); belastning på Pi (rate-grænse); retained-beskeder med forældede værdier (LWT + kvalitet i payload).

---

## Del C — Observability: systemhelbred, metrics, Prometheus

**I dag:** `/api/health` returnerer kun `{status, version, build, source_url}` og bruges af OTA-rollback — den skal forblive minimal og hurtig. Ingen metrics, ingen overvågning af SCADA selv. G1 (scrypt blokerer event-loopet) blev først fundet ved manuel måling — netop det en metric ville vise.

**Mål:** (1) se på ét sted om SCADA og PLC'erne har det godt, (2) lade Prometheus/Grafana scrape SCADA, (3) få alarm om SCADA's *egne* problemer.

### C1. Detaljeret helbred (GUI + API)
`GET /api/health/details` (tekniker+) og siden **System › Status** (grøn/gul/rød):
- Database: svar-test, WAL-størrelse; `trends.db`-størrelse og skrivehastighed.
- Pr. PLC: kommunikationsstatus, alder på seneste værdi, poll-kald/s mod budget (≤5), antal 429 og seneste, SSE tilsluttet.
- WebSocket-klienter, aktive/ukvitterede alarmer, ugeprogram-fejl.
- Host: uptime, hukommelse, ledig disk, CPU-temperatur og undervoltage/throttling på Pi, alder på seneste backup.
- **Event-loop-lag** (lille periodisk opgave) — afslører blokeringer som G1.

### C2. Prometheus-endpoint
`GET /metrics` i tekstformat. **Adgang:** ikke åben — separat scrape-token (skrive-kun i `secrets.json`) eller localhost/nginx-allowlist, fordi tag- og tegningsnavne er følsomme. Eksempler:
`scada_up`, `scada_build_info{version,build}`, `scada_event_loop_lag_seconds`, `scada_plc_up{plc}`, `scada_plc_last_ok_age_seconds{plc}`, `scada_plc_requests_total{plc,result}`, `scada_plc_rate_limited_total{plc}`, `scada_plc_poll_duration_seconds{plc}`, `scada_ws_clients`, `scada_alarms_active{state}`, `scada_trend_writes_total`, `scada_db_bytes{db}`, `scada_disk_free_bytes`, `scada_host_temp_celsius`, `scada_last_backup_age_seconds`.
**Valg:** håndskrevet eksponering (~100 linjer, ingen afhængighed — anbefalet til Pi) eller `prometheus_client` (Apache-2.0, kompatibel — kræver godkendelse).

### C3. Interne alarmer om SCADA selv
Genbrug alarmmotoren: pseudo-tags (`sys:disk_free`, `sys:loop_lag`, `sys:backup_age`, `sys:temp`) med grænser. Giver kvittering/historik/notifikation uden ny mekanisme.

### C4. PLC'ernes egne metrics (inden for rammen)
PLC'en udstiller `/api/metrics` (Prometheus-tekst, uden auth; inkl. `expansion_board_online`, Modbus-statistik, RS485-trafik, heap). SCADA's PLC-klient henter den lavfrekvent (fx hvert 30–60 s; tæller mod rate-budgettet) og viser udvalgte værdier i System › Status; evt. gen-eksponeret i `/metrics` med `plc`-label, så ét scrape dækker alt. Det løser B1 punkt 1 uden direkte board-adgang.

### C5. Drift
- Valgfrit: systemd `WatchdogSec` + `sd_notify` (SCADA genstartes, hvis event-loopet hænger) — testes på Pi.
- Eksempel-Grafana-dashboard og Prometheus-scrape-konfiguration i `docs/observability/`.
- Manualen: afsnit om Status og metrics; manualbillede af Status-siden.

---

## Faser og versionering (hvert trin = egen commit, OTA-pakke, doku)
1. **Del A** fejl 3–6 (små) — PATCH hver; `reviewer` på #1–#2.
2. **C1 + event-loop-lag** — MINOR. *Mål først på en rigtig Pi 4 (afgør A1 #8).*
3. **C2 + C4** — MINOR.
4. **C3** — MINOR.
5. **B2 MQTT** — MINOR, efter at afhængigheden er godkendt.
6. **A2/A3/A4** (doku/oprydning) — docs-only, ingen bump.

**Berørte filer (skøn):** `backend/app/services/health.py` (ny), `api/system.py`/`routes.py`, `services/alarms.py`, `services/plc_runtime.py`, `plc/client.py` (hent `/api/metrics`), `services/mqtt_publisher.py` (ny), `storage/secrets.py`, `frontend/src/pages/Status.svelte` (ny) + menu, `deploy/nginx-hypervisionplc-scada.conf` (allowlist for `/metrics`), `deploy/hypervisionplc-scada.service` (watchdog), manual, tests.

## Beslutninger (Jan)
1. **Direkte board-adgang:** (a) nej — brug PLC'ens `/api/metrics` og bed PLC-teamet om bulk/større cache *(anbefalet)* · (b) snæver skrivebeskyttet undtagelse for boardets `GET /api/status`.
2. **Ny afhængighed til MQTT:** `paho-mqtt` / `aiomqtt` — OK at undersøge licens og tilføje?
3. **Prometheus:** håndskrevet eksponering *(anbefalet)* eller `prometheus_client`.
4. **Bindingsmodel:** behold begge (A) *(anbefalet)*.
5. **Tjekliste til de gamle `in-progress`:** skal jeg lave den, så du kan kvittere?
6. **Rækkefølge:** start med fejl + Status-side, eller MQTT først?

---

# Plan: Symbol-editor — tilslutningspunkter pr. symboltype (Jan, 2026-10-30)

**Mål:** I en egen sektion kan teknikere rette et bibliotekssymbols tilslutningspunkter (rørenes fikspunkter): tilføje, flytte, fjerne, eller nulstille til de automatisk fundne. **Symboler der allerede står i en tegning arver IKKE ændringen** — kun symboler der indsættes bagefter.

**Beslutning:** punkterne bygges ind i symbolet ved indsættelse (`data-hv-ports="fx,fy;fx,fy"` på symbolets rod, brøkdele af symbolets egen boks — samme form som rørenes referencer). Rør-værktøjet bruger `data-hv-ports`, hvis det findes, ellers de automatiske punkter som i dag. Alternativer: slå punkterne op på serveren ved hver tegning (så arver alle — ikke ønsket) · gemme pr. tegning (ingen genbrug). Indbygning giver præcis "kun nye".

## Trin
1. **Backend:** ny tabel `symbol_ports (type TEXT PRIMARY KEY, ports TEXT NOT NULL, updated_by, updated_at)` (CREATE IF NOT EXISTS — ingen migration). Service + API i `api/symbols.py`: `GET /api/symbol-ports` (alle), `PUT /api/symbol-ports/{type}` (validering: kendt type, 1–32 punkter, 0 ≤ f ≤ 1), `DELETE` (= automatisk). Rolle tekniker/admin (som Tegn), audit-log. Med i backup/gendan. Tests.
2. **Frontend, ny side "Symboler"** under Opsætning (`pages/SymbolEditor.svelte`): liste over bibliotekets symboler (søg, kategorier) → stort preview med punkterne: klik på kanten/en streg for at tilføje (fanger til rørender/kantmidter), træk for at flytte, Delete/højreklik for at fjerne, *Nulstil til automatisk*, *Gem*. Viser "Ændringen gælder symboler, du indsætter fremover — symboler i tegningerne beholder deres punkter."
3. **Tegn:** ved indsættelse af et symbol med rettede punkter sættes `data-hv-ports`; `portsOf` i `scada-core.js` bruger dem. Rensningen beholder data-attributter (test).
4. Manual + manualbillede, FEATURES/CHANGELOG/RELEASE_NOTES. Version MINOR.

**Berørte filer:** `backend/app/storage/db.py`, `backend/app/services/symbol_ports.py` (ny), `backend/app/api/symbols.py`, backup-service, `frontend/src/pages/SymbolEditor.svelte` (ny), menu/routing i `App.svelte`, `frontend/svgedit-host/scada-core.js`, `pipes.js`, `DrawEditor.svelte` (indsæt), tests begge steder.

**Risici:** symboler der drejes/spejles — brøkdele i symbolets egne koordinater følger med (som rørene). Symboler med `data-hv-ports` fra et gammelt bibliotek ændres ikke — det er netop ønsket; evt. senere en knap i Tegn "Hent punkter fra biblioteket" for ét symbol.

---

# Plan: ny tegne-editor — egen Svelte-UI på `@svgedit/svgcanvas` (option B, 2026-10-30)

**Mål:** Tegn bliver et SCADA-værktøj i stedet for en generel illustrationseditor. Behold SVG-motoren (`@svgedit/svgcanvas` 7.4.2, MIT) og tegningsformatet; erstat SVG-Edits UI + iframe med egne Svelte-komponenter.

**Beslutning:** B frem for A (flere udvidelser i SVG-Edit — vi kæmper fortsat mod dens UI og patcher minificeret kode) og C (maxGraph/Fabric — kræver konvertering, mister id'er/bindinger). Tegninger, id-regler og backend-rensning er uændrede → ingen migration.

## Nyt layout (erstatter 3 værktøjslinjer: vores øverste, SVG-Edits top-kontekstlinje, SVG-Edits venstre)
```
┌ Topbar: Tegning ▾ (ny/åbn/version) · Gem kladde · Gem og udgiv │ Fortryd Gentag │ Størrelse │ Zoom − 100% + Tilpas ┐
├──┬──────────────────────────────────────────────────────────────┬───────────────────────┤
│▣ │                                                              │ Inspektør (faneblade) │
│╱ │                       Lærred                                 │  Egenskaber: X Y B H ∠│
│⌐ │                                                              │   fyld/streg/tekst    │
│▭ │                                                              │  Binding: tag, guide  │
│T │                                                              │  Lag / objekttræ      │
│◇ │                                                              │                       │
│⊞ │                                                              │                       │
├──┴──────────────────────────────────────────────────────────────┴───────────────────────┤
└ Statuslinje: x,y · gitter ☐ fang gitter ☐ fang objekter ☐ trin [10] · værktøjshjælp           ┘
```
- **Venstre værktøjsrail (SCADA-orienteret, få knapper, grupper med undermenu):** Vælg · Rør (ortogonal, Fase 3) · Linje/pil · Form ▸ (rektangel, ellipse, polygon, stjerne, fri) · Tekst · Symbol ▸ (bibliotek/favoritter, træk-og-slip) · Display/Omskifter · Panorér. Fjernes: pipette som værktøj (bliver knap i Inspektør), billede, SVG-Edits formbibliotek (talebobler m.m.).
- **Topbar:** kun dokument-handlinger + fortryd/zoom. Ingen kontekst-felter dér.
- **Markeringshandlinger** (justér, fordel, gruppér/opløs, frem/tilbage, dupliker, slet) vises som en flydende lille linje over markeringen + i højreklik-menu — ikke i topbaren.
- **Inspektør til højre** samler: geometri, stil, tag-binding, symbolguide, id/navn — erstatter dagens højrepanel i DrawEditor.svelte.
- Statuslinje: koordinater + hjælpelinje-indstillinger (i dag gemt i menu).

## Trin
**Status 2026-10-30:** trin 1 (v2.13.0), trin 2 (delt kerne — gjort i trin 1) og trin 3 (v2.14.0: panel, svævende linje, højreklikmenu, statuslinje) er lavet. Mangler fra trin 3: lag/objekttræ og at topbaren samles (bruger stadig Tegns nuværende øverste linje). Trin 4 (v2.15.0, rør) og trin 5 (v2.17.0, træk-og-slip; justér/fordel kom i v2.14.0) er lavet. Objekttræ (v2.18.0) og trin 6 (v3.0.0: den nye editor er Tegn, SVG-Edit-appen fjernet) er lavet — **planen er færdig**. Topbaren blev ikke bygget om: Tegns øverste linje dækker allerede tegning/gem/udgiv/størrelse; fortryd/gentag står i værktøjslinjen (Jans ønske) og zoom i bunden.

1. **Motor uden UI** (største risiko): `lib/draw/engine.ts` initialiserer `SvgCanvas` direkte i en `<div>` (ingen iframe), wrapper events (selected/changed/zoomed) til Svelte-stores. Bevis: åbn, tegn rektangel, fortryd, gem → identisk SVG som i dag.
2. **Flyt vores funktioner ind** fra `svgedit-host/scada-editor.js` (1138 linjer) som moduler: gitter/fang (`draw/guides.ts`), id-regler/renameCopies (`draw/ids.ts`), symbolindsættelse, normalize/settle. Tests for id- og fanglogik. Rotations-patchen i `copy-svgedit.mjs` erstattes af egen rotationshåndtering.
3. **Nyt layout**: Topbar, ToolRail, Inspector, StatusBar, SelectionBar som Svelte-komponenter; dansk tekst direkte (ingen localize-hacks). Funktionsparitet med i dag.
4. **Rør-værktøj**: forankringspunkter på symboler, ortogonal routing, rør følger symbolet ved flytning (gemmes som almindelig `<path>` + `data-`-attributter der overlever serverens rensning — tjek rensningen først).
5. **Symbolpalet med træk-og-slip** + justér/fordel.
6. Fjern `svgedit`-pakken, `copy-svgedit.mjs`, `svgedit-host/` og `public/svgedit` når 1–3 er verificeret.

**Version (Jan, 2026-10-30):** når den nye editor er færdig og gjort til standard (trin 6), bumpes til **3.0.0**. Indtil da er hver fase en egen commit/version (MINOR), egen OTA-pakke, visuelt verificeret på 10.1.1.31. Fase 1–3 bag skifter (`?editor=ny`) indtil paritet, så Tegn aldrig er ubrugelig.

## Berørte filer
`frontend/src/pages/DrawEditor.svelte` (opdeles), ny `frontend/src/lib/draw/*`, `frontend/svgedit-host/*` (udfases), `frontend/scripts/copy-svgedit.mjs`, `frontend/package.json` (svgcanvas er allerede installeret; `svgedit` fjernes i trin 6), evt. backend SVG-rensning (trin 4), FEATURES.md, manual-billeder.

## Risici
- `svgcanvas` alene er dårligt dokumenteret; dele af værdien (stifelt-redigering, tekstredigering, kontekstmenu) ligger i SVG-Edit-UI'et → må genbygges. Trin 1 er proof-of-concept; holder den ikke, stop og vurdér igen.
- Paritet: mange små opførsler i scada-editor.js (fang, id'er, guide-hooks) — liste dem op før trin 2 og tjek af én for én.
- Manualens skærmbilleder skal tages om.

---

# Plan: passiv visning af positioner + 7-/11-segment display (2026-10-30)

## A. Kun passiv visning med positioner (fx 3-punkts omskifter der kun viser PLC'ens trin)

**Mål:** et symbol med positioner kan vise PLC'ens position uden at kunne betjenes og uden at kræve et kommando-tag.

**Beslutning:** nyt felt `passive: bool` (standard `false`) på symbolopsætningen, sammen med `op = positions`.
Alternativer: ny `op` (flere grene i al kode) · `view` + positioner (ændrer betydningen af `view`). Flaget er mindst invasivt.

**Adfærd når `passive = true`:**
- Trin 1: valget *Kun passiv visning* får for symboler med positioner en underindstilling "Vis symbolets position fra tilbagemelding". *Interaktiv betjening* uændret.
- Trin 2: kolonnen **Kommando** (og *Skrives som*, *Fejlsignal*) er grå/deaktiveret; **Tilbagemelding er krævet** på alle signaler i kontaktplanerne (ellers kan positionen ikke findes).
- Trin 3: kontaktplanerne beskriver tilbagemeldingens mønster pr. position (som nu).
- Trin 4: *Vis* låses til "PLC'ens position"; ingen valideringsalarm for "valgt position".
- Trin 5: "Kun passiv visning — intet at betjene" (ingen bekræftelse, nøglelås, klik-valg).
- Backend: kommando-tag ikke påkrævet/skrivbart; `operate` afviser (409 "kun visning"); låse og skrivning ryddes; runtime finder positionen kun fra tilbagemeldingen.
- Overview: symbolet får ikke `hv-clickable`/`hv-step`, markør er pil, tooltip "Kun visning — kan ikke betjenes". Lille mærke (øje/lås-fri) kan tilføjes ved tilstandsmærket.
- Skift mellem passiv og interaktiv bevarer kontaktplanerne (tilbagemeldingerne bliver til kommando-tags ved skift til interaktiv kræver nyt valg — vises som fejl i trin 2).

**Berørte filer (≈10):** `backend/app/services/symbols.py` (model, validering, plans), `symbol_runtime.py`, `backend/app/api/symbols.py` (operate), `symbol_convert.py`, `frontend/src/lib/symbolConfig.ts`, `SymbolGuide.svelte`, `Overview.svelte`, `symbolUi.ts`, tests (backend + frontend), manual kap. 06, FEATURES/CHANGELOG/RELEASE_NOTES.
**Version:** MINOR (ny feature) → 2.8.0.

## B. Display-element: 7-/11-segment, 1–16 cifre

**Mål:** ét bibliotekssymbol "Segment-display" med valgfri type (7 eller 11 segmenter) og 1–16 cifre, styret af ét tal-tag.

**Antagelse (bekræft):** *7-segment* = a–g + decimalpunkt (8 pladser pr. ciffer). *11-segment* = a–f, midterstregen delt i to (g1/g2), to lodrette midtersegmenter (i/l) og decimalpunkt = 11 — kan vise tal og de fleste store bogstaver.

**Løsning:** (1) Indsættelse i Tegn som *Omskifter med egne positioner*: felter *Type* (7/11) og *Antal cifre* (1–16) → tegner N cifre med segmenter som navngivne dele (`data-hv-pid`, fx `c3_a`). (2) Ny animationstype **Segmenter** (`segments`) på hele symbolet: kilde = tal-tag; parametre: type, cifre, decimaler, fortegn (−), foranstillede nuller (til/fra), farve tændt/slukket, justering (højre/venstre), vis "OFL" ved overløb. Teksten formateres som i `Værdi` (skala/decimaler fra tagget) og hvert tegn slår de rette segmenter til. (3) Hurtig opsætning i guiden: vælg tag → opretter animationen.
Alternativer: ét symbol pr. cifre-antal (mange biblioteksposter) · hvert ciffer sit tag (besværligt). Valgt: ét symbol, én animation.

**Berørte filer (≈12):** `frontend/src/lib/symbols.ts` (+ ny `segDisplay.ts`: tegning + tegn→segmenter), `animate.ts`, `symbolConfig.ts`, `AnimParams.svelte`, `DrawEditor.svelte`, `backend/app/services/symbols.py` (ASegments, ANIM_PARAMS, label), tests (formatering, tegn→segmenter, tegning 1–16 cifre, backend-validering), manual kap. 04/05/06/07, FEATURES/CHANGELOG/RELEASE_NOTES.
**Version:** MINOR → 2.9.0 (efter A).

## Rækkefølge og risici
1. A først (rører backend-datamodel og bør være færdig og testet), commit + OTA-pakke 2.8.0.
2. B bagefter, commit + OTA-pakke 2.9.0.
- **Datamodel:** `passive` er nyt felt; gamle opsætninger mangler det → standard `false`, ingen migration.
- **Sikkerhed/PLC-skrivninger:** `operate` skal afvise passive symboler i backend (ikke kun i UI) — reviewer-agenten kontrollerer A før commit.
- **Visuel verifikation:** begge dele ses i browseren mod testserveren før de meldes færdige.

---

# Plan C: live preview ved animationerne i symbol-guiden (2026-10-30)

**Mål:** i guidens trin 4 står et lille preview af symbolet ved siden af animationerne, som viser, hvordan symbolet ser ud, når animationerne kører — og opdaterer sig med det samme, når en indstilling ændres.

**Beslutning:** ét preview for hele symbolet (alle animationer samtidig, som på Overview) frem for ét pr. animation — det viser samspillet (flere animationer på samme del, aktiv/passiv, prioritet). Alternativ: ét lille billede pr. animation (12 klon af symbolet, uoverskueligt).

**Løsning (kun frontend, ingen backend- eller datamodel-ændring):**
- Ny komponent `AnimPreview.svelte` i trin 4 (sticky i højre kolonne på brede skærme, over animationerne på smalle). Symbolets SVG hentes fra tegningen (guiden henter den allerede til farvehjælpen), klones til en lille indlejret `<svg>` med `viewBox` efter symbolets kasse.
- Genbruger Symboltestens motor (`symbolSim.ts`: `SimTag`, `SimAnim`, `syncSim`, `bindingOf`) og den rigtige animationsmotor (`applyBinding`) — så preview'et ser ud som på Overview.
- Ny ren funktion `simFromConfig(cfg, symbol)` (testet): laver SimAnim/SimTag ud fra guidens opsætning. Kilden afgør betjeningen i preview'et:
  - *til/fra-tag, logikblok, alarm, "altid til"* → to knapper **Fra / Til**
  - *tal-tag* → skyder fra min til max (område efter animationernes Min/Max)
  - *symbolets position* eller *pr. værdi* → en knap pr. position (positionens navn)
  - samme kilde bruges af flere animationer → én kontrol (som i Symboltest)
- Knapper: **Afspil** (løber gennem værdierne), **Nulstil**, og *Kvalitet* (God / Kommunikationsfejl) vises ikke i første version.
- "Gælder i positionerne", aktiv/passiv og "pr. værdi" oversættes som backend gør (`params.pos`, `only`, `when`, `pos_values`) — samme regler som `config_bindings`.
- Preview'et ændrer intet på serveren og gemmer intet.

**Berørte filer (≈5):** `frontend/src/lib/AnimPreview.svelte` (ny), `frontend/src/lib/simFromConfig.ts` (ny, ren logik) + test, `SymbolGuide.svelte` (monterer panelet; tegnings-SVG gemmes), `manual/06` (+ skærmbillede), FEATURES/CHANGELOG/RELEASE_NOTES.
**Version:** MINOR → 2.10.0.

**Risici:** (1) symbolets SVG skal klones uden id-kollisioner med tegningen (klonen sættes i et isoleret `<svg>`; id'er bevares, da dele findes via id); (2) segment-display og løbelys kræver at animationsmotoren kører i et frakoblet DOM — Symboltest gør det allerede; (3) ydeevne: preview'et opdateres med 100 ms debounce ved ændringer.
**Visuel verifikation:** installeres på testserveren og ses i guiden (trin 4) for omskifter, ventil, pumpe og segment-display.
