"""scada-maint: tørkørsel ændrer intet, --yes rydder logfiler/backups/historik, og tags/brugere/tegninger røres aldrig."""

import os
import sqlite3
import time

import pytest

from app import maint
from app.config import Settings
from app.storage.db import Database
from app.storage.trends_db import TrendDatabase

DAY = 86400


@pytest.fixture
def env(tmp_path):
    data = tmp_path / "data"
    state = tmp_path / "net"
    for d in (data / "backups", data / "updates", state):
        d.mkdir(parents=True)
    now = time.time()
    # scada.db med et tag, en energi-tag, audit og alarmer
    db = Database(data / "scada.db")
    con = sqlite3.connect(str(data / "scada.db"))
    con.execute("INSERT INTO audit(ts, username, action, result) VALUES (?, 'a', 'x', 'ok')", (now - 200 * DAY,))
    con.execute("INSERT INTO audit(ts, username, action, result) VALUES (?, 'a', 'x', 'ok')", (now - 1 * DAY,))
    con.execute("INSERT INTO alarm_events(ts, key, level, priority, event) VALUES (?, 'k', 'l', 'p', 'e')", (now - 200 * DAY,))
    con.execute("INSERT INTO alarm_events(ts, key, level, priority, event) VALUES (?, 'k', 'l', 'p', 'e')", (now - 1 * DAY,))
    con.commit()
    con.close()
    del db
    # trend-database: ét almindeligt og ét energi-tag, gamle og nye værdier
    tdb = TrendDatabase(data / "trends.db")
    tdb.insert_many([("temp", now - 100 * DAY, 1.0), ("temp", now - 1 * DAY, 2.0),
                     ("kwh", now - 100 * DAY, 10.0), ("kwh", now - 1 * DAY, 20.0)])
    tdb._conn.close()      # (Windows holder filen låst, så længe forbindelsen er åben)
    c = sqlite3.connect(str(data / "scada.db"))
    now_ = time.time()
    c.execute("INSERT INTO plcs(key, name, base_url, username, created_at, updated_at) VALUES ('p','P','http://x','u',?,?)", (now_, now_))
    c.execute("INSERT INTO tags(name, source, plc, created_at, updated_at, energy) VALUES ('kwh','s','p',?,?,'{}')", (now_, now_))
    c.commit()
    c.close()
    # filer
    for i in range(5):
        p = data / "backups" / f"scada-auto-{i}.json"
        p.write_text("x" * 100)
        os.utime(p, (now - i * 100, now - i * 100))
    (data / "backups" / "trends-auto-1.db.gz").write_bytes(b"y" * 50)
    (data / "updates" / "update.log").write_text("l" * 1000)
    (state / "network.log").write_text("n" * 500)
    s = Settings(data_dir=data, net_state_dir=state, admin_password="x")
    return s, data, state, None


def make(env, execute, out=None):
    s, *_ = env
    lines = [] if out is None else out
    return maint.Maint(s, execute=execute, out=lines.append, use_service=False), lines


def test_toerkoersel_aendrer_intet(env):
    s, data, state, _ = env
    m, lines = make(env, False)
    m.logs(); m.backups(keep=1, moved=True); m.trends(14); m.history(30, 30); m.trends_reset()
    assert (data / "updates" / "update.log").stat().st_size == 1000 and (state / "network.log").stat().st_size == 500
    assert len(list((data / "backups").glob("scada-*.json"))) == 5
    assert TrendDatabase(data / "trends.db").stats()["temp"]["samples"] == 2
    assert all("[tørkørsel]" in ln for ln in lines if ln.startswith(("Logfiler", "Gamle", "Trend", "Audit", "Hele")))


def test_logs_toemmes_men_filerne_bevares(env):
    s, data, state, _ = env
    m, _ = make(env, True)
    m.logs()
    assert (data / "updates" / "update.log").exists() and (data / "updates" / "update.log").stat().st_size == 0
    assert (state / "network.log").stat().st_size == 0


def test_backups_beholder_de_nyeste_og_trends_moved_kun_naar_bedt(env):
    s, data, _, _ = env
    (data / "trends.db.moved").write_bytes(b"m" * 10)
    m, _ = make(env, True)
    m.backups(keep=2)
    left = sorted(p.name for p in (data / "backups").glob("scada-*.json"))
    assert left == ["scada-auto-0.json", "scada-auto-1.json"]
    assert (data / "backups" / "trends-auto-1.db.gz").exists() and (data / "trends.db.moved").exists()
    m.backups(keep=2, moved=True)
    assert not (data / "trends.db.moved").exists()


def test_trends_sletter_gamle_men_beholder_energi_laenger(env):
    s, data, _, _ = env
    m, lines = make(env, True)
    removed = m.trends(14)
    assert removed == 1                                 # kun temp's 100 dage gamle værdi; energi-tagget (400 dage) røres ikke
    stats = TrendDatabase(data / "trends.db").stats()
    assert stats["temp"]["samples"] == 1 and stats["kwh"]["samples"] == 2


def test_history_trimmer_audit_og_alarmer(env):
    s, data, _, _ = env
    m, _ = make(env, True)
    assert m.history(30, 30) == 2
    c = sqlite3.connect(str(data / "scada.db"))
    assert c.execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM alarm_events").fetchone()[0] == 1
    c.close()


def test_trends_reset_arkiverer_og_sletter(env, tmp_path):
    s, data, _, _ = env
    m, _ = make(env, True)
    m.trends_reset(archive=tmp_path / "arkiv")
    assert not (data / "trends.db").exists()
    assert len(list((tmp_path / "arkiv").glob("trends-*.db.gz"))) == 1


def test_shrink_afvises_hvis_der_ikke_er_plads(env, monkeypatch):
    s, data, _, _ = env
    m, _ = make(env, True)
    monkeypatch.setattr(m, "free", lambda: 1)
    with pytest.raises(SystemExit, match="For lidt ledig plads"):
        m.history(30, 30, shrink=True)


def test_emergency_stopper_naar_der_er_plads(env, monkeypatch):
    s, data, _, _ = env
    m, lines = make(env, True)
    monkeypatch.setattr(m, "low", lambda: False)
    m.emergency()
    assert any("nok plads" in ln for ln in lines)
    assert (data / "trends.db").exists()      # intet så indgribende som en nulstilling


def test_emergency_gaar_trin_for_trin_til_det_er_nok(env, monkeypatch):
    s, data, _, _ = env
    m, lines = make(env, True)
    calls = {"n": 0}

    def low():
        calls["n"] += 1
        return calls["n"] < 4      # lavt indtil det tredje trin er kørt
    monkeypatch.setattr(m, "low", low)
    m.emergency()
    assert (data / "trends.db").exists() and any("nok plads" in ln for ln in lines)


def test_status_viser_stoerrelser_og_roerer_intet(env):
    s, data, _, _ = env
    m, lines = make(env, False)
    m.status()
    text = "\n".join(lines)
    assert "Disk (" in text and "trends.db" in text and "backups/" in text and "update.log" in text


def test_main_kraever_root_for_at_udfoere(env, monkeypatch, capsys):
    if not hasattr(os, "geteuid"):
        pytest.skip("kun Linux")
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    assert maint.main(["logs", "--yes"]) == 2
    assert "root" in capsys.readouterr().err
