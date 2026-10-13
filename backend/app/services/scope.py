"""Adgang pr. tegning: hvilke tegninger, tags og betjeninger en bruger må se og bruge.

- `None` betyder "ingen begrænsning".
- Viewer/operatør med begrænset adgang ser kun deres tegninger og kun de tags der vises i dem
  (eksplicitte og automatiske bindinger).
- Operatører (begrænsede eller ej) kan kun betjene tags der har en klik-handling
  (click:write/toggle/pulse) i en tegning de har adgang til — eksplicit eller fra et betjeningssymbol. Tekniker og admin kan betjene
  alle skrivbare tags.
"""

from __future__ import annotations

from typing import Any

from .auth import CurrentUser, role_at_least
from .bindings import WRITE_CLICKS, binding_tags
from .drawings import DrawingService


class ScopeService:
    def __init__(self, drawings: DrawingService, symbols: Any = None):
        self.drawings = drawings
        self.db = drawings.db
        self.symbols = symbols  # SymbolService: symbol-konfigurationernes tags og pseudo-tags hører til tegningen

    def drawing_ids(self, user: CurrentUser) -> set[str] | None:
        return None if user.drawings is None else set(user.drawings)

    def can_see_drawing(self, user: CurrentUser, drawing_id: str) -> bool:
        allowed = self.drawing_ids(user)
        return allowed is None or drawing_id in allowed

    def _ids(self, user: CurrentUser) -> list[str]:
        allowed = self.drawing_ids(user)
        return [d["id"] for d in self.db.list_drawings() if allowed is None or d["id"] in allowed]

    def visible_tags(self, user: CurrentUser) -> set[str] | None:
        if user.drawings is None:
            return None
        tags: set[str] = set()
        for did in self._ids(user):
            tags.update(t for b in self.drawings.effective_bindings(did) for t in binding_tags(b))
            if self.symbols is not None:
                tags.update(self.symbols.tags_for_drawing(did))
        return tags

    # Hvilke klik-handlinger der giver ret til hvilken betjening (operatører)
    ACTION_ANIMS = {"write": ("click:write", "click:select"), "toggle": ("click:toggle",), "pulse": ("click:pulse",)}

    def _operator_bindings(self, user: CurrentUser) -> list[dict[str, Any]]:
        # Effektive bindinger: også de automatiske fra betjeningssymboler (dannes kun for skrivbare tags)
        return [b for did in self._ids(user) for b in self.drawings.effective_bindings(did) if b["anim"] in WRITE_CLICKS]

    def operable_tags(self, user: CurrentUser, action: str | None = None) -> set[str] | None:
        """Tags operatøren må betjene — med `action` kun dem hvor netop den handling findes i en tegning
        (en til/fra-knap giver ikke ret til at skrive vilkårlige værdier)."""
        if role_at_least(user.role, "engineer"):
            return None
        anims = self.ACTION_ANIMS.get(action, WRITE_CLICKS) if action else WRITE_CLICKS
        return {b["tag"] for b in self._operator_bindings(user) if b["anim"] in anims}

    def write_values(self, user: CurrentUser, tag: str) -> set[float] | None:
        """Tilladte værdier ved skrivning: None = alle (inden for min/max) hvis tagget har et setpunkt-felt;
        ellers kun omskifternes positioner."""
        if role_at_least(user.role, "engineer"):
            return None
        bindings = [b for b in self._operator_bindings(user) if b["tag"] == tag]
        if any(b["anim"] == "click:write" for b in bindings):
            return None
        return {float(p["value"]) for b in bindings if b["anim"] == "click:select" for p in b["params"]["positions"]}
