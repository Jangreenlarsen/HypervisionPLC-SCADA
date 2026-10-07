"""Start mock-PLC'en med simuleret proces: `python -m mock_plc --port 8081`.

Login: scada / scada123
"""

import argparse

import uvicorn

from .app import create_mock_plc, default_state

parser = argparse.ArgumentParser(description="Mock HypervisionPLC")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8081)
args = parser.parse_args()

state = default_state()
state.sse_port = args.port  # den rigtige PLC har SSE på en separat port; mock'en bruger samme
uvicorn.run(create_mock_plc(state, simulate_process=True), host=args.host, port=args.port, log_level="warning")
