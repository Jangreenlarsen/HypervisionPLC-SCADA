# Integrationsmodel: SCADA ↔ andre systemer (Node-RED, Home Assistant, tredjepart) — designforslag 2026-11-03

**Status:** besluttet af Jan 2026-11-03 — **C** (kerne-API + adaptere) · **kun læs først**, skriv som valgfrit trin 3 · **`aiomqtt` må tilføjes ved trin 4** · **afgrænsning pr. nøgle** (valgte tags/præfiks, intet nyt flag pr. tag). Trin 1 (3.20) er i gang.

## 1. Hvad skal det løse?

Andre systemer skal kunne **læse** anlæggets værdier og alarmer, evt. **styre** udvalgte setpunkter og **abonnere** på ændringer — uden at få adgang til noget, de ikke skal. Typiske brugere:

| System | Naturlig måde at hente/styre på |
|---|---|
| **Node-RED** | MQTT-noder, `http request`, WebSocket/SSE, webhook-modtager |
| **Home Assistant** | **MQTT Discovery** (mest udbredt; entiteter oprettes af sig selv), ellers REST-sensorer/-kommandoer eller en egen komponent |
| **Grafana / historik** | Prometheus (`/metrics` findes) og en historik-API |
| **Tredjepart (BMS, Excel/Power BI, scripts)** | Almindelig REST med en API-nøgle, evt. webhook |

## 2. Hvad findes allerede, og hvad mangler?

**Findes:** REST (`/api/tags`, `/api/live`, `/api/trends/data`, `/api/alarms`, skrivning via `/api/tags/{navn}/write`), WebSocket `/ws/live`, webhook ud (alarmer), Prometheus `/metrics`.

**Mangler (det er hele problemet):**
1. **Godkendelse for maskiner.** Al adgang er en login-*session* (cookie) for et menneske. Der er ingen API-nøgler, ingen service-konti og intet, der kan begrænses til udvalgte tags. En integration ville i dag skulle logge ind som en person.
2. **Tag-baseret afgrænsning.** Adgang i dag er pr. *tegning* (viewer/operatør) — ikke "denne nøgle må kun læse disse 12 tags".
3. **Stabil, versioneret og dokumenteret grænseflade** (OpenAPI), der ikke ændrer sig, når frontenden gør.
4. **Push uden WebSocket-cookie** (SSE/MQTT) og **opdagelse** (hvilke punkter findes, enheder, skrivbare).

## 3. Forslag: ét fælles *punkt-register* + en kerne-API + adaptere

Kernen er **ét sted**, der beskriver "hvad kan udefra ses og styres": et *punkt* (point) = et tag med navn, beskrivelse, enhed, type (tal/til-fra), område, skrivbar, kvalitet og tidsstempel. **Alle** adaptere (REST, SSE, MQTT, webhook) bygges af samme register, så sikkerhed og betydning er ens overalt.

```
Node-RED / HA / tredjepart
   │  Bearer-nøgle                MQTT-mægler (Mosquitto, HA)
   ▼                                   ▲
┌─────────────── Integrations-lag (nyt) ───────────────┐
│ nøgler (hashed) · tag-afgrænsning · rate-limit · audit │
│ punkt-register  → REST /api/v1/integration/*  (kerne)  │
│                 → SSE-strøm                            │
│                 → MQTT-adapter + HA-discovery (valgfri)│
│                 → webhook (findes) · /metrics (findes) │
└──────────────┬──────────────────────────────────────────┘
               ▼  (uændret) live-cache · betjeningstjeneste · trend-DB · alarmmotor
```

### 3.1 Kerne-API `/api/v1/integration/` (stabil og versioneret)
| Endpoint | Formål |
|---|---|
| `GET /points` | punkter nøglen må se: navn, beskrivelse, enhed, type, min/max, decimaler, **skrivbar** (ja/nej for netop denne nøgle) — *aldrig* PLC-adresser |
| `GET /values?tags=` | øjebliksbillede `{navn: {v, q, ts}}` |
| `GET /stream` (SSE) | først et øjebliksbillede, derefter ændringer og alarmhændelser; genoptagelse med `Last-Event-ID`; hjerteslag; kun nøglens punkter |
| `GET /history` | historik (genbruger trend-nedsamplingen) |
| `GET /alarms`, `POST /alarms/ack` | alarmer inden for nøglens afgrænsning |
| `POST /points/{navn}/write` | **valgfri** styring, se 3.3 |
| `GET /openapi.json` | maskinlæsbar beskrivelse (kun denne del) |

### 3.2 API-nøgler (maskin-godkendelse)
- `Authorization: Bearer hv_<256-bit tilfældigt>`; gemmes kun som **SHA-256-kontrolsum** (som `/metrics`-tokenet); vises **én gang** ved oprettelse; kan **tilbagekaldes**; valgfri **udløbsdato**; valgfri **IP-liste**.
- **Afgrænsning pr. nøgle:** *hvilke punkter* (alle udpegede / valgte tags / præfiks), *læs* eller *læs+skriv*, og — kun hvis skriv — *hvilke tags der må skrives*.
- En nøgle er **en egen slags bruger**: den kan aldrig bruge admin-/konfigurations-API'et, og aldrig noget uden for `/api/v1/integration/`.
- Administreres på siden **System › Integrationer** (admin). Alt i audit-loggen (oprettet, tilbagekaldt, hver skrivning med nøglens navn).
- Hastighedsgrænse pr. nøgle (fx 20 læsninger/s, 2 skrivninger/s), samtidige strømme begrænset.

### 3.3 Styring udefra (skrivning) — bevidst snævert
Skrivning er **fra** som standard. For at en integration kan skrive til et tag skal **alle** være sande: nøglen har *skriv*, tagget står på nøglens skriveliste, tagget er `skrivbart`, og værdien er inden for min/max. Selve skrivningen går gennem **samme betjeningstjeneste som operatørerne** (tilbagelæsning, advarsel hvis PLC'en overskriver, audit, PLC'ens fejlbesked) — ingen ny skrivevej.

### 3.4 Adaptere
- **MQTT + Home Assistant Discovery** (valgfri, fase 4): udgiver punkter som `hvscada/<anlæg>/<punkt>` (JSON `{v,q,ts}`, bevaret), `…/availability` (LWT) og alarmer; sender HA's *discovery*-beskeder (`homeassistant/<sensor|binary_sensor|switch|number>/…/config`), så entiteter dukker op af sig selv. Styring via `…/set` går gennem 3.3. Kræver en **MQTT-mægler** (Mosquitto, evt. Home Assistants egen) og biblioteket **`aiomqtt`** (BSD-3; bygger på `paho-mqtt`, dual EPL-2.0/EDL-1.0).
- **Webhook ud** (findes) til hændelser; **Prometheus** (findes) til systemtal. Ingen ændring.
- **Node-RED** behøver intet særligt: HTTP/SSE med en nøgle, eller MQTT.

### 3.5 Udgivelsesregler (så strømmen ikke oversvømmer)
Pr. punkt: send ved ændring med **dødbånd**, **mindste interval** og **hjerteslag** (gentag værdien hvert N. minut, så modtageren kan se, at den er i live). Kvalitet (`good`/`bad`/`stale`) følger altid med; en PLC der er nede, giver kvalitet `bad`, ikke en gammel værdi som ny.

## 4. Alternativer

| | A. Kun MQTT | B. Kun REST/SSE + nøgler | **C. Kerne (B) + adaptere (MQTT senere)** |
|---|---|---|---|
| Home Assistant | ✔ discovery, mest naturlig | ✘ REST-sensorer (polling) eller egen komponent | ✔ (via MQTT-adapter) |
| Node-RED | ✔ | ✔ | ✔ |
| Tredjepart/scripts (REST) | ✘ | ✔ | ✔ |
| Ny afhængighed | `aiomqtt` + mægler | **ingen** | ingen i kernen; `aiomqtt` kun til MQTT-adapteren |
| Sikkerhed/audit | mægler-ACL, svært at samle | **fuld kontrol**, samme audit som i dag | **fuld kontrol**; MQTT-styring går gennem samme skrivevej |
| Historik/forespørgsler | ✘ | ✔ | ✔ |
| Arbejde | mellem | mellem | størst samlet, men leveres i fire små trin |

**Anbefaling: C.** Kernen (nøgler + REST + SSE) er nyttig for *alle* og kræver ingen nye pakker; MQTT/Home Assistant lægges oven på, når du vil have det. Dermed bliver intet opfundet to gange, og sikkerheden ligger ét sted.

## 5. Leveringsplan (hver version: tests, gennemgang af `reviewer`, manual)
1. **3.20 — Nøgler og læse-API:** nøgle-godkendelse (egen principal), side *System › Integrationer*, `/points`, `/values`, `/history`, `/alarms`, OpenAPI, hastighedsgrænse, audit, `/metrics`-tællere, eksempler til Node-RED og Home Assistant (REST) i manualen.
2. **3.21 — SSE-strøm** med øjebliksbillede, genoptagelse og hjerteslag.
3. **3.22 — Styring (valgfri):** skriveliste pr. nøgle, gennem betjeningstjenesten.
4. **3.23 — MQTT-adapter + Home Assistant Discovery** (kræver din accept af `aiomqtt`).

## 6. Risici og afvejninger
- **Eksponering:** hvert punkt, en nøgle må se, er en data-lækage, hvis nøglen stjæles → afgrænsning pr. nøgle, udløb, IP-liste, tilbagekald, HTTPS (nginx) og aldrig nøgler i URL'en.
- **Skrivning** er den farligste del → fra som standard, tre lås (nøgle, skriveliste, `skrivbar`), samme min/max og audit som operatører.
- **Belastning på Pi + PLC:** integrationer læser kun fra SCADA's cache (aldrig direkte fra PLC'en), så de øger ikke PLC'ens kald/s.
- **Stabilitet:** `/api/v1/integration/` versioneres; ændringer i frontend-API'et rører den ikke.

## 7. Beslutninger (Jan)
1. **Retning:** C (anbefalet) / A / B.
2. **Styring udefra:** med fra start (kun læs først, skriv i trin 3) eller helt uden?
3. **MQTT-adapter:** må `aiomqtt` (BSD-3) tilføjes, når vi når trin 4?
4. **Afgrænsning:** pr. nøgle (valgte tags/præfiks) — eller også et flag pr. tag ("kan ses af integrationer")?

## Kilder
- Home Assistant, [MQTT Discovery](https://git.jeena.net/jeena/home-assistant.github.io/raw/commit/12bd06e7fa8798ca5857f2757b72b9c8a7102236/docs/mqtt/discovery/index.html) (emneformat `homeassistant/<komponent>/<id>/config`, standardpræfiks `homeassistant`; søgningen gav kun ældre kopier af dokumentationen, så detaljer om tilgængelighed og *retain* skal kontrolleres mod den nuværende dokumentation ved bygning).
- [aiomqtt på PyPI](https://pypi.org/project/aiomqtt) (BSD-3-Clause; eneste afhængighed er `paho-mqtt`, som er dual-licenseret, bl.a. Eclipse Distribution License 1.0).
