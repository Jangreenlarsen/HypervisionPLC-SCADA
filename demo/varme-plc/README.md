# Demo-PLC: varmeanlæg emuleret i ST

En HypervisionPLC uden fysisk I/O, som opfører sig som varmeanlægget på tegningen `varme`. Det omfatter et brændefyr med Laddomat, et pillefyr, en varmepumpe, en akkumuleringstank i 6 lag, husets varmekreds, motorventiler, systemtryk med sikkerhedsventiler, alarmer og scenarier. SCADA læser og skriver programvariablerne direkte over PLC'ens REST API (`/api/logic/{id}`, `/var`), så der skal ikke laves Modbus-bindinger. Plan og baggrund: [PLAN.md](../../PLAN.md).

| Fil | Indhold |
|---|---|
| `globals.st` | 16 `GLOBAL_VAR` (fuldt budget), der forbinder programmerne |
| `logic1_styring.st` | **Styringen**: driftsform (Auto / manuel mode 1-3), tanken ind og ud, vejrkurve, pumper og ventiler, alarmer |
| `logic2_kilder.st` | Procesmodel: brændefyr, Laddomat og P4, pillefyr (tilstandsmaskine) i husets kreds |
| `logic3_tank_hus.st` | Procesmodel: tank i 6 lag, husets kreds (AVTB, P1, flow), MVS1/MVS2 med 30 s gangtid |
| `logic4_system.st` | Tryk og sikkerhedsventiler, udetemperatur og klokke, tidsfaktor, scenarier og fejl, varmepumpe og P3 |
| `load.py` | Indlæser det hele på PLC'en og kontrollerer, at det kører |
| `test/run.sh` | PC-test med PLC'ens egen ST-compiler og VM |

## Driftsmodes

| Mode | Kreds | M1 | M2 | Husets pumpe |
|---|---|---|---|---|
| 1 | Hus + pillefyr. Tanken er uden for kredsen | AB-A | AB-A | P1 |
| 2 | Hus + pillefyr + tank. Returvandet går gennem tanken (bund → top) og derefter pillefyret | AB-A | AB-B | P1 |
| 3 | Hus + tank. Tanktop → M2 B → M1 B → P2 → hus. Pillefyret er uden for kredsen | AB-B | AB-B | P2 |

- **`cmd_mode`:** 0 Auto, 1-3 manuel mode. I **Auto** kobles tanken ind (mode 3), når ATT1 ≥ `sp_tank_ind` (60 °C), og ud igen (mode 1) under `sp_tank_ud` (45 °C). Mode 2 vælges kun manuelt.
- **Varmepumpen** startes og stoppes manuelt (`cmd_vp`). P3 kører sammen med den. Den lader tanken med højst 65 °C fremløb og stopper, når tankens bund er 58 °C.
- **Brændefyret** fyres op manuelt (`cmd_fyr_op`) og lader tanken via Laddomat og P4 op til ca. 90 °C.
- **Pillefyret** er i drift i mode 1 og 2 og varmer husets vand direkte med fremløb STF_SP + 5 (højst `sp_pille`).
- **Rørene** på tegningen bindes til kredsdelens flow-flag (`F_HUS`, `F_PILLE`, `F_TANK`, `F_BYPASS`, `PS2` …), så strømningen følger den aktive mode.

## Indlæsning

```bash
bash demo/varme-plc/test/run.sh                                   # først: PC-test (kræver g++ og ../HypervisionPLC)
PLC_USER=admin PLC_PASS=... python demo/varme-plc/load.py http://<plc-ip>
PLC_USER=admin PLC_PASS=... python demo/varme-plc/load.py http://<plc-ip> --check   # kun status
PLC_USER=admin PLC_PASS=... python demo/varme-plc/load.py http://<plc-ip> --only=3  # kun Logic3 (resten og GLOBAL_VAR bevares)
```

Kræver en PLC **med PSRAM**. Demoen fylder ca. 18 KB, og kildepuljen er 64 KB med PSRAM, men kun 8 KB uden. Alle fire programmer kører med et interval på 500 ms. Fysikken regner med `dt = 0,5 s × sp_speed`, så intervallet skal stå på 500 ms.

## Opsætning af SCADA'en

```bash
SCADA_USER=... SCADA_PASS=... PLC_USER=... PLC_PASS=... python demo/varme-plc/scada_setup.py https://<scada> --cafile=<cert.pem> [--plc=http://<plc-ip>] [--drawing=varme] [--dry-run=ny.svg] [--only-configs]
```

Scriptet opretter PLC'en (nøgle `demo`) og alle tags, lægger betjeningspanelet nederst på tegningen (ny version, udgives) og sætter alle symboler op. Det kan køres igen: tidligere paneler fjernes først. Panelet kendes på sin baggrund, fordi serveren fjerner kommentarer ved gem. `--dry-run` skriver kun den nye SVG til en fil. `--only-configs` lader tegningen være og opdaterer kun PLC, tags og symbolopsætninger. Panelets symboler kommer fra `syms.json`, som genereres fra frontendens symbolbibliotek med `tools/symgen.ts` (se filens top). Adgangskoder angives kun som miljøvariabler.

## Variable til SCADA (tag-kind `logic`)

Navnene svarer til felterne på tegningen. **Fed** = skrivbar fra SCADA.

| Tegning | Program | Variabel | Enhed / værdier |
|---|---|---|---|
| SMS | 1 | `SMS_TXT` (tekst), `SMS` (kode) | Hus + pille · Hus + pille + tank · Hus + tank · TRYKSTOP. Koder: 1-3 = mode, 10 trykstop |
| Omskifter 1 | 1 | **`cmd_mode`** | 0 Auto · 1 M1 · 2 M2 · 3 M3 (manuel mode) |
| — | 1 | `MODE`, `TANK_IND` | Aktiv mode (1-3). Auto: tanken er koblet ind |
| — | 1 | `F_HUS`, `F_PILLE`, `F_TANK`, `F_BYPASS` | Flow i kredsdelene (til rørene) |
| Varmepumpe | 1 | **`cmd_vp`** | TRUE = varmepumpen startet (manuelt) |
| PS1–PS4 | 1 | `PS1` … `PS4` | BOOL, pumpen kører |
| Alarmer | 1 | `AL_P1`…`AL_P4`, `AL_VP`, `AL_PILLE`, `AL_TRYK_LAV`, `AL_TRYK_HOEJ`, `AL_FF_TEMP`, `AL_TANK_KOLD`, `ALARMER` (antal) | Pumpe-, VP- og pillefejl er låst, indtil de kvitteres. `AL_TANK_KOLD`: manuel mode 3, men tanken er mere end 5 °C under fremløbssetpunktet |
| — | 1 | **`cmd_kvitter`** | TRUE = kvittér (nulstilles af PLC'en) |
| — | 1 | **`sp_rum`** 21, **`sp_kurve`** 1,0, **`sp_stf_max`** 55, **`sp_tank_ind`** 60, **`sp_tank_ud`** 45, **`sp_vp_min`** −5 | °C |
| — | 1 | `STF_SP` | Beregnet fremløbssetpunkt, °C |
| FFTF / FFTR | 2 | `FFTF`, `FFTR` | °C |
| FFS | 4 | `FFS_TXT` | Slukket · Optænding · Drift · Overtemp |
| Fyr Fast | 2 | **`cmd_fyr_op`** | TRUE = læg 15 kg brænde i (højst 30 kg) |
| Laddomat | 2 | `LADDOMAT`, `FF_KW`, `FF_KG` | Åbner ved 72 °C |
| PFTF / PFTR | 2 | `PFTF`, `PFTR` | °C |
| Pille Status | 2 | `PILLE_TXT`, `PILLE_ST` | Stop · Tænding · Drift · Udbrænding · Fejl |
| — | 2 | `PILLE_KW`, `PILLE_KG`, `PILLE_STARTS`, **`sp_pille`** 75 | `sp_pille` = højeste fremløb |
| Energi | 2 / 4 | `E_FF`, `E_PILLE` (L2), `E_VP`, `E_VP_EL` (L4) | kWh, tæller op |
| ATT1–ATT6 | 3 | `ATT1` … `ATT6` | °C, top → bund |
| TS | 3 | `TS` | Tankens ladning i % (30–80 °C) |
| ATF | 3 | `ATF` | Fremløb fra tankens top, °C |
| STF / STR | 3 | `STF`, `STR` | Husets frem- og returløb, °C |
| FMTR | 3 | `FMTR` | L/min |
| MVS1 / MVS2 | 3 | `MVS1_TXT`, `MVS2_TXT`, `MVS1_POS`, `MVS2_POS` | AB-A · Kører · AB-B; position 0–100 % |
| Håndbetjening MVS1 / MVS2 | 3 | **`cmd_mvs1`, `cmd_mvs2`** | 0 = Auto (styringen), 1 = AB-A, 2 = AB-B — gælder i alle driftsformer (som håndbetjening på motoren); klik på ventilen i SCADA |
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

- **Auto, kold tank:** mode 1. Pillefyret varmer huset, og tanken er uden for kredsen.
- **Varmepumpe til:** Tanken lades til ca. 65 °C. Ved 60 °C kobler Auto tanken ind (mode 3): M1 og M2 kører til AB-B på 30 s, P2 overtager fra P1, og pillefyret går i stå. Når tanken er afladet til 45 °C, går Auto tilbage til mode 1.
- **Fyr op:** Brændefyret lader tanken via Laddomat og P4 op til ca. 90 °C, og Auto kobler tanken ind.
- **Manuel mode 2:** Returvandet forvarmes i tanken, og pillefyret varmer det sidste op.
- **Vinternat:** Varmepumpen er blokeret, og pillefyret holder huset på 21 °C.
- **Lækage:** Trykket falder, så alarmen for lavt tryk kommer ved 1,0 bar og trykstop ved 0,6 bar. *Efterfyld* genopretter.
- **Pumpefejl P1:** Alarmen kommer efter 10 s og er låst, indtil der kvitteres.
- **`f_P4` + fyr op:** Overtemperatur, så damp og tryk stiger, og sikkerhedsventilen åbner og tømmer anlægget. Bagefter giver det lavt tryk og kræver efterfyldning.
- **`f_pille`:** Pillefyret tænder ikke, og efter 10 min kommer `AL_PILLE`. **`f_vp`:** `AL_VP`, og pillefyret overtager.

## Firmware-forhold fundet under udviklingen (HypervisionPLC v7.9.68)

- **Højst 512 AST-noder pr. program.** Det er puljen i `st_parser.cpp` ved monolitisk kompilering. Testen måler forbruget. I dag ligger programmerne på 356, 441, 482 og 372 noder.
- **Strengkonstanter tælles pr. forekomst** (højst 8 pr. program), ikke pr. forskellig tekst.
- **En STRING-variabels startværdi (`:= 'x'`) sættes ikke.** Tildel den i koden i stedet.
- **Fejl: negative startværdier i VAR (`:= -5.0`, `:= -7`) bliver til 0.** Den er meldt til PLC-projektet. Her sættes `sp_vp_min` ved første scan i stedet.
- **Ingen bitvise operatorer på INT** (`AND`/`XOR`/`NOT` kræver BOOL). Brug `BIT_TST`/`BIT_SET`.
- **Fejl: CASE med flere værdier i samme gren (`4, 6:`) rammer ingen af værdierne.** Den er meldt til PLC-projektet. Her er den omgået med en hjælpevariabel.
