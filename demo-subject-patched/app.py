"""Patched Northstar Operations Diagnostics API for the negative demo case."""

from __future__ import annotations

import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


SERVICE = {
    "service": "northstar-operations-diagnostics",
    "version": "1.4.3",
    "environment": "staging",
}


def resolve_target(query: dict[str, list[str]]) -> dict[str, object]:
    """Return the diagnostic result without composing a shell command."""

    host = query.get("host", ["localhost"])[0]
    result = subprocess.run(
        ["printf", "resolved target=%s\n", host],
        shell=False,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return {
        **SERVICE,
        "target": host,
        "reachable": result.returncode == 0,
        "details": result.stdout[:500],
        "error": result.stderr[:500],
    }


def handle_request(path: str, query: dict[str, list[str]]) -> tuple[int, dict[str, object]]:
    if path == "/health":
        return 200, {**SERVICE, "status": "ok"}
    if path == "/api/v1/jobs/latest":
        return 200, {
            **SERVICE,
            "job": {"id": "diag-1042", "status": "completed", "target": "localhost"},
        }
    if path == "/api/v1/diagnostics/resolve":
        return 200, resolve_target(query)
    return 404, {"error": "not found", "service": SERVICE["service"]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib HTTPServer hook.
        parsed = urlparse(self.path)
        status, payload = handle_request(
            parsed.path,
            parse_qs(parsed.query, keep_blank_values=True),
        )
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


if __name__ == "__main__":  # pragma: no cover - executed inside Celesto.
    ThreadingHTTPServer(("127.0.0.1", 5002), Handler).serve_forever()
