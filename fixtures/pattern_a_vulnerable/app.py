"""Intentional CWE-78 fixture: unsafe shell composition in /diagnose.

This fixture deliberately uses only the Python standard library so it can run
in a network-disabled Celesto guest without installing dependencies.
"""

from __future__ import annotations

import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def handle_request(path: str, query: dict[str, list[str]]) -> tuple[int, dict[str, object]]:
    if path != "/diagnose":
        return 404, {"error": "not found"}
    host = query.get("host", ["127.0.0.1"])[0]
    # Deliberately vulnerable. This app is only run in a disposable guest.
    result = subprocess.run(
        f"printf 'diagnose %s\\n' {host}",
        shell=True,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return 200, {"output": result.stdout[:500], "error": result.stderr[:500]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib HTTPServer hook.
        status, payload = handle_request(
            urlparse(self.path).path,
            parse_qs(urlparse(self.path).query, keep_blank_values=True),
        )
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
