"""LLM-hjælperen, fase 0 (v3.37.0, PLAN.md): LLM-pakke, styring af LLM-tjenesten, status og afprøvning.

- **LLM-pakken** (`scada-llm-<arch>-<model>-<llama>.tar`, bygges med deploy/make-llm-package.sh) er ÉN samlet, lokal fil
  med llama-server og modellen. Den uploades under System › Hjælper (intet hentes fra internettet på serveren), kontrolleres
  her (sikre stier, manifest, arkitektur) og installeres af en root-hjælper (deploy/apply-llm.sh), der kontrollerer SHA256
  igen, før noget pakkes ud.
- **Tjenesten** (hypervisionplc-scada-llm.service) kører som egen bruger med lav prioritet og hukommelsesloft fra
  hardwareprofilen. SCADA'en lægger anmodninger (`<data>/llm/llm.request`), root-hjælperen udfører dem — samme mønster som
  genstart (services/power.py).
- **Kald til modellen** går gennem lag 4c (`app.llm.client`) og kun ét ad gangen; tællere til Status og metrics.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import tarfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from ..llm.client import LlmClient, LlmError
from .errors import ServiceError
from .hwprofile import HwProfileService

log = logging.getLogger("scada.assist")

ROOT = "scada-llm"
FORMAT = "hv-llm"
MAX_PACKAGE_BYTES = 16 * 1024 ** 3
MAX_FILES = 500
ACTIONS = ("install", "start", "stop", "remove")
WRITE_BUFFER_BYTES = 8 * 1024 * 1024        # upload skrives i blokke fra en tråd
DISK_CHECK_BYTES = 256 * 1024 * 1024        # ledig plads tjekkes undervejs så ofte
DISK_RESERVE_BYTES = 2 * 1024 ** 3          # så meget skal altid være fri til database, trends og logs
PENDING_MAX_S = 30 * 60                     # en installation af flere GB kan tage minutter
_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,60}\Z")
_SHA = re.compile(r"^[0-9a-f]{64}\Z")
ARCH_ALIASES = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}


def _safe_name(name: str) -> tuple[str, ...]:
    parts = PurePosixPath(name).parts
    if not parts or name.startswith(("/", "\\")) or "\\" in name or ".." in parts or ":" in parts[0]:
        raise ServiceError(400, f"LLM-pakken indeholder en usikker sti: {name[:80]}")
    if parts[0] != ROOT:
        raise ServiceError(400, f"Alt i LLM-pakken skal ligge under '{ROOT}/' — byg den med deploy/make-llm-package.sh")
    return parts


def parse_manifest(raw: bytes) -> dict[str, Any]:
    try:
        m = json.loads(raw)
        model = m["model"]
        out = {
            "format_version": int(m["format_version"]), "arch": ARCH_ALIASES.get(str(m["arch"]).lower(), ""),
            "llama_build": str(m["llama_build"]), "ctx": int(m.get("ctx", 8192)),
            "model": {"id": str(model["id"]), "name": str(model["name"])[:80], "file": str(model["file"]),
                      "quant": str(model.get("quant", ""))[:20], "license": str(model["license"])[:40],
                      "sha256": str(model["sha256"]).lower(), "size": int(model["size"])},
        }
        if m.get("format") != FORMAT:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ServiceError(400, "manifest.json i LLM-pakken kan ikke læses — byg pakken med deploy/make-llm-package.sh") from None
    if out["format_version"] != 1:
        raise ServiceError(400, f"LLM-pakkens format {out['format_version']} kendes ikke — opdatér SCADA'en først")
    if not out["arch"]:
        raise ServiceError(400, "LLM-pakken angiver en ukendt arkitektur")
    if not _ID.match(out["model"]["id"]) or not _ID.match(out["llama_build"]) or not _SHA.match(out["model"]["sha256"]):
        raise ServiceError(400, "manifest.json i LLM-pakken har ugyldige felter")
    if not re.match(r"^[A-Za-z0-9._-]{1,120}\.gguf\Z", out["model"]["file"]):
        raise ServiceError(400, "Modelfilen i LLM-pakken skal være en .gguf-fil")
    if not 512 <= out["ctx"] <= 131072:
        raise ServiceError(400, "Kontekstlængden i LLM-pakken er ugyldig")
    return out


def inspect_package(path: Path, sha256: str, machine_arch: str) -> dict[str, Any]:
    """Kontrollér en LLM-pakke uden at pakke den ud → {manifest, sha256, size, files}. SHA256 er beregnet under upload."""
    size = path.stat().st_size
    if size == 0:
        raise ServiceError(400, "Ingen fil modtaget")
    names: dict[str, int] = {}
    manifest_raw: bytes | None = None
    try:
        with tarfile.open(path, "r:") as tar:     # ukomprimeret: GGUF kan ikke pakkes mindre, og læsningen er hurtig
            for member in tar:
                if len(names) >= MAX_FILES:
                    raise ServiceError(400, f"LLM-pakken har for mange filer (max {MAX_FILES})")
                parts = _safe_name(member.name)
                if not (member.isreg() or member.isdir()):
                    raise ServiceError(400, f"LLM-pakken indeholder noget andet end filer og mapper ({member.name[:80]})")
                names["/".join(parts[1:])] = member.size
                if member.name.rstrip("/") == f"{ROOT}/manifest.json" and member.isreg():
                    stream = tar.extractfile(member)
                    manifest_raw = stream.read(64 * 1024) if stream else None
    except tarfile.TarError:
        raise ServiceError(400, "Filen er ikke en gyldig (ukomprimeret) tar-pakke — byg den med deploy/make-llm-package.sh") from None
    except EOFError:
        raise ServiceError(400, "LLM-pakken er beskadiget eller afbrudt (uventet slutning)") from None
    if manifest_raw is None:
        raise ServiceError(400, "LLM-pakken mangler manifest.json")
    man = parse_manifest(manifest_raw)
    want = ARCH_ALIASES.get(machine_arch.lower(), machine_arch)
    if man["arch"] != want:
        raise ServiceError(400, f"LLM-pakken er bygget til {man['arch']}, men maskinen er {want} — byg en pakke til {want}")
    model_path = f"model/{man['model']['file']}"
    if names.get(model_path) != man["model"]["size"]:
        raise ServiceError(400, f"LLM-pakken mangler modelfilen {model_path} (eller størrelsen passer ikke med manifestet)")
    if "llama/llama-server" not in names:
        raise ServiceError(400, "LLM-pakken mangler llama/llama-server")
    if not any(n.startswith("LICENSES/") for n in names):
        raise ServiceError(400, "LLM-pakken mangler licensfilerne (LICENSES/)")
    return {"manifest": man, "sha256": sha256, "size": size, "files": len(names)}


class AssistantService:
    def __init__(self, data_dir: Path, hw: HwProfileService, client: LlmClient, state_dir: Path | None = None):
        self.dir = data_dir / "llm"                                              # ejes af tjenesten: upload + anmodning
        self.state = state_dir or Path("/var/lib/hypervisionplc-scada-net")     # ejes af root: markør og status
        self.hw = hw
        self.client = client
        self._receiving = threading.Lock()
        self._sem = asyncio.Semaphore(1)
        self.waiting = 0
        self.stats = {"requests": 0, "errors": 0, "last_ms": None, "last_tokens_per_s": None, "last_error": None,
                      "last_at": None}

    # ------------------------------------------------------------------ filer og status
    @property
    def enabled(self) -> bool:
        """Root-hjælperen er installeret (install.sh lægger markøren)."""
        return (self.state / "llm-enabled").is_file()

    @property
    def incoming(self) -> Path:
        return self.dir / "incoming.tar"

    def _staged(self) -> dict[str, Any] | None:
        try:
            data = json.loads((self.dir / "staged.json").read_text(encoding="utf-8"))
            return data if isinstance(data, dict) and self.incoming.is_file() else None
        except (OSError, ValueError):
            return None

    def _installed(self) -> dict[str, Any] | None:
        """Hjælperens status (llm.json): installeret pakke, ønsket tilstand, seneste handling og fejl."""
        try:
            data = json.loads((self.state / "llm.json").read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, ValueError):
            return None

    def _pending(self) -> dict[str, str] | None:
        req = self.dir / "llm.request"
        try:
            if time.time() - req.stat().st_mtime >= PENDING_MAX_S:
                return None
            return dict(line.split("=", 1) for line in req.read_text(encoding="utf-8").splitlines() if "=" in line)
        except (OSError, ValueError):
            return None

    async def status(self) -> dict[str, Any]:
        hw = self.hw.status()
        health = await self.client.health() if self.enabled else {"ok": False, "status": "unavailable", "model": None}
        return {
            "helper_installed": self.enabled, "hw": hw, "installed": self._installed(), "staged": self._staged(),
            "pending": self._pending(), "service": health, "busy": self._sem.locked(), "waiting": self.waiting,
            "stats": dict(self.stats), "available": bool(hw["llm_allowed"] and health["ok"]),
        }

    def metrics(self) -> dict[str, Any]:
        return {"requests": self.stats["requests"], "errors": self.stats["errors"], "busy": int(self._sem.locked()),
                "waiting": self.waiting, "last_ms": self.stats["last_ms"] or 0}

    # ------------------------------------------------------------------ LLM-pakke
    @contextmanager
    def receiving(self) -> Iterator[Path]:
        if not self._receiving.acquire(blocking=False):
            raise ServiceError(409, "En LLM-pakke modtages allerede — vent til den er færdig")
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            yield self.dir / "receiving.tar"
        finally:
            (self.dir / "receiving.tar").unlink(missing_ok=True)
            self._receiving.release()

    def precheck(self, length: int | None) -> None:
        """Før upload: må hjælperen bruges, og er der plads? (Content-Length kan mangle — så tjekkes undervejs.)"""
        if not self.hw.status()["llm_allowed"]:
            raise ServiceError(409, "Hardwareprofilen tillader ikke hjælperen — vælg en profil med LLM (System › Hjælper)")
        self.dir.mkdir(parents=True, exist_ok=True)
        free = _free_bytes(self.dir)
        if free is not None and length is not None and free < length + DISK_RESERVE_BYTES:
            raise ServiceError(507, f"For lidt diskplads: LLM-pakken fylder {length / 1e9:.1f} GB, og der skal være "
                                    f"{DISK_RESERVE_BYTES / 1e9:.0f} GB tilbage — der er {free / 1e9:.1f} GB fri")

    def check_space_during_upload(self) -> None:
        free = _free_bytes(self.dir)
        if free is not None and free < DISK_RESERVE_BYTES:
            raise ServiceError(507, "Uploaden er stoppet: disken er ved at være fuld (databasen skal have plads)")

    def stage(self, actor: str, received: Path, sha256: str, machine_arch: str) -> dict[str, Any]:
        """En modtaget pakke kontrolleres og lægges klar til installation (`incoming.tar` + `staged.json`)."""
        if not self.hw.status()["llm_allowed"]:
            raise ServiceError(409, "Hardwareprofilen tillader ikke hjælperen — vælg en profil med LLM (System › Hjælper)")
        info = inspect_package(received, sha256, machine_arch)
        free = _free_bytes(self.dir)
        need = info["size"] + 1024 ** 3     # installationen: én pakkestørrelse mere ad gangen (se apply-llm.sh) + 1 GB luft
        if free is not None and free < need:
            raise ServiceError(507, f"For lidt diskplads til installationen: kræver ca. {need / 1e9:.1f} GB fri ud over "
                                    f"pakken, der er {free / 1e9:.1f} GB")
        received.replace(self.incoming)
        info["by"] = actor
        info["at"] = time.time()
        (self.dir / "staged.json").write_text(json.dumps(info), encoding="utf-8")
        log.info("LLM-pakke modtaget af %s: %s (%s, %.2f GB, sha256 %s)", actor, info["manifest"]["model"]["name"],
                 info["manifest"]["llama_build"], info["size"] / 1e9, sha256[:12])
        return info

    def discard(self) -> None:
        self.incoming.unlink(missing_ok=True)
        (self.dir / "staged.json").unlink(missing_ok=True)

    # ------------------------------------------------------------------ styring af tjenesten
    def request(self, action: str, actor: str) -> dict[str, Any]:
        if action not in ACTIONS:
            raise ServiceError(400, f"Ukendt handling '{action}' — vælg en af: {', '.join(ACTIONS)}")
        if not self.enabled:
            raise ServiceError(409, "Hjælperens styring er ikke installeret på maskinen — opdatér SCADA'en (System › Opdatering)")
        if self._pending():
            raise ServiceError(409, "En handling på hjælperen er allerede i gang — vent til den er færdig")
        hw = self.hw.status()
        lines = {"action": action, "by": re.sub(r"[^A-Za-z0-9._-]", "", actor)[:40] or "ukendt", "id": secrets.token_hex(4)}
        if action in ("install", "start"):
            if not hw["llm_allowed"]:
                raise ServiceError(409, f"Hardwareprofilen '{hw['profile']}' tillader ikke hjælperen")
            lines["threads"] = str(hw["llm_threads"])
            lines["mem_mb"] = str(hw["llm_mem_mb"])
        if action == "install":
            staged = self._staged()
            if staged is None:
                raise ServiceError(409, "Upload en LLM-pakke først")
            lines["sha256"] = staged["sha256"]
        if action == "start" and not (self._installed() or {}).get("model"):
            raise ServiceError(409, "Ingen LLM-pakke er installeret endnu")
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / "llm.request.tmp"
        tmp.write_text("".join(f"{k}={v}\n" for k, v in lines.items()), encoding="utf-8")
        tmp.replace(self.dir / "llm.request")
        log.warning("Hjælper: %s bestilt af %s", action, lines["by"])
        return {"requested": action}

    # ------------------------------------------------------------------ kald til modellen
    async def complete(self, messages: list[dict[str, str]], *, schema: dict[str, Any] | None = None,
                       max_tokens: int = 400, timeout: float = 90.0) -> Any:
        """Ét kald til modellen — højst ét ad gangen; de næste venter (tælles som `waiting`)."""
        if not self.hw.status()["llm_allowed"]:
            raise ServiceError(409, "Hjælperen er ikke slået til på denne hardware")
        self.waiting += 1
        try:
            await asyncio.wait_for(self._sem.acquire(), timeout=timeout)
        except asyncio.TimeoutError:
            raise ServiceError(503, "Hjælperen er optaget — prøv igen om lidt") from None
        finally:
            self.waiting -= 1
        self.stats["requests"] += 1
        self.stats["last_at"] = time.time()
        try:
            if schema is not None:
                data, done = await self.client.chat_json(messages, schema, max_tokens=max_tokens, timeout=timeout)
            else:
                done = await self.client.chat(messages, max_tokens=max_tokens, timeout=timeout)
                data = done.text
            self.stats["last_ms"] = round(done.ms)
            self.stats["last_tokens_per_s"] = done.tokens_per_s
            return data, done
        except LlmError as exc:
            self.stats["errors"] += 1
            self.stats["last_error"] = exc.message
            log.warning("Hjælper-kald fejlede (%s): %s", exc.kind, exc.message)
            raise ServiceError(503 if exc.kind in ("unavailable", "busy", "timeout") else 502, exc.message) from None
        finally:
            self._sem.release()

    async def selftest(self) -> dict[str, Any]:
        """Lille afprøvning med fast JSON-svar: virker modellen, og hvor hurtig er den?"""
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}, "svar": {"type": "string", "maxLength": 80}},
                  "required": ["ok", "svar"], "additionalProperties": False}
        data, done = await self.complete([
            {"role": "system", "content": "Du er en hjælper i et SCADA-system. Svar kort på dansk i JSON."},
            {"role": "user", "content": "Hvad bruges en cirkulationspumpe til i et varmeanlæg? Én sætning."},
        ], schema=schema, max_tokens=120, timeout=120)
        return {"answer": data.get("svar") if isinstance(data, dict) else None, "ms": round(done.ms),
                "tokens_in": done.tokens_in, "tokens_out": done.tokens_out, "tokens_per_s": done.tokens_per_s, "model": done.model}


def _free_bytes(path: Path) -> int | None:
    import shutil
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None
