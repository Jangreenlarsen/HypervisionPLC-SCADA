"""Signalvejene er fjernet (v6.0.0-b0395, Jan 2026-11-12: "fjern alt om den signal editor så vi har en frisk tilstand").

Gemte veje og deres opsætning som symbol (`sv~<id>`) slettes — én gang ved opstart, **backup først** (`foer-signalvej-fjern`). Fejler
backuppen, ændres intet, og det prøves igen ved næste opstart. Efter gendannelse af en ældre backup (`force`): ingen ny backup (gendannelsen
springer veje og `sv~`-opsætninger over i forvejen).

Virtuelle signaler er også fjernet: symboler, der læste en vejs gamle tag (`path:`), en blok i en vejs opsætning (`@sv~…`) eller et andet
symbols position/logik som tilbagemelding eller kilde (`sym:`), eller havde en kommando *kun i SCADA*, **røres ikke** — de står i rapporten
(`meta` `report.remove_paths` og audit) og vises med fejl i symbol-guiden, til de rettes.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from ...storage.db import Database

log = logging.getLogger("scada.migration")

DONE_KEY = "migration.remove_paths"
REPORT_KEY = "report.remove_paths"
ACTOR = "system"


def _reads_removed(cfg: dict[str, Any]) -> bool:
    if any(s.get("virtual") for s in cfg.get("signals", [])):
        return True
    srcs = [str(x.get("fb", "")) for x in cfg.get("signals", [])]
    srcs += [str(i.get("src", "")) for b in cfg.get("logic", []) for i in b.get("inputs", [])]
    srcs += [str(a.get("src", "")) for a in cfg.get("anims", [])]
    srcs += [str((a.get("params") or {}).get("dir_tag") or "") for a in cfg.get("anims", [])]
    return any(x.startswith(("path:", "@sv~", "sym:")) for x in srcs)


def migrate(db: Database, backups: Any = None, force: bool = False) -> dict[str, Any] | None:
    """→ rapporten, eller None hvis der intet var at gøre (eller backuppen fejlede: så er intet ændret)."""
    if not force and db.get_meta(DONE_KEY):
        return None
    readers = [{"drawing": c["drawing_id"], "element": c["element"]} for c in db.list_symbol_configs()
               if not c["element"].startswith("sv~") and _reads_removed(c["config"])]
    readers += [{"drawing": g.get("drawing_id", ""), "element": f"{g['element']} (gruppen {g['group_name']})"}
                for g in db.list_group_anims() if _reads_removed({"anims": g["anims"]})]
    if not db.count_signal_paths() and not readers:
        if not force:
            db.set_meta(DONE_KEY, str(time.time()))
        return None
    if backups is not None and not force and db.count_signal_paths():
        try:
            backups.save_to_server("foer-signalvej-fjern", ACTOR)
        except Exception:
            log.exception("Backup før fjernelse af signalvejene fejlede — intet er ændret; prøves igen ved næste opstart")
            return None
    counts = db.remove_signal_paths(ACTOR)
    report = {"at": time.time(), **counts, "readers": readers}
    db.set_meta(REPORT_KEY, json.dumps(report, ensure_ascii=False))
    if not force:
        db.set_meta(DONE_KEY, str(time.time()))
    log.warning("Signalvejene er fjernet: %d veje, %d symbol-opsætninger slettet; %d symboler brugte en vej eller et virtuelt signal "
                "(rettes i symbol-guiden)", counts["paths"], counts["setups"], len(readers))
    return report
