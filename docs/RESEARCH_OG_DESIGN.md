# Research og design — HypervisionPLC SCADA

Dato: 2026-10-07 · Status: godkendt retning (stack, live-data, editor-omfang og multi-PLC valgt af Jan)

---

## 1. Hvad gør tilsvarende systemer?

| System | Hvad vi lærer af det |
|---|---|
| **FUXA** (open source, Node.js + Angular) | Web-baseret SCADA/HMI hvor visninger er SVG og tegnes/bindes i en browser-editor. Node-runtime ejer PLC-forbindelserne; browsere får kun værdier fra serveren. Kører på Raspberry Pi. → Samme grundmodel som vi vælger: **server ejer PLC-kommunikation, browser er tynd klient.** |
| **JSON-SCADA / SCADAvis.io** | Tegninger laves i (en modificeret) Inkscape; animationer gemmes som metadata på SVG-elementerne og evalueres i browseren pr. opdatering. Animationstyper: farve/fyld, opacitet, rotation, flyt ("slider"), bar-niveau, tekst med format, tooltips, klik-scripts. → Vores **animationskatalog** er inspireret herfra. |
| **Rapid SCADA på Raspberry Pi** | Pi'en som opsamlings-node + web-klient; webapp er stateless og læser kun fra serverens REST-interface, så flere klienter (lokal HDMI-skærm i Chromium kiosk + LAN-brugere) ikke påvirker opsamlingen. → **Én poller, mange visere.** |
| **ISA-101 "High Performance HMI"** | Neutral grå baggrund, farve kun til afvigelser, alarmfarver reserveret til alarmer og ikke brugt andre steder. → Standard-tema i viseren, og editoren foreslår ISA-101-farvepalet. |
| **SVG-sikkerhed (DOMPurify / svg-sanitize)** | SVG kan indeholde `<script>`, `on*`-handlers, `<foreignObject>`, eksterne referencer og XXE. Upload skal saneres **på serveren** (og gerne også i klienten). |

Kilder: [FUXA](https://github.com/frangoteam/FUXA) · [JSON-SCADA SVG editor](https://github.com/riclolsen/json-scada/blob/master/src/svg-display-editor/README.md) · [Rapid SCADA på Raspberry Pi](https://industrialmonitordirect.com/blogs/knowledgebase/rapid-scada-on-raspberry-pi-modbus-tcp-daq-deployment-guide) · [Going Gray (ISA-101)](https://control.com/technical-articles/going-gray/) · [Creating a high-performance HMI](https://www.processonline.com.au/content/process-control-systems/sponsored/best-design-practices-creating-a-high-performance-hmi-1374659233) · [DOMPurify](https://www.greptile.com/grepository/dompurify) · [SVG-Edit (MIT)](https://github.com/SVG-Edit/svgedit)

---

## 2. Faste rammer fra HypervisionPLC (fra PLC'ens egen manual, kap. 7 + appendiks B)

- **Al kommunikation er REST/JSON over HTTP(S)**. Brug det **uversionerede** `/api/...` — `/api/v1` mangler bl.a. login, alarmer, analog og trend og giver 404 (PLC BUG-485).
- **Auth**: `POST /api/login` med Basic → Bearer-token, 30 min glidende timeout. Ved 401: log ind igen.
- **Rate-limit**: token bucket pr. klient-IP, **30 burst / 10 req/s**, max 8 IP'er trackes → `429`. *Derfor må kun Pi'en tale med PLC'en* — ellers tæller hver browser med.
- **Bulk-læsning**: `GET /api/registers/{hr|ir}?start=&count=` (max 200), `coils`/`di` (max 256). HR/coils/DI 0–255, IR 0–319 (firmware, manualen siger 0–255).
- **Forbindelser**: HTTP max 10 sockets, **HTTPS kun 2** og heap-følsom → SCADA bruger 1 vedvarende keep-alive-forbindelse pr. PLC og kalder serielt. Session-tokens: 8 pladser delt med alle brugere → genbrug token, re-login kun ved 401. Detaljer: [HYPERVISIONPLC_ANALYSE.md](HYPERVISIONPLC_ANALYSE.md).
- **Skrivning**: `POST /api/registers/hr/{addr}` `{"value","type":"uint|int|dint|dword|real"}` (dint/dword/real = 2 registre, high word først), `POST /api/registers/coils/{addr}`, bulk-varianter. 409 når PLC'en er i safe mode — fejlteksten skal vises til operatøren.
- **Andre kilder**: ST-variabler `GET /api/logic/{id}`, globale `GET /api/logic/globals`, tællere/timere, eksterne Modbus-værdier `GET /api/modbus/external`, alarmer `GET /api/alarms`, trend `GET /api/trend/data`.
- **SSE** (`GET :<sse_port>/api/events?subscribe=registers&hr=..&coils=..&token=`): push ved ændring. Begrænsninger: **max 32 adresser pr. type** i watch-list (eller `subscribe=all` = alle 256 af hver), **max 3 SSE-klienter** pr. PLC i praksis (delt med PLC'ens eget dashboard), altid ukrypteret selv med HTTPS, token fra `GET /api/events/status` (`sse_token`, kortlivet).
- Fejl-format: `{"error":"...","status":N}`.

---

## 3. Valgt arkitektur

```
 Browser (Overview / Editor / Admin)          Chromium kiosk på Pi'ens egen skærm
        │  HTTPS REST + WebSocket (/ws/live)         │
        └──────────────────┬────────────────────────┘
                           ▼
 ┌──────────────────── Raspberry Pi 4 · én systemd-service (uvicorn) ───────────────────┐
 │  API-lag (FastAPI routers)  — auth, tegninger, bindinger, tags, PLC'er, skriv, ws   │
 │  Service-lag                — tegning/sanering/versioner, tag-model, live-cache,     │
 │                               abonnementer, skrive-service + audit, alarmer          │
 │  PLC-klient-lag (hvplc)     — ÉNESTE sted der taler HTTP med PLC'er:                 │
 │                               login/token, poll-planlægger, SSE-lytter, rate-budget  │
 │  Lager                      — SQLite (WAL) + filer (SVG-versioner) + secrets-fil     │
 └──────────────────────────────────────────┬──────────────────────────────────────────┘
                                            │ REST (+ SSE) — kun Pi'ens IP
                         ┌──────────────────┼──────────────────┐
                    HypervisionPLC #1   HypervisionPLC #2   ...
```

### 3.1 Live-data: "Pi poller + PLC SSE"

1. **Abonnements-sæt**: Serveren ved hvilke tags der aktuelt vises (de tegninger åbne browsere abonnerer på via WebSocket) + tags med alarm-grænser (skal altid overvåges).
2. **Poll-planlægger** (pr. PLC): grupperer adresser pr. type i sammenhængende intervaller og fletter huller (≤ 200 HR/IR, ≤ 256 coil/DI pr. kald). Typisk 1–4 kald pr. cyklus.
3. **SSE-lytter** (pr. PLC, højst én forbindelse, valgfri pr. PLC): watch-list med de mest brugte adresser (max 32 pr. type, ellers `subscribe=all`). Ændringer pushes straks videre. `503` (fuld) eller SSE slået fra → ren polling. Anbefal ACL `service=sse` begrænset til Pi'ens IP.
4. **Adaptiv poll-rate**: SSE sund → resync-poll hvert 2 s (fanger værdier SSE ikke dækker: ST-variabler, `real`/`dint`-par, eksterne). SSE nede → poll hvert 500 ms. Hård grænse: **≤ 5 req/s pr. PLC** (halvdelen af PLC'ens budget, så PLC'ens eget dashboard stadig virker). 429 → eksponentiel backoff.
5. **Live-cache** pr. tag: værdi, kvalitet (`good` / `stale` / `bad` / `comm_error`), tidsstempel. Browsere får kun **ændringer** over WebSocket (delta-frames), plus fuldt snapshot ved abonnement.
6. Kommunikationsfejl gør værdier `stale` → viseren viser dem tydeligt (skraveret/grå + ikon), aldrig en "frossen" værdi der ligner en gyldig.

### 3.2 Tag-model (adskiller tegning fra adresse)

Tegninger binder til **tag-navne**, ikke rå adresser — flyttes en værdi i PLC'en, rettes kun tagget.

| Felt | Eksempel |
|---|---|
| navn | `Pumpe1_Drift` |
| kilde | `plc1:coil:5` · `plc1:hr:100:real` · `plc1:ir:7` · `plc1:di:3` · `plc1:logic:1:Niveau` · `plc1:global:Mode` · `plc1:counter:2` |
| datatype | bool, uint, int, dint, dword, real |
| skalering | `raw * 0.1 + 0` · enhed `°C` · decimaler |
| skrivbar | ja/nej + min/max + kræv bekræftelse |
| alarm (senere) | HH/H/L/LL, deadband, prioritet |

Import af tags fra PLC'ens `GET /api/bindings` og `GET /api/logic/{id}` (variabelnavne) gør opsætning hurtig.

### 3.3 SVG-tegning og bindinger

- **Upload**: SVG fra Inkscape/Visio/draw.io/AutoCAD-eksport → **saneres på serveren** (defusedxml, hvidliste af elementer/attributter, fjern `script`, `on*`, `foreignObject`, `javascript:`/eksterne `href`) → gemmes som ny version.
- **Bindinger gemmes separat** (JSON i DB, nøgle = elementets `id`) — ikke inde i SVG'en. Begrundelse: SVG-Edit's egen sanering fjerner ukendte attributter/navnerum, og en tegning kan gen-uploades fra Inkscape uden at miste bindinger, så længe element-id'erne bevares. Editoren advarer om bindinger hvis element er forsvundet ("forældreløse bindinger").
- **Auto-forslag**: elementer hvis `id` eller `inkscape:label` matcher et tag-navn (fx `Pumpe1_Drift`) foreslås bundet automatisk.
- **Animationskatalog** (pr. binding, flere pr. element tilladt):

| Type | Virkning |
|---|---|
| `text` | Erstat tekstindhold med formateret værdi (`%.1f °C`, bool-tekster "Kører/Stop") |
| `fill` / `stroke` | Farve ud fra tilstand eller tærskler |
| `visible` | Vis/skjul |
| `blink` | Blink ved alarm/tilstand |
| `level` | Fyld-niveau (tank/bar) 0–100 % via clip-path |
| `rotate` | Rotation (ventilator, viser) om centrum |
| `move` | Flyt mellem to positioner (glider/ventil) |
| `opacity` | Gennemsigtighed |
| `flow` | Løbelys: to farver løber langs en streg/et rør; tagget styrer start/stop og retning (til/fra, fortegn eller kode 0/1/2) — v0.29.0 |
| `click:write` | Setpunkt-dialog (min/max, bekræft) → skriv tag |
| `click:toggle` / `click:pulse` | Skift coil / puls (momentary) |
| `click:goto` | Navigér til anden tegning (drill-down) |

- **Fuld tegne-editor**: [SVG-Edit 7](https://github.com/SVG-Edit/svgedit) (MIT, npm `@svgedit/svgcanvas`) indlejres i editor-siden. Vi bygger vores egne paneler rundt om canvas'et: tag-browser, binding-panel og symbol-bibliotek (pumpe, ventil, tank, motor, rør, værdifelt — ISA-101-stil). Live-preview i editoren med rigtige værdier.
- **Versionering**: hver gemning = ny version; "udgiv" gør en version aktiv på Overview. Rollback mulig.

### 3.4 Brugere, roller og sikkerhed

| Rolle | Må |
|---|---|
| `viewer` | Se Overview |
| `operator` | + skrive til tags markeret skrivbare, kvittere alarmer |
| `engineer` | + uploade/redigere tegninger, bindinger, tags |
| `admin` | + brugere, PLC-forbindelser |

- Sidste admin kan ikke slettes/nedgraderes (håndhæves i backend).
- PLC-adgangskoder ligger i git-ignoreret secrets-fil på Pi'en; API returnerer kun `has_password`. Browseren ser aldrig PLC-credentials.
- Default admin-adgangskode → advarsel og tvunget skift ved første login.
- Alle skrivninger til PLC logges (bruger, tag, gammel→ny værdi, PLC-svar).

### 3.5 Raspberry Pi 4 drift

- Raspberry Pi OS Lite 64-bit (Bookworm), Python 3.11, én uvicorn-proces som systemd-service med `Restart=always`, kører som egen ikke-privilegeret bruger.
- Frontend bygges på udviklingsmaskinen (`npm run build`) → statiske filer serveres af FastAPI. Ingen Node på Pi'en.
- Valgfri lokal skærm: Chromium `--kiosk` på labwc/Wayland. Hold animationer enkle (Chromium kan bruge mærkbar CPU på Pi 4).
- SD-kort-slid: SQLite i WAL-mode, ingen pr.-værdi-logging til disk; historik i RAM-ringbuffer. Anbefaling: USB-SSD til produktion.
- Udvikling og test på Windows mod en **mock-PLC** (lille FastAPI-app der efterligner det relevante subset af HypervisionPLC-API'et inkl. rate-limit, 401 og SSE).

---

## 4. Faseplan

| Fase | Indhold | Leverance |
|---|---|---|
| 0 | Projektopsætning, research, arkitektur | Dette dokument |
| 1 | Backend-skelet, mock-PLC, PLC-klient (login, bulk-poll, SSE, rate-budget), tag-model | Live-cache med værdier fra mock-PLC, testet |
| 2 | SVG-upload + sanering + Overview-viser med live-bindinger over WebSocket | Første tegning med live værdier |
| 3 | Binding-editor (klik element → bind tag + animation), auto-forslag | Bindinger uden at røre SVG |
| 4 | SVG-Edit-integration, symbol-bibliotek, versioner/udgiv | Fuld tegne-editor |
| 5 | Skrivning til PLC (setpunkter, toggle), brugere/roller, audit-log | Operatør-betjening |
| 6 | Alarmer, trends, Pi-deployment (systemd, kiosk), backup/restore af projekt | Klar til drift |

## 5. Åbne punkter

- Skal PLC'erne køre HTTPS (selvsignerede certifikater → Pi'en skal kunne pinne/stole på dem)? NB: alle PLC'er på samme build deler certifikat, og SSE er altid ukrypteret.
- Dedikeret RBAC-bruger `scada` (rolle `api`, `read/write`) oprettes på hver PLC.
- Hvor mange SSE-klient-pladser må SCADA bruge pr. PLC (default 3 i alt)?
- Skal Overview være tilgængelig uden login (fx vægskærm), eller altid kræve login?
