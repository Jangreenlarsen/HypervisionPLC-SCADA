"""Alarmnotifikation (lag 2) — kun admin: konfiguration, prøvebesked og status. Hemmeligheder (webhook-adresse/-token, SMTP-adgangskode)
er skriv-kun: svaret siger kun *om* de er sat. Se services/notifier.py."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from ..services.notifier import NotificationService
from .auth import ADMIN, audit

router = APIRouter(prefix="/api/system/notifications")


class WebhookBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    url: str | None = None
    token: str | None = None
    clear_url: bool = False
    clear_token: bool = False


class EmailBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    host: str | None = None
    port: int | None = None
    security: str | None = None
    username: str | None = None
    sender: str | None = None
    recipients: list[str] | None = None
    password: str | None = None
    clear_password: bool = False


class NotificationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    min_priority: str | None = None
    on_clear: bool | None = None
    batch_s: float | None = None
    webhook: WebhookBody | None = None
    email: EmailBody | None = None


def _svc(request: Request) -> NotificationService:
    return request.app.state.notifier


@router.get("", dependencies=[ADMIN])
async def get_notifications(request: Request) -> dict[str, Any]:
    return _svc(request).public()


@router.put("", dependencies=[ADMIN])
async def put_notifications(body: NotificationBody, request: Request) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True, exclude_none=True)
    result = _svc(request).update(data)
    # audit: hvad der er ændret, aldrig værdierne (adresser, token og adgangskode er hemmeligheder)
    audit(request, "system.notifications.config", "", {"changed": sorted(k for k in data if k not in ("webhook", "email")) +
                                                      [f"{ch}.{k}" for ch in ("webhook", "email") for k in (data.get(ch) or {})
                                                       if k not in ("url", "token", "password")],
                                                      "secrets": result["secrets_changed"]})
    return result["public"]


@router.post("/test", dependencies=[ADMIN])
async def test_notifications(request: Request) -> dict[str, Any]:
    results = await _svc(request).send_test()
    audit(request, "system.notifications.test", "", {ch: r["ok"] for ch, r in results.items()})
    return {"results": results, **_svc(request).public()}
