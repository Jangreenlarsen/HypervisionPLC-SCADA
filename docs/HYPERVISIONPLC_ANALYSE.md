# Analyse af HypervisionPLC — set fra SCADA-projektet

Dato: 2026-10-07 · Analyseret version: **firmware v7.9.68.122** (build 2868, `C:\Projekter\HypervisionPLC`, 572 commits)
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
| Input registers | `GET /api/registers/ir?start=&count=` (≤ 200) | **0–319** i firmwaren (`INPUT_REGS_SIZE 320`, BUG-482). Manualen siger stadig 0–255. IR 220–251 = ST EXPORT-variabler, IR 252–293 = ST-statistik |
| Coils | `GET /api/registers/coils?start=&count=` (≤ 256), `POST .../coils/{addr}` | 0–255 |
| Discrete inputs | `GET /api/registers/di?start=&count=` (≤ 256) | 0–255, kun læs |
| ST-variabler | `GET /api/logic/{id}` → `variables[] {index,name,type,value}` | **Navngivne værdier.** Ét kald pr. program (1–4) |
| Globale ST-variabler | `GET /api/logic/globals` | `{globals:[{index,name,type,value}]}` |
| Fysisk I/O | `GET /api/gpio` | DI1–8 = virtuel GPIO 101–108, DO1–8 = 201–208. Skal være mappet til DI/coil for at kunne læses i registerlageret |
| Analog | `GET /api/analog` | Værdier ×100 fixed-point. HR 0–17 er reserveret til analog I/O |
| Tællere/timere | `GET /api/counters`, `GET /api/timers` | Tællere ligger desuden fast i HR 100–174 |
| Eksterne enheder | `GET /api/modbus/external[?watch=...]` | Cache for RTU-slaver og expansion boards med `status`/`age_ms` |
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
| **SSE-klienter** | **3 i praksis** (`SSE_MAX_CLIENTS 3`). Config tillader 1–5, men slot-arrays er 3 store | `sse_events.h:26`, `sse_events.cpp:71,100,980-1035` | Deles med PLC'ens eget dashboard. SCADA bruger 1 og skal tåle `503` |
| SSE watch-list | max 32 adresser pr. type, eller `subscribe=all` (alle 256 af hver) | `sse_events.h:30` | Ved > 32: brug `subscribe=all` |
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
8. **Brug uversioneret `/api/...` overalt** — `/api/v1` mangler ~20 endpoint-grupper inkl. `/api/login` og giver 404 uden fallback (PLC BUG-485).
9. **Ingen ændringer i PLC-firmwaren er nødvendige** til fase 1–6. Skal der senere bruges ét ekstra PLC-endpoint, er den bedste kandidat et samlet `GET /api/scada/snapshot` (flere områder i ét kald). Flash er dog på ~93 %, så det skal holdes lille.

## 6. Fund i PLC-projektet

Registreret i PLC'ens `BUGS_INDEX.md` 2026-10-07 (commit `16c98ca`). Ikke rettet.

| PLC-ID | Fund | Alvor |
|---|---|---|
| BUG-483 | `sse_max_clients` kan sættes til 4–5, men `SSE_MAX_CLIENTS` er kompileret til 3. En 4. klient passerer grænsetjekket (`sse_events.cpp:980`) og får sendt `200 OK` + SSE-headers, før `sse_registry_add()` fejler og skriver en rå `503`-statuslinje ind i strømmen (`:1029-1035`). Klienten får altså et ødelagt svar i stedet for en ren 503 | Lav |
| BUG-484 | Manualen (§6.3 og §B.7) siger IR 0–255, men firmwaren har IR 0–319 (BUG-482) | Lav (dokumentation) |
| BUG-485 | `/api/v1` mangler ~20 endpoint-grupper (login, logout, session/renew, alarms, analog, trend, syslog, ntp, rbac, acl, expansion, ota, schema …) og `v1_dispatch()` svarer 404 uden fallback. Manualen anbefaler ellers v1 og nævner kun alarmer som undtagelse | Middel |
| BUG-369d (eksisterende) | HTTPS-heap ved bursts står stadig som *under undersøgelse*. Det er relevant, hvis PLC'erne skal køre HTTPS med SCADA tilsluttet | Middel for drift |
