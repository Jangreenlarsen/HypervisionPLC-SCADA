"""Brugere, roller og sessioner.

- Adgangskoder: scrypt (stdlib) med tilfældigt salt pr. bruger.
- Sessioner: tilfældigt token i en HttpOnly-cookie; kun SHA-256 af tokenet gemmes i DB.
  Glidende udløb (fornyes ved brug).
- Roller (stigende): viewer < operator < engineer < admin. Håndhæves i backend.
- Viewer/operatør kan begrænses til udvalgte tegninger (`scoped`); se services/scope.py.
- Sidste aktive admin kan hverken slettes, nedgraderes eller deaktiveres
  (tjekket atomisk i databasen, CLAUDE.md regel 12).
- Første opstart uden brugere: `admin` oprettes med adgangskoden fra
  SCADA_ADMIN_PASSWORD, ellers en genereret adgangskode skrevet til
  <data>/initial-admin-password.txt (chmod 600) som SKAL skiftes ved første login.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..storage.db import Database
from .errors import ServiceError

log = logging.getLogger(__name__)

ROLES = ("viewer", "operator", "panel", "engineer", "admin")
# Rettighedsniveau: "panel" (driftpanel) har præcis operatørens rettigheder — forskellen er kun at web-UI'et viser
# drifttegningen alene (ingen menu). Rettighederne håndhæves her, aldrig ud fra hvad UI'et viser.
ROLE_LEVEL = {"viewer": 0, "operator": 1, "panel": 1, "engineer": 2, "admin": 3}
SCOPABLE_ROLES = ("viewer", "operator", "panel")  # tekniker og admin ser altid alle tegninger
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{2,32}\Z")
MIN_PASSWORD = 10
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}

# Login-låsning: efter MAX_FAILS fejl inden for vinduet låses (bruger, IP) i LOCK_S sekunder.
MAX_FAILS = 5
FAIL_WINDOW_S = 300
LOCK_S = 60
# Pr. IP på tværs af brugernavne (kodeanalyse 2, G1): ellers kunne fejlede logins med skiftende brugernavne holde
# serveren travl med scrypt. Over grænsen afvises der med 429 uden at beregne noget.
IP_MAX_FAILS = 20
IP_FAIL_WINDOW_S = 300
# Højst så mange adgangskode-tjek (scrypt) ad gangen; de køres i en tråd, men begrænses, så en byge ikke æder CPU'en
VERIFY_CONCURRENCY = 2
VERIFY_WAIT_S = 15


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return "scrypt${n}${r}${p}${salt}${hash}".format(
        **_SCRYPT, salt=base64.b64encode(salt).decode(), hash=base64.b64encode(digest).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), dklen=32, n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(calc, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def role_at_least(role: str, required: str) -> bool:
    return role in ROLE_LEVEL and ROLE_LEVEL[role] >= ROLE_LEVEL[required]


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


MAX_PALETTE = 60
_SYMBOL_ID = re.compile(r"[a-z0-9_]{1,40}")


def palette_key(username: str) -> str:
    """Indstillingen med brugerens "Mine symboler" (bibliotekets symbol-id'er i den valgte rækkefølge)."""
    return f"palette:{username}"


@dataclass
class CurrentUser:
    username: str
    role: str
    must_change_password: bool
    token_hash: str
    drawings: frozenset[str] | None = None  # None = alle tegninger

    def public(self) -> dict[str, Any]:
        return {"username": self.username, "role": self.role, "must_change_password": self.must_change_password,
                "drawings": sorted(self.drawings) if self.drawings is not None else None}


def check_password_rules(password: Any, username: str = "") -> str:
    if not isinstance(password, str) or not password.strip():
        raise ServiceError(400, "Adgangskoden må ikke være tom")
    if len(password) < MIN_PASSWORD:
        raise ServiceError(400, f"Adgangskoden skal være mindst {MIN_PASSWORD} tegn")
    if username and password.strip().lower() == username.lower():
        raise ServiceError(400, "Adgangskoden må ikke være lig brugernavnet")
    return password


class AuthService:
    def __init__(self, db: Database, data_dir: Path, *, session_ttl_s: float = 8 * 3600):
        self.db = db
        self.data_dir = data_dir
        self.session_ttl_s = session_ttl_s
        self._fails: dict[tuple[str, str], list[float]] = {}
        self._locked_until: dict[tuple[str, str], float] = {}
        self._ip_fails: dict[str, list[float]] = {}
        self._guard = threading.Lock()   # login kører i tråde (G1): tællerne opdateres under lås
        self._verify_slots = threading.BoundedSemaphore(VERIFY_CONCURRENCY)
        self._dummy_hash = hash_password(secrets.token_hex(16))

    def verify(self, password: str, stored: str) -> bool:
        """Tjek en adgangskode/PIN med højst VERIFY_CONCURRENCY samtidige scrypt-beregninger. Kaldes fra en tråd."""
        if not self._verify_slots.acquire(timeout=VERIFY_WAIT_S):
            raise ServiceError(503, "Serveren er optaget — prøv igen om lidt")
        try:
            return verify_password(password, stored)
        finally:
            self._verify_slots.release()

    # --------------------------------------------------------------- opstart

    def bootstrap(self, admin_password: str | None) -> None:
        if self.db.count_users() > 0:
            return
        if admin_password:
            check_password_rules(admin_password, "admin")
            self.db.insert_user("admin", {"password_hash": hash_password(admin_password), "role": "admin"})
            log.warning("Oprettede bruger 'admin' med adgangskode fra SCADA_ADMIN_PASSWORD")
            return
        password = secrets.token_urlsafe(12)
        path = self.data_dir / "initial-admin-password.txt"
        path.write_text(password + "\n", encoding="utf-8")
        if os.name == "posix":
            os.chmod(path, 0o600)
        self.db.insert_user("admin", {"password_hash": hash_password(password), "role": "admin",
                                      "must_change_password": True})
        log.warning("Oprettede bruger 'admin' — engangsadgangskode i %s (skal skiftes ved første login)", path)

    # ----------------------------------------------------------------- login

    def login(self, username: Any, password: Any, ip: str) -> tuple[str, CurrentUser]:
        if not isinstance(username, str) or not isinstance(password, str) or not username.strip() or not password:
            raise ServiceError(400, "Brugernavn og adgangskode skal udfyldes")
        username = username.strip()
        key = (username.lower(), ip)
        now = time.time()
        with self._guard:
            locked = self._locked_until.get(key, 0) - now
            ip_fails = [t for t in self._ip_fails.get(ip, []) if now - t < IP_FAIL_WINDOW_S]
            self._ip_fails[ip] = ip_fails
        if locked > 0:
            raise ServiceError(429, f"For mange fejlede login-forsøg — prøv igen om {int(locked) + 1} s")
        if len(ip_fails) >= IP_MAX_FAILS:
            wait = int(IP_FAIL_WINDOW_S - (now - ip_fails[0])) + 1
            raise ServiceError(429, f"For mange fejlede login-forsøg fra denne adresse — prøv igen om {wait} s")
        user = self.db.get_user(username)
        # Verificér altid (også for ukendt bruger), så svartiden ikke afslører om brugeren findes.
        ok = self.verify(password, user["password_hash"] if user else self._dummy_hash)
        if not user or not ok or user["disabled"]:
            with self._guard:
                fails = [t for t in self._fails.get(key, []) if now - t < FAIL_WINDOW_S] + [now]
                self._fails[key] = fails
                if len(fails) >= MAX_FAILS:
                    self._locked_until[key] = now + LOCK_S
                    self._fails.pop(key, None)
                self._ip_fails.setdefault(ip, []).append(now)
            log.warning("Fejlet login for '%s' fra %s", username, ip)
            if user and ok and user["disabled"]:
                raise ServiceError(403, "Brugeren er deaktiveret")
            raise ServiceError(401, "Forkert brugernavn eller adgangskode")
        with self._guard:
            self._fails.pop(key, None)
        token = secrets.token_urlsafe(32)
        self.db.purge_expired_sessions(now)
        self.db.insert_session(_token_hash(token), user["username"], now + self.session_ttl_s, ip)
        log.info("Login: '%s' (%s) fra %s", user["username"], user["role"], ip)
        return token, CurrentUser(user["username"], user["role"], user["must_change_password"], _token_hash(token),
                                  self._scope(user))

    def logout(self, token: str | None) -> None:
        if token:
            self.db.delete_session(_token_hash(token))

    def session_user(self, token: str | None) -> CurrentUser | None:
        if not token:
            return None
        th = _token_hash(token)
        session = self.db.get_session(th)
        now = time.time()
        if session is None or session["expires_at"] < now:
            return None
        user = self.db.get_user(session["username"])
        if user is None or user["disabled"]:
            return None
        if session["expires_at"] - now < self.session_ttl_s - 60:  # forny højst én gang i minuttet
            self.db.touch_session(th, now + self.session_ttl_s)
        return CurrentUser(user["username"], user["role"], user["must_change_password"], th, self._scope(user))

    def _scope(self, user: dict[str, Any]) -> frozenset[str] | None:
        if user["role"] not in SCOPABLE_ROLES or not user.get("scoped"):
            return None
        existing = {d["id"] for d in self.db.list_drawings()}
        return frozenset(d for d in self.db.get_user_drawings(user["username"]) if d in existing)

    def _validate_drawings(self, value: Any) -> list[str] | None:
        """None = alle tegninger; ellers en liste af eksisterende tegnings-id'er (tom liste = ingen)."""
        if value is None:
            return None
        if not isinstance(value, list) or not all(isinstance(d, str) for d in value):
            raise ServiceError(400, "drawings skal være null (alle) eller en liste af tegnings-id'er")
        existing = {d["id"] for d in self.db.list_drawings()}
        unknown = sorted(set(value) - existing)
        if unknown:
            raise ServiceError(400, f"Ukendte tegninger: {', '.join(unknown)}")
        return sorted(set(value))

    def change_own_password(self, current: CurrentUser, old: Any, new: Any) -> None:
        user = self.db.get_user(current.username)
        if user is None or not isinstance(old, str) or not self.verify(old, user["password_hash"]):
            raise ServiceError(400, "Den nuværende adgangskode er forkert")
        check_password_rules(new, current.username)
        if self.verify(new, user["password_hash"]):
            raise ServiceError(400, "Den nye adgangskode skal være forskellig fra den nuværende")
        self.db.update_user_guarded(current.username, {"password_hash": hash_password(new),
                                                       "must_change_password": False}, keep_admin=False)
        self.db.delete_user_sessions(current.username, except_hash=current.token_hash)
        initial = self.data_dir / "initial-admin-password.txt"
        if initial.exists() and current.username == "admin":
            initial.unlink()
        log.info("Bruger '%s' skiftede adgangskode", current.username)

    # ------------------------------------------------------------- brugere

    def list_users(self) -> list[dict[str, Any]]:
        out = []
        for u in self.db.list_users():
            row = {k: u[k] for k in ("username", "role", "disabled", "must_change_password", "created_at")}
            row["drawings"] = self.db.get_user_drawings(u["username"]) if u.get("scoped") else None
            out.append(row)
        return out

    def create_user(self, data: dict[str, Any]) -> dict[str, Any]:
        username = data.get("username")
        if not isinstance(username, str) or not USERNAME_RE.match(username.strip()):
            raise ServiceError(400, "Brugernavn skal være 2-32 tegn: bogstaver, tal, _ . -")
        username = username.strip()
        existing = self.db.get_user_ci(username)
        if existing is not None:
            raise ServiceError(409, f"Brugeren '{existing['username']}' findes allerede"
                                    + ("" if existing["username"] == username else " (store/små bogstaver er ens)"))
        role = data.get("role")
        if role not in ROLES:
            raise ServiceError(400, f"Ukendt rolle '{role}' (brug {', '.join(ROLES)})")
        password = check_password_rules(data.get("password"), username)
        drawings = self._validate_drawings(data.get("drawings"))
        self.db.insert_user(username, {"password_hash": hash_password(password), "role": role,
                                       "must_change_password": True})
        if drawings is not None:
            self.db.update_user_guarded(username, {"scoped": True}, keep_admin=False)
            self.db.set_user_drawings(username, drawings)
        log.info("Bruger '%s' oprettet med rollen %s", username, role)
        return next(u for u in self.list_users() if u["username"] == username)

    def update_user(self, actor: CurrentUser, username: str, data: dict[str, Any]) -> dict[str, Any]:
        changes: dict[str, Any] = {}
        if data.get("role") is not None:
            if data["role"] not in ROLES:
                raise ServiceError(400, f"Ukendt rolle '{data['role']}'")
            changes["role"] = data["role"]
        if data.get("disabled") is not None:
            changes["disabled"] = bool(data["disabled"])
        if data.get("password") is not None:
            changes["password_hash"] = hash_password(check_password_rules(data["password"], username))
            changes["must_change_password"] = True
        drawings: list[str] | None = None
        scope_given = "drawings" in data
        if scope_given:
            drawings = self._validate_drawings(data["drawings"])
            changes["scoped"] = drawings is not None
        result = self.db.update_user_guarded(username, changes, keep_admin=True)
        if result == "missing":
            raise ServiceError(404, f"Brugeren '{username}' findes ikke")
        if result == "last_admin":
            raise ServiceError(409, "Ændringen ville efterlade systemet uden en aktiv administrator")
        if scope_given:
            self.db.set_user_drawings(username, drawings or [])
            changes.pop("scoped", None)  # tegningsadgang slår igennem ved næste kald — ingen grund til at logge ud
        if changes:
            # Rolle/adgangskode/deaktivering skal slå igennem straks — også for igangværende sessioner.
            keep = actor.token_hash if actor.username == username and "password_hash" not in changes else None
            self.db.delete_user_sessions(username, except_hash=keep)
            log.info("Bruger '%s' ændret af '%s': %s", username, actor.username, sorted(changes))
        return next(u for u in self.list_users() if u["username"] == username)

    def delete_user(self, actor: CurrentUser, username: str) -> None:
        result = self.db.delete_user_guarded(username)
        if result == "missing":
            raise ServiceError(404, f"Brugeren '{username}' findes ikke")
        if result == "last_admin":
            raise ServiceError(409, "Den sidste aktive administrator kan ikke slettes")
        self.db.delete_user_scope(username)
        self.db.set_setting(palette_key(username), None)   # brugerens "Mine symboler" (v0.78.0)
        log.info("Bruger '%s' slettet af '%s'", username, actor.username)

    # ------------------------------------------------------------ "Mine symboler" i Tegn (v0.78.0)

    def palette(self, user: CurrentUser) -> list[str]:
        raw = self.db.get_setting(palette_key(user.username))
        try:
            data = json.loads(raw) if raw else []
        except ValueError:
            return []   # ødelagt værdi: start forfra hellere end at fejle
        return [s for s in data if isinstance(s, str) and _SYMBOL_ID.fullmatch(s)][:MAX_PALETTE] if isinstance(data, list) else []

    def set_palette(self, user: CurrentUser, symbols: list[str]) -> list[str]:
        clean: list[str] = []
        for s in symbols:
            if not isinstance(s, str) or not _SYMBOL_ID.fullmatch(s):
                raise ServiceError(400, f"Ugyldigt symbol-id: {s!r}")
            if s not in clean:
                clean.append(s)
        if len(clean) > MAX_PALETTE:
            raise ServiceError(400, f"Højst {MAX_PALETTE} symboler i Mine symboler")
        self.db.set_setting(palette_key(user.username), json.dumps(clean) if clean else None)
        return clean
