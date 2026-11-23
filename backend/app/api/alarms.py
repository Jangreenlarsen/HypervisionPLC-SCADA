"""Alarmer (lag 2): aktiv liste, kvittering og historik — filtreret efter brugerens adgang pr. tegning."""

from __future__ import annotations

import asyncio
import csv
import io
import re
from datetime import datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from ..services.alarms import EVENT_TYPES, KEEP_EVENTS, PRIORITIES, AlarmService
from ..services.bindings import binding_tags
from ..services.auth import CurrentUser
from ..services.errors import ServiceError
from ..services.schedule_engine import TZ
from .auth import audit, require

router = APIRouter(prefix="/api/alarms")

_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PRIO_TEXT = {"high": "Høj", "medium": "Medium", "low": "Lav"}
EVENT_TEXT = {"raise": "Opstået", "clear": "Ophørt", "ack": "Kvitteret", "change": "Ændret niveau"}


class AckBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keys: list[str] | None = Field(default=None, description="null = alle synlige")


def _svc(request: Request) -> AlarmService:
    return request.app.state.alarm_service


def _visible(request: Request, user: CurrentUser) -> set[str] | None:
    return request.app.state.scope_service.visible_tags(user)


@router.get("")
async def active(request: Request, user: CurrentUser = Depends(require("viewer"))) -> dict[str, Any]:
    vis = _visible(request, user)
    return {"summary": _svc(request).summary(vis), "active": _svc(request).active(vis)}


@router.post("/ack")
async def ack(body: AckBody, request: Request, user: CurrentUser = Depends(require("operator"))) -> dict[str, Any]:
    svc = _svc(request)
    vis = _visible(request, user)
    keys = body.keys if body.keys is not None else [a["key"] for a in svc.active(vis)]
    count = svc.ack(keys, user.username, svc.visible_keys(vis))
    if count:
        audit(request, "alarm.ack", "", {"count": count, "keys": keys[:50]})
    return {"acked": count}


def _parse_time(value: str, name: str, end: bool) -> float:
    """ISO-dato eller -datotid i dansk tid (SCADA_TZ) → epoch. En ren dato dækker hele dagen (til: dagens sidste øjeblik)."""
    text = value.strip()
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        raise ServiceError(400, f"Ugyldig '{name}'-værdi '{value}': brug en dato (ÅÅÅÅ-MM-DD) eller dato og tid (ÅÅÅÅ-MM-DDTTT:MM).") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    if end and _DATE_ONLY.match(text):
        # Dagens sidste øjeblik = næste midnat i dansk tid minus 1 µs (et døgn er 23 eller 25 timer ved sommertid)
        nxt = datetime.combine(dt.date() + timedelta(days=1), time(), tzinfo=TZ)
        return nxt.timestamp() - 0.000001
    return dt.timestamp()


def _cell(value: Any) -> Any:
    """CSV-celle: tekst der starter som en formel (=, +, -, @, tab, CR) får ' foran, så Excel ikke udfører den.
    Kun tekst — tal (også negative) står uændret."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _history_filter(request: Request, user: CurrentUser, q: str, from_: str | None, to: str | None,
                    event: str | None, priority: str | None, system: str | None) -> dict[str, Any]:
    flt: dict[str, Any] = {"q": q.strip()}
    if from_ and from_.strip():
        flt["ts_from"] = _parse_time(from_, "from", False)
    if to and to.strip():
        flt["ts_to"] = _parse_time(to, "to", True)
    if flt.get("ts_from") is not None and flt.get("ts_to") is not None and flt["ts_from"] > flt["ts_to"]:
        raise ServiceError(400, "'Fra' ligger efter 'Til'.")
    if event:
        if event not in EVENT_TYPES:
            raise ServiceError(400, f"Ukendt hændelse '{event}': vælg en af {', '.join(EVENT_TYPES)}.")
        flt["event"] = event
    if priority:
        if priority not in PRIORITIES:
            raise ServiceError(400, f"Ukendt prioritet '{priority}': vælg en af {', '.join(PRIORITIES)}.")
        flt["priority"] = priority
    if system:
        systems_ = _systems(request, user)
        if system != "-" and system not in {s["id"] for s in systems_}:
            raise ServiceError(400, f"Ukendt system '{system}'.")   # ikke et tomt resultat, der ligner et rigtigt
        flt["system"] = {"id": system, "ids": {s["id"] for s in systems_}, "all_tags": {t for s in systems_ for t in s["tags"]},
                         "tags": set(next((s["tags"] for s in systems_ if s["id"] == system), []))}
    return flt


@router.get("/history")
async def history(request: Request, limit: int = 300, q: str = "", from_: str | None = Query(None, alias="from"),
                  to: str | None = None, event: str | None = None, priority: str | None = None, system: str | None = None,
                  user: CurrentUser = Depends(require("viewer"))) -> list[dict[str, Any]]:
    flt = _history_filter(request, user, q, from_, to, event, priority, system)
    # fritekstsøgning scanner op til 50.000 rækker: ikke på event-loopet
    return await asyncio.to_thread(_svc(request).history, limit, _visible(request, user), flt)


@router.get("/history/export")
async def history_export(request: Request, q: str = "", from_: str | None = Query(None, alias="from"),
                         to: str | None = None, event: str | None = None, priority: str | None = None,
                         system: str | None = None, user: CurrentUser = Depends(require("viewer"))) -> Response:
    flt = _history_filter(request, user, q, from_, to, event, priority, system)
    svc, vis = _svc(request), _visible(request, user)

    def build() -> tuple[str, int]:   # i en tråd: op til 50.000 rækker
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(["Tid", "Tag", "PLC", "Type", "Prioritet", "Hændelse", "Værdi", "Bruger", "Besked"])
        rows = svc.history(KEEP_EVENTS, vis, flt, cap=KEEP_EVENTS)
        for e in rows:
            v = e["value"]
            # med offset (+01:00/+02:00), så timen hvor uret stilles tilbage ikke er tvetydig
            writer.writerow([datetime.fromtimestamp(e["ts"], TZ).isoformat(timespec="milliseconds"),
                             _cell(e["tag"]), _cell(e["plc"]), _cell(e["level"]), PRIO_TEXT.get(e["priority"], e["priority"]),
                             EVENT_TEXT.get(e["event"], e["event"]),
                             "" if v is None else (f"{v:.10g}".replace(".", ",") if isinstance(v, float) else _cell(v)),
                             _cell(e["username"] or ""), _cell(e["message"])])
        return buf.getvalue(), len(rows)

    body, count = await asyncio.to_thread(build)
    audit(request, "alarm.export", "", {"rows": count, "filters": {k: v for k, v in request.query_params.items() if v}})
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    return Response("﻿" + body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="alarmer-{stamp}.csv"'})


def _systems(request: Request, user: CurrentUser) -> list[dict[str, Any]]:
    """Systemerne (tegningerne) og de tags, de bruger. Kun brugerens egne tegninger og tags."""
    state = request.app.state
    allowed = state.scope_service.drawing_ids(user)
    vis = _visible(request, user)
    out: list[dict[str, Any]] = []
    for d in state.drawing_service.list():
        did = d["id"]
        if d.get("disabled") or (allowed is not None and did not in allowed):
            continue
        names = {t for b in state.drawing_service.effective_bindings(did) for t in binding_tags(b)} | state.symbol_service.tags_for_drawing(did)
        out.append({"id": did, "name": d["name"], "tags": sorted(n for n in names if vis is None or n in vis)})
    return out


@router.get("/systems")
async def systems(request: Request, user: CurrentUser = Depends(require("viewer"))) -> list[dict[str, Any]]:
    """Systemerne (tegningerne) og de tags, de bruger — så Alarmer kan filtrere pr. system."""
    return _systems(request, user)
