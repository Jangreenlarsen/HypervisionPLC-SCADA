"""Bump version.json efter CLAUDE.md regel 1 og print den nye version.

    python deploy/bump_version.py build   # kodeændring uden bugfix/feature: build +1
    python deploy/bump_version.py patch   # bugfix: PATCH +1 (build +1)
    python deploy/bump_version.py minor   # feature: MINOR +1, PATCH=0 (build +1)
    python deploy/bump_version.py major   # breaking: MAJOR +1, MINOR=PATCH=0 (build +1)

Build tælles altid op (+1, fire cifre) og nulstilles aldrig. Debug-serien (X.Y.Z.D) bumpes ikke her.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "version.json"


def main() -> int:
    kind = sys.argv[1] if len(sys.argv) > 1 else ""
    if kind not in ("build", "patch", "minor", "major"):
        print(__doc__)
        return 1
    data = json.loads(FILE.read_text(encoding="utf-8"))
    major, minor, patch = (int(x) for x in data["version"].split("."))
    if kind == "patch":
        patch += 1
    elif kind == "minor":
        minor, patch = minor + 1, 0
    elif kind == "major":
        major, minor, patch = major + 1, 0, 0
    version, build = f"{major}.{minor}.{patch}", f"{int(data['build']) + 1:04d}"
    FILE.write_text('{ "version": "%s", "build": "%s" }\n' % (version, build), encoding="utf-8", newline="\n")
    print(f"{version} build {build}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
