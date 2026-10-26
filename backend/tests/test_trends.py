"""Trends: optagerens regler, nedsampling og API."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.live_cache import LiveCache, LiveValue
from app.services.trends import TrendRecorder
from app.storage.trends_db import TrendDatabase

ADMIN_PW = "test-admin-pw-1"


class _StubDb:
    def __init__(self, tags):
        self.tags = tags

    def list_trend_tags(self):
        return self.tags

    def list_energy_tags(self):
        return [t for t in self.tags if t.get("energy")]


class _StubManager:
    def __init__(self, tags):
        self.db = _StubDb(tags)
        self.cache = LiveCache()


@pytest.fixture
def rec(tmp_path):
    tdb = TrendDatabase(tmp_path / "t.db")
    mgr = _StubManager([{"name": "A", "source": "plc1:hr:1", "trend_interval_s": 10.0},
                        {"name": "B", "source": "plc1:coil:1", "trend_interval_s": 10.0}])
    r = TrendRecorder(mgr, tdb, keepalive_s=300)
    r._refresh_config()
    yield r, tdb, mgr
    tdb.close()


def _good(v, ts):
    return LiveValue(value=v, quality="good", ts=ts)


def _rows(tdb, name):
    return [(ts, v) for _, ts, v in tdb.raw([name], 0, 1e12, 1000)]


def test_change_rate_limited_but_latest_value_kept(rec):
    r, tdb, _ = rec
    r.offer("A", _good(5, 1000))      # første værdi gemmes
    r.offer("A", _good(5, 1001))      # uændret → intet
    r.offer("A", _good(6, 1002))      # ændring inden for 10 s → udskudt
    r.offer("A", _good(7, 1003))      # nyeste udskudte vinder
    r.flush(now=1005)
    assert _rows(tdb, "A") == [(1000, 5.0)]
    r.flush(now=1011)                 # intervallet er gået → den udskudte gemmes med sit eget tidspunkt
    assert _rows(tdb, "A") == [(1000, 5.0), (1003, 7.0)]
    r.offer("A", _good(8, 1020))      # ændring efter intervallet → gemmes straks
    r.flush(now=1020)
    assert _rows(tdb, "A")[-1] == (1020, 8.0)


def test_bool_changes_always_stored(rec):
    r, tdb, _ = rec
    for i, v in enumerate([False, True, False, True]):
        r.offer("B", _good(v, 2000 + i))
    r.flush(now=2004)
    assert [v for _, v in _rows(tdb, "B")] == [0.0, 1.0, 0.0, 1.0]


def test_gap_on_comm_error_and_recovery(rec):
    r, tdb, _ = rec
    r.offer("A", _good(5, 3000))
    r.offer("A", LiveValue(value=5, quality="comm_error", ts=3001, error="nede"))
    r.offer("A", LiveValue(value=5, quality="comm_error", ts=3002, error="nede"))  # kun ét hul
    r.offer("A", _good(5, 3003))  # tilbage — gemmes selvom værdien er uændret
    r.flush(now=3004)
    assert _rows(tdb, "A") == [(3000, 5.0), (3001, None), (3003, 5.0)]


def test_keepalive(rec):
    r, tdb, mgr = rec
    mgr.cache.update({"A": _good(5, 4000)})
    r.offer("A", _good(5, 4000))
    r.flush(now=4100)
    assert len(_rows(tdb, "A")) == 1
    r.flush(now=4301)  # 300 s uden ændring → "jeg lever"-værdi
    assert _rows(tdb, "A")[-1] == (4301, 5.0)


def test_series_time_weighted(tmp_path):
    """BUGS v1.21.2: værdier gemmes kun ved ændring, så gennemsnittet skal vægtes med tiden. En fejlmåling (0,0) der kun stod
    i 10 s, må ikke trække spandets gennemsnit ned til det halve (rækkegennemsnit: (37+0)/2 = 18,5)."""
    tdb = TrendDatabase(tmp_path / "w.db")
    tdb.insert_many([("T", 0, 37.0), ("T", 290, 0.0), ("T", 300, 37.0)])
    rows = tdb.series("T", 0, 300, 300)
    assert rows[0][1] == pytest.approx(37 * 290 / 300) and rows[0][2] == 0.0 and rows[0][3] == 37.0   # min viser stadig fejlen
    # en uændret værdi gælder videre (spand uden rækker), men højst MAX_HOLD_S — derefter ingen data (ikke et hul)
    tdb.insert_many([("U", 0, 5.0), ("U", 2000, 6.0)])
    got = {round(r[0]): r[1] for r in tdb.series("U", 0, 2400, 100)}
    assert got[50] == 5.0 and got[350] == 5.0 and 450 not in got and got[2050] == 6.0
    # et hul (None) gælder også videre: spandene i hullet er huller, ikke blot tomme
    tdb.insert_many([("H", 0, 1.0), ("H", 100, None), ("H", 400, 2.0)])
    got = {round(r[0]): r[1] for r in tdb.series("H", 0, 500, 100)}
    assert got[50] == 1.0 and got[150] is None and got[250] is None and got[450] == 2.0
    # en værdi lige ved `end` (uden varighed) kommer med
    assert tdb.series("T", 300, 301, 1)[-1][1] == 37.0


def test_series_downsampling_and_gaps(tmp_path):
    tdb = TrendDatabase(tmp_path / "s.db")
    tdb.insert_many([("X", 90, 1.0)] + [("X", 100 + i, float(i)) for i in range(10)] + [("X", 120, None)])
    rows = tdb.series("X", 100, 130, 10)
    assert rows[0] == [100, 1.0, 1.0, 1.0]                 # sidste værdi før perioden
    assert rows[1] == [105, 4.5, 0.0, 9.0]                  # spand 100-110: gennemsnit/min/max
    assert rows[2] == [115, 9.0, 9.0, 9.0]                  # 9 gælder til hullet kl. 120 (gemmes kun ved ændring)
    assert rows[3] == [125, None, None, None]               # spand med kun et hul
    assert tdb.series("findes_ikke", 0, 10, 1) == []
    assert tdb.purge_before(100) == 1
    tdb.forget("X")
    assert tdb.stats() == {}
    tdb.close()


# ------------------------------------------------------------------- API

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
                 admin_password=ADMIN_PW, backup_hours=0, trend_flush_s=0.2)
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada",
                                  "password": "scada123", "sse_enabled": False})
        assert c.post("/api/tags", json={"name": "Niveau", "source": "plc1:hr:5", "scale": 0.1, "unit": "%",
                                         "trend": True, "trend_interval_s": 1}).status_code == 201
        assert c.post("/api/tags", json={"name": "Motor", "source": "plc1:coil:1", "trend": True}).status_code == 201
        c.post("/api/tags", json={"name": "Uden", "source": "plc1:hr:6"})
        yield c


def test_api_records_and_serves_series(api, mock_plc):
    for v in (100, 250, 400):
        mock_plc.state.hr[5] = v
        time.sleep(1.2)
    mock_plc.state.coils[1] = True
    url = f"/api/trends/data?tags=Niveau,Motor,Uden&points=200&start={time.time() - 30}"  # kort periode → fine spand
    data = _wait(lambda: (d := api.get(url).json())
                 and len([p for p in d["series"]["Niveau"] if p[1] is not None]) >= 3 and d["series"]["Motor"] and d)
    values = {round(p[1], 1) for p in data["series"]["Niveau"] if p[1] is not None}
    assert {10.0, 25.0, 40.0} <= values
    assert data["series"]["Uden"] == [] and data["meta"]["Niveau"]["unit"] == "%"
    info = {t["name"]: t for t in api.get("/api/trends/info").json()["tags"]}
    assert info["Niveau"]["samples"] >= 3 and info["Uden"]["trend"] is False


def test_csv_export(api, mock_plc):
    mock_plc.state.hr[5] = 123
    # Opsamlingen starter straks ved oprettelse, så første værdi kan være 0 — vent på 12,3
    _wait(lambda: ";Niveau;12,3" in api.get("/api/trends/export?tags=Niveau").text)
    r = api.get("/api/trends/export?tags=Niveau")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    lines = r.text.lstrip("﻿").splitlines()
    assert lines[0] == "tidspunkt;tag;vaerdi" and ";Niveau;12,3" in "\n".join(lines)


@pytest.mark.parametrize("query, message", [
    ("tags=", "mindst ét tag"),
    ("tags=Niveau&start=200&end=100", "før sluttidspunktet"),
    ("tags=Niveau&start=0&end=99999999999", "400 dage"),
    ("tags=" + ",".join(f"T{i}" for i in range(21)), "20 tags"),
])
def test_validation(api, query, message):
    r = api.get(f"/api/trends/data?{query}")
    assert r.status_code == 400 and message in r.json()["error"]


def test_trend_interval_validation(api):
    r = api.patch("/api/tags/Niveau", json={"trend_interval_s": 0.5})
    assert r.status_code == 400 and "1-3600" in r.json()["error"]


def test_deleting_tag_forgets_history(api, mock_plc):
    _wait(lambda: api.app.state.trend_db.stats().get("Motor"))
    assert api.delete("/api/tags/Motor").status_code == 204
    assert "Motor" not in api.app.state.trend_db.stats()


def test_recorder_forget_drops_buffered_values(rec):
    r, tdb, _ = rec
    r.offer("A", _good(5, 1000))
    r.flush(now=1001)
    r.offer("A", _good(9, 1020))  # ligger i bufferen, ikke skrevet endnu
    assert r.forget("A") == 1
    r.flush(now=1021)
    assert _rows(tdb, "A") == []  # den bufferede værdi dukker ikke op igen
    r.offer("A", _good(3, 1030))  # opsamlingen fortsætter: første værdi efter sletning gemmes straks
    r.flush(now=1031)
    assert _rows(tdb, "A") == [(1030, 3.0)]


def test_delete_history_api(api, mock_plc):
    _wait(lambda: api.app.state.trend_db.stats().get("Motor"))
    r = api.delete("/api/trends/history/Motor")
    assert r.status_code == 200 and r.json()["deleted"] >= 1
    assert api.get("/api/tags/Motor").json()["trend"] is True  # sletning slår ikke opsamlingen fra
    assert any(e["action"] == "trend.delete" and e["target"] == "Motor" for e in api.get("/api/audit").json())
    # "Stop" = tagets trend-felt; det gemte bevares
    _wait(lambda: api.app.state.trend_db.stats().get("Niveau"))
    assert api.patch("/api/tags/Niveau", json={"trend": False}).status_code == 200
    info = {t["name"]: t for t in api.get("/api/trends/info").json()["tags"]}
    assert info["Niveau"]["trend"] is False and info["Niveau"]["samples"] >= 1
    # Efter "Stop" + "Slet" kommer der ingen nye værdier (opsamleren stopper straks, ikke ved næste skrivning)
    api.delete("/api/trends/history/Niveau")
    mock_plc.state.hr[5] = 777
    time.sleep(1.0)
    assert "Niveau" not in api.app.state.trend_db.stats()
    # Kun tekniker/admin
    api.post("/api/users", json={"username": "kigger", "role": "viewer", "password": "Hemmelig-123"})
    api.post("/api/auth/login", json={"username": "kigger", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert api.delete("/api/trends/history/Niveau").status_code == 403


def test_scoped_user_only_gets_own_tags(api):
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><g id="M1" data-hv-type="lampe"><circle id="M1_c" r="3"/></g></svg>'
    did = api.post("/api/drawings", json={"name": "M", "svg": svg}).json()["drawing"]["id"]
    # Motor er trendet i tegningen (symbolets animation) — Niveau er ikke; kun opsatte trends er tilladt for en viewer
    cfg = {"op": "view", "anims": [{"part": "all", "type": "fill", "src": "Motor", "params": {}}]}
    assert api.put(f"/api/drawings/{did}/symbols/M1/config", json={"config": cfg}).status_code == 200
    api.post("/api/users", json={"username": "vagt", "role": "viewer", "password": "Hemmelig-123", "drawings": [did]})
    api.post("/api/auth/login", json={"username": "vagt", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert set(api.get("/api/trends/data?tags=Niveau,Motor").json()["series"]) == {"Motor"}
    assert [t["name"] for t in api.get("/api/trends/info").json()["tags"]] == ["Motor"]


def test_trend_settings_in_backup(api):
    backup = api.get("/api/backup").json()
    niveau = next(t for t in backup["tags"] if t["name"] == "Niveau")
    assert niveau["trend"] is True and niveau["trend_interval_s"] == 1
    assert api.post("/api/backup/restore", json=backup).status_code == 200
    assert api.get("/api/tags/Niveau").json()["trend"] is True


def test_trend_history_backup_download_and_merge(api, mock_plc, tmp_path):
    import gzip
    import sqlite3
    _wait(lambda: api.app.state.trend_db.stats().get("Niveau"))
    r = api.get("/api/backup/trends")
    assert r.status_code == 200 and r.headers["content-type"] == "application/gzip"
    assert "scada-historik-" in r.headers["content-disposition"]
    raw = gzip.decompress(r.content)
    assert raw.startswith(b"SQLite format 3")
    snap = tmp_path / "snap.db"
    snap.write_bytes(raw)
    con = sqlite3.connect(snap)
    names = {n for (n,) in con.execute("SELECT name FROM trend_tags")}
    # Tilføj et tag + to værdier der ikke findes på serveren; en eksisterende værdi må ikke overskrives
    con.execute("INSERT INTO trend_tags(name) VALUES ('Gammelt_tag')")
    tid = con.execute("SELECT id FROM trend_tags WHERE name = 'Gammelt_tag'").fetchone()[0]
    con.executemany("INSERT INTO samples VALUES (?, ?, ?)", [(tid, 1000.0, 1.5), (tid, 1060.0, None)])
    nid, ts = con.execute("SELECT s.tag_id, s.ts FROM samples s JOIN trend_tags t ON t.id = s.tag_id "
                          "WHERE t.name = 'Niveau' LIMIT 1").fetchone()
    con.execute("UPDATE samples SET value = -999 WHERE tag_id = ? AND ts = ?", (nid, ts))
    con.commit()
    con.close()
    assert "Niveau" in names
    r = api.post("/api/backup/trends/merge", content=gzip.compress(snap.read_bytes()))
    assert r.status_code == 200, r.text
    assert r.json()["samples_added"] == 2  # kun de nye — de eksisterende bevares
    assert api.app.state.trend_db.stats()["Gammelt_tag"]["samples"] == 2
    vals = [v for _, t, v in api.app.state.trend_db.raw(["Niveau"], ts - 0.001, ts + 0.001, 10)]
    assert -999 not in vals
    assert any(e["action"] == "backup.trends.merge" for e in api.get("/api/audit").json())
    # Ukompimeret .db virker også; skrald afvises med specifik fejl
    assert api.post("/api/backup/trends/merge", content=snap.read_bytes()).json()["samples_added"] == 0
    bad = api.post("/api/backup/trends/merge", content=b"ikke en database")
    assert bad.status_code == 400 and "hverken" in bad.json()["error"]
    other = tmp_path / "anden.db"
    sqlite3.connect(other).execute("CREATE TABLE x (a)").connection.commit()
    bad = api.post("/api/backup/trends/merge", content=other.read_bytes())
    assert bad.status_code == 400 and "ikke en trend-historik" in bad.json()["error"]


def test_trend_snapshot_on_server_and_pruning(api, mock_plc):
    svc = api.app.state.backup_service
    svc.trend_keep = 2
    names = [svc.save_trend_snapshot() for _ in range(3)]
    files = [f for f in api.get("/api/backup/files").json() if f["kind"] == "historik"]
    assert len(files) <= 2 and names[-1] in [f["name"] for f in files]
    r = api.get(f"/api/backup/files/{names[-1]}")
    assert r.status_code == 200 and r.headers["content-type"] == "application/gzip"
    assert api.get("/api/backup/files/..%2Ftrends.db").status_code in (400, 404)


def test_energy_tags_kept_longer_than_other_history(tmp_path):
    tdb = TrendDatabase(tmp_path / "t.db")
    tdb.insert_many([("Maaler", 100.0, 1.0), ("Maaler", 5000.0, 2.0), ("Andet", 100.0, 1.0), ("Andet", 5000.0, 2.0)])
    assert tdb.purge_before(1000.0, {"Maaler": 50.0}) == 1  # kun "Andet" ved ts 100
    assert [ts for _, ts, _ in tdb.raw(["Maaler"], 0, 1e9, 10)] == [100.0, 5000.0]
    assert tdb.samples_with_prev("Maaler", 1000.0, 6000.0) == [(100.0, 1.0), (5000.0, 2.0)]
    tdb.close()


def test_energy_validation_all_branches(api):
    # Kræver historik — ved oprettelse, opdatering (også når historikken slås fra) og import
    r = api.post("/api/tags", json={"name": "E1", "source": "plc1:hr:7", "energy": "counter"})
    assert r.status_code == 400 and "historik" in r.json()["error"]
    assert api.patch("/api/tags/Niveau", json={"energy": "power", "energy_factor": 0.001}).status_code == 200
    r = api.patch("/api/tags/Niveau", json={"trend": False})
    assert r.status_code == 400 and "historik" in r.json()["error"]
    r = api.patch("/api/tags/Motor", json={"energy": "counter"})  # coil = til/fra
    assert r.status_code == 400 and "tal-tag" in r.json()["error"]
    assert api.patch("/api/tags/Niveau", json={"energy_factor": 0}).status_code == 400
    assert api.patch("/api/tags/Niveau", json={"energy": "kwh"}).status_code == 400
    imp = api.post("/api/tags/import", json={"tags": [{"name": "E2", "source": "plc1:hr:8", "energy": "power"}]}).json()
    assert imp["created"] == [] and "historik" in imp["skipped"][0]["reason"]
    # Backup bærer felterne
    t = next(t for t in api.get("/api/backup").json()["tags"] if t["name"] == "Niveau")
    assert (t["energy"], t["energy_factor"]) == ("power", 0.001)


def test_energy_report_api(api, mock_plc):
    api.patch("/api/tags/Niveau", json={"energy": "power", "energy_factor": 1})
    _wait(lambda: api.app.state.trend_db.stats().get("Niveau"))
    tags = api.get("/api/energy/tags").json()
    assert [t["name"] for t in tags["tags"]] == ["Niveau"] and tags["energy_days"] >= 30
    r = api.get("/api/energy/report?period=day").json()
    assert len(r["buckets"]) == 14 and r["buckets"][-1]["current"] is True and r["unit"] == "kWh"
    assert r["series"]["Niveau"][-1] is not None and r["series"]["Niveau"][0] is None  # ingen data for 13 dage siden
    assert api.get("/api/energy/report?period=aar").status_code == 400
    csv_text = api.get("/api/energy/export?period=month").text.lstrip("﻿")
    assert csv_text.splitlines()[0].startswith("periode;fra;") and csv_text.splitlines()[-1].startswith("I alt;")


def test_purge_per_tag_uses_primary_key_and_keeps_energy_longer(tmp_path):
    """Kodeanalyse 26.10.2026 F2: oprydningen scannede hele tabellen (`ts < ?`) hver time i event-loopet."""
    tdb = TrendDatabase(tmp_path / "p.db")
    tdb.insert_many([("A", 10, 1.0), ("A", 200, 2.0), ("E", 10, 5.0), ("E", 60, 6.0), ("E", 200, 7.0)])
    assert tdb.purge_before(100, keep={"E": 50}) == 2          # A@10 og E@10 — E beholder alt efter 50
    assert tdb.stats()["A"]["samples"] == 1 and tdb.stats()["E"]["samples"] == 2
    plan = tdb._conn.execute("EXPLAIN QUERY PLAN DELETE FROM samples WHERE tag_id = ? AND ts < ?", (1, 100)).fetchall()
    assert any("SEARCH" in str(row) for row in plan) and not any("SCAN samples" in str(row) for row in plan)
