"""Signalveje i Tegn (v4.2.0; v4.13.0: grene; v5.0.0: signalvejen er sit eget objekt; v6.0.0: kun en definition).

En signalvej er en navngiven vej gennem tegningen: fra et startsymbol til et eller flere slutpunkter gennem rør, T-stykker, bøjninger,
ventiler og pumper. Vejen findes i Tegn ud fra geometrien (frontend/src/lib/signalpath/). Her gemmes den som ÉT objekt, der **kun
definerer, hvad vejen består af** (`validate.py` beskriver formen): elementerne, hvilke grene de ligger på, og flowretningen (`flows`).

Hvornår vejen er aktiv, og hvordan den ser ud, er ikke en del af vejen (v6.0.0): vejen bruges som et **almindeligt symbol** (`sv~<id>`,
se `symbols.py`) i symbol-guidens 6 trin — tilbagemelding fra et PLC-tag eller et andet symbols position, kontaktflade (trin 3) og
animationer på vejens dele (trin 4). Intet skrives i symbolernes egen opsætning, og vejen ændrer aldrig SVG'en eller PLC'en.

Kun tekniker og op (api/signal_paths.py).
"""

from __future__ import annotations

import logging
from typing import Any

from ...storage.db import Database
from ..auth import CurrentUser
from ..errors import ServiceError
from ..svg_sanitize import describe_element, index_svg, subtree_map
from ..symbols import SymbolService, path_symbol_id
from .validate import MAX_ELEMENTS, MAX_ENDS, valid_data

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
        configured = set(self.symbols.configs(drawing_id))
        out = []
        for r in self.db.list_signal_paths(drawing_id):
            d = r["data"]
            missing = [e.get("element") for e in d.get("elements", []) if e.get("element") not in ids]
            out.append({"id": r["id"], "name": r["name"], "start": d.get("start"), "end": d.get("end"),
                        "ends": [d["end"], *(d.get("ends") or [])] if d.get("end") else [], "ui": d.get("ui", {}),
                        "elements": d.get("elements", []), "missing": missing, "updated_at": r["updated_at"], "updated_by": r["updated_by"],
                        # vejen som symbol: id til symbol-guiden og om den har en opsætning
                        "symbol": path_symbol_id(r["id"]), "configured": path_symbol_id(r["id"]) in configured})
        return out

    def info(self, drawing_id: str, elements: list[str]) -> dict[str, Any]:
        """Til guiden: navn, type og navngivne dele for elementerne på vejen."""
        self.drawings._require(drawing_id)
        svg = self.drawings.svg(drawing_id)
        configs = self.symbols.configs(drawing_id)
        out = []
        for el in elements[:MAX_ELEMENTS]:
            d = describe_element(svg, el)
            if d is None:
                out.append({"element": el, "missing": True})
                continue
            parts = [{"id": pid, "pid": p.get("pid") or "", "line": bool(p.get("line")), "text": p.get("text") or ""}
                     for pid, p in list((d.get("parts") or {}).items())[:60]]
            out.append({"element": el, "name": d.get("name") or "", "type": d["type"], "configured": bool(configs.get(el)), "parts": parts})
        return {"elements": out}

    # ------------------------------------------------------------------ gem
    def _normalize(self, drawing_id: str, body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Kontrollér definitionen mod den gemte tegning. → (navn, data). Betingelser og udseende, som en ældre klient måtte sende, ignoreres."""
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
        if not elements:
            raise ServiceError(400, "Vejen skal bestå af mindst ét element")
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
            flows = [{"part": f["part"], "reverse": bool(f.get("reverse"))} for f in e.get("flows") or []]
            bad = [f["part"] for f in flows if not (f["part"] == "all" or f["part"] == el or f["part"] in parts)]
            if bad:
                raise ServiceError(400, f"'{el}' har ikke delen '{bad[0]}' — gem tegningen og find vejen igen")
            out_els.append({"element": el, "branches": br, "flows": flows})
        data = {"start": body["start"], "end": ends[0], "ends": ends[1:], "elements": out_els, "ui": body.get("ui") or {}}
        if problem := valid_data(data):        # samme kontrol som en backup: det gemte objekt er altid gyldigt
            raise ServiceError(400, f"Signalvejen kan ikke gemmes: {problem}")
        return name, data

    def save(self, actor: CurrentUser, drawing_id: str, body: dict[str, Any], path_id: int | None = None) -> dict[str, Any]:
        self.drawings._require(drawing_id)
        if path_id is not None and self.db.get_signal_path(drawing_id, path_id) is None:
            raise ServiceError(404, "Signalvejen findes ikke (er den slettet imens?)")
        name, data = self._normalize(drawing_id, body)
        if any(r["name"].lower() == name.lower() and r["id"] != path_id for r in self.db.list_signal_paths(drawing_id)):
            raise ServiceError(409, f"Der findes allerede en signalvej med navnet '{name}'")
        sid = self.db.write_signal_path(drawing_id, path_id, name, data, {}, actor.username)
        if sid is None or sid < 0:
            raise ServiceError(409, "Signalvejen kunne ikke gemmes — navnet er taget, eller den er ændret imens")
        if self.symbols.on_change is not None:
            self.symbols.on_change(drawing_id, path_symbol_id(sid))
        log.info("Signalvej '%s' (%s, id %s) gemt af %s: %d elementer, %d grene", name, drawing_id, sid, actor.username,
                 len(data["elements"]), 1 + len(data["ends"]))
        return {"id": sid, "name": name, "elements": len(data["elements"])}

    def delete(self, actor: CurrentUser, drawing_id: str, path_id: int) -> dict[str, Any]:
        self.drawings._require(drawing_id)
        old = self.db.get_signal_path(drawing_id, path_id)
        if old is None:
            raise ServiceError(404, "Signalvejen findes ikke (er den slettet imens?)")
        sym = path_symbol_id(path_id)       # vejens opsætning som symbol slettes med den
        mine = self.symbols.db.get_symbol_config(drawing_id, sym)
        if mine is not None:
            if users := self.symbols._logic_users(drawing_id, sym, {b["id"] for b in mine["config"].get("logic", [])}):
                raise ServiceError(409, f"Vejens logikblok {users[0][1]} bruges af '{users[0][0]}' — fjern henvisningen dér først")
            if users := self.symbols.signal_users(drawing_id, sym):
                raise ServiceError(409, f"Vejens position bruges af '{users[0]}' — fjern henvisningen dér først")
        done = self.db.write_signal_path(drawing_id, path_id, None, None, {sym: None}, actor.username,
                                         expect={sym: mine["config"] if mine else None})      # kun hvis opsætningen er uændret
        if done == -1:
            raise ServiceError(409, "Vejens opsætning blev ændret imens — prøv igen")
        if done is None:
            raise ServiceError(404, "Signalvejen findes ikke (er den slettet imens?)")
        if mine is not None and self.symbols.on_change is not None:
            self.symbols.on_change(drawing_id, sym)
        log.info("Signalvej '%s' (%s, id %s) slettet af %s", old["name"], drawing_id, path_id, actor.username)
        return {"deleted": path_id, "name": old["name"]}
