"""System › Konfiguration (læsning): tolkning af netværksoutput, skrivemåling og at kun admin får adgang."""

import json

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import sysconfig

ADMIN_PW = "test-admin-pw-1"

IP_ADDR = json.dumps([
    {"ifname": "lo", "flags": ["LOOPBACK", "UP"], "address": "00:00:00:00:00:00", "operstate": "UNKNOWN",
     "addr_info": [{"family": "inet", "local": "127.0.0.1", "prefixlen": 8}]},
    {"ifname": "eth0", "flags": ["UP"], "address": "dc:a6:32:01:02:03", "operstate": "UP",
     "addr_info": [{"family": "inet", "local": "10.1.1.31", "prefixlen": 24},
                   {"family": "inet", "local": "192.168.100.10", "prefixlen": 24},
                   {"family": "inet6", "local": "fe80::1", "prefixlen": 64}]},
])
IP_ROUTE = json.dumps([{"dst": "10.1.1.0/24", "dev": "eth0"}, {"dst": "default", "gateway": "10.1.1.1", "dev": "eth0"}])


def test_parse_ip_addr_springer_loopback_og_ipv6_over():
    nics = sysconfig.parse_ip_addr(IP_ADDR)
    assert [n["name"] for n in nics] == ["eth0"]
    assert nics[0]["state"] == "up" and nics[0]["mac"] == "dc:a6:32:01:02:03"
    assert nics[0]["addresses"] == [{"ip": "10.1.1.31", "prefix": 24}, {"ip": "192.168.100.10", "prefix": 24}]


def test_parse_default_route():
    assert sysconfig.parse_default_route(IP_ROUTE) == "10.1.1.1"
    assert sysconfig.parse_default_route("[]") == ""


def test_parse_resolv():
    assert sysconfig.parse_resolv("# kommentar\nnameserver 10.1.1.1\nsearch lan\nnameserver 8.8.8.8\n") == ["10.1.1.1", "8.8.8.8"]


def test_network_status_uden_ip_programmet(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("ip")

    monkeypatch.setattr(sysconfig.subprocess, "run", boom)
    st = sysconfig.network_status()
    assert st["available"] is False and "ip" in st["error"]


def test_storage_info_viser_filer_og_disk(tmp_path):
    (tmp_path / "trends.db").write_bytes(b"x" * 10)
    (tmp_path / "backups").mkdir()
    (tmp_path / "backups" / "a.json").write_bytes(b"y" * 5)
    info = sysconfig.storage_info(tmp_path)
    assert info["path"] == str(tmp_path)
    assert {"name": "trends.db", "size": 10} in info["files"]
    assert {"name": "backups", "size": 5} in info["folders"]
    assert info["disk"] and info["disk"]["free"] > 0


def test_write_stats_overslag_kraever_10_minutter():
    from app.services.trends import TrendRecorder

    class _Cfg:
        def list_trend_tags(self):
            return []

    class _Mgr:
        db = _Cfg()

    rec = TrendRecorder(_Mgr(), None)  # type: ignore[arg-type]
    rec._started = 1000.0
    rec.rows_written, rec.flushes = 120, 10
    assert rec.write_stats(now=1300.0)["rows_per_day"] is None
    s = rec.write_stats(now=1000.0 + 3600)
    assert s["rows_per_day"] == 2880 and s["flushes_per_day"] == 240


def test_kun_admin_kan_laese_konfigurationen(tmp_path):
    settings = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9,
                        frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0)
    with TestClient(create_app(settings)) as c:
        assert c.get("/api/system/config").status_code in (401, 403)
        assert c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW}).status_code == 200
        r = c.get("/api/system/config")
        assert r.status_code == 200
        body = r.json()
        assert body["storage"]["path"] == str(tmp_path)
        assert body["trends"]["write"]["rows"] == 0
        assert "interfaces" in body["network"]
        assert "password" not in json.dumps(body).lower()
