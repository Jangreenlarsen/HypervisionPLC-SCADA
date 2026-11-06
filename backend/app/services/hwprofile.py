"""Hardwareprofil (v3.37.0, PLAN.md › LLM-hjælper fase 0): hvad SCADA'en kører på, og om LLM-hjælperen kan slås til.

Profilen foreslås ud fra maskinen (`detect`: arkitektur, kerner, RAM, AVX2, Raspberry Pi-model) og bekræftes af en admin
(eller `install.sh --hw <profil>`). Den gemmes i `<data>/config/hw.json` (ejes af tjenesten). Profilen bestemmer, om
hjælperen må slås til, hvor mange tråde modellen får, og loftet for dens hukommelse.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
from pathlib import Path
from typing import Any

from .errors import ServiceError

log = logging.getLogger("scada.hw")

# id → tekst, om LLM er tilladt, anbefalet model-id, hukommelsesloft for LLM-tjenesten (MB)
PROFILES: dict[str, dict[str, Any]] = {
    "pi4": {"label": "Raspberry Pi 4", "llm": False, "llm_mem_mb": 0},
    "lille": {"label": "Lille VM/PC (under 8 GB RAM)", "llm": False, "llm_mem_mb": 0},
    "pi5": {"label": "Raspberry Pi 5 (8–16 GB)", "llm": True, "llm_mem_mb": 4500},
    "vm-8": {"label": "VM/PC med 8 GB RAM", "llm": True, "llm_mem_mb": 4500},
    "vm-16": {"label": "VM/PC med 16 GB RAM", "llm": True, "llm_mem_mb": 9000},
    "vm-32": {"label": "VM/PC med 32 GB RAM eller mere", "llm": True, "llm_mem_mb": 20000},
}
LLM_MIN_RAM_MB = 7000          # under det (efter SCADA'en) giver en 4B-model ingen mening
LLM_MIN_CPUS = 2


def parse_meminfo(text: str) -> int:
    """MemTotal i MB (0 hvis ukendt)."""
    m = re.search(r"^MemTotal:\s+(\d+)\s*kB", text, re.M)
    return int(m.group(1)) // 1024 if m else 0


def parse_cpu_flags(text: str) -> set[str]:
    """CPU-flag fra /proc/cpuinfo (x86 'flags', ARM 'Features')."""
    m = re.search(r"^(?:flags|Features)\s*:\s*(.*)$", text, re.M)
    return set(m.group(1).split()) if m else set()


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def suggest(arch: str, cpus: int, ram_mb: int, pi_model: str) -> str:
    """Profil ud fra målte tal — Pi-modellen vinder, ellers efter RAM."""
    if "Raspberry Pi 4" in pi_model or "Raspberry Pi 3" in pi_model:
        return "pi4"
    if "Raspberry Pi 5" in pi_model:
        return "pi5" if ram_mb >= LLM_MIN_RAM_MB else "pi4"
    if ram_mb >= 30000:
        return "vm-32"
    if ram_mb >= 15000:
        return "vm-16"
    if ram_mb >= LLM_MIN_RAM_MB:
        return "vm-8"
    return "pi4" if arch.startswith(("arm", "aarch")) and pi_model else "lille"


def detect() -> dict[str, Any]:
    """Det maskinen selv fortæller (kun læsning af /proc og /sys — ingen sideeffekter)."""
    arch = platform.machine() or "ukendt"
    cpus = os.cpu_count() or 1
    ram_mb = parse_meminfo(_read("/proc/meminfo"))
    flags = parse_cpu_flags(_read("/proc/cpuinfo"))
    pi_model = _read("/proc/device-tree/model").strip("\x00\n ")
    return {
        "arch": arch, "cpus": cpus, "ram_mb": ram_mb, "pi_model": pi_model,
        "avx2": "avx2" in flags, "neon": "asimd" in flags or "neon" in flags,
        "suggested": suggest(arch, cpus, ram_mb, pi_model),
    }


class HwProfileService:
    def __init__(self, data_dir: Path, detector: Any = detect):
        self.path = data_dir / "config" / "hw.json"
        self.detector = detector

    def _saved(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return raw if isinstance(raw, dict) and raw.get("profile") in PROFILES else {}

    def profile(self) -> str:
        """Den valgte profil — eller forslaget, hvis ingen er valgt endnu."""
        return self._saved().get("profile") or self.detector()["suggested"]

    def llm_threads(self, cpus: int | None = None) -> int:
        """Tråde til modellen: alle kerner minus én (SCADA'en skal altid have luft)."""
        n = cpus or self.detector()["cpus"]
        return max(1, n - 1)

    def status(self) -> dict[str, Any]:
        hw = self.detector()
        saved = self._saved()
        prof = saved.get("profile") or hw["suggested"]
        warnings = []
        if PROFILES[prof]["llm"]:
            if hw["arch"] in ("x86_64", "AMD64") and not hw["avx2"]:
                warnings.append("CPU'en giver ikke AVX2 videre — modellen bliver flere gange langsommere. "
                                "Sæt VM'ens CPU-type til 'host' (eller en type med AVX2).")
            if hw["ram_mb"] and hw["ram_mb"] < LLM_MIN_RAM_MB:
                warnings.append(f"Maskinen har {hw['ram_mb']} MB RAM — mindst {LLM_MIN_RAM_MB} MB anbefales til hjælperen.")
            if hw["cpus"] < LLM_MIN_CPUS:
                warnings.append("Kun én CPU-kerne — hjælperen vil konkurrere med SCADA'en.")
        return {
            "profile": prof, "confirmed": bool(saved), "set_by": saved.get("by"), "detected": hw,
            "llm_allowed": PROFILES[prof]["llm"], "llm_mem_mb": PROFILES[prof]["llm_mem_mb"],
            "llm_threads": self.llm_threads(hw["cpus"]), "warnings": warnings,
            "profiles": [{"id": k, "label": v["label"], "llm": v["llm"]} for k, v in PROFILES.items()],
        }

    def set_profile(self, profile: str, actor: str) -> dict[str, Any]:
        if profile not in PROFILES:
            raise ServiceError(400, f"Ukendt hardwareprofil '{profile}' — vælg en af: {', '.join(PROFILES)}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"profile": profile, "by": actor}), encoding="utf-8")
        tmp.replace(self.path)
        log.info("Hardwareprofil sat til %s af %s", profile, actor)
        return self.status()
