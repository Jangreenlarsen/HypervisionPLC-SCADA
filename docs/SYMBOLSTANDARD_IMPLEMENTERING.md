# Symbolstandard — implementeringsguide

**Status:** plan, godkendt til implementering af Jan 2026-10-13. Beskriver *hvordan* [SYMBOLSTANDARD.md](SYMBOLSTANDARD.md)
(hvad brugeren ser og hvilke regler der gælder) bygges ind i den eksisterende kode. Reference for opførsel er prototypen
[prototyper/symbolguide.html](prototyper/symbolguide.html) i den version der er committet sammen med dette dokument
(v0.31.0); afsnit 13 viser hvor hver af prototypens funktioner lander.

Ved uenighed gælder: SYMBOLSTANDARD.md for opførsel, denne guide for teknik, CLAUDE.md og ARCHITECTURE.md over begge.

---

## 1. Udgangspunkt (v0.31.0)

| Område | Findes i dag | Mangler for standarden |
| --- | --- | --- |
| Symboler i tegningen | `<g>` med id; dele = børn med id `<symbol>_<del>`; navn i `data-hv-name`, forklaring i `symbol_meta` | Hvilken bibliotekstype et symbol er (`data-hv-type`) og bibliotekets beskrivelse af dele/positioner |
| Konfiguration | `bindings` (ét tag + én animation pr. række) + automatiske bindinger fra `data-hv-auto`/`data-hv-part` | Én samlet konfiguration pr. symbol: positioner, signaler, kontaktplaner, visning, betjening, lås, animationer |
| Animationer (`animate.ts`) | text, fill, stroke, visible, blink, level, rotate, opacity, move, flow (inkl. retnings-tag og T/kryds) | Kilde = symbolets position, "gælder i positionerne", parametre pr. position, blinkfrekvens, kontinuerlig rotation (Roterer), glidning |
| Betjening (`operate.py`) | Ét tag pr. kald: write, toggle, pulse (coil/heltal 1→0) | Positionsskift med flere signaler i rækkefølge, puls med hvileværdi, fejl/låst-tag, accept, PIN |
| Tilstand | Ingen — klik skriver, visningen følger tagget | Fundet position, Lokal/Remote, Venter/Bekræftet/Afvigelse/Ukendt, valideringstid, sidst valgt (af hvem, hvornår) |
| Alarmer (`alarms.py`) | Tag-alarmer og kommunikation; prioritet `high`/`medium` | Afvigelsesalarm pr. symbol med niveau `low`/`medium`/`high` |
| Adgang (`scope.py`) | Tags i tegninger brugeren må se; betjening via klik-bindinger | Betjening pr. symbol; afledte værdier (pseudo-tags) |
| Backup (`backup.py`) | PLC'er, tags, tegninger, bindinger, ugeprogrammer, forklaringer | Symbol-konfigurationer (uden PIN-hashes) |

Live-værdier: alle tags på en aktiv PLC polles (`manager._runtime_tags`) — afledte symbolværdier kan derfor beregnes
på serveren ud fra live-cachen uden ekstra PLC-trafik.

### 1.1 Forudsætninger (fase 0)

Fire åbne fejl fra gennemgangen rammer netop betjening og live-data og rettes **før** fase 3:

1. Puls kan efterlade udgangen tændt ved timeout på TÆND (`operate.py` `pulse`) — SLUK skal forsøges altid.
2. Toggle er ikke atomisk (`operate.py` `toggle`) — værdien skal læses under låsen.
3. Fuld klient-kø dropper deltas (`live_cache.py`) — ved overløb sendes et nyt snapshot i stedet.
4. `/ws/live` fortsætter efter logout/rolleskift (`live_ws.py`) — sessionen gentjekkes periodisk.

---

## 2. Principper for implementeringen

1. **Én sandhed på serveren.** Konfiguration valideres, position og tilstand beregnes, og skrivninger planlægges i
   backend. Frontend viser og forhåndsviser — dens kopi af logikken (til guiden) er kun til live-feedback.
2. **Genbrug animationsmotoren.** Symbolets animationer omsættes på serveren til almindelige bindinger (samme format som
   i dag) og tegnes af `animate.ts`. Symbolets position publiceres som *pseudo-tags* i live-cachen, så "styres af
   position" er en binding på et pseudo-tag. WebSocket-protokollen ændres ikke.
3. **Side om side i overgangen.** Symboler uden symbol-konfiguration virker som i dag. Har et symbol en konfiguration,
   ignoreres gamle bindinger på symbolet og dets dele (konfigurationen vinder). Ingen tvungen migration.
4. **Additive skemaændringer.** Nye tabeller med `CREATE TABLE IF NOT EXISTS`; intet eksisterende ændres → MINOR-versioner.
   Når den gamle model fjernes (efter migration, afsnit 11), er det MAJOR.
5. **Regler der gælder én gren, gælder alle** (CLAUDE.md 12): alt der samler en bindings/konfigurations tags går gennem
   én hjælpefunktion (`binding_tags()` i dag, udvides til `config_tags()`), så live-data, adgang, tag-sletning og
   backup-import aldrig glemmer et tag.

---

## 3. Datamodel

### 3.1 Tabeller (lag 4b, `storage/db.py`)

```sql
-- Én konfiguration pr. symbol i en tegning (følger elementets id på tværs af versioner, som bindings)
CREATE TABLE IF NOT EXISTS symbol_config (
    drawing_id  TEXT NOT NULL REFERENCES drawings(id) ON DELETE CASCADE,
    element     TEXT NOT NULL,
    config      TEXT NOT NULL,          -- JSON, skema i 3.2 (valideret før skrivning)
    updated_at  REAL NOT NULL,
    updated_by  TEXT NOT NULL,
    PRIMARY KEY (drawing_id, element)
);
-- PIN til nøglelås: adskilt fra config, så den aldrig kan komme med i et svar eller en backup ved en fejl
CREATE TABLE IF NOT EXISTS symbol_pins (
    drawing_id  TEXT NOT NULL REFERENCES drawings(id) ON DELETE CASCADE,
    element     TEXT NOT NULL,
    pin_hash    TEXT NOT NULL,          -- scrypt, samme parametre som brugeradgangskoder
    set_by      TEXT NOT NULL,
    set_at      REAL NOT NULL,
    PRIMARY KEY (drawing_id, element)
);
-- Lokal tilstand: sidst valgte position (overlever genstart)
CREATE TABLE IF NOT EXISTS symbol_state (
    drawing_id  TEXT NOT NULL REFERENCES drawings(id) ON DELETE CASCADE,
    element     TEXT NOT NULL,
    chosen      INTEGER,                -- positionens indeks; NULL = aldrig valgt
    chosen_at   REAL NOT NULL,
    chosen_by   TEXT NOT NULL,          -- brugernavn, "accepteret af <bruger>" eller "import"
    PRIMARY KEY (drawing_id, element)
);
```

`SCHEMA_VERSION` 10 → 11. Opdateringer skriver kun de ændrede rækker (regel 12); `symbol_state` opdateres med
`INSERT … ON CONFLICT DO UPDATE` af de tre felter.

### 3.2 `config` (JSON) — valideres med pydantic i `services/symbols.py`

```jsonc
{
  "type": "selector",              // bibliotekstype (data-hv-type) eller "custom"
  "op": "positions",               // positions | pulse | entry | view
  "positions": [                    // 2–8 ved op=positions, ellers []; navne unikke og ikke tomme
    {"label": "Hand"}, {"label": "0"}, {"label": "Auto"}
  ],
  "signals": [                      // op=positions: 1–8; pulse/entry: præcis 1; view: []
    {"id": "S1", "tag": "P1_driftsform", "fb": "P1_driftsform_fb",
     "write": "set",               // set | pulse (pulse kun for registre)
     "ms": 500, "rest": null}       // ved pulse: 100–10000 ms og påkrævet heltal hvileværdi
  ],
  "planes": [                       // 1–8; values har én celle pr. position; null = røres ikke
    {"signal": "S1", "values": [0, 1, 2]}
  ],
  "fault": "",                      // valgfrit til/fra-tag: Til = betjening blokeret
  "display": "remote",              // remote | local
  "validate_s": 5,                  // 1–120
  "alarm": "medium",                // "" | low | medium | high
  "confirm": true,
  "pulse_ms": 500,                  // op=pulse
  "lock": {"positions": [false, false, true], "leave": false},   // PIN ligger i symbol_pins
  "anims": [                        // 0–12
    {"part": "grip", "type": "rotate", "src": "@pos",
     "params": {"angles": [-45, 0, 45]}, "only": null},
    {"part": "all", "type": "flow", "src": "Pumpe",
     "params": {"mode": "onoff", "dir_tag": "Retning", "arm": "up", "arm_flow": "in"}, "only": [true, true, false]}
  ]
}
```

- **Vinkel pr. position** (guidens trin 4 for omskiftere) gemmes ét sted: som `angles[]` i Drej-animationen på
  grebet. Guiden opretter/opdaterer den animation; der er ingen vinkel på `positions[]`.
- **Rækkefølge:** `anims[]` tegnes i rækkefølge; står flere animationer på samme del, vinder den nederste (▲▼ i guiden
  ændrer rækkefølgen). Serveren bevarer rækkefølgen i de bindinger den danner (feltet `position`).
- Når antallet af positioner ændres, tilpasses alle arrays (planernes celler, `lock.positions`, `only[]` og
  pr.-position-parametre) til den nye længde — nye celler: Fra for til/fra-signaler, "røres ikke" for registre
  (prototypens `structural`).

Grænser (samme som prototypen): positioner 2–8, kontaktplaner 1–8, signaler ≤ 8, animationer ≤ 12, valideringstid
1–120 s, puls 100–10000 ms, PIN præcis 4 cifre.

### 3.3 Animationstyper — prototypens navne → appens

Konfigurationen bruger appens navne og parametre, så `animate.ts` kan tegne dem direkte:

| Prototype | App (`anim`) | Nyt i appen |
| --- | --- | --- |
| Farve | `fill` / `stroke` (stroke når delen er en streg uden fyld — som prototypens `recolor`) | farve pr. position (`colors[]`) |
| Blink | `blink` | `speed`: slow / normal / fast (0,5 / 1 / 2 Hz, i takt på tværs) |
| Synlig | `visible` | — |
| Roterer | **`spin`** (ny) — kontinuerlig rotation om delens centrum | ny type |
| Niveau | `level` | — |
| Værdi | `text` | positionens navn når kilden er `@pos` |
| Drej | `rotate` | vinkel pr. position (`angles[]`); glidning |
| Flyt | `move` | dx/dy pr. position (`dx[]`, `dy[]`); glidning |
| Løbelys | `flow` | retning pr. position (`dirs[]`: -1/0/1) |

Betingelser fra prototypen: til/fra-kilde "når Til/Fra" = eksisterende `invert`; tal-kilde "når ≥ X" = ny parameter
`at_least` (blink/visible/spin); position = `set[]` (aktiv i de afkrydsede positioner).

---

## 4. Symbolbiblioteket (`frontend/src/lib/symbols.ts`)

1. `SymbolDef` får `meta`:
   ```ts
   meta?: { op?: 'positions' | 'pulse' | 'entry' | 'view'; positions?: { label: string; angle?: number }[];
            parts?: Record<string, string>;        // del-id → dansk navn ("rotor": "Løbehjul")
            spin?: string[]; level?: string[]; text?: string[]; turnMove?: boolean; flow?: boolean; junction?: boolean }
   ```
   Udfyldes for alle 82 symboler ud fra det prototypens import gør (`convertDef`): navngivne dele (`fyld`, `soejle`,
   `rotor`, `flamme`, `viser`, `vaerdi` …), rør/fittings = `flow`, T-stykke/kryds = `junction`.
2. Ved indsættelse i Tegn skrives `data-hv-type="<id>"` på roden og `data-hv-pid="<delens id i biblioteket>"` på hver del
   (`svgedit-host/scada-core.js` `insertSymbol`) — delenes id'er kan få løbenumre, så delens navn kan ikke udledes af
   id'et. Saneringen bevarer `data-*`; backend læser typen kun hvis den matcher `[a-z0-9_]{1,40}` (`describe_element`).
   `meta` bruges kun af guiden (forslag og navne) — backend validerer mod tegningens geometri (5.1).
3. Elementer uden `data-hv-type` (egne tegninger, gamle symboler): type `custom`; dele = børn med id; ingen særlige
   dele — Farve/Blink/Synlig/Flyt/Drej på hele symbolet eller en del. Løbelys tilbydes når elementet har streger.
4. `data-hv-auto`/`data-hv-part` bevares til den gamle model og bruges af "Konvertér" (afsnit 11).

---

## 5. Backend — service-lag

### 5.1 `services/symbols.py` — konfiguration (ny)

- `get(drawing_id, element)` → `{config, has_pin, orphaned, library}` — aldrig PIN eller hash (regel 6).
- `put(drawing_id, element, config, actor)` → valideret og normaliseret config. Validering = prototypens `validate()`
  trin 2–5, flyttet til backend og udvidet med det kun serveren ved:
  - tags findes; kommando-tags skrivbare og hr/coil; samme tag ikke i to signaler; tilbagemelding samme slags som kommandoen;
  - ét signal pr. plan; ens kontaktmønstre forbudt (pulssignaler tæller ikke med); register-celler heltal inden for tagets
    min/max ellers datatypens område (`INT_RANGES` i `operate.py`);
  - puls: længde, hvileværdi påkrævet, heltal, i området og ≠ alle positionsværdier; mindst ét plan med et sat-signal;
  - op=pulse kræver til/fra-tag; op=entry kræver tal-tag; view kræver mindst én animation;
  - animationer: del findes i elementet (eller `all`), typen passer til delens **geometri** — Niveau kræver `<rect>`,
    Værdi `<text>`, Løbelys streger eller et rør (besluttet under fase 1: så gælder reglen også egne tegninger, og
    bibliotekets beskrivelse findes kun ét sted, i frontend) — `@pos` kun ved positioner, grænser stigende, min < max,
    løbelys-farver forskellige, `dir_tag` ≠ kilden;
  - lås: låste positioner kræver at PIN er sat eller sættes i samme kald.
  Advarsler (blokerer ikke) returneres separat: ubrugt signal, celler der "røres ikke", animation uden gyldige positioner,
  alle positioner låst.
- `delete(drawing_id, element)`; ved sletning af en tegning kaskaderer tabellerne.
- `config_tags(config)` → alle tags konfigurationen læser/skriver (signaler, fb, fault, animationskilder, `dir_tag`).
  Bruges af scope, tag-sletning (`count_bindings_for_tag` udvides), backup-import og live-abonnementer.

### 5.2 `services/symbol_runtime.py` — position og tilstand (ny)

Kører som `AlarmService`: en løkke pr. `tick_s` + reaktion på live-cache-ændringer. For hvert symbol med op=positions i
aktive tegningsversioner:

1. **Fundet position (Remote)** = prototypens `remotePos`: for hver position sammenlignes alle planer med et
   sat-signal og en værdi i cellen med signalets tilbagemelding (ellers kommando-tagget). Præcis én position der
   passer → den; ingen eller flere → ukendt. Ugyldig kvalitet på et af de læste tags → ukendt.
2. **Tilstand** = prototypens `status`:
   - komm.fejl (kvalitet ≠ good på et læst tag) → `unknown`;
   - Remote: `pending` hvis der inden for `validate_s` er valgt en position som endnu ikke er fundet, ellers
     `confirmed`/`unknown`;
   - Lokal: fundet = valgt → `confirmed`; inden for `validate_s` → `pending`; ellers `mismatch`.
3. **Pseudo-tags** i live-cachen (navnerum `sym:` kan ikke kollidere med tags — `TAG_NAME_RE` tillader ikke `:`):
   - `sym:<tegning>:<element>:pos` — vist position (Lokal: valgt; Remote: fundet), heltal eller `null`;
   - `sym:<tegning>:<element>:remote` — fundet position (til "skygge" ved afvigelse);
   - `sym:<tegning>:<element>:state` — `confirmed | pending | mismatch | unknown`;
   - `sym:<tegning>:<element>:locked` — `true` når den viste position er låst.
   Kvalitet `good`, undtagen `comm_error` når et læst tag har komm.fejl.
4. **Afvigelsesalarm**: ved Lokal og `alarm` ≠ "" giver `mismatch` en betingelse til `AlarmService` (ny kind `symbol`,
   nøgle `sym:<tegning>:<element>`, besked "V1: valgt Auto, PLC viser Hand"). `PRIORITY` får niveauet fra
   konfigurationen; `low` tilføjes alarmlisten og sorteringen (Høj → Medium → Lav).
5. **Genstart**: `symbol_state` indlæses; et valg ældre end `validate_s` er ikke længere `pending`.

### 5.3 `services/symbol_operate.py` — betjening (ny, bruger `OperateService`)

Alle kald: rolle ≥ operator, tegningen i brugerens scope, symbolet konfigureret, fault-tag ikke Til, ingen komm.fejl på
kommando-tags. Én `asyncio.Lock` pr. symbol — er den optaget, svar 409 "Symbolet betjenes allerede — prøv igen".

- **`operate(position, pin?)`** (op=positions):
  1. PIN-tjek hvis `needsPin` (låst mål, eller `leave` og vist position låst) — afsnit 5.4.
  2. Skriveplan = prototypens `plannedWrites`: mål pr. signal fra planerne (`targets`); spring sat-signaler over hvis
     kommando-tagget allerede har værdien; pulssignaler skrives altid.
  3. Rækkefølge **break-before-make**: signaler der går mod 0/Fra først, derefter resten (planernes rækkefølge).
  4. Hver skrivning via `OperateService._write_raw` (samme omregning/min-max som `write`). **Fejler en skrivning,
     stoppes planen** — der rulles ikke tilbage (et automatisk tilbageskift kan være farligere end at stå stille);
     svaret siger præcis hvilke skrivninger der er udført, hvilke der er *usikre* (timeout — PLC'en kan have udført dem)
     og hvilke der ikke er skrevet; tilstanden bliver `mismatch`/`unknown`.
  5. Pulssignaler: værdi → vent `ms` → hvileværdi, kørt som baggrundsopgave (`asyncio.shield`) så hvileværdien skrives
     selvom browseren lukkes; hvile forsøges altid (også efter timeout på første skrivning — fase 0 punkt 1).
  6. `symbol_state` = valgt position (af hvem, hvornår); `runtime.poke()` én gang.
  7. Audit: én række `symbol.operate` med symbol, fra/til position og listen af skrivninger; hver PLC-skrivning logges
     med kontekst (plc, tag, bruger) via `logging`.
- **`pulse()`** (op=pulse): `OperateService.pulse` på signalets tag med `pulse_ms`.
- **`entry(value)`** (op=entry): `OperateService.write` (min/max, omregning, tilbagelæsning).
- **`accept()`**: kun ved `mismatch`; sætter `symbol_state` = fundet position, `chosen_at` = nu − `validate_s`,
  `chosen_by` = "accepteret af <bruger>"; skriver intet til PLC'en; audit `symbol.accept`.

### 5.4 Nøglelås

- `PUT …/pin` (rolle ≥ engineer): body `{pin}` 4 cifre → scrypt-hash i `symbol_pins`; svar kun `{has_pin: true}`.
  `DELETE …/pin` fjerner koden; låste positioner uden kode kan da ikke vælges (svar 409 "Låst — en tekniker skal sætte
  en kode"). Koden logges aldrig, heller ikke i audit.
- Kontrol kun i backend med konstant-tids sammenligning. Fejltæller pr. (symbol, bruger) i hukommelsen: 3 forkerte →
  spærret 60 s for den bruger på det symbol (svar 429 med resterende sekunder). Audit: `symbol.unlock` (ok) og
  `symbol.pin_failed` (antal) — aldrig koden.
- Tælleren nulstilles ved genstart (dokumenteret begrænsning; samme som login-låsningen) og når en tekniker sætter
  eller fjerner koden (ny kode = ny start).
- En kode kan kun sættes på et symbol med en konfiguration (ellers 404); fjernes konfigurationen, fjernes koden med.
  En konfiguration med låste positioner kan ikke gemmes uden kode — "låst uden kode" opstår kun efter `DELETE …/pin`
  eller en restore, og guiden viser da "Symbolet har ingen kode — sæt en ny kode".

### 5.5 Adgang (`services/scope.py`)

- `visible_tags` medtager `config_tags()` og pseudo-tags for symboler i synlige tegninger.
- Operatører betjener symboler via symbol-endpoints (scope = tegningen). De gamle `/api/tags/{name}/…` giver **ikke**
  adgang til symbolernes kommando-tags (ellers kunne en operatør skrive vilkårlige værdier uden om positionerne);
  `operable_tags`/`write_values` udvides tilsvarende kun for gamle klik-bindinger.

---

## 6. API (lag 2, `api/symbols.py`)

| Metode og sti | Rolle | Indhold |
| --- | --- | --- |
| `GET /api/drawings/{d}/symbols/{e}/config` | viewer | `{config, has_pin, warnings, library}` |
| `PUT /api/drawings/{d}/symbols/{e}/config` | engineer | body `{config, pin?}` → normaliseret config + advarsler; 400 med alle fejl pr. trin (`{"error": "...", "steps": {"2": [...], …}}`) |
| `DELETE /api/drawings/{d}/symbols/{e}/config` | engineer | fjerner konfigurationen (symbolet falder tilbage til den gamle model) |
| `PUT` / `DELETE /api/drawings/{d}/symbols/{e}/pin` | engineer | sæt/fjern kode (skriv-kun) |
| `POST /api/drawings/{d}/symbols/{e}/operate` | operator | body `{position, pin?}` → `{writes: [...], state}` |
| `POST …/pulse` · `POST …/entry` `{value}` · `POST …/accept` | operator | som 5.3 |
| `POST /api/drawings/{d}/symbols/{e}/preview` | engineer | body `{config}` → validering + skriveplan pr. position (til guidens trin 6) — skriver intet |

`GET /api/drawings/{d}/view` udvides med `symbols_config: {element: {op, positions, display, confirm, lock_positions,
has_pin, pseudo: {pos, remote, state, locked}}}` og de bindinger animationerne omsættes til (afsnit 7.1). Fejl følger
`errors.py` (én læsbar tekst; pydantic-lister flades ud).

---

## 7. Frontend

### 7.1 Visning (Overview)

- Serveren omsætter hver animation til en binding: `element` = del-id (`<symbol>_<del>`) eller symbolets rod (`all`),
  `tag` = kilden (`@pos` → pseudo-tag `…:pos`), `params` + `only` + `pos_tag`. `bindingTags()` (canvas.ts) medtager
  `pos_tag` og `dir_tag`, så en positionsændring gentegner animationen.
- `animate.ts`:
  - parametre pr. position (`colors[]`, `angles[]`, `dx[]/dy[]`, `dirs[]`, `set[]`) når kilden er et pseudo-tag;
  - `only[]`: uden for de valgte positioner tegnes delen som om animationen ikke fandtes (gendan original);
  - `blink.speed` (tre CSS-klasser, faste perioder så alle blink er i takt), `spin` (CSS-animation om delens centrum);
  - **glidning** for `rotate`/`move`: sæt `style.transform` (med `transform-box: fill-box`) i stedet for
    transform-attributten, så CSS-transition (0,4 s) virker; `prefers-reduced-motion` slår den fra. Skal ses i
    Chromium (regel 13).
- Trykknap (op=pulse) og setpunkt (op=entry) har intet tilstandsmærke; trykknappen bekræftes kun hvis `confirm`, setpunktet
  åbner altid indtastningen (fejl som "Værdien skal være mellem 0 og 100" kommer fra backend).
- Tilstandsmærke ✓ … ! ?, skygge af PLC'ens position ved afvigelse og hængelås tegnes som et overlay-lag ovenpå
  symbolet (samme metode som løbelysets lag), drevet af `…:state`, `…:remote`, `…:locked`.
- Klik på symbolet (prototypens `clickSymbol`): bekræftelse fra + 2 positioner → skift straks til den anden (PIN-dialog
  hvis låst); bekræftelse fra + flere positioner → dialog hvor et klik på en position skifter straks; ellers dialog med
  positionerne og en bekræft-knap, hængelås på låste, "Skift til …"/"Lås op og skift til …", liste over de tags der
  skrives (fra `…/preview`-logikken, uden at kalde serveren for hvert klik), fejlbesked fra backend vises uændret.
- Alarmlisten: niveau `low` med egen farve; sortering Høj → Medium → Lav.

### 7.2 Guiden (Bindinger)

- Klik på et symbol (element med `data-hv-type` eller `data-hv-name`) under Bindinger åbner `SymbolGuide.svelte` i
  stedet for binding-listen; "Avanceret: rå bindinger" giver adgang til den gamle model.
- Trin, felter, skabeloner (A ét register, B ét signal pr. position, C bitmaske, D dec → bin), eksemplet "7-trins vælger"
  og alle tekster som i prototypen. Fejlprikker pr. trin og "Gem" deaktiveret når der er fejl.
- Ren logik i `lib/symbolConfig.ts` (testet med vitest): `targets`, `activeAt`, skriveplan, kontaktmønstre,
  skabeloner, lokal validering til live-feedback. Den endelige validering er serverens (`PUT` svarer med fejl pr. trin).
- Trin 6 "Test og gem": live-værdier pr. signal fra WebSocket, fundet position beregnet lokalt, skriveplan pr. position
  fra `…/preview`, advarsler.
- Tag-felter bruger `TagSelect` (samme dropdown som i dag).

---

## 8. Backup og restore (`services/backup.py`)

- `symbol_config` kommer med (valideres som ved `PUT`, alle tags via `config_tags()` skal findes i backuppen).
- `symbol_pins` og `symbol_state` kommer **ikke** med (hemmeligheder/ driftstilstand). Efter restore har låste
  positioner ingen kode: de kan ikke vælges, og guiden viser "Sæt en ny kode" — sikker standard.
- Ældre backups uden `symbol_config` indlæses som i dag.

---

## 9. Logging og audit

- Struktureret `logging` med kontekst (tegning, symbol, plc, tag, bruger) ved konfiguration, betjening, accept, PIN.
- Audit-handlinger: `symbol.config` (diff af felter, aldrig PIN), `symbol.operate`, `symbol.pulse`, `symbol.entry`,
  `symbol.accept`, `symbol.unlock`, `symbol.pin_failed`, `symbol.pin_set`, `symbol.pin_cleared`.

---

## 10. Faseplan

Hver fase: FEATURES.md først, egen MINOR-version, tests, CHANGELOG/RELEASE_NOTES, commit til `dev`, Jan tester.

| Fase | Indhold | Acceptkriterier (udsnit) |
| --- | --- | --- |
| 0 | Fejl 1–4 fra afsnit 1.1 | Tests for hver fejl; puls-SLUK ved timeout; toggle under lås |
| 1 | Tabeller, `services/symbols.py` (validering), config-API, `config_tags()` i scope/tag-sletning/backup, `data-hv-type` + bibliotekets `meta` | Alle prototypens fejlbeskeder fra trin 2–5 kommer fra backend; et tag i en config kan ikke slettes; backup uden PIN |
| 2 | `symbol_runtime.py`: fundet position, tilstand, pseudo-tags, `symbol_state`, afvigelsesalarm med niveau inkl. `low` | 7-trins dec→bin (3 planer, 3 signaler) findes korrekt i alle 7 positioner; Lokal → Venter → Afvigelse efter `validate_s`; alarm med valgt niveau; genstart bevarer valgt position |
| 3 | `symbol_operate.py` + API: operate (skriveplan, break-before-make, stop ved fejl, puls med hvile), pulse, entry, accept, fault-tag, samtidighed | Mock-PLC: rækkefølge og antal skrivninger som prototypens log; fejl midt i plan stopper og rapporterer; hvileværdi skrives efter lukket browser; accept skriver intet |
| 4 | Overview: mærker, skygge, hængelås, dialoger (bekræftelse til/fra), accept, alarmniveau | Set i Chromium (regel 13): de fire tilstande, ét-klik-skift uden bekræftelse, dialog med positioner ved flere end 2 |
| 5 | Animationer: pseudo-tag-kilde, parametre pr. position, `only[]`, blinkfrekvens, `spin`, glidning, løbelys pr. position | Vippekontaktens greb glider; blink i takt; animation uden for valgte positioner viser delens egen tegning |
| 6 | Guiden (6 trin) inkl. skabeloner A–D, 7-trins eksempel, trin 6 test, Konvertér | Alle 82 bibliotekssymboler kan konfigureres; konvertering giver samme opførsel som før |
| 7 | Nøglelås: PIN sæt/fjern, kontrol, spærring, audit, restore uden kode | 3 forkerte → 60 s spærring pr. bruger; koden findes ikke i nogen svar, log eller backup |
| 8 | Migration (afsnit 11), dokumentation, fjern gammel model (MAJOR) | Alle tegninger konverteret uden ændret opførsel; Jan godkender |

---

## 11. Migration fra den gamle model

1. **Konvertér pr. symbol** (fase 6): guiden foreslår en config ud fra `data-hv-auto`/`data-hv-part` og eksisterende
   bindinger — samme regler som prototypens import (SYMBOLSTANDARD.md afsnit 7): `click:toggle` → 2 positioner med
   `true_text`/`false_text`, ét til/fra-signal; `click:select` → positioner + ét register; `click:pulse` → op=pulse;
   `click:write` → op=entry; `fill` → farve pr. position; `text` → værdi; `move`/`rotate` → Flyt/Drej pr. position.
   Teknikeren ser forslaget i guiden og gemmer.
2. **Konvertér alle** (fase 8): samme regler på tværs af tegninger med en rapport (konverteret / kræver manuel
   handling). Kører som tør-kørsel først. Implementeret som `POST /api/drawings/convert-symbols` (engineer; body
   `{apply: false, drawings?: [...]}`) og panelet "Symbolstandard: konvertér alle" under Tegninger. Kandidater er
   bibliotekssymboler (rødder med `data-hv-type`/`data-hv-auto`) uden konfiguration; status pr. symbol:
   `ready` (kan konverteres) / `converted` / `manual` (grund: forslaget kan ikke valideres eller intet kan overføres,
   fx kun "Gå til tegning") / `configured` / `none` (ingen bindinger). `apply` gemmer kun forslag uden fejl, via samme
   `put()` som guiden; audit `symbol.convert_all`. Hvert symbol kan fortrydes med "Fjern konfiguration".
   Almindelige bindinger på elementer der ikke er bibliotekssymboler berøres ikke.
   Kontrolleret mod hele biblioteket (82 symboler): de 7 betjeningssymboler med færdige bindinger konverteres uden
   fejl; alle animationstyper delenes geometri tillader, valideres på alle dele.
3. **Fjern gammel model** når ingen tegninger har gamle bindinger på symboler: `data-hv-auto`-logikken og
   symbol-delen af `_compute()` udgår (MAJOR).
   **Ikke udført** — kræver Jans godkendelse efter test på anlægget (irreversibel ændring).

---

## 12. Tests

- **Backend (pytest):** validering pr. regel (afsnit 5.1) inkl. fejltekster; position/tilstand for skabelon A–D og
  7-trins dec→bin; Lokal/Remote-tidslinjer med falsk ur; skriveplan og rækkefølge mod mock-PLC; stop ved fejl midt i
  plan; puls-hvile efter afbrudt request; PIN (hash, spærring, aldrig i svar/log/backup); scope (pseudo-tags og
  config-tags synlige, ingen betjening udenfor egne tegninger); backup med/uden symbol_config.
- **Frontend (vitest):** `symbolConfig.ts` (targets, activeAt, skabeloner, kontaktmønstre); `animate.ts` (pseudo-tag,
  `only[]`, pr.-position-parametre, spin, blinkfrekvens); dialoglogik (`clickSymbol`-regler).
- **Runtime-kontekst:** fase 3 og 7 testes også mod den kørende app med mock-PLC (ikke kun unit), og layout/animation
  ses i Chromium (regel 13).

---

## 13. Sporbarhed: prototypen → implementering

| Prototypen (symbolguide.html) | Implementering |
| --- | --- |
| `LIB`, `IMPDEF`, `convertDef`, `newImported` | `symbols.ts` `meta` + `data-hv-type` (afsnit 4); Konvertér (afsnit 11) |
| `setOp`, betjeningsformer, `KIND_TXT` | `config.op` (3.2); guidens trin 1 |
| Signaler (`sig-tag`, `sig-fb`, `sig-write`, `sig-ms`, `sig-rest`) | `config.signals` (3.2), validering 5.1 |
| Kontaktplaner (`plane-sig`, `cell`, `cycle`, `add-plane`) | `config.planes` (3.2), validering 5.1 |
| `template` A–D, `preset` (7-trins dec→bin) | `symbolConfig.ts` (7.2) |
| `targets`, `activeAt`, `plannedWrites` | skriveplan i `symbol_operate.py` (5.3) og `symbolConfig.ts` (7.2) |
| `remotePos`, `status`, `shownPos`, `STATE_TXT`, `GLYPH` | `symbol_runtime.py` (5.2) + pseudo-tags; mærker (7.1) |
| `display`, `validateS`, `alarm`, `ALARM_*` | `config.display/validate_s/alarm`; afvigelsesalarm (5.2.4) |
| `fault`, `blockedMsg` | `config.fault`; tjek i 5.3 |
| `confirm`, `clickSymbol`, `renderDialog` | `config.confirm`; dialog (7.1) |
| `operate`, `operatePulse`, `operateEntry` | `symbol_operate.py` (5.3) + API (6) |
| `accept`, `fieldSwitch` (skift ved maskinen) | `accept()` (5.3); skift ved maskinen = Remote/Lokal-logikken (5.2) |
| `lock`, `needsPin`, PIN-spærring, `LOCK_SVG` | 5.4 + hængelås (7.1) |
| Animationer `ATYPES`, `animDefaults`, `evalAnims`, `typesFor` | 3.3 + `animate.ts` (7.1) + validering (5.1) |
| `only[]` (gælder i positionerne) | binding-param `only` + `pos_tag` (7.1) |
| `BLINK_MS`, blinkfrekvens | `blink.speed` (3.3, 7.1) |
| Glidning `.tmove`, `morph` | `style.transform` + transition (7.1); Overview opdaterer allerede DOM på stedet |
| Løbelys `drawFlow`, `JUNC`, `dirSrc`, `FLOW_DIR` | allerede i appen (v0.29–0.31); `dirs[]` pr. position er nyt (3.3) |
| `validate` (trin 2–5 + advarsler) | `services/symbols.py` (5.1) + lokal spejling (7.2) |
| `renderLive6` (trin 6) | trin 6 + `…/preview` (6, 7.2) |
| Simulatoren (`sim`, `sim-mode`, `sim-delay`, `sim-comm`) | mock-PLC i tests (12); ikke en del af produktet |
