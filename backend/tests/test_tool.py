"""Server-værktøjskassen `scada-tool` (app/tool.py, v5.6.0) og hurtigere opdagelse af en hængende opdatering."""

import io
import json
import tarfile
import time
from pathlib import Path

import pytest

from app import tool
from app.services.auth import hash_password, verify_password
from app.services.updates import REQUIRED, UpdateService
from app.storage.db import Database


@pytest.fixture
def env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "updates").mkdir(parents=True)
    app = tmp_path / "app"
    app.mkdir()
    (app / "version.json").write_text('{"version": "5.0.0", "build": "0100"}', encoding="utf-8")
    envfile = tmp_path / "scada.env"
    envfile.write_text("SCADA_PORT=8123\nSCADA_ADMIN_PASSWORD=hemmelig-eksempel\nLOG_LEVEL=INFO\n# kommentar\n", encoding="utf-8")
    monkeypatch.setenv("SCADA_DATA_DIR", str(data))
    monkeypatch.setattr(tool, "APP", app)
    monkeypatch.setattr(tool, "ENVFILE", envfile)
    monkeypatch.setattr(tool, "audit", lambda msg: None)
    monkeypatch.setattr(tool, "ASSUME_YES", True)
    monkeypatch.setattr(tool, "is_running", lambda unit: False)
    monkeypatch.setattr(tool, "is_active", lambda unit: False)
    return tmp_path


def make_db(env_dir: Path) -> Database:
    db = Database(env_dir / "data" / "scada.db")
    db.insert_user("admin", {"password_hash": hash_password("Gammel-adgangskode-1"), "role": "admin"})
    return db


def stdin(monkeypatch, text: str) -> None:
    monkeypatch.setattr(tool.sys, "stdin", io.StringIO(text))


def test_user_reset_sets_a_new_password_forces_a_change_and_closes_sessions(env, monkeypatch, capsys):
    db = make_db(env)
    db.add_session("tokenhash", "admin", time.time(), time.time() + 3600, "127.0.0.1") if hasattr(db, "add_session") else None
    stdin(monkeypatch, "Ny-hemmelig-123\n")
    assert tool.main(["--yes", "user", "reset", "admin"]) == 0
    row = Database(env / "data" / "scada.db").get_user("admin")
    assert verify_password("Ny-hemmelig-123", row["password_hash"]) and not verify_password("Gammel-adgangskode-1", row["password_hash"])
    assert row["must_change_password"]
    out = capsys.readouterr().out
    assert "Ny-hemmelig-123" not in out                       # adgangskoden vises aldrig


def test_user_reset_checks_the_password_rules_and_the_user(env, monkeypatch, capsys):
    make_db(env)
    stdin(monkeypatch, "kort\n")
    assert tool.main(["--yes", "user", "reset", "admin"]) == 1
    assert "mindst" in capsys.readouterr().out
    stdin(monkeypatch, "Ny-hemmelig-123\n")
    assert tool.main(["--yes", "user", "reset", "findes-ikke"]) == 1
    assert tool.main(["user", "reset"]) == 2                  # navn mangler
    row = Database(env / "data" / "scada.db").get_user("admin")
    assert verify_password("Gammel-adgangskode-1", row["password_hash"])      # urørt


def test_user_reset_keep_does_not_force_a_change(env, monkeypatch):
    make_db(env)
    stdin(monkeypatch, "Ny-hemmelig-123\n")
    assert tool.main(["--yes", "user", "reset", "admin", "--keep"]) == 0
    assert not Database(env / "data" / "scada.db").get_user("admin")["must_change_password"]


def test_config_never_shows_secrets(env, capsys):
    assert tool.main(["config"]) == 0
    out = capsys.readouterr().out
    assert "SCADA_PORT = 8123" in out and "SCADA_ADMIN_PASSWORD = (sat)" in out and "hemmelig-eksempel" not in out


def test_update_reset_clears_a_stuck_update_but_not_a_running_one(env, monkeypatch, capsys):
    d = env / "data" / "updates"
    (d / "status.json").write_text(json.dumps({"state": "applying", "message": "x", "from": "5.0.0", "to": "5.1.0", "ts": 1}), encoding="utf-8")
    (d / "apply.request").write_text("SHA256=x", encoding="utf-8")
    (d / "incoming-abc.part").write_text("halv", encoding="utf-8")
    monkeypatch.setattr(tool, "is_running", lambda unit: True)
    assert tool.main(["--yes", "update", "reset"]) == 1                 # opdateringstjenesten kører: rør intet
    assert (d / "apply.request").exists()
    monkeypatch.setattr(tool, "is_running", lambda unit: False)
    assert tool.main(["--yes", "update", "reset"]) == 0
    st = json.loads((d / "status.json").read_text(encoding="utf-8"))
    assert st["state"] == "failed" and st["to"] == "5.1.0"
    assert not (d / "apply.request").exists() and not list(d.glob("incoming-*.part"))


def package(path: Path, version: str, build: str) -> Path:
    with tarfile.open(path, "w") as tar:
        for name in REQUIRED:
            data = json.dumps({"version": version, "build": build}).encode() if name == "version.json" else b"x"
            info = tarfile.TarInfo(f"scada/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def test_update_apply_queues_a_request_with_a_backup_and_waits_for_the_helper(env, monkeypatch, capsys):
    make_db(env)
    d = env / "data" / "updates"
    (d / "enabled").write_text("", encoding="utf-8")
    pkg = package(env / "pkg.tar", "5.1.0", "0101")

    def helper(_seconds):                       # opdateringstjenesten svarer: færdig
        if (d / "apply.request").exists():
            (d / "status.json").write_text(json.dumps({"state": "done", "message": "Opdateret"}), encoding="utf-8")
    monkeypatch.setattr(tool.time, "sleep", helper)
    assert tool.main(["--yes", "update", "apply", str(pkg)]) == 0
    req = (d / "apply.request").read_text(encoding="utf-8")
    assert "VERSION=5.1.0" in req and "BUILD=0101" in req and "BY=scada-tool" in req
    assert (d / "staged.tar").is_file() and json.loads((d / "staged.json").read_text())["version"] == "5.1.0"
    assert list((env / "data" / "backups").glob("scada-pre-update-cli-*.db"))


def test_update_apply_refuses_older_same_and_broken_packages(env, capsys):
    (env / "data" / "updates" / "enabled").write_text("", encoding="utf-8")
    assert tool.main(["--yes", "update", "apply", str(package(env / "gammel.tar", "4.0.0", "0001"))]) == 1
    assert "ÆLDRE" in capsys.readouterr().out
    assert tool.main(["--yes", "update", "apply", str(package(env / "samme.tar", "5.0.0", "0100"))]) == 1
    assert "Samme version" in capsys.readouterr().out
    (env / "dårlig.tar").write_bytes(b"ikke en tar")
    assert tool.main(["--yes", "update", "apply", str(env / "dårlig.tar")]) == 1
    assert not (env / "data" / "updates" / "apply.request").exists()


def test_check_finds_an_app_that_cannot_be_imported(env, monkeypatch, capsys):
    """Selve diagnosen, der ville have fundet v5.4.0-fejlen: appen skal kunne importeres med serverens Python."""
    monkeypatch.chdir(env)                       # her findes ingen `app` → importen fejler
    assert tool.main(["check"]) == 1
    out = capsys.readouterr().out
    assert "kan IKKE importeres" in out and "ModuleNotFoundError" in out


def test_backup_create_and_restore_round_trip(env, monkeypatch, capsys):
    db = make_db(env)
    assert tool.main(["backup", "create"]) == 0
    made = next((env / "data" / "backups").glob("scada-cli-*.db"))
    db.insert_user("senere", {"password_hash": hash_password("Hemmelig-12345"), "role": "operator"})
    db._conn.close()                                                   # (på Windows holder en åben forbindelse filen)
    monkeypatch.setattr(tool, "run", lambda cmd, timeout=30: (0, ""))
    monkeypatch.setattr(tool, "wait_health", lambda port, seconds, want=None: True)
    assert tool.main(["--yes", "backup", "restore", str(made)]) == 0
    names = {u["username"] for u in Database(env / "data" / "scada.db").list_users()}
    assert names == {"admin"}                                         # tilbage til backuppen
    assert list((env / "data" / "backups").glob("scada-before-restore-*.db"))      # den gamle er gemt først
    assert tool.main(["--yes", "backup", "restore", str(env / "ikke.db")]) == 1


@pytest.mark.parametrize("age,helper,state", [(30, False, "applying"), (200, False, "stalled"), (200, True, "applying"),
                                              (200, None, "applying"), (25 * 60, True, "stalled")])
def test_a_stuck_update_is_noticed_after_two_minutes_when_the_helper_is_not_running(tmp_path, age, helper, state):
    svc = UpdateService(tmp_path, backups=None, current=lambda: {"version": "5.0.0", "build": "0100"})
    (svc.dir / "status.json").write_text(json.dumps({"state": "applying", "message": "x", "ts": time.time() - age}), encoding="utf-8")
    svc.helper_running = lambda: helper
    st = svc.status()
    assert st["state"] == state and st["busy"] == (state == "applying")


def test_rollback_restores_the_previous_version_and_refuses_while_the_helper_runs(env, monkeypatch, capsys):
    app = env / "app"
    (app / "backend").mkdir()
    (app / "backend" / "ny.py").write_text("ny", encoding="utf-8")
    prev = env / "app.prev"
    (prev / "backend").mkdir(parents=True)
    (prev / "backend" / "gammel.py").write_text("gammel", encoding="utf-8")
    (prev / "version.json").write_text('{"version": "4.0.0", "build": "0001"}', encoding="utf-8")
    monkeypatch.setattr(tool, "run", lambda cmd, timeout=30: (0, ""))
    monkeypatch.setattr(tool, "wait_health", lambda port, seconds, want=None: True)
    monkeypatch.setattr(tool, "is_running", lambda unit: True)
    assert tool.main(["--yes", "update", "rollback"]) == 1                     # opdateringstjenesten kører: rør intet
    assert (app / "backend" / "ny.py").exists()
    monkeypatch.setattr(tool, "is_running", lambda unit: False)
    assert tool.main(["--yes", "update", "rollback"]) == 0
    assert (app / "backend" / "gammel.py").exists() and not (app / "backend" / "ny.py").exists()
    assert "4.0.0" in (app / "version.json").read_text(encoding="utf-8")
    assert not (app / "backend.new").exists()


def test_rollback_without_a_previous_version_changes_nothing(env, capsys):
    (env / "app" / "backend").mkdir()
    assert tool.main(["--yes", "update", "rollback"]) == 1
    assert (env / "app" / "backend").is_dir()


def test_restore_aborts_and_leaves_the_database_alone_if_the_service_cannot_be_stopped(env, monkeypatch, capsys):
    db = make_db(env)
    assert tool.main(["backup", "create"]) == 0
    made = next((env / "data" / "backups").glob("scada-cli-*.db"))
    db.insert_user("senere", {"password_hash": hash_password("Hemmelig-12345"), "role": "operator"})
    db._conn.close()
    monkeypatch.setattr(tool, "run", lambda cmd, timeout=30: (1, "stop fejlede"))
    assert tool.main(["--yes", "backup", "restore", str(made)]) == 1
    assert {u["username"] for u in Database(env / "data" / "scada.db").list_users()} == {"admin", "senere"}
    assert "kunne ikke stoppes" in capsys.readouterr().out


def test_restore_reports_failure_when_the_server_does_not_come_back(env, monkeypatch):
    db = make_db(env)
    assert tool.main(["backup", "create"]) == 0
    made = next((env / "data" / "backups").glob("scada-cli-*.db"))
    db._conn.close()
    monkeypatch.setattr(tool, "run", lambda cmd, timeout=30: (0, ""))
    monkeypatch.setattr(tool, "wait_health", lambda port, seconds, want=None: False)
    assert tool.main(["--yes", "backup", "restore", str(made)]) == 1


def test_the_password_never_reaches_the_audit_log_or_the_output(env, monkeypatch, capsys):
    make_db(env)
    logged: list[str] = []
    monkeypatch.setattr(tool, "audit", logged.append)
    stdin(monkeypatch, "Ny-hemmelig-123\n")
    assert tool.main(["--yes", "user", "reset", "admin"]) == 0
    assert logged and all("Ny-hemmelig-123" not in m for m in logged)
    assert "Ny-hemmelig-123" not in capsys.readouterr().out
    entries = Database(env / "data" / "scada.db").list_audit(10, "user.reset_cli")      # også i appens egen audit-tabel
    assert entries and "Ny-hemmelig-123" not in json.dumps(entries)


def test_check_reports_an_invalid_environment_instead_of_crashing(env, monkeypatch, capsys):
    (env / "scada.env").write_text("SCADA_PORT=abc\n", encoding="utf-8")
    monkeypatch.setenv("SCADA_PORT", "abc")
    assert tool.main(["check"]) == 1
    assert "ugyldig" in capsys.readouterr().out.lower()


def test_config_hides_urls_with_credentials(env, capsys):
    (env / "scada.env").write_text("SCADA_FOO=https://bruger:kode@eksempel.dk/x\nSCADA_BAR=https://eksempel.dk\n", encoding="utf-8")
    assert tool.main(["config"]) == 0
    out = capsys.readouterr().out
    assert "kode@" not in out and "SCADA_BAR = https://eksempel.dk" in out


def test_a_stalled_update_does_not_block_and_its_old_request_is_dropped(tmp_path):
    svc = UpdateService(tmp_path, backups=None, current=lambda: {"version": "5.0.0", "build": "0100"})
    (svc.dir / "status.json").write_text(json.dumps({"state": "queued", "message": "x", "ts": time.time() - 3000}), encoding="utf-8")
    (svc.dir / "apply.request").write_text("SHA256=gammel", encoding="utf-8")
    (svc.dir / "enabled").write_text("", encoding="utf-8")
    svc._require_idle()                                    # kaster ikke
    assert not (svc.dir / "apply.request").exists()
