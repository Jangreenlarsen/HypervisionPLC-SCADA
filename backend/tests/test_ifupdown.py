"""ifupdown-backenden (Debian/Ubuntu-servere, ESXi-VM'er): apply-config.sh og net-watchdog.sh med falske ifup/ifdown/ip."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

SH = shutil.which("sh")
DEPLOY = Path(__file__).resolve().parents[2] / "deploy"
APPLY = DEPLOY / "apply-config.sh"
WATCH = DEPLOY / "net-watchdog.sh"
needs_sh = pytest.mark.skipif(SH is None, reason="sh findes ikke")

INTERFACES = """# This file describes the network interfaces available on your system
source /etc/network/interfaces.d/*

# The loopback network interface
auto lo
iface lo inet loopback

# The primary network interface (fast IP)
auto ens3
iface ens3 inet static
    address 10.1.1.31/24
    gateway 10.1.1.1

auto ens4
iface ens4 inet dhcp
"""

FAKE_IFUP = """#!/bin/sh
echo "$(basename "$0") $@" >> "$FAKE_LOG"
case "$*" in *interfaces.new*) [ "$(basename "$0")" = fake-ifup ] && [ -n "${FAKE_FAIL_IFUP:-}" ] && exit 1 ;; esac
exit 0
"""
FAKE_HC = """#!/bin/sh
echo "hostnamectl $@" >> "$FAKE_LOG"
exit 0
"""
FAKE_IP = """#!/bin/sh
echo "ip $@" >> "$FAKE_LOG"
case "$*" in
  *"addr show dev"*)
      echo "2: ens3    inet 10.1.1.31/24 brd 10.1.1.255 scope global ens3"
      [ -f "$FAKE_LEASE" ] && echo "2: ens3    inet 10.1.1.77/24 brd 10.1.1.255 scope global dynamic ens3"
      [ -f "$FAKE_ADDR" ] && echo "2: ens3    inet $(cat "$FAKE_ADDR") scope global ens3"
      ;;
  *"addr add"*) echo "$3" > "$FAKE_ADDR" ;;
  *"addr del"*) rm -f "$FAKE_ADDR" ;;
  *"route show default"*) [ -f "$FAKE_DEFROUTE" ] && echo "default via 10.1.1.1 dev ens3" ;;
esac
exit 0
"""


@pytest.fixture
def box(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "capabilities").write_text("backend=ifupdown\ndhcp=1\n")
    for name, body in (("fake-ifup", FAKE_IFUP), ("fake-ifdown", FAKE_IFUP), ("fake-hostnamectl", FAKE_HC), ("fake-ip", FAKE_IP)):
        p = tmp_path / name
        p.write_text(body, newline="\n")
        p.chmod(0o755)
    (tmp_path / "interfaces").write_text(INTERFACES, newline="\n")
    (tmp_path / "resolv.conf").write_text("domain ll.lab\nsearch ll.lab\nnameserver 10.1.1.17\n", newline="\n")
    (tmp_path / "hosts").write_text("127.0.0.1 localhost\n127.0.1.1 gammel\n", newline="\n")
    (tmp_path / "sysnet" / "ens3").mkdir(parents=True)
    (tmp_path / "sysnet" / "ens3" / "carrier").write_text("1\n")
    env = {**os.environ, "DATA": str(tmp_path), "STATE": str(tmp_path / "state"), "IFUP": str(tmp_path / "fake-ifup"),
           "IFDOWN": str(tmp_path / "fake-ifdown"), "HOSTNAMECTL": str(tmp_path / "fake-hostnamectl"),
           "IFFILE": str(tmp_path / "interfaces"), "RESOLV": str(tmp_path / "resolv.conf"), "HOSTS": str(tmp_path / "hosts"),
           "IFRUN": "", "IPCMD": str(tmp_path / "fake-ip"), "SYSNET": str(tmp_path / "sysnet"), "FAKE_LOG": str(tmp_path / "calls.log"),
           "FAKE_LEASE": str(tmp_path / "lease"), "FAKE_ADDR": str(tmp_path / "addr"), "FAKE_DEFROUTE": str(tmp_path / "defroute")}
    return tmp_path, env


def request(tmp, **kw):
    v = {"ID": "1", "BY": "admin", "CONFIRM_S": "20", "IFACE": "ens3", "MODE": "static", "IP": "10.1.1.50", "PREFIX": "24",
         "GATEWAY": "10.1.1.1", "DNS": "10.1.1.1", "HOSTNAME": "", "FALLBACK_AFTER": "5", **kw}
    (tmp / "config" / "network.request").write_text("".join(f"{k}={x}\n" for k, x in v.items()), newline="\n")


def status(tmp):
    return json.loads((tmp / "state" / "status.json").read_text(encoding="utf-8"))


def calls(tmp):
    p = tmp / "calls.log"
    return p.read_text().splitlines() if p.exists() else []


def wait_for_state(tmp, state):
    for _ in range(200):
        try:
            if status(tmp)["state"] == state:
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise AssertionError(f"tilstanden {state} blev aldrig nået")


def start(env):
    return subprocess.Popen([SH, str(APPLY)], env=env)


@needs_sh
def test_ventefasen_roerer_ikke_netvaerksfilen_og_bruger_ifup_med_ny_fil(box):
    tmp, env = box
    request(tmp)
    p = start(env)
    wait_for_state(tmp, "waiting_confirm")
    assert (tmp / "interfaces").read_text() == INTERFACES                       # urørt, indtil der bekræftes
    log = calls(tmp)
    assert any(c.startswith("fake-ifdown --force -i") and c.endswith("ens3") and "interfaces.new" not in c for c in log)
    assert any(c.startswith("fake-ifup -i") and "interfaces.new" in c and c.endswith("ens3") for c in log)
    new = (tmp / "state" / "interfaces.new").read_text()
    assert "address 10.1.1.50/24" in new and "gateway 10.1.1.1" in new and "dns-nameservers 10.1.1.1" in new
    assert "10.1.1.31" not in new and "iface lo inet loopback" in new and "iface ens4 inet dhcp" in new
    assert "source /etc/network/interfaces.d/*" in new and "# The loopback network interface" in new
    assert new.count("iface ens3 inet") == 1 and new.count("auto ens3") == 1
    (tmp / "config" / "network.revert").write_text("ok")
    p.wait(timeout=30)


@needs_sh
def test_bekraeftet_skriver_filen_varigt_med_sikkerhedskopi_dns_og_vaertsnavn(box):
    tmp, env = box
    request(tmp, HOSTNAME="scada-1")
    p = start(env)
    wait_for_state(tmp, "waiting_confirm")
    assert not [c for c in calls(tmp) if "hostnamectl" in c]                     # værtsnavn først efter bekræftelse
    (tmp / "config" / "network.confirm").write_text("ok")
    p.wait(timeout=30)
    assert status(tmp)["state"] == "confirmed"
    final = (tmp / "interfaces").read_text()
    assert "address 10.1.1.50/24" in final and "iface ens4 inet dhcp" in final and "10.1.1.31" not in final
    assert len(list(tmp.glob("interfaces.hypervision-bak-*"))) == 1
    assert (list(tmp.glob("interfaces.hypervision-bak-*"))[0].read_text()) == INTERFACES
    resolv = (tmp / "resolv.conf").read_text()
    assert "nameserver 10.1.1.1" in resolv and "10.1.1.17" not in resolv and "search ll.lab" in resolv and "domain ll.lab" in resolv
    assert any("hostnamectl set-hostname scada-1" in c for c in calls(tmp))
    assert "127.0.1.1 scada-1" in (tmp / "hosts").read_text() or "127.0.1.1 gammel" in (tmp / "hosts").read_text()
    conf = (tmp / "state" / "watchdog.conf").read_text()
    assert "BACKEND=ifupdown" in conf and "MODE=static" in conf and "IFACE=ens3" in conf


@needs_sh
def test_fortryd_gendanner_med_den_gamle_fil_og_aendrer_intet_varigt(box):
    tmp, env = box
    request(tmp)
    p = start(env)
    wait_for_state(tmp, "waiting_confirm")
    (tmp / "config" / "network.revert").write_text("ok")
    p.wait(timeout=30)
    assert status(tmp)["state"] == "reverted"
    assert (tmp / "interfaces").read_text() == INTERFACES and not list(tmp.glob("interfaces.hypervision-bak-*"))
    log = calls(tmp)
    assert any(c.startswith("fake-ifdown --force -i") and "interfaces.new" in c for c in log)
    assert log[-1].startswith("fake-ifup -i") and "interfaces.new" not in log[-1] and str(tmp / "interfaces") in log[-1]
    assert "resolv" not in (tmp / "resolv.conf").read_text() and "10.1.1.17" in (tmp / "resolv.conf").read_text()


@needs_sh
def test_ifup_der_fejler_giver_failed_og_gendanner(box):
    tmp, env = box
    env["FAKE_FAIL_IFUP"] = "1"
    request(tmp)
    subprocess.run([SH, str(APPLY)], env=env, check=False, timeout=60)
    assert status(tmp)["state"] == "failed" and "gendannet" in status(tmp)["message"]
    assert (tmp / "interfaces").read_text() == INTERFACES
    assert calls(tmp)[-1].startswith("fake-ifup -i") and "interfaces.new" not in calls(tmp)[-1]


@needs_sh
def test_dhcp_uden_klient_afvises_foer_noget_roeres(box):
    tmp, env = box
    (tmp / "state" / "capabilities").write_text("backend=ifupdown\ndhcp=0\n")
    request(tmp, MODE="dhcp")
    subprocess.run([SH, str(APPLY)], env=env, check=False, timeout=60)
    assert status(tmp)["state"] == "failed" and "DHCP-klient" in status(tmp)["message"]
    assert calls(tmp) == []


@needs_sh
def test_netkort_uden_stanza_i_hovedfilen_afvises(box):
    tmp, env = box
    request(tmp, IFACE="ens9")
    subprocess.run([SH, str(APPLY)], env=env, check=False, timeout=60)
    assert status(tmp)["state"] == "failed" and "netværksfilen" in status(tmp)["message"]
    assert calls(tmp) == [] and (tmp / "interfaces").read_text() == INTERFACES


@needs_sh
@pytest.mark.parametrize("mode,present,absent", [
    ("dhcp", ["iface ens3 inet dhcp"], ["inet static", "address 10.1.1.50", "post-up"]),
    ("dhcp_fallback", ["iface ens3 inet dhcp"], ["inet static", "address 10.1.1.50", "post-up"]),
    ("dhcp_static", ["iface ens3 inet dhcp", "post-up ip addr add 10.1.1.50/24 dev ens3",
                     "pre-down ip addr del 10.1.1.50/24 dev ens3"], ["inet static", "gateway 10.1.1.1"]),
])
def test_tilstande_giver_de_rigtige_stanzaer(box, mode, present, absent):
    tmp, env = box
    request(tmp, MODE=mode)
    p = start(env)
    wait_for_state(tmp, "waiting_confirm")
    new = (tmp / "state" / "interfaces.new").read_text()
    (tmp / "config" / "network.revert").write_text("ok")
    p.wait(timeout=30)
    for e in present:
        assert e in new, e
    for a in absent:
        assert a not in new, a
    assert "iface ens4 inet dhcp" in new and "iface lo inet loopback" in new


@needs_sh
def test_resolv_conf_som_symlink_roeres_ikke(box):
    tmp, env = box
    target = tmp / "stub-resolv"
    target.write_text("nameserver 127.0.0.53\n")
    (tmp / "resolv.conf").unlink()
    try:
        (tmp / "resolv.conf").symlink_to(target)
    except OSError:
        pytest.skip("symlinks kan ikke oprettes her")
    request(tmp)
    p = start(env)
    wait_for_state(tmp, "waiting_confirm")
    (tmp / "config" / "network.confirm").write_text("ok")
    p.wait(timeout=30)
    assert status(tmp)["state"] == "confirmed" and target.read_text() == "nameserver 127.0.0.53\n"


@needs_sh
def test_recover_efter_dod_midt_i_en_aendring(box):
    tmp, env = box
    (tmp / "state" / "interfaces.new").write_text("x")
    (tmp / "state" / "ifupdown.state").write_text("iface_changed=ens3\n")
    (tmp / "state" / "status.json").write_text(json.dumps({"state": "waiting_confirm", "deadline": 1, "ts": 1}))
    subprocess.run([SH, str(APPLY), "--recover"], env=env, check=False, timeout=60)
    assert status(tmp)["state"] == "reverted"
    assert calls(tmp)[-1].startswith("fake-ifup -i") and "interfaces.new" not in calls(tmp)[-1]


# ---------------------------------------------------------------- DHCP-vagten med ifupdown
def wconf(tmp, mode="dhcp_fallback", n=2):
    (tmp / "state" / "watchdog.conf").write_text(
        f"BACKEND=ifupdown\nMODE={mode}\nIFACE=ens3\nUUID=\nIP=192.168.100.10\nPREFIX=24\nGATEWAY=192.168.100.1\nFALLBACK_AFTER={n}\n", newline="\n")


def tick(env):
    subprocess.run([SH, str(WATCH)], env=env, check=False, timeout=30)


def wout(tmp):
    return json.loads((tmp / "state" / "watchdog.json").read_text(encoding="utf-8"))


@needs_sh
def test_vagt_lease_er_en_dynamisk_adresse_og_reserve_ip_lægges_paa_med_ip(box):
    tmp, env = box
    wconf(tmp, n=2)
    tick(env)
    assert wout(tmp)["state"] == "searching" and wout(tmp)["fails"] == 1
    tick(env)
    assert wout(tmp)["state"] == "fallback" and wout(tmp)["fallback_active"] is True
    log = calls(tmp)
    assert "ip addr add 192.168.100.10/24 dev ens3" in log
    assert "ip route add default via 192.168.100.1 dev ens3" in log           # ingen standardrute → reserven får en
    (tmp / "lease").write_text("x")                                           # en dynamisk adresse = DHCP svarer
    tick(env)
    assert wout(tmp)["state"] == "ok" and wout(tmp)["fallback_active"] is False
    log = calls(tmp)
    assert "ip addr del 192.168.100.10/24 dev ens3" in log and "ip route del default via 192.168.100.1 dev ens3" in log


@needs_sh
def test_vagt_lægger_ikke_standardrute_paa_hvis_der_allerede_er_en(box):
    tmp, env = box
    (tmp / "defroute").write_text("x")
    wconf(tmp, n=1)
    tick(env)
    assert "ip addr add 192.168.100.10/24 dev ens3" in calls(tmp)
    assert not [c for c in calls(tmp) if "route add" in c]


@needs_sh
def test_vagt_taeller_ikke_uden_link(box):
    tmp, env = box
    (tmp / "sysnet" / "ens3" / "carrier").write_text("0\n")
    wconf(tmp, n=1)
    for _ in range(3):
        tick(env)
    assert wout(tmp)["state"] == "nolink" and not [c for c in calls(tmp) if "addr add" in c]


# ---------------------------------------------------------------- rettelser efter review
@needs_sh
@pytest.mark.parametrize("text", [
    INTERFACES.replace("\n", "\r\n"),                                                  # CRLF
    INTERFACES.replace("iface ens4 inet dhcp", "  iface ens4 inet dhcp"),                # indrykket nøgleord
    INTERFACES + "address 10.9.9.9\n",                                                   # ukendt linje uden indrykning
])
def test_filer_der_ikke_kan_omskrives_sikkert_afvises(box, text):
    tmp, env = box
    (tmp / "interfaces").write_bytes(text.encode())
    request(tmp)
    subprocess.run([SH, str(APPLY)], env=env, check=False, timeout=60)
    assert status(tmp)["state"] == "failed" and "omskrives" in status(tmp)["message"]
    assert calls(tmp) == [] and (tmp / "interfaces").read_bytes() == text.encode()


@needs_sh
def test_relative_source_stier_goeres_absolutte_i_den_nye_fil(box):
    tmp, env = box
    (tmp / "interfaces").write_text(INTERFACES.replace("source /etc/network/interfaces.d/*", "source interfaces.d/*"), newline="\n")
    request(tmp)
    p = start(env)
    wait_for_state(tmp, "waiting_confirm")
    new = (tmp / "state" / "interfaces.new").read_text()
    (tmp / "config" / "network.revert").write_text("ok")
    p.wait(timeout=30)
    assert f"source {tmp.as_posix()}/interfaces.d/*" in new or os.name == "nt"      # (Windows-stier ser anderledes ud — kun Linux er relevant)
    assert "source interfaces.d/*" not in new


@needs_sh
def test_kun_praecist_netkortnavn_matcher_ens3_matcher_ikke_ensx3(box):
    tmp, env = box
    request(tmp, IFACE="ens.")        # '.' må ikke virke som joker
    subprocess.run([SH, str(APPLY)], env=env, check=False, timeout=60)
    assert status(tmp)["state"] == "failed" and calls(tmp) == []
    request(tmp, IFACE="-all")
    subprocess.run([SH, str(APPLY)], env=env, check=False, timeout=60)
    assert status(tmp)["state"] == "failed" and calls(tmp) == []


@needs_sh
def test_kun_de_tre_nyeste_sikkerhedskopier_beholdes(box):
    tmp, env = box
    for i in range(5):
        (tmp / f"interfaces.hypervision-bak-2026010100000{i}").write_text("gammel")
    request(tmp)
    p = start(env)
    wait_for_state(tmp, "waiting_confirm")
    (tmp / "config" / "network.confirm").write_text("ok")
    p.wait(timeout=30)
    baks = sorted(x.name for x in tmp.glob("interfaces.hypervision-bak-*"))
    assert len(baks) == 3 and baks[-1] > "interfaces.hypervision-bak-20260101000004"     # den nyeste er den nye, af de gamle er de ældste fjernet


@needs_sh
def test_hosts_opdateres_uden_regex_og_et_mistaenkeligt_gammelt_navn_roeres_ikke(box):
    tmp, env = box
    (tmp / "hosts").write_text("127.0.0.1 localhost\n127.0.1.1 gammel gammel.lan\n", newline="\n")
    fake_hostname = tmp / "hostname"
    fake_hostname.write_text("#!/bin/sh\necho gammel\n", newline="\n")
    fake_hostname.chmod(0o755)
    env["HOSTNAME_CMD"] = str(fake_hostname)
    request(tmp, HOSTNAME="ny-vm")
    p = start(env)
    wait_for_state(tmp, "waiting_confirm")
    (tmp / "config" / "network.confirm").write_text("ok")
    p.wait(timeout=30)
    assert "127.0.1.1 ny-vm gammel.lan" in (tmp / "hosts").read_text()
    # et gammelt navn med regex-/sed-tegn bruges aldrig
    (tmp / "hosts").write_text("127.0.1.1 x\n", newline="\n")
    fake_hostname.write_text("#!/bin/sh\necho 'x$/id/e;#'\n", newline="\n")
    request(tmp, HOSTNAME="ny-vm2")
    p = start(env)
    wait_for_state(tmp, "waiting_confirm")
    (tmp / "config" / "network.confirm").write_text("ok")
    p.wait(timeout=30)
    assert (tmp / "hosts").read_text() == "127.0.1.1 x\n"


@needs_sh
def test_ifupdown_state_er_vaek_efter_varig_skrivning_saa_recover_ikke_ruller_tilbage(box):
    tmp, env = box
    request(tmp)
    p = start(env)
    wait_for_state(tmp, "waiting_confirm")
    assert (tmp / "state" / "ifupdown.state").exists()
    (tmp / "config" / "network.confirm").write_text("ok")
    p.wait(timeout=30)
    assert not (tmp / "state" / "ifupdown.state").exists()


@needs_sh
def test_vagten_ignorerer_en_gammel_status_fra_en_doed_aendring(box):
    tmp, env = box
    wconf(tmp, n=1)
    (tmp / "state" / "status.json").write_text(json.dumps({"state": "waiting_confirm", "ts": int(time.time()) - 3600}))
    tick(env)
    assert wout(tmp)["state"] == "fallback"                                   # blokerer ikke for evigt
    (tmp / "state" / "status.json").write_text(json.dumps({"state": "waiting_confirm", "ts": int(time.time())}))
    (tmp / "state" / "watchdog.json").unlink()
    tick(env)
    assert not (tmp / "state" / "watchdog.json").exists()                     # en frisk status blokerer stadig


@needs_sh
def test_vagtens_tilstand_nulstilles_efter_genstart_og_manglende_reserve_ip_er_ikke_en_fejl(box):
    tmp, env = box
    wconf(tmp, n=1)
    (tmp / "state" / "watchdog.state").write_text("boot=en-gammel-boot\nfails=9\nfallback=1\nroute=1\n")
    tick(env)          # tilstanden er fra en anden start → begynd forfra (1 fejl, så reserve-IP igen med n=1)
    assert wout(tmp)["fails"] == 1 and wout(tmp)["fallback_active"] is True
    assert "ip addr add 192.168.100.10/24 dev ens3" in calls(tmp)
    # DHCP svarer igen, men reserve-adressen er væk i forvejen: ingen 'addr del', ingen hængende tilstand
    (tmp / "calls.log").unlink()
    (tmp / "addr").unlink()                  # reserve-adressen er væk (som efter en genstart)
    (tmp / "lease").write_text("x")
    boot = open("/proc/sys/kernel/random/boot_id").read().strip() if os.path.exists("/proc/sys/kernel/random/boot_id") else "none"
    (tmp / "state" / "watchdog.state").write_text(f"boot={boot}\nfails=1\nfallback=1\nroute=0\n")
    tick(env)
    assert wout(tmp)["fallback_active"] is False and not [c for c in calls(tmp) if "addr del" in c]
