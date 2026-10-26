"""SVG-filer pr. tegningsversion: <data>/drawings/<id>/v<N>.svg."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}\Z")


class DrawingFiles:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def _dir(self, drawing_id: str) -> Path:
        if not _SAFE_ID.match(drawing_id):  # forsvar mod sti-traversering
            raise ValueError(f"ugyldigt tegnings-id: {drawing_id!r}")
        return self.root / drawing_id

    def write(self, drawing_id: str, version: int, svg: str) -> None:
        d = self._dir(drawing_id)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f"v{version}.svg.tmp"
        tmp.write_text(svg, encoding="utf-8")
        os.replace(tmp, d / f"v{version}.svg")

    def read(self, drawing_id: str, version: int) -> str | None:
        path = self._dir(drawing_id) / f"v{version}.svg"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def delete(self, drawing_id: str) -> None:
        shutil.rmtree(self._dir(drawing_id), ignore_errors=True)

    # ---------------------------------------------------- backup/restore

    def stage(self, files: dict[tuple[str, int], str]) -> Path:
        """Skriv et komplet nyt sæt filer i en staging-mappe ved siden af den aktive."""
        staging = self.root.with_name(self.root.name + ".staging")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        for (drawing_id, version), svg in files.items():
            if not _SAFE_ID.match(drawing_id):
                raise ValueError(f"ugyldigt tegnings-id: {drawing_id!r}")
            d = staging / drawing_id
            d.mkdir(exist_ok=True)
            (d / f"v{version}.svg").write_text(svg, encoding="utf-8")
        return staging

    def swap_in(self, staging: Path) -> Path:
        """Byt staging ind som aktiv; returnerer den gamle mappe (til tilbagerulning/sletning)."""
        old = self.root.with_name(self.root.name + ".old")
        shutil.rmtree(old, ignore_errors=True)
        os.replace(self.root, old)
        os.replace(staging, self.root)
        return old

    def swap_back(self, old: Path) -> None:
        failed = self.root.with_name(self.root.name + ".failed")
        shutil.rmtree(failed, ignore_errors=True)
        os.replace(self.root, failed)
        os.replace(old, self.root)
        shutil.rmtree(failed, ignore_errors=True)
