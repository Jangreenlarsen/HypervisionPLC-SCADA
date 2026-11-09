"""Signalveje i Tegn (v4.2.0, PLAN.md › Signalvej fase 2a; v4.13.0: grene).

En signalvej er en navngiven vej gennem tegningen: fra et startsymbol til et slutsymbol gennem rør, T-stykker, bøjninger,
ventiler og pumper. Vejen findes i Tegn ud fra geometrien (frontend/src/lib/signalPath.ts) — her gemmes den:

- **Betingelsen** (svarene på "hvornår går der flow gennem ventil V2 / kører pumpe P1?") bliver til logikblokke (AND) på
  vejens første element med løbelys (ejeren). Mere end 4 betingelser kædes: L2 = @L1 OG næste 3 …
- **Løbelys** lægges på hver del på vejen (rør, bøjning, T-stykkets ben) med blokken som kilde og retning efter vejen.
- **Grene** (v4.13.0): én vej kan have flere slutpunkter. Hver gren får sin egen OG-kæde af de betingelser, der ligger på den; et
  stykke, flere grene går igennem, lyser, når mindst én af dem er aktiv (en ELLER-blok over grenenes slutblokke). Én gren giver
  præcis de samme blokke som før.
- Alt valideres med den almindelige symbolvalidering (`validate_config`) og gemmes i ÉN transaktion sammen med signalvejen.
  `data` husker ejeren, blokkene og delene, så vejen kan rettes og slettes uden at røre brugerens egen opsætning.

Ændrer kun symbolopsætninger (ikke SVG'en, aldrig PLC'en). Kun tekniker og op (api/signal_paths.py).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..storage.db import Database
from .auth import CurrentUser
from .errors import ServiceError
from .svg_sanitize import describe_element, index_svg
from .symbols import MAX_LOGIC, MAX_LOGIC_INPUTS, ON, SymbolConfig, SymbolService, _TagInfo, cfg_refs, config_tags, \
    split_logic_ref, validate_config

log = logging.getLogger("scada.signalpath")

MAX_CONDITIONS = MAX_LOGIC_INPUTS + (MAX_LOGIC - 1) * (MAX_LOGIC_INPUTS - 1)   # 4 + 7·3 = 25 (8 blokke i kæde)
MAX_ELEMENTS = 200
MAX_ENDS = 4          # slutpunkter (grene) pr. signalvej (v4.13.0)
MAX_UI_CHARS = 8000   # guidens valg (vejvalg m.m.) gemmes sammen med vejen — samme grænse i API og backup
_BLOCK = re.compile(r"^L(\d+)\Z")


def _ref(owner: str, element: str, block: str) -> str:
    """Løbelysets kilde: vejens sidste logikblok (`@L3` på ejeren, `@ejer:L3` andre steder) — uden betingelser `@on`."""
    if not block:
        return ON
    return f"@{block}" if element == owner else f"@{owner}:{block}"


def _chunks(conds: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Betingelserne fordelt på blokke: første blok 4, de næste 3 (+ den forrige blok som første indgang)."""
    if not conds:
        return []
    out = [conds[:MAX_LOGIC_INPUTS]]
    rest = conds[MAX_LOGIC_INPUTS:]
    while rest:
        out.append(rest[:MAX_LOGIC_INPUTS - 1])
        rest = rest[MAX_LOGIC_INPUTS - 1:]
    return out


def _free_ids(used: set[str], n: int) -> list[str]:
    out: list[str] = []
    k = 1
    while len(out) < n:
        if f"L{k}" not in used:
            out.append(f"L{k}")
        k += 1
    return out


_DEFAULT = {k: v for k, v in SymbolConfig().model_dump().items() if k != "type"}
BLOCK_PREFIX = "Signalvej: "


def _is_empty(cfg: dict[str, Any]) -> bool:
    """En opsætning, der er HELT som standarden (kun signalvejens løbelys, som nu er fjernet), kan slettes. Har brugeren sat
    noget andet (fejl-tag, alarm, visning …), bevares den."""
    return {**_DEFAULT, **{k: v for k, v in cfg.items() if k != "type"}} == _DEFAULT


def valid_data(d: Any) -> str | None:
    """Kontrol af en signalvejs `data` (fra en backup): → fejltekst eller None."""
    if not isinstance(d, dict):
        return "data skal være et objekt"
    for k in ("start", "end", "owner", "final"):
        if not isinstance(d.get(k, ""), str):
            return f"{k} skal være tekst"
    if not isinstance(d.get("blocks", []), list) or not all(isinstance(b, str) for b in d.get("blocks", [])):
        return "blocks skal være en liste af blok-id'er"
    if not isinstance(d.get("created", []), list) or not all(isinstance(b, str) for b in d.get("created", [])):
        return "created skal være en liste af element-id'er"
    els = d.get("elements", [])
    if not isinstance(els, list):
        return "elements skal være en liste"
    for e in els:
        if not isinstance(e, dict) or not isinstance(e.get("element"), str) or not isinstance(e.get("flows", []), list):
            return "hvert element skal have element og flows"
        if not all(isinstance(f, dict) and isinstance(f.get("part"), str) for f in e.get("flows", [])):
            return "hver flow skal have en del (part)"
    if not isinstance(d.get("conditions", []), list) or not isinstance(d.get("style", {}), dict):
        return "conditions skal være en liste og style et objekt"
    ends = d.get("ends", [])
    if not isinstance(ends, list) or len(ends) > MAX_ENDS or not all(isinstance(x, str) for x in ends):
        return f"ends skal være en liste af højst {MAX_ENDS} element-id'er"
    for e in els:
        br = e.get("branches", [0])
        if not isinstance(br, list) or not all(isinstance(b, int) and not isinstance(b, bool) and 0 <= b < MAX_ENDS for b in br):
            return "branches skal være en liste af gren-numre"
        if not isinstance(e.get("block", ""), str):
            return "block skal være tekst"
    if not isinstance(d.get("ui", {}), dict) or len(json.dumps(d.get("ui", {}), default=str)) > MAX_UI_CHARS:
        return "ui skal være et lille objekt"
    blocks = set(d.get("blocks", []))
    for e in els:
        if e.get("block", "") not in blocks | {""}:
            return "block skal være tom eller en af vejens blokke"
    for c in d.get("conditions", []):
        br = c.get("branches") if isinstance(c, dict) else None
        if br is not None and (not isinstance(br, list) or not all(isinstance(b, int) and not isinstance(b, bool) and 0 <= b < MAX_ENDS for b in br)):
            return "conditions[].branches skal være en liste af gren-numre"
    return None


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
                        "ends": d.get("ends") or ([d["end"]] if d.get("end") else []), "ui": d.get("ui", {}),
                        "elements": d.get("elements", []), "conditions": d.get("conditions", []), "style": d.get("style", {}),
                        "missing": missing, "updated_at": r["updated_at"], "updated_by": r["updated_by"]})
        return out

    def info(self, drawing_id: str, elements: list[str], visible: set[str] | None = None) -> dict[str, Any]:
        """Til guiden: navn, type, symbolets egne tags (forslag til betingelsen) og løbelys der allerede findes.
        `visible`: de tags brugeren må se (None = alle)."""
        self.drawings._require(drawing_id)
        svg = self.drawings.svg(drawing_id)
        configs = self.symbols.configs(drawing_id)
        tags = {t["name"]: t for t in self.db.list_tags() if visible is None or t["name"] in visible}
        owned = self._owned(drawing_id)
        out = []
        for el in elements[:MAX_ELEMENTS]:
            d = describe_element(svg, el)
            if d is None:
                out.append({"element": el, "missing": True})
                continue
            cfg = configs.get(el) or {}
            own = [{"name": t, "is_bool": _TagInfo(tags[t]).is_bool, "unit": tags[t].get("unit") or "",
                    "description": tags[t].get("description") or ""} for t in config_tags(cfg) if t in tags]
            flows = [a.get("part") for a in cfg.get("anims", []) if a.get("type") == "flow"
                     and (el, a.get("part"), a.get("src")) not in owned]
            out.append({"element": el, "name": d.get("name") or "", "type": d["type"], "configured": bool(cfg),
                        "tags": own, "flows": flows})
        all_tags = [{"name": t["name"], "is_bool": _TagInfo(t).is_bool, "unit": t.get("unit") or "",
                     "description": t.get("description") or ""} for t in tags.values()]
        return {"elements": out, "max_conditions": MAX_CONDITIONS, "tags": all_tags}

    def _owned(self, drawing_id: str, skip: int | None = None) -> set[tuple[str, str, str]]:
        """(element, del, kilde) for løbelys, der tilhører en signalvej (ikke brugerens egne)."""
        out: set[tuple[str, str, str]] = set()
        for r in self.db.list_signal_paths(drawing_id):
            if r["id"] == skip:
                continue
            d = r["data"]
            for e in d.get("elements", []):
                for f in e.get("flows", []):
                    out.add((e.get("element"), f.get("part"),
                             _ref(d.get("owner", ""), e.get("element"), e.get("block", d.get("final", "")))))
        return out

    # ------------------------------------------------------------------ fjern en vejs dele fra opsætningerne
    @staticmethod
    def _strip(configs: dict[str, dict[str, Any]], data: dict[str, Any]) -> set[str]:
        """Fjern signalvejens løbelys og logikblokke fra `configs` (kopier). → de ændrede elementer."""
        owner, final, blocks = data.get("owner", ""), data.get("final", ""), set(data.get("blocks", []))
        changed: set[str] = set()
        for e in data.get("elements", []):
            el = e.get("element")
            cfg = configs.get(el)
            if not cfg:
                continue
            ref = _ref(owner, el, e.get("block", final))     # ældre veje har én slutblok (final) til alle
            parts = {f.get("part") for f in e.get("flows", [])}
            keep = [a for a in cfg.get("anims", []) if not (a.get("type") == "flow" and a.get("src") == ref
                                                             and a.get("part") in parts)]
            if len(keep) != len(cfg.get("anims", [])):
                configs[el] = {**cfg, "anims": keep}
                changed.add(el)
        if owner in configs and blocks:
            cfg = configs[owner]
            # kun vejens egne blokke: samme id OG vejens navn (har brugeren lavet en ny blok med samme id, bevares den)
            keep_logic = [b for b in cfg.get("logic", [])
                          if not (b.get("id") in blocks and str(b.get("name", "")).startswith(BLOCK_PREFIX))]
            if len(keep_logic) != len(cfg.get("logic", [])):
                configs[owner] = {**cfg, "logic": keep_logic}
                changed.add(owner)
        return changed

    def _check_refs(self, drawing_id: str, configs: dict[str, dict[str, Any]], owner: str, blocks: set[str]) -> None:
        """Ingen må stadig bruge de fjernede blokke (en tekniker kan have henvist til dem i et andet symbol)."""
        if not owner or not blocks:
            return
        users = []
        for el, cfg in configs.items():
            for s in cfg_refs(cfg):
                o, bid = split_logic_ref(s, el)
                if o == owner and bid in blocks:
                    users.append(el)
        for row in self.db.list_group_anims(drawing_id):
            for s in cfg_refs({"anims": row["anims"]}):
                o, bid = split_logic_ref(s, row["element"])
                if o == owner and bid in blocks:
                    users.append(row["element"])
        if users:
            raise ServiceError(409, f"Signalvejens betingelse bruges også af {', '.join(sorted(set(users)))} — "
                                    "fjern den henvisning først")

    # ------------------------------------------------------------------ gem
    def save(self, actor: CurrentUser, drawing_id: str, body: dict[str, Any], path_id: int | None = None) -> dict[str, Any]:
        self.drawings._require(drawing_id)
        name = " ".join(str(body["name"]).split())[:60]
        if not name:
            raise ServiceError(400, "Giv signalvejen et navn")
        old = None
        if path_id is not None:
            old = self.db.get_signal_path(drawing_id, path_id)
            if old is None:
                raise ServiceError(404, "Signalvejen findes ikke (er den slettet imens?)")
        if any(r["name"].lower() == name.lower() and r["id"] != path_id for r in self.db.list_signal_paths(drawing_id)):
            raise ServiceError(409, f"Der findes allerede en signalvej med navnet '{name}'")
        svg = self.drawings.svg(drawing_id)
        ids = index_svg(svg)
        elements = body["elements"]
        conds = body["conditions"]
        ends = list(dict.fromkeys([body["end"], *(body.get("ends") or [])]))
        if len(ends) > MAX_ENDS:
            raise ServiceError(400, f"Højst {MAX_ENDS} slutpunkter pr. signalvej")
        if body["start"] in ends:
            raise ServiceError(400, "Start og slut må ikke være det samme symbol")
        nb = len(ends)
        for e in elements:
            e["branches"] = sorted({int(b) for b in (e.get("branches") or [0])})
            if e["branches"][0] < 0 or e["branches"][-1] >= nb:
                raise ServiceError(400, f"'{e['element']}' hører til en gren, der ikke findes")
        on_branches = {e["element"]: e["branches"] for e in elements}
        # start gælder alle grene, et slutpunkt kun sin egen (en betingelse på dem, uden at de står som element)
        on_branches.setdefault(body["start"], list(range(nb)))
        for k, end_id in enumerate(ends):
            on_branches.setdefault(end_id, [k])
        for c in conds:
            c["branches"] = sorted({int(b) for b in c["branches"]}) if c.get("branches") else on_branches.get(c["element"], [0])
            if not c["branches"] or c["branches"][0] < 0 or c["branches"][-1] >= nb:
                raise ServiceError(400, f"Betingelsen for '{c['element']}' hører til en gren, der ikke findes")
        if len(elements) > MAX_ELEMENTS:
            raise ServiceError(400, f"Signalvejen er for lang (højst {MAX_ELEMENTS} elementer)")
        if len(conds) > MAX_CONDITIONS:
            raise ServiceError(400, f"Højst {MAX_CONDITIONS} betingelser pr. signalvej")
        missing = [e["element"] for e in elements if e["element"] not in ids]
        missing += [x for x in (body["start"], *ends) if x not in ids]
        if missing:
            raise ServiceError(400, f"Elementet '{missing[0]}' findes ikke i den gemte tegning — gem tegningen og find "
                                    "vejen igen")
        path_ids = {e["element"] for e in elements}
        bad = [c["element"] for c in conds if c["element"] not in path_ids | {body["start"], *ends}]
        if bad:
            raise ServiceError(400, f"Betingelsen for '{bad[0]}' hører ikke til et symbol på vejen")
        flowing = [e for e in elements if e["flows"]]
        if not flowing:
            raise ServiceError(400, "Ingen af delene på vejen kan vise løbelys (rør, bøjninger, T-stykker)")

        before = self.symbols.configs(drawing_id)
        configs = {k: dict(v) for k, v in before.items()}
        if old is not None:
            self._strip(configs, old["data"])
        owner = flowing[0]["element"]

        # Løbelys, der allerede ligger på de samme dele (brugerens egne eller fra en anden signalvej)
        conflicts = []
        for e in flowing:
            cfg = configs.get(e["element"]) or {}
            parts = {f["part"] for f in e["flows"]}
            hits = [a for a in cfg.get("anims", []) if a.get("type") == "flow" and a.get("part") in parts]
            if hits:
                conflicts.append({"element": e["element"], "parts": sorted({a["part"] for a in hits})})
        if conflicts and not body.get("replace"):
            raise ServiceError(409, f"{len(conflicts)} rør har allerede løbelys — bekræft at det skal erstattes",
                               {"conflicts": conflicts})
        other_owned = self._owned(drawing_id, skip=path_id)
        for c in conflicts:
            el = c["element"]
            if any((el, p, a.get("src")) in other_owned for a in configs[el].get("anims", []) for p in c["parts"]
                   if a.get("type") == "flow" and a.get("part") == p):
                raise ServiceError(409, f"'{el}' er en del af en anden signalvej — ret eller slet den først")
            configs[el] = {**configs[el], "anims": [a for a in configs[el].get("anims", [])
                                                    if not (a.get("type") == "flow" and a.get("part") in c["parts"])]}

        # Betingelsen → logikblokke på ejeren: en OG-kæde pr. gren, og en ELLER over grenenes slutblokke for de stykker, flere
        # grene går igennem. Én gren giver præcis de samme blokke som før (v4.13.0).
        bconds = [[c for c in conds if br in c["branches"]] for br in range(nb)]
        chains = [_chunks(bc) for bc in bconds]
        or_sets = sorted({tuple(e["branches"]) for e in flowing
                          if len(e["branches"]) > 1 and all(chains[br] for br in e["branches"])})
        total = sum(len(c) for c in chains) + len(or_sets)
        owner_cfg = dict(configs.get(owner) or {})
        used = {b["id"] for b in owner_cfg.get("logic", [])}
        if len(used) + total > MAX_LOGIC:
            raise ServiceError(400, f"'{owner}' har ikke plads til flere logikblokke (højst {MAX_LOGIC}; vejen skal bruge {total}) — "
                                    "vælg færre betingelser eller grene, eller fjern nogle af elementets egne blokke")
        reuse = [b for b in (old["data"].get("blocks", []) if old and old["data"].get("owner") == owner else [])
                 if b not in used]
        ids_new = (reuse + _free_ids(used | set(reuse), total))[:total]
        label = f"{BLOCK_PREFIX}{name}"[:40]
        blocks = []
        final: list[str] = []
        k = 0
        for br, chain in enumerate(chains):
            prev = ""
            for i, chunk in enumerate(chain):
                bid = ids_new[k]
                inputs = [{"src": f"@{prev}"}] if prev else []
                inputs += [{"src": c["src"], "neg": bool(c.get("neg")), "cmp": c.get("cmp") or "",
                            "value": c.get("value")} for c in chunk]
                if k == 0:
                    nm = label
                elif nb == 1:
                    nm = f"{label[:35]} ({i + 1})"
                else:
                    nm = f"{label[:33]} (g{br + 1}.{i + 1})"
                blocks.append({"id": bid, "name": nm, "op": "and", "inputs": inputs})
                prev = bid
                k += 1
            final.append(prev)
        or_id: dict[tuple[int, ...], str] = {}
        for n_or, sset in enumerate(or_sets, 1):
            bid = ids_new[k]
            k += 1
            srcs = list(dict.fromkeys(final[br] for br in sset))
            blocks.append({"id": bid, "name": f"{label[:28]} (eller {n_or})", "op": "or",
                           "inputs": [{"src": f"@{x}"} for x in srcs]})
            or_id[sset] = bid
        owner_cfg["logic"] = [*owner_cfg.get("logic", []), *blocks]
        configs[owner] = owner_cfg

        def block_of(br: list[int]) -> str:
            """Slutblokken for et stykke: grenens egen, en ELLER over flere, eller "" (altid) hvis en af dem er uden betingelser."""
            if len(br) == 1:
                return final[br[0]]
            if any(not final[x] for x in br):
                return ""
            return or_id[tuple(br)]

        style = body["style"]
        for e in flowing:
            el = e["element"]
            cfg = dict(configs.get(el) or {})
            e["block"] = block_of(e["branches"])
            src = _ref(owner, el, e["block"])
            cfg["anims"] = [*cfg.get("anims", []), *[
                {"part": f["part"], "type": "flow", "when": True, "src": src,
                 "params": {"reverse": bool(f["reverse"]), "light": style["light"], "speed": style["speed"],
                            "dash": style["dash"]}} for f in e["flows"]]]
            configs[el] = cfg

        # Fjernede blokke (gammel ejer) må ikke bruges af andre
        if old is not None:
            od = old["data"]
            gone = set(od.get("blocks", [])) - (set(ids_new) if od.get("owner") == owner else set())
            self._check_refs(drawing_id, configs, od.get("owner", ""), gone)

        # Valider alle ændrede opsætninger — ejeren først (de andre henviser til dens blokke)
        changed = [el for el in configs if configs[el] != before.get(el)]
        changed.sort(key=lambda el: el != owner)
        tags = self.symbols._tags()
        created = set((old["data"].get("created", []) if old else [])) | {el for el in changed if el not in before}
        result: dict[str, dict[str, Any] | None] = {}
        for el in changed:
            cfg = configs[el]
            if el in created and _is_empty(cfg):
                result[el] = None
                continue
            info = describe_element(svg, el)
            if info is None:
                raise ServiceError(400, f"Elementet '{el}' findes ikke i den gemte tegning")
            others = {k: v for k, v in configs.items() if k != el and result.get(k, v) is not None}
            normalized, res = validate_config(cfg, info, tags, self.db.get_symbol_pin_hash(drawing_id, el) is not None,
                                              el, others)
            if res.count:
                who = info.get("name") or el
                raise ServiceError(400, f"Signalvejen kan ikke gemmes — {who}: {res.first()}", {"element": el})
            result[el] = normalized
            configs[el] = normalized
        data = {"start": body["start"], "end": body["end"], "ends": ends, "owner": owner, "blocks": ids_new,
                "final": final[0] if nb == 1 else "",
                "elements": [{"element": e["element"], "flows": e["flows"], "branches": e["branches"], "block": e.get("block", "")}
                             for e in elements],
                "conditions": conds, "style": style, "ui": body.get("ui") or {}, "created": sorted(created & set(configs))}
        sid = self.db.write_signal_path(drawing_id, path_id, name, data, result, actor.username,
                                        expect={el: before.get(el) for el in result})
        if sid is None:
            raise ServiceError(409, "Signalvejen kunne ikke gemmes — navnet er taget, eller den er ændret imens")
        if sid < 0:
            raise ServiceError(409, "Et af symbolerne på vejen er ændret imens (af en anden) — prøv igen")
        self._notify(drawing_id, result)
        log.info("Signalvej '%s' (%s) gemt af %s: %d elementer, %d betingelser, %d opsætninger ændret",
                 name, drawing_id, actor.username, len(elements), len(conds), len(result))
        return {"id": sid, "name": name, "changed": sorted(result), "conflicts_replaced": conflicts}

    def delete(self, actor: CurrentUser, drawing_id: str, path_id: int) -> dict[str, Any]:
        self.drawings._require(drawing_id)
        old = self.db.get_signal_path(drawing_id, path_id)
        if old is None:
            raise ServiceError(404, "Signalvejen findes ikke (er den slettet imens?)")
        before = self.symbols.configs(drawing_id)
        configs = {k: dict(v) for k, v in before.items()}
        changed = self._strip(configs, old["data"])
        od = old["data"]
        self._check_refs(drawing_id, configs, od.get("owner", ""), set(od.get("blocks", [])))
        created = set(od.get("created", []))
        result: dict[str, dict[str, Any] | None] = {
            el: (None if el in created and _is_empty(configs[el]) else configs[el]) for el in changed}
        sid = self.db.write_signal_path(drawing_id, path_id, None, None, result, actor.username,
                                        expect={el: before.get(el) for el in result})
        if sid is None:
            raise ServiceError(404, "Signalvejen findes ikke (er den slettet imens?)")
        if sid < 0:
            raise ServiceError(409, "Et af symbolerne på vejen er ændret imens (af en anden) — prøv igen")
        self._notify(drawing_id, result)
        log.info("Signalvej '%s' (%s) slettet af %s", old["name"], drawing_id, actor.username)
        return {"deleted": path_id, "changed": sorted(result)}

    def _notify(self, drawing_id: str, changed: dict[str, Any]) -> None:
        if self.symbols.on_change is None:
            return
        for el in changed:
            try:
                self.symbols.on_change(drawing_id, el)
            except Exception:   # noqa: BLE001 — runtime genberegner også ved næste tick
                log.exception("Signalvej: runtime-opdatering af %s fejlede", el)
