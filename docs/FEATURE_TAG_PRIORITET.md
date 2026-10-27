# Feature: prioritet pr. tag (høj / normal)

**Status:** SCADA-delen færdig i v2.0.0 (27.10.2026); afventer PLC FEAT-515 for effekten · **Ønsket af:** Jan, 2026-10-27 · **Afhænger af:** HypervisionPLC-firmware **v7.9.68.156** eller nyere (FEAT-515, færdig 2026-10-27, kører på 10.1.1.30)

## Baggrund

Fra PLC-firmware **v7.9.68.155** (FEAT-514) står alle læsninger, der kommer ind via `GET /api/ext/rtu|mbx/...`, **bag PLC'ens egne** i PLC'ens Modbus-køer. Det gælder både RS485-køen og expansion-board-køen. Formålet er, at SCADA's polling ikke forsinker ST-programmernes læsninger.

| Prioritet i PLC'ens kø | Hvad |
|---|---|
| 0 (højest) | Skrivninger fra ST og fra SCADA. Et nødstop fra SCADA kommer altid først. |
| 1 | ST: første læsning af et register |
| 2 | ST: opfriskning af en kendt værdi |
| 3 (lavest) | SCADA-læsninger. Fortrænges først ved fuld kø og rykkes op til 2 efter 5 s i kø. |

Det er det rigtige for de fleste tags. Nogle tags skal SCADA dog have hurtigt, fx tilbagemelding fra et nødstop, sikkerhedsrelæer eller en kritisk alarm-status. Dem skal man kunne markere som **høj prioritet**, så PLC'en behandler dem som sine egne læsninger.

**Skrivninger kræver ingen ændring.** De har allerede højeste prioritet i PLC'en.

**Interne PLC-registre** (`plcN:hr:...`, bulk-læsning via `/api/registers`) berøres ikke. De læses direkte fra PLC'ens hukommelse og går ikke gennem nogen Modbus-kø. Prioriteten har kun betydning for tags med kilde `rtu` eller `mbx`.

## Kontrakt mod PLC'en

```
GET /api/ext/rtu/{slave}/{type}/{addr}?count=N&max_age=ms&prio=high
GET /api/ext/mbx/{board}/{kanal}/{slave}/{type}/{addr}?count=N&max_age=ms&prio=high
```

- `prio=high`: læsningen køes med PLC'ens normale prioritet (1/2) i stedet for 3.
- `prio` udeladt eller `prio=normal`: som i dag (prioritet 3).
- En ugyldig værdi (andet end `high`/`normal`) giver HTTP 400.
- PLC-firmware før v7.9.68.156 ignorerer parameteren, så den kan sendes til alle PLC'er. Der virker den bare ikke.

## Ønsket funktionalitet i SCADA

1. **Tag-felt `priority`**: `normal` (standard) eller `high`.
   - DB-migrering: nyt felt, eksisterende tags får `normal`.
   - Med i API-modellerne (`routes.py`, opret/ret tag), i backup/restore og i tag-import (import giver `normal`).
2. **Tags-siden**: valget *Prioritet: Normal / Høj* i redigeringspanelet.
   - Kun aktivt for tags med kilde *Extern* (`rtu`) eller *Expansion board* (`mbx`). For interne tags vises det nedtonet med forklaringen "kun for eksterne Modbus-tags".
   - Gerne en kolonne eller et filter, så man kan se, hvilke tags der står som høj.
3. **Poll-planlæggeren** (`plc_runtime.py`, `_ext_plan`):
   - Prioriteten indgår i gruppenøglen, så høje og normale tags ikke slås sammen i samme område (`count`). Ellers ville ét højt tag løfte op til 16 normale registre med op.
   - Høje områder polles først i hver runde.
4. **PLC-klienten** (`client.py`, `read_ext`): nyt argument `prio: str | None`, som sendes som query-parameter `prio=high`, når tagget er højt.
5. **Mock-PLC**: accepterer `prio` (og ignorerer det).
6. **Hjælpetekst** i UI'et: "Høj prioritet bruges kun til få, vigtige tags (fx nødstop-tilbagemelding). Står mange tags på høj, forsvinder effekten, og PLC'ens egne programmer kan blive forsinket."

## Acceptkriterier

- Et tag kan sættes til høj eller normal og bevares gennem gem, backup og restore.
- Høje eksterne tags sendes med `prio=high`, normale uden.
- Høje og normale tags deles aldrig i samme `/api/ext`-kald.
- Interne tags er upåvirkede, og valget er låst for dem.
- Tests i `backend/tests/test_ext.py` dækker parameteren og opdelingen af områder.
- Uændret adfærd mod PLC'er med ældre firmware.

## PLC-siden (HypervisionPLC)

FEAT-515 er færdig i v7.9.68.156 (PLC-commit `eea20a7`): `GET /api/ext/...` læser `prio`, og `high` giver PLC'ens egen kø-prioritet. Testet på 10.1.1.30 med `prio=high`, `prio=normal`, udeladt (alle 200) og en ugyldig værdi (400).
