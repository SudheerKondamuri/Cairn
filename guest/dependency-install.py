#!/usr/bin/env python3
"""Install supported language dependencies inside the isolated guest."""

from __future__ import annotations

import base64
import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path("/input/source").resolve()


def decode(value: str) -> str:
    return base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")


def main() -> int:
    if len(sys.argv) not in (4, 5):
        print("usage: dependency-install RUNTIME MODE ALLOW_SCRIPTS", file=sys.stderr)
        return 2
    runtime, mode, allow_scripts = (decode(value) for value in sys.argv[1:4])
    root = (ROOT / (decode(sys.argv[4]) if len(sys.argv) == 5 else ".")).resolve()
    try:
        root.relative_to(ROOT)
        if not root.is_dir(): raise ValueError("working directory does not exist")
    except ValueError as exc:
        return _write({"error": str(exc)}, 2)
    if runtime not in {"python", "node", "go"}:
        return _write({"installed": False, "supported": False, "error": "unsupported runtime"}, 2)
    if mode not in {"offline", "controlled_network", "prebuilt"}:
        return _write({"installed": False, "error": "unsupported dependency mode"}, 2)
    if allow_scripts not in {"true", "false"}:
        return _write({"installed": False, "error": "invalid install-script policy"}, 2)

    command: list[str] | None = None
    manifest: str | None = None
    if mode == "prebuilt":
        return _write({"installed": False, "supported": True, "reason": "using image dependencies"}, 0)
    if runtime == "python" and (root / "requirements.txt").is_file():
        manifest = "requirements.txt"
        pathlib.Path("/input/deps").mkdir(parents=True, exist_ok=True)
        command = [
            "python3",
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "--no-cache-dir",
            "--target",
            "/input/deps",
            "-r",
            str(root / "requirements.txt"),
        ]
        if mode == "offline":
            command.insert(5, "--no-index")
    elif runtime == "python" and ((root / "pyproject.toml").is_file() or (root / "setup.py").is_file()):
        manifest = "pyproject.toml" if (root / "pyproject.toml").is_file() else "setup.py"
        if allow_scripts != "true":
            return _write({"error": "Installing this Python project runs its build backend. Enable package installation scripts, or supply requirements.txt with wheel dependencies."}, 2)
        command = ["python3", "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--no-cache-dir", "--target", "/input/deps", str(root)]
        if mode == "offline": command.append("--no-index")
    elif runtime == "node" and (root / "package-lock.json").is_file():
        manifest = "package-lock.json"
        command = ["npm", "ci", "--no-audit", "--no-fund"]
        if allow_scripts != "true":
            command.append("--ignore-scripts")
        if mode == "offline":
            command.append("--offline")
    elif runtime == "node" and (root / "package.json").is_file():
        manifest = "package.json"
        command = ["npm", "install", "--no-audit", "--no-fund"]
        if allow_scripts != "true":
            command.append("--ignore-scripts")
        if mode == "offline":
            command.append("--offline")
    elif runtime == "go" and (root / "go.mod").is_file():
        manifest = "go.mod"
        command = ["go", "mod", "download"]
        if mode == "offline":
            return _write({"installed": False, "supported": False, "error": "Go downloads require network mode; use a prebuilt image for offline modules."}, 2)


    if command is None:
        return _write(
            {
                "installed": False,
                "supported": True,
                "manifest": None,
                "reason": "no supported dependency manifest found",
            },
            0,
        )

    if runtime == "python" and allow_scripts != "true":
        command.append("--only-binary=:all:")
    try:
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=270,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _write(
            {
                "installed": False,
                "manifest": manifest,
                "command": command[:3],
                "error": type(exc).__name__,
            },
            1,
        )
    return _write(
        {
            "installed": result.returncode == 0,
            "manifest": manifest,
            "command": command[:3],
            "exit_code": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "network_mode": mode,
            "install_scripts": allow_scripts == "true",
        },
        result.returncode,
    )


def _write(value: dict[str, object], exit_code: int) -> int:
    print(json.dumps(value))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
