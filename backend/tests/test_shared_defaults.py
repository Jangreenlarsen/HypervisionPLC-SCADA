"""v6.9.2 (analysen 2026-11-13): standarderne findes i backend og som kopier i frontend — den fælles fil holder dem i sync.
Fejler testen, er flow_defs.py ændret uden at shared/flow_defaults.json (og frontendens kopier) er fulgt med."""
import json
from pathlib import Path

from app.services.flow_defs import shared_fixture

SHARED = Path(__file__).resolve().parents[2] / "shared" / "flow_defaults.json"


def test_backend_defaults_match_the_shared_file():
    want = json.loads(json.dumps(shared_fixture()))
    got = json.loads(SHARED.read_text(encoding="utf-8"))
    assert got == want, "Kør: python -m app.services.flow_defs --write-shared, og ret frontendens kopier (frontend-testen viser hvor)"
