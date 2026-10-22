"""Tiny user-style HTTP app for a live Cairn smoke investigation.

This is intentionally separate from Cairn's canned fixture matrix. It has a
different route and parameter so the dynamic source-inspection path must find
the reproduction target.
"""

from __future__ import annotations

import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def handle_lookup(query: dict[str, list[str]]) -> dict[str, object]:
    name = query.get("q", ["localhost"])[0]
    # Deliberately vulnerable for this disposable Celesto Cloud test only.
    result = subprocess.run(
        f"printf 'lookup %s\\n' {name}",
        shell=True,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return {"output": result.stdout[:500], "error": result.stderr[:500]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib HTTPServer hook.
        parsed = urlparse(self.path)
        if parsed.path != "/lookup":
            status = 404
            payload: dict[str, object] = {"error": "not found"}
        else:
            status = 200
            payload = handle_lookup(parse_qs(parsed.query, keep_blank_values=True))
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
