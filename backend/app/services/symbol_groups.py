"""Navngivne symbolgrupper (v0.130.0): et udvalg af elementer på en tegning, gemt under et navn. Samme element må være med i
flere grupper. Gruppen ændrer ikke tegningen eller elementernes opsætning — den samler dem til at markere og vælge."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from ..storage.db import Database
from .errors import ServiceError
from .symbols import MAX_ANIMS, validate_config

log = logging.getLogger("scada.symbol_groups")

GROUP_KINDS = ("function", "selection")   # funktion (fx "Fyr uden akku-tank") / frit udvalg
MAX_GROUP_NAME = 60
MAX_GROUP_MEMBERS = 500
MAX_GROUPS = 200


def clean_members(members: list[str]) -> list[str]:
    """Rækkefølgen bevares; dubletter fjernes."""
    out = list(dict.fromkeys(m.strip() for m in members if m and m.strip()))
    if any(len(m) > 120 for m in out):
        raise ServiceError(400, "Et elements id er for langt (højst 120 tegn)")
    if len(out) > MAX_GROUP_MEMBERS:
        raise ServiceError(400, f"En gruppe kan højst have {MAX_GROUP_MEMBERS} elementer")
    return out


class SymbolGroupService:
    def __init__(self, db: Database, symbols: Any = None):
        self.db = db
        self.symbols = symbols   # SymbolService — bruges til at validere gruppe-animationer som symbolets egne

    def list(self, drawing_id: str) -> list[dict[str, Any]]:
        return self.db.list_symbol_groups(drawing_id)

    def _check_name(self, name: str, kind: str) -> str:
        name = name.strip()
        if not name:
            raise ServiceError(400, "Gruppen skal have et navn")
        if len(name) > MAX_GROUP_NAME:
            raise ServiceError(400, f"Gruppens navn må højst være {MAX_GROUP_NAME} tegn")
        if kind not in GROUP_KINDS:
            raise ServiceError(400, "Ukendt art — vælg 'function' eller 'selection'")
        return name

    def save(self, user: str, drawing_id: str, group_id: int | None, name: str, kind: str,
             members: list[str] | None) -> dict[str, Any]:
        name = self._check_name(name, kind)
        clean = clean_members(members) if members is not None else None
        existing = self.db.list_symbol_groups(drawing_id)
        if group_id is None and len(existing) >= MAX_GROUPS:
            raise ServiceError(400, f"Der kan højst være {MAX_GROUPS} grupper pr. tegning")
        if any(g["id"] != group_id and g["name"].casefold() == name.casefold() for g in existing):
            raise ServiceError(409, f"Der findes allerede en gruppe med navnet '{name}' på tegningen (store/små bogstaver tæller ikke)")
        try:
            gid = self.db.save_symbol_group(drawing_id, group_id, name, kind, clean, user)
        except sqlite3.IntegrityError:
            raise ServiceError(409, f"Der findes allerede en gruppe med navnet '{name}' på tegningen") from None
        if gid is None:
            raise ServiceError(404, "Gruppen findes ikke")
        log.info("Symbolgruppe gemt: tegning=%s gruppe=%s (%s) medlemmer=%s bruger=%s", drawing_id, name, kind,
                 len(clean) if clean is not None else "uændret", user)
        return self.db.get_symbol_group(drawing_id, gid)  # type: ignore[return-value]

    def change_members(self, user: str, drawing_id: str, group_id: int, add: list[str], remove: list[str]) -> dict[str, Any]:
        add, remove = clean_members(add), clean_members(remove)
        group = self.db.get_symbol_group(drawing_id, group_id)
        if group is None:
            raise ServiceError(404, "Gruppen findes ikke")
        if len(set(group["members"]) | set(add)) > MAX_GROUP_MEMBERS:
            raise ServiceError(400, f"En gruppe kan højst have {MAX_GROUP_MEMBERS} elementer")
        self.db.change_group_members(drawing_id, group_id, add, remove, user)
        log.info("Symbolgruppe %s/%s: +%d −%d medlemmer af %s", drawing_id, group["name"], len(add), len(remove), user)
        return self.db.get_symbol_group(drawing_id, group_id)  # type: ignore[return-value]

    def move_member(self, user: str, drawing_id: str, group_id: int, old: str, new: str) -> dict[str, Any]:  # → gruppen + dropped/discarded
        """Et medlem der ikke findes mere (nyt id) flyttes til det nye element; gruppe-animationerne følger med."""
        group = self.db.get_symbol_group(drawing_id, group_id)
        if group is None:
            raise ServiceError(404, "Gruppen findes ikke")
        if old not in group["members"]:
            raise ServiceError(404, f"'{old}' er ikke medlem af gruppen")
        parts: set[str] | None = None
        if self.symbols is not None:
            info = self.symbols._element(drawing_id, new)   # 404 hvis målet ikke findes i tegningen
            parts = set(info["parts"])
            if old in {s["id"] for s in self.symbols.list_symbols_ids(drawing_id)}:
                raise ServiceError(409, f"'{old}' findes stadig i tegningen — kun et forsvundet medlem kan flyttes")
        moved = self.db.rename_element_in_groups(drawing_id, old, new, group_id, valid_parts=parts)
        log.info("Symbolgruppe %s/%s: medlem %s flyttet til %s af %s (%d dele droppet, %d animationer kasseret)", drawing_id,
                 group["name"], old, new, user, len(moved["dropped"]), moved["discarded"])
        return {**self.db.get_symbol_group(drawing_id, group_id), "dropped": moved["dropped"], "discarded": moved["discarded"]}  # type: ignore[dict-item]

    def reorder(self, user: str, drawing_id: str, ids: list[int]) -> list[dict[str, Any]]:
        if not self.db.reorder_symbol_groups(drawing_id, ids):
            raise ServiceError(400, "Rækkefølgen skal indeholde præcis tegningens grupper")
        log.info("Symbolgrupper omordnet på %s af %s", drawing_id, user)
        return self.db.list_symbol_groups(drawing_id)

    def delete(self, user: str, drawing_id: str, group_id: int) -> str:
        group = self.db.get_symbol_group(drawing_id, group_id)
        if group is None:
            raise ServiceError(404, "Gruppen findes ikke")
        self.db.delete_symbol_group(drawing_id, group_id)
        log.info("Symbolgruppe slettet: tegning=%s gruppe=%s bruger=%s", drawing_id, group["name"], user)
        return group["name"]

    # ------------------------------------------------------------ animationer ejet af gruppen (v0.131.0)

    def get_anims(self, drawing_id: str, group_id: int) -> dict[str, list[dict[str, Any]]]:
        if self.db.get_symbol_group(drawing_id, group_id) is None:
            raise ServiceError(404, "Gruppen findes ikke")
        return {r["element"]: r["anims"] for r in self.db.list_group_anims(drawing_id, group_id)}

    def put_anims_all(self, user: str, drawing_id: str, group_id: int, anims: list[dict[str, Any]], mode: str,
                      skip_invalid: bool) -> dict[str, Any]:
        """Samme animationer på ALLE gruppens medlemmer (v1.2.0). Kun "Hele symbolet" (`part` = all) kan bruges samlet — dele
        hedder forskelligt fra symbol til symbol. Hvert medlem valideres for sig (tags, parametre, om animationen passer til
        symbolet). mode: "add" lægger dem oven i medlemmets egne gruppe-animationer, "replace" erstatter dem.
        skip_invalid: medlemmer hvor det ikke kan bruges springes over; ellers gemmes intet, hvis ét fejler.
        → {results: [{element, ok, count, error?}], applied, skipped}"""
        group = self.db.get_symbol_group(drawing_id, group_id)
        if group is None:
            raise ServiceError(404, "Gruppen findes ikke")
        if mode not in ("add", "replace"):
            raise ServiceError(400, "mode skal være 'add' eller 'replace'")
        if not anims:
            raise ServiceError(400, "Ingen animationer at anvende")
        if any(a.get("part", "all") != "all" for a in anims):
            raise ServiceError(400, "Samlet for alle kan kun \"Hele symbolet\" bruges (delene hedder forskelligt fra symbol til symbol)")
        if not group["members"]:
            raise ServiceError(400, "Gruppen har ingen symboler")
        svc = self.symbols
        others = svc.configs(drawing_id)
        tags = svc._tags()
        present = {s["id"] for s in svc.list_symbols_ids(drawing_id)}
        existing = {r["element"]: r["anims"] for r in self.db.list_group_anims(drawing_id, group_id)}
        results: list[dict[str, Any]] = []
        ready: list[tuple[str, list[dict[str, Any]]]] = []
        for el in group["members"]:
            if el not in present:
                results.append({"element": el, "ok": False, "count": 0, "error": "findes ikke længere på tegningen"})
                continue
            merged = ([*existing.get(el, []), *anims] if mode == "add" else list(anims))
            if len(merged) > MAX_ANIMS:
                results.append({"element": el, "ok": False, "count": 0, "error": f"ville få over {MAX_ANIMS} animationer"})
                continue
            try:
                normalized, res = validate_config({"op": "view", "anims": merged}, svc._element(drawing_id, el), tags, False, el, others)
            except ServiceError as exc:
                results.append({"element": el, "ok": False, "count": 0, "error": exc.message})
                continue
            if res.count:
                results.append({"element": el, "ok": False, "count": 0, "error": res.first()})
                continue
            ready.append((el, normalized["anims"]))
            results.append({"element": el, "ok": True, "count": len(normalized["anims"])})
        failed = [r for r in results if not r["ok"]]
        if failed and not skip_invalid:
            raise ServiceError(400, f"Kan ikke anvendes på {failed[0]['element']}: {failed[0]['error']}"
                               + (f" (og {len(failed) - 1} andre)" if len(failed) > 1 else "") + " — intet er gemt",
                               {"results": results})
        for el, merged_anims in ready:
            if not self.db.set_group_anims(group_id, el, merged_anims, user):
                for r in results:
                    if r["element"] == el:
                        r.update(ok=False, count=0, error="er ikke længere medlem af gruppen")
        applied = sum(1 for r in results if r["ok"])
        log.info("Gruppe-animationer til alle: tegning=%s gruppe=%s mode=%s anvendt=%d sprunget over=%d bruger=%s", drawing_id,
                 group["name"], mode, applied, len(results) - applied, user)
        return {"results": results, "applied": applied, "skipped": len(results) - applied}

    @staticmethod
    def _channel(anim_type: str) -> str:
        return "fill" if anim_type == "flicker" else anim_type   # samme kanal som canvas.ts

    def _overlaps(self, drawing_id: str, group: dict[str, Any], element: str, anims: list[dict[str, Any]],
                  configs: dict[str, dict[str, Any]]) -> list[str]:
        """Advarsler: samme del og slags animation fra flere ejere (symbolet selv eller andre grupper). Vinderen afgøres af
        ejernes rækkefølge — symbolets egne først, så grupperne i deres rækkefølge — og af "passiv"."""
        mine = {(a["part"], self._channel(a["type"])) for a in anims}
        out: list[str] = []
        for a in (configs.get(element) or {}).get("anims", []):
            if (a["part"], self._channel(a["type"])) in mine:
                out.append(f"{a['part']}/{a['type']}: symbolets egen animation gælder også — gruppens kommer efter")
        for row in self.db.list_group_anims(drawing_id):
            if row["element"] != element or row["group_id"] == group["id"]:
                continue
            for a in row["anims"]:
                if (a["part"], self._channel(a["type"])) in mine:
                    out.append(f"{a['part']}/{a['type']}: gruppen {row['group_name']} har også en animation her")
        return list(dict.fromkeys(out))

    def anims_on(self, drawing_id: str, element: str) -> list[dict[str, Any]]:
        """Alle gruppers animationer på ét element (til oversigten over, hvem der ejer hvad): [{group_id, group_name, kind, anims}]."""
        kinds = {g["id"]: g["kind"] for g in self.db.list_symbol_groups(drawing_id)}
        return [{"group_id": r["group_id"], "group_name": r["group_name"], "kind": kinds.get(r["group_id"], "selection"),
                 "anims": r["anims"]} for r in self.db.list_group_anims(drawing_id) if r["element"] == element]

    def put_anims(self, user: str, drawing_id: str, group_id: int, element: str, anims: list[dict[str, Any]]) -> dict[str, Any]:
        """→ {anims: normaliserede animationer, warnings: overlap med andre ejere}."""
        group = self.db.get_symbol_group(drawing_id, group_id)
        if group is None:
            raise ServiceError(404, "Gruppen findes ikke")
        if element not in group["members"]:
            raise ServiceError(400, f"'{element}' er ikke medlem af gruppen '{group['name']}'")
        if not anims:   # tom liste = fjern gruppens animationer på elementet (kræver ingen validering)
            self.db.set_group_anims(group_id, element, [], user)
            return {"anims": [], "warnings": []}
        svc = self.symbols
        info = svc._element(drawing_id, element)
        # Samme regler som symbolets egne animationer (visning uden positioner): tags, dele, parametre
        others = svc.configs(drawing_id)
        normalized, res = validate_config({"op": "view", "anims": anims}, info, svc._tags(), False, element, others)
        if res.count:
            raise ServiceError(400, f"Animationerne kan ikke gemmes ({res.count} fejl) — {res.first()}",
                               {"steps": res.steps, "warnings": res.warnings})
        if not self.db.set_group_anims(group_id, element, normalized["anims"], user):
            raise ServiceError(409, f"'{element}' er ikke længere medlem af gruppen '{group['name']}' — genindlæs og prøv igen")
        warnings = self._overlaps(drawing_id, group, element, normalized["anims"], others)
        log.info("Gruppe-animationer gemt: tegning=%s gruppe=%s element=%s antal=%d bruger=%s", drawing_id, group["name"],
                 element, len(normalized["anims"]), user)
        return {"anims": normalized["anims"], "warnings": warnings}
