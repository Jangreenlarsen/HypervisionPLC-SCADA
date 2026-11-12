"""Opgradering til v6.0.0: en signalvej **definerer** kun, hvad den består af (elementer, grene, flowretning).

Fra v4.2–v5.12 havde en vej også betingelser (hvornår den er aktiv), et udseende og senere egne grundanimationer i vejens symbol-
opsætning. Det hører nu til vejens **symbol** (`sv~<id>`, symbol-guidens 6 trin): tilbagemelding fra et PLC-tag eller et andet symbols
position (trin 2), kontaktflade (trin 3) og animationer (trin 4). Der migreres ikke (Jan: "vi ser kun fremad"):

- vejens definition består; betingelser, udseende og `materialized` fjernes (`strip_legacy`);
- vejens symbol-opsætning (`sv~<id>`) nulstilles — den indeholdt animationer, der læste de nu fjernede `path:`-tags (og evt. egne
  logikblokke og animationer: de står i rapporten som antal);
- symboler og grupper, der læste en vejs `path:`-tag eller en blok i vejens opsætning (`@sv~<id>:Lk`), røres ikke, men står i rapporten
  (de vises grå, til de rettes i guiden).

**Ingen backup, ingen ændring:** fejler den automatiske backup (`pre-v6`), ændres intet, og opgraderingen prøves igen ved næste opstart (de
gamle felter ignoreres i mellemtiden). Kører ved opstart (én gang) og efter gendannelse af en ældre backup (`force`: kun veje, der stadig
har det gamle; ingen ny backup). En vej, der ikke er gyldig, springes over og tælles. Rapporten gemmes i `meta` (`report.v60_paths`).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from ...storage.db import Database
from ..signal_paths.validate import is_legacy, strip_legacy, valid_data
from ..symbols import path_symbol_id

log = logging.getLogger("scada.migration")

DONE_KEY = "migration.v60_paths"
REPORT_KEY = "report.v60_paths"
ACTOR = "system"


def _reads_old_path(cfg: dict[str, Any]) -> bool:
    """Læser opsætningen en vejs gamle `path:`-tag eller en blok i en vejs opsætning (`@sv~<id>:Lk`)?"""
    srcs = [str(x.get("fb", "")) for x in cfg.get("signals", [])]
    srcs += [str(i.get("src", "")) for b in cfg.get("logic", []) for i in b.get("inputs", [])]
    srcs += [str(a.get("src", "")) for a in cfg.get("anims", [])]
    srcs += [str((a.get("params") or {}).get("dir_tag") or "") for a in cfg.get("anims", [])]
    return any(x.startswith("path:") or x.startswith("@sv~") for x in srcs)


def migrate(db: Database, backups: Any = None, force: bool = False) -> dict[str, Any] | None:
    """→ rapporten, eller None hvis der intet var at gøre (eller backuppen fejlede: så er intet ændret). `force` (efter en gendannelse):
    intet flag og ingen ny backup."""
    if not force and db.get_meta(DONE_KEY):
        return None
    paths = db.list_signal_paths()
    legacy = [r for r in paths if valid_data(r["data"]) is None and is_legacy(r["data"])]
    invalid = [r for r in paths if valid_data(r["data"]) is not None]
    configs = db.list_symbol_configs()
    readers = [(c["drawing_id"], c["element"]) for c in configs if not c["element"].startswith("sv~") and _reads_old_path(c["config"])]
    readers += [(g["drawing_id"] if "drawing_id" in g else "", f"{g['element']} (gruppen {g['group_name']})") for g in db.list_group_anims()
                if _reads_old_path({"anims": g["anims"]})]
    if not legacy and not readers:
        if not force:
            db.set_meta(DONE_KEY, str(time.time()))
        return None
    if backups is not None and not force:
        try:
            backups.save_to_server("pre-v6", ACTOR)
        except Exception:
            log.exception("Backup før opgradering til v6.0.0 fejlede — intet er ændret; prøves igen ved næste opstart")
            return None
    report: dict[str, Any] = {"at": time.time(), "paths": [], "reset_setups": 0, "skipped_invalid": len(invalid), "readers": []}
    by_key = {(c["drawing_id"], c["element"]): c["config"] for c in configs}
    for r in legacy:
        try:
            cfg = by_key.get((r["drawing_id"], path_symbol_id(r["id"])))
            db.write_signal_path(r["drawing_id"], r["id"], r["name"], strip_legacy(r["data"]), {path_symbol_id(r["id"]): None}, ACTOR)
        except Exception:
            log.exception("Signalvej '%s' (%s) kunne ikke opgraderes — springes over", r["name"], r["drawing_id"])
            report["skipped_invalid"] += 1
            continue
        report["paths"].append({"drawing": r["drawing_id"], "name": r["name"], "conditions": len(r["data"].get("conditions") or []),
                                "animations": len((cfg or {}).get("anims") or []), "logic_blocks": len((cfg or {}).get("logic") or [])})
        report["reset_setups"] += 1 if cfg is not None else 0
    report["readers"] = [{"drawing": d, "element": e} for d, e in readers]
    try:                       # en genkørsel (efter en gendannelse) lægges oven på den tidligere rapport
        prev = json.loads(db.get_meta(REPORT_KEY) or "null")
        if isinstance(prev, dict) and force:
            report["paths"] = [*prev.get("paths", []), *report["paths"]]
            report["reset_setups"] += int(prev.get("reset_setups", 0))
    except ValueError:
        pass
    db.set_meta(REPORT_KEY, json.dumps(report, ensure_ascii=False))
    if not force:
        db.set_meta(DONE_KEY, str(time.time()))
    log.warning("Opgradering v6.0.0 (signalveje): %d veje er nu kun en definition, %d symbol-opsætninger nulstillet, %d symboler læste en vejs "
                "gamle tag, %d veje sprunget over", len(report["paths"]), report["reset_setups"], len(report["readers"]), report["skipped_invalid"])
    return report
