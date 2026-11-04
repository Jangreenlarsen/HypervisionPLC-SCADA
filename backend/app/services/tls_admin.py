"""System › Certifikater (v3.25.0): nginx' TLS-certifikat fra GUI'en — selvsigneret, CSR + signeret certifikat, import af PKCS#12/PEM,
gendan forrige/selvsigneret.

Kryptografien sker her (cryptography); INSTALLATIONEN sker altid af root-hjælperen `deploy/apply-tls.sh` (udløst af en .path-enhed):
tjenesten lægger et færdigt par i `<data>/config/tls-pending/` og skriver `<data>/config/tls.request` ("<id> <handling>"). Hjælperen
flytter parret ind i en root-mappe, validerer igen og bruger `cert-deploy.sh` (kontrol af parret, `.prev`/`.selfsigned`, `nginx -t`,
gendannelse ved fejl — ingen lockout). Resultatet skrives til `<state>/tls-apply.json`; det offentlige certifikat til `<state>/cert.pem`.

Private nøgler og adgangskoder returneres og logges aldrig. Den ventende CSR-nøgle ligger i `<data>/tls/` (0600) til det signerede
certifikat er installeret.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import secrets as pysecrets
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .errors import ServiceError

log = logging.getLogger("scada.tls")

KEY_TYPES = ("ec256", "rsa2048", "rsa4096")
DEFAULT_DAYS = 825
MAX_DAYS = 3650
MAX_UPLOAD = 64 * 1024
MAX_SANS = 20
APPLY_TIMEOUT_S = 90
SHORT_LIFE_DAYS = 14
ACTIONS = ("install", "restore-prev", "restore-selfsigned")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ validering


def parse_sans(raw: Any) -> list[x509.GeneralName]:
    """Liste af værtsnavne/IP'er → SAN-poster. Tom liste afvises (browsere kræver SAN)."""
    if isinstance(raw, str):
        raw = re.split(r"[\s,]+", raw)
    if not isinstance(raw, list):
        raise ServiceError(400, "SAN-navne skal være en liste")
    out: list[x509.GeneralName] = []
    seen: set[str] = set()
    for item in raw:
        s = str(item).strip().lower()
        if not s or s in seen:
            continue
        seen.add(s)
        try:
            out.append(x509.IPAddress(ipaddress.ip_address(s)))
            continue
        except ValueError:
            pass
        if not re.fullmatch(r"(\*\.)?[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*", s) or len(s) > 253:
            raise ServiceError(400, f"Ugyldigt værtsnavn eller IP-adresse: {s[:80]}")
        out.append(x509.DNSName(s))
    if not out:
        raise ServiceError(400, "Angiv mindst ét værtsnavn eller én IP-adresse")
    if len(out) > MAX_SANS:
        raise ServiceError(400, f"Højst {MAX_SANS} navne")
    return out


def _text(body: dict[str, Any], key: str, maxlen: int = 64, required: bool = False) -> str:
    v = body.get(key, "")
    v = "" if v is None else str(v).strip()
    if required and not v:
        raise ServiceError(400, f"Feltet '{key}' skal udfyldes")
    if len(v) > maxlen or any(ord(c) < 32 for c in v):
        raise ServiceError(400, f"Feltet '{key}' er for langt eller indeholder ugyldige tegn")
    return v


def build_name(body: dict[str, Any], cn_required: bool = True) -> x509.Name:
    attrs = [x509.NameAttribute(NameOID.COMMON_NAME, _text(body, "cn", 64, cn_required))]
    for key, oid in (("o", NameOID.ORGANIZATION_NAME), ("ou", NameOID.ORGANIZATIONAL_UNIT_NAME), ("l", NameOID.LOCALITY_NAME),
                     ("st", NameOID.STATE_OR_PROVINCE_NAME), ("email", NameOID.EMAIL_ADDRESS)):
        if v := _text(body, key, 128):
            attrs.append(x509.NameAttribute(oid, v))
    if c := _text(body, "c", 8):
        if not re.fullmatch(r"[A-Za-z]{2}", c):
            raise ServiceError(400, "Land skal være en landekode på to bogstaver (fx DK)")
        attrs.append(x509.NameAttribute(NameOID.COUNTRY_NAME, c.upper()))
    return x509.Name(attrs)


def make_key(key_type: str) -> Any:
    if key_type == "ec256":
        return ec.generate_private_key(ec.SECP256R1())
    if key_type in ("rsa2048", "rsa4096"):
        return rsa.generate_private_key(public_exponent=65537, key_size=int(key_type[3:]))
    raise ServiceError(400, f"Ukendt nøgletype (vælg {', '.join(KEY_TYPES)})")


def _key_pem(key: Any) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def _pub(key_or_cert: Any) -> bytes:
    pub = key_or_cert.public_key()
    return pub.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


def _server_exts(builder: Any, sans: list[x509.GeneralName], ca: bool = False) -> Any:
    return (builder.add_extension(x509.SubjectAlternativeName(sans), critical=False)
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False))


def self_signed(body: dict[str, Any]) -> tuple[bytes, bytes]:
    """→ (certifikat-PEM, nøgle-PEM)."""
    sans = parse_sans(body.get("sans", []))
    days = body.get("days", DEFAULT_DAYS)
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= MAX_DAYS:
        raise ServiceError(400, f"Gyldighed skal være 1-{MAX_DAYS} dage")
    key = make_key(str(body.get("key_type") or "ec256"))
    name = build_name(body)
    now = _now()
    b = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=days)))
    b = _server_exts(b, sans).add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
    cert = b.sign(key, hashes.SHA256())
    return cert.public_bytes(serialization.Encoding.PEM), _key_pem(key)


def make_csr(body: dict[str, Any]) -> tuple[bytes, bytes]:
    """→ (CSR-PEM, nøgle-PEM)."""
    sans = parse_sans(body.get("sans", []))
    key = make_key(str(body.get("key_type") or "ec256"))
    csr = (x509.CertificateSigningRequestBuilder().subject_name(build_name(body))
           .add_extension(x509.SubjectAlternativeName(sans), critical=False).sign(key, hashes.SHA256()))
    return csr.public_bytes(serialization.Encoding.PEM), _key_pem(key)


def load_certs(data: bytes) -> list[x509.Certificate]:
    try:
        certs = x509.load_pem_x509_certificates(data)
    except ValueError:
        try:
            certs = [x509.load_der_x509_certificate(data)]
        except ValueError:
            raise ServiceError(400, "Filen indeholder ikke et læsbart certifikat (PEM eller DER)") from None
    return certs


def load_key(data: bytes, password: str | None) -> Any:
    pw = password.encode() if password else None
    try:
        return serialization.load_pem_private_key(data, pw)
    except TypeError:
        raise ServiceError(400, "Nøglen er krypteret — angiv adgangskoden" if pw is None else "Nøglen er ikke krypteret — lad adgangskoden stå tom") from None
    except ValueError:
        raise ServiceError(400, "Nøglen kunne ikke læses (forkert adgangskode eller ikke en PEM-nøgle)") from None


def order_chain(key: Any, certs: list[x509.Certificate]) -> list[x509.Certificate]:
    """Find certifikatet til nøglen (leaf) og sortér resten efter udsteder → emne. Afviser, hvis intet certifikat passer."""
    pub = _pub(key)
    leaf = next((c for c in certs if _pub(c) == pub), None)
    if leaf is None:
        raise ServiceError(400, "Nøglen passer ikke til nogen af certifikaterne")
    rest = [c for c in certs if c is not leaf]
    chain = [leaf]
    while rest:
        nxt = next((c for c in rest if c.subject == chain[-1].issuer), None)
        if nxt is None or chain[-1].issuer == chain[-1].subject:
            break
        chain.append(nxt)
        rest.remove(nxt)
    return chain + rest


def check_leaf(leaf: x509.Certificate) -> list[str]:
    """Afvis et certifikat, der ikke er gyldigt nu; advarsler (tekst) ved kort restlevetid eller manglende SAN."""
    now = _now()
    if leaf.not_valid_before_utc > now:
        raise ServiceError(400, f"Certifikatet er først gyldigt fra {leaf.not_valid_before_utc:%Y-%m-%d %H:%M} UTC")
    if leaf.not_valid_after_utc <= now:
        raise ServiceError(400, f"Certifikatet er udløbet ({leaf.not_valid_after_utc:%Y-%m-%d})")
    warnings = []
    if (leaf.not_valid_after_utc - now).days < SHORT_LIFE_DAYS:
        warnings.append(f"Certifikatet udløber om {(leaf.not_valid_after_utc - now).days} dage")
    if not sans_of(leaf):
        warnings.append("Certifikatet har ingen SAN-navne — moderne browsere afviser det")
    return warnings


def sans_of(cert: x509.Certificate) -> list[str]:
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return []
    return [str(v) for v in ext.get_values_for_type(x509.DNSName)] + [str(v) for v in ext.get_values_for_type(x509.IPAddress)]


def _name(n: x509.Name) -> str:
    return n.rfc4514_string()[:300]


def _key_desc(cert: x509.Certificate) -> str:
    pub = cert.public_key()
    if isinstance(pub, ec.EllipticCurvePublicKey):
        return f"EC {pub.curve.name}"
    if isinstance(pub, rsa.RSAPublicKey):
        return f"RSA {pub.key_size}"
    return type(pub).__name__


def describe(cert: x509.Certificate) -> dict[str, Any]:
    self_signed_ = cert.subject == cert.issuer
    issuer = _name(cert.issuer)
    kind = "selfsigned" if self_signed_ else "letsencrypt" if "Let's Encrypt" in issuer else "ca"
    cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    return {"subject": _name(cert.subject), "cn": str(cn[0].value) if cn else "", "issuer": issuer, "sans": sans_of(cert),
            "not_before": cert.not_valid_before_utc.timestamp(), "not_after": cert.not_valid_after_utc.timestamp(),
            "fingerprint": cert.fingerprint(hashes.SHA256()).hex(":").upper(), "self_signed": self_signed_, "kind": kind,
            "key": _key_desc(cert)}


def _clean(msg: str) -> str:
    """Fejltekst fra hjælperen/biblioteker: printbar, kort, uden PEM-blokke."""
    msg = re.sub(r"-----BEGIN[^-]*-----.*?-----END[^-]*-----", "[PEM]", msg, flags=re.S)
    return "".join(c for c in msg if c.isprintable())[:300]


# ------------------------------------------------------------------ tjeneste


class TlsAdmin:
    def __init__(self, data_dir: Path, state_dir: Path, config_dir: Path | None = None, apply_timeout_s: float = APPLY_TIMEOUT_S):
        self.dir = data_dir / "tls"
        self.config_dir = config_dir or (data_dir / "config")
        self.state_dir = state_dir
        self.apply_timeout_s = apply_timeout_s
        self._lock = threading.Lock()
        self.ops: dict[tuple[str, str], int] = {}
        self.last: dict[str, Any] | None = None

    # ---------- læs

    def current(self) -> dict[str, Any]:
        """Certifikatet nginx bruger (fra `<state>/cert.pem`, skrevet af cert-deploy.sh) + om forrige/selvsigneret kan gendannes."""
        info: dict[str, Any] = {"cert": None, "chain": 0, "has_prev": False, "has_selfsigned": False}
        try:
            meta = json.loads((self.state_dir / "cert.json").read_text(encoding="utf-8"))
            info["has_prev"] = bool(meta.get("has_prev"))
            info["has_selfsigned"] = bool(meta.get("has_selfsigned"))
        except (OSError, ValueError):
            pass
        try:
            certs = load_certs((self.state_dir / "cert.pem").read_bytes())
            info["cert"] = describe(certs[0])
            info["chain"] = len(certs) - 1
        except (OSError, ServiceError):
            pass
        return info

    def cert_pem(self) -> bytes:
        try:
            return (self.state_dir / "cert.pem").read_bytes()
        except OSError:
            raise ServiceError(404, "Certifikatet kan ikke læses (er nginx/TLS installeret?)") from None

    def pending(self) -> dict[str, Any] | None:
        try:
            csr = x509.load_pem_x509_csr((self.dir / "csr.pem").read_bytes())
        except (OSError, ValueError):
            return None
        try:
            sans = [str(v.value) for v in csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value]
        except x509.ExtensionNotFound:
            sans = []
        return {"subject": _name(csr.subject), "sans": sans, "created": (self.dir / "csr.pem").stat().st_mtime,
                "pem": csr.public_bytes(serialization.Encoding.PEM).decode()}

    def status(self) -> dict[str, Any]:
        return {**self.current(), "pending_csr": self.pending(), "last": self.last}

    # ---------- handlinger (blokerende: kaldes i en tråd)

    def create_self_signed(self, body: Any) -> dict[str, Any]:
        cert, key = self_signed(self._body(body))
        return self._install("selfsigned", cert, key, [])

    def create_csr(self, body: Any) -> dict[str, Any]:
        csr, key = make_csr(self._body(body))
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, 0o700)
        self._write_private(self.dir / "csr-key.pem", key)
        (self.dir / "csr.pem").write_bytes(csr)
        self._count("csr", "ok")
        log.info("CSR oprettet (%s)", x509.load_pem_x509_csr(csr).subject.rfc4514_string())
        return self.pending() or {}

    def cancel_csr(self) -> None:
        self._drop_csr()
        self._count("csr_cancel", "ok")

    def _drop_csr(self) -> None:
        for n in ("csr-key.pem", "csr.pem"):
            (self.dir / n).unlink(missing_ok=True)

    def install_signed(self, data: bytes) -> dict[str, Any]:
        self._size(data)
        try:
            key = serialization.load_pem_private_key((self.dir / "csr-key.pem").read_bytes(), None)
        except (OSError, ValueError):
            raise ServiceError(409, "Der er ingen ventende CSR — opret en CSR først") from None
        chain = order_chain(key, load_certs(data))
        warnings = check_leaf(chain[0])
        result = self._install("signed", self._chain_pem(chain), _key_pem(key), warnings)
        self._drop_csr()
        return result

    def import_pkcs12(self, data: bytes, password: str | None) -> dict[str, Any]:
        self._size(data)
        try:
            key, cert, extra = pkcs12.load_key_and_certificates(data, password.encode() if password else None)
        except ValueError:
            raise ServiceError(400, "PKCS#12-filen kunne ikke åbnes (forkert adgangskode eller ikke en .p12/.pfx)") from None
        if key is None or cert is None:
            raise ServiceError(400, "PKCS#12-filen skal indeholde både certifikat og privat nøgle")
        chain = order_chain(key, [cert, *(extra or [])])
        return self._install("pkcs12", self._chain_pem(chain), _key_pem(key), check_leaf(chain[0]))

    def import_pem(self, cert_data: bytes, key_data: bytes, password: str | None) -> dict[str, Any]:
        self._size(cert_data)
        self._size(key_data)
        key = load_key(key_data, password)
        chain = order_chain(key, load_certs(cert_data))
        return self._install("pem", self._chain_pem(chain), _key_pem(key), check_leaf(chain[0]))

    def restore(self, which: str) -> dict[str, Any]:
        action = {"prev": "restore-prev", "selfsigned": "restore-selfsigned"}.get(which)
        if action is None:
            raise ServiceError(400, "Ukendt gendannelse")
        return self._apply(f"restore_{which}", action, [])

    # ---------- intern

    @staticmethod
    def _body(body: Any) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise ServiceError(400, "Forventede et JSON-objekt")
        return body

    @staticmethod
    def _size(data: bytes) -> None:
        if not data:
            raise ServiceError(400, "Filen er tom")
        if len(data) > MAX_UPLOAD:
            raise ServiceError(413, f"Filen er for stor (højst {MAX_UPLOAD // 1024} KB)")

    @staticmethod
    def _chain_pem(chain: list[x509.Certificate]) -> bytes:
        return b"".join(c.public_bytes(serialization.Encoding.PEM) for c in chain)

    @staticmethod
    def _write_private(path: Path, data: bytes) -> None:
        path.unlink(missing_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)

    def _count(self, action: str, result: str) -> None:
        self.ops[(action, result)] = self.ops.get((action, result), 0) + 1

    def _install(self, source: str, cert: bytes, key: bytes, warnings: list[str]) -> dict[str, Any]:
        def prepare() -> None:
            pending = self.config_dir / "tls-pending"
            tmp = self.config_dir / "tls-pending.tmp"
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(mode=0o700)
            self._write_private(tmp / "privkey.pem", key)
            self._write_private(tmp / "fullchain.pem", cert)
            shutil.rmtree(pending, ignore_errors=True)
            tmp.rename(pending)
        return self._apply(source, "install", warnings, prepare)

    def _apply(self, source: str, action: str, warnings: list[str], prepare: Any = None) -> dict[str, Any]:
        """Bed root-hjælperen om handlingen og vent på dens svar (samme id) i `<state>/tls-apply.json`. Én ad gangen."""
        if not self._lock.acquire(blocking=False):
            raise ServiceError(409, "En anden certifikatændring er i gang")
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            if prepare:
                prepare()
            req_id = pysecrets.token_hex(4)
            tmp = self.config_dir / "tls.request.tmp"
            tmp.write_text(f"{req_id} {action}\n", encoding="utf-8")
            tmp.replace(self.config_dir / "tls.request")
            deadline = time.monotonic() + self.apply_timeout_s
            res: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                try:
                    r = json.loads((self.state_dir / "tls-apply.json").read_text(encoding="utf-8"))
                    if r.get("id") == req_id:
                        res = r
                        break
                except (OSError, ValueError):
                    pass
                time.sleep(0.5)
            if res is None:                                   # oprydning under låsen: en ny handling kan ikke nå at starte imellem
                shutil.rmtree(self.config_dir / "tls-pending", ignore_errors=True)
                (self.config_dir / "tls.request").unlink(missing_ok=True)
                self._count(source, "error")
                self.last = {"at": time.time(), "source": source, "ok": False, "message": "Root-hjælperen svarede ikke"}
                log.error("Certifikat (%s): root-hjælperen svarede ikke inden %d s", source, self.apply_timeout_s)
                raise ServiceError(504, "Root-hjælperen svarede ikke (er hypervisionplc-scada-tls.path installeret? Kør install.sh)")
            ok = bool(res.get("ok"))
            msg = _clean(str(res.get("message", "")))
            self._count(source, "ok" if ok else "error")
            self.last = {"at": time.time(), "source": source, "ok": ok, "message": msg}
        finally:
            self._lock.release()
        if not ok:
            log.warning("Certifikat (%s) blev ikke installeret: %s", source, msg)
            raise ServiceError(400, f"Certifikatet blev ikke installeret: {msg}")
        log.info("Certifikat installeret (%s): %s", source, msg)
        return {**self.status(), "warnings": warnings, "message": msg}

    def metrics(self) -> dict[str, Any]:
        return {"ops": {f"{a}|{r}": n for (a, r), n in self.ops.items()}}
