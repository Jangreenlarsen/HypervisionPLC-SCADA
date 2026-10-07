"""SVG-filer pr. tegningsversion: <data>/drawings/<id>/v<N>.svg."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


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
