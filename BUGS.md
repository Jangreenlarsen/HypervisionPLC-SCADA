# Bugs

Format: `[status] vX.X.X — beskrivelse`
Status: `open` | `investigating` | `fixed`

---

- [investigating] v0.7.0 — Langsom opdatering mod den rigtige PLC (rapporteret af Jan): SSE-watch-listen blev sendt URL-kodet (`coils=0%2C1%2C2`); PLC'en afkoder ikke query-strengen og overvågede kun den første adresse pr. type (`"watching":{"coils":1}`), mens SCADA'en antog at alle var dækket og kun pollede dem hvert 2. s. ST-variabler blev ligeledes kun pollet hvert 2. s, når SSE var sund. Desuden accepterer PLC'ens SSE kun HR/IR 0-159.
- [fixed] v0.7.0 — Binding-editor: når en ny binding blev skiftet til "Klik: til/fra", blev standarden "bed om bekræftelse" ikke slået til (formularen beholdt standarden fra den oprindelige animationstype) — klik på Overview skiftede derfor uden bekræftelse. Fundet ved visuel test før release. **Løsning:** standardværdier for klik-typer sættes når animationstypen skiftes.
- [fixed] v0.7.0 — Til/fra-klik blev logget som `write` i audit-loggen, så filteret "Til/fra" kun viste fejlede forsøg. **Løsning:** logges som `toggle`; test tilføjet.
- [fixed] v0.6.0 — Forældreløse bindinger (element forsvundet i ny tegningsversion) kunne ikke fjernes: `PUT /bindings/{element}` afviste alle elementer der ikke findes i den aktive version — også en tom liste. **Løsning:** tom liste (= fjern) tilladt for ethvert element; ikke-tomme lister kræver stadig at elementet findes. Test tilføjet.
- [fixed] v0.6.0 — Binding-editor viste aldrig "er gemt": efter gem genindlæses tegningen og elementet vælges igen, hvilket nulstillede beskeden. Fundet ved visuel test før release. **Løsning:** beskeden sættes efter genindlæsningen.
- [fixed] v0.3.0 — `/ws/live` gav 404 under rigtig uvicorn: `uvicorn` uden `[standard]` har intet WebSocket-bibliotek og afviser upgrade-forespørgsler ("Unsupported upgrade request"). FastAPI's TestClient fangede det ikke. Fundet ved visuel verifikation før release. **Løsning:** `websockets` tilføjet til `requirements.txt` + regressionstest der kører WebSocket mod en rigtig uvicorn-server (`test_websocket_works_under_real_uvicorn`).
