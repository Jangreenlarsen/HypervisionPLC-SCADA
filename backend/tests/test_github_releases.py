"""OTA fra GitHub: find nyeste udgivelse, hent og kontrollér pakken, klargør den via det almindelige opdateringsforløb."""

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from app.services.errors import ServiceError
from app.services.github_releases import GitHubReleases
from tests.test_updates import api, enable, make_tar  # noqa: F401  (fixture)

REPO = "ejer/repo"
CUR = {"version": "3.13.1", "build": "0304"}


def fake_github(pkg: bytes, *, name="scada-99.0.0-b9999.tar", sha=None, status=200, assets=None, fail=None):
    """MockTransport der svarer som GitHub: API'et for nyeste udgivelse og download-adresserne."""
    sha = sha if sha is not None else hashlib.sha256(pkg).hexdigest()
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        if fail:
            raise httpx.ConnectError("ingen net", request=req)
        if req.url.host == "api.github.com":
            if status != 200:
                return httpx.Response(status, json={"message": "x"})
            a = assets if assets is not None else [{"name": name, "size": len(pkg)}, {"name": name + ".sha256", "size": 90}]
            return httpx.Response(200, json={"tag_name": "v99.0.0", "body": "Noter", "html_url": "https://x", "assets": a})
        if req.url.path.endswith(".sha256"):
            return httpx.Response(200, text=f"{sha} *{name}\n")
        if req.url.path.endswith(".tar"):
            return httpx.Response(200, content=pkg)
        return httpx.Response(404)
    return httpx.MockTransport(handler), calls


def gh(transport, repo=REPO, current=CUR):
    return GitHubReleases(repo, lambda: current, transport)


def test_latest_describes_the_release_and_its_relation(tmp_path):
    t, _ = fake_github(b"x")
    info = gh(t).latest()
    assert (info["version"], info["build"], info["name"], info["relation"], info["notes"]) == \
        ("99.0.0", "9999", "scada-99.0.0-b9999.tar", "newer", "Noter")
    assert gh(t, current={"version": "99.0.0", "build": "9999"}).latest()["relation"] == "same"


@pytest.mark.parametrize("repo", ["", "  ", "ikke et repo", "a/b/c"])
def test_empty_or_invalid_repo_disables_the_feature(repo):
    t, calls = fake_github(b"x")
    with pytest.raises(ServiceError) as e:
        gh(t, repo=repo).latest()
    assert e.value.status == 409 and "slået fra" in e.value.message and not calls


@pytest.mark.parametrize("status,code,text", [(404, 404, "ingen udgivelse"), (403, 503, "for mange"), (500, 502, "fejl 500")])
def test_github_errors_become_specific_messages(status, code, text):
    t, _ = fake_github(b"x", status=status)
    with pytest.raises(ServiceError) as e:
        gh(t).latest()
    assert e.value.status == code and text in e.value.message


def test_no_network_is_explained():
    t, _ = fake_github(b"x", fail=True)
    with pytest.raises(ServiceError) as e:
        gh(t).latest()
    assert "internettet" in e.value.message


@pytest.mark.parametrize("assets,text", [([{"name": "andet.zip"}], "ingen pakke"),
                                         ([{"name": "scada-99.0.0-b9999.tar", "size": 1}], "mangler kontrolsummen")])
def test_release_without_package_or_checksum_is_refused(assets, text):
    t, _ = fake_github(b"x", assets=assets)
    with pytest.raises(ServiceError) as e:
        gh(t).latest()
    assert text in e.value.message


def test_download_writes_the_package_when_the_checksum_matches(tmp_path):
    pkg = make_tar(tmp_path / "p.tar").read_bytes()
    t, calls = fake_github(pkg)
    target = tmp_path / "in.tar"
    gh(t).download(target, "scada-99.0.0-b9999.tar")
    assert target.read_bytes() == pkg
    assert any(c.startswith(f"https://github.com/{REPO}/releases/download/v99.0.0/") for c in calls)


@pytest.mark.parametrize("sha", ["0" * 64, "ikke-en-sum"])
def test_wrong_or_invalid_checksum_leaves_nothing_behind(tmp_path, sha):
    t, _ = fake_github(b"pakke", sha=sha)
    target = tmp_path / "in.tar"
    with pytest.raises(ServiceError) as e:
        gh(t).download(target)
    assert "Kontrolsummen" in e.value.message and not target.exists()


def test_a_newer_release_than_the_one_shown_is_not_downloaded(tmp_path):
    t, _ = fake_github(b"x")
    with pytest.raises(ServiceError) as e:
        gh(t).download(tmp_path / "in.tar", "scada-98.0.0-b0001.tar")
    assert e.value.status == 409 and not (tmp_path / "in.tar").exists()


def test_too_large_package_is_refused_while_streaming(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.github_releases.MAX_PACKAGE_BYTES", 10)
    t, _ = fake_github(b"x" * 5, assets=[{"name": "scada-99.0.0-b9999.tar", "size": 5},
                                         {"name": "scada-99.0.0-b9999.tar.sha256"}])
    monkeypatch.setattr("app.services.github_releases.GitHubReleases.latest",
                        lambda self: {"tag": "v99.0.0", "name": "scada-99.0.0-b9999.tar", "size": 5})
    big, _ = fake_github(b"y" * 50)
    with pytest.raises(ServiceError) as e:
        gh(big).download(tmp_path / "in.tar")
    assert e.value.status == 413 and not (tmp_path / "in.tar").exists()


# ------------------------------------------------------------------ API

def test_api_search_and_download_stage_the_package_and_audit(api, tmp_path):  # noqa: F811
    enable(api)
    pkg = make_tar(tmp_path / "p.tar").read_bytes()
    t, _ = fake_github(pkg)
    api.app.state.github_releases = GitHubReleases(REPO, transport=t)
    r = api.get("/api/system/update/github")
    assert r.status_code == 200 and r.json()["relation"] == "newer"
    r = api.post("/api/system/update/github/download", json={"name": "scada-99.0.0-b9999.tar"})
    assert r.status_code == 200, r.text
    assert r.json()["sha256"] == hashlib.sha256(pkg).hexdigest()
    s = api.get("/api/system/update").json()
    assert s["staged"]["version"] == "99.0.0" and not (api.updates / "incoming.tar").exists()
    audit = api.get("/api/audit?action=system.update.github").json()
    assert audit and audit[0]["detail"]["name"] == "scada-99.0.0-b9999.tar"


def test_api_download_failure_is_audited_and_leaves_nothing(api, tmp_path):  # noqa: F811
    enable(api)
    t, _ = fake_github(b"pakke", sha="0" * 64)
    api.app.state.github_releases = GitHubReleases(REPO, transport=t)
    r = api.post("/api/system/update/github/download", json={"name": "scada-99.0.0-b9999.tar"})
    assert r.status_code == 502 and "Kontrolsummen" in r.json()["error"]
    assert not (api.updates / "incoming.tar").exists() and api.get("/api/system/update").json()["staged"] is None
    assert api.get("/api/audit?action=system.update.github").json()[0]["result"] == "error"


def test_api_requires_admin_and_enabled_helper(api, tmp_path):  # noqa: F811
    t, calls = fake_github(b"x")
    api.app.state.github_releases = GitHubReleases(REPO, transport=t)
    r = api.post("/api/system/update/github/download", json={"name": "scada-99.0.0-b9999.tar"})
    assert r.status_code == 409 and "ikke aktiveret" in r.json()["error"] and not calls
    from fastapi.testclient import TestClient
    anon = TestClient(api.app)
    assert anon.get("/api/system/update/github").status_code == 401
    assert anon.post("/api/system/update/github/download", json={"name": "x"}).status_code == 401


@pytest.mark.parametrize("tag", ["v99.0.0/../x", "v98.0.0", "99.0.0", ""])
def test_tag_must_be_safe_and_match_the_package(tag):
    def handler(req):
        return httpx.Response(200, json={"tag_name": tag, "assets": [{"name": "scada-99.0.0-b9999.tar", "size": 1},
                                                                    {"name": "scada-99.0.0-b9999.tar.sha256"}]})
    with pytest.raises(ServiceError) as e:
        gh(httpx.MockTransport(handler)).latest()
    assert e.value.status == 502 and "tag" in e.value.message


@pytest.mark.parametrize("body", [[1, 2], "tekst", {"tag_name": "v99.0.0", "assets": "x"}])
def test_unexpected_json_gives_a_clear_error(body):
    with pytest.raises(ServiceError) as e:
        gh(httpx.MockTransport(lambda req: httpx.Response(200, json=body))).latest()
    assert e.value.status == 502


def test_non_numeric_size_is_ignored():
    def handler(req):
        return httpx.Response(200, json={"tag_name": "v99.0.0", "assets": [{"name": "scada-99.0.0-b9999.tar", "size": "stor"},
                                                                          {"name": "scada-99.0.0-b9999.tar.sha256"}]})
    assert gh(httpx.MockTransport(handler)).latest()["size"] == 0


def test_only_one_package_is_received_at_a_time(api, tmp_path):  # noqa: F811
    enable(api)
    svc = api.app.state.update_service
    with svc.receiving() as first:
        assert first.exists() and first.parent == api.updates
        r = api.post("/api/system/update/github/download", json={"name": "scada-99.0.0-b9999.tar"})
        assert r.status_code == 409 and "allerede" in r.json()["error"]
        r = api.post("/api/system/update/upload", content=b"x", headers={"content-type": "application/octet-stream"})
        assert r.status_code == 409
    assert not first.exists()
    assert not list(api.updates.glob("incoming-*"))
