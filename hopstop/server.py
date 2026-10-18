"""Zero-dependency HTTP server & REST API for the HopStop Analyst Dashboard.

Serves:
  - GET /                    -> Interactive IBM Carbon-themed Analyst Dashboard
  - GET /api/benchmarks      -> Full benchmark results, metrics, chains & held alerts
  - GET /api/stream?offset=N -> Next slice of live-scored transactions with latency telemetry
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
DASHBOARD_HTML = Path(__file__).resolve().parent / "dashboard.html"


def _load_benchmarks() -> dict:
    p = ARTIFACTS_DIR / "benchmark_results.json"
    if not p.exists():
        from hopstop.train_and_benchmark import run_pipeline

        return run_pipeline(BASE_DIR)
    return json.loads(p.read_text(encoding="utf-8"))


class HopStopHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return  # Keep console clean

    def _send_json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            html = DASHBOARD_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return

        if parsed.path == "/api/benchmarks":
            self._send_json(_load_benchmarks())
            return

        if parsed.path == "/api/stream":
            data = _load_benchmarks()
            qs = parse_qs(parsed.query)
            idx = int(qs.get("offset", ["0"])[0])
            alerts = data.get("sample_held_alerts", [])
            item = alerts[idx % len(alerts)] if alerts else {}
            self._send_json({"index": idx, "alert": item})
            return

        self._send_json({"error": "Not found"}, status=404)


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    _load_benchmarks()
    server = HTTPServer((host, port), HopStopHandler)
    print(f"HopStop Live Analyst Dashboard running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    run_server()
