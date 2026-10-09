# Analyse af HypervisionPLC — set fra SCADA-projektet

Dato: 2026-10-07 · Analyseret version: **firmware v7.9.68.122** (build 2868, `C:\Projekter\HypervisionPLC`, 572 commits)
**Opdateret 2026-10-09 til v7.9.68.125** — se [§7](#7-nyt-i-plc-v7968123125-2026-10-09) for de nye muligheder (eksterne registre via REST) og de rettede fund.
Kilder: PLC'ens manual (`docs/manual/`, især kap. 1, 2, 6, 7, 10 og appendiks B), `SECURITY_INDEX.md`, `BUGS_INDEX.md` og kildekoden (`src/api_handlers.cpp`, `src/http_server.cpp`, `src/https_wrapper.c`, `src/rbac.cpp`, `src/sse_events.cpp`, `include/constants.h`). Alle tal i afsnit 3 er læst direkte i kildekoden.

---

## 1. Hvad PLC'en er

- **Hardware**: hovedmålet er **ES32D26** (ESP32-WROVER, 4 MB PSRAM) med 8 DI (74HC165), 8 relæer (74HC595), 4 spændings- og 4 strøm-AI, 2 AO og RS-485. Der findes også et ESP32-WROOM-32-build (prototype).
- **Netværk**: WiFi og/eller Ethernet (W5500), DHCP/statisk IP, NTP.
- **Kerne**: ét fælles register-/coil-lager, som Modbus RTU slave, Modbus master (async kø + cache), op til 4 ST Logic-programmer, 4 tællere, 4 timere, GPIO og REST API alle læser og skriver.
- **Udvidelse**: expansion boards over Modbus TCP (`MBX_*`) og eksterne RTU-slaver via masteren. Begge kan læses som cache via REST (`/api/modbus/external`).
- **Ikke**: SIL/PL-certificeret og ikke redundant. **SCADA'en må derfor aldrig være en del af en sikkerhedsfunktion.**
- PLC'ens backlog har **FEAT-100 "Mini-SCADA view"** (åben). Det dækker dette projekt i stedet. Firmwaren bruger desuden ~93 % af flash, så der er ikke plads til at lægge SCADA ind i PLC'en.

## 2. Datamodel SCADA'en kan binde til

| Kilde | REST | Bemærkning |
|---|---|---|
| Holding registers | `GET /api/registers/hr?start=&count=` (≤ 200), `POST /api/registers/hr/{addr}` | **0–255**. Skriv med `type` = uint/int/dint/dword/real |
| Input registers | `GET /api/registers/ir?start=&count=` (≤ 200) | **0–319** (`INPUT_REGS_SIZE 320`, BUG-482; manualen rettet i v7.9.68.124). IR 220–251 = ST EXPORT-variabler, IR 252–293 = ST-statistik |
| Coils | `GET /api/registers/coils?start=&count=` (≤ 256), `POST .../coils/{addr}` | 0–255 |
| Discrete inputs | `GET /api/registers/di?start=&count=` (≤ 256) | 0–255, kun læs |
| ST-variabler | `GET /api/logic/{id}` → `variables[] {index,name,type,value}` | **Navngivne værdier.** Ét kald pr. program (1–4) |
| Globale ST-variabler | `GET /api/logic/globals` | `{globals:[{index,name,type,value}]}` |
| Fysisk I/O | `GET /api/gpio` | DI1–8 = virtuel GPIO 101–108, DO1–8 = 201–208. Skal være mappet til DI/coil for at kunne læses i registerlageret |
| Analog | `GET /api/analog` | Værdier ×100 fixed-point. HR 0–17 er reserveret til analog I/O |
| Tællere/timere | `GET /api/counters`, `GET /api/timers` | Tællere ligger desuden fast i HR 100–174 |
| **Eksterne enheder — RS485-slaver** | `GET/POST /api/ext/rtu/{slave}/{hr\|ir\|coils\|di}/{addr}` | **Nyt i v7.9.68.123.** Slaver på PLC'ens egen RS485-bus (PLC'en er Modbus Master). Samme form som `/api/registers/...`, se §7 |
| **Eksterne enheder — expansion boards** | `GET/POST /api/ext/mbx/{board}/{kanal}/{slave}/{type}/{addr}` | **Nyt i v7.9.68.123.** Slaver bag et expansion board (kanal A–H). Se §7 |
| Eksterne enheder (snapshot) | `GET /api/modbus/external[?watch=...]` | Cache-dump for RTU-slaver og expansion boards med `status`/`age_ms`. Erstattes til tags af `/api/ext/...` |
| Alarmer | `GET /api/alarms`, `POST /api/alarms/ack` | Systemalarmer (heap, CRC, timeouts, auth), ikke procesalarmer |
| Register-ejerskab | `GET /api/bindings` → `usage` | Hvem skriver hvilke HR/coils (0–159). Bruges til tag-import og til at advare om skrivning til register, som ST overskriver |

**32-bit værdier**: dint/dword/real ligger i 2 registre, **high word først** (`api_handlers.cpp:1579-1615`). Bulk-GET returnerer rå 16-bit ord, så SCADA'en skal selv samle dem og skal læse begge ord i samme kald, så de to halvdele ikke kommer fra hver sin cyklus.

**Konflikt-risiko**: ST Logic, Modbus-slave og REST deler lageret. En værdi SCADA skriver til et register, som et ST-program har en output-binding på, bliver overskrevet i næste ST-cyklus. Derfor skal skriv altid bekræftes ved at læse værdien tilbage, og tag-editoren skal advare via `/api/bindings` `usage`.

## 3. Hårde grænser i PLC'en (verificeret i kildekoden)

| Grænse | Værdi | Kilde | Konsekvens for SCADA |
|---|---|---|---|
| Rate-limit pr. IP | 30 burst, 10 req/s, 8 IP-pladser (ældste genbruges) | `api_handlers.cpp:11554-11556` | Budget ≤ 5 req/s pr. PLC. Ved 429: backoff |
| HTTP-sockets | `max_open_sockets = 10`, LRU-purge | `http_server.cpp:1391` | Brug 1 vedvarende keep-alive-forbindelse, højst 2 |
| **HTTPS-sockets** | **`max_open_sockets = 2`** | `https_wrapper.c:86` | **Præcis 1 vedvarende TLS-forbindelse, ingen parallelle kald** |
| HTTPS-heap | ~40 KB pr. TLS-session; bursts har udtømt heap (BUG-369 → 369d, stadig *under undersøgelse*) | `BUGS_INDEX.md` | Aldrig bursts eller nye TLS-handshakes pr. kald. Forbindelsen genbruges |
| Session-tokens | 8 pladser i alt, 30 min glidende TTL. Er alle optaget, smides den der er tættest på at udløbe | `rbac.cpp:241-243, 264-300` | Genbrug ét token. Re-login kun ved 401. `POST /api/logout` ved nedlukning. Gentagne logins ville smide andre brugeres sessioner ud |
| Token-revokering | En "gated" ACL-ændring ugyldiggør **alle** tokens | `rbac.h` (FEAT-399) | 401 midt i drift er normalt → automatisk re-login |
| **SSE-klienter** | **3** (`SSE_MAX_CLIENTS 3`). Før v7.9.68.125 var det reelle loft **2** efter længere drift (BUG-487), og en klient uden plads fik et ødelagt svar (BUG-483). Nu: config 1–3, alle 3 workers oprettes ved opstart, klient nr. 4 får et rent `503` med JSON | `sse_events.h:26`, `sse_events.cpp` | Deles med PLC'ens eget dashboard. SCADA bruger 1 og skal tåle `503` |
| SSE watch-list | max 32 adresser pr. type, eller `subscribe=all` (HR/coils/DI 0–255, IR 0–255). Eksplicit liste: HR 0–255, IR 0–319 (før v7.9.68.124: HR/IR kun 0–159). `%2C`-kodede kommaer virker fra v7.9.68.124 (BUG-486) | `sse_events.h:30` | Ved > 32: brug `subscribe=all`. Sammenlign stadig `connected.watching` med det ønskede |
| SSE-ændringsdetektion | 100 ms (10 Hz), heartbeat 15 s | `sse_events.h:27-28` | Heartbeat bruges til at se, om forbindelsen lever |
| SSE-token | `GET /api/events/status` → `sse_token`, 5 min TTL, genbrugeligt inden for TTL, 8 pladser | `sse_events.cpp:442-530` | Hent nyt token ved hver genforbindelse |
| **SSE og TLS** | SSE er **altid ukrypteret** (SECURITY_INDEX #13, åben) | manual §10.4 | Bruges HTTPS, går SSE-data stadig i klartekst. Begræns med ACL `service=sse` til Pi'ens IP, eller slå SSE fra og poll |
| Fejlformat | `{"error":"...","status":N}`, 400/401/403/404/409/429/500 | appendiks B §B.1 | Vis `error`-teksten til brugeren |
| Safe mode | `POST /api/gpio/{pin}` → 409 i safe mode | §B.8 | Vis PLC'ens besked, ikke en generisk fejl |

## 4. Auth og bruger på PLC'en

- Standard er `auth_mode = bearer`: login med `POST /api/login` (Basic), derefter `Authorization: Bearer <token>`. Basic-headers på andre endpoints giver 401.
- **Anbefaling**: opret en dedikeret RBAC-bruger på hver PLC, fx `scada`, med rollen `api` og privilegiet `read/write` (eller `read`, hvis SCADA'en kun skal vise). Rollen `api` giver også adgang til SSE. Brug aldrig `admin/modbus123`. PLC'en advarer selv, når standard-adgangskoden bruges.
- PLC'ens offentlige statusside og `/api/metrics` kræver ikke login, men SCADA'en har ikke brug for dem.

## 5. Konsekvenser for SCADA-designet (rettelser til RESEARCH_OG_DESIGN.md)

1. **Forbindelseshåndtering**: én `httpx.AsyncClient` pr. PLC med `max_connections=1` og keep-alive, og en seriel request-kø. Det gælder både HTTP og HTTPS. Ingen parallelle kald mod samme PLC.
2. **Poll-plan pr. cyklus** (typisk): HR (1–2 kald) + IR (1–2) + coils (1) + DI (1) + ST-programmer i brug (0–4) + globals (0–1) ≈ 4–10 kald. Ved resync hvert 2. s giver det 2–5 req/s, og kun de intervaller, der faktisk bruges, bliver hentet. Fallback til 500 ms kræver, at planen begrænses til de mest kritiske områder, så budgettet på 5 req/s holdes.
3. **SSE er en bonus, ikke en forudsætning**: højst 1 SSE-forbindelse pr. PLC. Ved `503` (fuld) eller ukrypteret netværk kører SCADA'en på ren polling. SSE dækker kun registre/coils/DI og tællere/timere, ikke ST-variabler, analog eller eksterne værdier.
4. **Tag-typer**: IR-adresser tillades 0–319. 32-bit typer læses som par i samme kald.
5. **Tidsstempler**: SCADA'en sætter sit eget tidsstempel ved modtagelse. PLC'ens `epoch` er 0, hvis NTP ikke er synkroniseret.
6. **Historik**: PLC'ens trend-recorder (8 punkter, 720 samples, kun i RAM) er for lille til SCADA-trends. SCADA'en gemmer selv historik.
7. **Tag-import**: `/api/logic/{id}` (navngivne ST-variabler), `/api/logic/globals`, `/api/bindings` (`usage`) og `/api/gpio` giver nok til et "importér tags fra PLC"-flow.
8. **Brug uversioneret `/api/...`** — det virker på alle firmwareversioner. Fra v7.9.68.124 spejler `/api/v1/*` hele API'et (BUG-485 rettet), men ældre PLC'er giver 404 på bl.a. `/api/v1/login`.
9. **Ingen ændringer i PLC-firmwaren er nødvendige** til fase 1–6. Eksterne registre (RS485-slaver og expansion boards) kan fra v7.9.68.123 bruges som tags via `/api/ext/...` (§7). Skal der senere bruges ét ekstra PLC-endpoint, er den bedste kandidat et samlet `GET /api/scada/snapshot`. Flash er på 95,8 %, så det skal holdes lille.

## 6. Fund i PLC-projektet

Registreret i PLC'ens `BUGS_INDEX.md` 2026-10-07 (commit `16c98ca`). **BUG-483–487 er rettet og HW-testet i v7.9.68.124/125 (2026-10-09)** — se §7.

| PLC-ID | Fund | Alvor |
|---|---|---|
| BUG-483 | `sse_max_clients` kan sættes til 4–5, men `SSE_MAX_CLIENTS` er kompileret til 3. En 4. klient passerer grænsetjekket (`sse_events.cpp:980`) og får sendt `200 OK` + SSE-headers, før `sse_registry_add()` fejler og skriver en rå `503`-statuslinje ind i strømmen (`:1029-1035`). Klienten får altså et ødelagt svar i stedet for en ren 503 | Lav |
| BUG-484 | Manualen (§6.3 og §B.7) siger IR 0–255, men firmwaren har IR 0–319 (BUG-482) | Lav (dokumentation) |
| BUG-485 | `/api/v1` mangler ~20 endpoint-grupper (login, logout, session/renew, alarms, analog, trend, syslog, ntp, rbac, acl, expansion, ota, schema …) og `v1_dispatch()` svarer 404 uden fallback. Manualen anbefaler ellers v1 og nævner kun alarmer som undtagelse | Middel |
| BUG-369d (eksisterende) | HTTPS-heap ved bursts står stadig som *under undersøgelse*. Det er relevant, hvis PLC'erne skal køre HTTPS med SCADA tilsluttet | Middel for drift |

## 7. Nyt i PLC v7.9.68.123–125 (2026-10-09)

PLC-firmwaren kører v7.9.68.125 på test-PLC'en 10.1.1.30 (PLC-commits `d2b4deb`, `9e60c0b`, `af0c39d`). Alt nedenfor er HW-testet mod den.

### 7.1 Eksterne registre via REST (PLC FEAT-486)

SCADA'en kan nu læse og skrive registre på de enheder, PLC'en taler med, med samme slags URL'er som PLC'ens egne registre. Der er altså tre kilder for et tag:

| Kilde | Læs / skriv | Eksempel |
|---|---|---|
| **Intern** (PLC'ens eget registerlager) | `GET/POST /api/registers/{hr\|ir\|coils\|di}/{addr}` (uændret) | `/api/registers/hr/60` |
| **Extern** (slave på PLC'ens RS485-bus) | `GET/POST /api/ext/rtu/{slave}/{type}/{addr}` | `/api/ext/rtu/90/hr/0` |
| **Expansion board** (slave bag et board) | `GET/POST /api/ext/mbx/{board}/{kanal}/{slave}/{type}/{addr}` | `/api/ext/mbx/1/D/1/coils/0` |

`{type}` = `hr`, `ir`, `coils`, `di`. `{kanal}` = `A`–`H` eller `1`–`8`. Adresse 0–65535. Virker også under `/api/v1/ext/...`.

**Læsning (GET)** — valgfri query: `count` (højst 16 registre pr. kald), `type=uint|int|dint|dword|real` (32-bit = 2 registre, high word først, som de interne), `wait=ms` (≤ 2000: vent på frisk svar fra bussen), `max_age=ms` (standard 1000: hvor gammel en cache-værdi må være, før den hentes igen).

```
GET /api/ext/rtu/90/hr/0?count=2&wait=800                                     (247 ms)
{"src":"rtu","slave":90,"type":"hr","address":0,"format":"uint","value":234,"status":"ok","age_ms":67,
 "count":2,"values":[234,235],"states":["ok","ok"],"ages_ms":[67,3]}

GET /api/ext/mbx/1/D/1/coils/0?count=4&wait=1000                               (238 ms)
{"src":"mbx","board":1,"channel":"D","slave":1,"type":"coils","address":0,"format":"bool","value":false,
 "status":"ok","age_ms":105,"count":4,"values":[false,false,false,false],"states":["ok","ok","ok","ok"],"ages_ms":[105,74,41,9]}
```

`value`/`status`/`age_ms` gælder den første værdi (så `count=1` ligner `/api/registers/...`); `values`/`states`/`ages_ms` kommer med, når `count > 1`. `status` = `ok`, `pending` eller `error`; `value` er `null`, når der ikke er en gyldig værdi.

**Skrivning (POST)** — kun `hr` og `coils`, kræver skriverettighed (RBAC `read/write`), logges i PLC'ens hændelseslog med bruger og IP:

```
POST /api/ext/mbx/1/D/1/coils/0?wait=1500   {"value":true}                     (112 ms)
{"src":"mbx","board":1,"channel":"D","slave":1,"type":"coils","address":0,"registers":1,"result":"ok"}
```

Body: `{"value":…,"type":"uint|int|dint|dword|real"}` (ét register/én coil; 32-bit-typer skrives med FC16) eller `{"values":[…]}` (op til 16, FC16/FC15). `result` = `queued` uden `wait`, ellers slavens resultat `ok`/`error`/`timeout`. Flere-register-skrivninger til et expansion board kan ikke bekræftes og svarer altid `queued`.

**Fejlkoder** (verificeret): 400 forkert sti/type/adresse/`count`/kanal boardet ikke har · 404 board ikke konfigureret · 405 skrivning til `ir`/`di` · 409 PLC'ens Modbus Master er slået fra (gælder `rtu`) · 502 slaven svarede med fejl/timeout (ved `wait`) · 503 PLC'ens Modbus-kø er fuld.

**Sådan virker det inde i PLC'en** — og hvad det betyder for SCADA'en:

1. **Alt går gennem PLC'ens Modbus-kø og -cache** (den samme, ST Logic bruger). PLC'ens webserver taler aldrig selv med bussen. Uden `wait` får man straks den seneste kendte værdi, og kaldet sætter en opfriskning i kø. **Første læsning af en ny adresse giver derfor `"value":null,"status":"pending"`** — en SCADA, der poller fast, har værdien fra 2. kald. Behandl `pending` som "ingen værdi endnu" (stale-kvalitet), ikke som fejl.
2. **`wait` blokerer PLC'ens webserver**, mens den venter (målt 100–250 ms for ét svar). Brug den kun til skrivninger, der skal bekræftes, eller ved første læsning — ikke i hver poll-cyklus. Normal poll: uden `wait`, `max_age` ≈ poll-intervallet.
3. **Cachen er lille og delt med ST Logic**: 32 poster for RS485-masteren, 48 for expansion boards (LRU). Overvåger SCADA'en mange flere eksterne adresser end det, skubber de hinanden og ST's værdier ud, og hver læsning bliver til bustrafik. Hold antallet af eksterne adresser nede.
4. **Saml sammenhængende holding registers** i ét kald med `count` (bliver til ét FC03 på bussen). Coils/DI/IR med `count` bliver til ét bus-kald pr. adresse.
5. **Rate-budget**: hvert `/api/ext`-kald tæller med i de ≤ 5 req/s pr. PLC (§3) — og bussen bag er langsom (9600 baud ≈ 20–50 ms pr. transaktion, plus netværk for expansion boards). Grupper pr. (kilde, slave, type) som bulk-planlæggeren allerede gør for interne områder.
6. **SSE dækker ikke eksterne registre** — de skal polles.
7. **Skrivninger kræver tilbagelæsning** som de interne (§2): læs med `max_age=0` (eller brug `wait` på POST). Bemærk at et ST-program kan skrive til samme slave-adresse.

**Forslag til tag-kilde i SCADA'en** (udvidelse af `plcN:type:addr[:datatype]`):

```
plc1:hr:60:real                 intern (uændret)
plc1:rtu:90:hr:0:uint           ekstern RS485-slave 90, HR 0
plc1:mbx:1:D:1:coils:0          expansion board 1, kanal D, slave 1, coil 0
```

### 7.2 Rettede fund (se §6)

| PLC-ID | Rettet i | Hvad det betyder for SCADA'en |
|---|---|---|
| BUG-483 | v7.9.68.124 | SSE `max-clients` er 1–3; klient uden plads får et rent `503` med `{"error":"Max SSE clients reached"}` |
| BUG-484 | v7.9.68.124 | Manualen angiver IR 0–319 |
| BUG-485 | v7.9.68.124 | `/api/v1/*` spejler hele API'et inkl. `login`, `alarms`, `expansion`, `ntp`, `ext` og PUT. Uversioneret `/api/` virker fortsat |
| BUG-486 | v7.9.68.124 | SSE afkoder `%2C` — httpx' standard-kodning virker nu; watch-liste HR 0–255, IR 0–319 (SCADA v0.7.0.1/v0.8.1-workaround med ukodede kommaer er stadig gyldig) |
| BUG-487 | v7.9.68.125 | Fundet ved test: efter længere drift kunne kun **2** SSE-klienter forbinde — nr. 3 fik `200 OK` og blev lukket uden events. Nu får alle 3 events. **Relevant hvis SCADA'en har set SSE-forbindelser, der lukker straks efter `200 OK`** |

### 7.3 Kendte begrænsninger, der stadig gælder

- Flash er på 95,8 % — nye PLC-endpoints til SCADA'en skal være små.
- Cache-størrelserne i 7.1 punkt 3 er faste i firmwaren.
- Skriverettighed til `/api/ext` er ikke begrænset pr. slave/adresse (PLC SECURITY_INDEX #29): en bruger med `read/write` kan skrive til alt, PLC'en kan nå. Brug en dedikeret `scada`-bruger (§4) og SCADA'ens egne `skrivbar`/min/max-regler pr. tag.
