"""OTA fra GitHub (lag 3): find den nyeste udgivelse (GitHub Release) og hent dens pakke som `incoming.tar`.

Pakken klargøres derefter præcis som en uploadet pakke (`UpdateService.stage`): samme kontrol, backup, installation og
tilbagerulning. Kontrolsummen (`scada-*.tar.sha256`) hentes fra samme udgivelse og beskytter mod beskadigelse under
hentningen — ikke mod en kompromitteret GitHub-konto (samme niveau som deploy/bootstrap.sh).
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from ..config import read_version
from .errors import ServiceError
from .updates import MAX_PACKAGE_BYTES, relation

log = logging.getLogger(__name__)

API = "https://api.github.com"
_REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}\Z")
_TAG = re.compile(r"^v(\d{1,4}\.\d{1,4}\.\d{1,4})\Z")
_ASSET = re.compile(r"^scada-(\d{1,4}\.\d{1,4}\.\d{1,4})-b(\d{1,6})\.tar\Z")
_SHA = re.compile(r"^([0-9a-fA-F]{64})\b")
TIMEOUT_S = 15.0
NOTES_MAX = 4000
DOWNLOAD_DEADLINE_S = 10 * 60      # hele hentningen, ikke kun pr. læsning


class GitHubReleases:
    def __init__(self, repo: str, current: Callable[[], dict[str, str]] = read_version,
                 transport: httpx.BaseTransport | None = None):
        self.repo = repo.strip()
        self.current = current
        self.transport = transport          # tests: httpx.MockTransport

    @property
    def enabled(self) -> bool:
        return bool(_REPO.match(self.repo))

    def _client(self) -> httpx.Client:
        return httpx.Client(transport=self.transport, timeout=TIMEOUT_S, follow_redirects=True, max_redirects=5,
                            headers={"Accept": "application/vnd.github+json", "User-Agent": "HypervisionPLC-SCADA"})

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise ServiceError(409, "Opdatering fra GitHub er slået fra (SCADA_UPDATE_REPO er tom eller ugyldig)")

    # ------------------------------------------------------------- søg
    def latest(self) -> dict[str, Any]:
        """Den nyeste udgivelse: version, build, noter, pakkens navn/størrelse og forholdet til den installerede version."""
        self._require_enabled()
        try:
            with self._client() as c:
                r = c.get(f"{API}/repos/{self.repo}/releases/latest")
        except httpx.HTTPError as exc:
            log.warning("GitHub kunne ikke nås (%s): %s", self.repo, exc)
            raise ServiceError(502, "GitHub kunne ikke nås — har serveren forbindelse til internettet?") from exc
        if r.status_code == 404:
            raise ServiceError(404, f"Der er ingen udgivelse i {self.repo} på GitHub")
        if r.status_code in (403, 429):
            raise ServiceError(503, "GitHub afviser for mange forespørgsler lige nu — prøv igen om lidt")
        if r.status_code != 200:
            raise ServiceError(502, f"GitHub svarede med fejl {r.status_code}")
        try:
            rel = r.json()
            if not isinstance(rel, dict):
                raise TypeError("ikke et objekt")
            assets = {a["name"]: a for a in rel.get("assets") or [] if isinstance(a, dict) and isinstance(a.get("name"), str)}
            tag = str(rel.get("tag_name") or "")
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ServiceError(502, "Uforståeligt svar fra GitHub") from exc
        pkg = next((a for name, a in assets.items() if _ASSET.match(name)), None)
        if pkg is None:
            raise ServiceError(502, f"Udgivelsen {tag[:40] or '?'} har ingen pakke (scada-<version>-b<build>.tar)")
        if f"{pkg['name']}.sha256" not in assets:
            raise ServiceError(502, f"Udgivelsen {tag[:40] or '?'} mangler kontrolsummen ({pkg['name']}.sha256)")
        m = _ASSET.match(pkg["name"])
        version, build = m.group(1), m.group(2)
        t = _TAG.match(tag)
        if not t or t.group(1) != version:
            raise ServiceError(502, f"Udgivelsens tag ({tag[:40] or '?'}) passer ikke med pakken ({pkg['name']})")
        size = pkg.get("size")
        info = {"tag": tag, "version": version, "build": build, "name": pkg["name"],
                "size": size if isinstance(size, int) and size >= 0 else 0, "published_at": rel.get("published_at"), "url": rel.get("html_url"),
                "notes": str(rel.get("body") or "")[:NOTES_MAX], "repo": self.repo}
        info["relation"] = relation(self.current(), info)
        return info

    # ------------------------------------------------------------- hent
    def download(self, target: Path, expect_name: str | None = None) -> dict[str, Any]:
        """Hent den nyeste udgivelses pakke til `target` og kontrollér kontrolsummen. `expect_name`: den version admin
        så — er der kommet en nyere i mellemtiden, afvises hentningen, så der ikke klargøres noget andet end det viste."""
        info = self.latest()
        if expect_name and info["name"] != expect_name:
            raise ServiceError(409, f"Der er kommet en nyere udgivelse ({info['name']}) — søg igen og kontrollér den")
        if info["size"] > MAX_PACKAGE_BYTES:
            raise ServiceError(413, f"Pakken er for stor (max {MAX_PACKAGE_BYTES // 1024 // 1024} MB)")
        base = f"https://github.com/{self.repo}/releases/download/{info['tag']}/{info['name']}"
        try:
            with self._client() as c:
                s = c.get(base + ".sha256")
                if s.status_code != 200:
                    raise ServiceError(502, f"Kontrolsummen kunne ikke hentes (fejl {s.status_code})")
                m = _SHA.match(s.text.strip())
                if not m:
                    raise ServiceError(502, "Kontrolsummen fra GitHub er ugyldig")
                expected = m.group(1).lower()
                h, size = hashlib.sha256(), 0
                deadline = time.monotonic() + DOWNLOAD_DEADLINE_S
                with c.stream("GET", base) as r:
                    if r.status_code != 200:
                        raise ServiceError(502, f"Pakken kunne ikke hentes (fejl {r.status_code})")
                    if r.url.scheme != "https":
                        raise ServiceError(502, "GitHub sendte hentningen videre til en usikker adresse (ikke https)")
                    length = r.headers.get("content-length", "")
                    if length.isdigit() and int(length) > MAX_PACKAGE_BYTES:
                        raise ServiceError(413, f"Pakken er for stor (max {MAX_PACKAGE_BYTES // 1024 // 1024} MB)")
                    with target.open("wb") as f:
                        for chunk in r.iter_bytes():
                            size += len(chunk)
                            if size > MAX_PACKAGE_BYTES:
                                raise ServiceError(413, f"Pakken er for stor (max {MAX_PACKAGE_BYTES // 1024 // 1024} MB)")
                            if time.monotonic() > deadline:
                                raise ServiceError(504, "Hentningen fra GitHub tog for lang tid - prøv igen")
                            h.update(chunk)
                            f.write(chunk)
        except httpx.HTTPError as exc:
            target.unlink(missing_ok=True)
            log.warning("Hentning fra GitHub fejlede (%s): %s", info["name"], exc)
            raise ServiceError(502, "Hentningen fra GitHub blev afbrudt — prøv igen") from exc
        except ServiceError:
            target.unlink(missing_ok=True)
            raise
        except OSError as exc:
            target.unlink(missing_ok=True)
            log.error("Pakken fra GitHub kunne ikke gemmes: %s", exc)
            raise ServiceError(507, "Pakken kunne ikke gemmes på serveren - er disken fuld?") from exc
        if h.hexdigest() != expected:
            target.unlink(missing_ok=True)
            raise ServiceError(502, "Kontrolsummen passer ikke — pakken er beskadiget under hentningen; prøv igen")
        log.info("Pakke hentet fra GitHub: %s (%d bytes)", info["name"], size)
        return info
