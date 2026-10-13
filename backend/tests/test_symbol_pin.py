"""Symbolstandard fase 7: nøglelåsens kode — sæt/skift/fjern (skriv-kun), nulstilling af spærring, rettigheder,
og at koden aldrig findes i svar, log, audit eller backup (CLAUDE.md regel 6)."""

import json
import logging

from tests.test_symbol_operate import V1, _op, _set_bits, _setup, _wait, api  # noqa: F401 (fixture)
from tests.test_symbols import dec_bin

LOCKED = {"positions": [False] * 5 + [True, False], "leave": False}


def _pin(api, pin=None, element=V1):
    url = f"/api/drawings/{api.did}/symbols/{element}/pin"
    return api.put(url, json={"pin": pin}) if pin is not None else api.delete(url)


def test_set_change_and_clear_pin(api, mock_plc, caplog):
    caplog.set_level(logging.DEBUG)
    _set_bits(mock_plc, 1)
    _setup(api, mock_plc, dec_bin(display="remote", lock=LOCKED), pin="1357")
    assert _pin(api).status_code == 200                             # (som efter en restore: låst uden kode)
    assert _op(api, 5).status_code == 409
    r = _pin(api, "4711")
    assert r.status_code == 200 and r.json() == {"element": V1, "has_pin": True}
    assert api.get(f"/api/drawings/{api.did}/symbols/{V1}/config").json()["has_pin"] is True
    assert _op(api, 5, "4711").status_code == 200
    # Skift: den gamle kode virker ikke længere
    assert _pin(api, "8080").status_code == 200
    assert _op(api, 1).status_code == 200
    assert _op(api, 5, "4711").status_code == 403
    assert _op(api, 5, "8080").status_code == 200
    # Fjern: låst position kan ikke vælges før en ny kode er sat (sikker standard)
    r = _pin(api)
    assert r.status_code == 200 and r.json()["has_pin"] is False
    assert _op(api, 1).status_code == 200
    r = _op(api, 5, "8080")
    assert r.status_code == 409 and "en tekniker skal sætte en kode" in r.json()["error"]
    assert _pin(api).status_code == 404                             # ingen kode at fjerne
    log = api.get("/api/audit?limit=100").json()
    actions = [e["action"] for e in log]
    assert actions.count("symbol.pin_set") == 3 and actions.count("symbol.pin_cleared") == 2   # inkl. opsætningen
    everything = json.dumps(log) + caplog.text + json.dumps(api.get("/api/backup").json())
    assert "4711" not in everything and "8080" not in everything and "1357" not in everything


def test_new_pin_lifts_lockout(api, mock_plc):
    _set_bits(mock_plc, 1)
    _setup(api, mock_plc, dec_bin(display="remote", lock=LOCKED), pin="4711")
    for wrong in ("0000", "1111", "2222"):
        _op(api, 5, wrong)
    assert _op(api, 5, "4711").status_code == 429
    assert _pin(api, "4711").status_code == 200                     # teknikeren sætter koden igen
    assert _op(api, 5, "4711").status_code == 200


def test_pin_rules(api, mock_plc):
    _setup(api, mock_plc, dec_bin(display="remote", lock=LOCKED), pin="1357")
    for bad in ("123", "12345", "abcd", " 1234", ""):
        r = _pin(api, bad)
        assert r.status_code in (400, 422) and r.status_code != 200, bad
    # Kun symboler med en konfiguration kan få en kode
    assert api.delete(f"/api/drawings/{api.did}/symbols/{V1}/config").status_code == 204
    r = _pin(api, "1234")
    assert r.status_code == 404 and "opsæt symbolet" in r.json()["error"]
    # og en fjernet konfiguration tager koden med
    assert api.put(f"/api/drawings/{api.did}/symbols/{V1}/config",
                   json={"config": dec_bin(lock=LOCKED), "pin": "1234"}).status_code == 200
    assert api.delete(f"/api/drawings/{api.did}/symbols/{V1}/config").status_code == 204
    assert api.put(f"/api/drawings/{api.did}/symbols/{V1}/config", json={"config": dec_bin()}).status_code == 200
    assert api.get(f"/api/drawings/{api.did}/symbols/{V1}/config").json()["has_pin"] is False


def test_only_engineers_set_or_clear_pin(api, mock_plc):
    _setup(api, mock_plc, dec_bin(display="remote", lock=LOCKED), pin="4711")
    api.post("/api/users", json={"username": "op", "role": "operator", "password": "Hemmelig-123"})
    api.post("/api/auth/login", json={"username": "op", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert _pin(api, "0000").status_code == 403
    assert _pin(api).status_code == 403
    assert _wait(lambda: True)


def test_pin_must_be_exactly_four_ascii_digits(api, mock_plc):
    _setup(api, mock_plc, dec_bin(display="remote", lock=LOCKED), pin="1357")
    for bad in ("1234\n", "١٢٣٤"):
        assert _pin(api, bad).status_code == 400, repr(bad)
    r = api.put(f"/api/drawings/{api.did}/symbols/{V1}/config", json={"config": dec_bin(lock=LOCKED), "pin": "1234\n"})
    assert r.status_code == 400
