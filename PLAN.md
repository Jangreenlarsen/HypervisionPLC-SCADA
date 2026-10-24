# Plan: Skriv ST-variabler via REST (PLC-firmware + SCADA)

Ønske (Jan, 2026-10-24): SCADA skal kunne skrive til ST-variabler (`plcN:logic:<prog>:<var>` og GLOBAL_VAR), ikke kun hr/coil. Valgt løsning: ret PLC-firmwaren (HypervisionPLC-projektet), så REST API'et kan skrive en variabel direkte, og variabelnavne over 15 tegn virker i API'et.

Fund: PLC'ens API har intet kald, der sætter en ST-variabel (kun upload/bind/debug), og navne gemmes i `char var_names[64][16]` (`include/st_types.h:694`) → højst 15 tegn (`system_styre_mode` → `system_styre_mo`).

## Del A — PLC-firmware (C:\Projekter\HypervisionPLC, følger dets egen CLAUDE.md/workflow, ny FEAT i BUGS_INDEX)
1. `POST /api/logic/{id}/var` — body `{"name":"…","value":…}` (CHECK_AUTH_WRITE). Finder variablen på navn, konverterer efter `var_types` (BOOL/INT/DINT/REAL …), afviser STRING (400), ukendt navn (404 + liste), ikke-kompileret program (409) og en variabel der er **bundet som input** fra et register (409: "skriv til HR N i stedet" — ellers overskrives den hver cyklus).
2. `POST /api/logic/globals/var` — samme for GLOBAL_VAR.
3. **Ingen race med ST-tasken:** skrivningen lægges i en lille kø pr. program (fx 8 pladser, beskyttet af mutex/spinlock) og anvendes af ST-tasken i starten af næste cyklus (`st_logic_execute_program`), før VM'en kører. Svar `{"status":"queued"}` (evt. `?wait=ms` til den er anvendt). Skrivningen logges i hændelsesloggen (som `/api/ext`-skrivninger).
4. **Navne > 15 tegn:** `var_names[...][16]` → `[32]` (+4 KB RAM for 4 programmer — tjekkes i build-output), bytecode-cachens format (16 → 32 byte pr. navn) og `ST_BYTECODE_VERSION` bumpes, så gamle `.bc` genkompileres ved boot.
5. Manual (B_REST_API_Reference + kap. 7/8), BUGS_INDEX, version efter projektets regler, `pio run` + `test/st_host/run.sh`.
6. Hardwaretest: kræver Jans OK + adgang til test-PLC'en (OTA via `POST /api/system/ota`) — eller Jan flasher selv.

## Del B — SCADA
7. `PlcClient.write_logic_var(program, name, value)` og `write_global(name, value)` (kun i `backend/app/plc/`).
8. `tags.py`: `logic` og `global` kan være skrivbare; `operate.write` får en gren for dem (skalering omvendt, bool/tal). Ældre firmware (404 på endpointet) giver en klar fejl: "PLC-firmwaren understøtter ikke skrivning til ST-variabler (kræver vX)".
9. Setpunkt, trykknap, positioner, ugeprogrammer bruger alle `operate.write` → virker automatisk; audit-log som før.
10. Mock-PLC: de to nye endpoints; tests (skriv, afvisninger, gammel firmware).

## Risici / bemærkninger
- En variabel, som programmet selv tildeler hver cyklus, kan ikke "holdes" udefra — skrivningen overskrives straks. Typisk brug er indstillings-/kommandovariabler (fx `system_styre_mode`), som programmet kun læser.
- Værdien er ikke persistent: efter genstart af PLC'en starter variablen igen på sin startværdi (som i dag).
- RAM på ESP32: +4 KB for navnene; skal holdes under budget (build viser forbrug).
- Firmware og SCADA versioneres hver for sig; SCADA skal tåle ældre firmware.
