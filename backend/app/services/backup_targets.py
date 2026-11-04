"""Backup-tidsplan og eksterne destinationer (lag 2, v3.23.0).

Én samlet tidsplan (hver N. time / dagligt / ugentligt / fra) laver den lokale backup (konfiguration + trend-snapshot, som før) og sender
filerne videre til de destinationer, der er slået til: SFTP, SCP, FTP/FTPS, HTTPS (PUT), SMB (Windows-share/NAS) og NFS (monteres af
root-hjælperen, se deploy/apply-backup-mounts.sh). Adgangskoder og SSH-nøgler er hemmeligheder: de ligger i `secrets.json`, sættes
skriv-kun og når aldrig browseren, loggen eller auditloggen. Fejltekster renses for hemmeligheder, før de gemmes eller vises.

Afsendelse sker i tråde (event-loopet må ikke blokeres), hver fil skrives som `navn.part` og omdøbes til sidst (ingen halve filer på
fjernsiden), og *behold N* rydder kun op i filer med vores egne navnemønstre.
"""

from __future__ import annotations

import asyncio
import ftplib
import io
import ipaddress
import json
import logging
import os
import re
import secrets as _secrets
import shlex
import socket
import ssl
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

import httpx

from . import sysconfig
from .errors import ServiceError
from .schedule_engine import TZ

log = logging.getLogger(__name__)

SECTION = "backup_schedule"
TARGETS_SECTION = "backup_targets"
STATE_SECTION = "backup_state"
SECRET_SECTION = "backup_targets"

METHODS = ("sftp", "scp", "ftp", "ftps", "https", "smb", "nfs")
DEFAULT_PORTS = {"sftp": 22, "scp": 22, "ftp": 21, "ftps": 21, "smb": 445}
MAX_TARGETS = 10
TIMEOUT_S = 30.0
RETRY_DELAYS_S = (10.0, 30.0)                       # to genforsøg pr. destination og kørsel
FAIL_ALARM_AFTER = 2                                # fejl i træk → problem på Status (og SYS-alarm)
STARTUP_DELAY_S = 300.0                             # en kørsel, der er gået glip af (slukket), tages 5 min efter opstart
NFS_ROOT = Path("/mnt/hv-backup")
OWN_FILE = re.compile(r"^(scada-auto-\d{8}-\d{6}\.json|trends-auto-\d{8}-\d{6}\.db\.gz)$")
HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,252})$")
NAME_RE = re.compile(r"^[\w .,()æøåÆØÅ-]{2,48}$")
PATH_RE = re.compile(r"^[\w ./()æøåÆØÅ-]{0,200}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
USER_RE = re.compile(r"^[\w.@\\-]{0,64}$")


def _bad(msg: str) -> ServiceError:
    return ServiceError(400, msg)


# ------------------------------------------------------------------------------------------------ tidsplan

DEFAULT_SCHEDULE = {"mode": "interval", "every_h": 24.0, "time": "02:30", "days": [0, 1, 2, 3, 4, 5, 6]}


def validate_schedule(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise _bad("Ugyldig tidsplan")
    mode = body.get("mode")
    if mode not in ("off", "interval", "daily", "weekly"):
        raise _bad("Tidsplanen skal være off, interval, daily eller weekly")
    out = dict(DEFAULT_SCHEDULE, mode=mode)
    if "every_h" in body:
        try:
            every = float(body["every_h"])
        except (TypeError, ValueError):
            raise _bad("Intervallet skal være et tal (timer)") from None
        if not (1 <= every <= 24 * 31):
            raise _bad("Intervallet skal være 1-744 timer")
        out["every_h"] = every
    if "time" in body:
        if not isinstance(body["time"], str) or not TIME_RE.match(body["time"]):
            raise _bad("Klokkeslættet skal være TT:MM (fx 02:30)")
        out["time"] = body["time"]
    if "days" in body:
        days = body["days"]
        if not isinstance(days, list) or not all(isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 6 for d in days):
            raise _bad("Ugedage skal være en liste med 0 (mandag) til 6 (søndag)")
        out["days"] = sorted(set(days))
    if mode == "weekly" and not out["days"]:
        raise _bad("Vælg mindst én ugedag")
    return out


def next_run(cfg: dict[str, Any], last_run: float | None, now: float) -> float | None:
    """Første planlagte tidspunkt EFTER seneste kørsel (eller efter nu, hvis der aldrig er kørt). Kan ligge før `now` = forsinket
    (fx slukket maskine) → køres snarest. Dagligt/ugentligt regnes i lokal tid (SCADA_TZ), så sommertid følger med."""
    mode = cfg.get("mode")
    if mode == "off":
        return None
    after = last_run if last_run is not None else now
    if mode == "interval":
        return (last_run + float(cfg["every_h"]) * 3600) if last_run is not None else now + STARTUP_DELAY_S
    hh, mm = (int(x) for x in cfg["time"].split(":"))
    days = set(range(7)) if mode == "daily" else set(cfg["days"])
    start = datetime.fromtimestamp(after, TZ)
    for add in range(0, 8):
        d = (start + timedelta(days=add)).date()
        cand = datetime(d.year, d.month, d.day, hh, mm, tzinfo=TZ).timestamp()
        if cand > after and d.weekday() in days:
            return cand
    return None


def expected_interval_h(cfg: dict[str, Any]) -> float:
    """Til Status' advarsel om en for gammel backup (0 = slået fra)."""
    mode = cfg.get("mode")
    if mode == "off":
        return 0.0
    if mode == "interval":
        return float(cfg["every_h"])
    if mode == "daily":
        return 24.0
    days = sorted(cfg["days"])
    gaps = [((days[(i + 1) % len(days)] - d) % 7 or 7) for i, d in enumerate(days)]
    return 24.0 * max(gaps)


# ------------------------------------------------------------------------------------------------ destinationer

FIELDS = ("name", "method", "enabled", "host", "port", "path", "username", "url", "share", "export", "auth", "verify_tls",
          "send_config", "send_trends", "keep", "http_auth")


def validate_target(body: Any, current: dict[str, Any] | None = None) -> dict[str, Any]:
    """Felterne i en destination (uden hemmeligheder). `current` = eksisterende ved ændring (kun de felter, der sendes, ændres)."""
    if not isinstance(body, dict):
        raise _bad("Ugyldig destination")
    t = dict(current or {"enabled": True, "port": None, "path": "", "username": "", "url": "", "share": "", "export": "",
                         "auth": "password", "verify_tls": True, "send_config": True, "send_trends": True, "keep": 7,
                         "http_auth": "none", "host": "", "host_key": None})
    for k in FIELDS:
        if k in body:
            t[k] = body[k]
    if t.get("method") not in METHODS:
        raise _bad(f"Metoden skal være en af: {', '.join(METHODS)}")
    if current and current["method"] != t["method"]:
        t["host_key"] = None                                  # ny metode → værtsnøglen skal godkendes igen
    if not isinstance(t.get("name"), str) or not NAME_RE.match(t["name"].strip()):
        raise _bad("Navnet skal være 2-48 tegn")
    t["name"] = t["name"].strip()
    for flag in ("enabled", "verify_tls", "send_config", "send_trends"):
        if not isinstance(t[flag], bool):
            raise _bad(f"{flag} skal være sand/falsk")
    if not (t["send_config"] or t["send_trends"]):
        raise _bad("Vælg mindst én ting at sende (konfiguration og/eller historik)")
    if not isinstance(t["keep"], int) or isinstance(t["keep"], bool) or not 0 <= t["keep"] <= 365:
        raise _bad("Behold skal være 0-365 (0 = ryd aldrig op)")
    m = t["method"]
    if m in ("sftp", "scp", "ftp", "ftps", "smb"):
        host = t.get("host")
        if not isinstance(host, str) or not host.strip() or not (HOST_RE.match(host.strip()) or _is_ip(host.strip())):
            raise _bad("Ugyldig værtsadresse")
        t["host"] = host.strip()
        port = t.get("port")
        if port in (None, ""):
            t["port"] = DEFAULT_PORTS[m]
        elif not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise _bad("Porten skal være 1-65535")
        if not isinstance(t.get("username"), str) or not t["username"].strip() or not USER_RE.match(t["username"].strip()):
            raise _bad("Brugernavn mangler eller indeholder ugyldige tegn")
        t["username"] = t["username"].strip()
    if not isinstance(t.get("path"), str) or not PATH_RE.match(t["path"]) or ".." in PurePosixPath(t["path"]).parts:
        raise _bad("Mappen må kun indeholde bogstaver, tal, mellemrum og . _ - / ( ) — og ikke ..")
    t["path"] = t["path"].strip()
    if m in ("sftp", "scp"):
        if t["auth"] not in ("password", "key"):
            raise _bad("Login skal være adgangskode eller SSH-nøgle")
    if m == "https":
        url = t.get("url")
        if not isinstance(url, str) or not url.startswith("https://") or len(url) > 500 or any(c in url for c in " \n\r\t"):
            raise _bad("Adressen skal starte med https://")
        t["url"] = url.rstrip("/")
        if t["http_auth"] not in ("none", "basic", "bearer"):
            raise _bad("HTTP-login skal være none, basic eller bearer")
        if t["http_auth"] == "basic" and (not isinstance(t.get("username"), str) or not t["username"].strip()):
            raise _bad("Brugernavn mangler (basic-login)")
        if t["keep"]:
            raise _bad("HTTPS kan ikke rydde op på fjernsiden — sæt Behold til 0")
    if m == "smb":
        share = t.get("share")
        if not isinstance(share, str) or not re.match(r"^[\w.$ -]{1,80}$", share):
            raise _bad("Share-navnet mangler eller er ugyldigt (fx backup)")
    if m == "nfs":
        export = t.get("export")
        if not isinstance(export, str) or not re.match(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,252}:/[A-Za-z0-9._/-]{0,200}$", export) or ".." in export:
            raise _bad("NFS-eksporten skal skrives som vært:/sti (fx nas.local:/volume1/backup)")
    return t


def _is_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


class TargetError(Exception):
    """Fejl ved en destination — teksten vises til brugeren (efter rensning for hemmeligheder)."""


class HostKeyError(TargetError):
    """SSH-værtsnøglen er ukendt eller ændret (kan godkendes af en administrator efter sammenligning)."""


# ------------------------------------------------------------------------------------------------ transporter (blokerende)

class _Transport:
    def __init__(self, t: dict[str, Any], secret: Callable[[str], str | None]):
        self.t, self.secret = t, secret

    def __enter__(self) -> _Transport:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        pass

    def put(self, local: Path, name: str) -> None:
        raise NotImplementedError

    def list(self) -> list[str]:
        raise NotImplementedError

    def delete(self, name: str) -> None:
        raise NotImplementedError

    def remote(self, name: str) -> str:
        return str(PurePosixPath(self.t["path"] or ".") / name)


def _ssh_connect(t: dict[str, Any], secret: Callable[[str], str | None], seen_key: list[Any] | None = None) -> Any:
    import paramiko
    sock = socket.create_connection((t["host"], t["port"]), timeout=TIMEOUT_S)
    tr = paramiko.Transport(sock)
    tr.banner_timeout = tr.auth_timeout = TIMEOUT_S
    tr.start_client(timeout=TIMEOUT_S)
    key = tr.get_remote_server_key()
    fp = f"{key.get_name()} SHA256:{key.fingerprint}" if hasattr(key, "fingerprint") else f"{key.get_name()} {key.get_base64()[:16]}"
    stored = t.get("host_key")
    if seen_key is not None:
        seen_key.append({"type": key.get_name(), "key": key.get_base64(), "fingerprint": fp})
    if stored is None:
        tr.close()
        raise HostKeyError(f"Værtsnøglen er ikke godkendt endnu ({fp}) — brug 'Test forbindelse' og godkend den")
    if stored.get("type") != key.get_name() or stored.get("key") != key.get_base64():
        tr.close()
        raise HostKeyError(f"Værtsnøglen er ÆNDRET ({fp}) — det kan være et angreb. Godkend den nye nøgle kun hvis serveren er geninstalleret")
    try:
        if t["auth"] == "key":
            pem = secret("private_key")
            if not pem:
                raise TargetError("Der er ikke lavet en SSH-nøgle til destinationen endnu")
            tr.auth_publickey(t["username"], paramiko.Ed25519Key.from_private_key(io.StringIO(pem)))
        else:
            pw = secret("password")
            if not pw:
                raise TargetError("Adgangskoden er ikke sat")
            tr.auth_password(t["username"], pw)
    except paramiko.AuthenticationException:
        tr.close()
        raise TargetError("Login afvist (brugernavn, adgangskode eller nøgle)") from None
    except BaseException:
        tr.close()
        raise
    return tr


class _Sftp(_Transport):
    def __init__(self, t: dict[str, Any], secret: Callable[[str], str | None], seen_key: list[Any] | None = None):
        super().__init__(t, secret)
        import paramiko
        self.tr = _ssh_connect(t, secret, seen_key)
        self.sftp = paramiko.SFTPClient.from_transport(self.tr)
        self.sftp.get_channel().settimeout(TIMEOUT_S)

    def close(self) -> None:
        self.tr.close()

    def put(self, local: Path, name: str) -> None:
        dst = self.remote(name)
        self.sftp.put(str(local), dst + ".part", confirm=True)
        try:
            self.sftp.posix_rename(dst + ".part", dst)
        except OSError:
            self.sftp.rename(dst + ".part", dst)

    def list(self) -> list[str]:
        return self.sftp.listdir(self.t["path"] or ".")

    def delete(self, name: str) -> None:
        self.sftp.remove(self.remote(name))


class _Scp(_Transport):
    """SCP = `scp -t` over SSH (kun til servere uden SFTP). Oprydning/listning via `ls`/`rm` med citerede stier."""

    def __init__(self, t: dict[str, Any], secret: Callable[[str], str | None], seen_key: list[Any] | None = None):
        super().__init__(t, secret)
        self.tr = _ssh_connect(t, secret, seen_key)

    def close(self) -> None:
        self.tr.close()

    def _exec(self, cmd: str, data: Callable[[Any], None] | None = None) -> str:
        ch = self.tr.open_session(timeout=TIMEOUT_S)
        ch.settimeout(TIMEOUT_S)
        ch.exec_command(cmd)
        if data:
            data(ch)
        out = b""
        while chunk := ch.recv(65536):
            out += chunk
        code = ch.recv_exit_status()
        err = ch.recv_stderr(4096).decode(errors="replace").strip()
        ch.close()
        if code != 0:
            raise TargetError(f"Fjernkommandoen fejlede ({code}): {err[:200]}")
        return out.decode(errors="replace")

    def put(self, local: Path, name: str) -> None:
        size = local.stat().st_size
        folder = self.t["path"] or "."

        def send(ch: Any) -> None:
            def ack() -> None:
                if ch.recv(1) != b"\0":
                    raise TargetError("SCP-serveren afviste filen (findes mappen, og må brugeren skrive i den?)")
            ack()
            ch.sendall(f"C0640 {size} {name}.part\n".encode())
            ack()
            with local.open("rb") as f:
                while block := f.read(65536):
                    ch.sendall(block)
            ch.sendall(b"\0")
            ack()
            ch.shutdown_write()

        self._exec(f"scp -t -- {shlex.quote(folder)}", send)
        self._exec(f"mv -f -- {shlex.quote(self.remote(name) + '.part')} {shlex.quote(self.remote(name))}")

    def list(self) -> list[str]:
        return self._exec(f"ls -1A -- {shlex.quote(self.t['path'] or '.')}").splitlines()

    def delete(self, name: str) -> None:
        self._exec(f"rm -f -- {shlex.quote(self.remote(name))}")


class _Ftp(_Transport):
    def __init__(self, t: dict[str, Any], secret: Callable[[str], str | None]):
        super().__init__(t, secret)
        if t["method"] == "ftps":
            ctx = ssl.create_default_context()
            if not t["verify_tls"]:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            self.ftp: ftplib.FTP = ftplib.FTP_TLS(context=ctx, timeout=TIMEOUT_S)
        else:
            self.ftp = ftplib.FTP(timeout=TIMEOUT_S)
        try:
            self.ftp.connect(t["host"], t["port"])
            self.ftp.login(t["username"], secret("password") or "")
            if isinstance(self.ftp, ftplib.FTP_TLS):
                self.ftp.prot_p()                          # også dataforbindelsen krypteres
            if t["path"]:
                self.ftp.cwd(t["path"])
        except ftplib.error_perm as exc:
            self.close()
            raise TargetError(f"FTP-serveren afviste: {str(exc)[:200]}") from None
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        try:
            self.ftp.quit()
        except Exception:  # noqa: BLE001
            self.ftp.close()

    def remote(self, name: str) -> str:
        return name                                        # vi står allerede i mappen (cwd)

    def put(self, local: Path, name: str) -> None:
        with local.open("rb") as f:
            self.ftp.storbinary(f"STOR {name}.part", f)
        try:
            self.ftp.delete(name)
        except ftplib.error_perm:
            pass
        self.ftp.rename(f"{name}.part", name)

    def list(self) -> list[str]:
        try:
            return [PurePosixPath(n).name for n in self.ftp.nlst()]
        except ftplib.error_perm:
            return []                                     # nogle servere svarer 550 på en tom mappe

    def delete(self, name: str) -> None:
        self.ftp.delete(name)


class _Https(_Transport):
    """HTTPS PUT til `<url>/<filnavn>` (WebDAV, Nextcloud, egen modtager). Ingen listning → ingen oprydning."""

    def put(self, local: Path, name: str) -> None:
        headers = {"Content-Type": "application/gzip" if name.endswith(".gz") else "application/json"}
        auth = None
        if self.t["http_auth"] == "bearer":
            headers["Authorization"] = f"Bearer {self.secret('password') or ''}"
        elif self.t["http_auth"] == "basic":
            auth = (self.t["username"], self.secret("password") or "")
        with local.open("rb") as f, httpx.Client(timeout=TIMEOUT_S * 4, verify=self.t["verify_tls"], trust_env=False) as c:
            r = c.put(f"{self.t['url']}/{name}", content=f, headers=headers, auth=auth)
        if r.status_code >= 300:
            raise TargetError(f"Serveren svarede HTTP {r.status_code}")

    def list(self) -> list[str]:
        return []

    def delete(self, name: str) -> None:
        pass


class _Smb(_Transport):
    def __init__(self, t: dict[str, Any], secret: Callable[[str], str | None]):
        super().__init__(t, secret)
        import smbclient
        self.smb = smbclient
        self.server = t["host"]
        smbclient.register_session(t["host"], username=t["username"], password=secret("password") or "", port=t["port"],
                                   connection_timeout=int(TIMEOUT_S), require_signing=True)
        self.base = "\\\\" + t["host"] + "\\" + t["share"] + ("\\" + t["path"].strip("/").replace("/", "\\") if t["path"].strip("/") else "")

    def close(self) -> None:
        try:
            self.smb.delete_session(self.server)
        except Exception:  # noqa: BLE001
            pass

    def remote(self, name: str) -> str:
        return self.base + "\\" + name

    def put(self, local: Path, name: str) -> None:
        with local.open("rb") as src, self.smb.open_file(self.remote(name) + ".part", mode="wb") as dst:
            while block := src.read(1024 * 1024):
                dst.write(block)
        self.smb.replace(self.remote(name) + ".part", self.remote(name))

    def list(self) -> list[str]:
        return self.smb.listdir(self.base)

    def delete(self, name: str) -> None:
        self.smb.remove(self.remote(name))


class _Local(_Transport):
    """NFS: monteret af root-hjælperen under /mnt/hv-backup/<id>; vi skriver kun, hvis det faktisk ER et monteringspunkt
    (ellers ville backuppen havne på SD-kortet)."""

    def __init__(self, t: dict[str, Any], secret: Callable[[str], str | None], root: Path):
        super().__init__(t, secret)
        mount = root / t["id"]
        if not os.path.ismount(mount):
            raise TargetError("NFS-sharet er ikke monteret (se Status for root-hjælperens svar, og at serveren eksporterer stien)")
        self.mount = mount.resolve()
        rel = t["path"].strip("/")
        self.dir = mount / rel if rel else mount
        self.dir.mkdir(parents=True, exist_ok=True)
        self._inside(self.dir)

    def _inside(self, p: Path) -> Path:
        """Stien skal ligge inde i monteringen — også efter symlinks (en NFS-server kan lægge symlinks i sharet)."""
        if not p.resolve().is_relative_to(self.mount):
            raise TargetError("Stien peger uden for NFS-sharet (symlink?) — afvist")
        return p

    def put(self, local: Path, name: str) -> None:
        part = self._inside(self.dir / (name + ".part"))
        fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o640)
        with local.open("rb") as src, os.fdopen(fd, "wb") as dst:
            while block := src.read(1024 * 1024):
                dst.write(block)
            dst.flush()
            os.fsync(dst.fileno())
        part.replace(self._inside(self.dir / name) if not (self.dir / name).is_symlink() else self.dir / name)

    def list(self) -> list[str]:
        return [p.name for p in self.dir.iterdir()]

    def delete(self, name: str) -> None:
        p = self.dir / name
        if p.is_symlink() or self._inside(p):
            p.unlink(missing_ok=True)                      # et symlink slettes selv — aldrig det, det peger på


# ------------------------------------------------------------------------------------------------ tjenesten

class BackupScheduler:
    def __init__(self, data_dir: Path, secrets: Any, backup: Any, *, default_hours: float = 24.0, nfs_root: Path = NFS_ROOT,
                 config_dir: Path | None = None, state_dir: Path | None = None):
        self.data_dir = data_dir
        self.secrets = secrets
        self.backup = backup
        self.default_hours = default_hours
        self.nfs_root = nfs_root
        self.config_dir = config_dir or (data_dir / "config")       # root-hjælperens anmodninger (NFS-montering)
        self.state_dir = state_dir                                  # root-hjælperens svar (backup-mounts.json)
        self._wake = asyncio.Event()
        self._cfg_lock = threading.RLock()                          # read-modify-write af destinationslisten
        self._run_lock = asyncio.Lock()
        self.running = False
        self.results: dict[str, dict[str, Any]] = {}                # id → seneste resultat (tid, ok, fejl, filer, bytes, varighed)
        self.fails: dict[str, int] = {}                             # id → fejl i træk
        self.runs = {"ok": 0, "partial": 0, "error": 0}
        self.uploads: dict[str, dict[str, int]] = {}                # id → {"ok": n, "error": n}
        self.last_success: dict[str, float] = {}
        self.transport_factory: Callable[..., _Transport] = self._transport   # kan udskiftes i test

    # ------------------------------------------------------------ konfiguration

    def _section(self, name: str) -> Any:
        try:
            return json.loads(sysconfig._settings_path(self.data_dir).read_text(encoding="utf-8")).get(name)
        except (OSError, ValueError):
            return None

    def schedule(self) -> dict[str, Any]:
        raw = self._section(SECTION)
        if isinstance(raw, dict):
            try:
                return validate_schedule(raw)
            except ServiceError:
                log.warning("Ugyldig backup-tidsplan i indstillingerne — bruger standard")
        if self.default_hours <= 0:
            return dict(DEFAULT_SCHEDULE, mode="off")
        return dict(DEFAULT_SCHEDULE, every_h=max(1.0, float(self.default_hours)))

    def set_schedule(self, body: Any) -> dict[str, Any]:
        cfg = validate_schedule(body)
        sysconfig.save_section(self.data_dir, SECTION, cfg)
        self._wake.set()
        return self.schedule_public()

    def last_run(self) -> float | None:
        st = self._section(STATE_SECTION)
        if isinstance(st, dict) and isinstance(st.get("last_run"), (int, float)):
            return float(st["last_run"])
        autos = [b["created"] for b in self.backup.list_server_backups() if b["kind"] == "auto"]
        return max(autos) if autos else None                       # første gang efter opgradering: seneste lokale backup

    def schedule_public(self) -> dict[str, Any]:
        cfg = self.schedule()
        nxt = next_run(cfg, self.last_run(), time.time())
        return {**cfg, "next_run": nxt, "last_run": self.last_run(), "running": self.running,
                "runs": dict(self.runs), "expected_interval_h": expected_interval_h(cfg)}

    def targets(self) -> list[dict[str, Any]]:
        raw = self._section(TARGETS_SECTION)
        return [t for t in raw if isinstance(t, dict) and "id" in t] if isinstance(raw, list) else []

    def _save_targets(self, targets: list[dict[str, Any]]) -> None:
        before = self._nfs_lines(self.targets())
        sysconfig.save_section(self.data_dir, TARGETS_SECTION, targets)
        if self._nfs_lines(targets) != before:
            self._request_mounts(targets)                        # root-hjælperen udløses kun, når NFS-listen faktisk ændres

    @staticmethod
    def _nfs_lines(targets: list[dict[str, Any]]) -> list[str]:
        return [f"{t['id']} {t['export']}" for t in targets if t["method"] == "nfs" and t["enabled"]]

    def _get(self, target_id: str) -> dict[str, Any]:
        t = next((x for x in self.targets() if x["id"] == target_id), None)
        if t is None:
            raise ServiceError(404, "Destinationen findes ikke")
        return t

    def _secret(self, target_id: str) -> Callable[[str], str | None]:
        return lambda name: self.secrets.get_secret(SECRET_SECTION, f"{target_id}.{name}")

    def public(self, t: dict[str, Any]) -> dict[str, Any]:
        sec = self._secret(t["id"])
        pub = self.secrets.get_secret(SECRET_SECTION, f"{t['id']}.public_key")
        return {**{k: v for k, v in t.items() if k != "host_key"},
                "host_key": t["host_key"]["fingerprint"] if t.get("host_key") else None,
                "has_password": sec("password") is not None, "public_key": pub,
                "last": self.results.get(t["id"]), "fails": self.fails.get(t["id"], 0),
                "uploads": self.uploads.get(t["id"], {"ok": 0, "error": 0}),
                "mount": self._mount_status().get(t["id"]) if t["method"] == "nfs" else None}

    def _mount_status(self) -> dict[str, Any]:
        """Root-hjælperens svar for NFS-shares: id → {ok, error, ts}. Tom, hvis hjælperen ikke findes (fx under udvikling)."""
        if self.state_dir is None:
            return {}
        try:
            data = json.loads((self.state_dir / "backup-mounts.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def list_public(self) -> list[dict[str, Any]]:
        return [self.public(t) for t in self.targets()]

    def _apply_secret(self, target_id: str, body: dict[str, Any]) -> list[str]:
        changed = []
        pw = body.get("password")
        if pw is not None:
            if not isinstance(pw, str) or len(pw) > 500:
                raise _bad("Ugyldig adgangskode/token")
            if pw:
                self.secrets.set_secret(SECRET_SECTION, f"{target_id}.password", pw)
                changed.append("password")
        if body.get("clear_password"):
            self.secrets.delete_secret(SECRET_SECTION, f"{target_id}.password")
            changed.append("password (fjernet)")
        return changed

    def create(self, body: Any) -> dict[str, Any]:
        with self._cfg_lock:
            return self._locked_create(body)

    def _locked_create(self, body: Any) -> dict[str, Any]:
        targets = self.targets()
        if len(targets) >= MAX_TARGETS:
            raise _bad(f"Højst {MAX_TARGETS} destinationer")
        t = validate_target(body)
        if any(x["name"].lower() == t["name"].lower() for x in targets):
            raise ServiceError(409, "Der findes allerede en destination med det navn")
        t["id"] = _secrets.token_hex(4)
        t["host_key"] = None
        self._apply_secret(t["id"], body)
        targets.append(t)
        self._save_targets(targets)
        log.info("Backup-destination '%s' oprettet (%s)", t["name"], t["method"])
        return self.public(t)

    def update(self, target_id: str, body: Any) -> dict[str, Any]:
        with self._cfg_lock:
            return self._locked_update(target_id, body)

    def _locked_update(self, target_id: str, body: Any) -> dict[str, Any]:
        targets = self.targets()
        cur = self._get(target_id)
        t = validate_target(body, cur)
        if any(x["name"].lower() == t["name"].lower() and x["id"] != target_id for x in targets):
            raise ServiceError(409, "Der findes allerede en destination med det navn")
        if any(cur.get(k) != t.get(k) for k in ("host", "port")):
            t["host_key"] = None                                   # anden server → værtsnøglen skal godkendes igen
        self._apply_secret(target_id, body if isinstance(body, dict) else {})
        self._save_targets([t if x["id"] == target_id else x for x in targets])
        return self.public(t)

    def delete(self, target_id: str) -> None:
        with self._cfg_lock:
            return self._locked_delete(target_id)

    def _locked_delete(self, target_id: str) -> None:
        self._get(target_id)
        self._save_targets([x for x in self.targets() if x["id"] != target_id])
        for name in ("password", "private_key", "public_key"):
            self.secrets.delete_secret(SECRET_SECTION, f"{target_id}.{name}")
        for d in (self.results, self.fails, self.uploads, self.last_success):
            d.pop(target_id, None)

    def make_ssh_key(self, target_id: str) -> dict[str, Any]:
        """Nyt Ed25519-nøglepar til destinationen. Den private del bliver i secrets.json; den offentlige vises (til authorized_keys)."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        t = self._get(target_id)
        if t["method"] not in ("sftp", "scp"):
            raise _bad("SSH-nøgler bruges kun til SFTP og SCP")
        k = Ed25519PrivateKey.generate()
        pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()).decode()
        pub = k.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode()
        pub = f"{pub} hypervision-scada-backup-{socket.gethostname()}"
        self.secrets.set_secret(SECRET_SECTION, f"{target_id}.private_key", pem)
        self.secrets.set_secret(SECRET_SECTION, f"{target_id}.public_key", pub)
        return {"public_key": pub}

    # ------------------------------------------------------------ afsendelse

    def _transport(self, t: dict[str, Any], seen_key: list[Any] | None = None) -> _Transport:
        sec = self._secret(t["id"])
        m = t["method"]
        if m == "sftp":
            return _Sftp(t, sec, seen_key)
        if m == "scp":
            return _Scp(t, sec, seen_key)
        if m in ("ftp", "ftps"):
            return _Ftp(t, sec)
        if m == "https":
            return _Https(t, sec)
        if m == "smb":
            return _Smb(t, sec)
        return _Local(t, sec, self.nfs_root)

    def _fragments(self, target_id: str) -> list[str]:
        sec = self._secret(target_id)
        return [v for v in (sec("password"), sec("private_key")) if v and len(v) >= 4]

    def safe_error(self, target_id: str, exc: BaseException) -> str:
        text = str(exc) if isinstance(exc, TargetError) else f"{type(exc).__name__}: {exc}"
        for frag in self._fragments(target_id):
            text = text.replace(frag, "***")                      # FØR afkortning, så et halvt kodeord aldrig står tilbage
        return text.strip()[:300] or type(exc).__name__

    def _send_blocking(self, t: dict[str, Any], files: list[Path]) -> dict[str, Any]:
        sent, size = [], 0
        with self.transport_factory(t) as tr:
            for f in files:
                tr.put(f, f.name)
                sent.append(f.name)
                size += f.stat().st_size
            pruned = self._prune(tr, t) if t["keep"] else 0
        return {"files": sent, "bytes": size, "pruned": pruned}

    @staticmethod
    def _prune(tr: _Transport, t: dict[str, Any]) -> int:
        names = [n for n in tr.list() if OWN_FILE.match(n)]
        removed = 0
        for prefix in ("scada-auto-", "trends-auto-"):
            mine = sorted(n for n in names if n.startswith(prefix))
            for old in mine[: max(0, len(mine) - t["keep"])]:
                tr.delete(old)
                removed += 1
        return removed

    async def _send(self, t: dict[str, Any], files: list[Path]) -> dict[str, Any]:
        t0 = time.monotonic()
        error = ""
        for attempt in range(len(RETRY_DELAYS_S) + 1):
            try:
                res = await asyncio.to_thread(self._send_blocking, t, files)
                break
            except Exception as exc:  # noqa: BLE001 — alle fejl ved en destination skal registreres, ikke vælte kørslen
                error = self.safe_error(t["id"], exc)
                log.warning("Backup til '%s' (%s) fejlede (forsøg %d): %s", t["name"], t["method"], attempt + 1, error)
                if attempt < len(RETRY_DELAYS_S):
                    await asyncio.sleep(RETRY_DELAYS_S[attempt])
        else:
            res = None
        st = self.uploads.setdefault(t["id"], {"ok": 0, "error": 0})
        now = time.time()
        if res is not None:
            st["ok"] += 1
            self.fails[t["id"]] = 0
            self.last_success[t["id"]] = now
            out = {"at": now, "ok": True, "error": "", "duration_s": round(time.monotonic() - t0, 1), **res}
            log.info("Backup sendt til '%s' (%s): %d filer, %d bytes, %d gamle fjernet", t["name"], t["method"], len(res["files"]),
                     res["bytes"], res["pruned"])
        else:
            st["error"] += 1
            self.fails[t["id"]] = self.fails.get(t["id"], 0) + 1
            out = {"at": now, "ok": False, "error": error, "duration_s": round(time.monotonic() - t0, 1), "files": [], "bytes": 0}
        self.results[t["id"]] = out
        return out

    async def run_once(self, reason: str = "tidsplan") -> dict[str, Any]:
        """Lokal backup (konfiguration + historik) → send til destinationerne. Én kørsel ad gangen."""
        if self._run_lock.locked():
            raise ServiceError(409, "En backup kører allerede")
        async with self._run_lock:
            self.running = True
            try:
                return await self._run(reason)
            finally:
                self.running = False

    async def _run(self, reason: str) -> dict[str, Any]:
        log.info("Backup startet (%s)", reason)
        files: dict[str, Path] = {}
        local_error = ""
        try:
            name = await asyncio.to_thread(self.backup.save_to_server, "auto", "system")
            files["config"] = self.backup.backup_dir / name
        except Exception as exc:  # noqa: BLE001
            local_error = f"Konfiguration: {exc}"
            log.exception("Automatisk backup fejlede")
        if self.backup.trend_db is not None and self.backup.trend_keep > 0:
            try:
                name = await asyncio.to_thread(self.backup.save_trend_snapshot)
                files["trends"] = self.backup.backup_dir / name
            except Exception as exc:  # noqa: BLE001
                local_error = (local_error + "; " if local_error else "") + f"Historik: {exc}"
                log.exception("Automatisk backup af trend-historik fejlede")
        sysconfig.save_section(self.data_dir, STATE_SECTION, {"last_run": time.time()})
        jobs = []
        for t in self.targets():
            if not t["enabled"]:
                continue
            chosen = [p for k, p in files.items() if (k == "config" and t["send_config"]) or (k == "trends" and t["send_trends"])]
            if chosen:
                jobs.append(self._send(t, chosen))
        results = await asyncio.gather(*jobs) if jobs else []
        failed = sum(1 for r in results if not r["ok"])
        outcome = "error" if local_error or (results and failed == len(results)) else ("partial" if failed else "ok")
        self.runs[outcome] += 1
        log.info("Backup færdig (%s): %s, %d destinationer, %d fejlede", reason, outcome, len(results), failed)
        return {"result": outcome, "local_error": local_error, "files": [p.name for p in files.values()],
                "targets": len(results), "failed": failed}

    async def test(self, target_id: str, trust_fingerprint: str | None = None) -> dict[str, Any]:
        """Forbind, skriv og slet en lille testfil. SFTP/SCP: en ukendt værtsnøgle returneres, og gemmes kun hvis `trust_host_key`."""
        t = self._get(target_id)
        seen: list[Any] = []
        tmp = self.data_dir / "tmp"
        tmp.mkdir(exist_ok=True)
        probe = tmp / f"hv-test-{_secrets.token_hex(3)}.txt"
        probe.write_text(f"HypervisionPLC SCADA backup-test {datetime.now(TZ).isoformat(timespec='seconds')}\n", encoding="utf-8")

        def work() -> None:
            factory = self.transport_factory
            tr = factory(t, seen) if t["method"] in ("sftp", "scp") else factory(t)
            with tr:
                tr.put(probe, probe.name)
                if t["method"] != "https":
                    tr.delete(probe.name)

        try:
            if t["method"] in ("sftp", "scp") and trust_fingerprint:
                try:
                    await asyncio.to_thread(work)
                except HostKeyError:
                    key = seen[-1]
                    if key["fingerprint"] != trust_fingerprint:     # serveren viser nu en ANDEN nøgle end den, der blev godkendt
                        raise TargetError(f"Værtsnøglen er ikke den, du godkendte (nu: {key['fingerprint']}) — intet gemt") from None
                    await asyncio.to_thread(self._set_host_key, target_id, key)
                    t = self._get(target_id)
                    seen.clear()
                    await asyncio.to_thread(work)
            else:
                await asyncio.to_thread(work)
        except Exception as exc:  # noqa: BLE001
            unknown = seen[-1] if isinstance(exc, HostKeyError) and seen else None
            return {"ok": False, "error": self.safe_error(target_id, exc), "host_key": unknown["fingerprint"] if unknown else None}
        finally:
            probe.unlink(missing_ok=True)
        return {"ok": True, "error": "", "host_key": None}

    def _set_host_key(self, target_id: str, key: dict[str, Any]) -> None:
        with self._cfg_lock:
            return self._locked__set_host_key(target_id, key)

    def _locked__set_host_key(self, target_id: str, key: dict[str, Any]) -> None:
        self._save_targets([{**x, "host_key": key} if x["id"] == target_id else x for x in self.targets()])
        log.warning("Værtsnøgle godkendt for backup-destination %s: %s", target_id, key["fingerprint"])

    # ------------------------------------------------------------ NFS (root-hjælperen monterer)

    def _request_mounts(self, targets: list[dict[str, Any]]) -> None:
        """Ønsket liste over NFS-monteringer → anmodningsfil til root-hjælperen (kun id + vært:/sti; den validerer selv igen)."""
        lines = self._nfs_lines(targets)
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.config_dir / "backup-mounts.request.tmp"
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            tmp.replace(self.config_dir / "backup-mounts.request")
        except OSError as exc:
            log.warning("Kunne ikke bede om NFS-montering: %s", exc)

    # ------------------------------------------------------------ løkke + observability

    def failing(self) -> dict[str, str]:
        """Destinationer med mindst FAIL_ALARM_AFTER fejl i træk → navn: fejl (Status-problem og SYS-alarm)."""
        names = {t["id"]: t["name"] for t in self.targets() if t["enabled"]}
        return {names[i]: self.results.get(i, {}).get("error", "") for i, n in self.fails.items() if n >= FAIL_ALARM_AFTER and i in names}

    def metrics(self) -> dict[str, Any]:
        names = {t["id"]: t["name"] for t in self.targets()}
        return {"runs": dict(self.runs), "uploads": {names[i]: v for i, v in self.uploads.items() if i in names},
                "last_success": {names[i]: v for i, v in self.last_success.items() if i in names},
                "failing": {names[i]: 1 if n >= FAIL_ALARM_AFTER else 0 for i, n in self.fails.items() if i in names}}

    def run_now(self) -> None:
        if self._run_lock.locked():
            raise ServiceError(409, "En backup kører allerede")
        self._force = True
        self._wake.set()

    async def run(self) -> None:
        self._force = False
        self._request_mounts(self.targets())                       # efter opstart/opdatering: monteringerne genskabes
        started = time.time()
        while True:
            cfg = self.schedule()
            now = time.time()
            due = next_run(cfg, self.last_run(), now)
            if due is not None and due <= now:
                due = max(due, started + STARTUP_DELAY_S)          # forsinket (slukket): først 5 min efter opstart
            delay = None if due is None else max(0.0, due - now)
            self._wake.clear()
            if not self._force:
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=delay)
                    if not self._force:
                        continue                                    # tidsplanen er ændret → regn forfaldstiden ud igen
                except TimeoutError:
                    pass
            reason = "manuelt" if self._force else "tidsplan"
            self._force = False
            try:
                await self.run_once(reason)
            except ServiceError:
                pass
            except Exception:  # noqa: BLE001
                log.exception("Backup-kørslen fejlede")
