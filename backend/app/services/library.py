"""Egne symboler i symbolbiblioteket + bibliotekets opdeling (v3.28.0, PLAN.md).

En tekniker/admin gemmer et objekt eller en gruppe fra en tegning som et nyt bibliotekssymbol:
- **grafikken** tages fra tegningens gemte (rensede) SVG, flyttes til (0,0) og renses igen; elementer med id bliver
  symbolets navngivne **dele** (samme navn som delen havde i biblioteket, hvis den kom derfra — ellers dens id),
  og gradienter/markører som delene bruger, følger med i en `<defs>`;
- **standardopsætningen** (preset) er symbolets egen opsætning fra guiden plus animationerne fra indlejrede symboler,
  med delene omdøbt til delnavne. Tags fjernes som standard (de hører til anlægget, ikke symbolet).

Tegninger har altid deres egen kopi af et symbol (som de indbyggede): en ny version ændrer ingen tegning — den tages i
brug med "Erstat med symbol" i Tegn. Typen er `u_<navn>` og kan derfor aldrig kollidere med et indbygget symbol.

Opdelingen (`layout`) gælder hele biblioteket: egne sektioner, sektionernes rækkefølge og hvilken sektion og plads hvert
symbol (også de indbyggede) har. Den gemmes samlet med en revision, så to samtidige gem ikke overskriver hinanden.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any
from xml.etree import ElementTree as ET

from defusedxml.ElementTree import fromstring as _defused
from pydantic import ValidationError

from ..storage.db import Database
from .auth import CurrentUser
from .errors import ServiceError
from .svg_sanitize import SVG_NS, XLINK_NS, SvgError, _local, sanitize_svg
from .symbols import ALARM_REF, SymbolConfig

log = logging.getLogger("scada.library")


def _parse(text: str) -> ET.Element:
    return _defused(text.encode("utf-8"), forbid_dtd=True)

PREFIX = "u_"
TYPE_RE = re.compile(r"^u_[a-z0-9_]{1,38}\Z")
MAX_SYMBOLS = 500
MAX_SVG_BYTES = 256 * 1024
MAX_LABEL = 40
MAX_HINT = 200
MAX_SECTIONS = 50
MAX_SECTION_LABEL = 40
# De indbyggede kategorier (frontend/src/lib/symbols.ts CATEGORIES) + sektionen til egne symboler
BUILTIN_SECTIONS = ("betjening", "proces", "vvs", "el", "sol", "genveje")
OWN_SECTION = "egne"
SECTION_ID_RE = re.compile(r"^[a-z0-9_]{1,24}\Z")
ANY_TYPE_RE = re.compile(r"^[a-z0-9_]{1,40}\Z")
_SPECIAL_SRC = ("@pos", "@on", "@val:")   # kilder der ikke er et tag og ikke en logikblok
_URL_REF = re.compile(r"url\(\s*['\"]?#([^'\")\s]+)['\"]?\s*\)")
# Attributter på et element i tegningen, der hører til STEDET i tegningen og ikke til symbolet
_INSTANCE_ATTRS = ("data-hv-name", "data-hv-desc", "data-hv-type", "data-hv-ports", "data-hv-auto", "data-hv-part", "data-hv-pid")


def slug(text: str, limit: int = 38) -> str:
    """Navn → del af et id: små bogstaver, æøå omskrevet, alt andet `_`."""
    t = text.strip().lower().replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
    t = re.sub(r"[^a-z0-9_]+", "_", t).strip("_")
    return t[:limit].strip("_")


def type_for(label: str) -> str:
    s = slug(label)
    if not s:
        raise ServiceError(400, "Navnet skal indeholde mindst ét bogstav eller tal")
    return PREFIX + s


def clean_label(label: Any) -> str:
    if not isinstance(label, str) or not label.strip():
        raise ServiceError(400, "Symbolet skal have et navn")
    label = " ".join(label.split())
    if len(label) > MAX_LABEL:
        raise ServiceError(400, f"Navnet må højst være {MAX_LABEL} tegn")
    return label


def clean_hint(hint: Any) -> str:
    if hint is None:
        return ""
    if not isinstance(hint, str):
        raise ServiceError(400, "Forklaringen skal være tekst")
    hint = " ".join(hint.split())
    if len(hint) > MAX_HINT:
        raise ServiceError(400, f"Forklaringen må højst være {MAX_HINT} tegn")
    return hint


def clean_type(sym_type: Any) -> str:
    if not isinstance(sym_type, str) or not TYPE_RE.match(sym_type):
        raise ServiceError(404, "Symbolet findes ikke i biblioteket")
    return sym_type


# ------------------------------------------------------------------ grafik

def _is_tag_src(src: str) -> bool:
    return bool(src) and not src.startswith("@")


def _box(box: Any) -> tuple[float, float, float, float]:
    try:
        x, y, w, h = (float(box[k]) for k in ("x", "y", "w", "h"))
    except (TypeError, KeyError, ValueError):
        raise ServiceError(400, "Mangler objektets placering (x, y, w, h)") from None
    if not all(abs(v) < 1e6 for v in (x, y, w, h)) or w <= 0 or h <= 0:
        raise ServiceError(400, "Objektet har ingen størrelse — vælg et objekt med indhold")
    return x, y, w, h


def _refs(el: ET.Element) -> set[str]:
    """Id'er som elementet (og dets børn) peger på med url(#…) eller href="#…"."""
    out: set[str] = set()
    for e in el.iter():
        if not isinstance(e.tag, str):
            continue
        for k, v in e.attrib.items():
            if k in ("href", f"{{{XLINK_NS}}}href") and v.startswith("#"):
                out.add(v[1:])
            else:
                out.update(_URL_REF.findall(v))
        if _local(e.tag)[1] == "style" and e.text:
            out.update(_URL_REF.findall(e.text))
    return out


def _rename_refs(el: ET.Element, mapping: dict[str, str]) -> None:
    def sub(v: str) -> str:
        return _URL_REF.sub(lambda m: f"url(#{mapping.get(m.group(1), m.group(1))})", v)
    for e in el.iter():
        if not isinstance(e.tag, str):
            continue
        for k, v in list(e.attrib.items()):
            if k in ("href", f"{{{XLINK_NS}}}href") and v.startswith("#"):
                e.attrib[k] = "#" + mapping.get(v[1:], v[1:])
            elif "url(" in v:
                e.attrib[k] = sub(v)


def extract(svg: str, element_id: str, box: Any) -> tuple[str, dict[str, str], list[str]]:
    """Klip elementet ud af tegningen som et bibliotekssymbol.
    → (svg-fragment `<g>…</g>`, {element-id i tegningen: delnavn}, advarsler). Elementet selv får delnavnet "all"."""
    x, y, _w, _h = _box(box)
    root = _parse(svg)
    by_id = {e.attrib["id"]: e for e in root.iter() if isinstance(e.tag, str) and e.attrib.get("id")}
    src = by_id.get(element_id)
    if src is None:
        raise ServiceError(404, f"Elementet '{element_id}' findes ikke i den gemte version af tegningen — gem tegningen først")
    if _local(src.tag)[1] in ("svg", "defs", "title", "desc", "metadata", "style"):
        raise ServiceError(400, "Vælg et objekt eller en gruppe på tegningen")
    warnings: list[str] = []
    el = copy.deepcopy(src)

    # Dele: alle børn med id. Delnavnet er bibliotekets navn (data-hv-pid) hvis delen kom fra et symbol, ellers id'et.
    mapping: dict[str, str] = {element_id: "all"}
    used: set[str] = {"all"}
    for e in el.iter():
        if e is el or not isinstance(e.tag, str) or not e.attrib.get("id"):
            continue
        base = slug(e.attrib.get("data-hv-pid") or e.attrib["id"], 30) or "del"
        name, n = base, 2
        while name in used:
            name, n = f"{base}_{n}", n + 1
        used.add(name)
        mapping[e.attrib["id"]] = name
        e.attrib["id"] = name
    el.attrib.pop("id", None)
    for e in el.iter():
        if isinstance(e.tag, str):
            for a in _INSTANCE_ATTRS:
                e.attrib.pop(a, None)

    # Gradienter, markører m.m. som symbolet bruger, følger med (også dem de selv peger på)
    defs: list[ET.Element] = []
    want, seen = _refs(el), set()
    while want:
        rid = want.pop()
        if rid in seen:
            continue
        seen.add(rid)
        target = by_id.get(rid)
        if target is None:
            warnings.append(f"Henvisningen #{rid} findes ikke i tegningen og er ikke med")
            continue
        if rid in mapping:   # en del i selve symbolet
            continue
        d = copy.deepcopy(target)
        defs.append(d)
        want |= _refs(d) - seen
    ref_map: dict[str, str] = {}
    for d in defs:
        for e in d.iter():
            if not isinstance(e.tag, str) or not e.attrib.get("id"):
                continue
            old = e.attrib["id"]
            name, n = "def_" + (slug(old, 26) or "x"), 2
            while name in used:
                name, n = f"def_{slug(old, 26) or 'x'}_{n}", n + 1
            used.add(name)
            ref_map.setdefault(old, name)
            e.attrib["id"] = name
    ref_map.update({k: v for k, v in mapping.items() if v != "all"})
    _rename_refs(el, ref_map)
    for d in defs:
        _rename_refs(d, ref_map)

    # Symbolets rod sættes på plads ved indsættelse (translate); flytningen til (0,0) ligger derfor i en indre gruppe
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    outer = ET.Element(f"{{{SVG_NS}}}g")
    if defs:
        d_el = ET.SubElement(outer, f"{{{SVG_NS}}}defs")
        d_el.extend(defs)
    inner = ET.SubElement(outer, f"{{{SVG_NS}}}g", {"transform": f"translate({-x:g} {-y:g})"})
    inner.append(el)
    fragment = ET.tostring(outer, encoding="unicode")
    return clean_fragment(fragment, box), mapping, warnings


def clean_fragment(fragment: str, box: Any) -> str:
    """Rens et symbol-fragment med tegningernes regler (svg_sanitize) og returnér det rensede `<g>`."""
    _x, _y, w, h = _box(box)
    doc = f'<svg xmlns="{SVG_NS}" xmlns:xlink="{XLINK_NS}" viewBox="0 0 {w:g} {h:g}">{fragment}</svg>'
    try:
        res = sanitize_svg(doc)
    except SvgError as exc:
        raise ServiceError(400, f"Grafikken kan ikke bruges: {exc}") from None
    root = _parse(res.svg)
    kids = [c for c in root if isinstance(c.tag, str)]
    if len(kids) != 1 or _local(kids[0].tag)[1] != "g":
        raise ServiceError(400, "Symbolet skal være ét <g>-element")
    out = ET.tostring(kids[0], encoding="unicode")
    if len(out.encode("utf-8")) > MAX_SVG_BYTES:
        raise ServiceError(400, f"Symbolet er for stort ({len(out.encode('utf-8')) // 1024} KB) — højst {MAX_SVG_BYTES // 1024} KB")
    return out


# ------------------------------------------------------------------ standardopsætning

def build_preset(configs: dict[str, dict[str, Any]], mapping: dict[str, str], keep_tags: bool,
                 names: dict[str, str]) -> tuple[dict[str, Any] | None, list[str]]:
    """Saml opsætningerne for elementet og de indlejrede symboler til én standardopsætning med delnavne.
    Højst ét af dem må have betjening (et symbol har én betjeningsform). → (preset eller None, advarsler)."""
    warnings: list[str] = []
    mine = {el: cfg for el, cfg in configs.items() if el in mapping}
    if not mine:
        return None, warnings
    operating = [el for el, c in mine.items() if c.get("op", "view") != "view"]
    if len(operating) > 1:
        who = ", ".join(f"'{names.get(el) or el}'" for el in operating)
        raise ServiceError(400, f"Et symbol kan kun have én betjening, men {who} har hver deres. "
                                "Gør dem til 'Kun passiv visning' i guiden, eller gem dem som hvert sit symbol.")
    root_el = next((el for el, p in mapping.items() if p == "all"), None)
    base_el = operating[0] if operating else (root_el if root_el in mine else next(iter(mine)))
    base = copy.deepcopy(mine[base_el])
    own_blocks = {b.get("id") for b in base.get("logic", [])}

    def part_of(el: str, part: str) -> str | None:
        if part == "all":
            return mapping.get(el)
        return mapping.get(part)

    anims: list[dict[str, Any]] = []
    for el in [base_el] + [e for e in mine if e != base_el]:
        for a in mine[el].get("anims", []):
            p = part_of(el, a.get("part", ""))
            if p is None:
                warnings.append(f"En animation på '{names.get(el) or el}' peger på en del uden for objektet og er ikke med")
                continue
            src = a.get("src", "")
            if el != base_el and src.startswith("@") and not src.startswith(_SPECIAL_SRC + (ALARM_REF,)):
                warnings.append(f"En animation på '{names.get(el) or el}' bruger en logikblok i et andet symbol og er ikke med")
                continue
            if el != base_el and src == "@pos":
                warnings.append(f"En animation på '{names.get(el) or el}' følger det symbols position og er ikke med")
                continue
            anims.append({**a, "part": p})
    base["anims"] = anims
    if not base.get("chart"):
        base["chart"] = next((c["chart"] for c in mine.values() if c.get("chart")), None)
    # Logikblokke, der peger på andre symboler på tegningen (`@<symbol>:<blok>`), giver ingen mening i et bibliotekssymbol
    for b in base.get("logic", []):
        for i in b.get("inputs", []):
            s = i.get("src", "")
            if s.startswith("@") and ":" in s and not s.startswith(ALARM_REF):
                i["src"] = ""
                warnings.append(f"Logikblok '{b.get('name') or b.get('id')}': en indgang fra et andet symbol er fjernet")
            elif s.startswith("@") and s[1:] not in own_blocks and not s.startswith(ALARM_REF):
                i["src"] = ""
    base["lock"] = {"positions": [], "leave": False}   # nøglelåsen og koden hører til stedet i tegningen
    if not keep_tags:
        _strip_tags(base)
    try:
        preset = SymbolConfig.model_validate(base).model_dump()
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        raise ServiceError(400, f"Opsætningen kan ikke samles til ét symbol — {details}") from None
    return preset, warnings


def _strip_tags(cfg: dict[str, Any]) -> None:
    for s in cfg.get("signals", []):
        s["tag"], s["fb"] = "", ""
    cfg["fault"] = ""
    for a in cfg.get("anims", []):
        src = a.get("src", "")
        if _is_tag_src(src) or src.startswith(ALARM_REF):
            a["src"] = ""
        for k in ("dir_tag", "tag"):   # retnings-tag på løbelys m.fl.
            if isinstance(a.get("params"), dict) and isinstance(a["params"].get(k), str):
                a["params"][k] = ""
    for b in cfg.get("logic", []):
        for i in b.get("inputs", []):
            s = i.get("src", "")
            if _is_tag_src(s) or s.startswith(ALARM_REF):
                i["src"] = ""
    if cfg.get("chart"):
        cfg["chart"]["tags"] = []


def check_preset(preset: Any, svg: str) -> dict[str, Any] | None:
    """Et preset fra backup: skemaet og at delene findes i symbolets grafik."""
    if preset is None:
        return None
    try:
        cfg = SymbolConfig.model_validate(preset).model_dump()
    except ValidationError as exc:
        raise ServiceError(400, f"Ugyldig standardopsætning: {exc.errors()[0]['msg']}") from None
    parts = {e.attrib["id"] for e in _parse(svg).iter() if isinstance(e.tag, str) and e.attrib.get("id")}
    for a in cfg["anims"]:
        if a["part"] != "all" and a["part"] not in parts:
            raise ServiceError(400, f"Standardopsætningen bruger delen '{a['part']}', som ikke findes i symbolet")
    return cfg


# ------------------------------------------------------------------ opdeling

def clean_layout(raw: Any, known_own: set[str]) -> dict[str, Any]:
    """{sections: [{id, label}] (egne), order: [sektions-id], items: {type: [sektion, plads]}} — validér og normalisér."""
    if not isinstance(raw, dict):
        raise ServiceError(400, "Opdelingen skal være et objekt")
    sections: list[dict[str, str]] = []
    ids: set[str] = set(BUILTIN_SECTIONS) | {OWN_SECTION}
    raw_sections = raw.get("sections", [])
    if not isinstance(raw_sections, list) or len(raw_sections) > MAX_SECTIONS:
        raise ServiceError(400, f"Højst {MAX_SECTIONS} egne sektioner")
    labels: set[str] = set()
    for s in raw_sections:
        sid = s.get("id") if isinstance(s, dict) else None
        label = " ".join(str(s.get("label", "")).split()) if isinstance(s, dict) else ""
        if not isinstance(sid, str) or not SECTION_ID_RE.match(sid) or sid in ids:
            raise ServiceError(400, f"Ugyldigt eller dobbelt sektions-id: {sid!r}")
        if not label or len(label) > MAX_SECTION_LABEL:
            raise ServiceError(400, f"Sektionen skal have et navn på 1–{MAX_SECTION_LABEL} tegn")
        if label.casefold() in labels:
            raise ServiceError(400, f"Sektionen '{label}' findes to gange")
        labels.add(label.casefold())
        ids.add(sid)
        sections.append({"id": sid, "label": label})
    order = [o for o in raw.get("order", []) if isinstance(o, str) and o in ids] if isinstance(raw.get("order"), list) else []
    order = list(dict.fromkeys(order)) + [i for i in (*BUILTIN_SECTIONS, OWN_SECTION, *(s["id"] for s in sections)) if i not in order]
    items: dict[str, list[Any]] = {}
    raw_items = raw.get("items", {})
    if not isinstance(raw_items, dict) or len(raw_items) > 2000:
        raise ServiceError(400, "For mange symboler i opdelingen")
    for t, v in raw_items.items():
        if not isinstance(t, str) or not ANY_TYPE_RE.match(t):
            continue
        if t.startswith(PREFIX) and t not in known_own:
            continue   # et slettet eget symbol
        if not (isinstance(v, list) and len(v) == 2 and v[0] in ids and isinstance(v[1], int) and not isinstance(v[1], bool)):
            raise ServiceError(400, f"Ugyldig placering for '{t}'")
        items[t] = [v[0], max(0, min(v[1], 100000))]
    return {"sections": sections, "order": order, "items": items}


class LibraryService:
    def __init__(self, db: Database, drawings: Any, symbols: Any):
        self.db = db
        self.drawings = drawings
        self.symbols = symbols

    def _public(self, r: dict[str, Any]) -> dict[str, Any]:
        return {k: r[k] for k in ("type", "label", "hint", "svg", "preset", "version", "created_at", "created_by",
                                  "updated_at", "updated_by")}

    def _layout(self) -> dict[str, Any]:
        stored = self.db.get_library_layout() or {}
        try:
            clean = clean_layout(stored, {r["type"] for r in self.db.list_library_symbols()})
        except ServiceError:
            log.warning("Bibliotekets opdeling er beskadiget — standardopdelingen bruges")
            clean = clean_layout({}, set())
        return {**clean, "rev": int(stored.get("rev", 0)) if isinstance(stored.get("rev", 0), int) else 0}

    def list(self, with_presets: bool = True) -> dict[str, Any]:
        rows = [self._public(r) for r in self.db.list_library_symbols()]
        if not with_presets:   # standardopsætningen (evt. med tag-navne) er kun til teknikere/admin (guiden i Tegn)
            rows = [{**r, "preset": None} for r in rows]
        return {"symbols": rows, "layout": self._layout()}

    def count(self) -> int:
        return len(self.db.list_library_symbols())

    def export_from_drawing(self, actor: CurrentUser, drawing_id: str, element: str, box: Any, label: Any, hint: Any,
                            section: Any, keep_tags: bool, replace: bool, version: int | None = None) -> dict[str, Any]:
        label = clean_label(label)
        hint = clean_hint(hint)
        rows = self.db.list_library_symbols()
        # Et symbol kendes på sit NAVN (det kan være omdøbt, så typen ikke længere svarer til navnet)
        existing = next((r for r in rows if r["label"].casefold() == label.casefold()), None)
        if existing:
            sym_type = existing["type"]
        else:
            base, n = type_for(label), 2
            taken = {r["type"] for r in rows}
            sym_type = base
            while sym_type in taken:
                suffix = f"_{n}"
                sym_type, n = base[:40 - len(suffix)] + suffix, n + 1
        if existing and not replace:
            raise ServiceError(409, f"Symbolet '{existing['label']}' findes allerede (version {existing['version']}) — "
                                    "gem som ny version eller vælg et andet navn")
        if not existing and replace:
            raise ServiceError(404, f"Symbolet '{label}' findes ikke — gem det som nyt")
        if not existing and len(rows) >= MAX_SYMBOLS:
            raise ServiceError(400, f"Biblioteket har allerede {MAX_SYMBOLS} egne symboler")
        self.drawings._require(drawing_id)
        svg = self.drawings.svg(drawing_id, version)
        fragment, mapping, warnings = extract(svg, element, box)
        names = {e.attrib["id"]: e.attrib.get("data-hv-name", "") for e in _parse(svg).iter()
                 if isinstance(e.tag, str) and e.attrib.get("id")}
        preset, w2 = build_preset(self.symbols.configs(drawing_id), mapping, keep_tags, names)
        warnings += w2
        if preset is not None:
            preset["type"] = sym_type
        row = self.db.save_library_symbol(sym_type, label, hint, fragment, preset, actor.username, replace)
        if row is None:   # en anden nåede at oprette/slette det imens
            raise ServiceError(409, f"Symbolet '{label}' blev ændret samtidig af en anden — prøv igen")
        sec = section if isinstance(section, str) and section else OWN_SECTION
        self._place(sym_type, sec)
        log.info("Bibliotekssymbol %s gemt (version %d) af %s fra %s#%s — %d dele, %s", sym_type, row["version"],
                 actor.username, drawing_id, element, len(mapping) - 1,
                 "med opsætning" if preset else "uden opsætning")
        return {**self._public(row), "warnings": warnings, "parts": sorted(p for p in mapping.values() if p != "all")}

    def _place(self, sym_type: str, section: str) -> None:
        """Læg et (nyt) symbol sidst i en sektion — prøver igen, hvis opdelingen ændres samtidig."""
        for _ in range(5):
            lay = self._layout()
            ids = set(BUILTIN_SECTIONS) | {OWN_SECTION} | {s["id"] for s in lay["sections"]}
            sec = section if section in ids else OWN_SECTION
            cur = lay["items"].get(sym_type)
            if cur and cur[0] == sec:
                return
            last = max((v[1] for v in lay["items"].values() if v[0] == sec), default=-1)
            items = {**lay["items"], sym_type: [sec, last + 1]}
            if self.db.set_library_layout({"sections": lay["sections"], "order": lay["order"], "items": items}, lay["rev"]):
                return
        log.warning("Kunne ikke placere %s i sektionen %s (opdelingen ændres hele tiden)", sym_type, section)

    def update(self, actor: CurrentUser, sym_type: str, label: Any = None, hint: Any = None) -> dict[str, Any]:
        t = clean_type(sym_type)
        new_label = clean_label(label) if label is not None else None
        new_hint = clean_hint(hint) if hint is not None else None
        if new_label is not None:
            other = next((r for r in self.db.list_library_symbols()
                          if r["label"].casefold() == new_label.casefold() and r["type"] != t), None)
            if other:
                raise ServiceError(409, f"Et andet symbol hedder allerede '{other['label']}'")
        try:
            ok = self.db.rename_library_symbol(t, new_label, new_hint, actor.username)
        except Exception as exc:   # unikt indeks på navnet (samtidig omdøbning)
            if "UNIQUE" in str(exc):
                raise ServiceError(409, f"Et andet symbol hedder allerede '{new_label}'") from None
            raise
        if not ok:
            raise ServiceError(404, "Symbolet findes ikke i biblioteket")
        log.info("Bibliotekssymbol %s omdøbt/rettet af %s", t, actor.username)
        row = self.db.get_library_symbol(t)
        assert row is not None
        return self._public(row)

    def delete(self, actor: CurrentUser, sym_type: str) -> dict[str, Any]:
        t = clean_type(sym_type)
        row = self.db.get_library_symbol(t)
        if row is None or not self.db.delete_library_symbol(t):
            raise ServiceError(404, "Symbolet findes ikke i biblioteket")
        log.info("Bibliotekssymbol %s ('%s') slettet af %s — tegninger beholder deres kopi", t, row["label"],
                 actor.username)
        return {"type": t, "label": row["label"], "used_in": self.used_in(t)}

    def used_in(self, sym_type: str) -> list[str]:
        """Tegninger, hvis aktive version indeholder symbolet (til advarslen ved sletning)."""
        out: list[str] = []
        needle = f'data-hv-type="{sym_type}"'
        for d in self.db.list_drawings():
            try:
                if needle in self.drawings.svg(d["id"]):
                    out.append(d["id"])
            except ServiceError:
                continue
        return out

    def set_layout(self, actor: CurrentUser, raw: Any, rev: int | None) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ServiceError(400, "Opdelingen skal være et objekt")
        before = self._layout()
        keep = {s.get("id") for s in raw.get("sections", []) if isinstance(s, dict)} if isinstance(raw.get("sections"), list) else set()
        removed = {s["id"] for s in before["sections"]} - keep
        items = raw.get("items", {})
        if removed and isinstance(items, dict):
            # Symboler i en slettet sektion flyttes til "Egne symboler" (indbyggede tilbage til deres egen kategori)
            items = dict(items)
            for t, v in list(items.items()):
                if isinstance(v, list) and len(v) == 2 and v[0] in removed:
                    if isinstance(t, str) and t.startswith(PREFIX):
                        items[t] = [OWN_SECTION, v[1]]
                    else:
                        del items[t]
            raw = {**raw, "items": items}
        clean = clean_layout(raw, {r["type"] for r in self.db.list_library_symbols()})
        saved = self.db.set_library_layout(clean, rev)
        if saved is None:
            raise ServiceError(409, "Biblioteket er ændret af en anden imens — hent det igen og prøv igen")
        log.info("Bibliotekets opdeling gemt af %s (%d egne sektioner, %d placeringer)", actor.username,
                 len(clean["sections"]), len(clean["items"]))
        return self._layout()
