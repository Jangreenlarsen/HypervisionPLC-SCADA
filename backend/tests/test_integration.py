"""Integrationer: API-nøgler (skriv-kun, kun kontrolsum gemt), nøgle-godkendelse, afgrænsning, hastighedsgrænse, læse-API og OpenAPI."""

import hashlib
import json
import secrets
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.integration import IntegrationService, hash_key
from app.services.metrics import render

ADMIN_PW = "test-admin-pw-1"
BASE = "/api/v1/integration"


def new_key() -> str:
    return "hv_" + secrets.token_urlsafe(32)          # 43 tegn


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def _wait(predicate, timeout=8.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


@pytest.fixture
def api(tmp_path, mock_plc):
    s = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9, frontend_dir=tmp_path / "nope",
                 admin_password=ADMIN_PW, backup_hours=0, alarm_tick_s=0.1, health_alarm_warmup_s=999.0, trend_flush_s=0.2)
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada", "password": "scada123", "sse_enabled": False})
        for body in ({"name": "kedel_temp", "source": "plc1:hr:5", "scale": 0.1, "unit": "°C", "description": "Kedeltemperatur", "decimals": 1,
                      "alarm_hh": 90, "alarm_h": 80, "alarm_deadband": 1, "trend": True, "trend_interval_s": 1},
                     {"name": "kedel_pumpe", "source": "plc1:coil:4", "description": "Pumpe"},
                     {"name": "tank_niveau", "source": "plc1:hr:6", "unit": "%", "description": "Tank"}):
            assert c.post("/api/tags", json=body).status_code == 201
        c.tmp, c.plc = tmp_path, mock_plc
        yield c


def make_key(api, name="node-red", scope=None, **extra):
    key = new_key()
    body = {"name": name, "key": key, "scope": scope or {"all": True}, **extra}
    r = api.post("/api/system/integration/keys", json=body)
    assert r.status_code == 201, r.text
    return key, r.json()


def anon(api):
    return TestClient(api.app)


def get(api, path, key, **kw):
    return anon(api).get(BASE + path, headers=bearer(key), **kw)


# ------------------------------------------------------------------ administration

def test_key_management_is_admin_only(api):
    api.post("/api/users", json={"username": "tek", "role": "engineer", "password": "Hemmelig-kode-12345"})
    eng = TestClient(api.app)
    eng.post("/api/auth/login", json={"username": "tek", "password": "Hemmelig-kode-12345"})
    eng.post("/api/auth/password", json={"old_password": "Hemmelig-kode-12345", "new_password": "Nyt-hemmeligt-kode-9876"})
    for method, path in (("get", "/keys"), ("post", "/keys"), ("patch", "/keys/k_x"), ("delete", "/keys/k_x")):
        assert getattr(eng, method)("/api/system/integration" + path).status_code == 403
        assert getattr(anon(api), method)("/api/system/integration" + path).status_code == 401


def test_key_is_write_only_only_the_hash_is_stored_and_nothing_leaks(api):
    key, created = make_key(api)
    assert key not in json.dumps(created) and "key_hash" not in created and created["prefix"] == key[:11]
    rows = api.app.state.integration_service.db.list_api_keys()
    assert len(rows) == 1 and rows[0]["key_hash"] == hashlib.sha256(key.encode()).hexdigest()
    assert key not in json.dumps(rows) and key[11:] not in json.dumps(rows)
    for text in (api.get("/api/system/integration/keys").text, api.get("/api/audit?limit=50").text):
        assert key not in text and "key_hash" not in text and rows[0]["key_hash"] not in text
    audit = api.get("/api/audit?limit=50").json()
    assert any(a["action"] == "integration.key.create" and a["target"] == "node-red" for a in audit)
    assert key not in (api.tmp / "scada.db").read_bytes().decode("latin-1")             # heller ikke i selve databasen


@pytest.mark.parametrize("patch, message", [
    ({"key": "kort"}, "hv_"), ({"key": "hv_" + "a" * 42}, "hv_"), ({"key": "hv_" + "a" * 44}, "hv_"), ({"key": "xx_" + "a" * 43}, "hv_"),
    ({"key": "hv_" + "a" * 42 + " "}, "hv_"),
    ({"name": "a"}, "Navnet"), ({"name": "-ugyldigt"}, "Navnet"), ({"name": "x" * 80}, "Navnet"), ({"name": "med;semikolon"}, "Navnet"),
    ({"scope": {"all": False}}, "mindst ét"), ({"scope": {"tags": ["findes_ikke"]}}, "Ukendte tags"),
    ({"scope": {"prefixes": ["har mellemrum"]}}, "præfiks"), ({"scope": {"prefixes": ["x" * 50]}}, "præfiks"),
    ({"ip_allow": ["ikke-en-ip"]}, "IP-adresse"), ({"ip_allow": ["10.0.0.1/99"]}, "IP-adresse"),
    ({"expires_at": time.time() - 10}, "fremtiden"), ({"expires_at": time.time() + 40 * 365 * 86400}, "langt ude"),
])
def test_create_validation(api, patch, message):
    body = {"name": "gyldigt navn", "key": new_key(), "scope": {"all": True}}
    body.update(patch)
    r = api.post("/api/system/integration/keys", json=body)
    assert r.status_code in (400, 422) and message in r.json()["error"], r.text
    assert api.get("/api/system/integration/keys").json() == []


def test_unknown_fields_are_rejected(api):
    r = api.post("/api/system/integration/keys", json={"name": "abc", "key": new_key(), "scope": {"all": True}, "role": "admin"})
    assert r.status_code == 422


def test_duplicate_name_and_duplicate_key_are_conflicts_and_max_keys_is_enforced(api):
    key, _ = make_key(api, "Min nøgle")
    r = api.post("/api/system/integration/keys", json={"name": "min NØGLE", "key": new_key(), "scope": {"all": True}})
    assert r.status_code == 409 and "findes allerede" in r.json()["error"]
    r = api.post("/api/system/integration/keys", json={"name": "anden", "key": key, "scope": {"all": True}})
    assert r.status_code == 409
    import app.services.integration as m
    api.app.state.integration_service.db.count_api_keys = lambda: m.MAX_KEYS       # fyldt op
    r = api.post("/api/system/integration/keys", json={"name": "en-mere", "key": new_key(), "scope": {"all": True}})
    assert r.status_code == 409 and "højst" in r.json()["error"]


def test_update_disable_rename_and_delete(api):
    key, k = make_key(api, "script", scope={"prefixes": ["kedel_"]})
    assert get(api, "/info", key).status_code == 200
    r = api.patch(f"/api/system/integration/keys/{k['id']}", json={"disabled": True})
    assert r.status_code == 200 and r.json()["disabled"] is True
    assert get(api, "/info", key).status_code == 403
    api.patch(f"/api/system/integration/keys/{k['id']}", json={"disabled": False, "name": "script2", "scope": {"tags": ["tank_niveau"]}})
    assert get(api, "/info", key).status_code == 200
    assert [p["name"] for p in get(api, "/points", key).json()] == ["tank_niveau"]              # ny afgrænsning gælder straks
    make_key(api, "anden")
    assert api.patch(f"/api/system/integration/keys/{k['id']}", json={"name": "ANDEN"}).status_code == 409
    assert api.patch("/api/system/integration/keys/k_findesikke", json={"disabled": True}).status_code == 404
    assert api.delete(f"/api/system/integration/keys/{k['id']}").status_code == 204
    assert get(api, "/info", key).status_code == 401                                              # tilbagekaldt
    assert api.delete(f"/api/system/integration/keys/{k['id']}").status_code == 404


# ------------------------------------------------------------------ godkendelse

def test_only_a_valid_bearer_key_gives_access_never_a_session_or_query_string(api):
    key, _ = make_key(api)
    c = anon(api)
    r = c.get(BASE + "/info")
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    assert c.get(BASE + "/info", headers=bearer(new_key())).status_code == 401                   # ukendt nøgle
    assert c.get(BASE + "/info", headers={"Authorization": f"Basic {key}"}).status_code == 401
    assert c.get(BASE + "/info", headers={"Authorization": key}).status_code == 401
    assert c.get(BASE + f"/info?key={key}").status_code == 401 and c.get(BASE + f"/info?token={key}").status_code == 401
    assert api.get(BASE + "/info").status_code == 401                                             # en admin-session alene giver ikke adgang
    assert get(api, "/info", key).status_code == 200


def test_a_key_cannot_be_used_anywhere_else(api):
    key, _ = make_key(api)
    c = anon(api)
    for path in ("/api/tags", "/api/live", "/api/plcs", "/api/alarms", "/api/system/integration/keys", "/api/users", "/api/system/health"):
        assert c.get(path, headers=bearer(key)).status_code in (401, 404), path
    assert c.post("/api/tags/kedel_pumpe/toggle", headers=bearer(key)).status_code == 401


def test_expired_and_ip_restricted_keys_are_refused(api):
    key, k = make_key(api, ip_allow=["10.0.0.0/8"])
    r = get(api, "/info", key)
    assert r.status_code == 403 and "IP" in r.json()["error"]                                      # testklientens adresse er ikke 10.x
    key2, k2 = make_key(api, "udloeber", expires_at=time.time() + 3600)
    assert get(api, "/info", key2).status_code == 200
    api.app.state.integration_service.db.update_api_key(k2["id"], {"expires_at": time.time() - 1})
    r = get(api, "/info", key2)
    assert r.status_code == 403 and "udløbet" in r.json()["error"]
    assert next(x for x in api.get("/api/system/integration/keys").json() if x["id"] == k2["id"])["expired"] is True


@pytest.mark.parametrize("ip, allow, ok", [("10.1.2.3", "10.0.0.0/8", True), ("11.1.2.3", "10.0.0.0/8", False), ("192.168.1.5", "10.0.0.0/8,192.168.1.0/24", True),
                                           ("::1", "::1/128", True), ("ikke-ip", "10.0.0.0/8", False), ("", "10.0.0.0/8", False)])
def test_ip_allow_list_matching(ip, allow, ok):
    assert IntegrationService._ip_allowed(ip, allow) is ok


def test_last_used_is_recorded_but_not_written_on_every_call(api):
    key, k = make_key(api)
    svc = api.app.state.integration_service
    for _ in range(5):
        assert get(api, "/info", key).status_code == 200
    first = svc.db.get_api_key(k["id"])["last_used_at"]
    assert first is not None and svc.db.get_api_key(k["id"])["last_ip"]
    time.sleep(0.05)
    get(api, "/info", key)
    assert svc.db.get_api_key(k["id"])["last_used_at"] == first          # højst én skrivning pr. minut
    assert svc.stats[k["id"]].requests == 6


def test_rate_limit_is_per_key_with_retry_after_and_counted(api):
    key, k = make_key(api, "hurtig")
    other, ko = make_key(api, "rolig")
    svc = api.app.state.integration_service
    svc.rate_burst, svc.rate_per_s = 3, 0.5
    svc._buckets.clear()
    codes = [get(api, "/info", key).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]
    r = get(api, "/info", key)
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1 and "For mange kald" in r.json()["error"]
    assert get(api, "/info", other).status_code == 200                      # en anden nøgle er upåvirket
    assert svc.stats[k["id"]].rate_limited == 3


def test_auth_failures_are_counted(api):
    svc = api.app.state.integration_service
    before = svc.auth_failures
    anon(api).get(BASE + "/info")
    anon(api).get(BASE + "/info", headers=bearer(new_key()))
    assert svc.auth_failures == before + 2


# ------------------------------------------------------------------ læse-API og afgrænsning

def test_points_hide_plc_details_and_describe_type_and_range(api):
    key, _ = make_key(api)
    pts = {p["name"]: p for p in get(api, "/points", key).json()}
    assert set(pts) == {"kedel_temp", "kedel_pumpe", "tank_niveau"}
    assert pts["kedel_temp"] == {"name": "kedel_temp", "description": "Kedeltemperatur", "unit": "°C", "type": "number", "decimals": 1,
                                 "min": None, "max": None, "history": True, "writable": False}
    assert pts["kedel_pumpe"]["type"] == "bool" and pts["tank_niveau"]["history"] is False
    text = get(api, "/points", key).text
    for secret in ("plc1", "source", "coil", "hr:5", "scale", "alarm"):
        assert secret not in text


def test_scope_tags_and_prefixes_filter_every_endpoint(api):
    key, _ = make_key(api, "afgrænset", scope={"tags": ["tank_niveau"], "prefixes": ["kedel_p"]})
    assert {p["name"] for p in get(api, "/points", key).json()} == {"tank_niveau", "kedel_pumpe"}
    _wait(lambda: get(api, "/values", key).json()["values"].get("tank_niveau", {}).get("q") == "good")
    vals = get(api, "/values", key).json()["values"]
    assert set(vals) == {"tank_niveau", "kedel_pumpe"}
    assert set(get(api, "/values?tags=kedel_temp,tank_niveau", key).json()["values"]) == {"tank_niveau"}      # uden for afgrænsning udelades
    assert get(api, "/history?tag=kedel_temp", key).status_code == 404                                         # også historik
    assert get(api, "/history?tag=tank_niveau", key).status_code == 404                                        # tilladt, men ingen historik slået til
    assert get(api, "/values?tags=findes_ikke", key).json()["values"] == {}


def test_values_format_and_quality(api):
    api.plc.state.hr[6] = 42
    key, _ = make_key(api)
    v = _wait(lambda: (d := get(api, "/values?tags=tank_niveau", key).json())["values"].get("tank_niveau", {}).get("v") == 42 and d)
    e = v["values"]["tank_niveau"]
    assert e["v"] == 42 and e["q"] == "good" and isinstance(e["ts"], float) and "error" not in e
    assert v["time"].endswith("+00:00")


def test_history_returns_downsampled_rows_for_trend_tags(api):
    api.plc.state.hr[5] = 215
    key, _ = make_key(api)
    time.sleep(1.5)                                                                     # lad opsamleren gemme et par målinger
    r = get(api, "/history?tag=kedel_temp&points=50", key)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tag"] == "kedel_temp" and body["columns"] == ["time", "mean", "min", "max"] and body["unit"] == "°C"
    assert isinstance(body["rows"], list) and body["step_s"] > 0
    assert get(api, "/history?tag=kedel_temp&start=100&end=50", key).status_code == 400
    assert get(api, f"/history?tag=kedel_temp&start=1&end={time.time()}", key).status_code == 400          # over 90 dage
    assert get(api, "/history", key).status_code == 422                                                      # tag mangler
    svc = api.app.state.integration_service
    assert svc.stats[next(iter(svc.stats))].errors >= 1                                                      # 4xx tælles som fejl


def test_alarms_follow_the_scope(api):
    key_all, _ = make_key(api, "alle")
    key_pump, _ = make_key(api, "kun-pumpe", scope={"prefixes": ["kedel_p"]})
    key_tank, _ = make_key(api, "kun-tank", scope={"tags": ["tank_niveau"]})
    api.plc.state.hr[5] = 950                                                           # 95 °C → HH
    alarm = _wait(lambda: next((a for a in get(api, "/alarms", key_all).json() if a["tag"] == "kedel_temp"), None))
    assert alarm["priority"] == "high" and alarm["state"] == "active_unack" and alarm["acknowledged"] is False and "Kedeltemperatur" in alarm["message"]
    assert get(api, "/alarms", key_pump).json() == [] and get(api, "/alarms", key_tank).json() == []            # tag ikke i afgrænsningen
    key_temp, _ = make_key(api, "temp", scope={"tags": ["kedel_temp"]})
    assert [a["tag"] for a in get(api, "/alarms", key_temp).json()] == ["kedel_temp"]


def test_info_describes_the_key_and_limits(api):
    key, _ = make_key(api, "info-test", scope={"prefixes": ["kedel_"], "tags": ["tank_niveau"]})
    d = get(api, "/info", key).json()
    assert d["key"] == {"name": "info-test", "scope": {"all": False, "tags": 1, "prefixes": 1}, "write": False}
    assert d["limits"]["requests_per_s"] == 20 and d["version"] and d["time"]


def test_openapi_describes_only_the_integration_api(api):
    r = anon(api).get(BASE + "/openapi.json")
    assert r.status_code == 200
    doc = r.json()
    assert set(doc["paths"]) == {BASE + p for p in ("/info", "/points", "/values", "/history", "/alarms")}
    assert doc["components"]["securitySchemes"]["bearerAuth"] == {"type": "http", "scheme": "bearer"} and doc["security"] == [{"bearerAuth": []}]
    assert "Point" in doc["components"]["schemas"] and "ValuesResponse" in doc["components"]["schemas"]
    assert "/api/tags" not in json.dumps(doc) and "keys" not in " ".join(doc["paths"])               # ingen admin-/konfigurationsendpoints


# ------------------------------------------------------------------ rettelser efter gennemgang

def test_values_never_expose_plc_error_text(api):
    from app.services.live_cache import LiveValue
    key, _ = make_key(api)
    api.app.state.cache.update({"tank_niveau": LiveValue(value=None, quality="comm_error", ts=time.time(), error="ConnectError: http://10.1.1.30/api fejlede")})
    r = get(api, "/values?tags=tank_niveau", key)
    e = r.json()["values"]["tank_niveau"]
    assert e["q"] == "comm_error" and "error" not in e
    assert "10.1.1.30" not in r.text and "ConnectError" not in r.text


def _comm_alarm(api):
    api.app.state.alarm_service.state["plc:plc1:comm"] = {
        "key": "plc:plc1:comm", "tag": "", "plc": "plc1", "kind": "comm", "level": "COMM", "priority": "high", "state": "active_unack",
        "raised_at": time.time(), "value": None, "acked_by": None, "acked_at": None,
        "message": "PLC Kedel: kommunikation tabt — ConnectError mod http://10.1.1.30:80"}


def test_plc_communication_alarms_are_generic_and_only_for_all_tags_keys(api):
    key_all, _ = make_key(api, "alle")
    key_one, _ = make_key(api, "kun-en", scope={"tags": ["tank_niveau"]})
    _comm_alarm(api)
    mine = [a for a in get(api, "/alarms", key_all).json() if a["kind"] == "comm"]
    assert len(mine) == 1 and mine[0]["message"] == "PLC plc1: kommunikationsfejl" and mine[0]["tag"] == ""
    assert "10.1.1.30" not in get(api, "/alarms", key_all).text and "ConnectError" not in get(api, "/alarms", key_all).text
    assert get(api, "/alarms", key_one).json() == []                                  # begrænset nøgle ser kun alarmer på egne tags


def test_tag_alarms_do_not_expose_the_plc_key(api):
    key, _ = make_key(api)
    api.plc.state.hr[5] = 950
    a = _wait(lambda: next((x for x in get(api, "/alarms", key).json() if x["tag"] == "kedel_temp"), None))
    assert a["plc"] == ""


def test_unauthenticated_floods_are_throttled_per_ip_without_database_lookups(api):
    svc = api.app.state.integration_service
    import app.services.integration as m
    for _ in range(m.FAIL_LIMIT):
        with pytest.raises(Exception) as exc:
            svc.authenticate(new_key(), "9.9.9.9")
        assert exc.value.status == 401
    lookups = []
    real = svc.db.get_api_key_by_hash
    svc.db.get_api_key_by_hash = lambda h: lookups.append(h) or real(h)
    with pytest.raises(Exception) as exc:
        svc.authenticate(new_key(), "9.9.9.9")
    assert exc.value.status == 429 and int(exc.value.headers["Retry-After"]) >= 1 and lookups == []   # afvist uden at slå noget op
    key, _ = make_key(api, "uberoert")
    assert svc.authenticate(key, "8.8.8.8").name == "uberoert"                                         # andre adresser er upåvirkede
    assert svc._ip_fails["9.9.9.9"][0] >= m.FAIL_LIMIT


def test_ip_fail_table_stays_bounded(api):
    svc = api.app.state.integration_service
    for i in range(1100):
        svc._fail(f"10.{i // 250}.{i % 250}.1", "test")
    now = time.monotonic()
    for v in svc._ip_fails.values():
        v[1] = now - 1000                                              # alle gamle
    svc._fail("1.1.1.1", "ny")
    assert len(svc._ip_fails) < 5


def test_counters_are_exact_under_concurrent_calls(api):
    import threading
    key, k = make_key(api, "samtidig")
    svc = api.app.state.integration_service
    svc.rate_burst, svc.rate_per_s = 10**6, 10**6
    svc._buckets.clear()
    errors = []

    def worker():
        try:
            for _ in range(100):
                svc.authenticate(key, "1.2.3.4")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors and svc.stats[k["id"]].requests == 800


def test_rate_limit_is_exact_under_concurrent_calls(api):
    import threading
    key, k = make_key(api, "graense")
    svc = api.app.state.integration_service
    svc.rate_burst, svc.rate_per_s = 50, 0.0001
    svc._buckets.clear()
    ok = []

    def worker():
        for _ in range(40):
            try:
                svc.authenticate(key, "1.2.3.4")
                ok.append(1)
            except Exception:  # noqa: BLE001
                pass

    threads = [threading.Thread(target=worker) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(ok) == 50                                              # præcis burst-grænsen, ikke flere


def test_refusals_of_a_known_key_are_counted_per_key(api):
    key, k = make_key(api, "afvist")
    api.patch(f"/api/system/integration/keys/{k['id']}", json={"disabled": True})
    for _ in range(3):
        get(api, "/info", key)
    assert api.app.state.integration_service.stats[k["id"]].errors == 3


def test_nan_and_infinite_expiry_is_rejected(api):
    for bad in ("NaN", "Infinity", "-Infinity"):
        body = '{"name":"nan-test","key":"%s","scope":{"all":true},"expires_at":%s}' % (new_key(), bad)
        r = api.post("/api/system/integration/keys", content=body, headers={"content-type": "application/json"})
        assert r.status_code in (400, 422), (bad, r.text)
    assert api.get("/api/system/integration/keys").json() == []


@pytest.mark.parametrize("query", ["end=1e18", "start=-5", "start=nan", "end=inf", "start=1e300&end=1e301", "end=99999999999"])
def test_extreme_history_times_give_400_not_500(api, query):
    key, _ = make_key(api)
    r = get(api, f"/history?tag=kedel_temp&{query}", key)
    assert r.status_code == 400, (query, r.status_code, r.text)


def test_concurrent_duplicate_name_gives_conflict_not_500(api):
    make_key(api, "samme")
    svc = api.app.state.integration_service
    svc._validate_name = lambda name, current_id=None: name            # som om begge forespørgsler passerede tjekket samtidig
    r = api.post("/api/system/integration/keys", json={"name": "samme", "key": new_key(), "scope": {"all": True}})
    assert r.status_code == 409 and "findes allerede" in r.json()["error"]
    other, ko = make_key(api, "anden-nogle")
    r = api.patch(f"/api/system/integration/keys/{ko['id']}", json={"name": "samme"})
    assert r.status_code == 409


# ------------------------------------------------------------------ observability

def test_metrics_and_health_expose_counters_without_secrets(api):
    key, k = make_key(api, "grafana")
    get(api, "/info", key)
    get(api, "/history?tag=findes_ikke", key)
    anon(api).get(BASE + "/info")
    d = api.get("/api/health/details").json()
    assert d["integration"]["keys"] == 1 and d["integration"]["auth_failures"] >= 1
    assert d["integration"]["per_key"]["grafana"]["requests"] == 2 and d["integration"]["per_key"]["grafana"]["errors"] == 1
    assert key not in json.dumps(d)


def test_render_integration_metrics_with_escaped_labels():
    text = render({"version": {"version": "1", "build": "1"}, "integration": {"keys": 2, "auth_failures": 3, "per_key": {
        'a"b': {"requests": 5, "errors": 1, "rate_limited": 2}}}})
    assert "scada_integration_keys 2" in text and "scada_integration_auth_failures_total 3" in text
    assert 'scada_integration_requests_total{key="a\\"b"} 5' in text and 'scada_integration_rate_limited_total{key="a\\"b"} 2' in text
    assert "scada_integration" not in render({"version": {"version": "1", "build": "1"}})          # uden integrationsdata udelades målingerne


def test_hash_is_sha256_hex():
    assert hash_key("hv_x") == hashlib.sha256(b"hv_x").hexdigest()
