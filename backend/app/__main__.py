"""Start SCADA-serveren: `python -m app` (miljøvariabler: se app/config.py)."""

import uvicorn

from .config import Settings
from .main import configure_logging, create_app

settings = Settings()
configure_logging(settings.log_level)
uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level=settings.log_level.lower())
