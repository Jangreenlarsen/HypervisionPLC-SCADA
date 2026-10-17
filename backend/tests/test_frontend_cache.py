"""Cache-regler for frontenden (BUGS.md v0.63.0): hashede assets må gemmes, resten skal genvalideres efter en opdatering."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_cache_headers(tmp_path):
    front = tmp_path / "dist"
    (front / "assets").mkdir(parents=True)
    (front / "svgedit").mkdir()
    (front / "index.html").write_text("<!doctype html><title>x</title>", encoding="utf-8")
    (front / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (front / "svgedit" / "scada-editor.js").write_text("export {}", encoding="utf-8")
    settings = Settings(data_dir=tmp_path / "data", frontend_dir=front, admin_password="test-admin-pw-1", backup_hours=0)
    with TestClient(create_app(settings)) as c:
        for path in ("/", "/index.html", "/svgedit/scada-editor.js"):
            r = c.get(path)
            assert r.status_code == 200, path
            assert r.headers["cache-control"] == "no-cache", path
        r = c.get("/assets/index-abc123.js")
        assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
        # genvalidering: uændret fil → 304, stadig med reglen
        etag = c.get("/svgedit/scada-editor.js").headers["etag"]
        r = c.get("/svgedit/scada-editor.js", headers={"if-none-match": etag})
        assert r.status_code == 304 and r.headers["cache-control"] == "no-cache"
        # API'et er ikke berørt
        assert "immutable" not in c.get("/api/health").headers.get("cache-control", "")
