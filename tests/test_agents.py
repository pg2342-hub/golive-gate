import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from golive_gate import Response, http_agent


@pytest.fixture
def server():
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((body, self.headers.get("Authorization")))
            n = body["input"]["n"]
            reply = {"output": n * 2, "cost_usd": 0.01} if n >= 0 else {"raw": n}
            data = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}/agent", seen
    httpd.shutdown()


def test_http_agent_output_and_cost(server):
    url, seen = server
    agent = http_agent(url, headers={"Authorization": "Bearer t"})
    assert agent({"n": 3}) == Response(6, 0.01)
    assert seen == [({"input": {"n": 3}}, "Bearer t")]


def test_http_agent_without_output_key_returns_body(server):
    url, _ = server
    assert http_agent(url)({"n": -1}) == {"raw": -1}
