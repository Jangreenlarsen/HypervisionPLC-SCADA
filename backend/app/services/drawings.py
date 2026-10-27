"""Tegninger: upload (saneret), versioner, bindinger og den samlede visning til Overview."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from ..storage.db import Database
from ..storage.files import DrawingFiles
from .bindings import CLICK_TYPES, WRITE_CLICKS, BindingError, _spec_list, auto_binding, binding_tags, symbol_bindings, validate_binding
from .errors import ServiceError
from .live_cache import LiveCache
from .svg_sanitize import SvgError, index_svg, sanitize_svg, subtree_ids, subtree_map, symbol_specs
from .symbols import config_bindings, symbol_view
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
        return [{**{k: d[k] for k in ("id", "name", "active_version", "version_count", "updated_at")}, "start": d["id"] == start,
                 "disabled": bool(d["disabled"])}
                for d in self.db.list_drawings()]

    def disabled_ids(self) -> set[str]:
        """Deaktiverede tegninger (v1.6.0): offline — ingen live-data, ingen betjening, ingen symbol-runtime."""
        return {d["id"] for d in self.db.list_drawings() if d["disabled"]}

    def is_disabled(self, drawing_id: str) -> bool:
        d = self.db.get_drawing(drawing_id)
        return bool(d and d["disabled"])

    def set_disabled(self, drawing_id: str, disabled: bool) -> dict[str, Any]:
        self._require(drawing_id)
        self.db.set_drawing_disabled(drawing_id, disabled)
        return self.get(drawing_id)

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
                "disabled": bool(drawing["disabled"]), "versions": versions}

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
        # B4 (funktionsanalyse): også symboler sat op med guiden og gruppe-animationer, hvis element er væk
        report["orphaned_symbols"] = sorted(({r["element"] for r in self.db.list_symbol_configs(drawing_id)}
                                             | {r["element"] for r in self.db.list_group_anims(drawing_id)}) - ids)
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

    def usage(self, drawing_id: str) -> dict[str, Any]:
        """Hvad en sletning rammer — til bekræftelsen i brugerfladen."""
        drawing = self._require(drawing_id)
        names = {d["id"]: d["name"] for d in self.db.list_drawings()}
        all_bindings = self.db.list_all_bindings()
        gotos = sorted({names.get(b["drawing_id"], b["drawing_id"]) for b in all_bindings
                        if b["anim"] == "click:goto" and b["params"].get("drawing") == drawing_id and b["drawing_id"] != drawing_id})
        return {
            "id": drawing["id"], "name": drawing["name"],
            "versions": len(self.db.list_versions(drawing_id)),
            "bindings": sum(1 for b in all_bindings if b["drawing_id"] == drawing_id),
            "goto_from": gotos,                       # andre tegninger med en "gå til"-knap hertil
            "start": self.db.get_setting("start_drawing") == drawing_id,
            "users": self.db.users_with_drawing(drawing_id),  # brugere med adgang (begrænset til udvalgte tegninger)
        }

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
        normalized = self._normalize_bindings(items)
        if normalized:
            self._refuse_if_configured(drawing_id, element, normalized)
        self.db.set_element_bindings(drawing_id, element, normalized)
        return [b for b in self.db.list_bindings(drawing_id) if b["element"] == element]

    def _config_owner(self, drawing_id: str, element: str) -> tuple[str, dict[str, Any]] | None:
        """Det wizard-konfigurerede symbol, som elementet er (en del af) — eller None."""
        configs = {r["element"]: r["config"] for r in self.db.list_symbol_configs(drawing_id)}
        if not configs:
            return None
        if element in configs:
            return element, configs[element]
        for root, parts in subtree_map(self.svg(drawing_id), set(configs)).items():
            if element in parts:
                return root, configs[root]
        return None

    def _refuse_if_configured(self, drawing_id: str, element: str, items: list[dict[str, Any]]) -> None:
        """Funktionsanalyse B1: simple bindinger i et wizard-konfigureret symbol bruges ikke — afvis dem i stedet for at gemme
        døde bindinger. Undtagelse (B2): "Gå til tegning" på roden af et kun-visning-symbol gælder stadig."""
        owner = self._config_owner(drawing_id, element)
        if owner is None:
            return
        root, cfg = owner
        if items and element == root and cfg.get("op") == "view" and all(b["anim"] == "click:goto" for b in items):
            return
        where = f"'{root}'" if element == root else f"'{element}' er en del af symbolet '{root}', som"
        raise ServiceError(409, f"{where} er sat op med Opsæt symbol — simple bindinger her bruges ikke. Ret animationer og "
                                "betjening i Opsæt symbol" + (" (kun 'Gå til tegning' kan tilføjes på et kun-visning-symbol)"
                                                              if element == root and cfg.get("op") == "view" else ""))

    def _normalize_bindings(self, items: list[Any]) -> list[dict[str, Any]]:
        """Valider bindinger mod tags og regler (samme regler for manuelle og symbol-bindinger)."""
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
            if b["anim"] == "flow" and (dir_tag := b["params"].get("dir_tag")):
                if dir_tag == b["tag"]:
                    raise ServiceError(400, "Retnings-tagget skal være et andet tag end start/stop-tagget")
                if self.db.get_tag(dir_tag) is None:
                    raise ServiceError(400, f"Retnings-tagget '{dir_tag}' findes ikke")
            if b["anim"] in WRITE_CLICKS and not tag["writable"]:
                raise ServiceError(400, f"Tagget '{b['tag']}' er ikke markeret skrivbart — ret det under Tags først")
            if b["anim"] in ("click:toggle", "click:pulse") and parse_source(tag["source"]).datatype == "real":
                raise ServiceError(400, f"{b['anim']} kræver et til/fra-tag (coil eller heltals-register), ikke real")
            normalized.append(b)
        if sum(1 for b in normalized if b["anim"] in CLICK_TYPES) > 1:
            raise ServiceError(400, "Et element kan kun have én klik-handling")
        return normalized

    # ----------------------------------------------------------------- symboler

    def _symbol_element(self, drawing_id: str, element: str) -> tuple[str, dict[str, Any] | None]:
        svg = self.svg(drawing_id)
        if element not in index_svg(svg):
            raise ServiceError(404, f"Elementet '{element}' findes ikke i den aktive version af tegningen")
        return svg, symbol_specs(svg).get(element)

    def set_symbol_description(self, drawing_id: str, element: str, text: Any) -> None:
        """Symbolets forklaring (gemmes ved bindingerne, ikke i tegningen — kan ændres uden ny version)."""
        if not isinstance(text, str):
            raise ServiceError(400, "Forklaringen skal være tekst")
        text = " ".join(text.split()) if "\n" not in text else "\n".join(" ".join(l.split()) for l in text.strip().splitlines())
        if len(text) > 500:
            raise ServiceError(400, "Forklaringen må højst være 500 tegn")
        self._symbol_element(drawing_id, element)
        self.db.set_symbol_description(drawing_id, element, text)

    def bind_symbol(self, drawing_id: str, element: str, tag: str | None) -> dict[str, Any]:
        """Tilknyt et tag til et betjeningssymbol (eller fjern det med None): bindinger for hele symbolet — klik-handling på
        roden og visning på delene — dannes ud fra symbolets egen beskrivelse og erstatter de eksisterende for symbolet."""
        svg, spec = self._symbol_element(drawing_id, element)
        if spec is None:
            raise ServiceError(400, f"'{element}' er ikke et symbol med færdige bindinger — brug 'Tilføj binding' på elementet")
        if tag is not None:
            self._refuse_if_configured(drawing_id, element, [])
        elements = [element] + [child for child, _ in spec["parts"]]
        warning = ""
        per_element: dict[str, list[dict[str, Any]]] = {e: [] for e in elements}
        if tag is not None:
            row = self.db.get_tag(tag)
            if row is None:
                raise ServiceError(400, f"Tagget '{tag}' findes ikke")
            built = symbol_bindings(spec, element, {"name": tag, "writable": bool(row["writable"])})
            for b in built:
                per_element.setdefault(b["element"], []).append({"tag": b["tag"], "anim": b["anim"], "params": b["params"]})
            wants_write = any(isinstance(x, dict) and x.get("anim") in WRITE_CLICKS for x in _spec_items(spec))
            if wants_write and not any(b["anim"] in WRITE_CLICKS for b in built):
                warning = (f"Tagget '{tag}' er ikke markeret skrivbart — klik-handlingen er ikke tilføjet, symbolet viser kun "
                           "værdien. Markér tagget skrivbart under Tags og tilknyt det igen.")
            per_element = {e: self._normalize_bindings(items) for e, items in per_element.items()}
        self.db.set_symbol_bindings(drawing_id, per_element)
        return {"tag": tag, "elements": len([e for e, i in per_element.items() if i]), "warning": warning}

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
        used = sorted({t for b in effective for t in binding_tags(b)})
        meta = {n: self._meta(tags[n]) for n in used if n in tags}
        pins = self.db.symbol_pin_keys()
        index = index_svg(svg)
        configured = {r["element"]: symbol_view(drawing_id, r["element"], r["config"], (drawing_id, r["element"]) in pins)
                      for r in self.db.list_symbol_configs(drawing_id) if r["element"] in index}
        for v in configured.values():
            for name in [v.get("fault"), v.get("tag"), *((v.get("chart") or {}).get("tags") or [])]:
                if name and name in tags and name not in meta:
                    meta[name] = self._meta(tags[name])
        return {"id": drawing["id"], "name": drawing["name"], "version": drawing["active_version"],
                "disabled": bool(drawing["disabled"]), "svg": svg, "bindings": effective, "orphaned_bindings": sorted(set(orphans)), "tags": meta,
                "symbols": self.db.list_symbol_meta(drawing_id), "symbol_config": configured}

    def legacy_bindings(self, drawing_id: str, element: str) -> list[dict[str, Any]]:
        """Bindinger efter den gamle model (eksplicitte + automatiske) for et symbol og dets dele — også hvis symbolet
        har en symbol-konfiguration. Bruges til at foreslå en konfiguration (Konvertér)."""
        svg = self.svg(drawing_id)
        subtree = subtree_ids(svg, {element})
        return [b for b in self._compute(drawing_id, legacy=True)[2] if b["element"] in subtree]

    def _compute(self, drawing_id: str, legacy: bool = False) -> tuple[dict[str, Any], str, list[dict[str, Any]], list[str], dict[str, Any]]:
        drawing = self._require(drawing_id)
        svg = self.svg(drawing_id)
        index = index_svg(svg)
        specs = symbol_specs(svg)
        tags = {t["name"]: t for t in self.db.list_tags()}

        effective: list[dict[str, Any]] = []
        orphans: list[str] = []
        explicit_elements: set[str] = set()
        # Symbolstandard: har et symbol en konfiguration, gælder den — gamle bindinger på symbolet og dets dele ignoreres
        configs = ({} if legacy else
                   {r["element"]: r["config"] for r in self.db.list_symbol_configs(drawing_id) if r["element"] in index})
        covered = subtree_ids(svg, set(configs))
        for b in self.db.list_bindings(drawing_id):
            explicit_elements.add(b["element"])
            if b["element"] not in index:
                orphans.append(b["element"])
                continue
            if b["element"] in covered and not (b["anim"] == "click:goto" and configs.get(b["element"], {}).get("op") == "view"):
                continue   # B2: "Gå til tegning" på roden af et kun-visning-symbol gælder stadig
            effective.append({**b, "source": "explicit"})

        for element, (el_tag, label) in index.items():
            if element in explicit_elements or element in covered:
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
        for element, cfg in configs.items():
            effective.extend(config_bindings(drawing_id, element, cfg, covered))
        if not legacy:
            effective.extend(self._group_bindings(drawing_id, svg, index))
        return drawing, svg, effective, orphans, tags

    def _group_bindings(self, drawing_id: str, svg: str, index: dict[str, Any]) -> list[dict[str, Any]]:
        """Animationer ejet af symbolgrupper (v0.131.0): lægges efter symbolets egne, i gruppernes rækkefølge, så de gælder
        samtidig; flere af samme slags på samme del afgøres af den eksisterende prioritetsregel (canvas.ts)."""
        out: list[dict[str, Any]] = []
        order: dict[int, int] = {}
        rows = [r for r in self.db.list_group_anims(drawing_id) if r["element"] in index]
        subtrees = subtree_map(svg, {r["element"] for r in rows})   # ÉN gennemgang af tegningen (ikke én pr. række)
        for row in rows:
            gi = order.setdefault(row["group_id"], len(order))
            parts = subtrees.get(row["element"], set())
            for b in config_bindings(drawing_id, row["element"], {"anims": row["anims"]}, parts):
                out.append({**b, "position": 2000 + gi * 100 + (b["position"] - 1000), "source": "group",
                            "group": row["group_id"], "group_name": row["group_name"]})
        return out

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


def _spec_items(spec: dict[str, Any]) -> list[Any]:
    """Alle binding-beskrivelser i et symbols spec (rod + dele)."""
    items = list(_spec_list(spec.get("auto", "")))
    for _, raw in spec.get("parts", []):
        items += _spec_list(raw)
    return items
