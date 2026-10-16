"""OTA-opdatering (lag 3): tjek og stil en opdateringspakke klar, og bed den privilegerede hjælper om at installere den.

Arbejdsdeling (se deploy/apply-update.sh):
  * SCADA-tjenesten kører som en almindelig bruger og kan hverken skrive til programmappen eller genstarte sig selv.
  * Den modtager pakken, KONTROLLERER den (uden at pakke den ud), tager en backup og lægger `apply.request` i
    `<data>/updates/`. En root-tjeneste (systemd .path) installerer pakken, genstarter, tjekker /api/health og
    ruller tilbage ved fejl. Status skrives til `status.json` og `update.log`.
  * Pakken pakkes aldrig ud her — hjælperen kopierer den, tjekker kontrolsummen og pakker selv ud som root.

Afgrænsning: kontrolsummen beskytter mod beskadigelse og mod at en anden pakke end den godkendte installeres, ikke mod en
ondsindet admin (en admin kan via opdateringen i praksis køre kode som root). Signerede pakker kan tilføjes senere.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import tarfile
import time
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from ..config import read_version
from .errors import ServiceError

log = logging.getLogger(__name__)

MAX_PACKAGE_BYTES = 60 * 1024 * 1024      # under nginx' grænse (64 MB), så fejlen kommer fra appen og ikke som en nginx-side
MAX_FILES = 20_000
MAX_UNPACKED_BYTES = 600 * 1024 * 1024
ROOT = "scada"
REQUIRED = ("version.json", "deploy/install.sh", "deploy/apply-update.sh", "backend/app/main.py",
            "backend/requirements.txt", "frontend/dist/index.html")
_VERSION = re.compile(r"^\d{1,4}\.\d{1,4}\.\d{1,4}$")
_BUILD = re.compile(r"^\d{1,6}$")
_USER = re.compile(r"[^A-Za-z0-9_.@-]")
APPLYING_STALE_S = 20 * 60               # "applying" så længe = hjælperen er gået i stå


def _key(version: str, build: str) -> tuple[int, int, int, int]:
    major, minor, patch = (int(x) for x in version.split("."))
    return major, minor, patch, int(build)


def relation(current: dict[str, str], new: dict[str, str]) -> str:
    """'newer' | 'same' | 'older' | 'unknown' (den installerede version kan ikke læses)."""
    try:
        a, b = _key(current["version"], current["build"]), _key(new["version"], new["build"])
    except (KeyError, ValueError):
        return "unknown"
    return "newer" if b > a else "same" if b == a else "older"


def inspect_package(path: Path) -> dict[str, Any]:
    """Kontrollér en pakke uden at pakke den ud: sikre filnavne, kun filer og mapper, størrelser, nødvendige filer og version.
    → {version, build, sha256, size, files}. Kaster ServiceError(400) med en klar besked."""
    size = path.stat().st_size
    if size == 0:
        raise ServiceError(400, "Ingen fil modtaget")
    if size > MAX_PACKAGE_BYTES:
        raise ServiceError(413, f"Pakken er for stor (max {MAX_PACKAGE_BYTES // 1024 // 1024} MB)")
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    names: set[str] = set()
    total = 0
    version_raw: bytes | None = None
    try:
        with tarfile.open(path, "r:*") as tar:
            for member in tar:
                if len(names) >= MAX_FILES:
                    raise ServiceError(400, f"Pakken har for mange filer (max {MAX_FILES})")
                name = member.name
                parts = PurePosixPath(name).parts
                if not parts or name.startswith(("/", "\\")) or "\\" in name or ".." in parts or ":" in parts[0]:
                    raise ServiceError(400, f"Pakken indeholder en usikker sti: {name[:80]}")
                if parts[0] != ROOT:
                    raise ServiceError(400, f"Alt i pakken skal ligge under '{ROOT}/' (fandt '{name[:80]}') — byg den med deploy/make-package.sh")
                if not (member.isreg() or member.isdir()):
                    raise ServiceError(400, f"Pakken indeholder noget andet end filer og mapper ({name[:80]})")
                total += member.size
                if total > MAX_UNPACKED_BYTES:
                    raise ServiceError(400, "Pakken fylder for meget udpakket")
                names.add("/".join(parts))
                if name.rstrip("/") == f"{ROOT}/version.json" and member.isreg():
                    stream = tar.extractfile(member)
                    version_raw = stream.read(4096) if stream else None
    except tarfile.TarError:
        raise ServiceError(400, "Filen er ikke en gyldig tar-pakke (.tar, .tar.gz eller .tgz)") from None
    except EOFError:
        raise ServiceError(400, "Pakken er beskadiget eller afbrudt (uventet slutning)") from None
    missing = [r for r in REQUIRED if f"{ROOT}/{r}" not in names]
    if missing:
        raise ServiceError(400, f"Pakken mangler: {', '.join(missing)}")
    try:
        meta = json.loads(version_raw or b"")
        version, build = str(meta["version"]), str(meta["build"])
    except (ValueError, KeyError, TypeError):
        raise ServiceError(400, "version.json i pakken kan ikke læses") from None
    if not _VERSION.match(version) or not _BUILD.match(build):
        raise ServiceError(400, f"version.json i pakken har et ugyldigt versionsnummer ({version} build {build})")
    return {"version": version, "build": build, "sha256": digest.hexdigest(), "size": size, "files": len(names)}


class UpdateService:
    def __init__(self, data_dir: Path, backups: Any, current: Callable[[], dict[str, str]] = read_version):
        self.dir = data_dir / "updates"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.backups = backups
        self.current = current

    # ------------------------------------------------------------- filer
    @property
    def enabled(self) -> bool:
        """Hjælperen er installeret (install.sh lægger markøren)."""
        return (self.dir / "enabled").is_file()

    @property
    def incoming(self) -> Path:
        return self.dir / "incoming.tar"

    def _read(self, name: str) -> dict[str, Any] | None:
        try:
            data = json.loads((self.dir / name).read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, ValueError):
            return None

    def _write(self, name: str, data: dict[str, Any]) -> None:
        tmp = self.dir / f"{name}.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.dir / name)

    def _log_tail(self, lines: int = 40) -> list[str]:
        try:
            return (self.dir / "update.log").read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
        except OSError:
            return []

    # ------------------------------------------------------------- status
    def status(self) -> dict[str, Any]:
        current = self.current()
        staged = self._read("staged.json")
        if staged:
            staged["relation"] = relation(current, staged)
        last = self._read("status.json")
        pending = (self.dir / "apply.request").exists()
        state = (last or {}).get("state", "idle")
        if pending and state not in ("applying", "queued"):
            state = "queued"
        if state in ("applying", "queued") and last and time.time() - float(last.get("ts", 0)) > APPLYING_STALE_S:
            state = "stalled"
        return {"enabled": self.enabled, "current": current, "staged": staged, "state": state, "last": last,
                "busy": state in ("applying", "queued"), "log": self._log_tail()}

    # ------------------------------------------------------------- pakke
    def stage(self, uploaded_by: str) -> dict[str, Any]:
        """Kontrollér den uploadede `incoming.tar`; ved succes bliver den til den klargjorte pakke (`staged.tar`)."""
        self._require_enabled()
        self._require_idle()
        info = inspect_package(self.incoming)
        info["relation"] = relation(self.current(), info)
        info["uploaded_by"] = uploaded_by
        info["uploaded_at"] = time.time()
        self.incoming.replace(self.dir / "staged.tar")
        self._write("staged.json", info)
        log.info("Opdateringspakke klargjort: %s build %s (%s) af %s", info["version"], info["build"], info["relation"], uploaded_by)
        return info

    def discard(self) -> None:
        self._require_idle()
        for name in ("staged.tar", "staged.json", "incoming.tar"):
            (self.dir / name).unlink(missing_ok=True)

    def apply(self, sha256: str, actor: str, reinstall: bool = False) -> dict[str, Any]:
        """Tag en backup og bed hjælperen installere den klargjorte pakke. Kontrolsummen skal være den admin har set."""
        self._require_enabled()
        self._require_idle()
        staged = self._read("staged.json")
        if not staged or not (self.dir / "staged.tar").is_file():
            raise ServiceError(409, "Der er ingen klargjort pakke — upload en først")
        if staged.get("sha256") != sha256:
            raise ServiceError(409, "Kontrolsummen svarer ikke til den klargjorte pakke — hent status igen og kontrollér pakken")
        rel = relation(self.current(), staged)
        if rel == "older":
            raise ServiceError(409, f"Pakken ({staged['version']} build {staged['build']}) er ældre end den installerede — "
                                    "nedgradering understøttes ikke, fordi databasen kan være opgraderet")
        if rel == "same" and not reinstall:
            raise ServiceError(409, "Pakken er samme version som den installerede — bekræft at den skal geninstalleres")
        backup = self.backups.save_to_server("pre-update", actor)
        who = _USER.sub("", actor)[:64] or "ukendt"
        self._write("status.json", {"state": "queued", "message": "Anmodning sendt til opdateringstjenesten", "from": self.current()["version"],
                                    "to": staged["version"], "by": who, "ts": time.time(), "backup": backup})
        tmp = self.dir / "apply.request.tmp"
        tmp.write_text(f"SHA256={staged['sha256']}\nBY={who}\nVERSION={staged['version']}\nBUILD={staged['build']}\n", encoding="utf-8")
        tmp.replace(self.dir / "apply.request")      # først nu ser hjælperen den
        log.warning("OTA-opdatering anmodet af %s: %s → %s build %s (backup %s)", who, self.current()["version"], staged["version"],
                    staged["build"], backup)
        return {"queued": True, "backup": backup, "version": staged["version"], "build": staged["build"]}

    # ------------------------------------------------------------- hjælp
    def _require_enabled(self) -> None:
        if not self.enabled:
            raise ServiceError(409, "Opdatering via web er ikke aktiveret på denne server — kør 'sh deploy/install.sh' som root én gang")

    def _require_idle(self) -> None:
        state = self.status()["state"]
        if state in ("queued", "applying"):
            raise ServiceError(409, "En opdatering er i gang — vent til den er færdig")
