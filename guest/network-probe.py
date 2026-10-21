#!/usr/bin/env python3
"""Probe guest-local loopback and an external destination for containment evidence."""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    local_port = int(sys.argv[1]) if len(sys.argv) == 2 else 5000
    local = subprocess.run(
        ["curl", "-m", "2", "-sS", f"http://127.0.0.1:{local_port}"],
        capture_output=True,
        check=False,
    )
    external = subprocess.run(
        ["curl", "-m", "3", "-sS", "https://example.com"],
        capture_output=True,
        check=False,
    )
    local_ok = local.returncode == 0
    external_blocked = external.returncode != 0
    print(json.dumps({"loopback_ok": local_ok, "external_blocked": external_blocked}))
    return 0 if local_ok and external_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
