# Demo-PLC: brøndstation med klordosering

En HypervisionPLC uden fysisk I/O, der opfører sig som en lille brøndstation med flow-proportional klordosering. Forlægget er Guelph Emma Well (Nasby, ISA WWID 2020): brøndpumpe, hypoklorit-dosering efter flow, kontakttank med klor-analysatorer før og efter, og en skylleventil, der spuler kontakttanken før start. Alle tal (grænser, tider, størrelser) er vores antagelser, ikke fra kilden. Analyse og baggrund: [docs/ANALYSE_VANDVAERK.md](../../docs/ANALYSE_VANDVAERK.md).

SCADA læser og skriver programvariablerne over PLC'ens REST API; tagsene oprettes som kilde `logic:<nr>:<navn>`.

| Fil | Indhold |
|---|---|
| `globals.st` | 17 `GLOBAL_VAR` mellem styring og proces |
| `logic2_styring.st` | **Logic2, styring**: driftsform, startsekvens, stop, tilladelser, interlocks, alarmer, flow-proportional dosering med trim |
| `logic3_proces.st` | **Logic3, proces**: brønd, brøndpumpe, skylleventil, hypotank og doseringspumpe, højdebeholder, forbrug, klor (AT1/AT2, kontakttank, CT), klokke, tidsfaktor, scenarier |
| `load.py` | Indlæser det hele på PLC'en. Rører kun Logic2-3 og GLOBAL_VAR; Logic1 og Logic4 står |
| `test/run.sh` | PC-test med PLC'ens egen ST-compiler og VM (`test/vw_test.cpp`) |

Kræver PLC-firmware 7.9.68.168 eller nyere (64 globale variable, 16 timere, 2048 AST-noder, DINT/REAL uden startværdi). Logic2: 574 noder, 53 variable. Logic3: 364 noder, 38 variable.

## Anlægget

```
Brønd (LT) → Brøndpumpe P1 (FT, PT) → hypo-indsprøjtning (P2) → Kontakttank (AT1 før, AT2 efter) → Højdebeholder → Forbrug
                        Skylleventil XV1 (spuler kontakttanken før start)      Hypotank (LT) → P2
```

| Del | Størrelse |
|---|---|
| Brøndpumpe P1 | 35 l/s, 10 s opstart, 6 s nedkøring |
| Brønd | tilstrømning 70 l/s × (10 − niveau) / 10, 3 m² (niveau 0-10 m); lavt 2 m, lav-lav 1 m |
| Skylleventil XV1 | 8 s gangtid |
| Hypotank / doseringspumpe P2 | 50 l (12 % NaOCl = 120 g/l) / 0-5 l/t |
| Kontakttank | 40 m³, 1. ordens forsinkelse med V/flow (ca. 19 min ved 35 l/s), nedbrydning 5·10⁻⁵ /s |
| Højdebeholder | 300 m³ |
| Forbrug | 20 l/s i middel, 1 ± 0,6 over døgnet (spids kl. 15) |
| Døgnmængde | loft 2400 m³ (tilladelsen), advarsel ved 2160 m³; nulstilles ved midnat |

**Dosering:** `l/t = flow l/s × dosis mg/l × 3600 / 120.000`. Ved 35 l/s og 1,0 mg/l er det 1,05 l/t (21 % af pumpen). Trim: dosis = setpunkt + 0,5 × (mål-residual − AT2), 0,2-3,0 mg/l, når trim er slået til, analysatoren er gyldig og doseringen har kørt i 15 min (simuleret tid).

**Klor:** doseret koncentration = P2-flow × 120.000 / flow (mg/l). AT1 følger den (20 s). AT2 er AT1 efter kontakttanken. CT = AT2 × kontakttid (mg·min/l).

**Tid:** tidsfaktor `VW_SPEED` (1-120, standard 10). Klokken starter kl. 6.00. Interlock-tider for klor og trin kører i simuleret tid; hardwaretider (intet flow, doseringsfejl) kører i rigtig tid.

## Styring (Logic2)

`VW_MODE`: 0 Fra, 1 Auto, 2 Manuel.

**Auto:** `VW_SP_START` (40 %) og `VW_SP_STOP` (85 %) på højdebeholderen giver et ønske om drift med hysterese. Startsekvensen:

| Trin (`VW_TRIN`) | Hvad sker | Videre når |
|---|---|---|
| 1 Skyl | XV1 åbner | åben og 30 s |
| 2 Pumpe | XV1 lukker, P1 starter | flow ≥ 20 l/s og 15 s |
| 3 Dosering | P2 starter | P2 kører og 10 s |
| 4 Drift | | ønsket drift ophører, eller tilladelse forsvinder |
| 5 Stop | P2 stopper, efter 10 s P1 | 20 s |

**Tilladelser:** til start: brøndniveau ≥ 3 m, hypotank ≥ 10 %, ingen pumpefejl, døgnmængde < 2400 m³, ikke i trip. For at blive ved: brøndniveau ≥ 1,5 m, hypotank ≥ 5 %, beholder < 97 %, døgnmængde < 2400 m³.

**Manuel:** `VW_MAN_P1`, `VW_MAN_P2`, `VW_MAN_XV1`. Interlocks gælder: P1 kræver brøndniveau ≥ 1,5 m og ingen fejl, P2 kræver kørende P1 og hypotank ≥ 3 %, XV1 kan ikke åbnes, mens P1 kører.

**Trip** (stopper alt og låser til `VW_KVIT`, hvis årsagen er væk): `VW_TRIP`: 1 brønd lav-lav, 2 hypo tom eller doseringsfejl, 3 klor for højt (> `VW_SP_HOEJ` i 30 s) eller for lavt (< `VW_SP_LAV` i 600 s, først efter 15 min dosering), 4 pumpefejl eller intet flow (20 s). Klor-trips er spærret ved analysatorfejl (AT2 = -1).

**Status** `VW_STATUS`: 0 Stoppet, 1 Starter, 2 Drift, 3 Stopper, 4 Trip.

## Scenarier og fejl (Logic3)

| Tag | Virkning |
|---|---|
| `VW_SCEN` 0 | Normal |
| `VW_SCEN` 1 | Brøndpumpe fejl: P1 kan ikke køre, trip 4 under drift |
| `VW_SCEN` 2 | Hypotank tom (trykkes til 2 %): trip 2 under drift, ingen start. Vælg 0 og tryk `VW_FYLD` |
| `VW_SCEN` 3 | Høj efterspørgsel (2,5 ×): beholderen tømmes, døgnloftet kan stoppe pumpen |
| `VW_SCEN` 4 | Overdosering (4 ×): AT2 stiger, trip 3 |
| `VW_F_AN` | Analysatorfejl: AT2 = -1, alarm, ingen klor-trip |
| `VW_F_P2` | Doseringspumpe fejl: P2 leverer ikke, trip 2 under drift |
| `VW_F_LAV` | Lav grundvandsstand: tilstrømning 30 %, brønden tømmes |

## Tags

Skrivbare (S) og læsbare (L). Tagget oprettes som kilde `logic:2:<navn>` (styring) eller `logic:3:<navn>` (proces).

**Logic2, styring**

| Tag | Type | Skriv | Hvad |
|---|---|---|---|
| `VW_MODE` | INT | S | 0 Fra, 1 Auto, 2 Manuel |
| `VW_KVIT` | BOOL | S (puls) | Kvittér trip |
| `VW_MAN_P1`, `VW_MAN_P2`, `VW_MAN_XV1` | BOOL | S | Manuel betjening |
| `VW_SP_START`, `VW_SP_STOP` | REAL | S | Start-/stopniveau i højdebeholderen (%) |
| `VW_SP_DOSE`, `VW_SP_RES` | REAL | S | Dosis (mg/l) og mål-residual efter kontakttank (mg/l) |
| `VW_TRIM` | BOOL | S | Trim fra analysatoren |
| `VW_SP_LAV`, `VW_SP_HOEJ` | REAL | S | Klorgrænser (mg/l) |
| `VW_STATUS`, `VW_TRIN`, `VW_TRIP` | INT | L | Status, trin 0-5, tripårsag 0-4 |
| `VW_KOM_P1`, `VW_KOM_P2`, `VW_KOM_XV1` | BOOL | L | Kommandoer til udstyret |
| `VW_DOSIS_EFF`, `VW_P2_PCT` | REAL | L | Effektiv dosis (mg/l), doseringspumpens ydelse (%) |
| `VW_ALARMER` | INT | L | Antal aktive alarmer |
| `VW_AL_BROND`, `VW_AL_BROND_LL`, `VW_AL_HYPO`, `VW_AL_HYPO_TOM`, `VW_AL_KLOR_LAV`, `VW_AL_KLOR_HOEJ`, `VW_AL_P1`, `VW_AL_P2`, `VW_AL_FLOW`, `VW_AL_DOEGN`, `VW_AL_AN`, `VW_AL_BEH_LAV`, `VW_AL_BEH_HOEJ`, `VW_AL_TRIP` | BOOL | L | Alarmer (se nedenfor) |

**Logic3, proces**

| Tag | Type | Skriv | Hvad |
|---|---|---|---|
| `VW_SPEED` | REAL | S | Tidsfaktor 1-120 |
| `VW_SCEN` | INT | S | Scenarie 0-4 |
| `VW_F_AN`, `VW_F_P2`, `VW_F_LAV` | BOOL | S | Fejl der kan kombineres |
| `VW_FYLD` | BOOL | S (puls) | Fyld hypotanken |
| `VW_KLOKKE` | REAL | L | Klokken 0-24 |
| `VW_BROND` | REAL | L | Brøndniveau (m) |
| `VW_Q` | REAL | L | Flow (l/s) |
| `VW_TRYK` | REAL | L | Tryk efter pumpen (bar) |
| `VW_P1_FB`, `VW_P2_FB` | BOOL | L | P1 og P2 kører |
| `VW_XV1_AABEN`, `VW_XV1_LUKKET`, `VW_XV1_POS` | BOOL, BOOL, REAL | L | Skylleventil (positionen 0-100 %) |
| `VW_HYPO` | REAL | L | Hypotank (%) |
| `VW_P2_LH` | REAL | L | Doseret hypo (l/t) |
| `VW_BEH`, `VW_BEHOV` | REAL | L | Højdebeholder (%), forbrug (l/s) |
| `VW_DOEGN` | REAL | L | Døgnmængde (m³) |
| `VW_DOSE`, `VW_AT1`, `VW_AT2` | REAL | L | Doseret klor, klor efter indsprøjtning, klor efter kontakttank (mg/l; AT2 = -1 ved analysatorfejl) |
| `VW_TKONT`, `VW_CT` | REAL | L | Kontakttid (min), CT (mg·min/l) |

**Alarmer** (klasse efter Winnipeg-modellen: 1 straks, 2 dagtid, 3 ingen udkald)

| Tag | Betingelse | Klasse |
|---|---|---|
| `VW_AL_BROND_LL` | brøndniveau < 1,0 m | 1 |
| `VW_AL_BROND` | brøndniveau < 2,0 m | 2 |
| `VW_AL_HYPO_TOM` | hypotank < 3 % | 1 |
| `VW_AL_HYPO` | hypotank < 15 % | 2 |
| `VW_AL_KLOR_HOEJ` | AT2 > grænsen | 1 |
| `VW_AL_KLOR_LAV` | AT2 < grænsen i 120 s | 1 |
| `VW_AL_P1`, `VW_AL_P2` | pumpefejl | 1 |
| `VW_AL_FLOW` | P1 kommanderet uden flow i 10 s | 1 |
| `VW_AL_DOEGN` | døgnmængde > 2160 m³ | 2 |
| `VW_AL_AN` | analysatorfejl | 2 |
| `VW_AL_BEH_LAV` | beholder < 20 % | 2 |
| `VW_AL_BEH_HOEJ` | beholder > 95 % | 3 |
| `VW_AL_TRIP` | trip låst | 1 |

SCADA's tekst pr. værdi tillader højst 5 tekster, derfor har `VW_STATUS` 5 værdier og `VW_TRIP` er grupperet i 5 årsager (0-4).

## Brug

```bash
# PC-test (kræver g++ og PLC-repoet; sæt PLC_REPO, hvis det ikke ligger ved siden af)
PLC_REPO=C:/Projekter/HypervisionPLC bash demo/vandvaerk/test/run.sh

# Indlæs på PLC'en
PLC_USER=... PLC_PASS=... python demo/vandvaerk/load.py http://10.1.1.34 --check
PLC_USER=... PLC_PASS=... python demo/vandvaerk/load.py http://10.1.1.34
```

PC-testen kører Logic2-3 som PLC'en og tjekker: startsekvensen, 35 l/s, dosering (1,05 l/t), kontakttid og CT, stop ved stopniveau, et døgn i auto (flere cyklusser, døgnmængde under loftet, klor under grænsen), alle scenarier og fejl, trip og kvittering, manuelle interlocks, instruktionsloft og fysiske områder.
