# Kodeanalyse — fejl og robusthed (26.10.2026)

**Omfang:** SCADA-backend (`backend/app`, ca. 13.000 linjer), med fokus på det, der kører hele tiden på Pi'en: PLC-polling, SSE, live-cache, alarmer, trend-opsamling, ugeprogrammer, betjening (skrivninger til PLC) og energi. Frontend er ikke gennemgået i denne runde.
**Version:** v1.21.4 (build 0239).
**Metode:** Fase 1 er en bred gennemgang med mønstersøgning og læsning af de kritiske stier. Fase 2 verificerer hvert fund med måling på testserveren 10.1.1.31 eller med en test mod den rigtige kode, beskriver årsag og konsekvens og foreslår en rettelse. Ingen kode er ændret.

> Testserveren er en x86-VM med 2 kerner, ikke en Raspberry Pi 4. En Pi er typisk 3–5 × langsommere, så tider målt på serveren er et optimistisk bud for Pi'en.

---

## Fase 1 — oversigt

| # | Fund | Område | Alvor | Verificeret |
|---|------|--------|-------|-------------|
| F4 | Puls: SLUK forsøges kun én gang — fejler den, står udgangen tændt | Betjening | **Høj** | Test mod koden |
| F6 | Energirapport er kvadratisk og kører i event-loopet — kan fryse SCADA i minutter | Energi | **Høj** | Måling: 44 s på PC for 1 år |
| F1 | Trend-data og CSV-eksport kører synkront i event-loopet — hele serveren står stille imens | Trends | **Mellem-høj** | Måling: 2,2 s og 6,8 s stilstand |
| F5 | Én fejlmåling i en energitæller giver et kæmpe falsk forbrug | Energi | **Mellem** | Test mod koden |
| F2 | Timevis oprydning og `/api/trends/info` scanner hele trend-tabellen i event-loopet | Trends | Lav-mellem (vokser) | Forespørgselsplan + måling |
| F3 | Trend-opsamleren mister målinger, hvis en skrivning til databasen fejler | Trends | Lav | Test mod koden |
| F7 | Automatisk backup kører synkront i event-loopet | Backup | Lav | Kun læst i koden |

**Tjekket uden fund:**
- Alle baggrundsløkker (polling, SSE, alarmer, symboler, trends, ugeprogrammer, backup) er beskyttet mod at dø ubemærket.
- Live-cachens køer fletter ved overløb, så ingen ændring tabes.
- Ugeprogrammer regner i dansk vægur-tid og tåler sommertid/vintertid.
- Skrivninger er serialiseret pr. tag (`asyncio.Lock`) og bekræftes ved tilbagelæsning.
- SSE går ikke gennem PLC'ens rate-limit.

---

## Fase 2 — detaljer

### F4 · Puls: SLUK forsøges kun én gang (Høj)

**Hvor:** `services/operate.py`, `pulse()` (linje ca. 352–359) og `pulse_value()` (linje ca. 305–312).

**Hvad sker der:** En puls skriver TÆND, venter `ms` og skriver SLUK i en `finally`. SLUK-skrivningen forsøges **én gang**. Fejler den, får brugeren beskeden "ADVARSEL: pulsen blev sat men IKKE nulstillet", og udgangen bliver stående tændt, indtil nogen griber ind.

**Hvornår fejler SLUK:**
- En enkelt timeout eller et kort netværksudfald på netop det kald.
- PLC-klientens lokale backoff efter et 429 fra *et hvilket som helst* andet kald i de foregående 1–30 s. Så afvises SLUK lokalt uden overhovedet at nå PLC'en (`PlcClient._send`, "PLC'en har bedt os vente"). Med BUG-509 i PLC-firmwaren, rettet i v7.9.68.150 men endnu ikke flashet, er 429 ikke sjældent.

**Bevis:** En test med en klient, hvor SLUK rammer den lokale backoff, viser kaldene `[TÆND, SLUK]`, beskeden "IKKE nulstillet" og udgangen **tændt** bagefter.

**Konsekvens:** Pulser bruges til start/stop-signaler, kvittering o.l. En udgang, der bliver stående, kan holde en motor, en ventil eller en kvittering aktiv. Det er det mest alvorlige fund.

**Forslag:**
1. SLUK skrives med genforsøg i op til ca. 10 s (fx 0,25 → 0,5 → 1 → 2 s …), indtil PLC'en har bekræftet det.
2. SLUK må ikke blokeres af klientens lokale backoff. Tilføj et `urgent`-flag på skrivekaldet, der venter på tokens frem for at give op.
3. Lykkes det stadig ikke: kritisk post i hændelsesloggen og en alarm ("Udgang X kunne ikke nulstilles"), ikke kun en fejltekst til den bruger, der trykkede.
4. Samme behandling i `pulse_value()` og i timeout-grenen af `pulse()`.

*Omfang: lille (én hjælpefunktion + tests).*

### F6 · Energirapport: kvadratisk og i event-loopet (Høj)

**Hvor:** `services/energy.py`, `counter_energy()` og `power_energy()`. Kaldes fra `api/energy.py` (`async def energy_report/energy_export`) uden `to_thread`.

**Hvad sker der:** For **hver** periode (fx hver dag i et år) gennemløbes målingerne forfra (`counter_energy`), og *alle* stykker gennemløbes (`power_energy`). Arbejdet er altså perioder × målinger. Det hele kører synkront i den async-handler, så ingen anden kode i SCADA kører imens.

**Bevis (målt lokalt, syntetiske data med én måling pr. minut):**

| Periode | Målinger | Tæller | Effekt |
|---------|----------|--------|--------|
| 30 dage pr. dag | 43.200 | 0,03 s | 0,30 s |
| 1 år pr. dag | 525.600 | 4,3 s | **43,8 s** |

Testserveren har ingen energi-tags endnu, så det kan ikke måles dér.

**Konsekvens:** Én åben årsrapport over et effekt-tag kan fryse SCADA i et minut eller mere på en Pi. Det betyder ingen polling, ingen alarmer, ingen live-værdier og ingen betjening. Energiopsætning blev indført for nylig, så det rammer, så snart den tages i brug.

**Forslag:**
- Ét gennemløb, hvor målinger og perioder løbes igennem samtidig. Det giver lineær tid og typisk under 0,5 s for et år.
- Kør beregningen i `asyncio.to_thread`, så den aldrig blokerer event-loopet.

*Omfang: lille-mellem (to funktioner + tests af samme resultat som i dag).*

### F1 · Trend-data og CSV-eksport blokerer event-loopet (Mellem-høj)

**Hvor:** `api/trends.py`, `data()` og `export()`. `TrendDatabase.series()`/`raw()` og CSV-opbygningen kører synkront i `async def`.

**Bevis (testserveren, 8 tags, trend-db 23,8 MB / 1,0 mio. målinger, `/api/health` pinget hvert 50 ms imens):**

| Kald | Svartid | Største svartid for /api/health |
|------|---------|----------------------------------|
| Trends 24 t | 0,06 s | 0,05 s |
| Trends 30 dage | 2,2 s | **2,2 s** |
| CSV-eksport 30 dage | 7,2 s | **6,8 s** |
| `/api/trends/info` | 0,5 s | 0,5 s (se F2) |

`/api/health` venter præcis lige så længe som det tunge kald. Hele serveren står stille.

**Konsekvens:** Imens bliver polling, SSE-læsning, alarmer, ugeprogrammer og WebSocket-opdateringer forsinket. Det betyder frosne værdier på alle skærme og forsinket betjening. Tiden vokser med databasen (op til 30 dages historik) og er større på en Pi. v1.21.2 (tidsvægtet gennemsnit) gjorde `series()` ca. 4 × dyrere pr. tag (63 ms mod 15 ms for 30 dage på PC).

**Forslag:**
- `data()`: kør opslagene i `asyncio.to_thread`. `TrendDatabase` har allerede sin egen lås og en forbindelse med `check_same_thread=False`.
- `export()`: generér CSV i en tråd, eller send svaret som en strøm i bidder.
- Evt. senere: lad SQL lave det groveste af nedsamplingen ved lange perioder, så Python-løkken får færre rækker.

*Omfang: lille.*

### F5 · Fejlmåling i en energitæller giver falsk forbrug (Mellem)

**Hvor:** `services/energy.py`, `counter_energy()`: `total += d if d >= 0 else v` ("fald = nulstilling").

**Hvad sker der:** Ethvert fald i en tæller tolkes som en nulstilling. Én fejlmåling, fx 0 med god kvalitet som fra R4DCB08 i dag, eller en revet 32-bit-læsning, efterfulgt af den rigtige værdi tæller hele tællerens værdi som forbrug.

**Bevis:** Målingerne 12.345 → 0 → 12.346 kWh giver **12.346 kWh** i perioden i stedet for 1 kWh.

**Konsekvens:** Forkerte energirapporter, og det er svært at se, hvorfor. Et filter i PLC'en (FEAT-508) hjælper, men kun hvis det er sat op for netop den tæller.

**Forslag:** Et fald godtages kun som nulstilling, hvis det bekræftes. Kommer den næste gyldige værdi tilbage på eller over niveauet før faldet, var det en fejlmåling, og målingen springes over. Evt. også: et fald til en værdi tæt på 0 fra en stor værdi kræver to lave målinger i træk.

*Omfang: lille (én funktion + tests).*

### F2 · Fuld scanning af trend-tabellen (Lav-mellem, vokser)

**Hvor:** `storage/trends_db.py`: `purge_before()` (`DELETE … WHERE ts < ?`, kaldt hver time fra `TrendRecorder.flush()` i event-loopet) og `stats()` (`GROUP BY tag_id`, kaldt fra `/api/trends/info`, hver gang Trends åbnes).

**Bevis:** Forespørgselsplanen for `WHERE ts < ?` er `SCAN samples`. Primærnøglen `(tag_id, ts)` kan ikke bruges uden `tag_id`. Målt på serveren: 0,12 s for oprydningens scanning og 0,44 s for `stats()` ved 1 mio. målinger. Begge vokser lineært med historikken.

**Forslag:**
- Oprydning pr. tag (`DELETE … WHERE tag_id = ? AND ts < ?`), som bruger primærnøglen, og i en tråd.
- `stats()`: `MIN`/`MAX` pr. tag via primærnøglen og antal fra en tæller, der vedligeholdes ved indsættelse, eller i en tråd med kort cache.

*Omfang: lille.*

### F3 · Trend-opsamleren mister målinger ved databasefejl (Lav)

**Hvor:** `services/trends.py`, `flush()`: `rows, self._buffer = self._buffer, []` og derefter `insert_many(rows)`.

**Bevis:** En test med `insert_many`, der fejler ("database is locked"), viser, at bufferen er tømt, og at målingerne aldrig kommer i databasen ved næste flush.

**Konsekvens:** Huller i historikken ved kortvarige databasefejl (SD-kort, samtidig backup/flytning af databasen). Det sker sjældent, men det sker uden at nogen opdager det; det logges kun.

**Forslag:** Ved fejl lægges rækkerne tilbage forrest i bufferen (med en øvre grænse, fx 100.000 rækker, så hukommelsen ikke løber løbsk) og prøves igen ved næste flush.

*Omfang: meget lille.*

### F7 · Automatisk backup i event-loopet (Lav, ikke målt)

**Hvor:** `services/backup.py`, `auto_backup_loop()` kalder `save_to_server()` synkront. Trend-snapshot'et køres allerede korrekt i en tråd.

**Konsekvens:** En kort stilstand hver N. time, som vokser med antal tegninger (SVG'er) i databasen. Formentlig lille i dag.

**Forslag:** `await asyncio.to_thread(self.save_to_server, …)`.

---

## Anbefalet rækkefølge

1. **F4** (puls-SLUK med genforsøg): sikkerhed for udgange.
2. **F6 + F5** (energi): rettes samlet, da begge ligger i `energy.py`.
3. **F1 + F2 + F7** (event-loop-blokering): samme mønster (`to_thread`) og samme test (stilstand målt med `/api/health`).
4. **F3** (genforsøg ved databasefejl).

Hvert punkt kan laves som en selvstændig rettelse med test og versionsbump efter projektets workflow.
