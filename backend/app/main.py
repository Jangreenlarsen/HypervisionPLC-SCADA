"""HypervisionPLC SCADA — FastAPI-app.

Kør (udvikling):  .venv/Scripts/python.exe -m app
"""

from __future__ import annotations

import asyncio
import logging
import socket
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
from .api.tls import router as tls_router
from .api.energy import router as energy_router
from .api.health import router as health_router
from .api.integration import admin_router as integration_admin_router, router as integration_router
from .api.notifications import router as notifications_router
from .api.metrics import admin_router as metrics_admin_router, router as metrics_router
from .api.schedules import router as schedules_router
from .api.trends import router as trends_router
from .api.drawings import router as drawings_router
from .api.live_ws import router as live_router
from .api.operate import router as operate_router
from .api.symbol_groups import router as symbol_groups_router
from .api.symbol_ports import router as symbol_ports_router
from .api.library import router as library_router
from .api.symbols import router as symbols_router
from .api.system import router as system_router
from .api.system_config import router as system_config_router
from .api.system_power import router as system_power_router
from .api.assist import router as assist_router
from .api.routes import router
from .config import Settings, read_version
from .services.alarms import AlarmService
from .services import sysconfig
from .services.netconfig import NetworkService
from .services.power import PowerService
from .services.hwprofile import HwProfileService
from .services.assistant import AssistantService
from .llm.client import LlmClient
from .services.trend_views import TrendViewService
from .services.audit import AuditService
from .services.auth import AuthService
from .services.backup import BackupService
from .services.backup_targets import BackupScheduler
from .services.tls_admin import TlsAdmin
from .services.operate import OperateService
from .services.drawings import DrawingService
from .services.scope import ScopeService
from .services.drawing_activity import suspended_tags
from .services.symbol_groups import SymbolGroupService
from .services.symbol_ports import SymbolPortService
from .services.library import LibraryService
from .services.symbols import SymbolService
from .services.symbol_runtime import SymbolRuntime
from .services.symbol_operate import SymbolOperateService
from .services.schedules import ScheduleService
from .services.trends import TrendRecorder
from .services.live_cache import LiveCache
from .services.health import HealthService
from .services.integration import IntegrationService
from .services.notifier import NotificationService
from .services.health_alarms import HealthAlarms
from .services.manager import PlcManager, TransportFactory
from .services.plcs import PlcService
from .services.plc_removal import PlcRemovalService
from .services.tags import TagService
from .services.updates import UpdateService
from .services.github_releases import GitHubReleases
from .storage.db import Database
from .storage.files import DrawingFiles
from .storage.trends_db import TrendDatabase
from .storage.secrets import SecretStore

log = logging.getLogger("scada")


def origin_matches_host(origin: str, host: str) -> bool:
    """Samme side? Værtsnavnet skal passe; porten sammenlignes kun, når `Host` har en (nginx sendte før `$host`
    uden port, så en side på en ikke-standardport blev afvist). Skemaet og porten i en forskellig Origin uden
    port i Host er dækket af SameSite=Strict på sessionen."""
    try:
        parts = urlsplit(origin)
        h = urlsplit("//" + host)
        o_port, h_port = parts.port, h.port
    except ValueError:
        return False
    o_host, h_host = (parts.hostname or "").lower(), (h.hostname or "").lower()
    if not o_host or o_host != h_host:
        return False
    if h_port is None:
        return True
    return (o_port or (443 if parts.scheme == "https" else 80)) == h_port


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
        secrets = SecretStore(settings.secrets_path)
        app.state.secrets = secrets
        app.state.metrics_auth_failures = 0
        app.state.metrics_last_log = {}
        manager = PlcManager(db, secrets, LiveCache(), settings, transport_factory)
        app.state.cache = manager.cache
        app.state.settings = settings
        app.state.health_service = HealthService()
        app.state.manager = manager
        app.state.plc_service = PlcService(manager)
        app.state.tag_service = TagService(manager)
        app.state.audit_service = AuditService(db)
        app.state.operate_service = OperateService(manager, app.state.audit_service)
        drawing_files = DrawingFiles(settings.data_dir / "drawings")
        app.state.drawing_service = DrawingService(db, drawing_files, manager.cache)
        app.state.symbol_service = SymbolService(db, app.state.drawing_service)
        app.state.symbol_group_service = SymbolGroupService(db, app.state.symbol_service)
        app.state.symbol_port_service = SymbolPortService(db)
        app.state.library_service = LibraryService(db, app.state.drawing_service, app.state.symbol_service)
        # Tags kun deaktiverede tegninger bruger pollas ikke (v1.6.0)
        manager.suspended_tags = lambda: suspended_tags(db, app.state.drawing_service, app.state.symbol_service)
        app.state.tag_service.symbol_usage = app.state.symbol_service.usage
        app.state.tag_service.auto_usage = lambda name: [   # B6: hvor tagget vises via automatisk binding
            f"{d['name']}: {b['element']}" for d in db.list_drawings()
            for b in app.state.drawing_service.effective_bindings(d["id"]) if b.get("source") == "auto" and b.get("tag") == name]
        app.state.scope_service = ScopeService(app.state.drawing_service, app.state.symbol_service)
        app.state.backup_service = BackupService(manager, drawing_files, settings.data_dir / "backups",
                                                 keep=max(1, settings.backup_keep),
                                                 trend_keep=max(0, settings.trend_backup_keep))
        app.state.update_service = UpdateService(settings.data_dir, app.state.backup_service)
        app.state.github_releases = GitHubReleases(settings.update_repo)
        app.state.network_service = NetworkService(settings.data_dir, settings.net_state_dir)
        app.state.power_service = PowerService(settings.data_dir, settings.net_state_dir)
        app.state.hw_profile = HwProfileService(settings.data_dir)
        app.state.assistant = AssistantService(settings.data_dir, app.state.hw_profile,
                                               LlmClient(f"http://127.0.0.1:{settings.llm_port}"), settings.net_state_dir)
        app.state.trend_view_service = TrendViewService(db)
        await manager.start_all()
        app.state.alarm_service = AlarmService(manager, db, tick_s=settings.alarm_tick_s,
                                               comm_delay_s=settings.alarm_comm_delay_s)
        # Symbolstandard: position/tilstand som pseudo-tags + afvigelsesalarmer
        app.state.symbol_runtime = SymbolRuntime(db, manager.cache, app.state.drawing_service,
                                                 tick_s=settings.symbol_tick_s)
        app.state.symbol_runtime.reload()
        app.state.alarm_service.providers.append(app.state.symbol_runtime.alarm_conditions)
        app.state.alarm_service.providers.append(app.state.operate_service.alarm_conditions)  # udgange der ikke kunne nulstilles
        app.state.symbol_operate_service = SymbolOperateService(app.state.operate_service, app.state.symbol_runtime,
                                                                app.state.audit_service)
        symbol_task = asyncio.create_task(app.state.symbol_runtime.run(), name="symbols")
        alarm_task = asyncio.create_task(app.state.alarm_service.run(), name="alarms")
        lag_task = asyncio.create_task(app.state.health_service.run_lag_probe(), name="loop-lag")
        # Alarmnotifikation (webhook/e-mail): lytter på alarmmotorens hændelser
        app.state.notifier = NotificationService(settings.data_dir, secrets)
        app.state.alarm_service.listeners.append(app.state.notifier.on_alarm_event)
        notifier_task = asyncio.create_task(app.state.notifier.run(), name="notifier")
        # Interne alarmer om SCADA selv (system-helbredet → almindelige alarmer med kvittering og historik)
        app.state.health_alarms = HealthAlarms(app.state.health_service, app.state,
                                               sample_s=settings.health_alarm_sample_s, warmup_s=settings.health_alarm_warmup_s,
                                               stored=lambda: app.state.alarm_service.state)
        health_alarm_task = None
        if settings.health_alarms and settings.start_runtimes:
            app.state.alarm_service.providers.append(app.state.health_alarms.alarm_conditions)
            health_alarm_task = asyncio.create_task(app.state.health_alarms.run(), name="health-alarms")
        trend_path, trend_warning = sysconfig.resolve_trend_db_path(settings.data_dir)
        app.state.trend_storage_warning = trend_warning
        trend_db = TrendDatabase(trend_path)
        app.state.trend_db = trend_db
        # Integrationer: API-nøgler og læse-API (kun fra live-cache, trend-DB og alarmmotor — aldrig direkte fra PLC'er)
        app.state.integration_service = IntegrationService(db, app.state.tag_service, manager.cache, app.state.alarm_service, trend_db,
                                                           instance=socket.gethostname())
        app.state.alarm_service.listeners.append(app.state.integration_service.on_alarm_event)   # SSE: alarmhændelser
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
        # Fjern PLC: flyt tags eller fjern alt (v3.34.0)
        app.state.plc_removal = PlcRemovalService(db, manager, app.state.tag_service, app.state.backup_service,
                                                  alarms=app.state.alarm_service,
                                                  forget_history=app.state.trend_recorder.forget,
                                                  on_changed=app.state.symbol_runtime.reload)
        schedule_task = (asyncio.create_task(app.state.schedule_service.run(), name="schedules")
                         if settings.start_runtimes else None)
        # Backup: én tidsplan (lokal backup + eksterne destinationer: SFTP/SCP/FTP(S)/HTTPS/SMB/NFS)
        app.state.backup_scheduler = BackupScheduler(settings.data_dir, secrets, app.state.backup_service,
                                                     default_hours=settings.backup_hours, state_dir=settings.net_state_dir)
        app.state.tls_admin = TlsAdmin(settings.data_dir, settings.net_state_dir)   # System › Certifikater (root-hjælper installerer)
        backup_task = (asyncio.create_task(app.state.backup_scheduler.run(), name="backup")
                       if settings.start_runtimes else None)
        log.info("HypervisionPLC SCADA %s klar (data: %s)", read_version()["version"], settings.data_dir)
        try:
            yield
        finally:
            alarm_task.cancel()
            lag_task.cancel()
            notifier_task.cancel()
            if health_alarm_task is not None:
                health_alarm_task.cancel()
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
            if origin and not origin_matches_host(origin, request.headers.get("host", "")):
                return JSONResponse({"error": "Afvist: forespørgslen kommer fra en anden side (origin)"}, status_code=403)
        return await call_next(request)

    app.include_router(auth_router)
    app.include_router(backup_router)
    app.include_router(tls_router)
    app.include_router(system_router)
    app.include_router(system_config_router)
    app.include_router(system_power_router)
    app.include_router(assist_router)
    app.include_router(alarms_router)
    app.include_router(trends_router)
    app.include_router(energy_router)
    app.include_router(schedules_router)
    app.include_router(health_router)
    app.include_router(integration_router)
    app.include_router(integration_admin_router)
    app.include_router(notifications_router)
    app.include_router(metrics_router)
    app.include_router(metrics_admin_router)
    app.include_router(router)
    app.include_router(drawings_router)
    app.include_router(symbols_router)
    app.include_router(symbol_groups_router)
    app.include_router(symbol_ports_router)
    app.include_router(library_router)
    app.include_router(live_router)
    app.include_router(operate_router)
    if settings.frontend_dir.is_dir():
        app.mount("/", FrontendFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app



class FrontendFiles(StaticFiles):
    """Frontend med cache-regler (BUGS.md v0.63.0): Vites filer under assets/ har hash i navnet og må gemmes længe; alt
    andet (index.html, tegne-editorens markør under draw/, manualbilleder) skal genvalideres, så en opdatering slår igennem
    ved næste indlæsning i stedet for at browseren genbruger en gammel kopi."""

    async def get_response(self, path: str, scope: Any) -> Any:
        response = await super().get_response(path, scope)
        immutable = path.replace("\\", "/").startswith("assets/")
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable" if immutable else "no-cache"
        return response


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
