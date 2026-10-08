"""Adgang pr. tegning: hvilke tegninger, tags og betjeninger en bruger må se og bruge.

- `None` betyder "ingen begrænsning".
- Viewer/operatør med begrænset adgang ser kun deres tegninger og kun de tags der vises i dem
  (eksplicitte og automatiske bindinger).
- Operatører (begrænsede eller ej) kan kun betjene tags der har en klik-handling
  (click:write/toggle/pulse) i en tegning de har adgang til. Tekniker og admin kan betjene
  alle skrivbare tags.
"""

from __future__ import annotations

from .auth import CurrentUser, role_at_least
from .bindings import WRITE_CLICKS
from .drawings import DrawingService


class ScopeService:
    def __init__(self, drawings: DrawingService):
        self.drawings = drawings
        self.db = drawings.db

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
            tags.update(b["tag"] for b in self.drawings.effective_bindings(did) if b["tag"])
        return tags

    def operable_tags(self, user: CurrentUser) -> set[str] | None:
        if role_at_least(user.role, "engineer"):
            return None
        tags: set[str] = set()
        for did in self._ids(user):
            tags.update(b["tag"] for b in self.db.list_bindings(did) if b["anim"] in WRITE_CLICKS)
        return tags
