"""Flytning af trend-databasen (System › Konfiguration): relocate, validering og opstart med manglende disk."""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import sysconfig
from app.services.errors import ServiceError
from app.storage.trends_db import TrendDatabase

ADMIN_PW = "test-admin-pw-1"


def filled(path, n=50):
    db = TrendDatabase(path)
    db.insert_many([("a", 1000.0 + i, float(i)) for i in range(n)] + [("b", 1000.0 + i, None) for i in range(5)])
    return db


def test_relocate_bevarer_data_og_gemmer_den_gamle_fil(tmp_path):
    old = tmp_path / "old" / "trends.db"
    db = filled(old)
    new = tmp_path / "ssd" / "trends.db"
    new.parent.mkdir()
    moved = db.relocate(new)
    assert db.path == new and new.exists() and not old.exists()
    assert moved.name == "trends.db.moved" and moved.exists()
    assert db.stats()["a"]["samples"] == 50 and db.stats()["b"]["samples"] == 5
    db.insert_many([("a", 5000.0, 1.0)])           # skriv efter flytningen går til den nye fil
    assert db.stats()["a"]["samples"] == 51
    assert TrendDatabase(moved).stats()["a"]["samples"] == 50   # den gamle er urørt (uden den nye værdi)
    assert db.series("a", 1000.0, 1100.0, 10.0)


def test_relocate_afviser_eksisterende_maal_og_aendrer_intet(tmp_path):
    db = filled(tmp_path / "trends.db")
    target = tmp_path / "ssd" / "trends.db"
    target.parent.mkdir()
    target.write_bytes(b"findes")
    with pytest.raises(FileExistsError):
        db.relocate(target)
    assert db.path == tmp_path / "trends.db" and db.stats()["a"]["samples"] == 50
    assert target.read_bytes() == b"findes"


def test_relocate_tilbage_og_frem(tmp_path):
    db = filled(tmp_path / "data" / "trends.db")
    ssd = tmp_path / "ssd"
    ssd.mkdir()
    db.relocate(ssd / "trends.db")
    (tmp_path / "data" / "trends.db.moved").unlink()
    db.relocate(tmp_path / "data" / "trends.db")
    assert db.stats()["a"]["samples"] == 50


def validate(raw, tmp_path, **kw):
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    cur = data / "trends.db"
    cur.write_bytes(b"x" * 100)
    return sysconfig.validate_trend_dir(raw, data, cur, roots=(tmp_path / "mnt",), require_other_device=False, **kw)


def test_validering_af_placering(tmp_path):
    (tmp_path / "mnt" / "ssd").mkdir(parents=True)
    assert validate(str(tmp_path / "mnt" / "ssd"), tmp_path) == (tmp_path / "mnt" / "ssd").resolve() / "trends.db"

    def msg(raw, **kw):
        with pytest.raises(ServiceError) as e:
            validate(raw, tmp_path, **kw)
        return e.value.message

    assert "fuld sti" in msg("relativ/sti")
    assert "under /mnt eller /media" in msg(str(tmp_path / "andet"))
    assert "under /mnt eller /media" in msg(str(tmp_path / "mnt" / ".." / "data"))     # .. slipper ikke ud
    assert "findes ikke" in msg(str(tmp_path / "mnt" / "mangler"))
    assert "sti" in msg(5)
    (tmp_path / "mnt" / "ssd" / "trends.db").write_bytes(b"x")
    assert "allerede en trends.db" in msg(str(tmp_path / "mnt" / "ssd"))


def test_samme_disk_afvises(tmp_path):
    (tmp_path / "mnt" / "ssd").mkdir(parents=True)
    data = tmp_path / "data"
    data.mkdir()
    cur = data / "trends.db"
    cur.write_bytes(b"x")
    with pytest.raises(ServiceError, match="samme disk"):
        sysconfig.validate_trend_dir(str(tmp_path / "mnt" / "ssd"), data, cur, roots=(tmp_path / "mnt",))


def test_opstart_med_manglende_disk_bruger_datamappen_med_advarsel(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.json").write_text(json.dumps({"storage": {"trend_dir": str(tmp_path / "vaek")}}), encoding="utf-8")
    path, warning = sysconfig.resolve_trend_db_path(tmp_path)
    assert path == tmp_path / "trends.db" and "mangler" in warning
    ssd = tmp_path / "ssd"
    ssd.mkdir()
    (tmp_path / "config" / "settings.json").write_text(json.dumps({"storage": {"trend_dir": str(ssd)}}), encoding="utf-8")
    assert sysconfig.resolve_trend_db_path(tmp_path) == (ssd / "trends.db", "")
    (tmp_path / "config" / "settings.json").write_text("{ikke json", encoding="utf-8")
    assert sysconfig.resolve_trend_db_path(tmp_path) == (tmp_path / "trends.db", "")


def test_gem_afsnit_bevarer_de_andre(tmp_path):
    sysconfig.save_trend_settings(tmp_path, {"retention_days": 60.0, "flush_s": 30.0, "energy_days": 400.0})
    sysconfig.save_section(tmp_path, "storage", {"trend_dir": "/mnt/x"})
    doc = json.loads((tmp_path / "config" / "settings.json").read_text(encoding="utf-8"))
    assert doc["trends"]["flush_s"] == 30.0 and doc["storage"]["trend_dir"] == "/mnt/x"


def test_api_flytning_kun_admin_og_afviser_ugyldig_sti(tmp_path):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        assert c.put("/api/system/config/storage", json={"trend_dir": "/mnt/x"}).status_code in (401, 403)
        assert c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW}).status_code == 200
        r = c.put("/api/system/config/storage", json={"trend_dir": "/etc"})
        assert r.status_code == 400 and "/mnt" in r.json()["error"]
        r = c.put("/api/system/config/storage", json={"trend_dir": "relativ"})
        assert r.status_code == 400
        view = c.get("/api/system/config").json()["trends"]["storage"]
        assert view["path"].endswith("trends.db") and view["warning"] == "" and "/mnt" in view["roots"]
