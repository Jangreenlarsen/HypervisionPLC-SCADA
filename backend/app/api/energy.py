"""Energirapporter (lag 2): forbrug/produktion pr. dag, uge eller måned ud fra trend-historikken."""

from __future__ import annotations

import asyncio
import csv
import io
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from ..services.auth import CurrentUser
from ..services.energy import PERIODS, TZ, default_range, report
from ..services.errors import ServiceError
from .auth import require

router = APIRouter(prefix="/api/energy")


def _energy_tags(request: Request, user: CurrentUser) -> list[dict[str, Any]]:
    visible = request.app.state.scope_service.visible_tags(user)
    return [t for t in request.app.state.tag_service.list()
            if t.get("energy") and (visible is None or t["name"] in visible)]


def _report(request: Request, user: CurrentUser, tags: str | None, period: str,
            start: float | None, end: float | None) -> dict[str, Any]:
    if period not in PERIODS:
        raise ServiceError(400, f"Ukendt periode '{period}' — brug dag (day), uge (week) eller måned (month)")
    available = {t["name"]: t for t in _energy_tags(request, user)}
    names = [n.strip() for n in (tags or "").split(",") if n.strip()] or list(available)
    chosen = [available[n] for n in names if n in available]
    now = time.time()
    if start is None:
        start, default_end = default_range(period, now)
        end = default_end if end is None else end
    end = now if end is None else end
    if not start < end:
        raise ServiceError(400, "Starttidspunktet skal ligge før sluttidspunktet")
    tdb = request.app.state.trend_db
    try:
        return report(chosen, period, start, end, now, tdb.samples_with_prev)
    except ValueError as exc:
        raise ServiceError(400, str(exc)) from None


@router.get("/tags")
async def energy_tags(request: Request, user: CurrentUser = Depends(require("viewer"))) -> dict[str, Any]:
    stats = request.app.state.trend_db.stats()
    return {
        "energy_days": request.app.state.trend_recorder.energy_days,
        "tags": [{"name": t["name"], "description": t["description"], "unit": t["unit"], "energy": t["energy"],
                  "energy_factor": t["energy_factor"], "oldest": stats.get(t["name"], {}).get("oldest")}
                 for t in _energy_tags(request, user)],
    }


@router.get("/report")
async def energy_report(request: Request, tags: str | None = None, period: str = "day",
                        start: float | None = None, end: float | None = None,
                        user: CurrentUser = Depends(require("viewer"))) -> dict[str, Any]:
    # I en tråd: en lang periode må ikke stoppe polling, alarmer og live-værdier imens (kodeanalyse F6)
    return await asyncio.to_thread(_report, request, user, tags, period, start, end)


@router.get("/export")
async def energy_export(request: Request, tags: str | None = None, period: str = "day",
                        start: float | None = None, end: float | None = None,
                        user: CurrentUser = Depends(require("viewer"))) -> Response:
    """CSV (semikolon, decimalkomma, BOM) — åbner direkte i dansk Excel. Én kolonne pr. tag, kWh."""
    r = await asyncio.to_thread(_report, request, user, tags, period, start, end)
    names = list(r["series"])
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["periode", "fra", *[f"{r['meta'][n]['description'] or n} (kWh)" for n in names]])
    for i, b in enumerate(r["buckets"]):
        fra = datetime.fromtimestamp(b["start"], TZ).strftime("%Y-%m-%d %H:%M")
        w.writerow([b["label"], fra, *["" if r["series"][n][i] is None else f"{r['series'][n][i]:.4f}".replace(".", ",")
                                       for n in names]])
    w.writerow(["I alt", "", *[f"{r['totals'][n]:.4f}".replace(".", ",") for n in names]])
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="energi-{r["period"]}-{stamp}.csv"'})
