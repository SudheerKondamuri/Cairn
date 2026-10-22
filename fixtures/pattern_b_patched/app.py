"""Patched Pattern B fixture using validation and shutil.copy."""

from __future__ import annotations

import json
import os
import re
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


NAME_RE = re.compile(r"^[\w\-.]{1,128}$")


def handle_request(path: str, query: dict[str, list[str]]) -> tuple[int, dict[str, object]]:
    if path != "/convert":
        return 404, {"error": "not found"}
    filename = query.get("filename", ["sample.txt"])[0]
    if not NAME_RE.fullmatch(filename):
        return 400, {"error": "invalid filename"}
    try:
        shutil.copy(os.path.join("/srv/uploads", filename), f"/tmp/out_{filename}")
    except OSError:
        return 404, {"error": "source unavailable"}
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
