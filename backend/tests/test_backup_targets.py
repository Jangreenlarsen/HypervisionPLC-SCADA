"""Backup-tidsplan og eksterne destinationer (v3.23.0)."""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import backup_targets as bt
from app.services.backup_targets import BackupScheduler, TargetError, expected_interval_h, next_run, validate_schedule, validate_target
from app.services.errors import ServiceError
from app.services.schedule_engine import TZ
from app.storage.secrets import SecretStore

ADMIN_PW = "test-admin-pw-1"


def ts(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=TZ).timestamp()


# ------------------------------------------------------------------ tidsplan

def test_schedule_validation():
    assert validate_schedule({"mode": "daily", "time": "03:15"})["time"] == "03:15"
    for bad in ({"mode": "x"}, {"mode": "daily", "time": "25:00"}, {"mode": "interval", "every_h": 0},
                {"mode": "weekly", "days": []}, {"mode": "weekly", "days": [7]}, {"mode": "weekly", "days": [True]}, "nej"):
        with pytest.raises(ServiceError):
            validate_schedule(bad)


def test_next_run_interval_daily_weekly_and_missed():
    now = ts(2026, 11, 4, 12, 0)            # onsdag
    assert next_run({"mode": "off"}, None, now) is None
    assert next_run({**bt.DEFAULT_SCHEDULE, "every_h": 6}, now - 3600, now) == now + 5 * 3600
    assert next_run({**bt.DEFAULT_SCHEDULE, "every_h": 6}, None, now) == now + bt.STARTUP_DELAY_S
    daily = {**bt.DEFAULT_SCHEDULE, "mode": "daily", "time": "02:30"}
    assert next_run(daily, ts(2026, 11, 4, 2, 31), now) == ts(2026, 11, 5, 2, 30)
    assert next_run(daily, ts(2026, 11, 2, 2, 30), now) == ts(2026, 11, 3, 2, 30)     # gik glip af (slukket) → ligger før nu
    weekly = {**bt.DEFAULT_SCHEDULE, "mode": "weekly", "time": "01:00", "days": [0, 4]}   # mandag og fredag
    assert next_run(weekly, ts(2026, 11, 3, 1, 0), now) == ts(2026, 11, 6, 1, 0)


def test_next_run_follows_daylight_saving():
    daily = {**bt.DEFAULT_SCHEDULE, "mode": "daily", "time": "02:30"}
    before = ts(2026, 10, 25, 2, 30)                                # vintertid fra kl. 03 samme nat
    after = next_run(daily, before, before)
    assert datetime.fromtimestamp(after, TZ).strftime("%d %H:%M") == "26 02:30"
    assert after - before == 25 * 3600


def test_expected_interval():
    assert expected_interval_h({"mode": "off"}) == 0
    assert expected_interval_h({"mode": "daily"}) == 24
    assert expected_interval_h({"mode": "interval", "every_h": 6}) == 6
    assert expected_interval_h({"mode": "weekly", "days": [0, 4]}) == 96                # fredag → mandag
    assert expected_interval_h({"mode": "weekly", "days": [2]}) == 168


# ------------------------------------------------------------------ validering

def test_target_validation():
    ok = validate_target({"name": "NAS", "method": "sftp", "host": "nas.local", "username": "backup", "path": "scada/pi"})
    assert ok["port"] == 22 and ok["keep"] == 7 and ok["host_key"] is None
    for bad in ({"name": "x", "method": "sftp", "host": "h", "username": "u"},
                {"name": "NAS", "method": "telnet"},
                {"name": "NAS", "method": "sftp", "host": "h;rm -rf", "username": "u"},
                {"name": "NAS", "method": "sftp", "host": "h", "username": "u", "path": "../etc"},
                {"name": "NAS", "method": "sftp", "host": "h", "username": "u", "port": 70000},
                {"name": "NAS", "method": "https", "url": "http://x"},
                {"name": "NAS", "method": "https", "url": "https://x", "keep": 3},
                {"name": "NAS", "method": "smb", "host": "h", "username": "u", "share": "a/b"},
                {"name": "NAS", "method": "nfs", "export": "nas:/x/../y"},
                {"name": "NAS", "method": "ftp", "host": "h", "username": "u", "send_config": False, "send_trends": False}):
        with pytest.raises(ServiceError):
            validate_target(bad)
    assert validate_target({"name": "Web", "method": "https", "url": "https://x/dav/", "keep": 0})["url"] == "https://x/dav"


# ------------------------------------------------------------------ tjenesten med en falsk transport

class FakeBackup:
    def __init__(self, d: Path):
        self.backup_dir = d / "backups"
        self.backup_dir.mkdir(parents=True)
        self.trend_db = object()
        self.trend_keep = 2
        self.n = 0

    def save_to_server(self, kind, by):
        self.n += 1
        name = f"scada-auto-20261104-1200{self.n:02d}.json"
        (self.backup_dir / name).write_text("{}")
        return name

    def save_trend_snapshot(self):
        name = f"trends-auto-20261104-1200{self.n:02d}.db.gz"
        (self.backup_dir / name).write_bytes(b"x" * 100)
        return name

    def list_server_backups(self):
        return []


class FakeRemote(bt._Transport):
    store: dict[str, bytes] = {}
    fail: str | None = None

    def put(self, local, name):
        if FakeRemote.fail:
            raise TargetError(FakeRemote.fail)
        FakeRemote.store[name] = local.read_bytes()

    def list(self):
        return list(FakeRemote.store)

    def delete(self, name):
        FakeRemote.store.pop(name, None)


@pytest.fixture
def sched(tmp_path, monkeypatch):
    monkeypatch.setattr(bt, "RETRY_DELAYS_S", (0.0, 0.0))
    FakeRemote.store, FakeRemote.fail = {}, None
    s = BackupScheduler(tmp_path, SecretStore(tmp_path / "secrets.json"), FakeBackup(tmp_path), config_dir=tmp_path / "config")
    s.transport_factory = lambda t, seen=None: FakeRemote(t, s._secret(t["id"]))
    return s


def _target(s, **kw):
    return s.create({"name": "NAS", "method": "sftp", "host": "nas.local", "username": "backup", "password": "Hemmelig-123", **kw})


@pytest.mark.anyio
async def test_run_sends_files_and_prunes_only_own_files(sched):
    t = _target(sched, keep=2)
    FakeRemote.store["andet.txt"] = b"fremmed"
    for _ in range(3):
        r = await sched.run_once()
        assert r["result"] == "ok" and r["failed"] == 0
    names = sorted(FakeRemote.store)
    assert names.count("andet.txt") == 1                                             # fremmede filer røres aldrig
    assert len([n for n in names if n.startswith("scada-auto-")]) == 2 and len([n for n in names if n.startswith("trends-auto-")]) == 2
    pub = sched.public(sched._get(t["id"]))
    assert pub["last"]["ok"] and pub["uploads"] == {"ok": 3, "error": 0} and pub["has_password"]
    assert sched._section(bt.STATE_SECTION)["last_run"] > time.time() - 10


@pytest.mark.anyio
async def test_only_chosen_contents_are_sent(sched):
    _target(sched, send_trends=False)
    await sched.run_once()
    assert all(n.startswith("scada-auto-") for n in FakeRemote.store)


@pytest.mark.anyio
async def test_failures_are_retried_counted_and_never_leak_the_password(sched):
    t = _target(sched)
    FakeRemote.fail = "login afvist for backup med Hemmelig-123"
    r = await sched.run_once()
    assert r["result"] == "error" and r["failed"] == 1
    last = sched.results[t["id"]]
    assert not last["ok"] and "Hemmelig-123" not in last["error"] and "***" in last["error"]
    assert sched.failing() == {}                                                     # én fejl er ikke nok
    await sched.run_once()
    assert sched.failing() == {"NAS": last["error"]}
    m = sched.metrics()
    assert m["uploads"]["NAS"]["error"] == 2 and m["failing"]["NAS"] == 1 and m["runs"]["error"] == 2
    FakeRemote.fail = None
    await sched.run_once()
    assert sched.failing() == {} and m is not sched.metrics() and sched.metrics()["failing"]["NAS"] == 0


@pytest.mark.anyio
async def test_one_run_at_a_time(sched):
    async with sched._run_lock:
        with pytest.raises(ServiceError) as exc:
            await sched.run_once()
        assert exc.value.status == 409


def test_secrets_are_write_only_and_removed_with_the_target(sched, tmp_path):
    t = _target(sched)
    pub = sched.public(sched._get(t["id"]))
    assert "Hemmelig-123" not in json.dumps(pub) and "password" not in pub
    assert "Hemmelig-123" not in (tmp_path / "config").read_text() if (tmp_path / "config").is_file() else True
    key = sched.make_ssh_key(t["id"])["public_key"]
    assert key.startswith("ssh-ed25519 ")
    assert "PRIVATE" not in json.dumps(sched.list_public())
    sched.delete(t["id"])
    assert sched.secrets.get_secret("backup_targets", f"{t['id']}.password") is None
    assert sched.secrets.get_secret("backup_targets", f"{t['id']}.private_key") is None


def test_changing_host_resets_the_trusted_host_key(sched):
    t = _target(sched)
    sched._set_host_key(t["id"], {"type": "ssh-ed25519", "key": "AAAA", "fingerprint": "ssh-ed25519 SHA256:x"})
    assert sched.public(sched._get(t["id"]))["host_key"] == "ssh-ed25519 SHA256:x"
    sched.update(t["id"], {"name": "NAS 2"})
    assert sched._get(t["id"])["host_key"] is not None
    sched.update(t["id"], {"host": "andet.local"})
    assert sched._get(t["id"])["host_key"] is None


def test_duplicate_names_and_limit(sched):
    _target(sched)
    with pytest.raises(ServiceError) as exc:
        _target(sched)
    assert exc.value.status == 409


def test_nfs_targets_are_requested_from_the_root_helper_and_refused_when_not_mounted(sched, tmp_path):
    t = sched.create({"name": "NFS", "method": "nfs", "export": "nas.local:/volume1/backup"})
    req = (tmp_path / "config" / "backup-mounts.request").read_text()
    assert req.strip() == f"{t['id']} nas.local:/volume1/backup"
    with pytest.raises(TargetError, match="ikke monteret"):
        bt._Local(sched._get(t["id"]), sched._secret(t["id"]), tmp_path / "mnt")


@pytest.mark.anyio
async def test_test_connection_writes_and_removes_a_probe(sched):
    t = _target(sched)
    r = await sched.test(t["id"])
    assert r == {"ok": True, "error": "", "host_key": None} and FakeRemote.store == {}


@pytest.mark.anyio
async def test_scheduler_loop_runs_when_forced(sched):
    task = asyncio.create_task(sched.run())
    await asyncio.sleep(0.05)
    sched.run_now()
    for _ in range(100):
        await asyncio.sleep(0.02)
        if sched.runs["ok"]:
            break
    task.cancel()
    assert sched.runs["ok"] == 1


# ------------------------------------------------------------------ real SFTP-transport mod en lokal paramiko-server

def test_sftp_refuses_unknown_and_changed_host_keys(sched):
    import paramiko
    seen = []
    t = {**sched._get(_target(sched)["id"]), "host": "127.0.0.1"}

    class FakeT:
        def __init__(self, sock):
            pass
        banner_timeout = auth_timeout = 0

        def start_client(self, timeout):
            pass

        def get_remote_server_key(self):
            return key

        def close(self):
            pass

    key = paramiko.Ed25519Key.from_private_key(__import__("io").StringIO(_pem()))
    orig_conn, orig_t = bt.socket.create_connection, paramiko.Transport
    bt.socket.create_connection = lambda *a, **k: None
    paramiko.Transport = FakeT
    try:
        with pytest.raises(TargetError, match="ikke godkendt"):
            bt._ssh_connect(t, sched._secret(t["id"]), seen)
        assert seen[0]["type"] == "ssh-ed25519"
        with pytest.raises(TargetError, match="ÆNDRET"):
            bt._ssh_connect({**t, "host_key": {"type": "ssh-ed25519", "key": "andet"}}, sched._secret(t["id"]))
    finally:
        bt.socket.create_connection, paramiko.Transport = orig_conn, orig_t


def _pem():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH,
                                                      serialization.NoEncryption()).decode()


# ------------------------------------------------------------------ API

@pytest.fixture
def api(tmp_path):
    s = Settings(data_dir=tmp_path, frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=24)
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        yield c


def test_api_admin_only_write_only_secrets_and_audit(api):
    assert TestClient(api.app).get("/api/backup/targets").status_code == 401
    r = api.post("/api/backup/targets", json={"name": "FTP-server", "method": "ftps", "host": "ftp.example.com", "username": "u",
                                              "password": "Super-hemmelig-9"})
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["has_password"] and "Super-hemmelig-9" not in r.text
    assert "Super-hemmelig-9" not in api.get("/api/backup/targets").text
    log = api.get("/api/audit").text if api.get("/api/audit").status_code == 200 else ""
    assert "Super-hemmelig-9" not in log
    assert api.patch(f"/api/backup/targets/{t['id']}", json={"keep": 3}).json()["keep"] == 3
    assert api.patch(f"/api/backup/targets/{t['id']}", json={"port": "x"}).status_code == 400
    assert api.delete(f"/api/backup/targets/{t['id']}").status_code == 204
    assert api.get("/api/backup/targets").json() == []


def test_api_schedule_default_follows_backup_hours_and_can_be_changed(api):
    s = api.get("/api/backup/schedule").json()
    assert s["mode"] == "interval" and s["every_h"] == 24 and s["next_run"] is not None
    r = api.put("/api/backup/schedule", json={"mode": "weekly", "time": "03:00", "days": [6]})
    assert r.status_code == 200 and r.json()["expected_interval_h"] == 168
    assert api.put("/api/backup/schedule", json={"mode": "weekly", "days": []}).status_code == 400
    assert api.get("/api/health/details").json()["backup"]["interval_h"] == 168


# ------------------------------------------------------------------ root-hjælperen (NFS-montering)

import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

SH = shutil.which("sh")
MOUNT_SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "apply-backup-mounts.sh"


@pytest.mark.skipif(SH is None, reason="sh findes ikke")
def test_mount_helper_validates_mounts_and_unmounts(tmp_path):
    data, state, root = tmp_path / "data", tmp_path / "state", tmp_path / "mnt"
    (data / "config").mkdir(parents=True)
    state.mkdir()
    calls = tmp_path / "calls"
    for name in ("mount", "umount"):
        f = tmp_path / name
        f.write_text(f'#!/bin/sh\necho "{name} $*" >> "{calls.as_posix()}"\n')
        f.chmod(0o755)
    mounts = tmp_path / "mounts"
    mounts.write_bytes(f"nas:/old {root.as_posix()}/0000aaaa nfs4 rw 0 0\nnas:/keep {root.as_posix()}/1111bbbb nfs rw 0 0\n/dev/sda1 / ext4 rw 0 0\n".encode())
    (data / "config" / "backup-mounts.request").write_text(
        "1111bbbb nas:/keep\r\n2222cccc nas.local:/volume1/backup\nzzzz nas:/x\n3333dddd nas:/a/../etc\n4444eeee nas:/x -o exec\n", newline="")
    env = {**os.environ, "MOUNT": (tmp_path / "mount").as_posix(), "UMOUNT": (tmp_path / "umount").as_posix(),
           "MOUNTS": mounts.as_posix(), "ROOT": root.as_posix(), "DATA": data.as_posix(), "STATE": state.as_posix()}
    r = subprocess.run([SH, MOUNT_SCRIPT.as_posix()], env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    done = calls.read_text().splitlines()
    assert done == [f"umount -l {root.as_posix()}/0000aaaa",
                    f"mount -t nfs -o soft,timeo=150,retrans=2,nosuid,nodev,noexec,_netdev -- nas.local:/volume1/backup {root.as_posix()}/2222cccc"]
    status = json.loads((state / "backup-mounts.json").read_text())
    assert set(status) == {"1111bbbb", "2222cccc"} and all(v["ok"] for v in status.values())
    assert not (data / "config" / "backup-mounts.request").exists()
    assert "afvist linje" in (state / "backup-mounts.log").read_text()


# ------------------------------------------------------------------ rettelser efter gennemgang

def test_nfs_path_cannot_escape_the_mount_and_symlinks_are_refused(sched, tmp_path, monkeypatch):
    t = sched.create({"name": "NFS", "method": "nfs", "export": "nas.local:/v", "path": "/abs/sti"})
    root = tmp_path / "mnt"
    (root / t["id"]).mkdir(parents=True)
    monkeypatch.setattr(bt.os.path, "ismount", lambda p: True)
    loc = bt._Local(sched._get(t["id"]), sched._secret(t["id"]), root)
    assert loc.dir == root / t["id"] / "abs/sti"                                    # absolut sti → inde i monteringen
    src = tmp_path / "f.json"
    src.write_text("{}")
    loc.put(src, "scada-auto-20261104-120000.json")
    assert (loc.dir / "scada-auto-20261104-120000.json").read_text() == "{}"


def test_export_starting_with_dash_is_rejected():
    with pytest.raises(ServiceError):
        validate_target({"name": "NFS", "method": "nfs", "export": "-oexec:/x"})


@pytest.mark.anyio
async def test_host_key_is_only_trusted_if_it_matches_the_fingerprint_shown(sched):
    t = _target(sched)
    shown = {"type": "ssh-ed25519", "key": "AAAA", "fingerprint": "ssh-ed25519 SHA256:vist"}
    now_key = {"type": "ssh-ed25519", "key": "BBBB", "fingerprint": "ssh-ed25519 SHA256:angriber"}

    def factory(target, seen=None):
        if not target.get("host_key"):
            seen.append(now_key)
            raise bt.HostKeyError("Værtsnøglen er ikke godkendt endnu")
        return FakeRemote(target, sched._secret(target["id"]))

    sched.transport_factory = factory
    r = await sched.test(t["id"])
    assert not r["ok"] and r["host_key"] == "ssh-ed25519 SHA256:angriber"
    r = await sched.test(t["id"], trust_fingerprint=shown["fingerprint"])
    assert not r["ok"] and "ikke den, du godkendte" in r["error"] and sched._get(t["id"])["host_key"] is None
    r = await sched.test(t["id"], trust_fingerprint=now_key["fingerprint"])
    assert r["ok"] and sched._get(t["id"])["host_key"]["key"] == "BBBB"
