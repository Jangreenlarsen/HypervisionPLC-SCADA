"""Pi-strømstatus: deploy/power-info.sh (root-hjælper → <state>/power.json) og aflæsningen i health.py (read_throttled)."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from app.services.health import POWER_FRESH_S, read_throttled

SH = shutil.which("sh")
SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "power-info.sh"
needs_sh = pytest.mark.skipif(SH is None, reason="sh findes ikke")


def fake_vcgencmd(tmp_path, output, code=0):
    f = tmp_path / "fake-vcgencmd"
    f.write_text(f"#!/bin/sh\necho '{output}'\nexit {code}\n", newline="\n")
    f.chmod(0o755)
    return f


def run(tmp_path, vcgencmd):
    env = {**os.environ, "STATE": str(tmp_path / "state"), "VCGENCMD": str(vcgencmd)}
    return subprocess.run([SH, str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30)


def power(tmp_path):
    return json.loads((tmp_path / "state" / "power.json").read_text())


@needs_sh
@pytest.mark.parametrize("output, value", [("throttled=0x50005", 0x50005), ("throttled=0x0", 0), ("throttled=0xdeadbeef", 0xDEADBEEF),
                                           ("throttled=0x20000", 0x20000)])
def test_script_writes_the_flags_as_a_number(tmp_path, output, value):
    r = run(tmp_path, fake_vcgencmd(tmp_path, output))
    assert r.returncode == 0, r.stderr
    p = power(tmp_path)
    assert p["throttled"] == value and abs(p["ts"] - time.time()) < 30
    assert not list((tmp_path / "state").glob("*.tmp"))


@needs_sh
@pytest.mark.parametrize("output", ["", "error=1", "throttled=0xZZ", "throttled=50005", "throttled=0x50005; reboot", "throttled=0x123456789"])
def test_script_ignores_unexpected_output(tmp_path, output):
    r = run(tmp_path, fake_vcgencmd(tmp_path, output))
    assert r.returncode == 0 and not (tmp_path / "state" / "power.json").exists()


@needs_sh
def test_script_ignores_a_failing_vcgencmd(tmp_path):
    r = run(tmp_path, fake_vcgencmd(tmp_path, "throttled=0x50005", code=1))
    assert r.returncode == 0 and not (tmp_path / "state" / "power.json").exists()


@needs_sh
def test_script_removes_an_old_file_when_this_is_not_a_pi(tmp_path):
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "power.json").write_text('{"throttled":1,"ts":1}')
    r = run(tmp_path, tmp_path / "findes-ikke-vcgencmd")
    assert r.returncode == 0 and not (tmp_path / "state" / "power.json").exists()


# ------------------------------------------------------------------ aflæsningen

def write_power(state, throttled, ts):
    state.mkdir(exist_ok=True)
    (state / "power.json").write_text(json.dumps({"throttled": throttled, "ts": ts}))


def test_read_throttled_decodes_the_fresh_file(tmp_path):
    now = 1_000_000.0
    write_power(tmp_path, 0x50005, now - 10)
    r = read_throttled(tmp_path, now)
    assert r == {"now": ["undervoltage", "throttlet"], "past": ["undervoltage", "har været throttlet"]}


def test_read_throttled_zero_means_all_fine_not_unknown(tmp_path):
    write_power(tmp_path, 0, 100.0)
    assert read_throttled(tmp_path, 110.0) == {"now": [], "past": []}


def test_read_throttled_stale_or_invalid_file_is_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.read_text", _only_power_file(Path.read_text))   # sysfs-stien findes ikke her
    write_power(tmp_path, 0x50005, 100.0)
    assert read_throttled(tmp_path, 100.0 + POWER_FRESH_S + 1) is None                 # for gammel
    for bad in ("ikke json", "{}", '{"throttled": "x", "ts": 1}', '{"throttled": 1}', "[]"):
        (tmp_path / "power.json").write_text(bad)
        assert read_throttled(tmp_path, 100.0) is None, bad
    assert read_throttled(tmp_path / "findes-ikke", 100.0) is None
    assert read_throttled(None, 100.0) is None


def _only_power_file(real):
    def read_text(self, *a, **kw):
        if "get_throttled" in str(self):
            raise FileNotFoundError(str(self))
        return real(self, *a, **kw)
    return read_text
