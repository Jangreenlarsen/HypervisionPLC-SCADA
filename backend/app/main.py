"""HypervisionPLC SCADA — FastAPI-app.

Kør (udvikling):  .venv/Scripts/python.exe -m app
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.errors import install_error_handlers
from .api.alarms import router as alarms_router
from .api.auth import router as auth_router
from .api.backup import router as backup_router
from .api.energy import router as energy_router
from .api.schedules import router as schedules_router
from .api.trends import router as trends_router
from .api.drawings import router as drawings_router
from .api.live_ws import router as live_router
from .api.operate import router as operate_router
from .api.symbols import router as symbols_router
from .api.system import router as system_router
from .api.system_config import router as system_config_router
from .api.routes import router
from .config import Settings, read_version
from .services.alarms import AlarmService
from .services import sysconfig
from .services.audit import AuditService
from .services.auth import AuthService
from .services.backup import BackupService
from .services.operate import OperateService
from .services.drawings import DrawingService
from .services.scope import ScopeService
from .services.symbols import SymbolService
from .services.symbol_runtime import SymbolRuntime
from .services.symbol_operate import SymbolOperateService
from .services.schedules import ScheduleService
from .services.trends import TrendRecorder
from .services.live_cache import LiveCache
from .services.manager import PlcManager, TransportFactory
from .services.plcs import PlcService
from .services.tags import TagService
from .services.updates import UpdateService
from .storage.db import Database
from .storage.files import DrawingFiles
from .storage.trends_db import TrendDatabase
from .storage.secrets import SecretStore

log = logging.getLogger("scada")


def create_app(settings: Settings | None = None, transport_factory: TransportFactory | None = None) -> FastAPI:
    settings = settings or Settings()
    sysconfig.apply_overrides(settings)   # gemte trend-indstillinger (System › Konfiguration) overstyrer miljøvariablerne

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        for warning in settings.warn_insecure():
            log.warning("SIKKERHED: %s", warning)
        db = Database(settings.db_path)
        auth = AuthService(db, settings.data_dir, session_ttl_s=settings.session_hours * 3600)
        auth.bootstrap(settings.admin_password)
        app.state.auth_service = auth
        manager = PlcManager(db, SecretStore(settings.secrets_path), LiveCache(), settings, transport_factory)
        app.state.cache = manager.cache
        app.state.settings = settings
        app.state.manager = manager
        app.state.plc_service = PlcService(manager)
        app.state.tag_service = TagService(manager)
        app.state.audit_service = AuditService(db)
        app.state.operate_service = OperateService(manager, app.state.audit_service)
        drawing_files = DrawingFiles(settings.data_dir / "drawings")
        app.state.drawing_service = DrawingService(db, drawing_files, manager.cache)
        app.state.symbol_service = SymbolService(db, app.state.drawing_service)
        app.state.tag_service.symbol_usage = app.state.symbol_service.usage
        app.state.scope_service = ScopeService(app.state.drawing_service, app.state.symbol_service)
        app.state.backup_service = BackupService(manager, drawing_files, settings.data_dir / "backups",
                                                 keep=max(1, settings.backup_keep),
                                                 trend_keep=max(0, settings.trend_backup_keep))
        app.state.update_service = UpdateService(settings.data_dir, app.state.backup_service)
        await manager.start_all()
        app.state.alarm_service = AlarmService(manager, db, tick_s=settings.alarm_tick_s,
                                               comm_delay_s=settings.alarm_comm_delay_s)
        # Symbolstandard: position/tilstand som pseudo-tags + afvigelsesalarmer
        app.state.symbol_runtime = SymbolRuntime(db, manager.cache, app.state.drawing_service,
                                                 tick_s=settings.symbol_tick_s)
        app.state.symbol_runtime.reload()
        app.state.alarm_service.providers.append(app.state.symbol_runtime.alarm_conditions)
        app.state.symbol_operate_service = SymbolOperateService(app.state.operate_service, app.state.symbol_runtime,
                                                                app.state.audit_service)
        symbol_task = asyncio.create_task(app.state.symbol_runtime.run(), name="symbols")
        alarm_task = asyncio.create_task(app.state.alarm_service.run(), name="alarms")
        trend_db = TrendDatabase(settings.data_dir / "trends.db")
        app.state.trend_db = trend_db
        app.state.backup_service.trend_db = trend_db
        app.state.trend_recorder = TrendRecorder(manager, trend_db, flush_s=settings.trend_flush_s,
                                                 retention_days=settings.trend_days,
                                                 energy_days=settings.energy_days)
        # Slettet tag → historikken slettes, også værdier der endnu ligger i opsamlerens buffer
        app.state.tag_service.on_delete = app.state.trend_recorder.forget
        # Historik slået til/fra → opsamleren følger med straks (ikke først ved næste skrivning)
        app.state.tag_service.on_change = app.state.trend_recorder._refresh_config
        trend_task = asyncio.create_task(app.state.trend_recorder.run(), name="trends")
        app.state.schedule_service = ScheduleService(db, app.state.operate_service, manager)
        app.state.tag_service.schedule_usage = app.state.schedule_service.usage
        schedule_task = (asyncio.create_task(app.state.schedule_service.run(), name="schedules")
                         if settings.start_runtimes else None)
        backup_task = None
        if settings.backup_hours > 0 and settings.start_runtimes:
            backup_task = asyncio.create_task(app.state.backup_service.auto_backup_loop(settings.backup_hours))
        log.info("HypervisionPLC SCADA %s klar (data: %s)", read_version()["version"], settings.data_dir)
        try:
            yield
        finally:
            alarm_task.cancel()
            symbol_task.cancel()
            if schedule_task is not None:
                schedule_task.cancel()
            trend_task.cancel()
            try:
                await trend_task  # så de sidste samples bliver gemt
            except (asyncio.CancelledError, Exception):
                pass
            trend_db.close()
            if backup_task is not None:
                backup_task.cancel()
            await manager.stop_all()
            db.close()

    app = FastAPI(title="HypervisionPLC SCADA", version=read_version()["version"], lifespan=lifespan)
    install_error_handlers(app)

    @app.middleware("http")
    async def same_origin_writes(request: Request, call_next):  # type: ignore[no-untyped-def]
        # Forsvar mod CSRF ud over SameSite=Strict: ændrende kald fra en browser skal komme fra samme origin.
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host", ""):
                return JSONResponse({"error": "Afvist: forespørgslen kommer fra en anden side (origin)"}, status_code=403)
        return await call_next(request)

    app.include_router(auth_router)
    app.include_router(backup_router)
    app.include_router(system_router)
    app.include_router(system_config_router)
    app.include_router(alarms_router)
    app.include_router(trends_router)
    app.include_router(energy_router)
    app.include_router(schedules_router)
    app.include_router(router)
    app.include_router(drawings_router)
    app.include_router(symbols_router)
    app.include_router(live_router)
    app.include_router(operate_router)
    if settings.frontend_dir.is_dir():
        app.mount("/", FrontendFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app



class FrontendFiles(StaticFiles):
    """Frontend med cache-regler (BUGS.md v0.63.0): Vites filer under assets/ har hash i navnet og må gemmes længe; alt
    andet (index.html, SVG-Edit-værten under svgedit/, manualbilleder) skal genvalideres, så en opdatering slår igennem
    ved næste indlæsning i stedet for at browseren genbruger en gammel kopi."""

    async def get_response(self, path: str, scope: Any) -> Any:
        response = await super().get_response(path, scope)
        immutable = path.replace("\\", "/").startswith("assets/")
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable" if immutable else "no-cache"
        return response


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
