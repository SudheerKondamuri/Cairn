"""Northstar Operations Diagnostics API used for the Cairn demo.

This is a self-owned, dependency-free service with a small amount of realistic
business context. It has no external network dependency and must only be run in
a disposable Cairn/Celesto guest or a local test process.
"""

from __future__ import annotations

import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


SERVICE = {
    "service": "northstar-operations-diagnostics",
    "version": "1.4.2",
    "environment": "staging",
}


def resolve_target(query: dict[str, list[str]]) -> dict[str, object]:
    """Return the diagnostic result for one operator-supplied host value."""

    host = query.get("host", ["localhost"])[0]
    # Legacy diagnostic wrapper: the host value is incorrectly composed into a
    # shell command. Cairn's demo report asks whether this claim is reproducible.
    result = subprocess.run(
        f"printf 'resolved target=%s\\n' {host}",
        shell=True,
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
