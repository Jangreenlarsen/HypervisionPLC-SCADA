"""Opgradering v5.1.0: den gamle symbolmodel fjernes — bibliotekssymbolerne konverteres til guidens opsætning (lag 3).

Den gamle model (bindinger direkte på symbolerne og automatiske bindinger fra `data-hv-auto`/`data-hv-part`, når symbolets
id/navn er et tag) findes ikke længere i den almindelige kode (services/drawings.py). Dette modul beregner den gamle models
bindinger én sidste gang, laver en opsætning med samme regler som det tidligere "Konvertér alle", gemmer den via guidens
`SymbolService.put` og fjerner derefter de gamle bindinger på symbolerne. Det, der ikke kan konverteres, står i en rapport.
Kører ved opstart (én gang) og efter gendannelse af en backup.

Konverteringsreglerne (fra før v5.1.0):

Teknik: docs/SYMBOLSTANDARD_IMPLEMENTERING.md afsnit 11. Reference: prototypens `convertDef` og
SYMBOLSTANDARD.md afsnit 7:

| I dag              | I den nye model                                                          |
| click:toggle       | 2 positioner (true_text/false_text), ét til/fra-signal, én kontaktplan   |
| click:select       | positionerne og deres værdier, ét register, én kontaktplan               |
| click:pulse        | betjeningsform Trykknap                                                  |
| click:write        | betjeningsform Setpunkt                                                  |
| fill/stroke        | farve pr. position (ellers efter tagget)                                 |
| text               | positionens navn (ellers tagværdien)                                     |
| move/rotate        | Flyt/Drej pr. position (ellers efter tagget)                             |
| visible/blink      | synlig/blink i de positioner hvor betingelsen er opfyldt                 |
| level/opacity/flow | uændret efter tagget                                                     |

"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from ..auth import CurrentUser
from ..bindings import DEFAULT_OFF, DEFAULT_ON, auto_binding, symbol_bindings
from ..errors import ServiceError
from ..svg_sanitize import describe_element, index_svg, subtree_ids, symbol_roots, symbol_specs

log = logging.getLogger("scada.migration")
DONE_KEY = "migration.v51_symbols"          # sat, når opgraderingen er kørt
REPORT_KEY = "report.v51_symbols"           # rapporten (JSON) — vises i Tegn › Meddelelser og på Status, til den ryddes
ACTOR = CurrentUser(username="opgradering v5.1.0", role="admin", must_change_password=False, token_hash="")

CLICKS = ("click:toggle", "click:select", "click:pulse", "click:write")


def _color_for(value: float, p: dict[str, Any], boolean: bool = False) -> str:
    """Som frontendens colorFor: tærskler for tal, ellers on/off (et til/fra-tag bruger altid on/off)."""
    th = p.get("thresholds") or []
    if th and not boolean:
        color = p.get("off") or DEFAULT_OFF
        for t in th:
            if value >= t["value"]:
                color = t["color"]
        return color
    return (p.get("on") or DEFAULT_ON) if value else (p.get("off") or DEFAULT_OFF)


def _num(p: dict[str, Any], key: str, default: float) -> float:
    """Parameterens tal — `None`/manglende giver standardværdien (som frontendens `??`)."""
    v = p.get(key)
    return float(default) if v is None else float(v)


def _frac(v: float, p: dict[str, Any]) -> float:
    lo, hi = _num(p, "min", 0), _num(p, "max", 100)
    return 0.0 if hi <= lo else min(1.0, max(0.0, (v - lo) / (hi - lo)))


def legacy_bindings(drawings: Any, drawing_id: str, element: str) -> list[dict[str, Any]]:
    """Den gamle models bindinger for et symbol og dets dele: eksplicitte bindinger og automatiske (id/navn = tag;
    betjeningssymboler efter deres egen beskrivelse) — som `_compute` regnede dem før v5.1.0."""
    svg = drawings.svg(drawing_id)
    subtree = subtree_ids(svg, {element})
    index = index_svg(svg)
    specs = symbol_specs(svg)
    tags = {t["name"]: t for t in drawings.db.list_tags()}
    out: list[dict[str, Any]] = []
    explicit: set[str] = set()
    for b in drawings.db.list_bindings(drawing_id):
        explicit.add(b["element"])
        if b["element"] in subtree and b["element"] in index:
            out.append({**b, "source": "explicit"})
    for el, (el_tag, label) in index.items():
        if el in explicit or el not in subtree:
            continue
        name = el if el in tags else label if label in tags else None
        if name is None:
            continue
        if el in specs:
            for pos, b in enumerate(symbol_bindings(specs[el], el, {"name": name, "writable": bool(tags[name]["writable"])})):
                if (b["element"] == el or b["element"] not in explicit) and b["element"] in subtree:
                    out.append({**b, "position": pos, "source": "auto"})
            continue
        auto = auto_binding(el_tag, {"name": name, "is_bool": drawings._is_bool(tags[name])})
        if auto is not None:
            out.append({"element": el, "position": 0, **auto, "source": "auto"})
    return out


def suggest(drawings: Any, drawing_id: str, element: str) -> dict[str, Any]:
    """→ {"config": forslag, "notes": [forklaringer], "convertible": bool}. Kaster ikke for ukendte animationer —
    de nævnes i notes."""
    svg = drawings.svg(drawing_id)
    info = describe_element(svg, element)
    if info is None:
        return {"config": None, "notes": [f"Elementet '{element}' findes ikke i den aktive version"], "blockers": [],
                "has_bindings": False, "convertible": False}
    legacy = legacy_bindings(drawings, drawing_id, element)
    notes: list[str] = []
    blockers: list[str] = []   # det der ville gå tabt — så skal symbolet sættes op manuelt i guiden
    click = next((b for b in legacy if b["anim"] in CLICKS and b["element"] == element), None)
    for b in legacy:
        if b["anim"] in CLICKS and b is not click:
            blockers.append(f"Klik-handlingen {b['anim']} på {b['element']} kan ikke overføres (symbolet betjenes kun fra roden) "
                            f"— sæt betjeningen op i guiden.")
        elif b["anim"] == "click:goto" and b["element"] != element:
            blockers.append(f"'Gå til tegning' på delen {b['element']} kan ikke overføres — sæt den på symbolet i stedet.")
    cfg: dict[str, Any] = {"op": "view", "positions": [], "signals": [], "planes": [], "anims": [], "confirm": True,
                           "display": "remote", "validate_s": 5, "alarm": "medium", "lock": {"positions": [], "leave": False}}
    values: list[float] = []   # positionernes værdier (til animationer pr. position)
    text_spec = next((b["params"] for b in legacy if b["anim"] == "text" and click and b["tag"] == click["tag"]), {})
    if click is not None:
        tag, p = click["tag"], click["params"]
        if click["anim"] == "click:toggle":
            cfg.update(op="positions", confirm=bool(p.get("confirm", True)),
                       positions=[{"label": text_spec.get("false_text") or "Fra"}, {"label": text_spec.get("true_text") or "Til"}],
                       signals=[{"id": "S1", "tag": tag, "fb": tag}], planes=[{"signal": "S1", "values": [0, 1]}])
            values = [0, 1]
            notes.append("Til/fra → 2 positioner med ét signal og én kontaktplan.")
        elif click["anim"] == "click:select":
            pos = p.get("positions") or []
            cfg.update(op="positions", confirm=bool(p.get("confirm", True)),
                       positions=[{"label": x["label"]} for x in pos], signals=[{"id": "S1", "tag": tag, "fb": tag}],
                       planes=[{"signal": "S1", "values": [x["value"] for x in pos]}])
            values = [float(x["value"]) for x in pos]
            notes.append(f"Omskifter → {len(pos)} positioner, ét register med værdierne "
                         f"{'/'.join(f'{v:g}' for v in values)}.")
        elif click["anim"] == "click:pulse":
            cfg.update(op="pulse", pulse_ms=int(_num(p, "ms", 500)), confirm=bool(p.get("confirm", False)),
                       signals=[{"id": "S1", "tag": tag}])
            notes.append("Puls → betjeningsform Trykknap.")
        else:
            row = drawings.db.get_tag(tag)
            cfg.update(op="entry", signals=[{"id": "S1", "tag": tag}],
                       confirm=bool(row["confirm_write"]) if row is not None else True)
            notes.append("Setpunkt → betjeningsform Setpunkt.")
    pos_mode = cfg["op"] == "positions"
    n = len(cfg["positions"])
    cfg["lock"]["positions"] = [False] * n
    for b in legacy:
        if b["anim"] in CLICKS or b["anim"] == "click:goto":
            continue   # (klik på dele er med i blockers; "gå til" på roden bliver stående som binding)
        part = "all" if b["element"] == element else b["element"]
        p, anim = dict(b["params"]), b["anim"]
        own = click is not None and b["tag"] == click["tag"] and pos_mode
        if not own:
            cfg["anims"].append({"part": part, "type": anim, "src": b["tag"], "params": p})
            continue
        if anim in ("fill", "stroke"):
            toggle = click["anim"] == "click:toggle"
            cfg["anims"].append({"part": part, "type": anim, "src": "@pos",
                                 "params": {"colors": [_color_for(v, p, toggle) for v in values]}})
        elif anim == "text":
            cfg["anims"].append({"part": part, "type": "text", "src": "@pos", "params": {}})
            if p.get("prefix") or p.get("suffix"):
                notes.append(f"Teksten på {b['element']} viser nu positionens navn — for-/eftertekst "
                             f"('{p.get('prefix', '')}'/'{p.get('suffix', '')}') kommer ikke med.")
        elif anim == "move":
            cfg["anims"].append({"part": part, "type": "move", "src": "@pos", "params": {
                "dxs": [round(_num(p, "dx", 100) * _frac(v, p), 2) for v in values],
                "dys": [round(_num(p, "dy", 0) * _frac(v, p), 2) for v in values]}})
        elif anim == "rotate":
            a0, a1 = _num(p, "angle_min", 0), _num(p, "angle_max", 360)
            cfg["anims"].append({"part": part, "type": "rotate", "src": "@pos",
                                 "params": {"angles": [round(a0 + (a1 - a0) * _frac(v, p), 2) for v in values]}})
        elif anim in ("visible", "blink"):
            on = [bool(v) != bool(p.get("invert")) for v in values]
            cfg["anims"].append({"part": part, "type": anim, "src": "@pos", "params": {"set": on}})
        else:
            cfg["anims"].append({"part": part, "type": anim, "src": b["tag"], "params": p})
    if not legacy:
        notes.append("Symbolet har ingen bindinger i dag — vælg betjening og animationer i guiden.")
    elif not cfg["anims"] and cfg["op"] == "view":
        notes.append("Ingen animationer kunne overføres.")
    others = [b for b in legacy if b["anim"] != "click:goto"]
    return {"config": cfg, "notes": blockers + notes, "blockers": blockers, "has_bindings": bool(others),
            "convertible": bool(others) and not blockers and (cfg["op"] != "view" or bool(cfg["anims"])),
            "symbol": {"type": info["type"], "name": info["name"]}}


# ------------------------------------------------------------------ Konvertér alle (fase 8)

STATUS_TXT = {"ready": "Kan konverteres", "converted": "Konverteret", "manual": "Kræver manuel handling",
              "configured": "Allerede sat op", "none": "Ingen bindinger"}


def convert_all(symbols: Any, actor: Any, drawing_ids: list[str], apply: bool) -> dict[str, Any]:
    """Konvertér alle bibliotekssymboler med gamle bindinger. `apply=False` er en tør-kørsel. Ved `apply=True` gemmes kun
    forslag uden fejl — resten står som "kræver manuel handling" med grunden."""
    from ..symbols import validate_config   # (cirkulær import: symbols → drawings → symbols)

    drawings = symbols.drawings
    tags = symbols._tags()
    report: list[dict[str, Any]] = []
    for did in drawing_ids:
        try:
            svg = drawings.svg(did)
        except ServiceError as e:
            report.append({"drawing": did, "element": "", "name": None, "type": "", "status": "manual",
                           "reasons": [e.message], "notes": []})
            continue
        configured = symbols.configs(did)
        for el in symbol_roots(svg):
            info = describe_element(svg, el)
            row: dict[str, Any] = {"drawing": did, "element": el, "name": info and info["name"],
                                   "type": info["type"] if info else "", "reasons": [], "notes": []}
            report.append(row)
            if el in configured:
                row["status"] = "configured"
                continue
            if info is None:   # (kan ikke ske — elementet kommer fra samme tegning)
                row.update(status="manual", reasons=["Elementet findes ikke"])
                continue
            s = suggest(drawings, did, el)
            row["notes"] = [n for n in s["notes"] if n not in s["blockers"]]
            if not s["has_bindings"]:
                row["status"] = "none"
                continue
            if not s["convertible"]:
                row.update(status="manual", reasons=s["blockers"] or ["Ingen animationer kunne overføres"])
                continue
            _, res = validate_config(s["config"], info, tags, has_pin=False)
            if res.count:
                row.update(status="manual", reasons=[f"Trin {k}: {m}" for k, v in res.steps.items() for m in v])
                continue
            if not apply:
                row["status"] = "ready"
                continue
            try:
                symbols.put(actor, did, el, s["config"])
                row["status"] = "converted"
            except ServiceError as e:   # (fx tag slettet imellem) — kun dette symbol, resten fortsætter
                row.update(status="manual", reasons=[e.message])
    counts = {k: sum(r["status"] == k for r in report) for k in STATUS_TXT}
    return {"apply": apply, "counts": counts, "symbols": report}


# ------------------------------------------------------------------ selve opgraderingen

def _drop_symbol_bindings(drawings: Any, drawing_id: str) -> dict[str, list[dict[str, Any]]]:
    """Slet de gamle bindinger på bibliotekssymbolernes rod og dele. "Gå til tegning" på roden bliver stående (den gælder
    stadig). → {element: de slettede bindinger} (gemmes i rapporten, så intet går tabt uden spor)."""
    svg = drawings.svg(drawing_id)
    roots = set(symbol_roots(svg))
    if not roots:
        return {}
    parts = subtree_ids(svg, roots)
    db = drawings.db
    removed: dict[str, list[dict[str, Any]]] = {}
    rows = db.list_bindings(drawing_id)
    for el in sorted({b["element"] for b in rows if b["element"] in parts}):
        mine = [{"tag": b["tag"], "anim": b["anim"], "params": b["params"]} for b in rows if b["element"] == el]
        keep = [b for b in mine if el in roots and b["anim"] == "click:goto"]
        if len(keep) != len(mine):
            db.set_element_bindings(drawing_id, el, keep)
            removed[el] = [b for b in mine if b not in keep]
    return removed


def migrate(db: Any, symbols: Any, backups: Any | None = None, force: bool = False) -> dict[str, Any] | None:
    """Kør opgraderingen én gang (eller igen med `force`, fx efter gendannelse af en backup). Tager en backup først, hvis der er
    noget at ændre. → rapporten, eller None hvis der intet var at gøre."""
    if not force and db.get_meta(DONE_KEY):
        return None
    drawings = symbols.drawings
    ids = [d["id"] for d in db.list_drawings()]
    try:
        dry = convert_all(symbols, ACTOR, ids, apply=False)
    except Exception:
        log.exception("Opgradering v5.1.0: tør-kørslen fejlede — prøves igen ved næste opstart")
        return None
    pending = [r for r in dry["symbols"] if r["status"] in ("ready", "manual")]
    leftovers = 0
    for did in ids:
        try:
            svg = drawings.svg(did)
        except ServiceError:
            continue
        roots = set(symbol_roots(svg))
        parts = subtree_ids(svg, roots) if roots else set()
        leftovers += sum(1 for b in db.list_bindings(did) if b["element"] in parts and not (b["element"] in roots and b["anim"] == "click:goto"))
    if not pending and not leftovers:
        db.set_meta(DONE_KEY, str(time.time()))
        if force:
            db.set_meta(REPORT_KEY, None)     # (fx efter gendannelse: en rapport fra før gælder ikke længere)
        return None
    if backups is not None:
        try:
            name = backups.save_to_server("pre-update", ACTOR.username)
            log.warning("Opgradering v5.1.0: backup taget før den gamle symbolmodel fjernes (%s)", name)
        except Exception:
            log.exception("Opgradering v5.1.0: backuppen kunne ikke tages — opgraderingen udskydes")
            return None
    result = convert_all(symbols, ACTOR, ids, apply=True)
    removed: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for did in ids:
        try:
            removed[did] = _drop_symbol_bindings(drawings, did)
        except ServiceError:
            continue

    def gone(did: str, root: str) -> list[dict[str, Any]]:
        """De slettede bindinger på symbolet og dets dele (med elementet), så en manuel opsætning kan genskabe dem."""
        try:
            sub = subtree_ids(drawings.svg(did), {root})
        except ServiceError:
            sub = {root}
        return [{"element": el, **b} for el, items in removed.get(did, {}).items() if el in sub for b in items]

    report = {"at": time.time(), "counts": result["counts"],
              "removed_bindings": sum(len(v) for d in removed.values() for v in d.values()),
              "manual": [{**{k: r.get(k) for k in ("drawing", "element", "name", "type", "reasons")},
                          "removed": gone(r["drawing"], r["element"])}
                         for r in result["symbols"] if r["status"] == "manual"],
              "converted": [{**{k: r.get(k) for k in ("drawing", "element", "name", "type")}, "notes": r.get("notes") or []}
                            for r in result["symbols"] if r["status"] == "converted"]}
    db.set_meta(REPORT_KEY, json.dumps(report, ensure_ascii=False))
    db.set_meta(DONE_KEY, str(time.time()))
    log.warning("Opgradering v5.1.0: den gamle symbolmodel er fjernet — %d symboler konverteret, %d kræver manuel opsætning, "
                "%d gamle bindinger slettet", result["counts"].get("converted", 0), len(report["manual"]), report["removed_bindings"])
    return report


def pending(db: Any) -> bool:
    """Er opgraderingen endnu ikke kørt (fx fordi backuppen ikke kunne tages)?"""
    return not db.get_meta(DONE_KEY)


def report(db: Any) -> dict[str, Any] | None:
    raw = db.get_meta(REPORT_KEY)
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def clear_report(db: Any) -> None:
    db.set_meta(REPORT_KEY, "")
