"""OTA-opdatering: kontrol af pakken (sikker tar, version, nødvendige filer), API (kun admin, status, upload, bekræftelse,
anmodning til hjælperen) og at hjælperens scripts er gyldige shell."""

import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, read_version
from app.main import create_app
from app.services import updates
from app.services.errors import ServiceError
from app.services.updates import inspect_package, relation

ADMIN_PW = "test-admin-pw-1"
REPO = Path(__file__).resolve().parents[2]
FILES = {
    "version.json": None,   # sættes pr. pakke
    "deploy/install.sh": b"#!/bin/sh\n", "deploy/apply-update.sh": b"#!/bin/sh\n",
    "backend/app/main.py": b"# main\n", "backend/requirements.txt": b"fastapi\n", "frontend/dist/index.html": b"<html></html>",
}


def make_tar(path: Path, version="99.0.0", build="9999", *, drop=(), extra=(), mode="w", raw_version=None) -> Path:
    with tarfile.open(path, mode) as tar:
        for name, data in FILES.items():
            if name in drop:
                continue
            if name == "version.json":
                data = raw_version if raw_version is not None else json.dumps({"version": version, "build": build}).encode()
            info = tarfile.TarInfo(f"scada/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for info, data in extra:
            tar.addfile(info, io.BytesIO(data) if data is not None else None)
    return path


def member(name, kind=tarfile.REGTYPE, size=0, link=""):
    info = tarfile.TarInfo(name)
    info.type, info.size, info.linkname = kind, size, link
    return info


# ------------------------------------------------------------------ kontrol af pakken

def test_valid_package_is_described_with_version_checksum_and_size(tmp_path):
    p = make_tar(tmp_path / "p.tar")
    info = inspect_package(p)
    assert (info["version"], info["build"], info["files"]) == ("99.0.0", "9999", len(FILES))
    assert len(info["sha256"]) == 64 and info["size"] == p.stat().st_size


@pytest.mark.parametrize("mode,name", [("w:gz", "p.tar.gz"), ("w:bz2", "p.tar.bz2")])
def test_compressed_packages_are_accepted(tmp_path, mode, name):
    assert inspect_package(make_tar(tmp_path / name, mode=mode))["version"] == "99.0.0"


@pytest.mark.parametrize("name", ["/etc/passwd", "scada/../../etc/passwd", "../x", "scada\\evil", "C:/evil"])
def test_unsafe_paths_are_rejected(tmp_path, name):
    p = make_tar(tmp_path / "p.tar", extra=[(member(name, size=1), b"x")])
    with pytest.raises(ServiceError, match="usikker sti|under 'scada/'"):
        inspect_package(p)


def test_only_files_and_directories_are_allowed(tmp_path):
    for info in (member("scada/link", tarfile.SYMTYPE, link="/etc/passwd"), member("scada/hard", tarfile.LNKTYPE, link="scada/version.json"),
                 member("scada/dev", tarfile.CHRTYPE)):
        p = make_tar(tmp_path / "p.tar", extra=[(info, None)])
        with pytest.raises(ServiceError, match="andet end filer og mapper"):
            inspect_package(p)


def test_everything_must_be_under_scada_prefix(tmp_path):
    with pytest.raises(ServiceError, match="under 'scada/'"):
        inspect_package(make_tar(tmp_path / "p.tar", extra=[(member("andet/fil.txt", size=1), b"x")]))


@pytest.mark.parametrize("missing", ["version.json", "deploy/install.sh", "deploy/apply-update.sh", "frontend/dist/index.html", "backend/app/main.py"])
def test_missing_required_files_are_named(tmp_path, missing):
    with pytest.raises(ServiceError, match="mangler"):
        inspect_package(make_tar(tmp_path / "p.tar", drop=(missing,)))


@pytest.mark.parametrize("raw", [b"ikke json", b"{}", b'{"version": "1.2", "build": "0001"}', b'{"version": "1.2.3", "build": "x"}',
                                 b'{"version": "1.2.3; rm -rf /", "build": "0001"}', b'["liste"]'])
def test_bad_version_json_is_rejected(tmp_path, raw):
    with pytest.raises(ServiceError, match="version.json"):
        inspect_package(make_tar(tmp_path / "p.tar", raw_version=raw))


def test_empty_corrupt_and_oversized_files_are_rejected_with_clear_messages(tmp_path, monkeypatch):
    empty = tmp_path / "e.tar"
    empty.write_bytes(b"")
    with pytest.raises(ServiceError, match="Ingen fil"):
        inspect_package(empty)
    junk = tmp_path / "j.tar"
    junk.write_bytes(b"det her er ikke en tar-fil" * 100)
    with pytest.raises(ServiceError, match="ikke en gyldig tar"):
        inspect_package(junk)
    cut = tmp_path / "c.tar"
    cut.write_bytes(make_tar(tmp_path / "ok.tar").read_bytes()[:700])
    with pytest.raises(ServiceError, match="ikke en gyldig tar|beskadiget"):
        inspect_package(cut)
    monkeypatch.setattr(updates, "MAX_PACKAGE_BYTES", 100)
    with pytest.raises(ServiceError) as exc:
        inspect_package(make_tar(tmp_path / "big.tar"))
    assert exc.value.status == 413 if hasattr(exc.value, "status") else True


def test_relation_compares_version_then_build():
    cur = {"version": "0.49.0", "build": "0070"}
    assert relation(cur, {"version": "0.49.1", "build": "0071"}) == "newer"
    assert relation(cur, {"version": "0.49.0", "build": "0071"}) == "newer"
    assert relation(cur, {"version": "0.49.0", "build": "0070"}) == "same"
    assert relation(cur, {"version": "0.48.9", "build": "0099"}) == "older"
    assert relation(cur, {"version": "0.10.0", "build": "0001"}) == "older"      # 10 > 9 som tal, ikke som tekst
    assert relation({"version": "ukendt", "build": "ukendt"}, cur) == "unknown"


def test_relation_with_debug_versions():
    """Fejlsøgning bruger MAJOR.MINOR.PATCH.D (CLAUDE.md): 0.63.1.1 er nyere end 0.63.1, og 0.63.2 er nyere end 0.63.1.3."""
    assert relation({"version": "0.63.1", "build": "0092"}, {"version": "0.63.1.1", "build": "0093"}) == "newer"
    assert relation({"version": "0.63.1.1", "build": "0093"}, {"version": "0.63.1.1", "build": "0093"}) == "same"
    assert relation({"version": "0.63.1.3", "build": "0095"}, {"version": "0.63.2", "build": "0096"}) == "newer"
    assert relation({"version": "0.63.1.2", "build": "0094"}, {"version": "0.63.1.1", "build": "0093"}) == "older"
    assert relation({"version": "0.63.1", "build": "0092"}, {"version": "0.63.1.1.1", "build": "0093"}) == "unknown"


# ------------------------------------------------------------------ API

@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        assert c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW}).status_code == 200
        c.updates = tmp_path / "updates"
        yield c


def enable(api):
    (api.updates / "enabled").write_text("")


def upload(api, path: Path):
    return api.post("/api/system/update/upload", content=path.read_bytes(), headers={"content-type": "application/octet-stream"})


def test_only_admin_can_see_or_use_updates(api, tmp_path):
    enable(api)
    pkg = make_tar(tmp_path / "p.tar")
    assert api.post("/api/users", json={"username": "tek", "role": "engineer", "password": "Hemmelig-123"}).status_code in (200, 201)
    other = TestClient(api.app)
    other.post("/api/auth/login", json={"username": "tek", "password": "Hemmelig-123"})
    for r in (other.get("/api/system/update"), other.post("/api/system/update/upload", content=pkg.read_bytes()),
              other.post("/api/system/update/apply", json={"sha256": "a" * 64}), other.delete("/api/system/update/staged")):
        assert r.status_code == 403, r.text
    anon = TestClient(api.app)
    assert anon.get("/api/system/update").status_code == 401


def test_status_without_the_helper_installed_says_not_enabled_and_refuses_upload(api, tmp_path):
    s = api.get("/api/system/update").json()
    assert s["enabled"] is False and s["state"] == "idle" and s["staged"] is None and s["current"] == read_version()
    r = upload(api, make_tar(tmp_path / "p.tar"))
    assert r.status_code == 409 and "ikke aktiveret" in r.json()["error"]


def test_upload_stages_a_checked_package_and_status_shows_it(api, tmp_path):
    enable(api)
    r = upload(api, make_tar(tmp_path / "p.tar", "99.1.0", "0123"))
    assert r.status_code == 200, r.text
    info = r.json()
    assert (info["version"], info["build"], info["relation"], info["uploaded_by"]) == ("99.1.0", "0123", "newer", "admin")
    s = api.get("/api/system/update").json()
    assert s["enabled"] and s["staged"]["sha256"] == info["sha256"] and s["staged"]["relation"] == "newer"
    assert not (api.updates / "incoming.tar").exists()                       # den midlertidige fil ryddes altid
    audit = api.get("/api/audit?action=system.update.upload").json()
    assert audit and audit[0]["detail"]["sha256"] == info["sha256"]


def test_bad_upload_is_rejected_with_the_specific_reason_and_leaves_nothing_behind(api, tmp_path):
    enable(api)
    r = upload(api, make_tar(tmp_path / "p.tar", drop=("deploy/install.sh",)))
    assert r.status_code == 400 and "deploy/install.sh" in r.json()["error"]
    r = api.post("/api/system/update/upload", content=b"ikke en tar", headers={"content-type": "application/octet-stream"})
    assert r.status_code == 400 and "gyldig tar" in r.json()["error"]
    assert api.get("/api/system/update").json()["staged"] is None
    assert not (api.updates / "incoming.tar").exists() and not (api.updates / "staged.tar").exists()
    assert api.get("/api/audit?action=system.update.upload").json()[0]["result"] == "error"


def test_too_large_upload_is_refused_by_content_length(api, monkeypatch):
    enable(api)
    monkeypatch.setattr("app.api.system.MAX_PACKAGE_BYTES", 50)
    r = api.post("/api/system/update/upload", content=b"x" * 200, headers={"content-type": "application/octet-stream"})
    assert r.status_code == 413 and "for stor" in r.json()["error"]


def test_apply_makes_a_backup_and_hands_a_request_to_the_helper(api, tmp_path):
    enable(api)
    info = upload(api, make_tar(tmp_path / "p.tar", "99.1.0", "0123")).json()
    # forkert kontrolsum afvises — adminen skal have set den pakke der installeres
    r = api.post("/api/system/update/apply", json={"sha256": "0" * 64})
    assert r.status_code == 409 and "Kontrolsummen" in r.json()["error"]
    assert not (api.updates / "apply.request").exists()
    r = api.post("/api/system/update/apply", json={"sha256": info["sha256"].upper()})      # store/små bogstaver er ens
    assert r.status_code == 200, r.text
    assert r.json()["queued"] and r.json()["backup"].startswith("scada-pre-update-")
    req = dict(line.split("=", 1) for line in (api.updates / "apply.request").read_text().split())
    assert req == {"SHA256": info["sha256"], "BY": "admin", "VERSION": "99.1.0", "BUILD": "0123"}
    assert (tmp_path / "backups" / r.json()["backup"]).is_file()
    s = api.get("/api/system/update").json()
    assert s["state"] == "queued" and s["busy"] and s["last"]["to"] == "99.1.0"
    assert api.get("/api/audit?action=system.update.apply").json()[0]["target"] == "99.1.0"


def test_nothing_can_change_while_an_update_is_queued_or_applying(api, tmp_path):
    enable(api)
    pkg = make_tar(tmp_path / "p.tar", "99.1.0", "0123")
    sha = upload(api, pkg).json()["sha256"]
    assert api.post("/api/system/update/apply", json={"sha256": sha}).status_code == 200
    for r in (api.post("/api/system/update/apply", json={"sha256": sha}), upload(api, pkg), api.delete("/api/system/update/staged")):
        assert r.status_code == 409 and "i gang" in r.json()["error"], r.text
    # hjælperen melder færdig (som den gør: den sletter anmodningen og skriver status)
    (api.updates / "apply.request").unlink()
    (api.updates / "status.json").write_text(json.dumps({"state": "done", "message": "ok", "from": "a", "to": "b", "by": "admin", "ts": 9e9}))
    s = api.get("/api/system/update").json()
    assert s["state"] == "done" and not s["busy"] and s["last"]["message"] == "ok"
    assert api.delete("/api/system/update/staged").status_code == 204


def test_older_package_is_never_installed_and_same_version_needs_confirmation(api, tmp_path):
    enable(api)
    old = upload(api, make_tar(tmp_path / "o.tar", "0.0.1", "0001")).json()
    assert old["relation"] == "older"
    r = api.post("/api/system/update/apply", json={"sha256": old["sha256"], "reinstall": True})
    assert r.status_code == 409 and "nedgradering" in r.json()["error"].lower()
    cur = read_version()
    same = upload(api, make_tar(tmp_path / "s.tar", cur["version"], cur["build"])).json()
    assert same["relation"] == "same"
    r = api.post("/api/system/update/apply", json={"sha256": same["sha256"]})
    assert r.status_code == 409 and "geninstalleres" in r.json()["error"]
    assert api.post("/api/system/update/apply", json={"sha256": same["sha256"], "reinstall": True}).status_code == 200


def test_apply_without_a_staged_package_and_discard(api, tmp_path):
    enable(api)
    r = api.post("/api/system/update/apply", json={"sha256": "a" * 64})
    assert r.status_code == 409 and "ingen klargjort pakke" in r.json()["error"]
    upload(api, make_tar(tmp_path / "p.tar"))
    assert api.delete("/api/system/update/staged").status_code == 204
    assert api.get("/api/system/update").json()["staged"] is None and not (api.updates / "staged.tar").exists()


def test_a_helper_that_never_answers_is_reported_as_stalled(api):
    enable(api)
    (api.updates / "status.json").write_text(json.dumps({"state": "applying", "message": "x", "from": "a", "to": "b", "by": "u", "ts": 1}))
    s = api.get("/api/system/update").json()
    assert s["state"] == "stalled" and s["busy"] is False      # kan forsøges igen: en ny pakke kan uploades


def test_log_tail_is_returned(api):
    (api.updates / "update.log").write_text("\n".join(f"linje {i}" for i in range(100)))
    log = api.get("/api/system/update").json()["log"]
    assert len(log) == 40 and log[-1] == "linje 99"


# ------------------------------------------------------------------ scripts

@pytest.mark.parametrize("script", ["install.sh", "apply-update.sh", "make-package.sh"])
def test_deploy_scripts_are_valid_shell(script):
    sh = Path("C:/Program Files/Git/usr/bin/sh.exe")
    exe = str(sh) if sh.exists() else "sh"
    try:
        r = subprocess.run([exe, "-n", str(REPO / "deploy" / script)], capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        pytest.skip("sh findes ikke på denne maskine")
    assert r.returncode == 0, r.stderr


def test_helper_is_installed_outside_the_replaced_program_directory_and_removes_its_request_first():
    install = (REPO / "deploy" / "install.sh").read_text(encoding="utf-8")
    assert "/usr/local/lib/hypervisionplc-scada/apply-update.sh" in install and "--update" in install
    helper = (REPO / "deploy" / "apply-update.sh").read_text(encoding="utf-8")
    assert helper.index('rm -f "$REQ"') < helper.index('sh "$WORK/scada/deploy/install.sh"')   # ellers udløser .path-enheden igen og igen
    assert "sha256sum" in helper and "rollback" in helper and "/api/health" in helper
    assert "PathExists=/var/lib/hypervisionplc-scada/updates/apply.request" in (REPO / "deploy" / "hypervisionplc-scada-update.path").read_text(encoding="utf-8")
