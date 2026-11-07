"""Vælg LLM-model fra en liste (v4.4.0): kataloget, hentning af dele fra GitHub (falsk GitHub), kontrol og klargøring."""

import hashlib
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.errors import ServiceError
from app.services.llm_catalog import Cancelled, LlmCatalog, asset_name, release_tag
from tests.test_assist import ADMIN_PW, hw, package

BUILD = "b1"
REPO = "Jangreenlarsen/HypervisionPLC-SCADA"


def catalog_file(tmp_path, published=("x86_64",)):
    p = tmp_path / "llm-models.json"
    p.write_text(json.dumps({"llama": {"build": BUILD}, "models": {
        "lille-2b": {"name": "Lille 2B", "variant": "Hurtig", "about": "hurtig", "size": 100, "license": "Apache-2.0",
                     "profiles": ["vm-8", "vm-16"], "published": list(published)},
        "stor-8b": {"name": "Stor 8B", "variant": "Stor", "size": 900, "license": "Apache-2.0", "profiles": ["vm-32"],
                    "published": ["x86_64"]},
        "ikke-udgivet": {"name": "X", "size": 1, "profiles": ["vm-16"], "published": []},
    }}), encoding="utf-8")
    return p


def github(data: bytes, parts=2, sha=None, redirect_host="objects.githubusercontent.com", fail_part=None):
    """Falsk GitHub: releasen med delene, kontrolsummen og download-omdirigering til GitHubs CDN."""
    name = asset_name("x86_64", "lille-2b", BUILD)
    size = -(-len(data) // parts)
    chunks = [data[i * size:(i + 1) * size] for i in range(parts)]
    assets = {f"{name}.part{i + 1:02d}": c for i, c in enumerate(chunks)}
    assets[f"{name}.sha256"] = f"{sha or hashlib.sha256(data).hexdigest()}  {name}\n".encode()
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        if req.url.host == "api.github.com":
            if req.url.path == f"/repos/{REPO}/releases/tags/{release_tag('lille-2b', BUILD)}":
                return httpx.Response(200, json={"assets": [
                    {"name": n, "size": len(b), "browser_download_url": f"https://github.com/dl/{n}"} for n, b in assets.items()]})
            return httpx.Response(404)
        if req.url.host == "github.com":
            return httpx.Response(302, headers={"location": f"https://{redirect_host}/x/{req.url.path.split('/')[-1]}"})
        n = req.url.path.split("/")[-1]
        if fail_part and n.endswith(fail_part):
            return httpx.Response(500)
        return httpx.Response(200, content=assets[n])
    return httpx.MockTransport(handler), calls


def test_entries_follow_architecture_and_profile(tmp_path):
    cat = LlmCatalog(catalog_file(tmp_path), REPO)
    e = cat.entries("x86_64", "vm-16", "lille-2b")
    assert [x["id"] for x in e] == ["lille-2b", "stor-8b"]                 # ikke-udgivne vises ikke; Hurtig før Stor
    assert e[0]["fits"] and e[0]["installed"] and not e[1]["fits"]
    assert e[0]["release"] == "llm-lille-2b-b1" and e[0]["url"].endswith("/releases/tag/llm-lille-2b-b1")
    assert cat.entries("aarch64", "pi5", None) == []
    assert LlmCatalog(tmp_path / "findes-ikke.json", REPO).entries("x86_64", "vm-16", None) == []


def test_download_joins_parts_and_checks_sha(tmp_path):
    data = b"pakke-" * 1000
    transport, calls = github(data, parts=3)
    cat = LlmCatalog(catalog_file(tmp_path), REPO, transport)
    seen = []
    sha, size = cat.download("lille-2b", "x86_64", tmp_path / "ud.tar", seen.append, lambda: None)
    assert (tmp_path / "ud.tar").read_bytes() == data and size == len(data) and sha == hashlib.sha256(data).hexdigest()
    assert seen == [len(data)] and cat.job["parts"] == 3 and cat.job["done"] == len(data)
    assert sum("objects.githubusercontent.com" in c and ".part" in c for c in calls) == 3


@pytest.mark.parametrize("kw, msg", [
    ({"sha": "0" * 64}, "kontrolsummen"),
    ({"redirect_host": "ond.example.com"}, "ukendt adresse"),
    ({"fail_part": "part02"}, "GitHub svarede 500"),
])
def test_download_refuses_bad_or_foreign_data(tmp_path, kw, msg):
    transport, _ = github(b"x" * 5000, **kw)
    cat = LlmCatalog(catalog_file(tmp_path), REPO, transport)
    with pytest.raises(ServiceError) as e:
        cat.download("lille-2b", "x86_64", tmp_path / "ud.tar", lambda n: None, lambda: None)
    assert msg in e.value.message


def test_download_can_be_cancelled_and_unknown_models_are_refused(tmp_path):
    transport, _ = github(b"y" * 50000)
    cat = LlmCatalog(catalog_file(tmp_path), REPO, transport)
    cat.job = {"state": "running"}

    def precheck(n):
        cat.cancel()
    with pytest.raises(Cancelled):
        cat.download("lille-2b", "x86_64", tmp_path / "ud.tar", precheck, lambda: None)
    with pytest.raises(ServiceError) as e:
        cat.download("ikke-udgivet", "x86_64", tmp_path / "ud.tar", lambda n: None, lambda: None)
    assert e.value.status == 404


@pytest.fixture
def api(tmp_path, monkeypatch):
    state = tmp_path / "net-state"
    state.mkdir()
    settings = Settings(data_dir=tmp_path / "data", net_state_dir=state, frontend_dir=tmp_path / "nope",
                        admin_password=ADMIN_PW, backup_hours=0, start_runtimes=False,
                        llm_catalog=catalog_file(tmp_path))
    monkeypatch.setattr("app.api.assist.platform.machine", lambda: "x86_64")
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.app.state.hw_profile.detector = hw()
        c.state, c.dir = state, tmp_path / "data" / "llm"
        yield c


def _wait(c, states=("done", "error", "cancelled")):
    for _ in range(200):
        job = c.get("/api/assist/catalog").json()["job"]
        if job["state"] in states:
            return job
        time.sleep(0.05)
    raise AssertionError(job)


def test_api_downloads_stages_and_requests_install(api):
    (api.state / "llm-enabled").touch()     # root-hjælperen er installeret
    pkg = package(model=b"GGUF-hentet")
    transport, _ = github(pkg, parts=2)
    api.app.state.llm_catalog.transport = transport
    cat = api.get("/api/assist/catalog").json()
    assert cat["arch"] == "x86_64" and cat["profile"] == "vm-16" and [e["id"] for e in cat["entries"]] == ["lille-2b", "stor-8b"]
    r = api.post("/api/assist/download", json={"model": "lille-2b"})
    assert r.status_code == 200 and r.json()["state"] == "running"
    job = _wait(api)
    assert job["state"] == "done", job
    st = api.get("/api/assist/status").json()
    assert st["staged"]["sha256"] == hashlib.sha256(pkg).hexdigest() and st["pending"]["action"] == "install"
    acts = [a["action"] for a in api.get("/api/audit?limit=20").json()]
    assert "assist.download" in acts and "assist.package" in acts
    # Kan ikke vælge en model, der ikke passer til profilen, eller som ikke findes
    assert api.post("/api/assist/download", json={"model": "stor-8b"}).status_code == 409
    assert api.post("/api/assist/download", json={"model": "nej"}).status_code == 404


def test_api_errors_show_in_the_job_and_only_admin(api):
    transport, _ = github(package(), sha="1" * 64)
    api.app.state.llm_catalog.transport = transport
    api.post("/api/assist/download", json={"model": "lille-2b", "install": False})
    job = _wait(api)
    assert job["state"] == "error" and "kontrolsummen" in job["error"]
    transport, _ = github(package(), parts=2)
    api.app.state.llm_catalog.transport = transport
    api.post("/api/assist/download", json={"model": "lille-2b"})                 # hjælperen er ikke installeret
    job = _wait(api)
    assert job["state"] == "done" and "ikke installeret" in job["install_error"]
    api.delete("/api/assist/package")
    assert api.get("/api/assist/status").json()["staged"] is None
    api.app.state.hw_profile.detector = hw(ram_mb=2000)
    assert api.post("/api/assist/download", json={"model": "lille-2b"}).status_code == 409
    api.post("/api/users", json={"username": "tek", "role": "engineer", "password": "Hemmelig-123"})
    api.post("/api/auth/login", json={"username": "tek", "password": "Hemmelig-123"})
    api.post("/api/auth/password", json={"old_password": "Hemmelig-123", "new_password": "Hemmelig-123-ny"})
    assert api.get("/api/assist/catalog").status_code == 403
    assert api.post("/api/assist/download", json={"model": "lille-2b"}).status_code == 403


def test_pinned_sha_in_the_catalog_must_match_the_release(tmp_path):
    data = b"z" * 3000
    p = catalog_file(tmp_path)
    c = json.loads(p.read_text(encoding="utf-8"))
    c["models"]["lille-2b"]["published"] = {"x86_64": "a" * 64}         # kataloget har en anden SHA end udgivelsen
    p.write_text(json.dumps(c), encoding="utf-8")
    transport, _ = github(data)
    cat = LlmCatalog(p, REPO, transport)
    assert cat.entries("x86_64", "vm-16", None)[0]["pinned"] is True
    with pytest.raises(ServiceError) as e:
        cat.download("lille-2b", "x86_64", tmp_path / "ud.tar", lambda n: None, lambda: None)
    assert "ændret på GitHub" in e.value.message
    c["models"]["lille-2b"]["published"] = {"x86_64": hashlib.sha256(data).hexdigest()}
    p.write_text(json.dumps(c), encoding="utf-8")
    assert cat.download("lille-2b", "x86_64", tmp_path / "ud.tar", lambda n: None, lambda: None)[1] == len(data)


def test_disabled_repo_gives_no_list_and_no_download(tmp_path):
    cat = LlmCatalog(catalog_file(tmp_path), "")
    assert cat.entries("x86_64", "vm-16", None) == []
    with pytest.raises(ServiceError) as e:
        cat.download("lille-2b", "x86_64", tmp_path / "ud.tar", lambda n: None, lambda: None)
    assert e.value.status == 409


def test_cancel_right_after_start_is_not_lost(tmp_path):
    transport, _ = github(b"q" * 9000)
    cat = LlmCatalog(catalog_file(tmp_path), REPO, transport)
    cat.start({"state": "running"})
    assert cat.cancel() is True                                        # før tråden er gået i gang
    with pytest.raises(Cancelled):
        cat.download("lille-2b", "x86_64", tmp_path / "ud.tar", lambda n: None, lambda: None)
    cat.start({"state": "running"})                                    # næste hentning starter forfra
    assert not cat.cancelled()


def test_download_needs_room_for_the_install_too(api, monkeypatch):
    """BUGS v4.4.1: hentningen lykkedes, men root-hjælperen afviste installationen (pakke + gammel model + 1 GB)."""
    svc = api.app.state.assistant
    api.state.joinpath("llm.json").write_text(json.dumps({"state": "running", "model": {"id": "gammel", "name": "Gammel 4B",
                                                                                         "size": 2_500_000_000}}))
    monkeypatch.setattr("app.services.assistant._free_bytes", lambda p: 6_000_000_000)
    assert svc.install_need(1_400_000_000) == 1_400_000_000 + 2_500_000_000 + 200 * 1024 ** 2 + 1024 ** 3
    with pytest.raises(ServiceError) as e:
        svc.precheck_download(1_400_000_000)                       # 1,4 + 1,4 + 2,7 + 1,07 > 6 GB
    assert e.value.status == 507 and "Fjern den installerede model (Gammel 4B)" in e.value.message
    monkeypatch.setattr("app.services.assistant._free_bytes", lambda p: 9_000_000_000)
    svc.precheck_download(1_400_000_000)                           # nok plads
