"""Backup og restore af SCADA-projektet.

Indhold: PLC-forbindelser (UDEN adgangskoder), tags, tegninger med alle versioner og bindinger.
Ikke med: brugere (en restore må aldrig kunne låse administratorer ude), sessioner, audit-log
og hemmeligheder (CLAUDE.md regel 6).

Restore er "alt eller intet":
1. Hele filen valideres først — SVG'er saneres igen, kilder/bindinger tjekkes. Fejl → intet ændres.
2. Den nuværende tilstand gemmes automatisk som backup på serveren.
3. SVG-filer skrives i en staging-mappe og byttes ind; databasen udskiftes i én transaktion.
   Fejler databasen, byttes de gamle filer tilbage.
4. PLC-runtimes genstartes. Adgangskoder for PLC-nøgler der allerede fandtes, bevares.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..config import read_version
from ..storage.files import DrawingFiles
from .bindings import BindingError, binding_tags, validate_binding
from .schedules import validate_schedule
from .symbol_ports import MAX_TYPES, clean_ports, clean_type
from .trend_views import clean_view
from .symbol_groups import GROUP_KINDS, MAX_GROUP_MEMBERS, MAX_GROUP_NAME, MAX_GROUPS
from .symbols import SymbolConfig, config_tags
from .errors import ServiceError
from .manager import PlcManager
from .plcs import normalize_base_url
from .svg_sanitize import SvgError, sanitize_svg
from .tags import TAG_NAME_RE, WRITABLE_KINDS
from .tagsource import PLC_KEY_RE, TagSourceError, parse_source

log = logging.getLogger(__name__)

FORMAT = "hypervisionplc-scada-backup"
MAX_TREND_DB_BYTES = 2 * 1024 * 1024 * 1024  # udpakket historik ved indlæsning
FORMAT_VERSION = 1
MAX_RESTORE_BYTES = 64 * 1024 * 1024
_DRAWING_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}\Z")
_BACKUP_NAME = re.compile(r"^(scada-(auto|foer-restore)-\d{8}-\d{6}\.json|trends-auto-\d{8}-\d{6}\.db\.gz)\Z")
MAX_ERRORS = 25


def _alarm_fields(t: dict[str, Any], datatype: str) -> tuple[dict[str, Any], str]:
    """Alarmfelter fra en backup (ældre backups uden alarmer giver blot ingen alarmer)."""
    def num(key: str, default: Any) -> Any:
        v = t.get(key, default)
        if v is None:
            return None
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"{key} skal være et tal")
        return float(v)

    try:
        out = {k: num(k, None) for k in ("alarm_hh", "alarm_h", "alarm_l", "alarm_ll")}
        out["alarm_deadband"] = num("alarm_deadband", 0.0) or 0.0
        out["alarm_delay_s"] = num("alarm_delay_s", 0.0) or 0.0
    except ValueError as exc:
        return {}, str(exc)
    on = t.get("alarm_on")
    if on not in (None, "true", "false"):
        return {}, "alarm_on skal være null, 'true' eller 'false'"
    out["alarm_on"] = on
    out["trend"] = bool(t.get("trend", False))
    try:
        iv = num("trend_interval_s", 10.0)
    except ValueError as exc:
        return {}, str(exc)
    if iv is None or not 1 <= iv <= 3600:
        return {}, "trend_interval_s skal være 1-3600"
    out["trend_interval_s"] = iv
    energy = t.get("energy")
    if energy not in (None, "counter", "power"):
        return {}, "energy skal være null, 'counter' eller 'power'"
    try:
        factor = num("energy_factor", 1.0)
    except ValueError as exc:
        return {}, str(exc)
    if factor is None or not 0 < factor <= 1_000_000:
        return {}, "energy_factor skal være et positivt tal"
    if energy is not None and (not out["trend"] or datatype == "bool"):
        return {}, "energi kræver historik og et tal-tag"
    out["energy"], out["energy_factor"] = energy, factor
    limits = [out[k] for k in ("alarm_ll", "alarm_l", "alarm_h", "alarm_hh") if out[k] is not None]
    if limits != sorted(limits):
        return {}, "alarmgrænserne skal stige (LL ≤ L ≤ H ≤ HH)"
    if out["alarm_deadband"] < 0 or not 0 <= out["alarm_delay_s"] <= 3600:
        return {}, "ugyldigt dødbånd/forsinkelse"
    if limits and datatype == "bool":
        return {}, "HH/H/L/LL-grænser kræver et tal-tag"
    if on is not None and datatype not in ("bool", "auto"):
        return {}, "til/fra-alarm kræver et til/fra-tag"
    return out, ""


class BackupService:
    def __init__(self, manager: PlcManager, files: DrawingFiles, backup_dir: Path, keep: int = 7, trend_keep: int = 2):
        self.manager = manager
        self.db = manager.db
        self.files = files
        self.backup_dir = backup_dir
        self.keep = keep
        self.trend_keep = trend_keep
        self.trend_db: Any = None  # sættes når trend-historikken er startet (main.py)
        backup_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    # ----------------------------------------------------------------- eksport

    def export(self, created_by: str) -> dict[str, Any]:
        data = self.db.export_project()
        versions = []
        for v in data["versions"]:
            svg = self.files.read(v["drawing_id"], v["version"])
            if svg is None:
                log.warning("Backup: SVG mangler for %s v%s — springes over", v["drawing_id"], v["version"])
                continue
            versions.append({**v, "svg": svg})
        drawings = []
        for d in data["drawings"]:
            drawings.append({**d, "versions": [{k: v[k] for k in ("version", "comment", "created_at", "svg")}
                                               for v in versions if v["drawing_id"] == d["id"]]})
        return {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "app_version": read_version()["version"],
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "created_by": created_by,
            "contents": "PLC-forbindelser (uden adgangskoder), tags, tegninger, bindinger",
            "plcs": data["plcs"],
            "tags": [{k: v for k, v in t.items()} for t in data["tags"]],
            "drawings": drawings,
            "bindings": data["bindings"],
            "settings": data["settings"],
            "schedules": data["schedules"],
            "symbol_meta": data["symbol_meta"],
            "symbol_config": data["symbol_config"],
            "symbol_groups": data["symbol_groups"],
            "trend_views": data["trend_views"],
            "symbol_ports": data["symbol_ports"],
        }

    def save_to_server(self, kind: str, created_by: str) -> str:
        name = f"scada-{kind}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        path = self.backup_dir / name
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.export(created_by), ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        self._prune(kind)
        return name

    def _prune(self, kind: str) -> None:
        files = sorted(self.backup_dir.glob(f"scada-{kind}-*.json"))
        for old in files[: max(0, len(files) - self.keep)]:
            old.unlink(missing_ok=True)

    def list_server_backups(self) -> list[dict[str, Any]]:
        out = []
        for p in sorted(self.backup_dir.glob("scada-*.json"), reverse=True):
            st = p.stat()
            out.append({"name": p.name, "size": st.st_size, "created": st.st_mtime,
                        "kind": "auto" if "-auto-" in p.name else "før restore"})
        for p in sorted(self.backup_dir.glob("trends-auto-*.db.gz"), reverse=True):
            st = p.stat()
            out.append({"name": p.name, "size": st.st_size, "created": st.st_mtime, "kind": "historik"})
        return sorted(out, key=lambda f: f["created"], reverse=True)

    # ------------------------------------------------------- trend-historik

    def write_trend_snapshot(self, dest_gz: Path) -> int:
        """Komprimeret øjebliksbillede af trend-historikken → filstørrelse. Blokerende (kør i en tråd)."""
        if self.trend_db is None:
            raise ServiceError(503, "Trend-historikken er ikke startet")
        raw = dest_gz.with_name(dest_gz.name + ".tmp-db")
        tmp = dest_gz.with_name(dest_gz.name + ".tmp")
        try:
            self.trend_db.snapshot(raw)
            with raw.open("rb") as src, gzip.open(tmp, "wb", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            tmp.replace(dest_gz)
        finally:
            raw.unlink(missing_ok=True)
            tmp.unlink(missing_ok=True)
        return dest_gz.stat().st_size

    def save_trend_snapshot(self) -> str:
        name = f"trends-auto-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db.gz"
        self.write_trend_snapshot(self.backup_dir / name)
        files = sorted(self.backup_dir.glob("trends-auto-*.db.gz"))
        for old in files[: max(0, len(files) - self.trend_keep)]:
            old.unlink(missing_ok=True)
        return name

    def merge_trends(self, upload: Path) -> dict[str, Any]:
        """Flet en uploadet historik (.db eller .db.gz) ind i den eksisterende. Blokerende (kør i en tråd)."""
        if self.trend_db is None:
            raise ServiceError(503, "Trend-historikken er ikke startet")
        db_file = upload
        unpacked = upload.with_name(upload.name + ".db")
        try:
            with upload.open("rb") as f:
                magic = f.read(16)
            if magic[:2] == b"\x1f\x8b":
                try:
                    with gzip.open(upload, "rb") as src, unpacked.open("wb") as dst:
                        copied = 0
                        while chunk := src.read(1024 * 1024):
                            copied += len(chunk)
                            if copied > MAX_TREND_DB_BYTES:
                                raise ServiceError(413, f"Historikken er for stor udpakket (max {MAX_TREND_DB_BYTES // 1024 // 1024} MB)")
                            dst.write(chunk)
                except (OSError, EOFError):
                    raise ServiceError(400, "Filen er ikke en gyldig .gz-fil") from None
                db_file = unpacked
            elif not magic.startswith(b"SQLite format 3"):
                raise ServiceError(400, "Filen er hverken en trend-historik (.db) eller en komprimeret (.db.gz)")
            try:
                return self.trend_db.merge_from(db_file)
            except ValueError as exc:
                raise ServiceError(400, str(exc)) from None
        finally:
            unpacked.unlink(missing_ok=True)

    def server_backup_path(self, name: str) -> Path:
        if not _BACKUP_NAME.match(name):  # forsvar mod sti-traversering
            raise ServiceError(400, "Ugyldigt filnavn")
        path = self.backup_dir / name
        if not path.is_file():
            raise ServiceError(404, f"Backup '{name}' findes ikke")
        return path

    # ----------------------------------------------------------- validering

    def validate(self, backup: Any) -> dict[str, Any]:
        """Returnér normaliserede data klar til replace_project. Kaster ServiceError(400) med alle fundne fejl."""
        errors: list[str] = []

        def err(msg: str) -> None:
            if len(errors) < MAX_ERRORS:
                errors.append(msg)

        if not isinstance(backup, dict) or backup.get("format") != FORMAT:
            raise ServiceError(400, "Filen er ikke en HypervisionPLC SCADA-backup")
        if backup.get("format_version") != FORMAT_VERSION:
            raise ServiceError(400, f"Ukendt backup-formatversion {backup.get('format_version')!r} — forventet {FORMAT_VERSION}")
        for key in ("plcs", "tags", "drawings", "bindings"):
            if not isinstance(backup.get(key), list):
                raise ServiceError(400, f"Backup mangler listen '{key}'")

        plcs, plc_keys = [], set()
        for i, p in enumerate(backup["plcs"]):
            where = f"PLC #{i + 1}"
            if not isinstance(p, dict):
                err(f"{where}: ikke et objekt")
                continue
            key = p.get("key")
            if not isinstance(key, str) or not PLC_KEY_RE.match(key) or key in plc_keys:
                err(f"{where}: ugyldig eller dublet nøgle {key!r}")
                continue
            try:
                url = normalize_base_url(p.get("base_url", ""))
            except ServiceError as exc:
                err(f"PLC {key}: {exc.message}")
                continue
            username = p.get("username")
            if not isinstance(username, str) or not username.strip():
                err(f"PLC {key}: brugernavn mangler")
                continue
            plc_keys.add(key)
            plcs.append({"key": key, "name": str(p.get("name") or key)[:64], "base_url": url,
                         "username": username.strip(), "enabled": bool(p.get("enabled", True)),
                         "sse_enabled": bool(p.get("sse_enabled", True)), "verify_tls": bool(p.get("verify_tls", True))})

        tags, tag_names = [], set()
        for i, t in enumerate(backup["tags"]):
            name = t.get("name") if isinstance(t, dict) else None
            if not isinstance(name, str) or not TAG_NAME_RE.match(name) or name in tag_names:
                err(f"Tag #{i + 1}: ugyldigt eller dublet navn {name!r}")
                continue
            try:
                source = parse_source(t.get("source"))
            except TagSourceError as exc:
                err(f"Tag {name}: {exc}")
                continue
            if source.plc not in plc_keys:
                err(f"Tag {name}: PLC '{source.plc}' findes ikke i backuppen")
                continue
            scale, offset = t.get("scale", 1), t.get("offset", 0)
            nums_ok = all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                          for x in (scale, offset)) and scale != 0
            lo, hi = t.get("min"), t.get("max")
            if not nums_ok or any(x is not None and (isinstance(x, bool) or not isinstance(x, (int, float)))
                                  for x in (lo, hi)) or (lo is not None and hi is not None and lo > hi):
                err(f"Tag {name}: ugyldig skala/offset/min/max")
                continue
            writable = bool(t.get("writable", False))
            if writable and source.kind not in WRITABLE_KINDS:
                err(f"Tag {name}: kun hr/coil kan være skrivbare")
                continue
            dec = t.get("decimals")
            if dec is not None and (isinstance(dec, bool) or not isinstance(dec, int) or not 0 <= dec <= 6):
                err(f"Tag {name}: decimals skal være 0-6")
                continue
            alarm, alarm_err = _alarm_fields(t, source.datatype)
            if alarm_err:
                err(f"Tag {name}: {alarm_err}")
                continue
            priority = t.get("priority") or "normal"   # ældre backups har ingen prioritet
            if priority not in ("normal", "high") or (priority == "high" and not source.is_external):
                err(f"Tag {name}: priority skal være 'normal' (eller 'high' for eksterne Modbus-tags)")
                continue
            alarm["priority"] = priority
            tag_names.add(name)
            tags.append({"name": name, "source": str(source), "plc": source.plc,
                         "description": str(t.get("description") or "")[:200], "unit": str(t.get("unit") or "")[:16],
                         "scale": float(scale), "offset": float(offset), "decimals": dec, "writable": writable,
                         "min": lo, "max": hi, "confirm_write": bool(t.get("confirm_write", True)), **alarm})

        drawings, versions, files, drawing_ids = [], [], {}, set()
        for i, d in enumerate(backup["drawings"]):
            did = d.get("id") if isinstance(d, dict) else None
            if not isinstance(did, str) or not _DRAWING_ID.match(did) or did in drawing_ids:
                err(f"Tegning #{i + 1}: ugyldigt eller dublet id {did!r}")
                continue
            vlist = d.get("versions")
            if not isinstance(vlist, list) or not vlist:
                err(f"Tegning {did}: ingen versioner")
                continue
            numbers: set[int] = set()
            ok = True
            for v in vlist:
                num = v.get("version") if isinstance(v, dict) else None
                if not isinstance(num, int) or num < 1 or num in numbers:
                    err(f"Tegning {did}: ugyldigt versionsnummer {num!r}")
                    ok = False
                    continue
                try:
                    result = sanitize_svg(v.get("svg") or "")
                except SvgError as exc:
                    err(f"Tegning {did} v{num}: {exc}")
                    ok = False
                    continue
                numbers.add(num)
                files[(did, num)] = result.svg
                versions.append({"drawing_id": did, "version": num, "comment": str(v.get("comment") or "")[:200],
                                 "size": len(result.svg.encode()), "width": result.width, "height": result.height,
                                 "created_at": v.get("created_at") if isinstance(v.get("created_at"), (int, float)) else None})
            active = d.get("active_version")
            if ok and active not in numbers:
                err(f"Tegning {did}: aktiv version {active!r} findes ikke")
                ok = False
            if ok:
                drawing_ids.add(did)
                drawings.append({"id": did, "name": str(d.get("name") or did)[:80], "active_version": active,
                                 "disabled": d.get("disabled") is True})   # ældre backups har ingen deaktivering

        bindings, seen = [], set()
        for i, b in enumerate(backup["bindings"]):
            if not isinstance(b, dict):
                err(f"Binding #{i + 1}: ikke et objekt")
                continue
            did, element = b.get("drawing_id"), b.get("element")
            if did not in drawing_ids or not isinstance(element, str) or not element:
                err(f"Binding #{i + 1}: ukendt tegning {did!r} eller element mangler")
                continue
            try:
                nb = validate_binding(b)
            except BindingError as exc:
                err(f"Binding {did}#{element}: {exc}")
                continue
            if nb["anim"] == "click:goto":
                if nb["params"]["drawing"] not in drawing_ids:
                    err(f"Binding {did}#{element}: goto-tegning '{nb['params']['drawing']}' findes ikke i backuppen")
                    continue
            elif missing := [t for t in binding_tags(nb) if t not in tag_names]:
                err(f"Binding {did}#{element}: tagget '{missing[0]}' findes ikke i backuppen")
                continue
            pos = b.get("position", 0)
            if not isinstance(pos, int) or (did, element, pos) in seen:
                err(f"Binding {did}#{element}: ugyldig/dublet position")
                continue
            seen.add((did, element, pos))
            bindings.append({"drawing_id": did, "element": element, "position": pos, **nb})

        symbol_meta = []
        raw_meta = backup.get("symbol_meta", [])  # ældre backups har ingen symbol-forklaringer
        if not isinstance(raw_meta, list):
            err("symbol_meta skal være en liste")
            raw_meta = []
        for i, m in enumerate(raw_meta):
            if (not isinstance(m, dict) or m.get("drawing_id") not in drawing_ids or not isinstance(m.get("element"), str)
                    or not isinstance(m.get("description"), str) or len(m["description"]) > 500):
                err(f"Symbol-forklaring #{i + 1}: ugyldig (kendt tegning, element og tekst på højst 500 tegn kræves)")
                continue
            symbol_meta.append({"drawing_id": m["drawing_id"], "element": m["element"], "description": m["description"]})

        symbol_config = []
        raw_cfg = backup.get("symbol_config", [])  # ældre backups har ingen symbol-konfigurationer
        if not isinstance(raw_cfg, list):
            err("symbol_config skal være en liste")
            raw_cfg = []
        tag_names_all = {t["name"] for t in tags}
        for i, c in enumerate(raw_cfg):
            if not isinstance(c, dict) or c.get("drawing_id") not in drawing_ids or not isinstance(c.get("element"), str):
                err(f"Symbol-konfiguration #{i + 1}: ukendt tegning eller element mangler")
                continue
            where = f"Symbol {c['drawing_id']}#{c['element']}"
            try:
                cfg = SymbolConfig.model_validate(c.get("config")).model_dump()
            except ValidationError as exc:
                err(f"{where}: ugyldig konfiguration ({exc.errors()[0].get('msg', 'fejl')})")
                continue
            if missing := [t for t in config_tags(cfg) if t not in tag_names_all]:
                err(f"{where}: tagget '{missing[0]}' findes ikke i backuppen")
                continue
            symbol_config.append({"drawing_id": c["drawing_id"], "element": c["element"], "config": cfg})

        symbol_groups = []
        raw_groups = backup.get("symbol_groups", [])  # ældre backups har ingen symbolgrupper
        if not isinstance(raw_groups, list):
            err("symbol_groups skal være en liste")
            raw_groups = []
        seen_groups: set[tuple[str, str]] = set()
        for i, g in enumerate(raw_groups):
            ok = (isinstance(g, dict) and g.get("drawing_id") in drawing_ids and isinstance(g.get("name"), str)
                  and 0 < len(g["name"]) <= MAX_GROUP_NAME and g.get("kind") in GROUP_KINDS
                  and isinstance(g.get("members"), list) and len(g["members"]) <= MAX_GROUP_MEMBERS
                  and all(isinstance(m, str) and 0 < len(m) <= 120 for m in g["members"]))
            if not ok:
                err(f"Symbolgruppe #{i + 1}: ugyldig (kendt tegning, navn, art og medlemmer kræves)")
                continue
            if (g["drawing_id"], g["name"].casefold()) in seen_groups:
                err(f"Symbolgruppe '{g['name']}' på {g['drawing_id']}: navnet findes to gange")
                continue
            if sum(1 for d, _ in seen_groups if d == g["drawing_id"]) >= MAX_GROUPS:
                err(f"Tegningen {g['drawing_id']} har flere end {MAX_GROUPS} symbolgrupper")
                continue
            seen_groups.add((g["drawing_id"], g["name"].casefold()))
            members = list(dict.fromkeys(g["members"]))
            anims: dict[str, list[dict[str, Any]]] = {}
            raw_anims = g.get("anims") or {}   # backups fra før v0.131.0 har ingen gruppe-animationer
            bad = not isinstance(raw_anims, dict)
            for el, lst in ({} if bad else raw_anims).items():
                try:
                    cfg = SymbolConfig.model_validate({"op": "view", "anims": lst}).model_dump()
                except ValidationError as exc:
                    err(f"Symbolgruppe '{g['name']}', {el}: ugyldige animationer ({exc.errors()[0].get('msg', 'fejl')})")
                    continue
                if el not in members:
                    err(f"Symbolgruppe '{g['name']}': animationer på '{el}', som ikke er medlem")
                elif missing := [t for t in config_tags(cfg) if t not in tag_names_all]:
                    err(f"Symbolgruppe '{g['name']}', {el}: tagget '{missing[0]}' findes ikke i backuppen")
                else:
                    anims[el] = cfg["anims"]
            if bad:
                err(f"Symbolgruppe '{g['name']}': anims skal være et objekt")
            symbol_groups.append({"drawing_id": g["drawing_id"], "name": g["name"], "kind": g["kind"],
                                  "members": members, "anims": anims})

        trend_views = []
        raw_views = backup.get("trend_views", [])   # ældre backups har ingen gemte trend-visninger
        if not isinstance(raw_views, list):
            err("trend_views skal være en liste")
            raw_views = []
        seen_views: set[str] = set()
        for i, v in enumerate(raw_views):
            try:
                clean = clean_view(v if isinstance(v, dict) else {})
            except ServiceError as exc:
                err(f"Trend-visning #{i + 1}: {exc.message}")
                continue
            if clean["name"].casefold() in seen_views:
                err(f"Trend-visning '{clean['name']}': navnet findes to gange")
                continue
            seen_views.add(clean["name"].casefold())
            trend_views.append(clean)

        symbol_ports: dict[str, list[list[float]]] = {}
        raw_ports = backup.get("symbol_ports", {})   # ældre backups har ingen rettede tilslutningspunkter
        if not isinstance(raw_ports, dict):
            err("symbol_ports skal være et objekt")
            raw_ports = {}
        if len(raw_ports) > MAX_TYPES:
            err(f"symbol_ports: højst {MAX_TYPES} symboler kan have rettede tilslutningspunkter")
            raw_ports = {}
        for sym_type, ports in raw_ports.items():
            try:
                symbol_ports[clean_type(sym_type)] = clean_ports(ports)
            except ServiceError as exc:
                err(f"Tilslutningspunkter for '{sym_type}': {exc.message}")

        schedules = []
        raw_schedules = backup.get("schedules", [])  # ældre backups har ingen ugeprogrammer
        if not isinstance(raw_schedules, list):
            err("schedules skal være en liste")
            raw_schedules = []
        tag_rows = {t["name"]: {**t, "writable": bool(t["writable"])} for t in tags}
        seen_names: set[str] = set()
        for i, s in enumerate(raw_schedules):
            try:
                clean = validate_schedule(s, tag_rows)
            except ServiceError as exc:
                err(f"Ugeprogram #{i + 1}: {exc.message}")
                continue
            if clean["name"] in seen_names:
                err(f"Ugeprogram '{clean['name']}': navnet findes to gange")
                continue
            seen_names.add(clean["name"])
            schedules.append(clean)

        if errors:
            more = " (flere fejl udeladt)" if len(errors) >= MAX_ERRORS else ""
            raise ServiceError(400, "Backuppen kan ikke gendannes — intet er ændret:\n- " + "\n- ".join(errors) + more)
        settings = backup.get("settings") if isinstance(backup.get("settings"), dict) else {}
        start = settings.get("start_drawing")
        # En start-tegning der ikke findes i backuppen ignoreres (ikke en fejl — Overview viser så den første)
        return {"plcs": plcs, "tags": tags, "drawings": drawings, "versions": versions, "bindings": bindings,
                "files": files, "settings": {"start_drawing": start if start in drawing_ids else None},
                "schedules": schedules, "symbol_meta": symbol_meta, "symbol_config": symbol_config,
                "symbol_groups": symbol_groups, "trend_views": trend_views,
                "symbol_ports": symbol_ports}

    # ---------------------------------------------------------------- restore

    async def restore(self, backup: Any, actor: str) -> dict[str, Any]:
        async with self._lock:
            data = self.validate(backup)
            before = self.save_to_server("foer-restore", actor)
            old_keys = {p["key"] for p in self.db.list_plcs()}
            staging = self.files.stage(data["files"])
            old_dir = self.files.swap_in(staging)
            try:
                self.db.replace_project(data)
            except Exception:
                log.exception("Restore fejlede i databasen — gamle tegningsfiler gendannes")
                self.files.swap_back(old_dir)
                raise ServiceError(500, "Restore fejlede — den tidligere tilstand er bevaret") from None
            shutil.rmtree(old_dir, ignore_errors=True)

            new_keys = {p["key"] for p in data["plcs"]}
            for key in old_keys - new_keys:
                self.manager.secrets.delete_plc_password(key)
            self.manager.cache.remove(list(self.manager.cache.snapshot().keys()))
            for key in old_keys | new_keys:
                await self.manager.reload_plc(key)
            missing = sorted(k for k in new_keys if not self.manager.secrets.has_plc_password(k))
            pins = self.db.symbol_pin_keys()
            missing_pins = sorted(f"{c['drawing_id']}#{c['element']}" for c in data.get("symbol_config", [])
                                  if any((c["config"].get("lock") or {}).get("positions") or [])
                                  and (c["drawing_id"], c["element"]) not in pins)
            log.info("Restore gennemført af %s: %d PLC'er, %d tags, %d tegninger, %d bindinger",
                     actor, len(data["plcs"]), len(data["tags"]), len(data["drawings"]), len(data["bindings"]))
            return {"plcs": len(data["plcs"]), "tags": len(data["tags"]), "drawings": len(data["drawings"]),
                    "schedules": len(data["schedules"]),
                    "versions": len(data["versions"]), "bindings": len(data["bindings"]),
                    "symbol_configs": len(data.get("symbol_config", [])), "symbol_groups": len(data.get("symbol_groups", [])),
                    # B5: symboler med nøglelås uden kode (fx gendannet på en ny server) — en tekniker skal sætte koden
                    "missing_pins": missing_pins,
                    "missing_passwords": missing, "pre_restore_backup": before}

    # ------------------------------------------------------- automatisk backup

    async def auto_backup_loop(self, interval_hours: float) -> None:
        first_delay = 300.0  # første automatiske backup 5 min efter opstart
        await asyncio.sleep(first_delay)
        while True:
            try:
                # i en tråd: læser alle tegninger og skriver filen — må ikke stoppe polling og live-værdier (kodeanalyse F7)
                name = await asyncio.to_thread(self.save_to_server, "auto", "system")
                log.info("Automatisk backup gemt: %s", name)
            except Exception:
                log.exception("Automatisk backup fejlede")
            if self.trend_db is not None and self.trend_keep > 0:
                try:
                    name = await asyncio.to_thread(self.save_trend_snapshot)
                    log.info("Automatisk backup af trend-historik gemt: %s", name)
                except Exception:
                    log.exception("Automatisk backup af trend-historik fejlede")
            await asyncio.sleep(interval_hours * 3600)
