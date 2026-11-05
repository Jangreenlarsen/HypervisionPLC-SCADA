# Demo-PLC: varmeanlæg emuleret i ST

En HypervisionPLC uden fysisk I/O, som opfører sig som varmeanlægget på tegningen `varme`. Det omfatter et brændefyr med Laddomat, et pillefyr, en varmepumpe, en akkumuleringstank i 6 lag, husets varmekreds, motorventiler, systemtryk med sikkerhedsventiler, alarmer og scenarier. SCADA læser og skriver programvariablerne direkte over PLC'ens REST API (`/api/logic/{id}`, `/var`), så der skal ikke laves Modbus-bindinger. Plan og baggrund: [PLAN.md](../../PLAN.md).

| Fil | Indhold |
|---|---|
| `globals.st` | 16 `GLOBAL_VAR` (fuldt budget), der forbinder programmerne |
| `logic1_styring.st` | **Styringen**: driftsform, prioritering af varmekilder, vejrkurve, pumper og ventiler, alarmer |
| `logic2_kilder.st` | Procesmodel: brændefyr, Laddomat og P4, pillefyr (tilstandsmaskine) og P2 |
| `logic3_tank_hus.st` | Procesmodel: tank i 6 lag, husets kreds (AVTB, P1, flow), MVS1/MVS2 med 30 s gangtid |
| `logic4_system.st` | Tryk og sikkerhedsventiler, udetemperatur og klokke, tidsfaktor, scenarier og fejl, varmepumpe og P3 |
| `load.py` | Indlæser det hele på PLC'en og kontrollerer, at det kører |
| `test/run.sh` | PC-test med PLC'ens egen ST-compiler og VM |

## Indlæsning

```bash
bash demo/varme-plc/test/run.sh                                   # først: PC-test (kræver g++ og ../HypervisionPLC)
PLC_USER=admin PLC_PASS=... python demo/varme-plc/load.py http://<plc-ip>
PLC_USER=admin PLC_PASS=... python demo/varme-plc/load.py http://<plc-ip> --check   # kun status
```

Kræver en PLC **med PSRAM**. Demoen fylder ca. 18 KB, og kildepuljen er 64 KB med PSRAM, men kun 8 KB uden. Alle fire programmer kører med et interval på 500 ms. Fysikken regner med `dt = 0,5 s × sp_speed`, så intervallet skal stå på 500 ms.

## Variable til SCADA (tag-kind `logic`)

Navnene svarer til felterne på tegningen. **Fed** = skrivbar fra SCADA.

| Tegning | Program | Variabel | Enhed / værdier |
|---|---|---|---|
| SMS | 1 | `SMS_TXT` (tekst), `SMS` (kode) | Stop · Tank · Brændefyr · Varmepumpe · Pillefyr · Frostsikring · Manuel · TRYKSTOP. Koder: 0 stop, 1 tank, 2 brændefyr, 3 VP, 4 pille, 6 pille direkte, 8 frost, 9 manuel, 10 trykstop |
| Omskifter 1 | 1 | **`cmd_mode`** | 0 Fra · 1 Auto · 2 Sommer · 3 Kun pille · 4 Manuel |
| PS1–PS4 | 1 | `PS1` … `PS4` | BOOL, pumpen kører |
| Alarmer | 1 | `AL_P1`…`AL_P4`, `AL_VP`, `AL_PILLE`, `AL_TRYK_LAV`, `AL_TRYK_HOEJ`, `AL_FF_TEMP`, `AL_TANK_KOLD`, `ALARMER` (antal) | Pumpe-, VP- og pillefejl er låst, indtil de kvitteres |
| — | 1 | **`cmd_kvitter`** | TRUE = kvittér (nulstilles af PLC'en) |
| — | 1 | **`man_P1`…`man_P4`, `man_MVS`, `man_pille`, `man_VP`** | Gælder kun i Manuel |
| — | 1 | **`sp_rum`** 21, **`sp_kurve`** 1,0, **`sp_stf_max`** 55, **`sp_tank_min`** 45, **`sp_tank_hyst`** 8, **`sp_vp_min`** −5, **`sp_sommer`** 17 | °C |
| — | 1 | `STF_SP` | Beregnet fremløbssetpunkt, °C |
| FFTF / FFTR | 2 | `FFTF`, `FFTR` | °C |
| FFS | 4 | `FFS_TXT` | Slukket · Optænding · Drift · Overtemp |
| Fyr Fast | 2 | **`cmd_fyr_op`** | TRUE = læg 15 kg brænde i (højst 30 kg) |
| Laddomat | 2 | `LADDOMAT`, `FF_KW`, `FF_KG` | Åbner ved 72 °C |
| PFTF / PFTR | 2 | `PFTF`, `PFTR` | °C |
| Pille Status | 2 | `PILLE_TXT`, `PILLE_ST` | Stop · Tænding · Drift · Udbrænding · Fejl |
| — | 2 | `PILLE_KW`, `PILLE_KG`, `PILLE_STARTS`, **`sp_pille`** 75 | |
| Energi | 2 / 4 | `E_FF`, `E_PILLE` (L2), `E_VP`, `E_VP_EL` (L4) | kWh, tæller op |
| ATT1–ATT6 | 3 | `ATT1` … `ATT6` | °C, top → bund |
| TS | 3 | `TS` | Tankens ladning i % (30–80 °C) |
| ATF | 3 | `ATF` | Fremløb fra tankens top, °C |
| STF / STR | 3 | `STF`, `STR` | Husets frem- og returløb, °C |
| FMTR | 3 | `FMTR` | L/min |
| MVS1 / MVS2 | 3 | `MVS1_TXT`, `MVS2_TXT`, `MVS1_POS`, `MVS2_POS` | AB-A · Kører · AB-B; position 0–100 % |
| MVT2 | 3 | `MVT2` | °C |
| — | 3 | `T_RUM`, `Q_HUS`, `E_HUS`, `E_TANK` | Rumtemperatur, husets effekt og energi |
| ST | 4 | `ST` | bar |
| Sikkerhedsventiler | 4 | `SV_AABEN` | Åbner ved 2,5 bar og lukker igen ved 2,3 bar |
| VP / VPTF / VPTR | 4 | `VP_RUN`, `VPTF`, `VPTR`, `VP_KW`, `VP_EL`, `VP_COP` | |
| Omskifter 2 | 4 | **`cmd_scenarie`** | 0 Normal · 1 Vinternat (−15…−9 °C) · 2 Sommer · 3 Lækage · 4 Pumpefejl P1 |
| — | 4 | **`sp_speed`** | Tidsfaktor 1–120 (fx 60 = én time pr. minut) |
| — | 4 | **`cmd_efterfyld`** | TRUE = efterfyld anlægget til 1,2 bar (kold) |
| — | 4 | **`f_P1`…`f_P4`, `f_pille`, `f_vp`, `f_laek`** | Fejl, der kan slås til og fra enkeltvis |
| — | 4 | **`sp_tude_fast`**, **`sp_tude`** | Fastlås udetemperaturen |
| — | 4 | `T_UDE`, `KLOKKE`, `DAG` | Udetemperatur, simuleret klokkeslæt og dag |

## Hvad demoen viser

- **Auto:** Varmepumpen lader tanken først. Pillefyret hjælper, når tanken er kold, eller når det er for koldt til varmepumpen. Er tanken for kold til huset, kører pillefyret **direkte**: MVS1 og MVS2 kører til AB-B på 30 s.
- **Fyr op:** Brændefyret tager over. Laddomat og P4 lader tanken, op til 80+ °C.
- **Vinternat:** Varmepumpen er blokeret, og pillefyret holder huset på 21 °C.
- **Lækage:** Trykket falder, så alarmen for lavt tryk kommer ved 1,0 bar og trykstop ved 0,6 bar. *Efterfyld* genopretter.
- **Pumpefejl P1:** Alarmen kommer efter 10 s og er låst, indtil der kvitteres.
- **`f_P4` + fyr op:** Overtemperatur, så damp og tryk stiger, og sikkerhedsventilen åbner og tømmer anlægget. Bagefter giver det lavt tryk og kræver efterfyldning.
- **`f_pille`:** Pillefyret tænder ikke, og efter 10 min kommer `AL_PILLE`. **`f_vp`:** `AL_VP`, og pillefyret overtager.

## Firmware-forhold fundet under udviklingen (HypervisionPLC v7.9.68)

- **Højst 512 AST-noder pr. program.** Det er puljen i `st_parser.cpp` ved monolitisk kompilering. Testen måler forbruget. I dag ligger programmerne på 473, 484, 443 og 370 noder.
- **Strengkonstanter tælles pr. forekomst** (højst 8 pr. program), ikke pr. forskellig tekst.
- **En STRING-variabels startværdi (`:= 'x'`) sættes ikke.** Tildel den i koden i stedet.
- **Fejl: negative startværdier i VAR (`:= -5.0`, `:= -7`) bliver til 0.** Den er meldt til PLC-projektet. Her sættes `sp_vp_min` ved første scan i stedet.
- **Ingen bitvise operatorer på INT** (`AND`/`XOR`/`NOT` kræver BOOL). Brug `BIT_TST`/`BIT_SET`.
- **Fejl: CASE med flere værdier i samme gren (`4, 6:`) rammer ingen af værdierne.** Den er meldt til PLC-projektet. Her er den omgået med en hjælpevariabel.
