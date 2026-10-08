# Bugs

Format: `[status] vX.X.X — beskrivelse`
Status: `open` | `investigating` | `fixed`

---

- [fixed] v0.6.0 — Forældreløse bindinger (element forsvundet i ny tegningsversion) kunne ikke fjernes: `PUT /bindings/{element}` afviste alle elementer der ikke findes i den aktive version — også en tom liste. **Løsning:** tom liste (= fjern) tilladt for ethvert element; ikke-tomme lister kræver stadig at elementet findes. Test tilføjet.
- [fixed] v0.6.0 — Binding-editor viste aldrig "er gemt": efter gem genindlæses tegningen og elementet vælges igen, hvilket nulstillede beskeden. Fundet ved visuel test før release. **Løsning:** beskeden sættes efter genindlæsningen.
- [fixed] v0.3.0 — `/ws/live` gav 404 under rigtig uvicorn: `uvicorn` uden `[standard]` har intet WebSocket-bibliotek og afviser upgrade-forespørgsler ("Unsupported upgrade request"). FastAPI's TestClient fangede det ikke. Fundet ved visuel verifikation før release. **Løsning:** `websockets` tilføjet til `requirements.txt` + regressionstest der kører WebSocket mod en rigtig uvicorn-server (`test_websocket_works_under_real_uvicorn`).
