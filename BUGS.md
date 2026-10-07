# Bugs

Format: `[status] vX.X.X — beskrivelse`
Status: `open` | `investigating` | `fixed`

---

- [fixed] v0.3.0 — `/ws/live` gav 404 under rigtig uvicorn: `uvicorn` uden `[standard]` har intet WebSocket-bibliotek og afviser upgrade-forespørgsler ("Unsupported upgrade request"). FastAPI's TestClient fangede det ikke. Fundet ved visuel verifikation før release. **Løsning:** `websockets` tilføjet til `requirements.txt` + regressionstest der kører WebSocket mod en rigtig uvicorn-server (`test_websocket_works_under_real_uvicorn`).
