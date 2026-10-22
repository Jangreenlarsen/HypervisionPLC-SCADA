"""DHCP-vagten (deploy/net-watchdog.sh) med en falsk nmcli, samt validering/tilstand for 'fast IP efter N fejl'."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.services import netconfig
from app.services.errors import ServiceError

SH = shutil.which("sh")
SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "net-watchdog.sh"
needs_sh = pytest.mark.skipif(SH is None, reason="sh findes ikke")

FAKE_NMCLI = """#!/bin/sh
echo "$@" >> "$FAKE_LOG"
case "$*" in
  *"GENERAL.STATE device show"*) echo "${FAKE_STATE:-100 (connected)}" ;;
  *"DHCP4.OPTION device show"*) [ -f "$FAKE_LEASE" ] && echo "dhcp_lease_time = 86400" ;;
  *) ;;
esac
exit 0
"""


@pytest.fixture
def box(tmp_path):
    (tmp_path / "state").mkdir()
    fake = tmp_path / "fake-nmcli"
    fake.write_text(FAKE_NMCLI, newline="\n")
    fake.chmod(0o755)
    env = {**os.environ, "STATE": str(tmp_path / "state"), "NMCLI": str(fake), "FAKE_LOG": str(tmp_path / "nmcli.log"),
           "FAKE_LEASE": str(tmp_path / "lease")}
    return tmp_path, env


def conf(tmp, mode="dhcp_fallback", n=3):
    (tmp / "state" / "watchdog.conf").write_text(
        f"MODE={mode}\nIFACE=eth0\nUUID=1111-2222\nIP=192.168.100.10\nPREFIX=24\nGATEWAY=192.168.100.1\nFALLBACK_AFTER={n}\n", newline="\n")


def tick(env):
    subprocess.run([SH, str(SCRIPT)], env=env, check=False, timeout=30)


def out(tmp):
    return json.loads((tmp / "state" / "watchdog.json").read_text(encoding="utf-8"))


def mods(tmp):
    p = tmp / "nmcli.log"
    return [c for c in (p.read_text().splitlines() if p.exists() else []) if "connection modify" in c]


@needs_sh
def test_uden_konfiguration_goer_den_intet(box):
    tmp, env = box
    tick(env)
    assert not (tmp / "nmcli.log").exists() and not (tmp / "state" / "watchdog.json").exists()


@needs_sh
def test_fast_ip_er_ikke_foerer_dhcp(box):
    tmp, env = box
    conf(tmp, "static")
    tick(env)
    assert out(tmp)["state"] == "idle" and mods(tmp) == []


@needs_sh
def test_reserve_ip_foerst_efter_n_kontroller_uden_dhcp_svar(box):
    tmp, env = box
    conf(tmp, n=3)
    for i in (1, 2):
        tick(env)
        assert out(tmp)["state"] == "searching" and out(tmp)["fails"] == i and mods(tmp) == []
    tick(env)                                   # 3. kontrol uden svar → reserve-IP
    m = mods(tmp)
    assert len(m) == 1 and "--temporary" in m[0] and "ipv4.addresses 192.168.100.10/24" in m[0] and "ipv4.gateway 192.168.100.1" in m[0]
    assert out(tmp)["state"] == "fallback" and out(tmp)["fallback_active"] is True
    assert any("device reapply" in c for c in (tmp / "nmcli.log").read_text().splitlines())
    tick(env)                                   # lægges ikke på igen
    assert len(mods(tmp)) == 1


@needs_sh
def test_reserve_ip_fjernes_naar_dhcp_svarer_igen(box):
    tmp, env = box
    conf(tmp, n=1)
    tick(env)
    assert out(tmp)["fallback_active"] is True
    (tmp / "lease").write_text("x")
    tick(env)
    m = mods(tmp)
    assert len(m) == 2 and 'ipv4.addresses  ipv4.gateway' in m[1] and "--temporary" in m[1]
    st = out(tmp)
    assert st["state"] == "ok" and st["fallback_active"] is False and st["fails"] == 0


@needs_sh
def test_dhcp_uden_reserve_taeller_men_aendrer_intet(box):
    tmp, env = box
    conf(tmp, "dhcp", n=1)
    for _ in range(4):
        tick(env)
    assert out(tmp)["fails"] == 4 and mods(tmp) == []
    conf(tmp, "dhcp_static", n=1)
    tick(env)
    assert mods(tmp) == []


@needs_sh
def test_et_enkelt_dhcp_svar_nulstiller_taelleren(box):
    tmp, env = box
    conf(tmp, n=3)
    tick(env); tick(env)
    (tmp / "lease").write_text("x")
    tick(env)
    (tmp / "lease").unlink()
    tick(env)
    assert out(tmp)["fails"] == 1 and mods(tmp) == []


@needs_sh
def test_taeller_ikke_naar_kablet_er_ude(box):
    tmp, env = box
    conf(tmp, n=1)
    env["FAKE_STATE"] = "20 (unavailable)"
    for _ in range(3):
        tick(env)
    assert out(tmp)["state"] == "nolink" and mods(tmp) == []


@needs_sh
def test_roerer_ikke_netvaerket_mens_en_aendring_er_i_gang(box):
    tmp, env = box
    conf(tmp, n=1)
    (tmp / "state" / "status.json").write_text(json.dumps({"state": "waiting_confirm", "ts": 1}))
    tick(env)
    assert not (tmp / "nmcli.log").exists()


@needs_sh
def test_ugyldig_konfiguration_afvises(box):
    tmp, env = box
    (tmp / "state" / "watchdog.conf").write_text("MODE=dhcp_fallback\nIFACE=eth0;reboot\nUUID=1\nFALLBACK_AFTER=1\n")
    tick(env)
    assert not (tmp / "nmcli.log").exists()


# ---------------------------------------------------------------- backend
STATIC = {"interface": "eth0", "mode": "dhcp_fallback", "ip": "192.168.100.10", "prefix": 24, "gateway": "192.168.100.1",
          "dns": [], "hostname": "", "fallback_after": 5}


def test_validering_af_dhcp_med_reserve_ip():
    cfg = netconfig.validate_network(STATIC, ["eth0"])
    assert cfg["fallback_after"] == 5 and cfg["ip"] == "192.168.100.10" and cfg["gateway"] == "192.168.100.1"
    assert netconfig.validate_network({k: v for k, v in STATIC.items() if k != "fallback_after"}, ["eth0"])["fallback_after"] == 5
    for bad in (0, 21, "5", True, None):
        with pytest.raises(ServiceError, match="Reserve-IP"):
            netconfig.validate_network({**STATIC, "fallback_after": bad}, ["eth0"])
    with pytest.raises(ServiceError, match="IP-adresse"):
        netconfig.validate_network({**STATIC, "ip": ""}, ["eth0"])      # reserve-IP'en skal angives


def test_request_indeholder_fallback_after():
    text = netconfig.build_request(netconfig.validate_network(STATIC, ["eth0"]), "admin", "1")
    assert "FALLBACK_AFTER=5" in text.splitlines() and "MODE=dhcp_fallback" in text.splitlines()


def test_aarsag_til_at_netvaerk_ikke_er_aktiveret(tmp_path):
    svc = netconfig.NetworkService(tmp_path, tmp_path / "state")
    assert svc.disabled_reason() == "not_installed" and svc.status()["disabled_reason"] == "not_installed"
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "no-nmcli").write_text("")
    assert svc.disabled_reason() == "no_nmcli"
    (tmp_path / "state" / "enabled").write_text("")
    assert svc.disabled_reason() == "" and svc.status()["enabled"] is True


def test_vagtens_status_vises_og_foraeldes(tmp_path):
    import time

    svc = netconfig.NetworkService(tmp_path, tmp_path / "state")
    (tmp_path / "state").mkdir()
    assert svc.status()["watchdog"] is None
    (tmp_path / "state" / "watchdog.json").write_text(json.dumps({"state": "searching", "fails": 2, "ts": time.time()}))
    assert svc.status()["watchdog"]["fails"] == 2 and "stale" not in svc.status()["watchdog"]
    (tmp_path / "state" / "watchdog.json").write_text(json.dumps({"state": "ok", "ts": time.time() - 3600}))
    assert svc.status()["watchdog"]["stale"] is True
