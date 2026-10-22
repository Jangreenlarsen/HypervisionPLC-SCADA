"""deploy/net-detect.sh: finder netværkssystem og DHCP-klient (med falske kommandoer) og holder capabilities opdateret."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SH = shutil.which("sh")
SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "net-detect.sh"
needs_sh = pytest.mark.skipif(SH is None, reason="sh findes ikke")


def fake(bin_dir, name, body="exit 0"):
    p = bin_dir / name
    p.write_text(f"#!/bin/sh\n{body}\n", newline="\n")
    p.chmod(0o755)


def detect(tmp, commands, nm_active=False, interfaces=True):
    bin_dir = tmp / "bin"
    bin_dir.mkdir(exist_ok=True)
    for c in list(bin_dir.iterdir()):
        c.unlink()
    for c in commands:
        fake(bin_dir, c)
    fake(bin_dir, "systemctl", "exit 0" if nm_active else "exit 3")
    # Linux: kun de nødvendige systemværktøjer (symlinks) — så maskinens egne nmcli/ifup/dhcpcd aldrig kan skinne igennem.
    # Windows (Git Bash): værktøjerne kræver deres DLL'er, så den almindelige søgesti bruges (kun lokal udvikling).
    if os.name == "nt":
        posix = bin_dir.as_posix()
        posix = "/" + posix[0].lower() + posix[2:] if posix[1:2] == ":" else posix      # C:/x → /c/x (kolon er skilletegn i PATH)
        search = f"{posix}:/usr/bin"
    else:
        tools = tmp / "tools"
        tools.mkdir(exist_ok=True)
        for c in ("cat", "mkdir", "chmod", "mv", "rm"):
            if not (tools / c).exists():
                (tools / c).symlink_to(shutil.which(c))
        search = f"{bin_dir}:{tools}"
    iffile = tmp / "interfaces"
    if interfaces:
        iffile.write_text("auto lo\n")
    elif iffile.exists():
        iffile.unlink()
    env = {**os.environ, "STATE": str(tmp / "state"), "IFFILE": str(iffile), "NETDETECT_PATH": search}
    subprocess.run([SH, str(SCRIPT)], env=env, check=True, timeout=30, capture_output=True)
    st = tmp / "state"
    return (st / "capabilities").read_text(), (st / "enabled").exists(), (st / "no-backend").exists()


@needs_sh
def test_networkmanager_har_sin_egen_dhcp_klient(tmp_path):
    caps, enabled, none = detect(tmp_path, ["nmcli"], nm_active=True)
    assert "backend=nm" in caps and "dhcp=1" in caps and enabled and not none


@needs_sh
def test_ifupdown_uden_dhcpcd_har_ingen_dhcp(tmp_path):
    caps, enabled, none = detect(tmp_path, ["ifup", "ifdown", "dhclient", "udhcpc"])
    assert "backend=ifupdown" in caps and "dhcp=0" in caps and enabled and not none      # dhclient/udhcpc godkendes ikke


@needs_sh
def test_ifupdown_med_dhcpcd_og_opdatering_naar_den_installeres_senere(tmp_path):
    caps, *_ = detect(tmp_path, ["ifup", "ifdown"])
    assert "dhcp=0" in caps
    caps, enabled, none = detect(tmp_path, ["ifup", "ifdown", "dhcpcd"])          # "apt install dhcpcd-base" bagefter
    assert "backend=ifupdown" in caps and "dhcp=1" in caps and enabled


@needs_sh
def test_networkmanager_der_ikke_kører_giver_ifupdown_eller_intet(tmp_path):
    caps, *_ = detect(tmp_path, ["nmcli", "ifup", "ifdown"], nm_active=False)
    assert "backend=ifupdown" in caps
    caps, enabled, none = detect(tmp_path, ["nmcli"], nm_active=False, interfaces=False)
    assert "backend=none" in caps and not enabled and none


@needs_sh
def test_ingen_ifup_uden_interfaces_fil_er_ingen_backend(tmp_path):
    caps, enabled, none = detect(tmp_path, ["ifup", "ifdown"], interfaces=False)
    assert "backend=none" in caps and none and not enabled
