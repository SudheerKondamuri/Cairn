"""Patched Pattern A fixture using validation and an argument vector."""

from __future__ import annotations

import json
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


HOST_RE = re.compile(r"^[a-zA-Z0-9.\-]{1,255}$")


def handle_request(path: str, query: dict[str, list[str]]) -> tuple[int, dict[str, object]]:
    if path != "/diagnose":
        return 404, {"error": "not found"}
    host = query.get("host", ["127.0.0.1"])[0]
    if not HOST_RE.fullmatch(host):
        return 400, {"error": "invalid host"}
    result = subprocess.run(
        ["printf", "diagnose %s\n", host],
        shell=False,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return 200, {"output": result.stdout[:500], "error": result.stderr[:500]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib HTTPServer hook.
        parsed = urlparse(self.path)
        status, payload = handle_request(parsed.path, parse_qs(parsed.query, keep_blank_values=True))
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


def serve(port: int = 5000) -> None:
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":  # pragma: no cover - executed inside Celesto.
    serve()
