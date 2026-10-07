"""Login, roller, sessioner og sidste-admin-beskyttelse."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.auth import hash_password, verify_password

ADMIN_PW = "test-admin-pw-1"


def _settings(tmp_path, **kw):
    kw.setdefault("admin_password", ADMIN_PW)
    return Settings(data_dir=tmp_path, frontend_dir=tmp_path / "nope", **kw)


def _login(client, user, pw):
    return client.post("/api/auth/login", json={"username": user, "password": pw})


@pytest.fixture
def admin(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as c:
        assert _login(c, "admin", ADMIN_PW).status_code == 200
        yield c


def _new_client(admin_client):
    return TestClient(admin_client.app)


def _make_user(admin_client, username, role, pw="Hemmelig-123"):
    r = admin_client.post("/api/users", json={"username": username, "role": role, "password": pw})
    assert r.status_code == 201, r.text
    # Nye brugere skal skifte adgangskode ved første login
    c = _new_client(admin_client)
    assert _login(c, username, pw).json()["must_change_password"] is True
    assert c.post("/api/auth/password", json={"old_password": pw, "new_password": pw + "-ny"}).status_code == 204
    return c


def test_password_hashing():
    h = hash_password("korrekt hest")
    assert h.startswith("scrypt$") and "korrekt" not in h
    assert verify_password("korrekt hest", h)
    assert not verify_password("forkert", h)
    assert not verify_password("x", "md5$abc")
    assert not verify_password("x", "noget-skrald")
    assert hash_password("a" * 10) != hash_password("a" * 10)  # unikt salt


def test_generated_admin_password_must_be_changed(tmp_path):
    with TestClient(create_app(_settings(tmp_path, admin_password=None))) as c:
        pw_file = tmp_path / "initial-admin-password.txt"
        password = pw_file.read_text().strip()
        assert len(password) >= 12
        assert _login(c, "admin", password).json()["must_change_password"] is True
        r = c.get("/api/tags")
        assert r.status_code == 403 and "skifte din adgangskode" in r.json()["error"]
        assert c.get("/api/auth/me").status_code == 200
        r = c.post("/api/auth/password", json={"old_password": password, "new_password": password})
        assert r.status_code == 400 and "forskellig" in r.json()["error"]
        assert c.post("/api/auth/password", json={"old_password": password, "new_password": "Ny-adgangskode-42"}).status_code == 204
        assert not pw_file.exists()
        assert c.get("/api/tags").status_code == 200


def test_unauthenticated_and_public(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as c:
        assert c.get("/api/health").status_code == 200
        for method, path in [("GET", "/api/tags"), ("GET", "/api/drawings"), ("GET", "/api/live"),
                             ("POST", "/api/tags"), ("GET", "/api/users"), ("GET", "/api/plcs")]:
            r = c.request(method, path, json={} if method == "POST" else None)
            assert r.status_code == 401, (method, path, r.status_code)
            assert r.json()["error"] == "Du er ikke logget ind"


def test_login_errors_and_lockout(admin):
    c = _new_client(admin)
    assert _login(c, "", "").status_code in (400, 422)
    for _ in range(4):
        r = _login(c, "admin", "forkert-forkert")
        assert r.status_code == 401 and r.json()["error"] == "Forkert brugernavn eller adgangskode"
    r = _login(c, "ukendt", "forkert-forkert")
    assert r.status_code == 401 and r.json()["error"] == "Forkert brugernavn eller adgangskode"  # samme svar
    assert _login(c, "admin", "forkert-forkert").status_code == 401  # 5. fejl → låst
    r = _login(c, "admin", ADMIN_PW)
    assert r.status_code == 429 and "prøv igen" in r.json()["error"]


def test_role_matrix(admin):
    viewer = _make_user(admin, "operatoer1", "viewer")
    engineer = _make_user(admin, "tekniker1", "engineer")

    assert viewer.get("/api/tags").status_code == 200
    assert viewer.get("/api/drawings").status_code == 200
    r = viewer.post("/api/tags", json={"name": "X", "source": "plc1:hr:1"})
    assert r.status_code == 403 and "engineer" in r.json()["error"]
    assert viewer.get("/api/plcs").status_code == 403
    assert viewer.get("/api/users").status_code == 403

    assert engineer.get("/api/plcs").status_code == 200
    r = engineer.post("/api/drawings", json={"name": "x", "svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>'})
    assert r.status_code == 201
    r = engineer.post("/api/plcs", json={"key": "plc9", "base_url": "http://10.0.0.9", "username": "u"})
    assert r.status_code == 403 and "admin" in r.json()["error"]
    assert engineer.get("/api/users").status_code == 403

    assert admin.get("/api/users").status_code == 200


def test_last_admin_cannot_be_removed(admin):
    for body in ({"role": "engineer"}, {"disabled": True}):
        r = admin.patch("/api/users/admin", json=body)
        assert r.status_code == 409 and "administrator" in r.json()["error"]
    r = admin.delete("/api/users/admin")
    assert r.status_code == 409
    assert admin.get("/api/auth/me").json()["role"] == "admin"  # intet ændret

    second = _make_user(admin, "admin2", "admin")
    assert second.patch("/api/users/admin", json={"role": "viewer"}).status_code == 200
    # nu er admin2 den eneste → kan ikke nedgradere sig selv
    assert second.patch("/api/users/admin2", json={"role": "viewer"}).status_code == 409
    # disabled admin tæller ikke som aktiv
    assert second.patch("/api/users/admin", json={"role": "admin", "disabled": True}).status_code == 200
    assert second.delete("/api/users/admin2").status_code == 409


def test_role_change_ends_target_sessions(admin):
    engineer = _make_user(admin, "tekniker2", "engineer")
    assert engineer.get("/api/plcs").status_code == 200
    assert admin.patch("/api/users/tekniker2", json={"role": "viewer"}).status_code == 200
    assert engineer.get("/api/plcs").status_code == 401  # skal logge ind igen og får ny rolle


def test_disabled_user_cannot_login(admin):
    _make_user(admin, "midlertidig", "viewer")
    admin.patch("/api/users/midlertidig", json={"disabled": True})
    r = _login(_new_client(admin), "midlertidig", "Hemmelig-123-ny")
    assert r.status_code == 403 and "deaktiveret" in r.json()["error"]


@pytest.mark.parametrize("body, message", [
    ({"username": "a", "role": "viewer", "password": "Hemmelig-123"}, "2-32 tegn"),
    ({"username": "ny bruger", "role": "viewer", "password": "Hemmelig-123"}, "2-32 tegn"),
    ({"username": "bruger1", "role": "superuser", "password": "Hemmelig-123"}, "Ukendt rolle"),
    ({"username": "bruger1", "role": "viewer", "password": "kort"}, "mindst 10"),
    ({"username": "bruger1", "role": "viewer", "password": "          "}, "tom"),
    ({"username": "bruger1234", "role": "viewer", "password": "BRUGER1234"}, "brugernavnet"),
])
def test_user_validation(admin, body, message):
    r = admin.post("/api/users", json=body)
    assert r.status_code == 400 and message in r.json()["error"], r.text


def test_logout_and_cookie_flags(tmp_path):
    with TestClient(create_app(_settings(tmp_path, cookie_secure=True)), base_url="https://testserver") as c:
        r = _login(c, "admin", ADMIN_PW)
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie and "secure" in cookie
        assert c.post("/api/auth/logout").status_code == 204
        assert c.get("/api/tags").status_code == 401


def test_cross_origin_write_rejected(admin):
    r = admin.post("/api/tags", json={"name": "X", "source": "plc1:hr:1"}, headers={"origin": "http://evil.example"})
    assert r.status_code == 403 and "origin" in r.json()["error"]
    r = admin.post("/api/tags", json={"name": "X", "source": "plc1:hr:1"}, headers={"origin": "http://testserver"})
    assert r.status_code == 400  # forbi origin-tjekket; fejler på at plc1 ikke findes
