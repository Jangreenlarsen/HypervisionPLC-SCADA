"""LLM-hjælperen, fase 0 (v4.0.0): hardwareprofil, LLM-klient (lag 4c), LLM-pakke, styring af tjenesten og root-hjælperen."""

import asyncio
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.client import LlmClient, LlmError
from app.main import create_app
from app.services import hwprofile

ADMIN_PW = "test-admin-pw-1"
SH = shutil.which("sh")
SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "apply-llm.sh"
needs_sh = pytest.mark.skipif(SH is None or shutil.which("sha256sum") is None, reason="sh/sha256sum findes ikke")


def hw(ram_mb=16000, cpus=4, arch="x86_64", avx2=True, pi=""):
    return lambda: {"arch": arch, "cpus": cpus, "ram_mb": ram_mb, "pi_model": pi, "avx2": avx2, "neon": False,
                    "suggested": hwprofile.suggest(arch, cpus, ram_mb, pi)}


def package(arch="x86_64", model=b"GGUF-test-model", extra=None, manifest=None, root="scada-llm") -> bytes:
    """En lille, gyldig LLM-pakke (som deploy/make-llm-package.sh laver den)."""
    man = manifest or {"format": "hv-llm", "format_version": 1, "arch": arch, "llama_build": "b1", "ctx": 4096,
                       "model": {"id": "test-4b", "name": "Test 4B", "file": "test.gguf", "quant": "Q4_K_M",
                                 "license": "Apache-2.0", "sha256": hashlib.sha256(model).hexdigest(), "size": len(model)}}
    files = {f"{root}/manifest.json": json.dumps(man).encode(), f"{root}/model/test.gguf": model,
             f"{root}/llama/llama-server": b"#!/bin/sh\n", f"{root}/LICENSES/README.txt": b"MIT/Apache-2.0", **(extra or {})}
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


@pytest.fixture
def api(tmp_path):
    state = tmp_path / "net-state"
    state.mkdir()
    settings = Settings(data_dir=tmp_path / "data", net_state_dir=state, frontend_dir=tmp_path / "nope",
                        admin_password=ADMIN_PW, backup_hours=0, start_runtimes=False)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.app.state.hw_profile.detector = hw()
        c.state, c.dir = state, tmp_path / "data" / "llm"
        yield c


# ------------------------------------------------------------------ hardwareprofil

def test_detection_parsing_and_suggestions():
    assert hwprofile.parse_meminfo("MemTotal:       16303344 kB\nMemFree: 1 kB") == 15921
    assert "avx2" in hwprofile.parse_cpu_flags("processor : 0\nflags\t\t: fpu sse avx avx2 fma\n")
    assert hwprofile.parse_cpu_flags("Features\t: fp asimd evtstrm") == {"fp", "asimd", "evtstrm"}
    assert hwprofile.suggest("aarch64", 4, 8000, "Raspberry Pi 4 Model B Rev 1.5") == "pi4"
    assert hwprofile.suggest("aarch64", 4, 16000, "Raspberry Pi 5 Model B") == "pi5"
    assert hwprofile.suggest("x86_64", 4, 16000, "") == "vm-16"
    assert hwprofile.suggest("x86_64", 4, 14985, "") == "vm-16"   # demo-VM'en: "16 GB" melder 14.985 MB
    assert hwprofile.suggest("x86_64", 8, 64000, "") == "vm-32"
    assert hwprofile.suggest("x86_64", 2, 1967, "") == "lille"    # testserveren: ingen hjælper
    assert hwprofile.suggest("x86_64", 4, 0, "") == "lille"       # RAM ukendt: hellere uden hjælper


def test_profile_status_warnings_and_admin_only(api):
    st = api.get("/api/assist/status").json()["hw"]
    assert st["profile"] == "vm-16" and not st["confirmed"] and st["llm_allowed"] and st["llm_threads"] == 3 and st["warnings"] == []
    api.app.state.hw_profile.detector = hw(ram_mb=4000, avx2=False)
    assert api.get("/api/assist/status").json()["hw"]["profile"] == "lille"           # forslag: uden hjælper
    api.put("/api/assist/profile", json={"profile": "vm-8"})                            # admin vælger alligevel → advarsler
    warn = api.get("/api/assist/status").json()["hw"]["warnings"]
    assert any("AVX2" in w for w in warn) and any("RAM" in w for w in warn)
    assert api.put("/api/assist/profile", json={"profile": "nej"}).status_code == 400
    r = api.put("/api/assist/profile", json={"profile": "pi4"})
    assert r.status_code == 200 and r.json()["profile"] == "pi4" and r.json()["confirmed"] and not r.json()["llm_allowed"]
    assert any(a["action"] == "assist.profile" for a in api.get("/api/audit").json())
    api.post("/api/users", json={"username": "op", "password": "op-pw-1234567", "role": "operator"})
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "op", "password": "op-pw-1234567"})
    api.post("/api/auth/password", json={"old_password": "op-pw-1234567", "new_password": "op-pw-1234567-ny"})
    assert api.get("/api/assist/available").json() == {"available": False, "busy": False, "waiting": 0}
    for m, u, b in (("GET", "/api/assist/status", None), ("PUT", "/api/assist/profile", {"profile": "vm-16"}),
                    ("POST", "/api/assist/service", {"action": "start"}), ("POST", "/api/assist/test", {})):
        assert api.request(m, u, json=b).status_code == 403, u


# ------------------------------------------------------------------ LLM-klient (lag 4c)

def test_client_only_loopback_and_parses_answers():
    with pytest.raises(ValueError):
        LlmClient("http://10.0.0.5:8091")

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "test.gguf"}]})
        body = json.loads(req.content)
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
        assert body["response_format"]["json_schema"]["schema"]["type"] == "object"
        return httpx.Response(200, json={"model": "test.gguf", "choices": [{"message": {"content": '{"ok": true}'}}],
                                         "usage": {"prompt_tokens": 20, "completion_tokens": 5}})
    c = LlmClient(transport=httpx.MockTransport(handler))
    assert asyncio.run(c.health()) == {"ok": True, "status": "ok", "model": "test.gguf"}
    data, done = asyncio.run(c.chat_json([{"role": "user", "content": "x"}], {"type": "object"}))
    assert data == {"ok": True} and done.tokens_out == 5 and done.model == "test.gguf"


@pytest.mark.parametrize("response, kind", [
    (httpx.Response(503, json={}), "busy"), (httpx.Response(500, text="x"), "bad_response"),
    (httpx.Response(200, json={"choices": []}), "bad_response"), ("timeout", "timeout"), ("down", "unavailable"),
])
def test_client_errors_are_typed(response, kind):
    def handler(req):
        if response == "timeout":
            raise httpx.ReadTimeout("t", request=req)
        if response == "down":
            raise httpx.ConnectError("c", request=req)
        return response
    with pytest.raises(LlmError) as e:
        asyncio.run(LlmClient(transport=httpx.MockTransport(handler)).chat([{"role": "user", "content": "x"}]))
    assert e.value.kind == kind
    st = asyncio.run(LlmClient(transport=httpx.MockTransport(handler)).health()) if response == "down" else None
    assert st is None or st == {"ok": False, "status": "unavailable", "model": None}


def test_selftest_uses_the_client_and_counts(api):
    def handler(req):
        if req.url.path == "/health":
            return httpx.Response(200, json={})
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": '{"ok": true, "svar": "Den flytter vand"}'}}],
                                         "usage": {"prompt_tokens": 30, "completion_tokens": 8}})
    api.app.state.assistant.client = LlmClient(transport=httpx.MockTransport(handler))
    r = api.post("/api/assist/test", json={})
    assert r.status_code == 200 and r.json()["answer"] == "Den flytter vand" and r.json()["tokens_out"] == 8
    st = api.get("/api/assist/status").json()
    assert st["stats"]["requests"] == 1 and st["stats"]["errors"] == 0
    api.app.state.assistant.client = LlmClient(transport=httpx.MockTransport(lambda req: (_ for _ in ()).throw(httpx.ConnectError("x", request=req))))
    r = api.post("/api/assist/test", json={})
    assert r.status_code == 503 and "kan ikke nås" in r.json()["error"]
    assert api.get("/api/assist/status").json()["stats"]["errors"] == 1


# ------------------------------------------------------------------ LLM-pakke og styring

def test_package_upload_checks_and_stages(api):
    bad = {
        "arch": (package(arch="aarch64"), "bygget til aarch64"),
        "path": (package(extra={"scada-llm/../evil": b"x"}), "usikker sti"),
        "root": (package(extra={"andet/x": b"x"}), "skal ligge under"),
        "size": (package(manifest={"format": "hv-llm", "format_version": 1, "arch": "x86_64", "llama_build": "b1",
                                   "model": {"id": "t", "name": "T", "file": "test.gguf", "license": "MIT",
                                             "sha256": "0" * 64, "size": 99}}), "størrelsen passer ikke"),
        "notar": (b"ikke en tar", "tar-pakke"),
    }
    for key, (data, msg) in bad.items():
        r = api.post("/api/assist/package", content=data, headers={"Content-Type": "application/octet-stream"})
        assert r.status_code == 400 and msg in r.json()["error"], (key, r.text)
    data = package()
    r = api.post("/api/assist/package", content=data, headers={"Content-Type": "application/octet-stream"})
    assert r.status_code == 200, r.text
    assert r.json()["sha256"] == hashlib.sha256(data).hexdigest() and r.json()["manifest"]["model"]["name"] == "Test 4B"
    assert (api.dir / "incoming.tar").read_bytes() == data and api.get("/api/assist/status").json()["staged"]["size"] == len(data)
    assert api.delete("/api/assist/package").status_code == 204 and not (api.dir / "incoming.tar").exists()
    api.put("/api/assist/profile", json={"profile": "pi4"})
    r = api.post("/api/assist/package", content=data, headers={"Content-Type": "application/octet-stream"})
    assert r.status_code == 409 and "tillader ikke" in r.json()["error"]


def test_service_requests_for_the_root_helper(api):
    r = api.post("/api/assist/service", json={"action": "install"})
    assert r.status_code == 409 and "ikke installeret" in r.json()["error"]
    (api.state / "llm-enabled").write_text("")
    assert api.post("/api/assist/service", json={"action": "install"}).json()["error"] == "Upload en LLM-pakke først"
    assert "Ingen LLM-pakke" in api.post("/api/assist/service", json={"action": "start"}).json()["error"]
    data = package()
    api.post("/api/assist/package", content=data, headers={"Content-Type": "application/octet-stream"})
    assert api.post("/api/assist/service", json={"action": "install"}).status_code == 200
    req = dict(l.split("=", 1) for l in (api.dir / "llm.request").read_text().splitlines())
    assert req["action"] == "install" and req["sha256"] == hashlib.sha256(data).hexdigest()
    assert req["threads"] == "3" and req["mem_mb"] == "9000" and req["by"] == "admin"
    r = api.post("/api/assist/service", json={"action": "stop"})
    assert r.status_code == 409 and "allerede i gang" in r.json()["error"]
    assert api.get("/api/assist/status").json()["pending"]["action"] == "install"
    old = time.time() - 3600
    os.utime(api.dir / "llm.request", (old, old))
    assert api.post("/api/assist/service", json={"action": "stop"}).status_code == 200
    assert api.post("/api/assist/service", json={"action": "reboot"}).status_code == 422
    assert any(a["action"] == "assist.service" for a in api.get("/api/audit").json())


# ------------------------------------------------------------------ root-hjælperen deploy/apply-llm.sh

def _helper_env(tmp_path):
    for d in ("data/llm", "state", "opt", "etc", "units"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    calls = tmp_path / "systemctl.log"
    fake = tmp_path / "systemctl"
    fake.write_text(f'#!/bin/sh\necho "$@" >> "{calls.as_posix()}"\n', newline="\n")
    fake.chmod(0o755)
    py = shutil.which("python3") or shutil.which("python")
    p = lambda d: (tmp_path / d).as_posix()   # msys-tar på Windows kan ikke bruge "C:\..." med -C
    return {**os.environ, "DATA": p("data"), "STATE": p("state"), "OPT": p("opt"), "ETC": p("etc"), "UNITDIR": p("units"),
            "SYSTEMCTL": f"sh {fake.as_posix()}", "PY": py, "SKIP_DEPS": "1"}, calls


def _request(tmp_path, **fields):
    (tmp_path / "data/llm/llm.request").write_text("".join(f"{k}={v}\n" for k, v in fields.items()), newline="\n")


def _run(env):
    return subprocess.run([SH, str(SCRIPT)], env=env, capture_output=True, text=True, timeout=120)


def _status(tmp_path):
    return json.loads((tmp_path / "state/llm.json").read_text())


@needs_sh
def test_helper_installs_checks_and_controls(tmp_path):
    env, calls = _helper_env(tmp_path)
    data = package()
    (tmp_path / "data/llm/incoming.tar").write_bytes(data)
    _request(tmp_path, action="install", by="admin", sha256="0" * 64, threads="3", mem_mb="9000")
    _run(env)
    st = _status(tmp_path)
    assert st["state"] == "error" and "SHA256" in st["message"] and not (tmp_path / "opt/current").exists()

    (tmp_path / "data/llm/incoming.tar").write_bytes(data)
    _request(tmp_path, action="install", by="admin", sha256=hashlib.sha256(data).hexdigest(), threads="3", mem_mb="9000")
    _run(env)
    st = _status(tmp_path)
    assert st["state"] == "running", (st, (tmp_path / "state/llm.log").read_text())
    assert st["model"]["name"] == "Test 4B" and st["llama_build"] == "b1"
    assert (tmp_path / "opt/current/model/test.gguf").read_bytes() == b"GGUF-test-model"
    envfile = (tmp_path / "etc/hypervisionplc-scada-llm.env").read_text()
    assert "LLM_THREADS=3" in envfile and "LLM_CTX=4096" in envfile and "test.gguf" in envfile
    assert "MemoryMax=9000M" in (tmp_path / "units/hypervisionplc-scada-llm.service.d/limits.conf").read_text()
    assert "restart hypervisionplc-scada-llm.service" in calls.read_text()
    assert not (tmp_path / "data/llm/incoming.tar").exists() and not (tmp_path / "data/llm/llm.request").exists()

    _request(tmp_path, action="stop", by="admin")
    _run(env)
    assert _status(tmp_path)["state"] == "stopped" and "disable --now" in calls.read_text()
    _request(tmp_path, action="start", by="admin", threads="999", mem_mb="abc")    # ugyldige tal → sikre standarder
    _run(env)
    assert "LLM_THREADS=2" in (tmp_path / "etc/hypervisionplc-scada-llm.env").read_text()
    _request(tmp_path, action="remove", by="admin")
    _run(env)
    assert _status(tmp_path)["state"] == "removed" and not (tmp_path / "opt").exists()


@needs_sh
def test_helper_rejects_unsafe_packages_and_requests(tmp_path):
    env, _ = _helper_env(tmp_path)
    data = package(extra={"scada-llm/../../evil": b"x"})
    (tmp_path / "data/llm/incoming.tar").write_bytes(data)
    _request(tmp_path, action="install", by="admin", sha256=hashlib.sha256(data).hexdigest())
    _run(env)
    assert _status(tmp_path)["state"] == "error" and "usikker sti" in _status(tmp_path)["message"]
    assert not (tmp_path / "evil").exists() and not (tmp_path / "data/evil").exists()
    _request(tmp_path, action="rm -rf /", by="admin")
    _run(env)
    assert "ukendt handling" in (tmp_path / "state/llm.log").read_text()
    _request(tmp_path, action="stop", by="admin")
    old = time.time() - 7200
    os.utime(tmp_path / "data/llm/llm.request", (old, old))
    _run(env)
    assert "for gammel" in (tmp_path / "state/llm.log").read_text()


def test_upload_refused_before_streaming_when_disk_is_short(api, monkeypatch):
    from app.services import assistant
    monkeypatch.setattr(assistant, "_free_bytes", lambda p: 1024 ** 3)       # 1 GB fri < pakke + 2 GB reserve
    data = package()
    r = api.post("/api/assist/package", content=data, headers={"Content-Type": "application/octet-stream"})
    assert r.status_code == 507 and "diskplads" in r.json()["error"]
    assert not (api.dir / "incoming.tar").exists() and not (api.dir / "receiving.tar").exists()
