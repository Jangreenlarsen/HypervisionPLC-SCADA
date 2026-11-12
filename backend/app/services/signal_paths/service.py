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
import re
from typing import Any

from ...storage.db import Database
from ..auth import CurrentUser
from ..errors import ServiceError
from ..svg_sanitize import describe_element, describe_group, index_svg, subtree_map
from ..symbols import SymbolService, _TagInfo, config_tags, path_symbol_id, validate_config
from .materialize import TooManyAnims, base_anims, merge
from .runtime import branch_sets, path_tag, path_tags
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
        configured = set(self.symbols.configs(drawing_id))
        out = []
        for r in self.db.list_signal_paths(drawing_id):
            d = r["data"]
            missing = [e.get("element") for e in d.get("elements", []) if e.get("element") not in ids]
            out.append({"id": r["id"], "name": r["name"], "start": d.get("start"), "end": d.get("end"),
                        "ends": [d["end"], *(d.get("ends") or [])] if d.get("end") else [], "ui": d.get("ui", {}),
                        "elements": d.get("elements", []), "conditions": d.get("conditions", []), "style": d.get("style", {}),
                        "missing": missing, "updated_at": r["updated_at"], "updated_by": r["updated_by"],
                        # vejen som symbol (v5.4.0): id til symbol-guiden, om den har egen opsætning, og pseudo-tags som kilde
                        "symbol": path_symbol_id(r["id"]), "configured": path_symbol_id(r["id"]) in configured,
                        "sources": [{"tag": path_tag(drawing_id, r["id"], b), "branches": list(b)} for b in branch_sets(d)]
                        if valid_data(d) is None else []})
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
        # beregnede signaler (v5.10.0): symbolers position og logikblokke kan også være betingelser
        all_tags += [{"name": x["id"], "is_bool": x["is_bool"], "unit": "", "description": x["label"], "derived": True, "group": x["group"],
                      "labels": x["labels"]} for x in self.symbols.derived_signals(drawing_id)]
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
        derived = {x["id"]: x for x in self.symbols.derived_signals(drawing_id)}       # symbolers position og logikblokke (v5.10.0)
        conds = []
        for c in body.get("conditions") or []:
            if c["element"] not in on_branches:
                raise ServiceError(400, f"Betingelsen for '{c['element']}' hører ikke til et symbol på vejen")
            if c["src"] not in derived and (c["src"] not in tags or (visible is not None and c["src"] not in visible)):
                raise ServiceError(400, f"Tagget '{c['src']}' findes ikke")
            is_bool = derived[c["src"]]["is_bool"] if c["src"] in derived else _TagInfo(tags[c["src"]]).is_bool
            br = sorted({int(b) for b in c["branches"]}) if c.get("branches") else on_branches[c["element"]]
            if not br or br[0] < 0 or br[-1] >= nb:
                raise ServiceError(400, f"Betingelsen for '{c['element']}' hører til en gren, der ikke findes")
            if c.get("cmp") and c.get("value") is None:
                raise ServiceError(400, f"{c['src']}: vælg en grænseværdi")
            if not c.get("cmp") and not is_bool:
                raise ServiceError(400, f"{derived[c['src']]['label']} er et tal: vælg ≥, ≤ eller = og en værdi" if c["src"] in derived
                                   else f"{c['src']} er et tal-tag: vælg ≥, ≤ eller = og en grænseværdi")
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
        data = {**data, "materialized": True}          # vejens grundanimationer er skrevet ind i opsætningen (opgraderingen rører den ikke igen)
        dropped = 0
        if path_id is not None:
            # grundanimationerne skrives ind i vejens symbol-opsætning (v5.8.0) i samme transaktion som vejen
            cfg, old, dropped, err = self._config_with_base(drawing_id, path_id, name, data)
            if err:
                raise ServiceError(400, f"Vejens animationer kan ikke gemmes: {err}")
            sym = path_symbol_id(path_id)
            sid = self.db.write_signal_path(drawing_id, path_id, name, data, {sym: cfg}, actor.username, expect={sym: old})
            if sid == -1:
                raise ServiceError(409, "Vejens opsætning blev ændret imens (i symbol-guiden) — hent vejen igen, og gem på ny")
            if sid is None:
                raise ServiceError(409, "Signalvejen kunne ikke gemmes — navnet er taget, eller den er ændret imens")
        else:
            sid = self.db.write_signal_path(drawing_id, None, name, data, {}, actor.username)
            if sid is None or sid < 0:
                raise ServiceError(409, "Signalvejen kunne ikke gemmes — navnet er taget, eller den er ændret imens")
            try:      # en ny vej kender først nu sit id (og dermed sine pseudo-tags): grundanimationerne skrives nu — alt eller intet
                cfg, old, dropped, err = self._config_with_base(drawing_id, sid, name, data)
                if err:
                    raise ServiceError(400, f"Vejens animationer kan ikke gemmes: {err}")
                if self.db.write_signal_path(drawing_id, sid, name, data, {path_symbol_id(sid): cfg}, actor.username,
                                             expect={path_symbol_id(sid): old}) != sid:
                    raise ServiceError(409, "Vejens opsætning blev ændret imens — prøv igen")
            except BaseException:
                self.db.write_signal_path(drawing_id, sid, None, None, {}, actor.username)      # rul tilbage: ingen halv vej
                raise
        if dropped:
            log.warning("Signalvej '%s' (%s, id %s): %d egne animationer fjernet (gren eller del findes ikke mere)", name, drawing_id, sid, dropped)
        if self.symbols.on_change is not None:
            self.symbols.on_change(drawing_id, path_symbol_id(sid))
        log.info("Signalvej '%s' (%s, id %s) gemt af %s: %d elementer, %d grene, %d betingelser",
                 name, drawing_id, sid, actor.username, len(data["elements"]), 1 + len(data["ends"]), len(data["conditions"]))
        return {"id": sid, "name": name, "elements": len(data["elements"]), "conditions": len(data["conditions"]), "dropped": dropped}

    _FAIL = re.compile(r"^Animation (\d+):")

    def _config_with_base(self, drawing_id: str, path_id: int, name: str, data: dict[str, Any]
                          ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, int, str | None]:
        """Vejens symbol-opsætning med nye grundanimationer (`auto`) og alle andre animationer bevaret, valideret som et gem i guiden.
        Grundanimationer, som reglerne for et symbol ikke kan acceptere (fx løbelys på en del uden streger), kan ikke blokere for
        vejen — de udelades og logges. Egne animationer på en gren eller del, der ikke findes mere, fjernes (og tælles).
        → (ny opsætning, den gamle (til `expect`), antal egne animationer fjernet, fejl)"""
        sym = path_symbol_id(path_id)
        info = describe_group(self.drawings.svg(drawing_id), [e["element"] for e in data["elements"]], name)
        row = self.db.get_symbol_config(drawing_id, sym)
        old = row["config"] if row else None
        tags = set(path_tags(drawing_id, path_id, data))
        mine = [a for a in (old or {}).get("anims", []) if not a.get("auto")]
        mark = f"path:{drawing_id}:{path_id}:"
        keep = [a for a in mine if not (str(a.get("src", "")).startswith(mark) and a["src"] not in tags) and a.get("part") in info["parts"]]
        try:
            base = base_anims(drawing_id, path_id, data, set(info["parts"]))
        except TooManyAnims as exc:
            return None, old, 0, str(exc)
        others = {k: v for k, v in self.symbols.configs(drawing_id).items() if k != sym}
        pseudo = self.symbols.path_sources(drawing_id, exclude=path_id) | tags
        tag_rows = self.symbols._tags()
        # de gamle grundanimationer bevarer deres plads i rækkefølgen (merge erstatter dem), egne animationer, der fjernes, falder ud
        cfg = merge({**(old or {"op": "view"}), "anims": [a for a in (old or {}).get("anims", []) if a.get("auto") or a in keep]}, base)
        normalized, res = validate_config(cfg, info, tag_rows, False, sym, others, pseudo)
        if res.count:
            bad = {int(m.group(1)) - 1 for msg in res.steps.get("4", []) if (m := self._FAIL.match(msg))}
            auto_bad = {i for i in bad if 0 <= i < len(cfg["anims"]) and cfg["anims"][i].get("auto")}
            if auto_bad and res.count == len(bad) and bad == auto_bad:       # kun grundanimationer fejler: udelad dem i stedet for at blokere vejen
                for i in sorted(auto_bad):
                    a = cfg["anims"][i]
                    log.warning("Signalvej '%s' (%s): grundanimationen %s på '%s' kan ikke bruges og udelades (%s)", name, drawing_id, a["type"], a["part"],
                                next(m for m in res.steps.get("4", []) if m.startswith(f"Animation {i + 1}:")))
                cfg = {**cfg, "anims": [a for i, a in enumerate(cfg["anims"]) if i not in auto_bad]}
                normalized, res = validate_config(cfg, info, tag_rows, False, sym, others, pseudo)
            if res.count:
                return None, old, 0, res.first()
        return normalized, old, len(mine) - len(keep), None

    def materialize_existing(self, username: str = "system") -> dict[str, int]:
        """Opgradering til v5.8.0 (og efter en gendannelse af en backup fra før v5.8.0): vejens grundanimationer skrives ind i opsætningen for
        de veje, der ikke er markeret `materialized`. Rører ikke veje, der er det — heller ikke hvis brugeren har frigjort/slettet alle
        grundanimationerne. Vejen og opsætningen skrives i én transaktion (ikke hvis opsætningen er ændret imens)."""
        done = skipped = failed = 0
        for d in self.db.list_drawings():
            for r in self.db.list_signal_paths(d["id"]):
                if r["data"].get("materialized") or valid_data(r["data"]) is not None:
                    skipped += 1 if r["data"].get("materialized") else 0
                    failed += 0 if r["data"].get("materialized") else 1
                    continue
                sym = path_symbol_id(r["id"])
                try:
                    data = {**r["data"], "materialized": True}
                    cfg, old, _dropped, err = self._config_with_base(d["id"], r["id"], r["name"], data)
                    if err:
                        log.error("Signalvej '%s' (%s): grundanimationerne kan ikke gemmes: %s", r["name"], d["id"], err)
                        failed += 1
                        continue
                    if self.db.write_signal_path(d["id"], r["id"], r["name"], data, {sym: cfg}, username, expect={sym: old}) != r["id"]:
                        log.warning("Signalvej '%s' (%s): opsætningen blev ændret imens — prøves igen senere", r["name"], d["id"])
                        failed += 1
                        continue
                    if self.symbols.on_change is not None:
                        self.symbols.on_change(d["id"], sym)
                    done += 1
                except Exception:
                    log.exception("Signalvej '%s' (%s): grundanimationerne kunne ikke bygges", r["name"], d["id"])
                    failed += 1
        log.info("Signalvejenes grundanimationer: %d skrevet, %d var det allerede, %d fejlede", done, skipped, failed)
        return {"written": done, "had": skipped, "failed": failed}

    def delete(self, actor: CurrentUser, drawing_id: str, path_id: int) -> dict[str, Any]:
        self.drawings._require(drawing_id)
        old = self.db.get_signal_path(drawing_id, path_id)
        if old is None:
            raise ServiceError(404, "Signalvejen findes ikke (er den slettet imens?)")
        sym = path_symbol_id(path_id)       # vejens egen opsætning som symbol (v5.4.0) slettes med den
        mine = self.symbols.db.get_symbol_config(drawing_id, sym)
        if mine is not None and (users := self.symbols._logic_users(drawing_id, sym, {b["id"] for b in mine["config"].get("logic", [])})):
            raise ServiceError(409, f"Vejens logikblok {users[0][1]} bruges af '{users[0][0]}' — fjern henvisningen dér først")
        if users := self.symbols.path_users(drawing_id, path_id):
            raise ServiceError(409, f"Signalvejen bruges som kilde af '{users[0]}' — fjern henvisningen dér først")
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
