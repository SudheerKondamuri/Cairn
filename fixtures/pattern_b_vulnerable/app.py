"""Intentional CWE-78 fixture: unsafe shell composition in /convert."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def handle_request(path: str, query: dict[str, list[str]]) -> tuple[int, dict[str, object]]:
    if path != "/convert":
        return 404, {"error": "not found"}
    filename = query.get("filename", ["sample.txt"])[0]
    # Deliberately vulnerable. The guest contains only disposable fixture data.
    os.system(f"cp /srv/uploads/{filename} /tmp/out_{filename}")
    return 200, {"status": "done"}


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


def serve(port: int = 5001) -> None:
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":  # pragma: no cover - executed inside Celesto.
    serve()
