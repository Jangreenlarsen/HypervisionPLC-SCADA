"""Fjern en PLC (v3.34.0, PLAN.md): flyt dens tags til en anden PLC, eller fjern PLC'en med alle tags og henvisninger.

Før kunne en PLC kun slettes uden tags, og et tag kun uden bindinger, symbolopsætninger og ugeprogrammer — i praksis
umuligt. Nu:
- **usage** viser, hvad der rammes (tags, tegninger, symboler, ugeprogrammer, trendvisninger, API-nøgler, alarmer),
- **move** giver hvert tag en ny kilde på mål-PLC'en (samme adresse/variabel). Alle tags valideres først med tag-reglerne;
  ét problem stopper hele flytningen, før noget ændres. Navne, bindinger, opsætninger og historik bevares,
- **remove_all** tager backup, og fjerner så i ÉN transaktion PLC'en, tagsene og alle henvisninger til dem (rensede
  symbolopsætninger skal sættes op igen). Trendhistorikken (egen database) glemmes bagefter. Alarmhændelser bevares.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from typing import Any, Callable

from ..storage.db import Database
from .auth import CurrentUser, role_at_least
from .errors import ServiceError
from .symbols import config_tags, parse_alarm_ref

log = logging.getLogger("scada.plcs")

BACKUP_KIND = "foer-plc-fjern"
TAG_BACKUP_KIND = "foer-tag-slet"
MAX_TAGS = 1000


def _hit(src: Any, names: set[str]) -> bool:
    """Kilden er et af tagsene — direkte eller som alarm på tagget (@alarm:active:<tag>)."""
    if not isinstance(src, str) or not src:
        return False
    alarm = parse_alarm_ref(src)
    return (alarm[1] if alarm else src) in names


def _dir_tag(a: Any) -> Any:
    params = a.get("params") if isinstance(a, dict) else None
    return params.get("dir_tag") if isinstance(params, dict) else None


def strip_anims(anims: list[dict[str, Any]], names: set[str]) -> list[dict[str, Any]]:
    out = []
    for a in anims:
        if _hit(a.get("src"), names):
            continue   # animationen viste et tag, der ikke findes mere
        a = copy.deepcopy(a)
        params = a.get("params")
        if a.get("type") == "flow" and isinstance(params, dict) and params.get("dir_tag") in names:
            params["dir_tag"] = ""
        out.append(a)
    return out


def strip_config(cfg: dict[str, Any], names: set[str]) -> dict[str, Any] | None:
    """Symbolopsætningen uden henvisninger til tagsene → ny opsætning, eller None hvis den ikke brugte dem."""
    if not set(config_tags(cfg)) & names:
        return None
    out = copy.deepcopy(cfg)
    for s in out.get("signals", []):
        for k in ("tag", "fb"):
            if s.get(k) in names:
                s[k] = ""
    if out.get("fault") in names:
        out["fault"] = ""
    for b in out.get("logic", []):
        for i in b.get("inputs", []):
            if _hit(i.get("src"), names):
                i["src"] = ""
    if out.get("chart"):
        out["chart"]["tags"] = [t for t in out["chart"].get("tags", []) if t not in names]
    out["anims"] = strip_anims(out.get("anims", []), names)
    fl = out.get("flow")
    if isinstance(fl, dict):                     # flowberegningens tags (v6.1.0/v6.3.0): rate, restriktion, målt flow
        for k in ("rate", "restrict", "measured"):
            if isinstance(fl.get(k), dict) and fl[k].get("src") in names:
                fl[k]["src"] = ""
    return out


def moved_source(source: str, key: str, target: str) -> str:
    if not source.startswith(f"{key}:"):
        raise ServiceError(500, f"Kilden '{source}' hører ikke til PLC '{key}'")
    return f"{target}:{source[len(key) + 1:]}"


class PlcRemovalService:
    def __init__(self, db: Database, manager: Any, tags: Any, backup: Any, *, alarms: Any = None,
                 forget_history: Callable[[str], None] | None = None, on_changed: Callable[[], None] | None = None):
        self.alarms = alarms
        self.db = db
        self.manager = manager
        self.tags = tags
        self.backup = backup
        self.forget_history = forget_history
        self.on_changed = on_changed   # symbolernes runtime m.m. læser opsætningerne igen

    def _plc(self, key: str) -> dict[str, Any]:
        plc = self.db.get_plc(key)
        if plc is None:
            raise ServiceError(404, f"PLC '{key}' findes ikke")
        return plc

    def _scan(self, names: set[str]) -> dict[str, Any]:
        """Alle henvisninger til tagsene: (opsætninger, gruppe-animationer, ugeprogrammer, visninger, API-scopes, tegninger)."""
        drawings = {d["id"]: d["name"] for d in self.db.list_drawings()}
        per: dict[str, dict[str, int]] = {}

        def bump(did: str, what: str) -> None:
            per.setdefault(did, {"bindings": 0, "symbols": 0})[what] += 1

        for did in drawings:
            for b in self.db.list_bindings(did):
                if b.get("tag") in names or _dir_tag(b) in names:
                    bump(did, "bindings")
        configs = []
        for r in self.db.list_symbol_configs():
            new = strip_config(r["config"], names)
            if new is not None:
                configs.append((r["drawing_id"], r["element"], new))
                bump(r["drawing_id"], "symbols")
        groups = []
        for r in self.db.list_group_anims():
            if any(_hit(a.get("src"), names) or _dir_tag(a) in names for a in r["anims"]):
                groups.append((r["group_id"], r["element"], strip_anims(r["anims"], names)))
                bump(r["drawing_id"], "symbols")
        schedules = [s for s in self.db.list_schedules() if s.get("tag") in names]
        views: dict[str, dict[str, Any] | None] = {}
        for v in self.db.list_trend_views():
            if set(v.get("tags", [])) & names:
                tags = [t for t in v["tags"] if t not in names]
                views[v["name"]] = ({**v, "tags": tags, "assign": {t: n for t, n in v.get("assign", {}).items() if t in tags}}
                                    if tags else None)
        api: dict[str, dict[str, Any]] = {}
        keys: list[str] = []
        for k in self.db.list_api_keys():
            scope = k.get("scope")
            if isinstance(scope, str):
                try:
                    scope = json.loads(scope)
                except ValueError:
                    continue
            if isinstance(scope, dict) and set(scope.get("tags") or []) & names:
                api[k["id"]] = {**scope, "tags": [t for t in scope["tags"] if t not in names]}
                keys.append(k["name"])
        return {"configs": configs, "groups": groups, "schedules": schedules, "views": views, "api": api, "api_names": keys,
                "drawings": [{"id": d, "name": drawings.get(d, d), **c} for d, c in sorted(per.items(), key=lambda x: drawings.get(x[0], x[0]))]}

    def usage(self, key: str) -> dict[str, Any]:
        self._plc(key)
        tags = self.db.list_tags(plc=key)
        names = {t["name"] for t in tags}
        scan = self._scan(names)
        alarms = sum(1 for a in self.db.list_alarm_states() if a.get("tag") in names)
        return {
            "key": key,
            "tags": len(tags),
            "tag_names": sorted(names)[:200],
            "history": sum(1 for t in tags if t.get("trend")),
            "drawings": scan["drawings"],
            "symbols": len(scan["configs"]) + len(scan["groups"]),
            "schedules": [s["name"] for s in scan["schedules"]],
            "trend_views": sorted(scan["views"]),
            "api_keys": scan["api_names"],
            "alarms": alarms,
            "targets": [{"key": p["key"], "name": p["name"], "enabled": bool(p.get("enabled", True)),
                         "has_password": self.manager.secrets.has_plc_password(p["key"])}
                        for p in self.db.list_plcs() if p["key"] != key],
        }

    # ------------------------------------------------------------ slet tags, der er i brug (v3.35.0)

    def _tag_names(self, raw: list[Any]) -> list[str]:
        names = list(dict.fromkeys(raw))
        if not names:
            raise ServiceError(400, "Vælg mindst ét tag")
        if len(names) > MAX_TAGS:
            raise ServiceError(400, f"Højst {MAX_TAGS} tags ad gangen")
        missing = [n for n in names if not isinstance(n, str) or self.db.get_tag(n) is None]
        if missing:
            raise ServiceError(404, f"Tag findes ikke: {', '.join(str(m)[:60] for m in missing[:10])}"
                                    f"{' …' if len(missing) > 10 else ''} — intet er slettet", {"missing": missing[:100]})
        return names

    @staticmethod
    def _in_use(scan: dict[str, Any]) -> bool:
        return bool(scan["drawings"] or scan["schedules"] or scan["views"] or scan["api"])

    def tag_usage(self, raw: list[Any]) -> dict[str, Any]:
        """Hvad sletning af tagsene rammer (samme oversigt som ved Fjern PLC) + automatiske visninger (B6)."""
        names = self._tag_names(raw)
        wanted = set(names)
        scan = self._scan(wanted)
        auto: list[str] = []
        auto_usage = getattr(self.tags, "auto_usage", None)
        if auto_usage is not None:
            for n in names:
                auto += [f"{n} ({p})" for p in auto_usage(n)]
        tags = [self.db.get_tag(n) or {} for n in names]
        return {
            "tags": len(names),
            "history": sum(1 for t in tags if t.get("trend")),
            "in_use": self._in_use(scan),
            "drawings": scan["drawings"],
            "symbols": len(scan["configs"]) + len(scan["groups"]),
            "schedules": [x["name"] for x in scan["schedules"]],
            "trend_views": sorted(scan["views"]),
            "api_keys": scan["api_names"],
            "alarms": sum(1 for a in self.db.list_alarm_states() if a.get("tag") in wanted),
            "auto": auto[:50],
        }

    async def remove_tags(self, actor: CurrentUser, raw: list[Any]) -> dict[str, Any]:
        """Slet tagsene og alle henvisninger til dem i én transaktion. Bruges de, eller har de historik, tages backup
        først; ubrugte tags uden historik slettes direkte."""
        names = self._tag_names(raw)
        scan = self._scan(set(names))
        self._check_api_keys(actor, scan)
        trend = any((self.db.get_tag(n) or {}).get("trend") for n in names)
        backup = history_backup = None
        needs_backup = self._in_use(scan) or trend
        if needs_backup:
            try:   # uden backup ingen destruktiv handling — i en tråd, så live-data ikke står stille
                backup = await asyncio.to_thread(self.backup.save_to_server, TAG_BACKUP_KIND, actor.username)
                if trend and getattr(self.backup, "trend_db", None) is not None:
                    history_backup = await asyncio.to_thread(self.backup.save_trend_snapshot, TAG_BACKUP_KIND)
            except Exception as exc:
                log.error("Backup før sletning af tags %s fejlede: %s", names[:10], exc)
                raise ServiceError(500, f"Backup før sletningen fejlede ({exc}) — intet er slettet") from None
        # VIGTIGT: ingen `await` mellem _scan og transaktionen (se remove_all). Er tagsene taget i brug (eller fået
        # historik) under backuppen, og blev der ikke taget backup → afvis hellere end at slette uden backup.
        names = self._tag_names(names)
        scan = self._scan(set(names))
        self._check_api_keys(actor, scan)
        if not needs_backup and (self._in_use(scan) or any((self.db.get_tag(n) or {}).get("trend") for n in names)):
            raise ServiceError(409, "Tagget er taget i brug imens — intet er slettet. Prøv igen.")
        counts = self.db.remove_tags_cascade(names, scan["configs"], scan["groups"], [x["id"] for x in scan["schedules"]],
                                             scan["views"], scan["api"], actor.username)
        if counts is None:
            raise ServiceError(409, "Et af tagsene er slettet imens — intet er slettet. Prøv igen.")
        self.manager.reload_tags(removed=names)
        if self.alarms is not None:
            counts["alarms"] = max(counts["alarms"], self.alarms.forget(set(names)))   # samme rækker — tæl dem én gang
        if self.on_changed:
            self.on_changed()
        failed = await asyncio.to_thread(self._forget_all, names) if self.forget_history else 0
        log.info("%d tag(s) slettet af %s (backup %s, historik %s): %s — %s", len(names), actor.username, backup,
                 history_backup, ", ".join(names[:20]), counts)
        return {"backup": backup, "history_backup": history_backup, **counts, "history_failed": failed}

    @staticmethod
    def _check_api_keys(actor: CurrentUser, scan: dict[str, Any]) -> None:
        """API-nøgler kan kun ændres af admin — en tekniker må ikke indsnævre deres adgang via en tag-sletning."""
        if scan["api"] and not role_at_least(actor.role, "admin"):
            raise ServiceError(403, f"Tagget bruges af API-nøgle: {', '.join(scan['api_names'][:5])} — kun en admin kan "
                                    "slette det (eller fjern tagget fra nøglen under Integration først)")

    def _forget_all(self, names: list[str]) -> int:
        bad = 0
        for n in names:
            try:
                self.forget_history(n)  # type: ignore[misc]
            except Exception as exc:   # historikken ligger i sin egen database — fejl her ruller ikke resten tilbage
                bad += 1
                log.warning("Historikken for %s kunne ikke slettes: %s", n, exc)
        return bad

    async def move(self, actor: CurrentUser, key: str, target: str) -> dict[str, Any]:
        self._plc(key)
        if target == key:
            raise ServiceError(400, "Vælg en anden PLC at flytte tagsene til")
        if self.db.get_plc(target) is None:
            raise ServiceError(404, f"PLC '{target}' findes ikke")
        tags = self.db.list_tags(plc=key)
        sources: dict[str, str] = {}
        problems: list[str] = []
        for t in tags:   # samme regler som når et tag rettes (kilde, skrivbarhed, energi, alarm) — alle tjekkes før noget ændres
            try:
                new = moved_source(t["source"], key, target)
                self.tags._validate({"source": new}, t)
                sources[t["name"]] = new
            except ServiceError as exc:
                problems.append(f"{t['name']}: {exc.message}")
        if problems:
            raise ServiceError(400, f"{len(problems)} tag(s) kan ikke flyttes til '{target}' — intet er ændret",
                               {"problems": problems[:100]})
        if not self.db.move_plc_tags(key, target, sources):
            raise ServiceError(409, f"PLC '{key}' er ændret imens (nye tags) — prøv igen")
        self.manager.secrets.delete_plc_password(key)
        await self.manager.reload_plc(key)
        await self.manager.reload_plc(target)
        self.manager.reload_tags(removed=list(sources))   # gamle værdier fra den fjernede PLC må ikke blive stående
        if self.alarms is not None:
            self.alarms.forget(set(sources), plc=key, moved_to=target)
        warnings = []
        tgt = self.db.get_plc(target) or {}
        if not tgt.get("enabled", True):
            warnings.append(f"PLC '{target}' er slået fra — tagsene viser ingen værdier, før den slås til")
        if not self.manager.secrets.has_plc_password(target):
            warnings.append(f"PLC '{target}' har ingen adgangskode — tagsene viser ingen værdier, før den er sat")
        log.info("PLC %s fjernet af %s: %d tags flyttet til %s", key, actor.username, len(sources), target)
        return {"mode": "move", "target": target, "tags": len(sources), "warnings": warnings}

    async def remove_all(self, actor: CurrentUser, key: str) -> dict[str, Any]:
        self._plc(key)
        tags = self.db.list_tags(plc=key)
        names = [t["name"] for t in tags]
        history_backup = None
        try:   # uden backup ingen destruktiv handling — i en tråd, så live-data og WebSocket ikke står stille
            backup = await asyncio.to_thread(self.backup.save_to_server, BACKUP_KIND, actor.username)
            # Historikken ligger ikke i den almindelige backup og slettes nedenfor — tag den med først
            if any(t.get("trend") for t in tags) and getattr(self.backup, "trend_db", None) is not None:
                history_backup = await asyncio.to_thread(self.backup.save_trend_snapshot, BACKUP_KIND)
        except Exception as exc:
            log.error("Backup før fjernelse af PLC %s fejlede: %s", key, exc)
            raise ServiceError(500, f"Backup før fjernelsen fejlede ({exc}) — intet er ændret") from None
        # VIGTIGT: ingen `await` mellem _scan og transaktionen — så kan ingen anden forespørgsel (alle skrive-endpoints
        # kører på event-loopet) gemme en symbolopsætning imellem, som så blev overskrevet med den scannede version.
        names = [t["name"] for t in self.db.list_tags(plc=key)]
        scan = self._scan(set(names))
        counts = self.db.remove_plc_cascade(key, names, scan["configs"], scan["groups"], [s["id"] for s in scan["schedules"]],
                                            scan["views"], scan["api"], actor.username)
        if counts is None:
            raise ServiceError(409, f"PLC '{key}' er ændret imens (nye tags) — prøv igen")
        self.manager.secrets.delete_plc_password(key)
        await self.manager.reload_plc(key)
        self.manager.reload_tags(removed=names)
        if self.alarms is not None:
            counts["alarms"] = max(counts["alarms"], self.alarms.forget(set(names), plc=key))
        if self.on_changed:
            self.on_changed()
        failed = 0
        if self.forget_history and names:
            failed = await asyncio.to_thread(self._forget_all, names)
        log.info("PLC %s fjernet med alt af %s (backup %s, historik %s): %s", key, actor.username, backup, history_backup, counts)
        return {"mode": "all", "backup": backup, "history_backup": history_backup, **counts, "history_failed": failed}
