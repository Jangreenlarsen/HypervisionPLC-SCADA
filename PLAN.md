# Plan: Demo-PLC — ST-program der emulerer varmeanlægget — 2026-11-05

**Mål:** en HypervisionPLC, der uden fysisk I/O opfører sig som varmeanlægget på tegningen `varme` (v121 på 10.1.1.31), så SCADA-demoen viser levende temperaturer, flow, tryk, pumper, ventiler, alarmer, trends og betjening — og reagerer realistisk når operatøren griber ind.

**Rammer (fra PLC-manualen, D.6/§8.9/§8.10/B):** 4 programmer · 64 variabel-slots pr. program · 16 `GLOBAL_VAR` (kun skalarer, nulstilles ved genstart) · 8 timere/edges/tællere pr. program · ARRAY ≤ 24 · REAL er 32-bit · kilde-pool 64 KB (PSRAM) delt mellem programmerne. SCADA læser programvariable via `GET /api/logic/{id}` (tag-kind `logic`) og skriver via `POST /api/logic/{id}/var` og `/api/logic/globals/var` — **ingen Modbus-bindinger nødvendige**, og intet nyt i SCADA's PLC-lag.

## 1. Anlægget som det står på tegningen (tolkning — skal bekræftes)

| Del | Symboler/felter | Emuleres som |
|---|---|---|
| Fastbrændselsfyr | Fyr Fast, FFS, FFTF, FFTR, Laddomat (≈70 °C), Pumpe 4 (PS4) | Brændeindhold (kg) der brænder ud efter en kurve; Laddomat-ventil åbner mod tank ved ~72 °C; P4 starter ved FFTF > 60 °C |
| Pillefyr | Fyr Pille, Status, PFTF, PFTR, Pumpe 2 (PS2), sikkerhedsventil | Tilstandsmaskine OFF → TÆNDING (60 s) → DRIFT (modulerende 5–15 kW) → UDBRÆNDING; tændingsfejl som scenarie |
| Varmepumpe | VP + lampe, VPTF, VPTR, Pumpe 3 (PS3), AVTA-ventil (≈50 °C) | Ydelse og COP som funktion af udetemp. og fremløb, maks. 55 °C fremløb |
| Akkumuleringstank | Aku Tank, TS, ATT1–ATT6, ATF | 6 lagdelte zoner à 125 L; varmt ind i toppen, retur i bunden, varmetab, udligning ved inversion |
| Husets varmekreds | System Output (STF), System input (STR), AVTB-blandeventil (≈50 °C), Pumpe 1 (PS1), Flow Måler (FMTR), MVT2 | Varmebehov UA·(T_rum − T_ude); vejrkompenseret fremløb; STR = STF − Q/(ṁ·cp); flow fra P1 |
| Motorventiler | MVS1, MVS2 (ON = AB-B, OFF = AB-A), Bypass-ventil | Gangtid 30 s, position 0–100 %, status Åben/Lukket/Kører/Fejl |
| Tryk/sikkerhed | System Tryk (ST), 2× sikkerhedsventil 2,5 bar, ekspansionsbeholder | Tryk = p₀ + k·(middeltemp − 20) dæmpet af ekspansion; ventil åbner > 2,5 bar; lækage-scenarie; "Efterfyld"-kommando |
| Tilstand | SMS, omskifter 1 (Fra/Auto/…), omskifter 2 (Fra/Til/…) | Omskifter 1 = driftsform, omskifter 2 = demo-scenarie (etiketter rettes på tegningen) |

## 2. Programopdeling (valgt: styring adskilt fra procesmodel)

Alternativer: (a) ét stort program — rammer 64-slot-grænsen; (b) ét program pr. anlægsdel med egen styring — få globals, men styring og fysik blandes sammen; (c) **valgt:** Logic1 er "den rigtige PLC-styring", Logic2–4 er "anlægget". Det er sådan et rigtigt anlæg ser ud og gør demoen troværdig: styringen kan senere flyttes til en rigtig PLC uændret.

| Program | Indhold | Interval |
|---|---|---|
| **Logic1 STYRING** | Driftsform (Fra/Auto/Kun VP/Kun pille/Manuel), kildeprioritet (fast > pille > VP efter ATT1/ATT3), pumpe-/ventilkommandoer, vejrkurve, setpunkter, alarmer (bool-variable), kvittering, driftstimer og starttællere | 500 ms |
| **Logic2 KILDER** | Fastbrændselsfyr + Laddomat, pillefyr-tilstandsmaskine, varmepumpe-COP; energitællere kWh pr. kilde (DINT) | 200 ms |
| **Logic3 TANK + HUS** | 6-lags tank, husets varmebehov, AVTB-blanding, STF/STR/FMTR, udetemperatur (døgnsinus + overstyring), MVS1/MVS2-gangtid | 200 ms |
| **Logic4 SYSTEM + DEMO** | Tryk, sikkerhedsventiler, efterfyldning, sensorstøj (lille, så trends lever), scenarier og fejlinjektion, tidsacceleration (×1/×10/×60), `WDT_FEED` | 500 ms |

**GLOBAL_VAR (16, fuldt budget):** `g_cmd` (INT, bitmaske pumper/ventiler/brænder fra Logic1), `g_fb` (INT, bitmaske tilbagemelding/fejl fra modellen), `g_fault` (INT, injicerede fejl fra Logic4), `g_speed` (REAL), `g_tude`, `g_att1`, `g_att3`, `g_att6`, `g_fftf`, `g_pftf`, `g_vptf`, `g_stf`, `g_str`, `g_flow`, `g_tryk`, `g_last_kw`. Alt andet er lokale variable i det program der ejer dem (SCADA læser dem direkte). Fysikken bruger `dt = interval · g_speed`, så accelereret tid er konsistent i alle programmer.

**Navne:** variablerne hedder som felterne på tegningen (`FFTF`, `ATT1`, `PS1` …), så binding i SCADA bliver 1:1. Skrivbare variable får præfiks `sp_` (setpunkt) eller `cmd_` (kommando), så det er tydeligt hvad operatøren må røre.

## 3. Betjening fra SCADA (det demoen skal vise)
- Omskifter 1 → `Logic1.cmd_mode`; omskifter 2 → `Logic4.cmd_scenarie`.
- Setpunkter: rumtemp., vejrkurvehældning, tank-min., pillefyr-start/stop-temp., Laddomat-temp.
- Kommandoer: "Fyr op i brændefyr" (læg 15 kg brænde i), manuel pumpe/ventil i Manuel-form, efterfyld anlæg, kvittér alarmer, tidsacceleration.
- Scenarier: Normal · Kold vinternat (−15 °C) · Sommer (kun VP) · Lækage (tryk falder) · Pumpefejl P1 · Pillefyr tænder ikke · Overophedning fastbrændselsfyr (P4 stopper → sikkerhedsventil åbner).

## 4. Trin
1. **Bekræft tolkning** af hydraulikken (afsnit 1) og hvilken PLC der bliver demo-PLC.
2. **ST-kilde i repoet:** `demo/varme-plc/` med `globals.st`, `logic1_styring.st` … `logic4_system.st`, `README.md` (opsætning, variabeloversigt, scenarier) og et `load.py`, der uploader alt via PLC'ens REST API og sætter intervaller.
3. **Test på PC** med PLC-projektets host-harness (`C:\Projekter\HypervisionPLC\test\st_host`): kompilér alle fire programmer og kør et simuleret døgn ×60; tjek at temperaturer holder sig fysisk (0–100 °C), tryk 0,5–3 bar, ingen runtime-fejl, og at hvert scenarie udløser den forventede alarm. (Kræver at harnessen kan køre flere programmer med `GLOBAL_VAR` — ellers en lille udvidelse i PLC-repoet.)
4. **Indlæs på demo-PLC'en**, verificér med `GET /api/logic/{1-4}` og `/stats` (exec-tid, ingen fejl, ingen overruns).
5. **SCADA-opsætning (konfiguration, ingen kode):** tilføj PLC'en, opret tags via discover af logic-variable (enheder, decimaler, min/max, skrivbare med bekræftelse), kopiér `varme` → `varme-demo` og bind alle symboler, trends (ATT1–6, STF/STR, udetemp., tryk, kWh), alarmregler, evt. tidsplan for natsænkning og energisiden.
6. **Demo-gennemgang** i browseren (set, ikke kun bygget) + skærmbilleder til manualen hvis demoen beskrives der.

## Berørte filer
Nyt: `demo/varme-plc/*`. Dokumentation: `FEATURES.md` (registreres før start), `CHANGELOG.md`/`RELEASE_NOTES.md`. Ingen ændring i backend/frontend forventes; viser opsætningen et hul i SCADA (fx manglende bindingstype), registreres det som separat feature.

## Risici
- **Variabel-/globalgrænser:** 64 slots og 16 globals er stramt — bitmasker og REAL-felter er planlagt ind; Logic3 (tank + hus) er tættest på grænsen og kan deles, hvis det kniber.
- **Kildegrænse:** manualen nævner både 5.000 bytes pr. program (D.6) og en 64 KB-pool (B) — kontrollér på demo-PLC'ens firmware; hold kommentarer korte i de indlæste filer.
- **Globals nulstilles ved genstart** → Logic4 initialiserer fornuftige startværdier (tank 45 °C, tryk 1,5 bar) første scan.
- **SCADA-polling:** 4 programmer × `GET /api/logic/{id}` pr. cyklus; 10.1.1.30 viser allerede ~0,2 s pr. program. Overvåg `request_rate`/`slowest` på PLC-statussen; brug SSE hvor muligt.
- **Instruktionsloft** 10.000 pr. scan (NORMAL): 6-lags tank-løkken er lille, men tjek `max_execution_us` i `/stats`.
