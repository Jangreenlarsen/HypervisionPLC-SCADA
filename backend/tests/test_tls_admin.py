"""System › Certifikater (v3.25.0): kryptografi, validering, API og root-hjælperen (apply-tls.sh + cert-deploy.sh) ende til ende."""

import base64
import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import tls_admin as ta
from app.services.errors import ServiceError
from app.services.tls_admin import TlsAdmin

ADMIN_PW = "Admin-Test-123!"
REPO = Path(__file__).resolve().parents[2]
SH, OPENSSL = shutil.which("sh"), shutil.which("openssl")


def _ca():
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1)
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(key, hashes.SHA256()))
    return key, cert


def _sign(csr_pem: bytes, ca, days: int = 365, start: int = -1):
    ca_key, ca_cert = ca
    csr = x509.load_pem_x509_csr(csr_pem)
    now = datetime.now(timezone.utc)
    b = (x509.CertificateBuilder().subject_name(csr.subject).issuer_name(ca_cert.subject).public_key(csr.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(now + timedelta(days=start)).not_valid_after(now + timedelta(days=days)))
    for ext in csr.extensions:
        b = b.add_extension(ext.value, ext.critical)
    return b.sign(ca_key, hashes.SHA256())


# ------------------------------------------------------------------ kryptografi og validering

def test_self_signed_has_sans_name_and_lifetime():
    cert_pem, key_pem = ta.self_signed({"cn": "scada.local", "sans": "scada.local, 10.1.1.31", "days": 825, "key_type": "ec256"})
    cert = x509.load_pem_x509_certificate(cert_pem)
    assert ta.sans_of(cert) == ["scada.local", "10.1.1.31"]
    d = ta.describe(cert)
    assert d["self_signed"] and d["kind"] == "selfsigned" and d["cn"] == "scada.local" and d["key"] == "EC secp256r1"
    assert 824 <= (cert.not_valid_after_utc - cert.not_valid_before_utc).days <= 825
    assert ta.order_chain(serialization.load_pem_private_key(key_pem, None), [cert])[0] == cert


@pytest.mark.parametrize("body,msg", [
    ({"cn": "x", "sans": []}, "mindst ét"),
    ({"cn": "x", "sans": ["bad name!"]}, "Ugyldigt"),
    ({"cn": "x", "sans": ["a"], "days": 0}, "Gyldighed"),
    ({"cn": "x", "sans": ["a"], "days": 5000}, "Gyldighed"),
    ({"cn": "x", "sans": ["a"], "key_type": "dsa"}, "nøgletype"),
    ({"cn": "", "sans": ["a"]}, "'cn'"),
    ({"cn": "x", "sans": ["a"], "c": "DNK"}, "landekode"),
])
def test_validation(body, msg):
    with pytest.raises(ServiceError, match=msg):
        ta.self_signed(body)


def test_chain_is_ordered_and_wrong_key_and_expired_are_refused():
    ca = _ca()
    csr, key_pem = ta.make_csr({"cn": "scada.example.com", "o": "Laces", "c": "dk", "sans": ["scada.example.com"]})
    leaf = _sign(csr, ca)
    key = serialization.load_pem_private_key(key_pem, None)
    assert ta.order_chain(key, [ca[1], leaf]) == [leaf, ca[1]]
    with pytest.raises(ServiceError, match="passer ikke"):
        ta.order_chain(ec.generate_private_key(ec.SECP256R1()), [leaf])
    with pytest.raises(ServiceError, match="udløbet"):
        ta.check_leaf(_sign(csr, ca, days=-1, start=-10))
    assert "udløber om" in ta.check_leaf(_sign(csr, ca, days=3))[0]


def test_encrypted_pem_key_needs_the_right_password():
    _, key_pem = ta.self_signed({"cn": "a", "sans": ["a"]})
    key = serialization.load_pem_private_key(key_pem, None)
    enc = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(b"pw-123"))
    with pytest.raises(ServiceError, match="krypteret"):
        ta.load_key(enc, None)
    with pytest.raises(ServiceError, match="forkert adgangskode"):
        ta.load_key(enc, "nej")
    assert ta.load_key(enc, "pw-123").private_numbers() == key.private_numbers()


# ------------------------------------------------------------------ tjenesten med en falsk root-hjælper

class FakeHelper:
    """Svarer på tls.request som root-hjælperen: lægger parret som 'installeret' og skriver cert.pem/tls-apply.json."""

    def __init__(self, cfg: Path, state: Path, ok: bool = True):
        self.cfg, self.state, self.ok, self.stop, self.seen = cfg, state, ok, False, []
        self.t = threading.Thread(target=self.run, daemon=True)
        self.t.start()

    def run(self):
        while not self.stop:
            req = self.cfg / "tls.request"
            if req.exists():
                rid, action = req.read_text().split()
                req.unlink()
                self.seen.append(action)
                pend = self.cfg / "tls-pending"
                if action == "install" and pend.exists():
                    self.seen.append((pend / "privkey.pem").read_bytes())
                    (self.state / "cert.pem").write_bytes((pend / "fullchain.pem").read_bytes())
                    shutil.rmtree(pend)
                (self.state / "tls-apply.json").write_text(json.dumps({"id": rid, "ok": self.ok, "message": "ok" if self.ok else "FEJL: nginx afviste"}))
            time.sleep(0.05)


@pytest.fixture
def svc(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    s = TlsAdmin(tmp_path / "data", state, apply_timeout_s=5)
    h = FakeHelper(tmp_path / "data" / "config", state)
    (tmp_path / "data" / "config").mkdir(parents=True)
    yield s, h
    h.stop = True


def test_csr_then_signed_certificate_is_installed_with_the_pending_key(svc):
    s, h = svc
    pend = s.create_csr({"cn": "scada.example.com", "sans": ["scada.example.com", "10.1.1.31"]})
    assert "BEGIN CERTIFICATE REQUEST" in pend["pem"] and pend["sans"] == ["scada.example.com", "10.1.1.31"]
    assert oct((s.dir / "csr-key.pem").stat().st_mode)[-3:] == "600" or os.name == "nt"
    ca = _ca()
    leaf = _sign(pend["pem"].encode(), ca)
    pem = (ca[1].public_bytes(serialization.Encoding.PEM) + leaf.public_bytes(serialization.Encoding.PEM))
    r = s.install_signed(pem)
    assert r["cert"]["cn"] == "scada.example.com" and r["cert"]["kind"] == "ca" and r["chain"] == 1
    assert s.pending() is None and not (s.dir / "csr-key.pem").exists()
    assert h.seen[0] == "install" and b"PRIVATE KEY" in h.seen[1]
    with pytest.raises(ServiceError, match="ingen ventende"):
        s.install_signed(pem)
    assert s.metrics()["ops"] == {"csr|ok": 1, "signed|ok": 1}


def test_pkcs12_import_and_helper_failure_keeps_error(svc):
    s, h = svc
    cert_pem, key_pem = ta.self_signed({"cn": "imp", "sans": ["imp.local"]})
    p12 = pkcs12.serialize_key_and_certificates(b"x", serialization.load_pem_private_key(key_pem, None),
                                                x509.load_pem_x509_certificate(cert_pem), None,
                                                serialization.BestAvailableEncryption(b"Hemmelig-p12"))
    with pytest.raises(ServiceError, match="PKCS#12"):
        s.import_pkcs12(p12, "forkert")
    assert s.import_pkcs12(p12, "Hemmelig-p12")["cert"]["cn"] == "imp"
    h.ok = False
    with pytest.raises(ServiceError, match="nginx afviste"):
        s.create_self_signed({"cn": "x", "sans": ["x"]})
    assert s.last["ok"] is False and s.metrics()["ops"]["selfsigned|error"] == 1


def test_only_one_change_at_a_time(tmp_path):
    s = TlsAdmin(tmp_path / "data", tmp_path, apply_timeout_s=1)
    s._lock.acquire()
    try:
        with pytest.raises(ServiceError, match="i gang") as e:
            s.create_self_signed({"cn": "x", "sans": ["x"]})
        assert e.value.status == 409
    finally:
        s._lock.release()


def test_no_helper_gives_a_clear_error_and_cleans_up(tmp_path):
    s = TlsAdmin(tmp_path / "data", tmp_path, apply_timeout_s=0.3)
    with pytest.raises(ServiceError, match="Root-hjælperen svarede ikke") as e:
        s.create_self_signed({"cn": "x", "sans": ["x"]})
    assert e.value.status == 504
    assert not (tmp_path / "data" / "config" / "tls-pending").exists() and not (tmp_path / "data" / "config" / "tls.request").exists()


# ------------------------------------------------------------------ API

@pytest.fixture
def api(tmp_path):
    s = Settings(data_dir=tmp_path, frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, net_state_dir=tmp_path / "state")
    (tmp_path / "state").mkdir()
    with TestClient(create_app(s)) as c:
        c.app.state.tls_admin.apply_timeout_s = 5
        h = FakeHelper(tmp_path / "config", tmp_path / "state")
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        yield c
        h.stop = True


def test_api_admin_only_and_secrets_never_returned(api):
    assert TestClient(api.app).get("/api/system/tls").status_code == 401
    r = api.post("/api/system/tls/selfsigned", json={"cn": "scada.local", "sans": ["scada.local"]})
    assert r.status_code == 200, r.text
    assert r.json()["cert"]["cn"] == "scada.local" and "PRIVATE" not in r.text
    assert "BEGIN CERTIFICATE" in api.get("/api/system/tls/cert.pem").text
    cert_pem, key_pem = ta.self_signed({"cn": "p", "sans": ["p"]})
    key = serialization.load_pem_private_key(key_pem, None)
    p12 = pkcs12.serialize_key_and_certificates(b"x", key, x509.load_pem_x509_certificate(cert_pem), None,
                                                serialization.BestAvailableEncryption(b"P12-Hemmelig"))
    r = api.post("/api/system/tls/import", json={"format": "pkcs12", "p12": base64.b64encode(p12).decode(), "password": "P12-Hemmelig"})
    assert r.status_code == 200, r.text
    r = api.post("/api/system/tls/import", json={"format": "pem", "cert": cert_pem.decode(), "key": key_pem.decode()})
    assert r.status_code == 200, r.text
    assert api.post("/api/system/tls/import", json={"format": "x"}).status_code == 400
    assert api.post("/api/system/tls/signed", json={"cert": cert_pem.decode()}).status_code == 409
    audit = api.get("/api/audit").text if api.get("/api/audit").status_code == 200 else ""
    assert "P12-Hemmelig" not in audit and "PRIVATE KEY" not in audit
    from app.services.metrics import render  # noqa: PLC0415
    details = api.portal.call(api.app.state.health_service.details, api.app.state)
    assert 'scada_tls_operations_total{action="pkcs12",result="ok"} 1' in render(details)


# ------------------------------------------------------------------ root-hjælperen ende til ende (sh + openssl)

@pytest.mark.skipif(SH is None or OPENSSL is None, reason="sh/openssl findes ikke")
def test_helper_installs_keeps_prev_restores_and_rejects_bad_pairs(tmp_path):
    data, state, priv, tlsdir = tmp_path / "data", tmp_path / "state", tmp_path / "priv", tmp_path / "tls"
    (data / "config").mkdir(parents=True)
    state.mkdir()
    true = tmp_path / "true.sh"
    true.write_bytes(b"#!/bin/sh\nexit 0\n")
    true.chmod(0o755)
    env = {**os.environ, "DATA": data.as_posix(), "STATE": state.as_posix(), "PRIV": priv.as_posix(), "TLSDIR": tlsdir.as_posix(),
           "HOOK": (REPO / "deploy" / "cert-deploy.sh").as_posix(), "NGINX": true.as_posix(), "SYSTEMCTL": true.as_posix()}

    def run(rid, action, cert=None, key=None):
        if cert is not None:
            p = data / "config" / "tls-pending"
            p.mkdir()
            (p / "fullchain.pem").write_bytes(cert)
            (p / "privkey.pem").write_bytes(key)
        (data / "config" / "tls.request").write_bytes(f"{rid} {action}\n".encode())
        r = subprocess.run([SH, (REPO / "deploy" / "apply-tls.sh").as_posix()], env=env, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        res = json.loads((state / "tls-apply.json").read_text())
        assert res["id"] == rid
        return res

    c1, k1 = ta.self_signed({"cn": "first", "sans": ["first"]})
    c2, k2 = ta.self_signed({"cn": "second", "sans": ["second"]})
    assert run("0000000a", "install", c1, k1)["ok"]
    assert "CN=first" in x509.load_pem_x509_certificate((state / "cert.pem").read_bytes()).subject.rfc4514_string()
    r = run("0000000b", "install", c2, k1)                      # nøglen passer ikke
    assert not r["ok"] and "passer ikke" in r["message"]
    assert run("0000000c", "install", c2, k2)["ok"]
    meta = json.loads((state / "cert.json").read_text())
    assert meta["has_prev"] and meta["has_selfsigned"]
    assert run("0000000d", "restore-prev")["ok"]
    assert "CN=first" in x509.load_pem_x509_certificate((state / "cert.pem").read_bytes()).subject.rfc4514_string()
    assert not run("0000000e", "rm-rf")["ok"]
    assert not (data / "config" / "tls-pending").exists() and not (data / "config" / "tls.request").exists()
    assert not any(priv.iterdir())                              # ingen nøgler ligger tilbage i hjælperens arbejdsmappe
    # afvist: symlink (eller for stor fil, hvor symlinks ikke kan laves) i stedet for nøglen
    p = data / "config" / "tls-pending"
    p.mkdir()
    (p / "fullchain.pem").write_bytes(c1)
    try:
        (p / "privkey.pem").symlink_to(tlsdir / "privkey.pem")
    except OSError:
        (p / "privkey.pem").write_bytes(b"x" * 70000)
    (data / "config" / "tls.request").write_bytes(b"0000000f install\n")
    subprocess.run([SH, (REPO / "deploy" / "apply-tls.sh").as_posix()], env=env, capture_output=True, timeout=60)
    res = json.loads((state / "tls-apply.json").read_text())
    assert res["id"] == "0000000f" and not res["ok"]
    # ugyldigt id: intet svar
    (data / "config" / "tls.request").write_bytes(b"../x install\n")
    subprocess.run([SH, (REPO / "deploy" / "apply-tls.sh").as_posix()], env=env, capture_output=True, timeout=60)
    assert json.loads((state / "tls-apply.json").read_text())["id"] == "0000000f"


# ------------------------------------------------------------------ Let's Encrypt (tjenesten + root-hjælperen)

def test_le_requests_are_validated_queued_one_at_a_time_and_token_is_write_only(tmp_path):
    s = TlsAdmin(tmp_path / "data", tmp_path)
    cfg = tmp_path / "data" / "config"
    with pytest.raises(ServiceError, match="offentligt DNS-navn"):
        s.le_issue({"method": "http", "host": "10.1.1.31", "email": "a@b.dk"})
    with pytest.raises(ServiceError, match="Metode"):
        s.le_issue({"method": "ftp", "host": "a.dk", "email": "a@b.dk"})
    with pytest.raises(ServiceError, match="Tokenet"):
        s.le_dns({"zone": "x.dedyn.io", "token": "kort"})
    s.le_issue({"method": "http", "host": "scada.laces.dk", "email": "jan@laces.dk", "dry_run": True})
    rid, *rest = (cfg / "le.request").read_text().split()
    assert rest == ["issue", "http", "scada.laces.dk", "jan@laces.dk", "dry"]
    with pytest.raises(ServiceError, match="allerede i gang") as e:
        s.le_install()
    assert e.value.status == 409
    with pytest.raises(ServiceError, match="allerede i gang"):
        s.le_dns({"zone": "x.dedyn.io", "token": "TESTTOKEN_abcdefghijklmnop1234"})
    assert not (cfg / "le-token").exists()                            # 409 → tokenet skrives slet ikke
    old = time.time() - 300
    os.utime(cfg / "le.request", (old, old))                          # en anmodning ingen hjælper henter, glemmes efter 2 min
    s.le_dns({"zone": "Mitnavn.dedyn.io", "token": "TESTTOKEN_abcdefghijklmnop1234"})
    assert (cfg / "le.request").read_text().split()[1:] == ["dns-config", "mitnavn.dedyn.io", "scada-acme"]
    assert (cfg / "le-token").read_text().strip() == "TESTTOKEN_abcdefghijklmnop1234"
    assert "TESTTOKEN" not in json.dumps(s.le_status())


@pytest.mark.skipif(SH is None, reason="sh findes ikke")
def test_le_helper_validates_runs_and_reports(tmp_path):
    data, state, priv, conf = tmp_path / "data", tmp_path / "state", tmp_path / "priv", tmp_path / "conf"
    (data / "config").mkdir(parents=True)
    calls = tmp_path / "calls"
    fake = tmp_path / "le.sh"
    fake.write_bytes(b'#!/bin/sh\necho "$@" >> "' + calls.as_posix().encode() + b'"\n[ "$1" = set-token ] && cat >> "'
                     + calls.as_posix().encode() + b'"\n[ "$2" = fail.dk ] && { echo "FEJL: certbot fejlede"; exit 1; }\necho "Done."\nexit 0\n')
    fake.chmod(0o755)
    env = {**os.environ, "DATA": data.as_posix(), "STATE": state.as_posix(), "PRIV": priv.as_posix(), "LE": fake.as_posix(),
           "LE_CONF": conf.as_posix(), "CERTBOT_LIVE": (tmp_path / "live").as_posix(), "SYSTEMCTL": "false"}

    def run(line, token=None):
        if token is not None:
            (data / "config" / "le-token").write_bytes(token)
        (data / "config" / "le.request").write_bytes(line.encode() + b"\n")
        r = subprocess.run([SH, (REPO / "deploy" / "apply-letsencrypt.sh").as_posix()], env=env, capture_output=True, timeout=60)
        assert r.returncode == 0, r.stderr
        return json.loads((state / "le-status.json").read_text())

    st = run("0000000a issue http scada.laces.dk jan@laces.dk dry")
    assert st["state"] == "ok" and st["id"] == "0000000a"
    assert calls.read_text().splitlines()[-1] == "issue scada.laces.dk jan@laces.dk --method http --dry-run"
    assert json.loads((state / "le-info.json").read_text())["last"] is None            # en prøve gemmes ikke som "seneste"
    assert run("0000000b issue http fail.dk a@b.dk live")["state"] == "error"
    assert "FEJL" in run("0000000c issue http fail.dk a@b.dk live")["message"]
    for bad in ("0000000d issue http -d a@b.dk live", "0000000e issue smtp a.dk a@b.dk live", "0000000f issue http a.dk a@b.dk live extra",
                "00000010 dns-config bad_zone x", "00000011 rm -rf"):
        assert run(bad)["state"] == "error", bad
    st = run("00000012 dns-config mitnavn.dedyn.io scada-acme", token=b"TESTTOKEN_abcdefghijklmnop1234\n")
    assert st["state"] == "ok"
    assert calls.read_text().splitlines()[-2:] == ["set-token", "TESTTOKEN_abcdefghijklmnop1234"] or "set-target mitnavn.dedyn.io scada-acme" in calls.read_text()
    assert not (data / "config" / "le-token").exists() and not (priv / "le.token").exists()
    assert "TESTTOKEN" not in (state / "le-run.log").read_text() + (state / "le-status.json").read_text()
    assert run("00000013 issue dns scada.laces.dk jan@laces.dk live")["state"] == "ok"
    assert json.loads((state / "le-info.json").read_text())["last"]["host"] == "scada.laces.dk"
