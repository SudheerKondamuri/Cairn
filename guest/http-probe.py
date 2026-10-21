#!/usr/bin/env python3
"""GET one allowlisted fixture route from inside the guest."""

from __future__ import annotations

import base64
import json
import pathlib
import re
import shutil
import sys
import time
import urllib.parse
import urllib.error
import urllib.request


TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
PARAMETER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,63}$")


def decode(value: str) -> str:
    return base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")


def main() -> int:
    if len(sys.argv) != 7:
        print("usage: http-probe PORT PATH PARAM VALUE MARKER MODE", file=sys.stderr)
        return 2
    port_value, path, param_name, param_value, marker, mode = (
        decode(value) for value in sys.argv[1:]
    )
    try:
        port = int(port_value)
    except ValueError:
        print("invalid port", file=sys.stderr)
        return 2
    if not 1 <= port <= 65535:
        print("invalid port", file=sys.stderr)
        return 2
    if mode not in {"any", "exact"}:
        print("invalid marker mode", file=sys.stderr)
        return 2
    if not TOKEN.fullmatch(marker):
        print("invalid marker", file=sys.stderr)
        return 2
    markers = pathlib.Path("/tmp/cairn-markers")
    markers.mkdir(parents=True, exist_ok=True)
    for child in markers.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    if not path.startswith("/") or path.startswith("//") or any(char in path for char in "?#\\"):
        print("path is not a local route", file=sys.stderr)
        return 2
    if not PARAMETER.fullmatch(param_name):
        print("parameter is not allowlisted", file=sys.stderr)
        return 2
    url = f"http://127.0.0.1:{port}{path}?{urllib.parse.urlencode({param_name: param_value})}"
    started = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        print(
            json.dumps(
                {
                    "ok": True,
                    "status_code": exc.code,
                    "body": body,
                    "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
                }
            )
        )
        return 0
    except Exception as exc:  # outcome is surfaced as unknown to the controller
        print(
            json.dumps(
                {"ok": False, "error": type(exc).__name__}
            ),
            file=sys.stdout,
        )
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "status_code": status,
                "body": body,
                "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
