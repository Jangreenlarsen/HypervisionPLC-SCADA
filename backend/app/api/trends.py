"""Trends (lag 2): nedsamplede serier til grafer, CSV-eksport og oversigt — filtreret efter adgang."""

from __future__ import annotations

import csv
import io
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from ..services.auth import CurrentUser, role_at_least
from ..services.errors import ServiceError
from ..services.schedule_engine import TZ
from ..services.tagsource import TagSourceError, parse_source
from .auth import audit, require

router = APIRouter(prefix="/api/trends")
MAX_SPAN_S = 400 * 86400
MAX_EXPORT_ROWS = 1_000_000


def _is_bool(source: str) -> bool:
    try:
        return parse_source(source).datatype == "bool"
    except TagSourceError:
        return False


def _allowed(request: Request, user: CurrentUser) -> set[str] | None:
    """Tags brugeren må trende. Tekniker/admin: alle synlige tags (None = ingen yderligere begrænsning). Viewer, operatør og
    driftpanel: kun tags i de trends der er sat op i deres tegninger (symboler og trendgrafer) — ikke frit valg af tags."""
    visible = request.app.state.scope_service.visible_tags(user)
    if role_at_least(user.role, "engineer"):
        return visible
    scope = request.app.state.scope_service
    configured = {t for s in request.app.state.symbol_service.trend_symbols(scope.drawing_ids(user)) for t in s["tags"]}
    return configured if visible is None else configured & visible


def _names(request: Request, user: CurrentUser, tags: str) -> list[str]:
    names = [t.strip() for t in tags.split(",") if t.strip()]
    if not names:
        raise ServiceError(400, "Vælg mindst ét tag")
    if len(names) > 20:
        raise ServiceError(400, "Højst 20 tags ad gangen")
    allowed = _allowed(request, user)
    if allowed is not None:
        names = [n for n in names if n in allowed]
    return names


def _range(start: float | None, end: float | None) -> tuple[float, float]:
    now = time.time()
    end = now if end is None else end
    start = end - 3600 if start is None else start
    if not start < end:
        raise ServiceError(400, "Starttidspunktet skal ligge før sluttidspunktet")
    if end - start > MAX_SPAN_S:
        raise ServiceError(400, "Perioden må højst være 400 dage")
    return start, end


class ViewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    tags: list[str]
    assign: dict[str, int] = {}
    range: str = "1h"


@router.get("/views", dependencies=[Depends(require("viewer"))])
async def list_views(request: Request) -> list[dict[str, Any]]:
    """Gemte visninger (fælles for alle). Hvem der må se kurverne afgøres stadig pr. tag, når data hentes."""
    return request.app.state.trend_view_service.list()


@router.post("/views", dependencies=[Depends(require("engineer"))])
async def save_view(body: ViewBody, request: Request, user: CurrentUser = Depends(require("engineer"))) -> dict[str, Any]:
    view = request.app.state.trend_view_service.save(user.username, body.model_dump())
    audit(request, "trend.view.save", view["name"], {"tags": len(view["tags"])})
    return view


@router.delete("/views", dependencies=[Depends(require("engineer"))], status_code=204)
async def delete_view(name: str, request: Request) -> Response:
    request.app.state.trend_view_service.delete(name)
    audit(request, "trend.view.delete", name)
    return Response(status_code=204)


@router.get("/data")
async def data(request: Request, tags: str, start: float | None = None, end: float | None = None,
               points: int = 600, user: CurrentUser = Depends(require("viewer"))) -> dict[str, Any]:
    names = _names(request, user, tags)
    start, end = _range(start, end)
    points = max(10, min(points, 2000))
    step = (end - start) / points
    tdb = request.app.state.trend_db
    all_tags = {t["name"]: t for t in request.app.state.tag_service.list()}
    return {
        "start": start, "end": end, "step": step,
        "series": {n: tdb.series(n, start, end, step) for n in names},
        "meta": {n: {k: all_tags[n][k] for k in ("unit", "description", "decimals")} for n in names if n in all_tags},
    }


@router.get("/export")
async def export(request: Request, tags: str, start: float | None = None, end: float | None = None,
                 user: CurrentUser = Depends(require("viewer"))) -> Response:
    names = _names(request, user, tags)
    start, end = _range(start, end)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["tidspunkt", "tag", "vaerdi"])
    for name, ts, value in request.app.state.trend_db.raw(names, start, end, MAX_EXPORT_ROWS):
        # Dansk tid (SCADA_TZ) uanset serverens tidszone — en Pi står ofte på UTC
        writer.writerow([datetime.fromtimestamp(ts, TZ).replace(tzinfo=None).isoformat(timespec="milliseconds"), name,
                         "" if value is None else f"{value:.10g}".replace(".", ",")])
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="trend-{stamp}.csv"'})


@router.get("/info")
async def info(request: Request, user: CurrentUser = Depends(require("viewer"))) -> dict[str, Any]:
    visible = _allowed(request, user)
    stats = request.app.state.trend_db.stats()
    tags = []
    for t in request.app.state.tag_service.list():
        if visible is not None and t["name"] not in visible:
            continue
        s = stats.get(t["name"], {})
        tags.append({"name": t["name"], "unit": t["unit"], "description": t["description"], "plc": t["plc"],
                     "trend": t["trend"], "trend_interval_s": t["trend_interval_s"],
                     "samples": s.get("samples", 0), "oldest": s.get("oldest"),
                     "is_bool": _is_bool(t["source"])})
    recorder = request.app.state.trend_recorder
    return {"retention_days": recorder.retention_days, "db_size": request.app.state.trend_db.size_bytes(),
            "tags": tags}


@router.get("/symbols")
async def symbols(request: Request, user: CurrentUser = Depends(require("viewer"))) -> list[dict[str, Any]]:
    """Opsatte symboler og deres tags (v0.80.0) — så Trends kan vise et symbols kurver samlet.
    Kun tegninger og tags brugeren må se; symboler uden synlige tags udelades."""
    scope = request.app.state.scope_service
    visible = scope.visible_tags(user)
    known = {t["name"] for t in request.app.state.tag_service.list()}
    out = []
    for s in request.app.state.symbol_service.trend_symbols(scope.drawing_ids(user)):
        tags = [t for t in s["tags"] if t in known and (visible is None or t in visible)]
        if tags:
            out.append({**s, "tags": tags})
    return out


@router.delete("/history/{name}")
async def delete_history(name: str, request: Request, user: CurrentUser = Depends(require("engineer"))) -> dict[str, Any]:
    """Slet al gemt historik for ét tag. Opsamlingen slås IKKE fra her (det er tagets "trend"-felt)."""
    deleted = request.app.state.trend_recorder.forget(name)
    audit(request, "trend.delete", name, {"samples": deleted})
    return {"deleted": deleted}
