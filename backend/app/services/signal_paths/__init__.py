"""Signalveje (se service.py). Pakken samler det offentlige: grænser, `valid_data` (backup) og `SignalPathService`."""

from .blocks import BLOCK_PREFIX  # noqa: F401
from .service import SignalPathService  # noqa: F401
from .validate import MAX_ANIMS, MAX_CONDITIONS, MAX_ELEMENTS, MAX_ENDS, MAX_UI_CHARS, PATH_ANIMS, valid_data  # noqa: F401
