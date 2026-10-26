"""Server-side sanering af uploadede SVG-tegninger (ARCHITECTURE.md princip 5).

Hvidliste af SVG-elementer; alt andet fjernes. Derudover fjernes:
- alle `on*`-event-attributter
- `href`/`xlink:href` der ikke er en intern reference (`#id`) — undtaget `<image>` med
  rasterbillede som data-URI (png/jpeg/gif/webp, aldrig svg)
- `javascript:`/`data:` i enhver attribut, og `url(...)` til eksterne ressourcer i style
- `<style>` med `@import` eller eksterne `url(...)` renses
- SMIL-animation (`animate`, `set` ...) — kan sætte `href` til javascript:
- elementer/attributter fra fremmede navnerum, undtagen `inkscape:label` (bruges til
  auto-binding) og `sodipodi`/`inkscape`-metadata der blot droppes

XML parses med defusedxml (ingen DTD/entiteter → ingen XXE eller "billion laughs").
"""

from __future__ import annotations

import re
from typing import Any
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
MAX_SVG_BYTES = 5 * 1024 * 1024

ALLOWED_ELEMENTS = {
    "svg", "g", "defs", "symbol", "use", "title", "desc", "style",
    "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "text", "tspan", "textPath",
    "linearGradient", "radialGradient", "stop", "pattern", "clipPath", "mask", "marker", "image",
    "filter", "feGaussianBlur", "feOffset", "feBlend", "feColorMatrix", "feComposite", "feFlood",
    "feMerge", "feMergeNode", "feMorphology", "feDropShadow",
}
# Navn og forklaring på symboler/elementer: attribut → højeste længde
TEXT_ATTRS = {"data-hv-name": 60, "data-hv-desc": 500}
_RASTER_DATA_URI = re.compile(r"^data:image/(png|jpeg|jpg|gif|webp);base64,[A-Za-z0-9+/=\s]+$", re.I)
_DANGEROUS_VALUE = re.compile(r"(javascript|vbscript|data)\s*:", re.I)
_EXTERNAL_URL = re.compile(r"url\(\s*(['\"]?)(?!#)[^)]*\)", re.I)
_CSS_IMPORT = re.compile(r"@import[^;]*;?", re.I)
_CSS_ESCAPE = re.compile(r"\\([0-9a-fA-F]{1,6})[ \t\r\n\f]?|\\(.)", re.S)
_CSS_EXPRESSION = re.compile(r"expression\s*\(", re.I)


class SvgError(ValueError):
    pass


@dataclass
class SanitizeResult:
    svg: str
    removed_elements: dict[str, int] = field(default_factory=dict)
    removed_attributes: dict[str, int] = field(default_factory=dict)
    element_ids: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)  # id → inkscape:label
    width: float | None = None
    height: float | None = None

    @property
    def changed(self) -> bool:
        return bool(self.removed_elements or self.removed_attributes)


def _local(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{"):
        ns, _, name = tag[1:].partition("}")
        return ns, name
    return None, tag


def _count(d: dict[str, int], key: str) -> None:
    d[key] = d.get(key, 0) + 1


def _css_unescape(text: str) -> str:
    """Afkod CSS-escapes (`\\69` = i, `\\(` = `(`) — browseren gør det, så kontrollerne skal se det samme
    (kodeanalyse 2, G2: `@\\69mport` og `u\\72l(` slap ellers forbi)."""
    def one(m: re.Match[str]) -> str:
        if m.group(1) is not None:
            cp = int(m.group(1), 16)
            return chr(cp) if 0 < cp <= 0x10FFFF and not 0xD800 <= cp <= 0xDFFF else "�"
        return m.group(2)
    return _CSS_ESCAPE.sub(one, text)


def _clean_css(text: str) -> str:
    if "\\" in text:
        text = _css_unescape(text)
    text = _CSS_IMPORT.sub("", text)
    text = _EXTERNAL_URL.sub("none", text)
    return _CSS_EXPRESSION.sub("(", text)


def sanitize_svg(data: bytes | str) -> SanitizeResult:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if not raw or not raw.strip():
        raise SvgError("Filen er tom")
    if len(raw) > MAX_SVG_BYTES:
        raise SvgError(f"Tegningen er for stor ({len(raw) // 1024} KB) — max {MAX_SVG_BYTES // 1024 // 1024} MB")
    try:
        root = fromstring(raw, forbid_dtd=True)
    except DefusedXmlException:
        raise SvgError("SVG'en indeholder DTD/entiteter, som ikke er tilladt") from None
    except ET.ParseError as exc:
        raise SvgError(f"Ikke gyldig SVG/XML: {exc}") from None

    ns, name = _local(root.tag)
    if name != "svg" or ns not in (SVG_NS, None):
        raise SvgError("Filen er ikke en SVG-tegning (rodelementet skal være <svg>)")

    result = SanitizeResult(svg="")
    _clean_element(root, result)
    _ensure_viewbox(root, result)

    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    ET.register_namespace("inkscape", INKSCAPE_NS)
    result.svg = ET.tostring(root, encoding="unicode")
    return result


def _clean_element(el: ET.Element, result: SanitizeResult) -> None:
    for child in list(el):
        ns, name = _local(child.tag) if isinstance(child.tag, str) else (None, "")
        if not isinstance(child.tag, str) or ns not in (SVG_NS, None) or name not in ALLOWED_ELEMENTS:
            _count(result.removed_elements, name or "kommentar/processing-instruction")
            _remove_keep_tail(el, child)
            continue
        _clean_element(child, result)

    ns, name = _local(el.tag)
    for attr in list(el.attrib):
        a_ns, a_name = _local(attr)
        value = el.attrib[attr]
        reason = _attribute_problem(name, a_ns, a_name, value)
        if reason:
            _count(result.removed_attributes, reason)
            del el.attrib[attr]
        elif a_name == "style":
            cleaned = _clean_css(value)
            if cleaned != value:
                _count(result.removed_attributes, "style:url/import")
                el.attrib[attr] = cleaned
    if name == "style" and el.text:
        cleaned = _clean_css(el.text)
        if cleaned != el.text:
            _count(result.removed_attributes, "<style>:url/import")
            el.text = cleaned

    el_id = el.attrib.get("id")
    if el_id:
        result.element_ids.append(el_id)
        label = el.attrib.get(f"{{{INKSCAPE_NS}}}label")
        if label:
            result.labels[el_id] = label


def _attribute_problem(element: str, ns: str | None, name: str, value: str) -> str | None:
    if ns == INKSCAPE_NS:
        return None if name == "label" else f"inkscape:{name}"
    if ns not in (None, XLINK_NS, "http://www.w3.org/XML/1998/namespace"):
        return "fremmed navnerum"
    if name.lower().startswith("on"):
        return name.lower()
    if name in TEXT_ATTRS:
        # Symbolets navn/forklaring (sat i Tegn): vises kun som tekst, så "data:" i en forklaring er harmløst
        return None if len(value) <= TEXT_ATTRS[name] else f"{name} for lang"
    if name == "href":
        v = value.strip()
        if v.startswith("#"):
            return None
        if element == "image" and _RASTER_DATA_URI.match(v):
            return None
        return "ekstern href"
    plain = _css_unescape(value) if "\\" in value else value   # præsentationsattributter tolkes som CSS (G2)
    if _DANGEROUS_VALUE.search(plain) and name not in ("d", "points"):
        return f"{name}=javascript/data"
    if name != "style" and _EXTERNAL_URL.search(plain):
        return "ekstern url()"
    return None


def _remove_keep_tail(parent: ET.Element, child: ET.Element) -> None:
    """Fjern et element men bevar evt. tekst der stod efter det."""
    if child.tail and child.tail.strip():
        idx = list(parent).index(child)
        if idx > 0:
            prev = parent[idx - 1]
            prev.tail = (prev.tail or "") + child.tail
        else:
            parent.text = (parent.text or "") + child.tail
    parent.remove(child)


def _ensure_viewbox(root: ET.Element, result: SanitizeResult) -> None:
    """Viseren skalerer tegningen til skærmen og kræver derfor en viewBox."""
    vb = root.attrib.get("viewBox")
    if vb:
        parts = re.split(r"[\s,]+", vb.strip())
        if len(parts) == 4:
            try:
                result.width, result.height = float(parts[2]), float(parts[3])
                return
            except ValueError:
                pass
    w = _length(root.attrib.get("width"))
    h = _length(root.attrib.get("height"))
    if w is None or h is None:
        raise SvgError("Tegningen mangler viewBox og har ingen brugbar width/height — kan ikke skaleres")
    root.attrib["viewBox"] = f"0 0 {w:g} {h:g}"
    result.width, result.height = w, h


def _length(text: str | None) -> float | None:
    if not text:
        return None
    m = re.match(r"^\s*([0-9.]+)\s*(px|pt|mm|cm|in)?\s*$", text)
    if not m:
        return None
    factor = {"px": 1, None: 1, "pt": 4 / 3, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96}[m.group(2)]
    value = float(m.group(1)) * factor
    return value if value > 0 else None


def symbol_specs(svg: str) -> dict[str, dict[str, Any]]:
    """Betjeningssymboler: {rod-id: {"auto": data-hv-auto, "parts": [(barn-id, data-hv-part), ...]}}.
    Værdierne er rå tekst (JSON) — de valideres først når bindingerne dannes."""
    root = fromstring(svg.encode("utf-8"), forbid_dtd=True)
    out: dict[str, dict[str, Any]] = {}
    for el in root.iter():
        if not isinstance(el.tag, str) or not el.attrib.get("id") or "data-hv-auto" not in el.attrib:
            continue
        parts = [(c.attrib["id"], c.attrib["data-hv-part"]) for c in el.iter()
                 if c is not el and isinstance(c.tag, str) and c.attrib.get("id") and c.attrib.get("data-hv-part")]
        out[el.attrib["id"]] = {"auto": el.attrib["data-hv-auto"], "parts": parts}
    return out


def index_svg(svg: str) -> dict[str, tuple[str, str | None]]:
    """{element-id: (elementnavn, inkscape:label)} for en allerede saneret SVG."""
    root = fromstring(svg.encode("utf-8"), forbid_dtd=True)
    out: dict[str, tuple[str, str | None]] = {}
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        el_id = el.attrib.get("id")
        if el_id:
            out[el_id] = (_local(el.tag)[1], el.attrib.get(f"{{{INKSCAPE_NS}}}label"))
    return out


_TYPE_RE = re.compile(r"^[a-z0-9_]{1,40}\Z")
_STROKE_SHAPES = {"path", "line", "polyline", "polygon", "circle", "ellipse"}


def _shape_info(el: ET.Element) -> dict[str, Any]:
    """Hvad en del kan animeres med: elementtype og om den har streger/rør (til løbelys)."""
    name = _local(el.tag)[1]
    shapes = [el, *[c for c in el.iter() if c is not el]]
    has_line = False
    for s in shapes:
        if not isinstance(s.tag, str):
            continue
        sn = _local(s.tag)[1]
        stroke = (s.attrib.get("stroke") or "").strip()
        if sn == "rect" or (sn in _STROKE_SHAPES and stroke and stroke != "none"):
            has_line = True
            break
    return {"tag": name, "line": has_line}


def describe_element(svg: str, element_id: str) -> dict[str, Any] | None:
    """Et symbol i tegningen: elementtype, bibliotekstype (data-hv-type), navn og dele (børn med id).
    `parts`: {barn-id: {"tag", "line", "pid"}} — pid = delens id i biblioteket (data-hv-pid), hvis kendt.
    None hvis elementet ikke findes."""
    root = fromstring(svg.encode("utf-8"), forbid_dtd=True)
    for el in root.iter():
        if not isinstance(el.tag, str) or el.attrib.get("id") != element_id:
            continue
        sym_type = el.attrib.get("data-hv-type", "")
        parts: dict[str, dict[str, Any]] = {}
        for c in el.iter():
            if c is el or not isinstance(c.tag, str) or not c.attrib.get("id"):
                continue
            parts[c.attrib["id"]] = {**_shape_info(c), "pid": c.attrib.get("data-hv-pid")}
            if _local(c.tag)[1] == "text":   # teksten giver delen et navn i guiden (v0.81.0)
                parts[c.attrib["id"]]["text"] = " ".join("".join(c.itertext()).split())[:24]
        return {**_shape_info(el), "type": sym_type if _TYPE_RE.match(sym_type) else "custom",
                "name": el.attrib.get("data-hv-name"), "parts": parts}
    return None


def named_symbols(svg: str) -> list[dict[str, Any]]:
    """Symboler i tegningen: elementer med bibliotekstype (data-hv-type) eller et navn (data-hv-name), i dokumentrækkefølge.
    → [{"id", "name", "type"}] — til at vælge hvilke symboler en opsætning skal kopieres til."""
    root = fromstring(svg.encode("utf-8"), forbid_dtd=True)
    out: list[dict[str, Any]] = []
    for el in root.iter():
        if not isinstance(el.tag, str) or not el.attrib.get("id"):
            continue
        sym_type = el.attrib.get("data-hv-type", "")
        name = el.attrib.get("data-hv-name")
        if sym_type or name:
            out.append({"id": el.attrib["id"], "name": name, "type": sym_type if _TYPE_RE.match(sym_type) else "custom"})
    return out


def symbol_roots(svg: str) -> list[str]:
    """Bibliotekssymboler i tegningen (rødder med data-hv-type eller data-hv-auto), i dokumentrækkefølge."""
    root = fromstring(svg.encode("utf-8"), forbid_dtd=True)
    return [el.attrib["id"] for el in root.iter()
            if isinstance(el.tag, str) and el.attrib.get("id")
            and ("data-hv-type" in el.attrib or "data-hv-auto" in el.attrib)]


def subtree_map(svg: str, roots: set[str]) -> dict[str, set[str]]:
    """{rod: id'er i roden og dens efterkommere} — én gennemgang af tegningen uanset antal rødder."""
    out: dict[str, set[str]] = {}
    if not roots:
        return out
    root = fromstring(svg.encode("utf-8"), forbid_dtd=True)
    for el in root.iter():
        rid = el.attrib.get("id") if isinstance(el.tag, str) else None
        if rid in roots:
            out.setdefault(rid, set()).update(c.attrib["id"] for c in el.iter() if isinstance(c.tag, str) and c.attrib.get("id"))
    return out


def subtree_ids(svg: str, roots: set[str]) -> set[str]:
    """Alle id'er i de givne elementer og deres efterkommere (én gennemgang af tegningen)."""
    if not roots:
        return set()
    root = fromstring(svg.encode("utf-8"), forbid_dtd=True)
    out: set[str] = set()
    for el in root.iter():
        if isinstance(el.tag, str) and el.attrib.get("id") in roots:
            out.update(c.attrib["id"] for c in el.iter() if isinstance(c.tag, str) and c.attrib.get("id"))
    return out
