"""Fælles testopsætning: en server med en PLC, tre tags og en tegning (kedel → pumpe → rør → ventil → radiator), og en
falsk LLM til hjælperens tests. (Var tidligere en del af signalvejenes tests, fjernet i v6.0.0-b0395.)"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_PW = "test-admin-pw-1"
S = 'stroke="#555" stroke-width="10" fill="none"'
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 200">'
       '<g id="kedel" data-hv-type="kedel" data-hv-name="Kedel"><rect id="kedel_hus" width="40" height="60" fill="#ccc"/></g>'
       f'<path id="r1" data-hv-pipe="1" d="M40 30 H100" {S}/>'
       '<g id="p1" data-hv-type="pumpe" data-hv-name="P1"><circle id="p1_hjul" cx="120" cy="30" r="20" fill="#ccc" stroke="#555"/></g>'
       f'<path id="r2" data-hv-pipe="1" d="M140 30 H200" {S}/>'
       '<g id="t1" data-hv-type="t_stykke" data-hv-name="T1">'
       f'<path id="t1_a" d="M200 30 H245" {S}/><path id="t1_b" d="M245 30 H290" {S}/><path id="t1_c" d="M245 25 V0" {S}/></g>'
       f'<path id="r3" data-hv-pipe="1" d="M290 30 H350" {S}/>'
       '<g id="v2" data-hv-type="kugleventil" data-hv-name="V2"><path id="v2_hus" d="M350 20 L380 40" fill="#ccc"/></g>'
       f'<path id="r4" data-hv-pipe="1" d="M380 30 H440" {S}/>'
       '<g id="rad" data-hv-type="radiator" data-hv-name="Radiator"><rect id="rad_hus" x="440" width="40" height="60" fill="#ccc"/></g>'
       '</svg>')


@pytest.fixture
def api(tmp_path, mock_plc):
    settings = Settings(data_dir=tmp_path / "data", frontend_dir=tmp_path / "nope", admin_password=ADMIN_PW, backup_hours=0,
                        start_runtimes=False)
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada", "password": "scada123",
                                  "sse_enabled": False})
        for t in [{"name": "P1_drift", "source": "plc1:coil:1"}, {"name": "V2_stilling", "source": "plc1:hr:2"},
                  {"name": "Ekstra", "source": "plc1:coil:3"}]:
            assert c.post("/api/tags", json=t).status_code == 201
        d = c.post("/api/drawings", json={"name": "Varme", "svg": SVG}).json()["drawing"]["id"]
        c.d = d
        yield c


def cfg(c, el):
    return c.get(f"/api/drawings/{c.d}/symbols/{el}/config").json()["config"]


def _llm(api, answer):
    import json as _json

    import httpx

    from app.llm.client import LlmClient
    from tests.test_assist import hw
    api.app.state.hw_profile.detector = hw()
    seen = []

    def handler(req):
        if req.url.path == "/v1/chat/completions":
            seen.append(_json.loads(req.content))
            return httpx.Response(200, json={"model": "m", "usage": {"prompt_tokens": 300, "completion_tokens": 40},
                                             "choices": [{"message": {"content": _json.dumps(answer)}}]})
        return httpx.Response(200, json={})
    api.app.state.assistant.client = LlmClient(transport=httpx.MockTransport(handler))
    return seen


def _events(r):
    import json as _json
    return [_json.loads(x[5:]) for x in r.text.splitlines() if x.startswith("data:")]
