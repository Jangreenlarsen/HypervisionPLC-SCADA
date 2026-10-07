"""HypervisionPLC SCADA — FastAPI-app.

Kør (udvikling):  .venv/Scripts/python.exe -m app
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api.errors import install_error_handlers
from .api.routes import router
from .config import Settings, read_version
from .services.live_cache import LiveCache
from .services.manager import PlcManager, TransportFactory
from .services.plcs import PlcService
from .services.tags import TagService
from .storage.db import Database
from .storage.secrets import SecretStore

log = logging.getLogger("scada")


def create_app(settings: Settings | None = None, transport_factory: TransportFactory | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        for warning in settings.warn_insecure():
            log.warning("SIKKERHED: %s", warning)
        db = Database(settings.db_path)
        manager = PlcManager(db, SecretStore(settings.secrets_path), LiveCache(), settings, transport_factory)
        app.state.cache = manager.cache
        app.state.manager = manager
        app.state.plc_service = PlcService(manager)
        app.state.tag_service = TagService(manager)
        await manager.start_all()
        log.info("HypervisionPLC SCADA %s klar (data: %s)", read_version()["version"], settings.data_dir)
        try:
            yield
        finally:
            await manager.stop_all()
            db.close()

    app = FastAPI(title="HypervisionPLC SCADA", version=read_version()["version"], lifespan=lifespan)
    install_error_handlers(app)
    app.include_router(router)
    if settings.frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
