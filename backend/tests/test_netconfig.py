"""Netværksopsætning: validering, anmodning/bekræftelse og selve hjælpescriptet (med en falsk nmcli)."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import netconfig
from app.services import sysconfig as netconfig_sys
from app.services.errors import ServiceError

ADMIN_PW = "test-admin-pw-1"
STATIC = {"interface": "eth0", "mode": "static", "ip": "10.1.1.50", "prefix": 24, "gateway": "10.1.1.1",
          "dns": ["10.1.1.1", "8.8.8.8"], "hostname": "Scada-1"}


def bad(**kw):
    with pytest.raises(ServiceError) as e:
        netconfig.validate_network({**STATIC, **kw}, ["eth0"])
    assert e.value.status == 400
    return e.value.message


def test_gyldig_opsaetning_normaliseres():
    cfg = netconfig.validate_network(STATIC, ["eth0"])
    assert cfg["ip"] == "10.1.1.50" and cfg["prefix"] == 24 and cfg["hostname"] == "scada-1" and cfg["dns"] == ["10.1.1.1", "8.8.8.8"]


def test_dhcp_kraever_ingen_adresser():
    cfg = netconfig.validate_network({"interface": "eth0", "mode": "dhcp"}, ["eth0"])
    assert cfg["mode"] == "dhcp" and cfg["ip"] == ""


def test_afviser_forkerte_vaerdier_med_specifik_besked():
    assert "Netkort" in bad(interface="wlan9")
    assert "Netkort" in bad(interface="eth0; reboot")
    assert "Tilstand" in bad(mode="magic")
    assert "IP-adresse" in bad(ip="10.1.1")
    assert "IP-adresse" in bad(ip="")
    assert "IP-adresse" in bad(ip="300.1.1.1")
    assert "IP-adresse" in bad(ip="127.0.0.1")
    assert "IP-adresse" in bad(ip="0.0.0.0")
    assert "broadcast" in bad(ip="10.1.1.255")
    assert "Subnet" in bad(prefix=31)
    assert "Subnet" in bad(prefix=4)
    assert "Subnet" in bad(prefix="24")
    assert "subnettet" in bad(gateway="192.168.0.1")
    assert "samme" in bad(gateway="10.1.1.50")
    assert "DNS" in bad(dns=["x"])
    assert "DNS" in bad(dns=["1.1.1.1"] * 4)
    assert "Værtsnavn" in bad(hostname="-abc")
    assert "Værtsnavn" in bad(hostname="a b")
    assert "Værtsnavn" in bad(hostname="a" * 64)


def test_gateway_er_valgfri_ved_fast_ip_og_ignoreres_ved_dhcp_plus_fast():
    assert netconfig.validate_network({**STATIC, "gateway": ""}, ["eth0"])["gateway"] == ""
    assert netconfig.validate_network({**STATIC, "mode": "dhcp_static"}, ["eth0"])["gateway"] == ""


def test_request_indeholder_kun_sikre_tegn():
    cfg = netconfig.validate_network(STATIC, ["eth0"])
    text = netconfig.build_request(cfg, 'adm\nin;rm -rf"', "123")
    assert all("\n" not in line and ";" not in line and " " not in line and '"' not in line for line in text.splitlines())
    assert "BY=adminrm-rf" in text.splitlines()
    assert "IP=10.1.1.50" in text and "DNS=10.1.1.1,8.8.8.8" in text and "CONFIRM_S=90" in text


def make_service(tmp_path, enabled=True):
    state = tmp_path / "state"
    state.mkdir()
    if enabled:
        (state / "enabled").write_text("")
    (tmp_path / "config").mkdir()
    return netconfig.NetworkService(tmp_path, state), state


def test_kraever_at_hjaelperen_er_installeret(tmp_path):
    svc, _ = make_service(tmp_path, enabled=False)
    with pytest.raises(ServiceError, match="ikke aktiveret"):
        svc.request_apply(netconfig.validate_network(STATIC, ["eth0"]), "admin")


def test_tilstandsmaskine_bekraeft_kun_naar_der_venter(tmp_path):
    svc, state = make_service(tmp_path)
    cfg = netconfig.validate_network(STATIC, ["eth0"])
    st = svc.request_apply(cfg, "admin")
    assert st["state"] == "queued" and (tmp_path / "config" / "network.request").exists() and st["target"]["ip"] == "10.1.1.50"
    with pytest.raises(ServiceError, match="allerede i gang"):
        svc.request_apply(cfg, "admin")
    with pytest.raises(ServiceError, match="venter på bekræftelse"):
        svc.confirm()
    (state / "status.json").write_text(json.dumps(
        {"state": "waiting_confirm", "message": "x", "deadline": time.time() + 60, "ts": time.time()}))
    (tmp_path / "config" / "network.request").unlink()
    assert svc.status()["busy"] is True
    svc.confirm()
    assert (tmp_path / "config" / "network.confirm").exists()
    assert svc.saved() is None      # huskes først, når hjælperen selv melder "confirmed" (ikke ved et race med fristen)
    (state / "status.json").write_text(json.dumps({"state": "confirmed", "ts": time.time()}))
    assert svc.status()["saved"]["ip"] == "10.1.1.50"


def test_udloebet_frist_giver_stalled_og_gemmer_ikke(tmp_path):
    svc, state = make_service(tmp_path)
    svc.request_apply(netconfig.validate_network(STATIC, ["eth0"]), "admin")
    (tmp_path / "config" / "network.request").unlink()
    (state / "status.json").write_text(json.dumps({"state": "reverted", "ts": time.time()}))
    assert svc.status()["saved"] is None


def test_haengt_anmodning_giver_stalled(tmp_path):
    svc, state = make_service(tmp_path)
    (state / "status.json").write_text(json.dumps({"state": "applying", "ts": time.time() - 3600}))
    assert svc.status()["state"] == "stalled"
    (state / "status.json").write_text(json.dumps({"state": "idle", "ts": time.time()}))
    req = tmp_path / "config" / "network.request"
    req.write_text("x")
    os.utime(req, (time.time() - 3600, time.time() - 3600))
    assert svc.status()["state"] == "stalled"


def test_api_kun_admin_og_validering(tmp_path, monkeypatch):
    # Uafhængig af maskinen: netkortene er altid eth0 (på Linux ville `ip` ellers give maskinens rigtige netkort)
    monkeypatch.setattr(netconfig_sys, "network_status", lambda: {"available": True, "hostname": "t", "gateway": "", "dns": [],
                                                                  "error": "", "interfaces": [{"name": "eth0", "mac": "", "state": "up", "addresses": []}]})
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0,
                        net_state_dir=tmp_path / "state")
    with TestClient(create_app(settings)) as c:
        assert c.put("/api/system/config/network", json=STATIC).status_code in (401, 403)
        assert c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW}).status_code == 200
        r = c.put("/api/system/config/network", json={**STATIC, "ip": "nej"})
        assert r.status_code == 400 and "IP-adresse" in r.json()["error"]
        r = c.put("/api/system/config/network", json=STATIC)       # hjælperen er ikke installeret her
        assert r.status_code in (400, 409)
        assert c.post("/api/system/config/network/confirm").status_code == 409
        assert c.get("/api/system/config/network").json()["state"] == "idle"
        assert "network_config" in c.get("/api/system/config").json()



def test_api_accepts_exactly_what_the_frontend_sends_in_every_mode(tmp_path, monkeypatch):
    """Regression (v1.8.2): siden sender altid `fallback_after`; API-modellen kendte det ikke ("fallback_after: ukendt felt"), så INTET
    skift (fx til fast IP) kunne anvendes fra web siden v0.123.0. Testen bruger hjælperen som installeret og frontendens fulde body."""
    monkeypatch.setattr(netconfig_sys, "network_status", lambda: {"available": True, "hostname": "t", "gateway": "", "dns": [],
                                                                  "error": "", "interfaces": [{"name": "eth0", "mac": "", "state": "up", "addresses": []}]})
    state = tmp_path / "state"
    state.mkdir()
    (state / "enabled").write_text("")
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0, net_state_dir=state)
    base = {"interface": "eth0", "mode": "static", "ip": "10.1.1.31", "prefix": 24, "gateway": "10.1.1.1", "dns": ["10.1.1.17"],
            "hostname": "HypervisionSCADA", "fallback_after": 5}
    req = tmp_path / "config" / "network.request"
    with TestClient(create_app(settings)) as c:
        assert c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW}).status_code == 200
        for body in (base, {**base, "mode": "dhcp", "ip": "", "prefix": 0, "gateway": ""},
                     {**base, "mode": "dhcp_static", "gateway": ""}, {**base, "mode": "dhcp_fallback", "fallback_after": 8}):
            req.unlink(missing_ok=True)
            (state / "status.json").unlink(missing_ok=True)
            r = c.put("/api/system/config/network", json=body)
            assert r.status_code == 200, (body["mode"], r.text)
            assert req.exists() and f"MODE={body['mode']}" in req.read_text(encoding="utf-8")
        assert "FALLBACK_AFTER=8" in req.read_text(encoding="utf-8")
        # ukendte felter afvises stadig
        assert c.put("/api/system/config/network", json={**base, "uventet": 1}).status_code == 422


# ---------------------------------------------------------------- hjælpescriptet med en falsk nmcli
SH = shutil.which("sh")
SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "apply-config.sh"

FAKE_NMCLI = """#!/bin/sh
echo "$@" >> "$FAKE_LOG"
case "$*" in
  *"GENERAL.CONNECTION device show"*) echo "Wired connection 1" ;;
  *"connection.uuid connection show"*) echo "1111-2222" ;;
  *"connection modify"*) [ -n "${FAKE_FAIL_MODIFY:-}" ] && exit 1 ;;
  *"connection up"*) [ -n "${FAKE_FAIL_UP:-}" ] && [ ! -f "$FAKE_LOG.reloaded" ] && exit 1 ;;
  *"connection reload"*) : > "$FAKE_LOG.reloaded" ;;
  *) ;;
esac
exit 0
"""

needs_sh = pytest.mark.skipif(SH is None, reason="sh findes ikke")


@pytest.fixture
def sandbox(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "state").mkdir()
    fake = tmp_path / "fake-nmcli"
    fake.write_text(FAKE_NMCLI, newline="\n")
    fake.chmod(0o755)
    hc = tmp_path / "fake-hostnamectl"
    hc.write_text('#!/bin/sh\necho "hostnamectl $@" >> "$FAKE_LOG"\nexit 0\n', newline="\n")
    hc.chmod(0o755)
    env = {**os.environ, "DATA": str(tmp_path), "STATE": str(tmp_path / "state"), "NMCLI": str(fake), "HOSTNAMECTL": str(hc),
           "FAKE_LOG": str(tmp_path / "nmcli.log")}
    return tmp_path, env


def request(tmp, **kw):
    v = {"ID": "1", "BY": "admin", "CONFIRM_S": "20", "IFACE": "eth0", "MODE": "static", "IP": "10.1.1.50", "PREFIX": "24",
         "GATEWAY": "10.1.1.1", "DNS": "10.1.1.1", "HOSTNAME": "", **kw}
    (tmp / "config" / "network.request").write_text("".join(f"{k}={x}\n" for k, x in v.items()), newline="\n")


def status(tmp):
    return json.loads((tmp / "state" / "status.json").read_text(encoding="utf-8"))


def calls(tmp):
    p = tmp / "nmcli.log"
    return p.read_text().splitlines() if p.exists() else []


def run(env, timeout=60):
    subprocess.run([SH, str(SCRIPT)], env=env, check=False, timeout=timeout)


def wait_for_state(tmp, state):
    for _ in range(200):
        try:
            if status(tmp)["state"] == state:
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise AssertionError(f"tilstanden {state} blev aldrig nået")


@needs_sh
def test_script_afviser_ugyldigt_input_uden_at_roere_nmcli(sandbox):
    tmp, env = sandbox
    for kw in ({"IP": "10.1.1.999"}, {"IP": ""}, {"IFACE": "eth0;reboot"}, {"DNS": "1.1.1.1;reboot"}, {"PREFIX": "0"},
               {"PREFIX": "31"}, {"MODE": "magic"}, {"HOSTNAME": "-x"}):
        request(tmp, **kw)
        run(env, 30)
        assert status(tmp)["state"] == "failed", kw
    assert calls(tmp) == []
    assert not (tmp / "config" / "network.request").exists()


@needs_sh
def test_script_bekraeftet_goer_aendringen_varig_foerst_efter_bekraeftelsen(sandbox):
    tmp, env = sandbox
    request(tmp, HOSTNAME="scada-1")
    p = subprocess.Popen([SH, str(SCRIPT)], env=env)
    wait_for_state(tmp, "waiting_confirm")
    before = calls(tmp)
    mods = [c for c in before if "connection modify" in c]
    assert len(mods) == 1 and "--temporary" in mods[0]            # midlertidig mens der ventes
    assert not any("hostnamectl" in c for c in before)            # værtsnavn først efter bekræftelse
    (tmp / "config" / "network.confirm").write_text("ok")
    p.wait(timeout=30)
    assert status(tmp)["state"] == "confirmed"
    after = calls(tmp)
    mods = [c for c in after if "connection modify" in c]
    assert len(mods) == 2 and "--temporary" not in mods[1]        # varig ændring efter bekræftelse
    assert "ipv4.method manual" in mods[1] and "ipv4.addresses 10.1.1.50/24" in mods[1] and "ipv4.gateway 10.1.1.1" in mods[1]
    assert any("hostnamectl set-hostname scada-1" in c for c in after)


@needs_sh
def test_script_gendanner_ved_fortryd_uden_varig_aendring(sandbox):
    tmp, env = sandbox
    request(tmp)
    p = subprocess.Popen([SH, str(SCRIPT)], env=env)
    wait_for_state(tmp, "waiting_confirm")
    (tmp / "config" / "network.revert").write_text("ok")
    p.wait(timeout=30)
    assert status(tmp)["state"] == "reverted"
    log = calls(tmp)
    assert any("connection reload" in c for c in log)
    assert len([c for c in log if "connection modify" in c]) == 1     # kun den midlertidige — intet blev gemt varigt


@needs_sh
def test_script_gendanner_hvis_der_ikke_bekraeftes(sandbox):
    tmp, env = sandbox
    request(tmp, CONFIRM_S="20")      # mindsteværdien
    run(env, 90)
    assert status(tmp)["state"] == "reverted" and "Ingen bekræftelse" in status(tmp)["message"]
    assert any("connection reload" in c for c in calls(tmp))
    assert len([c for c in calls(tmp) if "connection modify" in c]) == 1


@needs_sh
def test_script_confirm_s_begraenses_og_oktalfaelden_undgaas(sandbox):
    tmp, env = sandbox
    for raw, expected in (("999", 180), ("090", 90), ("5", 20)):
        request(tmp, CONFIRM_S=raw)
        p = subprocess.Popen([SH, str(SCRIPT)], env=env)
        wait_for_state(tmp, "waiting_confirm")
        st = status(tmp)
        assert abs((st["deadline"] - st["ts"]) - expected) <= 2, (raw, st)
        (tmp / "config" / "network.revert").write_text("ok")
        p.wait(timeout=30)
        assert status(tmp)["state"] == "reverted"
        (tmp / "nmcli.log").unlink()


@needs_sh
def test_script_gendanner_hvis_nmcli_afviser(sandbox):
    tmp, env = sandbox
    env["FAKE_FAIL_MODIFY"] = "1"
    request(tmp)
    run(env, 30)
    assert status(tmp)["state"] == "failed" and "gendannet" in status(tmp)["message"]
    assert any("connection reload" in c for c in calls(tmp))


@needs_sh
def test_script_gendanner_hvis_netkortet_ikke_kommer_op(sandbox):
    tmp, env = sandbox
    env["FAKE_FAIL_UP"] = "1"
    request(tmp)
    run(env, 30)
    assert status(tmp)["state"] == "failed" and "gendannet" in status(tmp)["message"]
    assert any("connection reload" in c for c in calls(tmp))


@needs_sh
def test_script_dhcp_plus_fast_ip_bruger_ingen_gateway_og_uendelig_dhcp(sandbox):
    tmp, env = sandbox
    request(tmp, MODE="dhcp_static", GATEWAY="10.1.1.1")
    p = subprocess.Popen([SH, str(SCRIPT)], env=env)
    wait_for_state(tmp, "waiting_confirm")
    mod = [c for c in calls(tmp) if "connection modify" in c][0]
    (tmp / "config" / "network.revert").write_text("ok")
    p.wait(timeout=30)
    assert "ipv4.method auto" in mod and "ipv4.addresses 10.1.1.50/24" in mod
    assert "ipv4.dhcp-timeout 2147483647" in mod
    assert "ipv4.gateway  ipv4.may-fail yes" in mod      # gatewayen sendes som tom parameter — DHCP leverer den


@needs_sh
def test_script_filtrerer_by_i_status(sandbox):
    tmp, env = sandbox
    request(tmp, BY='ad"min","state":"confirmed', IP="x")
    run(env, 30)
    st = status(tmp)
    assert st["state"] == "failed" and '"' not in st["by"]


@needs_sh
def test_script_afviser_symlink_som_anmodning(sandbox):
    tmp, env = sandbox
    target = tmp / "hemmelig.txt"
    target.write_text("IFACE=eth0\n")
    try:
        (tmp / "config" / "network.request").symlink_to(target)
    except OSError:
        pytest.skip("symlinks kan ikke oprettes her")
    run(env, 30)
    assert status(tmp)["state"] == "failed"
    assert calls(tmp) == []
    assert target.read_text() == "IFACE=eth0\n"


@needs_sh
def test_script_recover_gendanner_efter_afbrudt_aendring(sandbox):
    tmp, env = sandbox
    (tmp / "state" / "status.json").write_text(json.dumps({"state": "waiting_confirm", "deadline": 1, "ts": 1}))
    subprocess.run([SH, str(SCRIPT), "--recover"], env=env, check=False, timeout=30)
    assert status(tmp)["state"] == "reverted"
    assert any("connection reload" in c for c in calls(tmp))
    (tmp / "nmcli.log").unlink()
    (tmp / "state" / "status.json").write_text(json.dumps({"state": "confirmed", "ts": 1}))
    subprocess.run([SH, str(SCRIPT), "--recover"], env=env, check=False, timeout=30)
    assert status(tmp)["state"] == "confirmed" and calls(tmp) == []     # rører ikke en afsluttet ændring


@needs_sh
def test_script_skriver_vagtens_konfiguration_foerst_efter_bekraeftelse(sandbox):
    tmp, env = sandbox
    request(tmp, MODE="dhcp_fallback", FALLBACK_AFTER="7", IP="192.168.100.10", GATEWAY="192.168.100.1")
    p = subprocess.Popen([SH, str(SCRIPT)], env=env)
    wait_for_state(tmp, "waiting_confirm")
    assert not (tmp / "state" / "watchdog.conf").exists()
    mod = [c for c in calls(tmp) if "connection modify" in c][0]
    assert "ipv4.method auto" in mod and 'ipv4.addresses ' in mod and "192.168.100.10" not in mod   # profilen er ren DHCP
    (tmp / "config" / "network.confirm").write_text("ok")
    p.wait(timeout=30)
    conf = (tmp / "state" / "watchdog.conf").read_text()
    assert "MODE=dhcp_fallback" in conf and "FALLBACK_AFTER=7" in conf and "IP=192.168.100.10" in conf and "UUID=1111-2222" in conf


@needs_sh
def test_script_afvist_aendring_roerer_ikke_vagtens_konfiguration(sandbox):
    tmp, env = sandbox
    (tmp / "state" / "watchdog.conf").write_text("MODE=dhcp\n")
    request(tmp)
    p = subprocess.Popen([SH, str(SCRIPT)], env=env)
    wait_for_state(tmp, "waiting_confirm")
    (tmp / "config" / "network.revert").write_text("ok")
    p.wait(timeout=30)
    assert (tmp / "state" / "watchdog.conf").read_text() == "MODE=dhcp\n"
