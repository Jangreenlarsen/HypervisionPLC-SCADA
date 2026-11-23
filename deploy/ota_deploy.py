"""Deploy en OTA-pakke til en SCADA-server via OTA-API'et og kør konsistenskontrollen bagefter.

    SCADA_USER=<bruger> SCADA_PASS=<adgangskode> python deploy/ota_deploy.py https://scada.laces.dk [pakke.tar] [--no-audit]

Uden pakkenavn bruges scada-<version>-b<build>.tar ud fra version.json. Trin: login, upload, apply (serveren tager backup,
genstarter og ruller selv tilbage), vent til /api/health viser den nye version, og kør derefter deploy/audit_drawings.py
(kun læsning). Kun standardbiblioteket, så scriptet virker uden venv. Adgangskoden gives kun som miljøvariabel
(CLAUDE.md regel 3) og skrives aldrig ud. Returkode: 0 ok, 1 fejl, 2 login, 3 audit fandt problemer.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _call(op: urllib.request.OpenerDirector, method: str, url: str, body: bytes | None = None,
          ctype: str = "application/json", timeout: int = 300) -> dict:
    req = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": ctype})
    try:
        with op.open(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise SystemExit(f"{method} {url} -> {exc.code}: {detail}")
    return json.loads(raw) if raw else {}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        print(__doc__)
        return 1
    base = args[0].rstrip("/")
    ver = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    tar = Path(args[1]) if len(args) > 1 else ROOT / f"scada-{ver['version']}-b{ver['build']}.tar"
    if not tar.is_file():
        print(f"Pakken findes ikke: {tar} (kør sh deploy/make-package.sh)")
        return 1
    try:
        user, pw = os.environ["SCADA_USER"], os.environ["SCADA_PASS"]
    except KeyError:
        print("SCADA_USER og SCADA_PASS skal være sat som miljøvariabler")
        return 2

    op = _opener()
    try:
        _call(op, "POST", f"{base}/api/auth/login", json.dumps({"username": user, "password": pw}).encode())
    except SystemExit as exc:
        print(f"Login fejlede: {exc}")
        return 2
    info = _call(op, "POST", f"{base}/api/system/update/upload", tar.read_bytes(), "application/octet-stream")
    print(f"Uploadet: {tar.name} ({info.get('size')} bytes), sha256 {str(info.get('sha256'))[:16]}…, {info.get('relation')}")
    res = _call(op, "POST", f"{base}/api/system/update/apply",
                json.dumps({"sha256": info["sha256"], "reinstall": False}).encode())
    print("Apply:", json.dumps(res, ensure_ascii=False)[:300])

    want = f"{ver['version']}"
    for _ in range(60):  # højst ca. 2 minutter; serveren genstarter (≈5 s) og ruller selv tilbage ved fejl
        time.sleep(2)
        try:
            h = _call(_opener(), "GET", f"{base}/api/health", timeout=10)
        except (SystemExit, OSError):
            continue
        if h.get("version") == want and str(h.get("build", "")) == str(ver["build"]):
            print(f"Live: v{h['version']} b{h['build']}")
            break
    else:
        print(f"FEJL: /api/health viste ikke v{want} b{ver['build']} — serveren kan være rullet tilbage")
        return 1

    if "--no-audit" in flags:
        return 0
    py = ROOT / "backend" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    audit = subprocess.run([str(py if py.exists() else sys.executable), str(ROOT / "deploy" / "audit_drawings.py"), base],
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return 0 if audit.returncode == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
