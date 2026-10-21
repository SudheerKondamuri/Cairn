#!/usr/bin/env python3
"""Launch a user-supplied argv inside the guest without a shell."""

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
    if len(sys.argv) < 4:
        print("usage: process-launch RUNTIME WORKING_DIRECTORY ARG...", file=sys.stderr)
        return 2
    try:
        runtime = decode(sys.argv[1])
        if runtime not in {"python", "node", "go"}:
            raise ValueError("unsupported runtime")
        working_directory = safe_cwd(decode(sys.argv[2]))
        argv = [decode(value) for value in sys.argv[3:]]
        if not argv or any(not value or "\x00" in value for value in argv):
            raise ValueError("argv must contain non-empty strings")
        log_path = pathlib.Path("/tmp/cairn-subject.log")
        log = log_path.open("ab")
        environment = None
        if runtime == "python":
            environment = os.environ.copy()
            current = environment.get("PYTHONPATH", "")
            environment["PYTHONPATH"] = "/input/deps" + ((":" + current) if current else "")
        process = subprocess.Popen(
            argv,
            cwd=working_directory,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=environment,
            start_new_session=True,
            shell=False,
        )
        log.close()
        print(json.dumps({"pid": process.pid, "log_path": str(log_path)}))
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
