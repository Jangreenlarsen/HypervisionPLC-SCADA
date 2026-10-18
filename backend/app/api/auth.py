"""Login, sessioner og brugeradministration (lag 2) + rolle-afhængigheder til alle andre routes."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, Request, Response, WebSocket
from pydantic import BaseModel, ConfigDict, Field

from ..services.auth import AuthService, CurrentUser, role_at_least
from ..services.errors import ServiceError

COOKIE = "scada_session"
router = APIRouter(prefix="/api")


def _auth(request: Request) -> AuthService:
    return request.app.state.auth_service


def client_ip(request: Request) -> str:
    # Bag nginx (127.0.0.1) bruges X-Real-IP; ellers socket-adressen. Kun til log og login-låsning.
    peer = request.client.host if request.client else ""
    if peer in ("127.0.0.1", "::1") and request.headers.get("x-real-ip"):
        return request.headers["x-real-ip"]
    return peer


def require(role: str, *, allow_password_change: bool = False) -> Callable[[Request], CurrentUser]:
    """Afhængighed: kræver login med mindst `role`. Rollen tjekkes i backend — UI'et skjuler blot knapper."""

    def dependency(request: Request) -> CurrentUser:
        user = _auth(request).session_user(request.cookies.get(COOKIE))
        if user is None:
            raise ServiceError(401, "Du er ikke logget ind")
        if user.must_change_password and not allow_password_change:
            raise ServiceError(403, "Du skal skifte din adgangskode før du kan fortsætte")
        if not role_at_least(user.role, role):
            raise ServiceError(403, f"Kræver rollen '{role}' — du er '{user.role}'")
        request.state.user = user
        return user

    return dependency


def audit(request: Request, action: str, target: str = "", detail: dict[str, Any] | None = None) -> None:
    """Registrér en gennemført konfigurationsændring (kaldes efter succes)."""
    user = getattr(request.state, "user", None)
    request.app.state.audit_service.record(user.username if user else "-", client_ip(request), action, target,
                                           detail or {})


VIEWER = Depends(require("viewer"))
ENGINEER = Depends(require("engineer"))
ADMIN = Depends(require("admin"))


def websocket_user(ws: WebSocket) -> CurrentUser | None:
    user = ws.app.state.auth_service.session_user(ws.cookies.get(COOKIE))
    if user is None or user.must_change_password:
        return None
    return user


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginBody(_Model):
    username: str
    password: str


class PasswordBody(_Model):
    old_password: str
    new_password: str


class UserCreate(_Model):
    username: str
    role: str
    password: str
    drawings: list[str] | None = None  # None = alle tegninger


class UserUpdate(_Model):
    role: str | None = None
    disabled: bool | None = None
    password: str | None = None
    drawings: list[str] | None = None  # sendes null eksplicit = alle tegninger


@router.post("/auth/login")
async def login(body: LoginBody, request: Request, response: Response) -> dict[str, Any]:
    try:
        token, user = _auth(request).login(body.username, body.password, client_ip(request))
    except ServiceError as exc:
        request.app.state.audit_service.record(body.username[:64], client_ip(request), "login", body.username[:64],
                                               {}, "error", exc.message)
        raise
    request.app.state.audit_service.record(user.username, client_ip(request), "login", user.username)
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", path="/",
                        secure=request.app.state.settings.cookie_secure,
                        max_age=int(_auth(request).session_ttl_s))
    return user.public()


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response) -> None:
    _auth(request).logout(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")


@router.get("/auth/me")
async def me(user: CurrentUser = Depends(require("viewer", allow_password_change=True))) -> dict[str, Any]:
    return user.public()


class PaletteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbols: list[str] = Field(max_length=100)


@router.get("/auth/me/palette")
async def get_palette(request: Request, user: CurrentUser = Depends(require("engineer"))) -> dict[str, Any]:
    """"Mine symboler" i Tegn (v0.78.0) — pr. bruger."""
    return {"symbols": _auth(request).palette(user)}


@router.put("/auth/me/palette")
async def put_palette(body: PaletteBody, request: Request, user: CurrentUser = Depends(require("engineer"))) -> dict[str, Any]:
    return {"symbols": _auth(request).set_palette(user, body.symbols)}


@router.post("/auth/password", status_code=204)
async def change_password(body: PasswordBody, request: Request,
                          user: CurrentUser = Depends(require("viewer", allow_password_change=True))) -> None:
    _auth(request).change_own_password(user, body.old_password, body.new_password)
    audit(request, "user.password", user.username)


@router.get("/users", dependencies=[ADMIN])
async def list_users(request: Request) -> list[dict[str, Any]]:
    return _auth(request).list_users()


@router.post("/users", status_code=201, dependencies=[ADMIN])
async def create_user(body: UserCreate, request: Request) -> dict[str, Any]:
    result = _auth(request).create_user(body.model_dump())
    audit(request, "user.create", body.username, {"role": body.role, "drawings": body.drawings})
    return result


@router.patch("/users/{username}")
async def update_user(username: str, body: UserUpdate, request: Request,
                      user: CurrentUser = Depends(require("admin"))) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    result = _auth(request).update_user(user, username, data)
    audit(request, "user.update", username, data)
    return result


@router.delete("/users/{username}", status_code=204)
async def delete_user(username: str, request: Request, user: CurrentUser = Depends(require("admin"))) -> None:
    _auth(request).delete_user(user, username)
    audit(request, "user.delete", username)
