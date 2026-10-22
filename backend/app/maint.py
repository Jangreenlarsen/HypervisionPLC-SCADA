"""Vedligeholdelse ved fuld disk: ryd logfiler, gamle backups og historik uden at web-siden skal virke.

Køres på maskinen som root via `scada-maint` (deploy/scada-maint.sh):

    scada-maint status
    scada-maint logs [--journal-size 100M]
    scada-maint backups [--keep 2] [--moved]
    scada-maint trends --keep-days 14 [--shrink]
    scada-maint history --audit-days 90 --alarm-days 90 [--shrink]
    scada-maint trends-reset [--archive MAPPE]
    scada-maint emergency

Alt er TØRKØRSEL (viser hvad der ville ske og hvor meget plads det giver), medmindre `--yes` er angivet. Tags, brugere, tegninger,
bindinger og opsætning slettes aldrig — kun logfiler, gamle backups og historik (trend-værdier, audit, alarmhistorik).
Hvert skridt skrives i systemloggen (logger -t scada-maint).
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from .config import Settings
from .services import sysconfig
from .storage.trends_db import TrendDatabase

SERVICE = "hypervisionplc-scada"
LOW_FREE_FRACTION = 0.05     # "emergency" går videre til næste trin, så længe der er mindre end 5 % ledigt …
LOW_FREE_BYTES = 200 * 1024 * 1024   # … eller under 200 MB


def fmt(n: float) -> str:
    n = float(n)
    for unit in ("B", "kB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


class Maint:
    def __init__(self, settings: Settings, execute: bool, out: Callable[[str], None] = print, use_service: bool = True):
        self.s = settings
        self.execute = execute
        self.out = out
        self.use_service = use_service
        sysconfig.apply_overrides(self.s)
        self.data = self.s.data_dir
        self.trend_path, _warn = sysconfig.resolve_trend_db_path(self.data)

    # ------------------------------------------------------------- hjælp
    def free(self) -> int:
        return shutil.disk_usage(self.data).free

    def low(self) -> bool:
        du = shutil.disk_usage(self.data)
        return du.free < LOW_FREE_BYTES or du.free / du.total < LOW_FREE_FRACTION

    def note(self, text: str) -> None:
        self.out(("" if self.execute else "[tørkørsel] ") + text)
        if self.execute:
            try:
                subprocess.run(["logger", "-t", "scada-maint", text], check=False, timeout=5)
            except (OSError, subprocess.SubprocessError):
                pass

    def _service(self, action: str) -> None:
        if not (self.execute and self.use_service) or shutil.which("systemctl") is None:
            return
        subprocess.run(["systemctl", action, SERVICE], check=False, timeout=120)

    def _remove(self, path: Path) -> int:
        try:
            size = path.stat().st_size
        except OSError:
            return 0
        if self.execute:
            try:
                path.unlink()
            except OSError as exc:
                self.out(f"  kunne ikke slette {path}: {exc}")
                return 0
        return size

    # ------------------------------------------------------------- status
    def status(self) -> None:
        du = shutil.disk_usage(self.data)
        self.out(f"Disk ({self.data}): {fmt(du.free)} ledig af {fmt(du.total)} ({100 * du.used // du.total} % brugt)"
                 + ("   ← LAV PLADS" if self.low() else ""))
        rows = []
        for name in ("scada.db", "scada.db-wal"):
            p = self.data / name
            if p.exists():
                rows.append((name, p.stat().st_size))
        for suffix in ("", "-wal", ".moved"):
            p = Path(str(self.trend_path) + suffix)
            if p.exists():
                rows.append((str(p), p.stat().st_size))
        for sub in ("backups", "drawings", "updates"):
            d = self.data / sub
            if d.is_dir():
                rows.append((sub + "/", sum(f.stat().st_size for f in d.rglob("*") if f.is_file())))
        for lg in self._logs():
            rows.append((str(lg), lg.stat().st_size))
        for name, size in sorted(rows, key=lambda r: -r[1]):
            self.out(f"  {fmt(size):>10}  {name}")
        j = self._journal_size()
        if j is not None:
            self.out(f"  {fmt(j):>10}  systemd-journal")

    # ------------------------------------------------------------- logfiler
    def _logs(self) -> list[Path]:
        found = []
        for d, patterns in ((self.s.net_state_dir, ("*.log",)), (self.data / "updates", ("*.log",))):
            if d.is_dir():
                for pat in patterns:
                    found += [p for p in d.glob(pat) if p.is_file() and not p.is_symlink()]
        return found

    def _journal_size(self) -> int | None:
        if shutil.which("journalctl") is None:
            return None
        try:
            r = subprocess.run(["journalctl", "--disk-usage"], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return None
        import re
        m = re.search(r"([\d.]+)\s*([KMGT]?)B?", r.stdout.split("take up")[-1]) if "take up" in r.stdout else None
        if not m:
            return None
        return int(float(m.group(1)) * {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}[m.group(2)])

    def logs(self, journal_size: str = "100M") -> int:
        total = 0
        for lg in self._logs():
            size = lg.stat().st_size
            if size == 0:
                continue
            total += size
            if self.execute:
                try:
                    lg.write_text("", encoding="utf-8")   # tømmes (filen bevares, så den ikke bliver oprettet med forkert ejer)
                except OSError as exc:
                    self.out(f"  kunne ikke tømme {lg}: {exc}")
        self.note(f"Logfiler tømmes: {fmt(total)}")
        if shutil.which("journalctl") is not None:
            if self.execute:
                subprocess.run(["journalctl", f"--vacuum-size={journal_size}"], check=False, timeout=120)
            self.note(f"systemd-journal begrænses til {journal_size}")
        return total

    # ------------------------------------------------------------- backups
    def backups(self, keep: int = 2, moved: bool = False) -> int:
        d = self.data / "backups"
        total = 0
        if d.is_dir():
            for pattern in ("scada-*.json", "trends-auto-*.db.gz"):
                files = sorted((p for p in d.glob(pattern) if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
                for p in files[max(0, keep):]:
                    total += self._remove(p)
        if moved:
            for suffix in ("", "-wal", "-shm"):
                p = Path(str(self.trend_path) + ".moved" + suffix)
                if p.exists():
                    total += self._remove(p)
        self.note(f"Gamle backups slettes (beholder de {keep} nyeste af hver slags{', samt trends.db.moved' if moved else ''}): {fmt(total)}")
        return total

    # ------------------------------------------------------------- databaser
    def _need_space_to_shrink(self, path: Path) -> None:
        need = int(path.stat().st_size * 1.2) + 20 * 1024 * 1024
        if self.free() < need:
            raise SystemExit(f"For lidt ledig plads til --shrink (VACUUM skal bruge ca. {fmt(need)}, der er {fmt(self.free())}). "
                             f"Tag først 'logs'/'backups', eller brug 'trends-reset'.")

    def trends(self, keep_days: float, shrink: bool = False) -> int:
        if not self.trend_path.exists():
            self.out("Ingen trend-database fundet")
            return 0
        cutoff = time.time() - keep_days * 86400
        energy_cut = time.time() - max(self.s.energy_days, keep_days) * 86400
        keep = {name: energy_cut for name in self._energy_tags()}
        con = sqlite3.connect(f"file:{self.trend_path}?mode=ro", uri=True, timeout=60)
        try:
            sql = "SELECT COUNT(*) FROM samples s JOIN trend_tags t ON t.id = s.tag_id WHERE s.ts < ?"
            if keep:
                sql += " AND t.name NOT IN (%s)" % ",".join("?" * len(keep))
            marks = con.execute(sql, (cutoff, *keep)).fetchone()[0]
        finally:
            con.close()
        self.note(f"Trend-værdier ældre end {keep_days:g} dage slettes (energi-tags beholdes længere): {marks} rækker")
        if self.execute and marks:
            tdb = TrendDatabase(self.trend_path)
            tdb.purge_before(cutoff, keep)
            self._compact(self.trend_path, shrink)
        return marks

    def _energy_tags(self) -> list[str]:
        """Energi-tags (gemmes længere end anden historik). Læses skrivebeskyttet — ingen oprettelse/migrering af scada.db."""
        path = self.data / "scada.db"
        if not path.exists():
            return []
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
            try:
                return [r[0] for r in con.execute("SELECT name FROM tags WHERE energy IS NOT NULL")]
            finally:
                con.close()
        except sqlite3.Error as exc:
            self.out(f"  advarsel: energi-tags kunne ikke læses ({exc}) — alle tags trimmes ens")
            return []

    def history(self, audit_days: float, alarm_days: float, shrink: bool = False) -> int:
        path = self.data / "scada.db"
        con = sqlite3.connect(str(path), timeout=60)
        try:
            a = con.execute("SELECT COUNT(*) FROM audit WHERE ts < ?", (time.time() - audit_days * 86400,)).fetchone()[0]
            b = con.execute("SELECT COUNT(*) FROM alarm_events WHERE ts < ?", (time.time() - alarm_days * 86400,)).fetchone()[0]
            self.note(f"Audit ældre end {audit_days:g} dage: {a} rækker; alarmhistorik ældre end {alarm_days:g} dage: {b} rækker slettes")
            if self.execute and (a or b):
                con.execute("DELETE FROM audit WHERE ts < ?", (time.time() - audit_days * 86400,))
                con.execute("DELETE FROM alarm_events WHERE ts < ?", (time.time() - alarm_days * 86400,))
                con.commit()
        finally:
            con.close()
        if self.execute and (a or b):
            self._compact(path, shrink)
        return a + b

    def _compact(self, path: Path, shrink: bool) -> None:
        con = sqlite3.connect(str(path), timeout=60, isolation_level=None)
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            if shrink:
                self._need_space_to_shrink(path)
                self.note(f"VACUUM af {path.name} (filen skrumper)")
                con.execute("VACUUM")
                con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            con.close()

    def trends_reset(self, archive: Path | None = None) -> int:
        """Nødløsning: slet HELE trend-historikken (fx når disken er så fuld, at en almindelig sletning ikke kan skrive)."""
        files = [Path(str(self.trend_path) + s) for s in ("", "-wal", "-shm")]
        total = sum(f.stat().st_size for f in files if f.exists())
        self.note(f"Hele trend-historikken slettes ({self.trend_path}): {fmt(total)}"
                  + (f" — en komprimeret kopi gemmes først i {archive}" if archive else ""))
        if not self.execute:
            return total
        self._service("stop")
        try:
            if archive is not None and self.trend_path.exists():
                archive.mkdir(parents=True, exist_ok=True)
                target = archive / f"trends-{time.strftime('%Y%m%d-%H%M%S')}.db.gz"
                with self.trend_path.open("rb") as src, gzip.open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                self.out(f"  arkiveret: {target}")
            for f in files:
                f.unlink(missing_ok=True)
        finally:
            self._service("start")
        return total

    # ------------------------------------------------------------- nødprogram
    def emergency(self) -> None:
        self.out("== Nødoprydning (fra mindst til mest indgribende; stopper, når der er plads nok)")
        self.status()
        steps: list[tuple[str, Callable[[], object]]] = [
            ("logfiler", lambda: self.logs()),
            ("gamle backups", lambda: self.backups(keep=1, moved=True)),
            ("trend-værdier ældre end 7 dage", lambda: self.trends(7)),
            ("audit og alarmhistorik ældre end 30 dage", lambda: self.history(30, 30)),
            ("hele trend-historikken", lambda: self.trends_reset()),
        ]
        for name, step in steps:
            if not self.low() and self.execute:
                self.out(f"Der er nu nok plads ({fmt(self.free())} ledig) — stopper")
                break
            self.out(f"-- {name}")
            try:
                step()
            except (SystemExit, sqlite3.Error, OSError) as exc:
                self.out(f"  trinnet mislykkedes: {exc}")
            self.out(f"  ledig plads nu: {fmt(self.free())}")
        self.out("Færdig." if self.execute else "Tørkørsel — kør igen med --yes for at udføre.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="scada-maint", description="Vedligeholdelse ved fuld disk (tørkørsel, medmindre --yes)")
    ap.add_argument("--yes", action="store_true", help="udfør (uden: kun tørkørsel)")
    ap.add_argument("--no-service", action="store_true", help="start/stop ikke systemd-tjenesten")
    # --yes / --no-service må stå hvor som helst på linjen (også efter kommandoen)
    raw = list(sys.argv[1:] if argv is None else argv)
    argv = [a for a in raw if a in ("--yes", "--no-service")] + [a for a in raw if a not in ("--yes", "--no-service")]
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("logs"); p.add_argument("--journal-size", default="100M")
    p = sub.add_parser("backups"); p.add_argument("--keep", type=int, default=2); p.add_argument("--moved", action="store_true")
    p = sub.add_parser("trends"); p.add_argument("--keep-days", type=float, required=True); p.add_argument("--shrink", action="store_true")
    p = sub.add_parser("history"); p.add_argument("--audit-days", type=float, default=90); p.add_argument("--alarm-days", type=float, default=90)
    p.add_argument("--shrink", action="store_true")
    p = sub.add_parser("trends-reset"); p.add_argument("--archive", type=Path)
    sub.add_parser("emergency")
    args = ap.parse_args(argv)

    destructive = args.cmd != "status"
    if destructive and args.yes and hasattr(os, "geteuid") and os.geteuid() != 0:
        print("Kør som root (su -c 'scada-maint …' eller sudo) — filerne ejes af brugeren 'scada'.", file=sys.stderr)
        return 2
    m = Maint(Settings(), execute=args.yes, use_service=not args.no_service)
    try:
        if args.cmd == "status":
            m.status()
        elif args.cmd == "logs":
            m.logs(args.journal_size)
        elif args.cmd == "backups":
            m.backups(args.keep, args.moved)
        elif args.cmd == "trends":
            m.trends(args.keep_days, args.shrink)
        elif args.cmd == "history":
            m.history(args.audit_days, args.alarm_days, args.shrink)
        elif args.cmd == "trends-reset":
            m.trends_reset(args.archive)
        elif args.cmd == "emergency":
            m.emergency()
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 1
    if destructive and not args.yes:
        print("\nTørkørsel — intet er ændret. Tilføj --yes for at udføre.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
