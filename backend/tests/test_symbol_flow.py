"""Ind/ud-definitioner pr. symboltype (symbol_flow, v4.13.0): API, validering, rettigheder og backup."""

from tests.drawing_api import api  # noqa: F401 — fixture

# ------------------------------------------------------------------ symbol_flow

DEF = {"ports": [{"x": 0.1, "y": 0.5, "name": "A", "role": "both"}, {"x": 0.9, "y": 0.5, "name": "B", "role": "both"},
                 {"x": 0.5, "y": 1, "name": "AB", "role": "both", "common": True, "part": "port_ab"}],
       "ways": [["AB", "A"], ["AB", "B"]]}


def test_symbol_flow_crud_validation_and_audit(api):
    assert api.get("/api/symbol-flow").json() == {}
    r = api.put("/api/symbol-flow/trevejs_x", json=DEF)
    assert r.status_code == 200 and r.json()["ways"] == [["AB", "A"], ["AB", "B"]]
    assert api.get("/api/symbol-flow").json()["trevejs_x"]["ports"][2]["common"] is True
    bad = [
        {"ports": []},
        {"ports": [{"x": 2, "y": 0, "name": "A"}]},
        {"ports": [{"x": 0, "y": 0, "name": "A b"}]},
        {"ports": [{"x": 0, "y": 0, "name": "A"}, {"x": 1, "y": 1, "name": "A"}]},
        {"ports": [{"x": 0, "y": 0, "name": "A", "role": "midt"}]},
        {"ports": [{"x": 0, "y": 0, "name": "A"}], "ways": [["A", "X"]]},
        {"ports": [{"x": 0, "y": 0, "name": "A", "part": "../x"}]},
    ]
    for b in bad:
        assert api.put("/api/symbol-flow/trevejs_x", json=b).status_code == 400, b
    assert api.put("/api/symbol-flow/Ugyldig Type", json=DEF).status_code == 400
    assert api.delete("/api/symbol-flow/trevejs_x").status_code == 204
    assert api.get("/api/symbol-flow").json() == {}
    acts = [a["action"] for a in api.get("/api/audit?limit=30").json()]
    assert "symbol_flow.set" in acts and "symbol_flow.reset" in acts


def test_symbol_flow_needs_engineer_and_follows_the_backup(api):
    api.put("/api/symbol-flow/trevejs_x", json=DEF)
    backup = api.get("/api/backup").json()
    assert backup["symbol_flow"]["trevejs_x"]["ways"] == [["AB", "A"], ["AB", "B"]]
    api.delete("/api/symbol-flow/trevejs_x")
    assert api.post("/api/backup/restore", json=backup).status_code == 200
    assert "trevejs_x" in api.get("/api/symbol-flow").json()                     # gendannet
    old = {k: v for k, v in backup.items() if k != "symbol_flow"}                 # ældre backup: røres ikke
    assert api.post("/api/backup/restore", json=old).status_code == 200
    assert "trevejs_x" in api.get("/api/symbol-flow").json()
    broken = {**backup, "symbol_flow": {"trevejs_x": {"ports": [{"x": 5, "y": 0, "name": "A"}]}}}
    assert api.post("/api/backup/restore", json=broken).status_code == 400
    api.post("/api/users", json={"username": "op", "password": "Operator-pw-123", "role": "operator"})
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "op", "password": "Operator-pw-123"})
    assert api.get("/api/symbol-flow").status_code == 403
