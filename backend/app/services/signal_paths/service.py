"""Signalveje i Tegn (v4.2.0; v4.13.0: grene; v5.0.0: signalvejen er sit eget objekt).

En signalvej er en navngiven vej gennem tegningen: fra et startsymbol til et eller flere slutsymboler (grene) gennem rør, T-stykker,
bøjninger, ventiler og pumper. Vejen findes i Tegn ud fra geometrien (frontend/src/lib/signalpath/) — her gemmes den som ÉT
objekt (`validate.py` beskriver formen):

- **Intet skrives i symbolernes opsætning** (v5.0.0). Betingelserne regnes af serveren hvert tick (`runtime.py`), og vejens
  animationer lægges på som almindelige bindinger, når Overview henter tegningen (services/drawings.py). Ret og slet rører derfor
  kun vejen selv.
- Ligger en animation af samme slags allerede på delen (brugerens egen eller fra en anden vej), gælder den eksisterende
  prioritetsregel i Overview (aktiv/passiv, den øverste aktive vinder) — intet overskrives.

Kun tekniker og op (api/signal_paths.py). Ændrer aldrig SVG'en eller PLC'en.
"""

from __future__ import annotations

import logging
from typing import Any

from ...storage.db import Database
from ..auth import CurrentUser
from ..errors import ServiceError
from ..svg_sanitize import describe_element, index_svg, subtree_map
from ..symbols import SymbolService, _TagInfo, config_tags
from .validate import MAX_CONDITIONS, MAX_ELEMENTS, MAX_ENDS, clean_params, valid_data

log = logging.getLogger("scada.signalpath")


class SignalPathService:
    def __init__(self, db: Database, symbols: SymbolService):
        self.db = db
        self.symbols = symbols
        self.drawings = symbols.drawings

    # ------------------------------------------------------------------ læsning
    def list(self, drawing_id: str) -> list[dict[str, Any]]:
        self.drawings._require(drawing_id)
        ids = set(index_svg(self.drawings.svg(drawing_id)))
        out = []
        for r in self.db.list_signal_paths(drawing_id):
            d = r["data"]
            missing = [e.get("element") for e in d.get("elements", []) if e.get("element") not in ids]
            out.append({"id": r["id"], "name": r["name"], "start": d.get("start"), "end": d.get("end"),
                        "ends": [d["end"], *(d.get("ends") or [])] if d.get("end") else [], "ui": d.get("ui", {}),
                        "elements": d.get("elements", []), "conditions": d.get("conditions", []), "style": d.get("style", {}),
                        "missing": missing, "updated_at": r["updated_at"], "updated_by": r["updated_by"]})
        return out

    def info(self, drawing_id: str, elements: list[str], visible: set[str] | None = None) -> dict[str, Any]:
        """Til guiden: navn, type, symbolets egne tags (forslag til betingelsen) og dets navngivne dele.
        `visible`: de tags brugeren må se (None = alle)."""
        self.drawings._require(drawing_id)
        svg = self.drawings.svg(drawing_id)
        configs = self.symbols.configs(drawing_id)
        tags = {t["name"]: t for t in self.db.list_tags() if visible is None or t["name"] in visible}
        out = []
        for el in elements[:MAX_ELEMENTS]:
            d = describe_element(svg, el)
            if d is None:
                out.append({"element": el, "missing": True})
                continue
            cfg = configs.get(el) or {}
            own = [{"name": t, "is_bool": _TagInfo(tags[t]).is_bool, "unit": tags[t].get("unit") or "",
                    "description": tags[t].get("description") or ""} for t in config_tags(cfg) if t in tags]
            parts = [{"id": pid, "pid": p.get("pid") or "", "line": bool(p.get("line")), "text": p.get("text") or ""}
                     for pid, p in list((d.get("parts") or {}).items())[:60]]
            out.append({"element": el, "name": d.get("name") or "", "type": d["type"], "configured": bool(cfg),
                        "tags": own, "parts": parts})
        all_tags = [{"name": t["name"], "is_bool": _TagInfo(t).is_bool, "unit": t.get("unit") or "",
                     "description": t.get("description") or ""} for t in tags.values()]
        return {"elements": out, "max_conditions": MAX_CONDITIONS, "tags": all_tags}

    # ------------------------------------------------------------------ gem
    def _normalize(self, drawing_id: str, body: dict[str, Any], visible: set[str] | None = None) -> tuple[str, dict[str, Any]]:
        """Kontrollér body mod den gemte tegning og taglisten, og byg vejens `data`. → (navn, data)"""
        name = " ".join(str(body["name"]).split())[:60]
        if not name:
            raise ServiceError(400, "Giv signalvejen et navn")
        svg = self.drawings.svg(drawing_id)
        ids = index_svg(svg)
        ends = list(dict.fromkeys([body["end"], *(body.get("ends") or [])]))
        if len(ends) > MAX_ENDS:
            raise ServiceError(400, f"Højst {MAX_ENDS} slutpunkter pr. signalvej")
        if body["start"] in ends:
            raise ServiceError(400, "Start og slut må ikke være det samme symbol")
        nb = len(ends)
        elements = body["elements"]
        if len(elements) > MAX_ELEMENTS:
            raise ServiceError(400, f"Signalvejen er for lang (højst {MAX_ELEMENTS} elementer)")
        missing = [e["element"] for e in elements if e["element"] not in ids] + [x for x in (body["start"], *ends) if x not in ids]
        if missing:
            raise ServiceError(400, f"Elementet '{missing[0]}' findes ikke i den gemte tegning — gem tegningen og find vejen igen")
        subtrees = subtree_map(svg, {e["element"] for e in elements})
        out_els: list[dict[str, Any]] = []
        for e in elements:
            el = e["element"]
            br = sorted({int(b) for b in (e.get("branches") or [0])})
            if br[0] < 0 or br[-1] >= nb:
                raise ServiceError(400, f"'{el}' hører til en gren, der ikke findes")
            parts = subtrees.get(el, set())
            ok_part = lambda p, el=el, parts=parts: p == "all" or p == el or p in parts   # noqa: E731
            flows = [{"part": f["part"], "reverse": bool(f.get("reverse"))} for f in e.get("flows") or []]
            anims = []
            for a in e.get("anims") or []:
                params = clean_params(a["type"], a.get("params"))
                if params is None:
                    raise ServiceError(400, f"'{el}': {a['type']} mangler en gyldig farve/hastighed")
                anims.append({"part": a["part"], "type": a["type"], "params": params, "when": bool(a.get("when", True))})
            bad = [x["part"] for x in flows + anims if not ok_part(x["part"])]
            if bad:
                raise ServiceError(400, f"'{el}' har ikke delen '{bad[0]}' — gem tegningen og find vejen igen")
            out_els.append({"element": el, "branches": br, "flows": flows, "anims": anims})
        if not any(e["flows"] or e["anims"] for e in out_els):
            raise ServiceError(400, "Vælg mindst én animation, og sørg for, at der er dele på vejen at sætte den på "
                                    "(rør, bøjninger og T-stykker kan få løbelys)")
        # Betingelserne: start gælder alle grene, et slutpunkt kun sin egen; et element på vejen de grene, der går igennem det
        on_branches = {e["element"]: e["branches"] for e in out_els}
        on_branches.setdefault(body["start"], list(range(nb)))
        for k, end_id in enumerate(ends):
            on_branches.setdefault(end_id, [k])
        tags = {t["name"]: t for t in self.db.list_tags()}
        conds = []
        for c in body.get("conditions") or []:
            if c["element"] not in on_branches:
                raise ServiceError(400, f"Betingelsen for '{c['element']}' hører ikke til et symbol på vejen")
            if c["src"] not in tags or (visible is not None and c["src"] not in visible):
                raise ServiceError(400, f"Tagget '{c['src']}' findes ikke")
            br = sorted({int(b) for b in c["branches"]}) if c.get("branches") else on_branches[c["element"]]
            if not br or br[0] < 0 or br[-1] >= nb:
                raise ServiceError(400, f"Betingelsen for '{c['element']}' hører til en gren, der ikke findes")
            if c.get("cmp") and c.get("value") is None:
                raise ServiceError(400, f"{c['src']}: vælg en grænseværdi")
            if not c.get("cmp") and not _TagInfo(tags[c["src"]]).is_bool:
                raise ServiceError(400, f"{c['src']} er et tal-tag: vælg ≥, ≤ eller = og en grænseværdi")
            conds.append({"element": c["element"], "src": c["src"], "neg": bool(c.get("neg")), "cmp": c.get("cmp") or "",
                          "value": c.get("value"), "branches": br})
        if len(conds) > MAX_CONDITIONS:
            raise ServiceError(400, f"Højst {MAX_CONDITIONS} betingelser pr. signalvej")
        style = body.get("style") or {}
        data = {"start": body["start"], "end": ends[0], "ends": ends[1:], "elements": out_els, "conditions": conds,
                "style": {"light": style.get("light", "#8fc8ea"), "speed": style.get("speed", 40), "dash": style.get("dash", 12)},
                "ui": body.get("ui") or {}}
        if problem := valid_data(data):        # samme kontrol som en backup: det gemte objekt er altid gyldigt
            raise ServiceError(400, f"Signalvejen kan ikke gemmes: {problem}")
        return name, data

    def save(self, actor: CurrentUser, drawing_id: str, body: dict[str, Any], path_id: int | None = None,
             visible: set[str] | None = None) -> dict[str, Any]:
        self.drawings._require(drawing_id)
        if path_id is not None and self.db.get_signal_path(drawing_id, path_id) is None:
            raise ServiceError(404, "Signalvejen findes ikke (er den slettet imens?)")
        name, data = self._normalize(drawing_id, body, visible)
        if any(r["name"].lower() == name.lower() and r["id"] != path_id for r in self.db.list_signal_paths(drawing_id)):
            raise ServiceError(409, f"Der findes allerede en signalvej med navnet '{name}'")
        sid = self.db.write_signal_path(drawing_id, path_id, name, data, {}, actor.username)
        if sid is None or sid < 0:
            raise ServiceError(409, "Signalvejen kunne ikke gemmes — navnet er taget, eller den er ændret imens")
        log.info("Signalvej '%s' (%s, id %s) gemt af %s: %d elementer, %d grene, %d betingelser",
                 name, drawing_id, sid, actor.username, len(data["elements"]), 1 + len(data["ends"]), len(data["conditions"]))
        return {"id": sid, "name": name, "elements": len(data["elements"]), "conditions": len(data["conditions"])}

    def delete(self, actor: CurrentUser, drawing_id: str, path_id: int) -> dict[str, Any]:
        self.drawings._require(drawing_id)
        old = self.db.get_signal_path(drawing_id, path_id)
        if old is None:
            raise ServiceError(404, "Signalvejen findes ikke (er den slettet imens?)")
        if self.db.write_signal_path(drawing_id, path_id, None, None, {}, actor.username) is None:
            raise ServiceError(404, "Signalvejen findes ikke (er den slettet imens?)")
        log.info("Signalvej '%s' (%s, id %s) slettet af %s", old["name"], drawing_id, path_id, actor.username)
        return {"deleted": path_id, "name": old["name"]}
