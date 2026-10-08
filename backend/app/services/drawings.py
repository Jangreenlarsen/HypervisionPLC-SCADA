"""Tegninger: upload (saneret), versioner, bindinger og den samlede visning til Overview."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from ..storage.db import Database
from ..storage.files import DrawingFiles
from .bindings import CLICK_TYPES, WRITE_CLICKS, BindingError, auto_binding, symbol_bindings, validate_binding
from .errors import ServiceError
from .live_cache import LiveCache
from .svg_sanitize import SvgError, index_svg, sanitize_svg, symbol_specs
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
        start = self.start_drawing()
        return [{**{k: d[k] for k in ("id", "name", "active_version", "version_count", "updated_at")}, "start": d["id"] == start}
                for d in self.db.list_drawings()]

    def start_drawing(self) -> str | None:
        """Tegningen Overview åbner med. En slettet tegning ignoreres (Overview falder tilbage til den første)."""
        start = self.db.get_setting("start_drawing")
        return start if start and self.db.get_drawing(start) is not None else None

    def set_start_drawing(self, drawing_id: str | None) -> None:
        drawing_id = (drawing_id or "").strip() or None
        if drawing_id is not None:
            self._require(drawing_id)
        self.db.set_setting("start_drawing", drawing_id)

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
        self.db.delete_drawing_scope(drawing_id)
        if self.db.get_setting("start_drawing") == drawing_id:
            self.db.set_setting("start_drawing", None)
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
            if b["anim"] == "click:goto":
                if self.db.get_drawing(b["params"]["drawing"]) is None:
                    raise ServiceError(400, f"Tegningen '{b['params']['drawing']}' findes ikke")
                normalized.append(b)
                continue
            tag = self.db.get_tag(b["tag"])
            if tag is None:
                raise ServiceError(400, f"Tagget '{b['tag']}' findes ikke")
            if b["anim"] in WRITE_CLICKS and not tag["writable"]:
                raise ServiceError(400, f"Tagget '{b['tag']}' er ikke markeret skrivbart — ret det under Tags først")
            if b["anim"] in ("click:toggle", "click:pulse") and parse_source(tag["source"]).datatype == "real":
                raise ServiceError(400, f"{b['anim']} kræver et til/fra-tag (coil eller heltals-register), ikke real")
            normalized.append(b)
        if sum(1 for b in normalized if b["anim"] in CLICK_TYPES) > 1:
            raise ServiceError(400, "Et element kan kun have én klik-handling")
        self.db.set_element_bindings(drawing_id, element, normalized)
        return [b for b in self.db.list_bindings(drawing_id) if b["element"] == element]

    # ----------------------------------------------------------------- visning

    def effective_bindings(self, drawing_id: str) -> list[dict[str, Any]]:
        """Eksplicitte + automatiske bindinger for den aktive version (uden forældreløse)."""
        return self._compute(drawing_id)[2]

    def view(self, drawing_id: str, visible_drawings: set[str] | None = None) -> dict[str, Any]:
        """Alt Overview behøver: SVG, effektive bindinger (eksplicitte + auto) og tag-metadata.
        `visible_drawings`: "gå til"-bindinger til tegninger brugeren ikke må se, fjernes."""
        drawing, svg, effective, orphans, tags = self._compute(drawing_id)
        if visible_drawings is not None:
            effective = [b for b in effective
                         if b["anim"] != "click:goto" or b["params"].get("drawing") in visible_drawings]
        used = sorted({b["tag"] for b in effective if b["tag"]})
        meta = {n: self._meta(tags[n]) for n in used if n in tags}
        return {"id": drawing["id"], "name": drawing["name"], "version": drawing["active_version"],
                "svg": svg, "bindings": effective, "orphaned_bindings": sorted(set(orphans)), "tags": meta}

    def _compute(self, drawing_id: str) -> tuple[dict[str, Any], str, list[dict[str, Any]], list[str], dict[str, Any]]:
        drawing = self._require(drawing_id)
        svg = self.svg(drawing_id)
        index = index_svg(svg)
        specs = symbol_specs(svg)
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
            if element in specs:
                # Betjeningssymbol: klik-handling + visning ifølge symbolet (dele uden egne bindinger)
                for pos, b in enumerate(symbol_bindings(specs[element], element,
                                                        {"name": name, "writable": bool(tags[name]["writable"])})):
                    if b["element"] == element or b["element"] not in explicit_elements:
                        effective.append({**b, "position": pos, "source": "auto"})
                continue
            auto = auto_binding(el_tag, {"name": name, "is_bool": self._is_bool(tags[name])})
            if auto is not None:
                effective.append({"element": element, "position": 0, **auto, "source": "auto"})
        return drawing, svg, effective, orphans, tags

    def _meta(self, tag: dict[str, Any]) -> dict[str, Any]:
        """Det Overview behøver om et tag — også til setpunkt-dialogen."""
        try:
            source = parse_source(tag["source"])
            kind, datatype = source.kind, source.datatype
        except TagSourceError:
            kind, datatype = "?", "?"
        return {"unit": tag["unit"], "decimals": tag["decimals"], "description": tag["description"],
                "plc": tag["plc"], "writable": tag["writable"], "min": tag["min"], "max": tag["max"],
                "confirm_write": tag["confirm_write"], "kind": kind, "datatype": datatype,
                "is_bool": self._is_bool(tag)}

    def _is_bool(self, tag: dict[str, Any]) -> bool:
        try:
            source = parse_source(tag["source"])
        except TagSourceError:
            return False
        if source.datatype == "bool":
            return True
        return isinstance(self.cache.get(tag["name"]).value, bool)  # ST-variabler: kendes først fra live-værdien
