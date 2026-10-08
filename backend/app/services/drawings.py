"""Tegninger: upload (saneret), versioner, bindinger og den samlede visning til Overview."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from ..storage.db import Database
from ..storage.files import DrawingFiles
from .bindings import BindingError, auto_binding, validate_binding
from .errors import ServiceError
from .live_cache import LiveCache
from .svg_sanitize import SvgError, index_svg, sanitize_svg
from .tagsource import TagSourceError, parse_source


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name.replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
                                 .replace("Æ", "ae").replace("Ø", "oe").replace("Å", "aa"))
    text = re.sub(r"[^a-z0-9]+", "-", text.encode("ascii", "ignore").decode().lower()).strip("-")
    return text[:48] or "tegning"


def _report(result: Any) -> dict[str, Any]:
    return {
        "removed_elements": result.removed_elements,
        "removed_attributes": result.removed_attributes,
        "element_count": len(result.element_ids),
    }


class DrawingService:
    def __init__(self, db: Database, files: DrawingFiles, cache: LiveCache):
        self.db = db
        self.files = files
        self.cache = cache

    # ------------------------------------------------------------- tegninger

    def list(self) -> list[dict[str, Any]]:
        return [{k: d[k] for k in ("id", "name", "active_version", "version_count", "updated_at")}
                for d in self.db.list_drawings()]

    def _require(self, drawing_id: str) -> dict[str, Any]:
        drawing = self.db.get_drawing(drawing_id)
        if drawing is None:
            raise ServiceError(404, f"Tegningen '{drawing_id}' findes ikke")
        return drawing

    def get(self, drawing_id: str) -> dict[str, Any]:
        drawing = self._require(drawing_id)
        versions = [{k: v[k] for k in ("version", "comment", "size", "width", "height", "created_at")}
                    for v in self.db.list_versions(drawing_id)]
        return {"id": drawing["id"], "name": drawing["name"], "active_version": drawing["active_version"],
                "versions": versions}

    def create(self, name: str, svg: str, comment: str = "") -> dict[str, Any]:
        name = (name or "").strip()
        if not name:
            raise ServiceError(400, "Tegningen skal have et navn")
        if len(name) > 80:
            raise ServiceError(400, "Navnet må højst være 80 tegn")
        result = self._sanitize(svg)
        base = slugify(name)
        drawing_id, n = base, 2
        while self.db.get_drawing(drawing_id) is not None:
            drawing_id, n = f"{base}-{n}", n + 1
        meta = {"size": len(result.svg.encode()), "width": result.width, "height": result.height, "comment": comment}
        version = self.db.add_drawing_version(drawing_id, name, meta, activate=True)
        self.files.write(drawing_id, version, result.svg)
        return {"drawing": self.get(drawing_id), "report": _report(result)}

    def add_version(self, drawing_id: str, svg: str, comment: str = "", activate: bool = True) -> dict[str, Any]:
        self._require(drawing_id)
        result = self._sanitize(svg)
        meta = {"size": len(result.svg.encode()), "width": result.width, "height": result.height, "comment": comment}
        # DB'en tildeler versionsnummeret atomisk; filen skrives derefter under netop det nummer.
        version = self.db.add_drawing_version(drawing_id, None, meta, activate=activate)
        self.files.write(drawing_id, version, result.svg)
        ids = set(result.element_ids)
        orphans = sorted({b["element"] for b in self.db.list_bindings(drawing_id)} - ids)
        report = _report(result)
        report["orphaned_bindings"] = orphans
        return {"drawing": self.get(drawing_id), "version": version, "report": report}

    def _sanitize(self, svg: str) -> Any:
        try:
            return sanitize_svg(svg)
        except SvgError as exc:
            raise ServiceError(400, str(exc)) from None

    def rename(self, drawing_id: str, name: str) -> dict[str, Any]:
        self._require(drawing_id)
        name = (name or "").strip()
        if not name or len(name) > 80:
            raise ServiceError(400, "Navnet skal være 1-80 tegn")
        self.db.rename_drawing(drawing_id, name)
        return self.get(drawing_id)

    def activate(self, drawing_id: str, version: int) -> dict[str, Any]:
        self._require(drawing_id)
        if version not in {v["version"] for v in self.db.list_versions(drawing_id)}:
            raise ServiceError(404, f"Version {version} findes ikke for '{drawing_id}'")
        self.db.set_active_version(drawing_id, version)
        return self.get(drawing_id)

    def delete(self, drawing_id: str) -> None:
        self._require(drawing_id)
        self.db.delete_drawing(drawing_id)
        self.files.delete(drawing_id)

    def svg(self, drawing_id: str, version: int | None = None) -> str:
        drawing = self._require(drawing_id)
        v = version if version is not None else drawing["active_version"]
        text = self.files.read(drawing_id, v)
        if text is None:
            raise ServiceError(404, f"SVG-filen for '{drawing_id}' version {v} mangler på disken")
        return text

    # ------------------------------------------------------------- bindinger

    def bindings(self, drawing_id: str) -> list[dict[str, Any]]:
        self._require(drawing_id)
        return self.db.list_bindings(drawing_id)

    def set_element_bindings(self, drawing_id: str, element: str, items: list[Any]) -> list[dict[str, Any]]:
        index = index_svg(self.svg(drawing_id))
        # En tom liste fjerner bindingerne — det skal også virke for forældreløse bindinger,
        # hvis element er forsvundet i en ny version af tegningen.
        if element not in index and items:
            raise ServiceError(400, f"Elementet '{element}' findes ikke i den aktive version af tegningen")
        normalized = []
        for item in items:
            try:
                b = validate_binding(item)
            except BindingError as exc:
                raise ServiceError(400, str(exc)) from None
            if self.db.get_tag(b["tag"]) is None:
                raise ServiceError(400, f"Tagget '{b['tag']}' findes ikke")
            normalized.append(b)
        self.db.set_element_bindings(drawing_id, element, normalized)
        return [b for b in self.db.list_bindings(drawing_id) if b["element"] == element]

    # ----------------------------------------------------------------- visning

    def view(self, drawing_id: str) -> dict[str, Any]:
        """Alt Overview behøver: SVG, effektive bindinger (eksplicitte + auto) og tag-metadata."""
        drawing = self._require(drawing_id)
        svg = self.svg(drawing_id)
        index = index_svg(svg)
        tags = {t["name"]: t for t in self.db.list_tags()}

        effective: list[dict[str, Any]] = []
        orphans: list[str] = []
        explicit_elements: set[str] = set()
        for b in self.db.list_bindings(drawing_id):
            explicit_elements.add(b["element"])
            if b["element"] not in index:
                orphans.append(b["element"])
                continue
            effective.append({**b, "source": "explicit"})

        for element, (el_tag, label) in index.items():
            if element in explicit_elements:
                continue
            name = element if element in tags else label if label in tags else None
            if name is None:
                continue
            auto = auto_binding(el_tag, {"name": name, "is_bool": self._is_bool(tags[name])})
            if auto is not None:
                effective.append({"element": element, "position": 0, **auto, "source": "auto"})

        used = sorted({b["tag"] for b in effective})
        meta = {n: {"unit": tags[n]["unit"], "decimals": tags[n]["decimals"], "description": tags[n]["description"],
                    "plc": tags[n]["plc"]} for n in used if n in tags}
        return {"id": drawing["id"], "name": drawing["name"], "version": drawing["active_version"],
                "svg": svg, "bindings": effective, "orphaned_bindings": sorted(set(orphans)), "tags": meta}

    def _is_bool(self, tag: dict[str, Any]) -> bool:
        try:
            source = parse_source(tag["source"])
        except TagSourceError:
            return False
        if source.datatype == "bool":
            return True
        return isinstance(self.cache.get(tag["name"]).value, bool)  # ST-variabler: kendes først fra live-værdien
