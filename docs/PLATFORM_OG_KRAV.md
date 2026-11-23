# Platforme og krav

Opdateret 2026-11-23. SCADA-serveren er én systemd-service (Python/FastAPI) på **Debian 12/13 eller Raspberry Pi OS (64-bit)**. Den er **ikke bundet til en Raspberry Pi**: samme pakke og samme `install.sh` bruges på en Pi og i en Linux-VM. Al kommunikation med PLC'en sker fortsat kun via PLC'ens REST API, så serveren kan stå hvor som helst, der har netværk til PLC'en.

## Målplatforme

| Platform | Arkitektur | Hjælper (LLM) | Bemærkning |
|---|---|---|---|
| **Linux-VM, 16 GB RAM, 30 GB disk** (anbefalet) | x86_64 eller arm64 | ja: *Hurtig* og *Standard* anbefales (*Stor* er langsom på 4 vCPU og over hukommelsesloftet, se nedenfor) | Demoen (scada.laces.dk) er en VM med 15,7 GB RAM; målt 2026-11-23. Profilen *vm-16* |
| VM/PC med 8 GB RAM | x86_64 / arm64 | ja, *Hurtig* og *Standard* | Profilen *vm-8* |
| VM/PC med 32 GB RAM eller mere | x86_64 / arm64 | ja, alle modeller | Profilen *vm-32* |
| Raspberry Pi 5 (8-16 GB) | arm64 | ja, *Hurtig* og *Standard* | Kræver Raspberry Pi OS 13 "Trixie" eller nyere til hjælperen. Profilen *pi5* |
| Raspberry Pi 4 | arm64 | nej | SCADA'en kører fint; hjælperen er slået fra. Profilen *pi4* |
| Lille VM/PC (under 8 GB RAM) | x86_64 / arm64 | nej | Profilen *lille* |

Pi 5 er altså **ikke et krav**. Profilen foreslås automatisk ud fra maskinen (`backend/app/services/hwprofile.py`) og bekræftes under *System › Konfiguration*, eller sættes ved installation med `install.sh --hw <profil>`.

## VM med 16 GB RAM og 30 GB disk

**Minimum for SCADA'en alene (skøn, ikke målt):** 2 vCPU, 2 GB RAM, 8 GB disk. **Anbefalet med hjælperen:** 4 vCPU (8 til modellen *Stor*), 16 GB RAM, 30 GB disk, NTP, og et netværk med adgang til PLC'en (og til GitHub, hvis opdateringer hentes derfra).

### Hukommelse (profilen *vm-16*)

| Post | Omtrent |
|---|---|
| Loft for hjælperens model (`llm_mem_mb`) | 9.000 MB |
| Rest til styresystem, SCADA og filcache | ca. 6,7 GB |

Målt på demo-VM'en: 15,7 GB samlet og 10,3 GB tilgængelig under drift (2026-11-23).

**Modellerne mod loftet på 9000 MB** (Linux, kontekst 8192, målt 2026-11-23, se `docs/LLM_ANALYSE.md`, femte måling): *Hurtig* 2,7 GB og *Standard* 5,4 GB i spids holder sig under loftet; *Stor* (Ministral-3-8B) når 10,2 GB og Qwen3.5-9B 9,4 GB og overstiger det, og Gemma 4 12B når 12,6 GB. Loftet er et hårdt `MemoryMax` på tjenesten uden swap, så *Stor* hører hjemme på *vm-32* eller kræver et højere loft på *vm-16*. På demo-VM'en (4 vCPU) tog et svar fra Ministral 341 s.

### Disk (30 GB)

Målt på demoen: 20,2 GB disk, 7,8 GB brugt (styresystem, SCADA, data og installeret hjælper). Pakkerne er målt på de færdige filer.

| Post | Størrelse | Kilde |
|---|---|---|
| Modellen *Hurtig* (Qwen3.5-2B Q4_K_M) | 1,3 GB | `deploy/llm-models.json` |
| Modellen *Standard* (Qwen3.5-4B Q4_K_M) | 2,7 GB | samme |
| Modellen *Stor* (Ministral-3-8B Q4_K_M), kun *vm-16* og *vm-32* | 5,2 GB | samme |
| LLM-pakke til installation (tar) | 1,4 / 2,8 / 5,3 GB | `scada-llm-*.tar` |
| Opdateringspakke (OTA) | ca. 19 MB | `scada-<version>-b<build>.tar` |
| Sikkerhedskopier | 7 automatiske + 2 trend-kopier, ældre slettes | `backend/app/services/backup.py` |
| Trends | 30 dages opbevaring (demo: 34 MB) | `backend/app/services/trends.py` |

**Installation af en model:** `deploy/apply-llm.sh` kræver, ud over den uploadede pakke, plads til en kopi under udpakning, den gamle model, der først fjernes til sidst, og 1 GB luft. Efter uploadet skal der altså være ca. 11,5 GB fri for *Stor* (5,3 + 5,2 + 1) og ca. 6,5 GB for *Standard* (2,8 + 2,7 + 1); med selve pakken på disken er det samlet op til ca. 17 GB for *Stor* og ca. 9 GB for *Standard*. Med 30 GB disk og ca. 5-8 GB i brug er der plads til at skifte model, men ikke til at have *alle* modeller liggende ved siden af hinanden, hvis den ledige plads skal holde sig over advarselsgrænsen.

**Advarsler:** *Status* melder lav plads ved under 10 % eller 1 GB ledigt og fejl ved under 5 % eller 200 MB. På 30 GB betyder det, at der bør være **mindst 3 GB ledigt** i drift.

### Før en VM tages i brug

1. Installér Debian 12 eller 13 (server uden grafisk miljø), og kør `deploy/bootstrap.sh` eller `deploy/install.sh` (se README).
2. Kontrollér under *System › Konfiguration*, at profilen er *vm-16*, og under *Status*, at uret er synkroniseret og disken har mindst 3 GB ledigt.
3. Tag en backup (*System › Backup*), og kontrollér at den kan gendannes, før anlægget sættes i drift.
4. Kør en testbetjening og en alarm igennem fra en browser på det rigtige netværk.

## Hvad der ikke ændrer sig

- Kun SCADA-serveren taler med PLC'en; browsere taler kun med SCADA-serveren.
- `pytest` og `npm test` kører på udviklingsmaskinen (Windows 11); produktion er Debian/Linux.
- Selv på en VM skal ændringer, der rører systemd, rettigheder eller filstier, prøves i en systemd-service på en Linux-maskine, ikke kun i en lokal shell.
