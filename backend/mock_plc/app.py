"""Mock af HypervisionPLC's REST API (firmware v7.9.68.122) til udvikling og test.

Efterligner det subset SCADA'en bruger, med samme svarformer og grænser som den
rigtige PLC (src/api_handlers.cpp, src/rbac.cpp, src/sse_events.cpp):
- auth_mode=bearer: POST /api/login (Basic) → token; Basic på andre endpoints → 401
- 8 session-pladser; fuld tabel → den der er tættest på at udløbe smides ud
- rate-limit pr. klient-IP: token bucket 30 burst / 10 pr. s → 429
- fejlformat {"error": "...", "status": N}
- bulk-læsning: hr/ir max 200, coils/di max 256; IR 0-319
- SSE med max 3 klienter, watch-lists (max 32 pr. type) eller subscribe=all
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import secrets
import struct
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

HR_SIZE, IR_SIZE, BIT_SIZE = 256, 320, 256


def _err(status: int, message: str) -> JSONResponse:
    headers = {"WWW-Authenticate": "Basic"} if status == 401 else None
    return JSONResponse({"error": message, "status": status}, status_code=status, headers=headers)


@dataclass
class _Bucket:
    tokens: float
    last: float


@dataclass
class MockPlcState:
    users: dict[str, str] = field(default_factory=lambda: {"scada": "scada123"})
    rate_limit: bool = True
    rate: float = 10.0
    burst: int = 30
    max_sessions: int = 8
    session_ttl_s: float = 1800.0
    sse_enabled: bool = True
    sse_max_clients: int = 3
    sse_port: int = 0  # sættes af den der starter serveren
    sse_check_s: float = 0.1
    sse_heartbeat_s: float = 15.0
    # Modbus-cachen for eksterne registre (FEAT-447): nøgle → hændelsesdata, fx
    # {"src": "rtu", "slave": 90, "type": "hr", "addr": 0, "value": 234, "status": "ok"} — sendes som `ext` i watch_all
    ext: dict[str, dict[str, Any]] = field(default_factory=dict)
    hr: list[int] = field(default_factory=lambda: [0] * HR_SIZE)
    ir: list[int] = field(default_factory=lambda: [0] * IR_SIZE)
    coils: list[bool] = field(default_factory=lambda: [False] * BIT_SIZE)
    di: list[bool] = field(default_factory=lambda: [False] * BIT_SIZE)
    programs: dict[int, dict[str, Any]] = field(default_factory=dict)
    globals: list[dict[str, Any]] = field(default_factory=list)
    var_write: bool = True              # firmware med FEAT-503 (skriv ST-variabler); False = ældre firmware (404)
    input_bound: set[tuple[int, str]] = field(default_factory=set)   # (program, variabel) bundet som INPUT → 409
    bindings: list[dict[str, Any]] = field(default_factory=list)     # GET /api/bindings (input-bindinger skriver registeret → variablen)
    sessions: dict[str, float] = field(default_factory=dict)  # token → udløb
    sse_tokens: dict[str, float] = field(default_factory=dict)
    sse_active: int = 0
    buckets: dict[str, _Bucket] = field(default_factory=dict)
    request_log: list[str] = field(default_factory=list)
    # Test: afvis alle skrivninger med denne tekst (409), fx "Safe mode aktiv".
    reject_writes: str = ""
    # Test: afvis skrivning til bestemte adresser: {("coil", 12): "Udgang låst"}
    reject_addr: dict[tuple[str, int], str] = field(default_factory=dict)
    # Test: de næste N skrivninger UDFØRES, men svaret kommer først efter slow_write_s (svar tabt/timeout)
    slow_writes: int = 0
    slow_write_s: float = 2.0
    # Test: registre/coils som "ST-programmet" holder fast efter enhver skrivning: {("hr", 5): 0}
    locks: dict[tuple[str, int], int] = field(default_factory=dict)
    writes: list[tuple[str, int, object]] = field(default_factory=list)
    logins: int = 0

    def apply_locks(self) -> None:
        for (kind, addr), value in self.locks.items():
            if kind == "hr":
                self.hr[addr] = value
            elif kind == "coil":
                self.coils[addr] = bool(value)

    def apply_bindings(self) -> None:
        """Som PLC'ens input-bindinger ved starten af en ST-cyklus: register → ST-variabel (lav ord først for 32 bit)."""
        for b in self.bindings:
            if b["direction"] != "input" or b["register_type"] == "DI":
                continue
            prog = self.programs.get(b["program"])
            var = next((v for v in (prog or {}).get("variables", []) if v["name"] == b["name"]), None)
            if var is None:
                continue
            a, t = b["register_addr"], str(b["type"]).upper()
            if b["register_type"] == "Coil":
                var["value"] = bool(self.coils[a])
            elif t == "BOOL":
                var["value"] = bool(self.hr[a])
            elif t == "INT":
                var["value"] = struct.unpack(">h", struct.pack(">H", self.hr[a]))[0]
            else:
                bits = (self.hr[a + 1] << 16) | self.hr[a]
                fmt = {"REAL": ">f", "DWORD": ">I"}.get(t, ">i")
                var["value"] = struct.unpack(fmt, struct.pack(">I", bits))[0]

    # ---- testhjælpere
    def revoke_all_sessions(self) -> None:
        self.sessions.clear()

    def set_hr_real(self, addr: int, value: float) -> None:
        hi, lo = struct.unpack(">HH", struct.pack(">f", value))
        self.hr[addr], self.hr[addr + 1] = hi, lo

    def set_hr_dint(self, addr: int, value: int) -> None:
        hi, lo = struct.unpack(">HH", struct.pack(">i", value))
        self.hr[addr], self.hr[addr + 1] = hi, lo


def default_state() -> MockPlcState:
    st = MockPlcState()
    st.programs = {
        1: {"id": 1, "name": "Tank", "enabled": True, "compiled": True, "variables": [
            {"index": 0, "name": "Niveau", "type": "REAL", "value": 42.5},
            {"index": 1, "name": "PumpeKoerer", "type": "BOOL", "value": True},
            {"index": 2, "name": "Starter", "type": "INT", "value": 7},
        ]},
        2: {"id": 2, "name": "Tom", "enabled": False, "compiled": False, "variables": []},
    }
    st.globals = [{"index": 0, "name": "Mode", "type": "INT", "value": 1}]
    return st


def simulate(st: MockPlcState, t: float) -> None:
    """Lidt bevægelse til demo: tankniveau (HR 10, x10), pumpe (coil 0), temperatur (HR 20-21 real)."""
    level = 500 + 400 * math.sin(t / 10)
    st.hr[10] = int(level)
    st.coils[0] = level < 600
    st.set_hr_real(20, 21.5 + 2 * math.sin(t / 7))
    st.di[0] = int(t) % 10 < 5
    st.programs[1]["variables"][0]["value"] = round(level / 10, 1)
    st.programs[1]["variables"][1]["value"] = st.coils[0]


def create_mock_plc(state: MockPlcState | None = None, *, simulate_process: bool = False) -> FastAPI:
    st = state or default_state()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = None
        if simulate_process:
            async def loop() -> None:
                t0 = time.monotonic()
                while True:
                    simulate(st, time.monotonic() - t0)
                    await asyncio.sleep(0.5)
            task = asyncio.create_task(loop())
        try:
            yield
        finally:
            if task is not None:
                task.cancel()

    app = FastAPI(title="Mock HypervisionPLC", lifespan=lifespan)
    app.state.plc = st

    # ------------------------------------------------------------ middleware

    @app.middleware("http")
    async def rate_limit(request: Request, call_next: Any) -> Response:
        st.request_log.append(f"{request.method} {request.url.path}")
        if st.rate_limit and request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "?"
            now = time.monotonic()
            b = st.buckets.setdefault(ip, _Bucket(float(st.burst), now))
            b.tokens = min(st.burst, b.tokens + (now - b.last) * st.rate)
            b.last = now
            if b.tokens < 1:
                return _err(429, "Too Many Requests")
            b.tokens -= 1
        return await call_next(request)

    def _gc(now: float) -> None:
        for tok, exp in list(st.sessions.items()):
            if exp <= now:
                del st.sessions[tok]

    def _auth(request: Request) -> JSONResponse | None:
        header = request.headers.get("authorization", "")
        if header.lower().startswith("basic "):
            return _err(401, "Basic Auth not accepted in bearer mode - use POST /api/login")
        if not header.lower().startswith("bearer "):
            return _err(401, "Authentication required")
        now = time.monotonic()
        _gc(now)
        token = header[7:].strip()
        if token not in st.sessions:
            return _err(401, "Invalid or expired session")
        st.sessions[token] = now + st.session_ttl_s  # glidende timeout
        return None

    # --------------------------------------------------------------- auth

    async def _maybe_slow() -> None:
        """Skrivningen er udført; svaret forsinkes så klienten giver op (som et tabt svar på et ustabilt net)."""
        if st.slow_writes > 0:
            st.slow_writes -= 1
            await asyncio.sleep(st.slow_write_s)

    @app.post("/api/login")
    async def login(request: Request) -> Response:
        header = request.headers.get("authorization", "")
        try:
            user, _, pw = base64.b64decode(header[6:]).decode().partition(":") if header.lower().startswith("basic ") else ("", "", "")
        except Exception:
            user, pw = "", ""
        if not user or st.users.get(user) != pw:
            return _err(401, "Authentication required")
        now = time.monotonic()
        _gc(now)
        if len(st.sessions) >= st.max_sessions:
            oldest = min(st.sessions, key=st.sessions.__getitem__)
            del st.sessions[oldest]
        token = secrets.token_hex(11)
        st.sessions[token] = now + st.session_ttl_s
        st.logins += 1
        return JSONResponse({"authenticated": True, "username": user, "roles": "api",
                             "privilege": "read/write", "mode": "rbac", "token": token})

    @app.post("/api/logout")
    async def logout(request: Request) -> Response:
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            st.sessions.pop(header[7:].strip(), None)
        return JSONResponse({"status": "ok"})

    # ------------------------------------------------------------- registre

    def _bulk(request: Request, size: int, max_count: int, key: str, values: list[Any], as_bool: bool) -> Response:
        if (denied := _auth(request)) is not None:
            return denied
        try:
            start = int(request.query_params.get("start", 0))
            count = int(request.query_params.get("count", 10))
        except ValueError:
            return _err(400, "Invalid start address")
        if start < 0 or start >= size:
            return _err(400, "Invalid start address")
        if count < 1 or count > max_count:
            return _err(400, f"Count must be 1-{max_count}")
        count = min(count, size - start)
        items = [{"addr": start + i, "value": bool(values[start + i]) if as_bool else int(values[start + i])}
                 for i in range(count)]
        return JSONResponse({"start": start, "count": count, key: items})

    @app.get("/api/registers/hr")
    async def hr_bulk(request: Request) -> Response:
        return _bulk(request, HR_SIZE, 200, "registers", st.hr, False)

    @app.get("/api/registers/ir")
    async def ir_bulk(request: Request) -> Response:
        return _bulk(request, IR_SIZE, 200, "registers", st.ir, False)

    @app.get("/api/registers/coils")
    async def coils_bulk(request: Request) -> Response:
        return _bulk(request, BIT_SIZE, 256, "coils", st.coils, True)

    @app.get("/api/registers/di")
    async def di_bulk(request: Request) -> Response:
        return _bulk(request, BIT_SIZE, 256, "inputs", st.di, True)

    @app.post("/api/registers/hr/{addr}")
    async def hr_write(addr: int, request: Request) -> Response:
        if (denied := _auth(request)) is not None:
            return denied
        if addr < 0 or addr >= HR_SIZE:
            return _err(400, "Invalid register address")
        if st.reject_writes:
            return _err(409, st.reject_writes)
        if ("hr", addr) in st.reject_addr:
            return _err(409, st.reject_addr[("hr", addr)])
        try:
            body = await request.json()
        except ValueError:
            return _err(400, "Invalid JSON")
        dtype = body.get("type", "uint")
        value = body.get("value")
        if dtype in ("dint", "dword", "real"):
            if addr + 1 >= HR_SIZE:
                return _err(400, f"{dtype.upper()} requires 2 registers, address out of range")
            fmt = {"dint": ">i", "dword": ">I", "real": ">f"}[dtype]
            hi, lo = struct.unpack(">HH", struct.pack(fmt, value if dtype == "real" else int(value)))
            st.hr[addr], st.hr[addr + 1] = hi, lo
        elif dtype in ("uint", "int"):
            st.hr[addr] = int(value) & 0xFFFF
        else:
            return _err(400, "Invalid type (use: uint, int, dint, dword, real)")
        st.writes.append(("hr", addr, value))
        st.apply_locks()
        st.apply_bindings()
        await _maybe_slow()
        return JSONResponse({"status": 200, "address": addr, "value": value, "type": dtype})

    @app.post("/api/registers/coils/{addr}")
    async def coil_write(addr: int, request: Request) -> Response:
        if (denied := _auth(request)) is not None:
            return denied
        if addr < 0 or addr >= BIT_SIZE:
            return _err(400, "Invalid coil address")
        if st.reject_writes:
            return _err(409, st.reject_writes)
        if ("coil", addr) in st.reject_addr:
            return _err(409, st.reject_addr[("coil", addr)])
        body = await request.json()
        st.coils[addr] = bool(body.get("value"))
        st.writes.append(("coil", addr, st.coils[addr]))
        st.apply_locks()
        st.apply_bindings()
        await _maybe_slow()
        return JSONResponse({"status": 200, "address": addr, "value": st.coils[addr]})

    # ------------------------------------------------------------- ST Logic

    @app.get("/api/logic")
    async def logic_list(request: Request) -> Response:
        if (denied := _auth(request)) is not None:
            return denied
        programs = [{k: p[k] for k in ("id", "name", "enabled", "compiled")} for p in st.programs.values()]
        return JSONResponse({"enabled": True, "programs": programs})

    @app.get("/api/logic/globals")
    async def logic_globals(request: Request) -> Response:
        if (denied := _auth(request)) is not None:
            return denied
        return JSONResponse({"globals": st.globals, "count": len(st.globals)})

    def _st_value(var: dict[str, Any], value: Any) -> tuple[Any, JSONResponse | None]:
        """Som firmwarens st_var_json_to_value: typekonvertering og områdetjek."""
        t = str(var.get("type")).upper()
        if t == "BOOL":
            if isinstance(value, bool) or value in (0, 1):
                return bool(value), None
            return None, _err(400, "BOOL expects true/false or 0/1")
        if t == "REAL":
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value), None
            return None, _err(400, "REAL expects a number")
        if t == "STRING":
            return None, _err(400, "STRING variables cannot be written via REST")
        if not isinstance(value, int) or isinstance(value, bool):
            return None, _err(400, "Integer value expected")
        lo, hi = {"INT": (-32768, 32767), "DWORD": (0, 4294967295)}.get(t, (-2**31, 2**31 - 1))
        if not lo <= value <= hi:
            return None, _err(400, f"{t} out of range")
        return value, None

    async def _var_body(request: Request) -> tuple[str | None, Any, JSONResponse | None]:
        try:
            body = await request.json()
        except ValueError:
            return None, None, _err(400, "Invalid JSON")
        if not body.get("name"):
            return None, None, _err(400, "Missing 'name' field")
        if body.get("value") is None:
            return None, None, _err(400, "Missing 'value' field")
        return body["name"], body["value"], None

    @app.post("/api/logic/globals/var")
    async def logic_global_write(request: Request) -> Response:
        if (denied := _auth(request)) is not None:
            return denied
        if not st.var_write:
            return _err(404, "Not found")
        name, value, bad = await _var_body(request)
        if bad is not None:
            return bad
        var = next((g for g in st.globals if g["name"] == name), None)
        if var is None:
            return _err(404, f"GLOBAL_VAR '{name}' not found")
        val, bad = _st_value(var, value)
        if bad is not None:
            return bad
        var["value"] = val
        st.writes.append(("global", name, val))
        return JSONResponse({"status": "ok", "name": name, "value": val})

    @app.post("/api/logic/{pid}/var")
    async def logic_var_write(pid: int, request: Request) -> Response:
        if (denied := _auth(request)) is not None:
            return denied
        if not st.var_write:
            return _err(404, "Not found")
        if pid < 1 or pid > 4:
            return _err(400, "Invalid logic ID (must be 1-4)")
        prog = st.programs.get(pid)
        if not prog or not prog.get("compiled"):
            return _err(409, "Program not compiled. Upload source code first.")
        name, value, bad = await _var_body(request)
        if bad is not None:
            return bad
        var = next((v for v in prog["variables"] if v["name"] == name), None)
        if var is None:
            return _err(404, f"Variable '{name}' not found. Available: " + ", ".join(v["name"] for v in prog["variables"]))
        bound = next((b for b in st.bindings if b["direction"] == "input" and b["program"] == pid and b["name"] == name), None)
        if bound is not None or (pid, name) in st.input_bound:
            where = f"{bound['register_type']} {bound['register_addr']}" if bound else "HR 100"
            return _err(409, f"Variable '{name}' is bound as INPUT from {where} - write that register instead")
        val, bad = _st_value(var, value)
        if bad is not None:
            return bad
        var["value"] = val
        st.writes.append(("logic", f"{pid}:{name}", val))
        return JSONResponse({"status": "ok", "program": pid, "name": name, "value": val})

    @app.get("/api/bindings")
    async def bindings_list(request: Request) -> Response:
        if (denied := _auth(request)) is not None:
            return denied
        return JSONResponse({"count": len(st.bindings), "bindings": st.bindings})

    @app.get("/api/logic/{pid}")
    async def logic_single(pid: int, request: Request) -> Response:
        if (denied := _auth(request)) is not None:
            return denied
        if pid < 1 or pid > 4:
            return _err(400, "Invalid program ID")
        prog = st.programs.get(pid, {"id": pid, "name": f"Logic{pid}", "enabled": False, "compiled": False, "variables": []})
        out = {k: v for k, v in prog.items() if k != "variables"}
        if prog.get("compiled"):
            out["variables"] = prog["variables"]
        return JSONResponse(out)

    # ------------------------------------------------------------------ SSE

    @app.get("/api/events/status")
    async def sse_status(request: Request) -> Response:
        if (denied := _auth(request)) is not None:
            return denied
        token = secrets.token_hex(11)
        st.sse_tokens[token] = time.monotonic() + 300
        return JSONResponse({"sse_enabled": st.sse_enabled, "sse_port": st.sse_port,
                             "max_clients": st.sse_max_clients, "active_clients": st.sse_active,
                             "check_interval_ms": int(st.sse_check_s * 1000),
                             "heartbeat_ms": int(st.sse_heartbeat_s * 1000),
                             "topics": ["counters", "timers", "registers", "system"],
                             "sse_token": token, "sse_token_ttl_ms": 300000})

    @app.get("/api/events")
    async def sse_events(request: Request) -> Response:
        token = request.query_params.get("token", "")
        if st.sse_tokens.get(token, 0) < time.monotonic():
            return _err(401, "Authentication required")
        if not st.sse_enabled:
            return _err(503, "SSE disabled")
        if st.sse_active >= st.sse_max_clients:
            return _err(503, "Max SSE clients reached")
        # Som den rigtige PLC: query-strengen URL-afkodes IKKE (sse_get_query_param i sse_events.cpp)
        watch = _parse_watch_raw(request.url.query)
        # Som sse_events.cpp: eksterne registre sendes kun i watch_all (subscribe=all uden adresselister)
        watch_all = "all" in (_raw_param(request.url.query, "subscribe") or "all") and not any(
            _raw_param(request.url.query, p) for p in ("hr", "ir", "coils", "di"))
        st.sse_active += 1

        async def stream() -> AsyncIterator[bytes]:
            try:
                connected = {"status": "connected", "max_clients": st.sse_max_clients, "active_clients": st.sse_active,
                             "watching": {("coils" if k == "coil" else k): len(v) for k, v in watch.items()}}
                yield f"event: connected\ndata: {json.dumps(connected)}\n\n".encode()
                prev = _snapshot(st, watch)
                prev_ext: dict[str, str] = {}
                last_hb = time.monotonic()
                while True:
                    await asyncio.sleep(st.sse_check_s)
                    if await request.is_disconnected():
                        return
                    cur = _snapshot(st, watch)
                    for (kind, addr), value in cur.items():
                        if prev.get((kind, addr)) != value:
                            data = json.dumps({"type": kind, "addr": addr, "value": value})
                            yield f"event: register\ndata: {data}\n\n".encode()
                    prev = cur
                    if watch_all:
                        for key, entry in list(st.ext.items()):
                            data = json.dumps(entry)
                            if prev_ext.get(key) != data:
                                prev_ext[key] = data
                                yield f"event: ext\ndata: {data}\n\n".encode()
                    if time.monotonic() - last_hb >= st.sse_heartbeat_s:
                        last_hb = time.monotonic()
                        yield f"event: heartbeat\ndata: {json.dumps({'uptime_ms': int(last_hb * 1000)})}\n\n".encode()
            finally:
                st.sse_active -= 1

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    return app


def _raw_param(query: str, key: str) -> str | None:
    for part in query.split("&"):
        k, _, v = part.partition("=")
        if k == key:
            return v  # bevidst uden URL-afkodning — som PLC'en
    return None


def _parse_addrs_plc(text: str, max_addr: int) -> list[int]:
    """Efterligner sse_parse_addr_list: stopper ved første tegn der ikke er tal, komma, mellemrum eller '-'."""
    out: list[int] = []
    i, n = 0, len(text)
    while i < n and len(out) < 32:
        while i < n and text[i] in ", ":
            i += 1
        j = i
        while j < n and text[j].isdigit():
            j += 1
        if j == i:
            break
        start = int(text[i:j])
        i = j
        if i < n and text[i] == "-":
            k = i + 1
            while k < n and text[k].isdigit():
                k += 1
            if k == i + 1:
                break
            end = min(int(text[i + 1:k]), max_addr)
            i = k
            out.extend(a for a in range(start, end + 1) if len(out) < 32)
        elif start <= max_addr:
            out.append(start)
    return out[:32]


def _parse_watch_raw(query: str) -> dict[str, list[int]]:
    subscribe = _raw_param(query, "subscribe") or "all"
    limits = {"hr": ("hr", 159), "ir": ("ir", 159), "coils": ("coil", 255), "di": ("di", 255)}
    explicit = {}
    for param, (kind, max_addr) in limits.items():
        raw = _raw_param(query, param)
        if raw:
            explicit[kind] = _parse_addrs_plc(raw, max_addr)
    if explicit:
        return explicit
    if "all" in subscribe:
        return {"hr": list(range(256)), "ir": list(range(256)), "coil": list(range(256)), "di": list(range(256))}
    return {"hr": list(range(16))}


def _parse_watch(params: Any) -> dict[str, list[int]]:
    subscribe = params.get("subscribe", "all")
    names = {"hr": "hr", "ir": "ir", "coils": "coil", "di": "di"}
    explicit = {kind: _parse_addrs(params.get(p)) for p, kind in names.items() if params.get(p)}
    if explicit:
        return {k: v[:32] for k, v in explicit.items()}
    if subscribe == "all":
        return {"hr": list(range(256)), "ir": list(range(256)), "coil": list(range(256)), "di": list(range(256))}
    return {"hr": list(range(16))}


def _parse_addrs(text: str) -> list[int]:
    out: list[int] = []
    for part in text.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        elif part.strip():
            out.append(int(part))
    return [a for a in out if 0 <= a <= 255]


def _snapshot(st: MockPlcState, watch: dict[str, list[int]]) -> dict[tuple[str, int], int]:
    src = {"hr": st.hr, "ir": st.ir, "coil": st.coils, "di": st.di}
    return {(kind, a): int(src[kind][a]) for kind, addrs in watch.items() for a in addrs}
