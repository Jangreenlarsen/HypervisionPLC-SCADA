"""Gemte trend-visninger (v1.16.0): et navn (fx "Tank temp") på et udvalg af tags, deres grafer og perioden — vælges i en dropdown på Trends.
Gemmes som én indstilling pr. visning (`setting.trendview.<navn>`), så samtidige ændringer af andre visninger aldrig overskriver hinanden."""

from __future__ import annotations

import re
from typing import Any

from ..storage.db import Database
from .errors import ServiceError

MAX_VIEWS = 100
MAX_NAME = 40
MAX_TAGS = 40
MAX_CHARTS = 8
RANGE_IDS = ("15m", "1h", "8h", "24h", "7d", "30d")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def clean_view(raw: dict[str, Any]) -> dict[str, Any]:
    """Valider og normalisér en visning: {name, tags[], assign{tag: graf 1-8}, range}. Kaster ServiceError 400."""
    name = str(raw.get("name") or "").strip()
    if not name or len(name) > MAX_NAME or _CTRL.search(name):
        raise ServiceError(400, f"Navnet skal være 1-{MAX_NAME} tegn (ingen styretegn)")
    tags = raw.get("tags")
    if not isinstance(tags, list) or not tags or not all(isinstance(t, str) and 0 < len(t) <= 64 for t in tags):
        raise ServiceError(400, "Vælg mindst ét tag til visningen")
    tags = list(dict.fromkeys(tags))
    if len(tags) > MAX_TAGS:
        raise ServiceError(400, f"En visning kan højst have {MAX_TAGS} tags")
    assign_in = raw.get("assign") or {}
    if not isinstance(assign_in, dict):
        raise ServiceError(400, "assign skal være et objekt (tag → graf-nummer)")
    assign: dict[str, int] = {}
    for tag, n in assign_in.items():
        if tag in tags and isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= MAX_CHARTS:
            assign[tag] = n
    rng = raw.get("range", "1h")
    if rng not in RANGE_IDS:
        rng = "1h"   # "brugerdefineret" huskes ikke
    return {"name": name, "tags": tags, "assign": assign, "range": rng}


class TrendViewService:
    def __init__(self, db: Database):
        self.db = db

    def list(self) -> list[dict[str, Any]]:
        return self.db.list_trend_views()

    def save(self, user: str, raw: dict[str, Any]) -> dict[str, Any]:
        view = clean_view(raw)
        existing = self.db.list_trend_views()
        if not any(v["name"].casefold() == view["name"].casefold() for v in existing) and len(existing) >= MAX_VIEWS:
            raise ServiceError(400, f"Der kan højst gemmes {MAX_VIEWS} visninger")
        # samme navn med andre store/små bogstaver erstatter den eksisterende (navnet er unikt uden hensyn til dem)
        self.db.set_trend_view(view["name"], view)
        return view

    def delete(self, name: str) -> None:
        if not self.db.set_trend_view(name, None):
            raise ServiceError(404, f"Visningen '{name}' findes ikke")
