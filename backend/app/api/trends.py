"""Trends (lag 2): nedsamplede serier til grafer, CSV-eksport og oversigt — filtreret efter adgang."""

from __future__ import annotations

import csv
import io
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from ..services.auth import CurrentUser
from ..services.errors import ServiceError
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


def _names(request: Request, user: CurrentUser, tags: str) -> list[str]:
    names = [t.strip() for t in tags.split(",") if t.strip()]
    if not names:
        raise ServiceError(400, "Vælg mindst ét tag")
    if len(names) > 20:
        raise ServiceError(400, "Højst 20 tags ad gangen")
    visible = request.app.state.scope_service.visible_tags(user)
    if visible is not None:
        names = [n for n in names if n in visible]
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
        writer.writerow([datetime.fromtimestamp(ts).isoformat(timespec="milliseconds"), name,
                         "" if value is None else f"{value:.10g}".replace(".", ",")])
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="trend-{stamp}.csv"'})


@router.get("/info")
async def info(request: Request, user: CurrentUser = Depends(require("viewer"))) -> dict[str, Any]:
    visible = request.app.state.scope_service.visible_tags(user)
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


@router.delete("/history/{name}")
async def delete_history(name: str, request: Request, user: CurrentUser = Depends(require("engineer"))) -> dict[str, Any]:
    """Slet al gemt historik for ét tag. Opsamlingen slås IKKE fra her (det er tagets "trend"-felt)."""
    deleted = request.app.state.trend_recorder.forget(name)
    audit(request, "trend.delete", name, {"samples": deleted})
    return {"deleted": deleted}
