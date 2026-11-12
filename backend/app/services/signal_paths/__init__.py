"""Signalveje (se service.py). Pakken samler det offentlige: grænser, `valid_data` (backup) og `SignalPathService`."""

from .service import SignalPathService  # noqa: F401
from .validate import MAX_ELEMENTS, MAX_ENDS, MAX_UI_CHARS, is_legacy, strip_legacy, valid_data  # noqa: F401
