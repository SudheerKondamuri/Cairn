#!/usr/bin/env python3
"""Run a declared package harness inside the guest without a shell."""

from __future__ import annotations

import base64
import json
import os
import pathlib
import subprocess
import sys


ROOT = pathlib.Path("/input/source").resolve()


def decode(value: str) -> str:
    return base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")


def safe_cwd(value: str) -> pathlib.Path:
    candidate = (ROOT / value).resolve()
    candidate.relative_to(ROOT)
    if not candidate.is_dir():
        raise ValueError("working directory is not a directory")
    return candidate


def main() -> int:
    if len(sys.argv) < 5:
        print("usage: process-run RUNTIME WORKING_DIRECTORY MARKER ARG...", file=sys.stderr)
        return 2
    try:
        runtime = decode(sys.argv[1])
        if runtime not in {"python", "node", "go"}:
            raise ValueError("unsupported runtime")
        working_directory = safe_cwd(decode(sys.argv[2]))
        marker = decode(sys.argv[3])
        argv = [decode(value) for value in sys.argv[4:]]
        if not marker or not argv or any(not value or "\x00" in value for value in argv):
            raise ValueError("marker and argv are required")
        environment = os.environ.copy()
        environment["CAIRN_MARKER_TOKEN"] = marker
        if runtime == "python":
            current = environment.get("PYTHONPATH", "")
            environment["PYTHONPATH"] = "/input/deps" + ((":" + current) if current else "")
        result = subprocess.run(
            argv,
            cwd=working_directory,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            shell=False,
        )
        print(
            json.dumps(
                {
                    "ok": result.returncode == 0,
                    "exit_code": result.returncode,
                    "stdout": result.stdout[-8000:],
                    "stderr": result.stderr[-8000:],
                }
            )
        )
        return 0
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
