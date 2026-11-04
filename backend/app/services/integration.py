"""Integrationer (lag 3): API-nøgler til maskiner (Node-RED, Home Assistant, scripts …) og et stabilt, afgrænset læse-API.

- En **nøgle** er en egen slags principal: den kan kun bruge `/api/v1/integration/*` og aldrig en session eller et admin-endpoint.
- Nøglen genereres i browseren (`hv_` + 43 tegn) og sendes hertil; serveren gemmer KUN SHA-256-kontrolsummen og returnerer aldrig
  værdien (som `/metrics`-tokenet). Den kan have udløbsdato, IP-liste og afgrænsning til valgte tags/præfikser.
- Integrationer læser kun fra live-cachen, trend-databasen og alarmmotoren — aldrig direkte fra en PLC.
- Hastighedsgrænse pr. nøgle (standard 20 kald/s, burst 40), tællere til /metrics, audit af nøgle-ændringer.

Fase 1 (v3.21): kun læsning. Styring (skrivning) kommer som et valgfrit trin 3 gennem betjeningstjenesten.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import math
import re
import secrets as _secrets
import sqlite3
import threading
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..config import read_version
from ..storage.db import Database
from .alarms import AlarmService
from .errors import ServiceError
from .tagsource import parse_source

log = logging.getLogger(__name__)

KEY_RE = re.compile(r"^hv_[A-Za-z0-9_-]{43}$")
NAME_RE = re.compile(r"^[A-Za-z0-9ÆØÅæøå][A-Za-z0-9ÆØÅæøå _.-]{1,62}[A-Za-z0-9ÆØÅæøå]$")
PREFIX_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,40}$")
MAX_KEYS = 50
MAX_SCOPE_ITEMS = 500
TOUCH_EVERY_S = 60.0           # "sidst brugt" skrives højst én gang pr. minut pr. nøgle (ingen databaseskrivning pr. kald)
RATE_PER_S = 20.0
RATE_BURST = 40
MAX_HISTORY_POINTS = 2000
MAX_SPAN_S = 90 * 86400
LOG_EVERY_S = 60.0
FAIL_WINDOW_S = 60.0
FAIL_LIMIT = 30                # afviste kald pr. IP pr. minut, før der svares 429 uden at slå noget op (DoS-værn)
MAX_ABS_TIME = 365 * 86400      # historik: tidspunkter højst et år ude i fremtiden
STREAM_INTERVAL_S = 0.5         # SSE: ændringer samles og sendes højst så ofte (standard; 0,1-60 pr. forbindelse)
STREAM_HEARTBEAT_S = 15.0       # kommentarlinje, når intet er sendt — holder forbindelsen åben gennem nginx og netværk
STREAM_REVALIDATE_S = 10.0      # nøglen og afgrænsningen tjekkes igen så ofte under en åben strøm
MAX_STREAMS_PER_KEY = 5
MAX_STREAMS_TOTAL = 50
STREAM_ALARM_QUEUE = 200


def _bad(message: str, status: int = 400) -> ServiceError:
    return ServiceError(status, message)


@dataclass
class Principal:
    """En godkendt nøgle (aldrig en bruger)."""
    id: str
    name: str
    scope: dict[str, Any]

    def allows(self, tag: str) -> bool:
        if self.scope.get("all"):
            return True
        return tag in self.scope.get("tags", ()) or any(tag.startswith(p) for p in self.scope.get("prefixes", ()))


@dataclass
class KeyStats:
    requests: int = 0
    errors: int = 0
    rate_limited: int = 0
    streams_opened: int = 0
    stream_events: int = 0


@dataclass
class StreamState:
    """En åben SSE-forbindelse: egen kø med værdi-ændringer (fra live-cachen) og alarmhændelser."""
    id: str
    key_id: str
    principal: Principal
    ip: str
    allowed: set[str]
    cache_q: Any
    alarm_q: Any
    overflow: bool = False


@dataclass
class _Bucket:
    tokens: float = float(RATE_BURST)
    last: float = field(default_factory=time.monotonic)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class IntegrationService:
    def __init__(self, db: Database, tags: Any, cache: Any, alarms: AlarmService, trend_db: Any = None, *, instance: str = "",
                 rate_per_s: float = RATE_PER_S, rate_burst: int = RATE_BURST) -> None:
        self.db = db
        self.tags = tags              # TagService
        self.cache = cache            # LiveCache
        self.alarms = alarms
        self.trend_db = trend_db      # sættes når den findes (oprettes senere i main)
        self.instance = instance
        self.rate_per_s, self.rate_burst = rate_per_s, rate_burst
        self.stats: dict[str, KeyStats] = {}
        self.auth_failures = 0
        self._buckets: dict[str, _Bucket] = {}
        self._last_touch: dict[str, float] = {}
        self._last_log: dict[str, float] = {}
        self._ip_fails: dict[str, list[float]] = {}     # ip → [antal, vinduets start]
        self._streams: dict[str, StreamState] = {}
        self._lock = threading.Lock()   # kald godkendes i FastAPI's trådpulje: hastighedsgrænse og tællere er read-modify-write

    # ------------------------------------------------------------- nøgle-administration (admin)

    @staticmethod
    def _decode_scope(raw: str) -> dict[str, Any]:
        try:
            s = json.loads(raw or "{}")
        except ValueError:
            s = {}
        return {"all": bool(s.get("all")), "tags": [str(t) for t in s.get("tags", [])], "prefixes": [str(p) for p in s.get("prefixes", [])]}

    def _public(self, row: dict[str, Any]) -> dict[str, Any]:
        st = self.stats.get(row["id"], KeyStats())
        return {"id": row["id"], "name": row["name"], "prefix": row["prefix"], "scope": self._decode_scope(row["scope"]),
                "ip_allow": [x for x in row["ip_allow"].split(",") if x], "expires_at": row["expires_at"],
                "disabled": bool(row["disabled"]), "created_at": row["created_at"], "created_by": row["created_by"],
                "last_used_at": row["last_used_at"], "last_ip": row["last_ip"],
                "expired": row["expires_at"] is not None and row["expires_at"] <= time.time(),
                "stats": {"requests": st.requests, "errors": st.errors, "rate_limited": st.rate_limited}}

    def list_keys(self) -> list[dict[str, Any]]:
        return [self._public(r) for r in self.db.list_api_keys()]

    def _validate_scope(self, scope: Any) -> dict[str, Any]:
        if not isinstance(scope, dict):
            raise _bad("Afgrænsning mangler")
        out: dict[str, Any] = {"all": bool(scope.get("all")), "tags": [], "prefixes": []}
        if out["all"]:
            return out
        tags, prefixes = scope.get("tags") or [], scope.get("prefixes") or []
        if not isinstance(tags, list) or not isinstance(prefixes, list):
            raise _bad("Tags og præfikser skal være lister")
        if not tags and not prefixes:
            raise _bad("Vælg mindst ét tag eller præfiks — eller alle tags")
        if len(tags) + len(prefixes) > MAX_SCOPE_ITEMS:
            raise _bad(f"Højst {MAX_SCOPE_ITEMS} tags/præfikser pr. nøgle")
        known = {t["name"] for t in self.db.list_tags()}
        unknown = sorted({str(t) for t in tags} - known)
        if unknown:
            raise _bad("Ukendte tags: " + ", ".join(unknown[:5]) + (" …" if len(unknown) > 5 else ""))
        for p in prefixes:
            if not isinstance(p, str) or not PREFIX_RE.match(p):
                raise _bad(f"Ugyldigt præfiks '{p}' (1-40 tegn: bogstaver, tal, _ . : -)")
        out["tags"] = sorted({str(t) for t in tags})
        out["prefixes"] = sorted(set(prefixes))
        return out

    @staticmethod
    def _validate_ips(items: Any) -> str:
        if items in (None, ""):
            return ""
        if not isinstance(items, list) or len(items) > 20:
            raise _bad("IP-listen skal være op til 20 adresser eller netværk")
        nets = []
        for raw in items:
            try:
                nets.append(str(ipaddress.ip_network(str(raw).strip(), strict=False)))
            except ValueError:
                raise _bad(f"Ugyldig IP-adresse eller netværk: '{raw}'") from None
        return ",".join(nets)

    @staticmethod
    def _validate_expiry(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= time.time():
            raise _bad("Udløbsdatoen skal ligge i fremtiden")
        if value > time.time() + 20 * 365 * 86400:
            raise _bad("Udløbsdatoen er for langt ude (højst 20 år)")
        return float(value)

    def _validate_name(self, name: Any, current_id: str | None = None) -> str:
        if not isinstance(name, str) or not NAME_RE.match(name.strip()):
            raise _bad("Navnet skal være 3-64 tegn: bogstaver, tal, mellemrum, _ . -")
        name = name.strip()
        for r in self.db.list_api_keys():
            if r["name"].lower() == name.lower() and r["id"] != current_id:
                raise _bad(f"Der findes allerede en nøgle med navnet '{r['name']}'", 409)
        return name

    def create(self, actor: str, body: dict[str, Any]) -> dict[str, Any]:
        """Opret en nøgle. `body["key"]` er genereret i browseren; kun kontrolsummen gemmes, og værdien returneres aldrig."""
        key = body.get("key")
        if not isinstance(key, str) or not KEY_RE.match(key):
            raise _bad("Nøglen skal være hv_ efterfulgt af 43 tegn (genereres af siden)")
        if self.db.count_api_keys() >= MAX_KEYS:
            raise _bad(f"Der kan højst være {MAX_KEYS} nøgler — tilbagekald en, der ikke bruges", 409)
        name = self._validate_name(body.get("name"))
        scope = self._validate_scope(body.get("scope"))
        ips = self._validate_ips(body.get("ip_allow"))
        expires = self._validate_expiry(body.get("expires_at"))
        digest = hash_key(key)
        if self.db.get_api_key_by_hash(digest) is not None:
            raise _bad("Denne nøgle er allerede i brug — opret en ny", 409)
        row = {"id": "k_" + _secrets.token_hex(6), "name": name, "key_hash": digest, "prefix": key[:11], "scope": json.dumps(scope),
               "ip_allow": ips, "expires_at": expires, "disabled": False, "created_at": time.time(), "created_by": actor}
        try:
            self.db.insert_api_key(row)
        except sqlite3.IntegrityError:           # samtidig oprettelse med samme navn eller nøgle
            raise _bad("Der findes allerede en nøgle med dette navn (eller denne nøgle) — prøv igen", 409) from None
        log.warning("API-nøgle '%s' (%s…) oprettet af %s (afgrænsning: %s)", name, row["prefix"], actor,
                    "alle tags" if scope["all"] else f"{len(scope['tags'])} tags, {len(scope['prefixes'])} præfikser")
        return self._public(self.db.get_api_key(row["id"]))  # type: ignore[arg-type]

    def update(self, key_id: str, body: dict[str, Any]) -> dict[str, Any]:
        row = self.db.get_api_key(key_id)
        if row is None:
            raise _bad("Nøglen findes ikke", 404)
        fields: dict[str, Any] = {}
        if "name" in body:
            fields["name"] = self._validate_name(body["name"], key_id)
        if "scope" in body:
            fields["scope"] = json.dumps(self._validate_scope(body["scope"]))
        if "ip_allow" in body:
            fields["ip_allow"] = self._validate_ips(body["ip_allow"])
        if "expires_at" in body:
            fields["expires_at"] = self._validate_expiry(body["expires_at"])
        if "disabled" in body:
            if not isinstance(body["disabled"], bool):
                raise _bad("'disabled' skal være sand eller falsk")
            fields["disabled"] = body["disabled"]
        if fields:
            try:
                self.db.update_api_key(key_id, fields)
            except sqlite3.IntegrityError:
                raise _bad("Der findes allerede en nøgle med dette navn", 409) from None
            self._buckets.pop(key_id, None)
        return self._public(self.db.get_api_key(key_id))  # type: ignore[arg-type]

    def delete(self, key_id: str) -> dict[str, Any]:
        row = self.db.get_api_key(key_id)
        if row is None:
            raise _bad("Nøglen findes ikke", 404)
        self.db.delete_api_key(key_id)
        for d in (self._buckets, self._last_touch, self.stats):
            d.pop(key_id, None)
        log.warning("API-nøgle '%s' (%s…) tilbagekaldt", row["name"], row["prefix"])
        return {"name": row["name"], "prefix": row["prefix"]}

    # ------------------------------------------------------------- godkendelse (hver forespørgsel)

    def _fail(self, ip: str, why: str) -> None:
        with self._lock:
            self.auth_failures += 1
            now = time.monotonic()
            entry = self._ip_fails.get(ip)
            if entry is None or now - entry[1] > FAIL_WINDOW_S:
                if len(self._ip_fails) > 1000:                      # ingen ubegrænset vækst
                    self._ip_fails = {k: v for k, v in self._ip_fails.items() if now - v[1] <= FAIL_WINDOW_S}
                self._ip_fails[ip] = entry = [0.0, now]
            entry[0] += 1
            log_it = now - self._last_log.get(ip, -LOG_EVERY_S) >= LOG_EVERY_S      # ikke en logpost pr. kald
            if log_it:
                if len(self._last_log) > 1000:
                    self._last_log = {k: t for k, t in self._last_log.items() if now - t < LOG_EVERY_S}
                self._last_log[ip] = now
        if log_it:
            log.warning("Afvist integrationskald fra %s: %s", ip, why)

    def _ip_blocked(self, ip: str) -> float:
        """→ sekunder at vente, hvis IP'en har haft for mange afviste kald i det seneste minut (slås ikke op i databasen), ellers 0."""
        with self._lock:
            entry = self._ip_fails.get(ip)
            if entry is None:
                return 0.0
            age = time.monotonic() - entry[1]
            if age > FAIL_WINDOW_S:
                self._ip_fails.pop(ip, None)
                return 0.0
            return (FAIL_WINDOW_S - age) if entry[0] >= FAIL_LIMIT else 0.0

    def authenticate(self, key: str | None, ip: str) -> Principal:
        """→ Principal, ellers ServiceError (401 ukendt/forkert, 403 deaktiveret/udløbet/IP, 429 hastighedsgrænse)."""
        unauthorized = {"WWW-Authenticate": "Bearer"}
        blocked = self._ip_blocked(ip)
        if blocked > 0:
            raise ServiceError(429, "For mange afviste kald fra denne adresse — vent lidt", headers={"Retry-After": str(max(1, int(blocked + 0.999)))})
        if not key or not KEY_RE.match(key):
            self._fail(ip, "manglende eller forkert nøgle")
            raise ServiceError(401, "Manglende eller ugyldig API-nøgle (Authorization: Bearer hv_…)", headers=unauthorized)
        digest = hash_key(key)
        row = self.db.get_api_key_by_hash(digest)
        if row is None or not hmac.compare_digest(row["key_hash"], digest):
            self._fail(ip, "ukendt nøgle")
            raise ServiceError(401, "Manglende eller ugyldig API-nøgle (Authorization: Bearer hv_…)", headers=unauthorized)
        refused = None
        if row["disabled"]:
            refused = (403, "Nøglen er deaktiveret", "deaktiveret")
        elif row["expires_at"] is not None and row["expires_at"] <= time.time():
            refused = (403, "Nøglen er udløbet", "udløbet")
        elif row["ip_allow"] and not self._ip_allowed(ip, row["ip_allow"]):
            refused = (403, "Nøglen må ikke bruges fra denne IP-adresse", "IP-adressen er ikke tilladt for")
        if refused is not None:
            with self._lock:
                self.stats.setdefault(row["id"], KeyStats()).errors += 1
            self._fail(ip, f"{refused[2]} nøgle '{row['name']}'" if refused[2] != "IP-adressen er ikke tilladt for" else f"{refused[2]} nøglen '{row['name']}'")
            raise ServiceError(refused[0], refused[1])
        with self._lock:
            st = self.stats.setdefault(row["id"], KeyStats())
            wait = self._take_token(row["id"])
            if wait > 0:
                st.rate_limited += 1
                st.errors += 1
            else:
                st.requests += 1
            now = time.time()
            touch = wait <= 0 and now - self._last_touch.get(row["id"], 0.0) >= TOUCH_EVERY_S
            if touch:
                self._last_touch[row["id"]] = now
        if wait > 0:
            raise ServiceError(429, f"For mange kald — vent {wait:.1f} s (grænse {self.rate_per_s:g} kald/s)",
                               headers={"Retry-After": str(max(1, int(wait + 0.999)))})
        if touch:
            self.db.touch_api_key(row["id"], now, ip)
        return Principal(row["id"], row["name"], self._decode_scope(row["scope"]))

    @staticmethod
    def _ip_allowed(ip: str, allow: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(addr in ipaddress.ip_network(n, strict=False) for n in allow.split(",") if n)

    def _take_token(self, key_id: str) -> float:
        """Token-spand pr. nøgle. → 0 hvis kaldet er tilladt, ellers sekunder at vente."""
        b = self._buckets.setdefault(key_id, _Bucket(tokens=float(self.rate_burst)))
        now = time.monotonic()
        b.tokens = min(float(self.rate_burst), b.tokens + (now - b.last) * self.rate_per_s)
        b.last = now
        if b.tokens >= 1:
            b.tokens -= 1
            return 0.0
        return (1 - b.tokens) / self.rate_per_s

    def count_error(self, p: Principal) -> None:
        with self._lock:
            self.stats.setdefault(p.id, KeyStats()).errors += 1

    def metrics(self) -> dict[str, Any]:
        """Tællere til /metrics og Status: nøgler (navn → tællere) og afviste kald."""
        names = {r["id"]: r["name"] for r in self.db.list_api_keys()}
        return {"keys": len(names), "auth_failures": self.auth_failures, "streams": len(self._streams),
                "per_key": {names[i]: {"requests": s.requests, "errors": s.errors, "rate_limited": s.rate_limited,
                                       "stream_events": s.stream_events}
                            for i, s in self.stats.items() if i in names}}

    # ------------------------------------------------------------- læse-API

    def allowed_names(self, p: Principal) -> list[str]:
        return [t["name"] for t in self.db.list_tags() if p.allows(t["name"])]

    def info(self, p: Principal) -> dict[str, Any]:
        v = read_version()
        return {"instance": self.instance, "version": v.get("version", ""), "time": _iso(time.time()),
                "key": {"name": p.name, "scope": {"all": p.scope["all"], "tags": len(p.scope["tags"]), "prefixes": len(p.scope["prefixes"])},
                        "write": False},
                "limits": {"requests_per_s": self.rate_per_s, "burst": self.rate_burst, "history_points": MAX_HISTORY_POINTS}}

    def points(self, p: Principal) -> list[dict[str, Any]]:
        """De punkter nøglen må se — aldrig PLC-adresser eller kilder."""
        out = []
        for t in self.db.list_tags():
            if not p.allows(t["name"]):
                continue
            try:
                kind = parse_source(t["source"]).kind
            except Exception:       # ugyldig kilde i databasen: punktet vises som tal
                kind = ""
            out.append({"name": t["name"], "description": t["description"], "unit": t["unit"],
                        "type": "bool" if kind in ("coil", "di") else "number", "decimals": t["decimals"],
                        "min": t["min"], "max": t["max"], "history": bool(t.get("trend")), "writable": False})
        return out

    def values(self, p: Principal, names: list[str] | None) -> dict[str, Any]:
        allowed = set(self.allowed_names(p))
        wanted = [n for n in (names if names is not None else sorted(allowed)) if n in allowed]
        snap = self.cache.snapshot(wanted)
        return {"time": _iso(time.time()),
                # kvaliteten siger, om værdien er brugbar — selve fejlteksten (PLC-navn, adresse, httpx-fejl) udleveres aldrig
                "values": {n: {"v": v["value"], "q": v["quality"], "ts": v["ts"]} for n, v in snap.items()}}

    async def history(self, p: Principal, tag: str, start: float | None, end: float | None, points: int) -> dict[str, Any]:
        if tag not in set(self.allowed_names(p)):
            raise _bad(f"Tag '{tag}' findes ikke eller er ikke tilladt for nøglen", 404)
        row = next((t for t in self.db.list_tags() if t["name"] == tag), None)
        if row is None or not row.get("trend"):
            raise _bad(f"Der gemmes ikke historik for '{tag}' (slå historik til under Tags)", 404)
        if self.trend_db is None:
            raise _bad("Historik er ikke tilgængelig", 503)
        now = time.time()
        end = now if end is None else end
        start = end - 3600 if start is None else start
        for t in (start, end):
            if not math.isfinite(t) or t < 0 or t > now + MAX_ABS_TIME:
                raise _bad("Ugyldigt tidspunkt (Unix-sekunder, højst et år ude i fremtiden)")
        if not start < end:
            raise _bad("Starttidspunktet skal ligge før sluttidspunktet")
        if end - start > MAX_SPAN_S:
            raise _bad(f"Perioden er for lang (højst {MAX_SPAN_S // 86400} dage)")
        points = max(10, min(points, MAX_HISTORY_POINTS))
        step = (end - start) / points
        series = await asyncio.to_thread(self.trend_db.series, tag, start, end, step)
        return {"tag": tag, "start": _iso(start), "end": _iso(end), "step_s": step, "unit": row["unit"],
                "columns": ["time", "mean", "min", "max"],
                "rows": [[_iso(r[0]), r[1], r[2], r[3]] for r in series]}

    @staticmethod
    def _alarm_texts(a: dict[str, Any]) -> tuple[str, str]:
        """(plc, besked) til udlevering: en tag-løs kommunikationsalarm får en generisk tekst — PLC-fejlteksten udleveres aldrig."""
        if not a["tag"] and a.get("kind") == "comm":
            return a["plc"], f"PLC {a['plc']}: kommunikationsfejl"
        return "", a["message"]

    def alarms_for(self, p: Principal) -> list[dict[str, Any]]:
        """Alarmer inden for nøglens afgrænsning. En nøgle med valgte tags ser kun alarmer på DE tags. Kun en nøgle med *alle tags* ser
        også tag-løse alarmer (PLC-kommunikation, serverens egne SYS-alarmer) — PLC-fejlteksten (navn, adresse, httpx-fejl) udleveres aldrig."""
        rows = self.alarms.active(None)
        if not p.scope["all"]:
            allowed = set(self.allowed_names(p))
            rows = [a for a in rows if a["tag"] and a["tag"] in allowed]
        out = []
        for a in rows:
            plc, message = self._alarm_texts(a)
            out.append({"key": a["key"], "tag": a["tag"], "plc": plc, "kind": a["kind"], "level": a["level"], "priority": a["priority"],
                        "state": a["state"], "message": message, "raised_at": _iso(a["raised_at"]), "acknowledged": a["state"] == "active_ack"})
        return out

    # ------------------------------------------------------------- SSE-strøm (Server-Sent Events)

    def open_stream(self, p: Principal, ip: str) -> StreamState:
        """Registrér en strøm (loft pr. nøgle og i alt). Kaldes FØR svaret begynder, så en afvisning bliver en rigtig 429."""
        mine = sum(1 for s in self._streams.values() if s.key_id == p.id)
        if mine >= MAX_STREAMS_PER_KEY or len(self._streams) >= MAX_STREAMS_TOTAL:
            with self._lock:
                self.stats.setdefault(p.id, KeyStats()).errors += 1
            raise ServiceError(429, f"For mange åbne strømme (højst {MAX_STREAMS_PER_KEY} pr. nøgle, {MAX_STREAMS_TOTAL} i alt)",
                               headers={"Retry-After": "5"})
        s = StreamState(id=_secrets.token_hex(6), key_id=p.id, principal=p, ip=ip, allowed=set(self.allowed_names(p)),
                        cache_q=self.cache.subscribe(maxsize=100), alarm_q=asyncio.Queue(maxsize=STREAM_ALARM_QUEUE))
        self._streams[s.id] = s
        with self._lock:
            self.stats.setdefault(p.id, KeyStats()).streams_opened += 1
        return s

    def close_stream(self, s: StreamState) -> None:
        self.cache.unsubscribe(s.cache_q)
        self._streams.pop(s.id, None)

    def on_alarm_event(self, row: dict[str, Any], event: str, now: float) -> None:
        """Lytter på alarmmotoren (kaldes på event-loopet): hændelsen lægges i køen hos de strømme, der må se den."""
        if not self._streams or event not in ("raise", "clear", "change"):
            return
        plc, message = self._alarm_texts(row)
        entry = {"event": event, "alarm": {"key": row["key"], "tag": row["tag"], "plc": plc, "kind": row.get("kind", ""), "level": row["level"],
                                           "priority": row["priority"], "message": message, "at": _iso(now)}}
        for s in list(self._streams.values()):
            if not (s.principal.scope["all"] or (row["tag"] and row["tag"] in s.allowed)):
                continue
            try:
                s.alarm_q.put_nowait(entry)
            except asyncio.QueueFull:
                s.overflow = True          # klienten er for langsom: den får et nyt øjebliksbillede i stedet for en afbrudt række

    def revalidate(self, s: StreamState) -> str | None:
        """Tjek nøglen igen under en åben strøm. → årsag hvis strømmen skal lukkes (tilbagekaldt/deaktiveret/udløbet/IP), ellers None;
        afgrænsningen opdateres (nye tags kommer med, fjernede forsvinder)."""
        row = self.db.get_api_key(s.key_id)
        if row is None:
            return "nøglen er tilbagekaldt"
        if row["disabled"]:
            return "nøglen er deaktiveret"
        if row["expires_at"] is not None and row["expires_at"] <= time.time():
            return "nøglen er udløbet"
        if row["ip_allow"] and not self._ip_allowed(s.ip, row["ip_allow"]):
            return "nøglen må ikke længere bruges fra denne IP-adresse"
        s.principal = Principal(row["id"], row["name"], self._decode_scope(row["scope"]))
        s.allowed = set(self.allowed_names(s.principal))
        return None

    async def stream_events(self, request: Any, s: StreamState, tags: list[str] | None, interval: float, max_events: int | None,
                            with_alarms: bool) -> AsyncIterator[bytes]:
        """SSE: `snapshot` (alle værdier + aktive alarmer), derefter `values` (ændringer, samlet pr. `interval`) og `alarm`; en
        kommentarlinje som hjerteslag; `closed` når nøglen ikke længere gælder (eller `max_events` er nået). Ved genforbindelse sendes
        altid et nyt øjebliksbillede (ingen afspilning af mistede hændelser — øjebliksbilledet er hele sandheden)."""
        counter = 0

        def frame(event: str, data: Any) -> bytes:
            nonlocal counter
            counter += 1
            with self._lock:
                self.stats.setdefault(s.key_id, KeyStats()).stream_events += 1
            return f"event: {event}\nid: {counter}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n".encode()

        wanted = set(tags) if tags else None

        def snapshot_data() -> dict[str, Any]:
            names = sorted(n for n in s.allowed if wanted is None or n in wanted)
            data: dict[str, Any] = self.values(s.principal, names)
            if with_alarms:
                data["alarms"] = self.alarms_for(s.principal)
            return data

        async def snapshot() -> bytes:            # DB-opslag i en tråd — event-loopet (polling, WebSocket) må ikke blokeres
            return frame("snapshot", await asyncio.to_thread(snapshot_data))

        def drain(q: Any) -> list[Any]:
            out = []
            while True:
                try:
                    out.append(q.get_nowait())
                except asyncio.QueueEmpty:
                    return out

        try:
            yield b"retry: 5000\n\n"
            yield await snapshot()
            pending: dict[str, Any] = {}
            now = last_beat = last_check = time.monotonic()
            last_resync = 0.0
            while True:
                if max_events is not None and counter >= max_events:
                    yield frame("closed", {"reason": "max_events"})
                    return
                await asyncio.sleep(interval)
                if await request.is_disconnected():
                    return
                now = time.monotonic()
                if now - last_check >= STREAM_REVALIDATE_S:
                    last_check = now
                    reason = await asyncio.to_thread(self.revalidate, s)
                    if reason:
                        yield frame("closed", {"reason": reason})
                        return
                for delta in drain(s.cache_q):
                    for name, v in delta.items():
                        if name in s.allowed and (wanted is None or name in wanted):
                            pending[name] = {"v": v["value"], "q": v["quality"], "ts": v["ts"]}
                if pending:
                    yield frame("values", {"time": _iso(time.time()), "values": pending})
                    pending, last_beat = {}, now
                if with_alarms:
                    if s.overflow:                      # for langsom klient: nyt øjebliksbillede i stedet for en hullet række
                        s.overflow = False
                        drain(s.alarm_q)
                        if now - last_resync < STREAM_REVALIDATE_S:   # højst ét nyt øjebliksbillede pr. 10 s
                            s.overflow = True
                            continue
                        last_resync = now
                        yield frame("resync", {"reason": "klienten var for langsom"})
                        yield await snapshot()
                        last_beat = now
                    for item in drain(s.alarm_q):
                        yield frame("alarm", item)
                        last_beat = now
                else:
                    drain(s.alarm_q)
                if now - last_beat >= STREAM_HEARTBEAT_S:
                    yield b": heartbeat\n\n"
                    last_beat = now
        finally:
            self.close_stream(s)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")
