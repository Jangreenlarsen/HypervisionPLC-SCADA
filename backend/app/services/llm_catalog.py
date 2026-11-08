"""Vælg LLM-model fra en liste (v4.4.0, PLAN.md › Vælg LLM-model): varianterne hentes som færdige LLM-pakker fra
projektets GitHub-udgivelser — administratoren skal ikke selv hente noget fra Hugging Face.

- **Kataloget** er `deploy/llm-models.json` (følger med SCADA'en): navn, variant (Hurtig/Standard/Stor), størrelse, licens,
  profiler og hvilke arkitekturer der er udgivet. Udgivelsen hedder `llm-<model-id>-<llama-build>` og er en prerelease, så
  SCADA-opdateringerne (`/releases/latest`) aldrig forveksles med en LLM-pakke.
- **Pakken** (`scada-llm-<arkitektur>-<model-id>-<llama-build>.tar`) ligger i dele (`.part01` …, højst 2 GiB pr. fil på
  GitHub) med `.sha256` for hele pakken. Delene skrives direkte i én fil, mens SHA256 beregnes; passer den ikke, slettes
  filen. Derefter klargøres den som en uploadet pakke (samme kontrol), og root-hjælperen tjekker SHA256 igen ved
  installationen. Samme sikkerhedsniveau som OTA fra GitHub (kontrolsummen beskytter mod fejl, ikke mod en kompromitteret
  GitHub-konto).
- **Netværk:** kun `api.github.com`, `github.com` og GitHubs download-domæner; ingen proxy/netrc fra miljøet (`trust_env=False`).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

from .errors import ServiceError
from .github_releases import _REPO
from .assistant import glibc_problem, parse_glibc
from .hwprofile import PROFILES

log = logging.getLogger("scada.assist")

API = "https://api.github.com"
ALLOWED_HOSTS = {"api.github.com", "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}
_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,60}\Z")
_SHA = re.compile(r"^([0-9a-fA-F]{64})\b")
_PART = re.compile(r"\.part(\d{2})\Z")
CHUNK = 4 * 1024 * 1024
MAX_PACKAGE_BYTES = 16 * 1024 ** 3   # som upload (services/assistant.py)
READ_TIMEOUT_S = 60.0


def asset_name(arch: str, model_id: str, build: str) -> str:
    return f"scada-llm-{arch}-{model_id}-{build}.tar"


def release_tag(model_id: str, build: str) -> str:
    return f"llm-{model_id}-{build}"


class Cancelled(Exception):
    pass


def published(m: dict[str, Any]) -> dict[str, str | None]:
    """{arkitektur: fastlåst SHA256 eller None}. `published` kan være en liste (kun arkitekturer) eller et objekt med
    pakkens SHA256 pr. arkitektur — så kontrolleres pakken også mod kataloget, der følger med SCADA'en (ikke kun mod
    kontrolsummen i samme GitHub-udgivelse)."""
    p = m.get("published") or []
    if isinstance(p, dict):
        return {a: (s.lower() if isinstance(s, str) and _SHA.match(s) else None) for a, s in p.items() if isinstance(a, str)}
    return {a: None for a in p if isinstance(a, str)}


class LlmCatalog:
    def __init__(self, path: Path, repo: str, transport: httpx.BaseTransport | None = None):
        self.path = path
        self.repo = repo.strip()
        self.transport = transport
        self._cache: tuple[float, dict[str, Any]] | None = None
        self._lock = threading.Lock()
        self.job: dict[str, Any] = {"state": "idle"}
        self._cancel = threading.Event()

    # ------------------------------------------------------------------ kataloget
    def load(self) -> dict[str, Any]:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            return {"llama": {}, "models": {}}
        if self._cache and self._cache[0] == mtime:
            return self._cache[1]
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.warning("LLM-kataloget kunne ikke læses: %s", self.path)
            data = {}
        data = data if isinstance(data, dict) else {}
        models = {k: v for k, v in (data.get("models") or {}).items() if isinstance(v, dict) and _ID.match(k)}
        out = {"llama": data.get("llama") or {}, "models": models}
        self._cache = (mtime, out)
        return out

    @property
    def enabled(self) -> bool:
        return bool(_REPO.match(self.repo))

    def entries(self, arch: str, profile: str, installed_model: str | None,
                glibc: tuple[int, ...] | None = None) -> list[dict[str, Any]]:
        """Varianterne til listen: kun dem der er udgivet til denne arkitektur. `fits`: passer til hardwareprofilen og
        styresystemet (`blocked` siger hvorfor ikke, når det er styresystemet)."""
        c = self.load()
        build = str(c["llama"].get("build") or "")
        la = c["llama"].get(arch)
        blocked = glibc_problem(parse_glibc(la.get("glibc") if isinstance(la, dict) else None), glibc)
        out = []
        if not self.enabled:
            return []
        for mid, m in c["models"].items():
            if arch not in published(m):
                continue
            profiles = [p for p in m.get("profiles") or [] if p in PROFILES]
            out.append({
                "id": mid, "name": str(m.get("name") or mid), "variant": str(m.get("variant") or ""),
                "about": str(m.get("about") or ""), "quant": str(m.get("quant") or ""), "license": str(m.get("license") or ""),
                "size": int(m.get("size") or 0), "profiles": profiles, "fits": profile in profiles and not blocked,
                "blocked": blocked,
                "installed": installed_model == mid, "release": release_tag(mid, build),
                "url": f"https://github.com/{self.repo}/releases/tag/{release_tag(mid, build)}",
                "pinned": bool(published(m)[arch]),
            })
        order = {"Hurtig": 0, "Standard": 1, "Stor": 2}
        return sorted(out, key=lambda e: (order.get(e["variant"], 9), e["size"]))

    # ------------------------------------------------------------------ GitHub
    def _client(self) -> httpx.Client:
        def guard(request: httpx.Request) -> None:   # også efter omdirigeringer
            if request.url.scheme != "https" or request.url.host not in ALLOWED_HOSTS:
                raise ServiceError(502, f"Hentningen blev omdirigeret til en ukendt adresse ({request.url.host})")
        return httpx.Client(transport=self.transport, timeout=httpx.Timeout(READ_TIMEOUT_S, connect=10.0),
                            follow_redirects=True, max_redirects=5, trust_env=False,
                            headers={"User-Agent": "HypervisionPLC-SCADA", "Accept": "application/vnd.github+json"},
                            event_hooks={"request": [guard]})

    def _assets(self, c: httpx.Client, tag: str) -> dict[str, dict[str, Any]]:
        try:
            r = c.get(f"{API}/repos/{self.repo}/releases/tags/{tag}")
        except httpx.HTTPError as exc:
            raise ServiceError(502, "GitHub kunne ikke nås — har serveren forbindelse til internettet?") from exc
        if r.status_code == 404:
            raise ServiceError(404, f"Udgivelsen {tag} findes ikke på GitHub ({self.repo})")
        if r.status_code in (403, 429):
            raise ServiceError(503, "GitHub afviser for mange forespørgsler lige nu — prøv igen om lidt")
        if r.status_code != 200:
            raise ServiceError(502, f"GitHub svarede med fejl {r.status_code}")
        try:
            assets = r.json().get("assets") or []
            return {a["name"]: {"url": a["browser_download_url"], "size": int(a.get("size") or 0)}
                    for a in assets if isinstance(a, dict) and isinstance(a.get("name"), str)
                    and isinstance(a.get("browser_download_url"), str)}
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ServiceError(502, "Uforståeligt svar fra GitHub") from exc

    def plan(self, c: httpx.Client, model_id: str, arch: str) -> dict[str, Any]:
        """Hvad der skal hentes: delene (eller én fil), deres samlede størrelse og den forventede SHA256."""
        cat = self.load()
        if not self.enabled:
            raise ServiceError(409, "Hentning fra GitHub er slået fra (SCADA_UPDATE_REPO er tom eller ugyldig)")
        m = cat["models"].get(model_id)
        if m is None or arch not in published(m):
            raise ServiceError(404, f"Modellen '{model_id}' findes ikke til {arch} i kataloget")
        pinned = published(m)[arch]
        build = str(cat["llama"].get("build") or "")
        tag, base = release_tag(model_id, build), asset_name(arch, model_id, build)
        assets = self._assets(c, tag)
        parts = sorted((n for n in assets if n.startswith(base + ".part") and _PART.search(n)),
                       key=lambda n: int(_PART.search(n).group(1)))
        if not parts and base in assets:
            parts = [base]
        if not parts:
            raise ServiceError(502, f"Udgivelsen {tag} har ingen pakke til {arch} ({base})")
        if [int(_PART.search(n).group(1)) for n in parts if n != base] not in ([], list(range(1, len(parts) + 1))):
            raise ServiceError(502, f"Udgivelsen {tag} mangler en del af pakken")
        if base + ".sha256" not in assets:
            raise ServiceError(502, f"Udgivelsen {tag} mangler kontrolsummen ({base}.sha256)")
        try:
            r = c.get(assets[base + ".sha256"]["url"])
            m_sha = _SHA.match(r.text.strip()) if r.status_code == 200 else None
        except httpx.HTTPError as exc:
            raise ServiceError(502, "Kontrolsummen kunne ikke hentes fra GitHub") from exc
        if not m_sha:
            raise ServiceError(502, f"Kontrolsummen i {tag} kan ikke læses")
        if pinned and m_sha.group(1).lower() != pinned:
            raise ServiceError(502, f"Udgivelsen {tag} passer ikke med kataloget (SHA256) — den er ændret på GitHub og "
                                    "hentes ikke")
        total = sum(assets[n]["size"] for n in parts)
        if total > MAX_PACKAGE_BYTES:
            raise ServiceError(413, f"Pakken i {tag} er for stor ({total / 1e9:.1f} GB)")
        return {"tag": tag, "name": base, "parts": [(n, assets[n]["url"], assets[n]["size"]) for n in parts],
                "total": sum(assets[n]["size"] for n in parts), "sha256": m_sha.group(1).lower()}

    # ------------------------------------------------------------------ hent (kører i en tråd)
    def busy(self) -> bool:
        return self.job.get("state") == "running"

    def cancel(self) -> bool:
        if not self.busy():
            return False
        self._cancel.set()
        return True

    def start(self, job: dict[str, Any]) -> None:
        """Ny hentning: nulstil afbrydelsen FØR opgaven startes (en afbrydelse lige efter start må ikke gå tabt)."""
        self._cancel.clear()
        self.job = job

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def download(self, model_id: str, arch: str, target: Path, precheck: Callable[[int], None],
                 space_check: Callable[[], None]) -> tuple[str, int]:
        """Hent pakken til `target`. → (sha256, størrelse). Kaster ServiceError eller Cancelled. Opdaterer `self.job`."""
        with self._client() as c:
            plan = self.plan(c, model_id, arch)
            precheck(plan["total"])
            self.job.update({"total": plan["total"], "parts": len(plan["parts"]), "part": 0, "done": 0,
                             "release": plan["tag"], "name": plan["name"]})
            digest = hashlib.sha256()
            size = 0
            next_check = 256 * 1024 * 1024
            with target.open("wb") as f:
                for k, (name, url, expect) in enumerate(plan["parts"], 1):
                    self.job["part"] = k
                    part_size = 0
                    try:
                        with c.stream("GET", url) as r:
                            if r.status_code != 200:
                                raise ServiceError(502, f"{name}: GitHub svarede {r.status_code}")
                            for chunk in r.iter_bytes(CHUNK):
                                if self._cancel.is_set():
                                    raise Cancelled()
                                f.write(chunk)
                                digest.update(chunk)
                                size += len(chunk)
                                part_size += len(chunk)
                                self.job["done"] = size
                                if size > plan["total"] + CHUNK:
                                    raise ServiceError(502, "GitHub sendte mere end pakkens størrelse")
                                if size >= next_check:
                                    next_check += 256 * 1024 * 1024
                                    space_check()
                    except httpx.HTTPError as exc:
                        raise ServiceError(502, f"Hentningen af {name} blev afbrudt ({type(exc).__name__}) — prøv igen") \
                            from exc
                    if expect and part_size != expect:
                        raise ServiceError(502, f"{name} har forkert størrelse ({part_size} af {expect} bytes)")
        sha = digest.hexdigest()
        if sha != plan["sha256"]:
            raise ServiceError(502, "Den hentede pakke passer ikke med kontrolsummen (SHA256) — den er kasseret")
        return sha, size
