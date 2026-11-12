"""Server-værktøjskassen `scada-tool` (v5.6.0): de mest brugte vedligeholdelsesfunktioner samlet i ét kommando på serveren.

Køres på maskinen som root via `scada-tool` (deploy/scada-tool.sh) — virker også, når web-siden ikke kører:

    scada-tool status                          version, tjeneste, health, opdatering, disk, hukommelse, seneste fejl
    scada-tool check                           diagnose: hvorfor starter serveren ikke?
    scada-tool logs [-n N] [-f] [--fejl] [--tjeneste scada|update|nginx|llm]
    scada-tool start | stop | restart
    scada-tool update status | reset | apply FIL.tar | rollback
    scada-tool backup list | create | restore FIL.db
    scada-tool user list | reset NAVN
    scada-tool config
    scada-tool maint …                         diskoprydning (scada-maint)

Alt der ændrer noget, spørger først (eller kræver --yes) og logges i systemloggen (`logger -t scada-tool`). Adgangskoder læses kun fra
terminalen (eller stdin) — aldrig fra kommandolinjen — og vises eller logges aldrig.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Sequence

APP = Path(os.environ.get("SCADA_APP_DIR") or "/opt/hypervisionplc-scada")      # (ikke det generiske "APP": det kan arves fra miljøet)
ENVFILE = Path(os.environ.get("ENVFILE", "/etc/hypervisionplc-scada.env"))
UNITS = {"scada": "hypervisionplc-scada", "update": "hypervisionplc-scada-update", "nginx": "nginx", "llm": "hypervisionplc-scada-llm"}
SECRET = re.compile(r"PASS|PWD|SECRET|TOKEN|KEY|PIN|CREDENTIAL|AUTH|COOKIE", re.I)
UPDATE_WAIT_S = 420
ASSUME_YES = False


def say(msg: str = "") -> None:
    print(msg, flush=True)


def audit(msg: str) -> None:
    """Systemloggen (aldrig en adgangskode)."""
    try:
        subprocess.run(["logger", "-t", "scada-tool", msg], timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def run(cmd: Sequence[str], timeout: float = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout, errors="replace")
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)


def confirm(question: str) -> bool:
    if ASSUME_YES:
        return True
    if not sys.stdin.isatty():
        say(f"{question} — afbrudt (kræver --yes, når der ikke er en terminal)")
        return False
    return input(f"{question} [j/N] ").strip().lower() in ("j", "ja", "y", "yes")


def settings() -> Any:
    from .config import Settings
    try:
        return Settings()
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Miljøfilen er ugyldig: {exc}") from None


def version_of(root: Path = APP) -> str:
    try:
        d = json.loads((root / "version.json").read_text(encoding="utf-8"))
        return f"{d['version']} build {d['build']}"
    except (OSError, ValueError, KeyError):
        return "ukendt"


def is_active(unit: str) -> bool | None:
    code, out = run(["systemctl", "is-active", unit], 10)
    if code == 127:
        return None          # ingen systemd (fx under test)
    return out.strip() == "active"


def is_running(unit: str) -> bool | None:
    """Som is_active, men også mens en oneshot-tjeneste kører ('activating') — fx opdateringstjenesten."""
    code, out = run(["systemctl", "is-active", unit], 10)
    if code == 127:
        return None
    return out.strip() in ("active", "activating", "reloading", "deactivating")


def write_json(path: Path, data: dict[str, Any], mode: int = 0o644, like: Path | None = None) -> None:
    """Skriv atomisk (tmp + replace) — web-siden læser filen, mens vi skriver."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.chmod(mode)
    if like is not None:
        _chown_like(tmp, like)
    tmp.replace(path)


def num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def fix_owner(s: Any) -> None:
    """Root har måske åbnet databasen: giv scada.db, -wal og -shm tilbage til ejeren af data-mappen (ellers kan tjenesten ikke skrive)."""
    for ext in ("", "-wal", "-shm"):
        p = Path(str(s.db_path) + ext)
        if p.exists():
            _chown_like(p, s.data_dir)


def health(port: int, timeout: float = 3) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as r:
            data = json.load(r)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def wait_health(port: int, seconds: float, want: tuple[str, str] | None = None) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        h = health(port)
        if h and h.get("status") == "ok" and (want is None or (str(h.get("version")), str(h.get("build"))) == want):
            return True
        time.sleep(2)
    return False


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def human(n: float) -> str:
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ------------------------------------------------------------------------------------------------- status

def memory_line() -> str:
    try:
        info = {k: int(v.split()[0]) * 1024 for k, v in (ln.split(":", 1) for ln in Path("/proc/meminfo").read_text().splitlines())}
        return f"{human(info['MemAvailable'])} ledig af {human(info['MemTotal'])}"
    except (OSError, KeyError, ValueError):
        return "ukendt"


def cmd_status(_: argparse.Namespace) -> int:
    s = settings()
    say(f"Version installeret:   {version_of()}")
    active = is_active(UNITS["scada"])
    code, since = run(["systemctl", "show", UNITS["scada"], "-p", "ActiveEnterTimestamp", "--value"], 10)
    say(f"Tjeneste:              {'kører' if active else 'KØRER IKKE' if active is False else 'ukendt'}{f' (siden {since})' if active and code == 0 and since else ''}")
    h = health(s.port)
    say(f"/api/health (:{s.port}):   " + (f"ok — {h.get('version')} build {h.get('build')}" if h and h.get("status") == "ok"
                                          else "SVARER IKKE" + ("" if active else " (tjenesten kører ikke — prøv: scada-tool check)")))
    st = read_json(s.data_dir / "updates" / "status.json")
    if st:
        say(f"Seneste opdatering:    {st.get('state')} — {st.get('message')} ({st.get('from')} → {st.get('to')})")
    for label, path in (("Disk (data)", s.data_dir), ("Disk (/)", Path("/"))):
        try:
            u = shutil.disk_usage(path)
            say(f"{label + ':':<22} {human(u.free)} ledig af {human(u.total)} ({100 * u.used // max(u.total, 1)} % brugt)")
        except OSError:
            pass
    say(f"Hukommelse:            {memory_line()}")
    for key in ("update", "nginx", "llm"):
        a = is_running(UNITS[key])
        if a is not None:
            say(f"{UNITS[key] + ':':<46} {'kører' if a else 'ikke aktiv'}")
    code, errs = run(["journalctl", "-u", UNITS["scada"], "-p", "err", "--since", "-2 hours", "--no-pager", "-n", "5", "-o", "cat"], 15)
    if code == 0 and errs and "-- No entries --" not in errs:
        say("\nSeneste fejl i loggen (2 timer):")
        say("\n".join("  " + ln[:200] for ln in errs.splitlines()))
    return 0


# ------------------------------------------------------------------------------------------------- check

def cmd_check(_: argparse.Namespace) -> int:
    """Diagnose af en server, der ikke starter: hvert tjek siger OK eller hvad der er galt."""
    try:
        s = settings()
    except SystemExit as exc:
        say(f"FEJL   {exc}")
        return 1
    bad = 0

    def line(ok: bool, what: str, detail: str = "") -> None:
        nonlocal bad
        bad += 0 if ok else 1
        say(f"{'OK    ' if ok else 'FEJL  '} {what}" + (f" — {detail}" if detail else ""))

    line(version_of() != "ukendt", "version.json kan læses", version_of())
    line(ENVFILE.is_file(), f"miljøfilen {ENVFILE} findes")
    # appen skal kunne importeres med serverens egen Python (fanger en manglende import, syntaksfejl, manglende pakke)
    code, out = run([sys.executable, "-c", "import app.main"], 90)
    if code == 0:
        line(True, "appen kan importeres (python -c 'import app.main')")
    else:
        line(False, "appen kan IKKE importeres", "sidste linjer:\n    " + "\n    ".join(out.splitlines()[-6:]))
    # databaserne
    for path in (s.db_path, s.data_dir / "trends.db"):
        if not path.exists():
            line(path != s.db_path, f"{path.name} findes", "(oprettes ved første start)" if path != s.db_path else "mangler")
            continue
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
            res = con.execute("PRAGMA quick_check").fetchone()
            con.close()
            line(bool(res) and res[0] == "ok", f"{path.name}: PRAGMA quick_check", str(res[0] if res else "intet svar"))
        except sqlite3.Error as exc:
            line(False, f"{path.name} kan ikke åbnes", str(exc))
    fix_owner(s)         # (en skrivebeskyttet åbning kan have oprettet -shm som root)
    # rettigheder: tjenestens bruger skal kunne skrive i data-mappen
    code, user = run(["systemctl", "show", UNITS["scada"], "-p", "User", "--value"], 10)
    if code == 0 and user.strip():
        try:
            import pwd
            owner = pwd.getpwuid(s.data_dir.stat().st_uid).pw_name
            line(owner == user.strip(), f"data-mappen {s.data_dir} ejes af tjenestens bruger", f"ejer {owner}, tjenesten kører som {user.strip()}")
        except (ImportError, KeyError, OSError) as exc:
            line(False, "data-mappen kan ikke undersøges", str(exc))
    # tjenesten og porten
    active = is_active(UNITS["scada"])
    if active is not None:
        line(bool(active), "tjenesten kører", "" if active else "start den med: scada-tool start")
    h = health(s.port)
    line(bool(h and h.get("status") == "ok"), f"/api/health svarer på port {s.port}", f"{h.get('version')} build {h.get('build')}" if h else "")
    if active is False or (active is not None and not h):
        code, journal = run(["journalctl", "-u", UNITS["scada"], "-n", "40", "--no-pager", "-o", "cat"], 15)
        hit = [ln for ln in journal.splitlines() if re.search(r"Traceback|Error|error|Exception|FEJL", ln)]
        if hit:
            say("\nFra loggen (seneste fejl):")
            say("\n".join("  " + ln[:220] for ln in hit[-8:]))
    # en hængende opdatering?
    st = read_json(s.data_dir / "updates" / "status.json")
    if st and st.get("state") in ("applying", "queued"):
        ua = is_running(UNITS["update"])
        age = time.time() - num(st.get("ts"))
        line(not (ua is False and age > 120), "opdateringsstatus", f"står som '{st.get('state')}' i {age / 60:.0f} min, men opdateringstjenesten kører ikke — ryd med: scada-tool update reset")
    say("\n" + ("Alt ser fint ud." if not bad else f"{bad} problem{'er' if bad != 1 else ''} fundet."))
    return 1 if bad else 0


# ------------------------------------------------------------------------------------------------- logs, start/stop

def cmd_logs(a: argparse.Namespace) -> int:
    cmd = ["journalctl", "-u", UNITS[a.tjeneste], "--no-pager", "-o", "short-iso", "-n", str(a.n)]
    if a.fejl:
        cmd += ["-p", "err"]
    if a.f:
        cmd.append("-f")
    return subprocess.call(cmd)


def cmd_service(a: argparse.Namespace) -> int:
    s = settings()
    if a.action != "start" and not confirm(f"{a.action} {UNITS['scada']}?"):
        return 1
    code, out = run(["systemctl", a.action, UNITS["scada"]], 120)
    audit(f"{a.action} {UNITS['scada']} (exit {code})")
    if code != 0:
        say(f"systemctl {a.action} fejlede: {out}")
        return 1
    if a.action == "stop":
        say("Tjenesten er stoppet.")
        return 0
    say("Venter på /api/health …")
    if wait_health(s.port, 60):
        say(f"Serveren svarer: {version_of()}")
        return 0
    say("Serveren svarer ikke efter 60 s. De seneste linjer i loggen:")
    subprocess.call(["journalctl", "-u", UNITS["scada"], "-n", "25", "--no-pager", "-o", "cat"])
    say("\nKør 'scada-tool check' for en diagnose.")
    return 1


# ------------------------------------------------------------------------------------------------- opdatering

def _updates(s: Any) -> Path:
    return s.data_dir / "updates"


def cmd_update_status(_: argparse.Namespace) -> int:
    d = _updates(settings())
    st = read_json(d / "status.json")
    say(json.dumps(st, ensure_ascii=False, indent=2) if st else "Ingen opdateringsstatus (aldrig opdateret via web/CLI).")
    staged = read_json(d / "staged.json")
    if staged:
        say(f"Klargjort pakke: {staged.get('version')} build {staged.get('build')} ({staged.get('relation')})")
    say(f"Anmodning venter: {'ja' if (d / 'apply.request').exists() else 'nej'}")
    ua = is_running(UNITS["update"])
    say(f"Opdateringstjenesten: {'kører' if ua else 'kører ikke' if ua is False else 'ukendt'}")
    try:
        log = (d / "update.log").read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
        if log:
            say("\nupdate.log (seneste 20 linjer):\n" + "\n".join("  " + ln for ln in log))
    except OSError:
        pass
    return 0


def cmd_update_reset(a: argparse.Namespace) -> int:
    """Ryd en hængende opdatering (status 'applying'/'queued', en anmodning eller halvfærdige filer) — rører kun updates/-mappen."""
    d = _updates(settings())
    if is_running(UNITS["update"]) and not a.force:
        say("Opdateringstjenesten kører lige nu — vent til den er færdig (eller brug --force, hvis du er sikker på, at den hænger).")
        return 1
    st = read_json(d / "status.json") or {}
    say(f"Status nu: {st.get('state', 'ingen')} — {st.get('message', '')}")
    if not confirm("Ryd den hængende opdatering?"):
        return 1
    for name in ("apply.request", "apply.request.tmp", "incoming.tar"):
        (d / name).unlink(missing_ok=True)
    for p in d.glob("incoming-*.part"):
        p.unlink(missing_ok=True)
    keep = ("from", "to", "by")
    write_json(d / "status.json", {"state": "failed", "message": "Ryddet manuelt med scada-tool update reset", "ts": time.time(),
                                   **{k: st[k] for k in keep if k in st}})
    audit("update reset: hængende opdatering ryddet")
    say("Ryddet. Du kan nu uploade/anvende en pakke igen.")
    return 0

def _backup_db(s: Any, kind: str) -> Path:
    dest_dir = s.data_dir / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"scada-{kind}-{time.strftime('%Y%m%d-%H%M%S')}.db"
    src = sqlite3.connect(f"file:{s.db_path}?mode=ro", uri=True, timeout=30)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    dest.chmod(0o600)
    _chown_like(dest, s.data_dir)
    fix_owner(s)
    return dest


def _chown_like(path: Path, ref: Path) -> None:
    try:
        st = ref.stat()
        os.chown(path, st.st_uid, st.st_gid)
    except (OSError, AttributeError):
        pass


def cmd_update_apply(a: argparse.Namespace) -> int:
    """Installér en OTA-pakke fra en fil på serveren (samme kontrol og tilbagerulning som System › Opdatering)."""
    from .services.errors import ServiceError
    from .services.updates import inspect_package, relation
    s = settings()
    d = _updates(s)
    pkg = Path(a.file)
    if not (d / "enabled").is_file():
        say("Opdatering er ikke aktiveret på denne server (eller data-mappen er en anden end opdateringstjenestens) — kør 'sh deploy/install.sh' som root.")
        return 1
    if is_running(UNITS["update"]):
        say("Opdateringstjenesten kører lige nu — vent til den er færdig.")      # (gælder også med --force: to kørsler ødelægger hinanden)
        return 1
    st = read_json(d / "status.json") or {}
    if st.get("state") in ("applying", "queued") and not a.force:
        say("En opdatering står som i gang — tjek 'scada-tool update status', og ryd evt. med 'scada-tool update reset'.")
        return 1
    # først en kopi, og alt kontrolleres på KOPIEN — så kontrolsummen i anmodningen er af præcis den fil, der installeres
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "staged.tar.tmp"
    try:
        shutil.copyfile(pkg, tmp)
        tmp.chmod(0o600)
        _chown_like(tmp, d)
        info = inspect_package(tmp)
    except (ServiceError, OSError) as exc:
        tmp.unlink(missing_ok=True)
        say(f"Pakken kan ikke bruges: {getattr(exc, 'message', exc)}")
        return 1
    try:
        cur = json.loads((APP / "version.json").read_text(encoding="utf-8"))
        rel = relation(cur, info)
        say(f"Pakke:      {info['version']} build {info['build']} ({human(info['size'])}, {info['files']} filer)")
        say(f"SHA256:     {info['sha256']}")
        say(f"Installeret: {cur.get('version')} build {cur.get('build')} → pakken er "
            f"{dict(newer='nyere', same='den samme', older='ÆLDRE', unknown='ukendt').get(rel, rel)}")
        if rel == "older":
            say("Nedgradering understøttes ikke (databasen kan være opgraderet).")
            return 1
        if rel == "same" and not a.reinstall:
            say("Samme version — brug --reinstall for at geninstallere.")
            return 1
        if not confirm("Installér pakken nu? Serveren genstartes, og rulles tilbage, hvis den nye version ikke svarer"):
            return 1
        if not a.no_backup:
            say(f"Backup af databasen: {_backup_db(s, 'pre-update-cli').name}")
        tmp.replace(d / "staged.tar")
    finally:
        tmp.unlink(missing_ok=True)
    write_json(d / "staged.json", {**info, "relation": rel, "uploaded_by": "scada-tool", "uploaded_at": time.time()}, like=d)
    write_json(d / "status.json", {"state": "queued", "message": "Anmodning sendt til opdateringstjenesten", "from": cur.get("version"),
                                   "to": info["version"], "by": "scada-tool", "ts": time.time()})
    req = d / "apply.request.tmp"
    req.write_text(f"SHA256={info['sha256']}\nBY=scada-tool\nVERSION={info['version']}\nBUILD={info['build']}\n", encoding="utf-8")
    req.replace(d / "apply.request")      # først nu ser opdateringstjenesten den
    audit(f"update apply {info['version']} build {info['build']} fra {pkg.name}")
    say("Anmodning sendt. Venter på resultatet …")
    end, last = time.time() + UPDATE_WAIT_S, ""
    while time.time() < end:
        time.sleep(3)
        st = read_json(d / "status.json") or {}
        msg = f"{st.get('state')}: {st.get('message')}"
        if msg != last:
            say("  " + msg)
            last = msg
        if st.get("state") in ("done", "failed", "rolled_back"):
            if st["state"] != "done":
                try:
                    say("\nupdate.log:\n" + "\n".join("  " + ln for ln in (d / "update.log").read_text(errors="replace").splitlines()[-20:]))
                except OSError:
                    pass
            return 0 if st["state"] == "done" else 1
    say("Tiden gik, før opdateringen blev færdig — tjek 'scada-tool update status'.")
    return 1

def cmd_update_rollback(_: argparse.Namespace) -> int:
    """Gendan forrige version (<app>.prev, som opdateringen lagde) og start tjenesten."""
    s = settings()
    prev = Path(str(APP) + ".prev")
    if not (prev / "backend").is_dir() or not (prev / "version.json").is_file():
        say(f"Der er ingen forrige version at gå tilbage til ({prev}/backend findes ikke).")
        return 1
    if not (APP / "version.json").is_file() or APP.resolve() in (Path("/"), Path("/opt")):
        say(f"{APP} ser ikke ud som en installation — afbrudt.")
        return 1
    if is_running(UNITS["update"]):
        say("Opdateringstjenesten kører lige nu — vent til den er færdig.")
        return 1
    say(f"Installeret: {version_of()}   Forrige: {version_of(prev)}")
    if not confirm("Gå tilbage til den forrige version?"):
        return 1
    # først kopieres til .new ved siden af (fuld disk m.m. opdages, mens den nuværende version stadig er intakt) — derefter byttes
    new = {sub: APP / f"{sub}.new" for sub in ("backend", "frontend")}
    try:
        for sub, dest in new.items():
            shutil.rmtree(dest, ignore_errors=True)
            if (prev / sub).is_dir():
                shutil.copytree(prev / sub, dest, symlinks=True)
    except OSError as exc:
        for dest in new.values():
            shutil.rmtree(dest, ignore_errors=True)
        say(f"Kopieringen af den forrige version fejlede ({exc}) — intet er ændret, og tjenesten kører videre.")
        return 1
    code, out = run(["systemctl", "stop", UNITS["scada"]], 120)
    if code != 0 or is_active(UNITS["scada"]):
        for dest in new.values():
            shutil.rmtree(dest, ignore_errors=True)
        say(f"Tjenesten kunne ikke stoppes ({out}) — afbrudt, intet er ændret.")
        return 1
    for sub, dest in new.items():
        shutil.rmtree(APP / sub, ignore_errors=True)
        if dest.is_dir():
            dest.rename(APP / sub)
    shutil.copyfile(prev / "version.json", APP / "version.json")
    audit(f"update rollback til {version_of(prev)}")
    run(["systemctl", "start", UNITS["scada"]], 120)
    ok = wait_health(s.port, 60)
    say(f"{'Serveren svarer' if ok else 'Serveren svarer IKKE'}: {version_of()}" + ("" if ok else " — kør 'scada-tool check'"))
    return 0 if ok else 1

# ------------------------------------------------------------------------------------------------- backup, brugere

def cmd_backup(a: argparse.Namespace) -> int:
    s = settings()
    bdir = s.data_dir / "backups"
    if a.action == "list":
        files = sorted([p for p in bdir.glob("*") if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
        for p in files:
            st = p.stat()
            say(f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))}  {human(st.st_size):>9}  {p.name}")
        if not files:
            say("Ingen backups.")
        return 0
    if a.action == "create":
        say(f"Backup af databasen: {_backup_db(s, 'cli')}")
        audit("backup create")
        return 0
    # restore: kun en .db fra denne maskine (SQLite-kopi). JSON-backups gendannes i System › Backup.
    src = Path(a.file or "")
    if not src.is_file() or src.suffix != ".db":
        say("Angiv en .db-backup fra 'scada-tool backup list' (JSON-backups gendannes i web: System › Backup).")
        return 1
    try:
        con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        ok = con.execute("PRAGMA quick_check").fetchone()
        con.close()
    except sqlite3.Error as exc:
        say(f"Backuppen kan ikke åbnes: {exc}")
        return 1
    if not ok or ok[0] != "ok":
        say("Backuppen er beskadiget (quick_check).")
        return 1
    if not confirm(f"Erstat databasen med {src.name}? Serveren stoppes, og den nuværende database gemmes først"):
        return 1
    if is_running(UNITS["update"]):
        say("Opdateringstjenesten kører lige nu — vent til den er færdig.")
        return 1
    code, out = run(["systemctl", "stop", UNITS["scada"]], 120)
    if code != 0 or is_active(UNITS["scada"]):
        say(f"Tjenesten kunne ikke stoppes ({out}) — afbrudt, databasen er urørt.")
        return 1
    keep = _backup_db(s, "before-restore")
    tmp = s.db_path.with_name(s.db_path.name + ".restore.tmp")
    try:
        shutil.copyfile(src, tmp)
        tmp.chmod(0o640)
        _chown_like(tmp, s.data_dir)
        for ext in ("-wal", "-shm"):
            Path(str(s.db_path) + ext).unlink(missing_ok=True)
        tmp.replace(s.db_path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        say(f"Gendannelsen fejlede ({exc}) — den nuværende database er urørt (kopi: {keep.name}). Starter tjenesten igen.")
        run(["systemctl", "start", UNITS["scada"]], 120)
        return 1
    audit(f"backup restore {src.name} (den gamle gemt som {keep.name})")
    run(["systemctl", "start", UNITS["scada"]], 120)
    ok = wait_health(s.port, 60)
    say(f"Gendannet. Den gamle database ligger i {keep.name}. Serveren svarer: {'ja' if ok else 'NEJ — kør scada-tool check'}")
    return 0 if ok else 1


def _read_password() -> str:
    if sys.stdin.isatty():
        a, b = getpass.getpass("Ny adgangskode: "), getpass.getpass("Gentag adgangskoden: ")
        if a != b:
            raise SystemExit("De to adgangskoder er ikke ens.")
        return a
    return sys.stdin.readline().rstrip("\n")       # fra stdin (aldrig fra kommandolinjen)


def cmd_user(a: argparse.Namespace) -> int:
    from .storage.db import Database
    s = settings()
    if not s.db_path.is_file():
        say(f"Databasen {s.db_path} findes ikke — tjek 'scada-tool config' (forkert data-mappe?).")
        return 1
    db = Database(s.db_path)
    try:
        return _user(a, db, s)
    finally:
        try:
            db._conn.close()
        except Exception:
            pass
        fix_owner(s)         # root må ikke efterlade scada.db-wal/-shm, som tjenesten ikke kan skrive i


def _user(a: argparse.Namespace, db: Any, s: Any) -> int:
    from .services.audit import AuditService
    from .services.auth import check_password_rules, hash_password
    from .services.errors import ServiceError
    if a.action == "list":
        for u in db.list_users():
            say(f"{u['username']:<24} {u['role']:<10} {'deaktiveret' if u.get('disabled') else 'aktiv'}")
        return 0
    user = db.get_user_ci(a.name or "")
    if not user:
        say(f"Brugeren '{a.name}' findes ikke. Se 'scada-tool user list'.")
        return 1
    try:
        pw = check_password_rules(_read_password(), user["username"])
    except ServiceError as exc:
        say(str(getattr(exc, "message", exc)))
        return 1
    res = db.update_user_guarded(user["username"], {"password_hash": hash_password(pw), "must_change_password": not a.keep,
                                                    **({"disabled": False} if a.enable else {})}, keep_admin=False)
    if res != "ok":
        say(f"Kunne ikke opdatere brugeren ({res}).")
        return 1
    db.delete_user_sessions(user["username"])
    audit(f"user reset: adgangskoden for '{user['username']}' er nulstillet")
    AuditService(db).record("scada-tool (root)", "", "user.reset_cli", user["username"], {"must_change": not a.keep})
    say(f"Adgangskoden for '{user['username']}' er nulstillet; åbne sessioner er lukket."
        + ("" if a.keep else " Brugeren skal vælge en ny ved næste login."))
    say("Er brugeren låst efter for mange forsøg, ryddes låsen ved: scada-tool restart")
    return 0


# ------------------------------------------------------------------------------------------------- config

def cmd_config(_: argparse.Namespace) -> int:
    s = settings()
    say(f"Version:        {version_of()}")
    say(f"Program:        {APP}")
    say(f"Data:           {s.data_dir}")
    say(f"Port/vært:      {s.host}:{s.port}")
    say(f"Miljøfil:       {ENVFILE}")
    try:
        for ln in ENVFILE.read_text(encoding="utf-8").splitlines():
            if ln.strip() and not ln.lstrip().startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                hide = v.strip() and (SECRET.search(k) or re.search(r"://[^/\s]*@", v))
                say(f"  {k.strip()} = " + ("(sat)" if hide else v.strip()))
    except OSError:
        say("  (kan ikke læses)")
    code, out = run(["hostname", "-I"], 5)
    if code == 0:
        say(f"Adresser:       {out}")
    code, out = run(["ss", "-ltn"], 5)
    if code == 0:
        say("Lytter på:\n" + "\n".join("  " + ln for ln in out.splitlines()[1:] if ":" in ln))
    return 0


def cmd_maint(a: argparse.Namespace) -> int:
    from . import maint
    return int(maint.main(a.args) or 0) if hasattr(maint, "main") else subprocess.call([sys.executable, "-m", "app.maint", *a.args])


# ------------------------------------------------------------------------------------------------- opbygning

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="scada-tool", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--yes", "-y", action="store_true", help="svar ja på spørgsmål (til scripts)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="overblik over serveren").set_defaults(fn=cmd_status)
    sub.add_parser("check", help="diagnose: hvorfor starter serveren ikke?").set_defaults(fn=cmd_check)
    lg = sub.add_parser("logs", help="systemloggen")
    lg.add_argument("-n", type=int, default=50)
    lg.add_argument("-f", action="store_true", help="følg løbende")
    lg.add_argument("--fejl", action="store_true", help="kun fejl")
    lg.add_argument("--tjeneste", choices=sorted(UNITS), default="scada", dest="tjeneste")
    lg.set_defaults(fn=cmd_logs)
    for name in ("start", "stop", "restart"):
        sub.add_parser(name, help=f"{name} SCADA-tjenesten").set_defaults(fn=cmd_service, action=name)
    up = sub.add_parser("update", help="opdatering")
    us = up.add_subparsers(dest="ucmd", required=True)
    us.add_parser("status").set_defaults(fn=cmd_update_status)
    rs = us.add_parser("reset", help="ryd en hængende opdatering")
    rs.add_argument("--force", action="store_true")
    rs.set_defaults(fn=cmd_update_reset)
    ap = us.add_parser("apply", help="installér en OTA-pakke fra en fil")
    ap.add_argument("file")
    ap.add_argument("--reinstall", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.set_defaults(fn=cmd_update_apply)
    us.add_parser("rollback", help="gå tilbage til forrige version").set_defaults(fn=cmd_update_rollback)
    bk = sub.add_parser("backup", help="backup af databasen")
    bk.add_argument("action", choices=("list", "create", "restore"))
    bk.add_argument("file", nargs="?")
    bk.set_defaults(fn=cmd_backup)
    us2 = sub.add_parser("user", help="brugere (nulstil adgangskode)")
    us2.add_argument("action", choices=("list", "reset"))
    us2.add_argument("name", nargs="?")
    us2.add_argument("--keep", action="store_true", help="kræv ikke ny adgangskode ved næste login")
    us2.add_argument("--enable", action="store_true", help="aktivér også brugeren, hvis den er deaktiveret")
    us2.set_defaults(fn=cmd_user)
    sub.add_parser("config", help="porte, stier, miljø (aldrig hemmeligheder)").set_defaults(fn=cmd_config)
    mt = sub.add_parser("maint", help="diskoprydning (scada-maint)")
    mt.add_argument("args", nargs=argparse.REMAINDER)
    mt.set_defaults(fn=cmd_maint)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    global ASSUME_YES
    args = build_parser().parse_args(argv)
    ASSUME_YES = bool(args.yes)
    if args.cmd == "user" and args.action == "reset" and not args.name:
        print("Angiv brugernavn: scada-tool user reset NAVN", file=sys.stderr)
        return 2
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
