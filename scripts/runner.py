#!/usr/bin/env python3
"""Live Celesto Cloud helpers shared by Gate 0 and evaluation scripts.

This module is intentionally not imported by the API container. It requires a
local Celesto SDK installation and reads credentials from the process
environment. The SDK version installed for this workspace exposes cloud
network policy in the generated request model but not in ``Computer``'s public
CloudOptions, so the private-model adaptation below fails closed if that shape
changes rather than silently creating an open guest.
"""

from __future__ import annotations

import base64
import atexit
import hashlib
import io
import json
import os
import shlex
import signal
import sys
import tarfile
import threading
import time
from collections.abc import Sequence
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.audit import CommandAuditLog
from core.bundles import collect_source_files, source_digest
from core.investigation import InvestigationSpec
from core.sandbox import CelestoSandboxAdapter, SandboxResult


_ACTIVE_GUESTS: set["LiveGuest"] = set()
_SIGNALS_INSTALLED = False


def _cleanup_active_guests() -> None:
    for guest in list(_ACTIVE_GUESTS):
        try:
            guest.delete()
        except Exception:
            pass


def _handle_interrupt(signum: int, _frame: Any) -> None:
    _cleanup_active_guests()
    raise SystemExit(128 + signum)


def _install_cleanup_handlers() -> None:
    global _SIGNALS_INSTALLED
    if _SIGNALS_INSTALLED:
        return
    atexit.register(_cleanup_active_guests)
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, _handle_interrupt)
        signal.signal(signal.SIGTERM, _handle_interrupt)
    _SIGNALS_INSTALLED = True


class LiveRuntimeError(RuntimeError):
    """Raised when a live Celesto prerequisite is missing or unsafe."""


def load_env(path: Path = ROOT / ".env") -> None:
    """Load simple KEY=value entries without printing their values."""

    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value and value[0:1] == value[-1:] and value[0:1] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def unique_sandbox_name(prefix: str = "cairn") -> str:
    return f"sbx-{prefix}{uuid.uuid4().hex[:12]}"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _network_off(computer: Any) -> None:
    provider = getattr(computer, "_provider", None)
    body = getattr(provider, "_body", None)
    if body is None or not hasattr(body, "network_policy"):
        raise LiveRuntimeError(
            "installed Celesto Cloud SDK does not expose a network_policy request field; refusing an open guest"
        )
    try:
        from _celesto_cloud_api.models.network_policy import NetworkPolicy
        from _celesto_cloud_api.models.network_policy_mode import NetworkPolicyMode

        body.network_policy = NetworkPolicy(mode=NetworkPolicyMode.OFF)
    except (ImportError, AttributeError, TypeError) as exc:
        raise LiveRuntimeError("could not configure Celesto Cloud network policy off") from exc


class LiveGuest:
    """One persistent Cloud computer whose cleanup is explicit."""

    def __init__(self, sandbox_name: str, *, audit_path: Path | None = None) -> None:
        _install_cleanup_handlers()
        load_env()
        api_key = os.getenv("CELESTO_API_KEY", "")
        if not api_key or api_key == "replace-me":
            raise LiveRuntimeError(
                "CELESTO_API_KEY is missing; create /home/omni/Projects/Cairn/.env with a real key"
            )
        try:
            from celesto import Computer
        except ImportError as exc:
            raise LiveRuntimeError("install celesto before a live run: python3 -m pip install celesto") from exc

        options: dict[str, Any] = {"api_key": api_key}
        template_id = os.getenv("CELESTO_TEMPLATE_ID", "coding-agent")
        if template_id:
            options["template_id"] = template_id
        else:
            options["image"] = os.getenv("CELESTO_IMAGE", "ubuntu-desktop-24.04")
        base_url = os.getenv("CELESTO_BASE_URL")
        if base_url:
            options["base_url"] = base_url
        self.computer = Computer(provider="cloud", lifetime="persistent", **options)
        _network_off(self.computer)
        self.sandbox_name = sandbox_name
        self.audit = CommandAuditLog(
            audit_path or ROOT / "logs/commands.jsonl", sandbox_name=sandbox_name
        )
        self.started = False
        self._created = False
        self.deleted = False
        self.boot_to_ready_s: float | None = None
        _ACTIVE_GUESTS.add(self)

    @property
    def id(self) -> str | None:
        return getattr(self.computer, "id", None)

    def start(self) -> None:
        started = time.monotonic()
        if self._created:
            resume = getattr(self.computer, "resume", None)
            if not callable(resume):
                raise LiveRuntimeError("Celesto computer cannot resume a persistent guest")
            resume()
        else:
            self.computer.start()
            self._created = True
        self.started = True
        # Computer.start()/resume() return only after Celesto reports the guest
        # ready. The first fixed guest command is the application-level probe;
        # repeating remote ``true`` calls here adds tens of seconds and can
        # race the cloud transport's transient 409 while a guest is settling.
        self.boot_to_ready_s = time.monotonic() - started

    def run(self, command: str, *, timeout: int = 30) -> SandboxResult:
        if not isinstance(command, str) or not command.strip():
            raise ValueError("guest command must be non-empty")
        self.audit.allow(command)
        try:
            result = self.computer.run(command, timeout=timeout)
        except Exception:
            # The attempt was allowed to the guest, but its outcome is unknown.
            raise
        return SandboxResult(
            ok=result.exit_code == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
        )

    def upload_bytes(self, data: bytes, guest_path: str, *, executable: bool = False) -> None:
        if not guest_path.startswith("/") or ".." in Path(guest_path).parts:
            raise ValueError("guest_path must be absolute and contained")
        encoded = base64.b64encode(data).decode("ascii")
        parent = shlex.quote(str(Path(guest_path).parent))
        target = shlex.quote(guest_path)
        mode = " && chmod 700 " + target if executable else ""
        command = f"mkdir -p {parent} && printf '%s' {shlex.quote(encoded)} | base64 -d > {target}{mode}"
        result = self.run(command, timeout=30)
        if not result.ok:
            raise LiveRuntimeError(result.stderr or f"upload failed: {guest_path}")

    def upload_file(self, local_path: Path, guest_path: str, *, executable: bool = False) -> None:
        self.upload_bytes(local_path.read_bytes(), guest_path, executable=executable)

    def upload_files(self, files: Sequence[tuple[Path, str, bool]]) -> None:
        """Upload controlled files in one guest command to reduce cloud RTTs."""

        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:gz") as bundle:
            for local_path, guest_path, executable in files:
                if not guest_path.startswith("/") or ".." in Path(guest_path).parts:
                    raise ValueError("guest_path must be absolute and contained")
                data = local_path.read_bytes()
                info = tarfile.TarInfo(guest_path.lstrip("/"))
                info.size = len(data)
                info.mode = 0o700 if executable else 0o600
                bundle.addfile(info, io.BytesIO(data))
        encoded = base64.b64encode(archive.getvalue()).decode("ascii")
        command = f"printf %s {shlex.quote(encoded)} | base64 -d | tar -xzf - -C /"
        result = self.run(command, timeout=30)
        if not result.ok:
            raise LiveRuntimeError(result.stderr or "bundle upload failed")

    def stop(self) -> None:
        if self.started:
            self.computer.stop()
            self.started = False

    def delete(self) -> None:
        if not self.deleted:
            try:
                self.computer.delete()
            finally:
                self.deleted = True
                self.started = False
                _ACTIVE_GUESTS.discard(self)

    def adapter(
        self,
        *,
        port: int = 5000,
        runtime: str = "python",
        dependency_mode: str = "offline",
        allow_install_scripts: bool = False,
        working_directory: str = ".",
        test_argv: Sequence[str] = (),
    ) -> CelestoSandboxAdapter:
        return CelestoSandboxAdapter(
            self.computer,
            sandbox_name=self.sandbox_name,
            port=port,
            runtime=runtime,
            dependency_mode=dependency_mode,
            allow_install_scripts=allow_install_scripts,
            working_directory=working_directory,
            test_argv=test_argv,
            audit=lambda command: self.audit.allow(command),
        )

    def __enter__(self) -> "LiveGuest":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            self.stop()
        finally:
            self.delete()


def upload_guest_helpers(guest: LiveGuest) -> None:
    guest.run("mkdir -p /opt/cairn /input/source /srv/uploads /tmp/cairn-markers")
    python_setup = (
        "if command -v python3 >/dev/null 2>&1; then "
        "python_path=$(command -v python3); "
        "elif [ -x /opt/celesto/python/bin/python3 ]; then "
        "python_path=/opt/celesto/python/bin/python3; "
        "else exit 127; fi; "
        "ln -sf \"$python_path\" /usr/local/bin/python3; "
        "ln -sf \"$python_path\" /usr/local/bin/python"
    )
    result = guest.run(python_setup)
    if not result.ok:
        raise LiveRuntimeError("guest has no usable Python 3 runtime")
    guest.upload_files(
        [
            (path, f"/opt/cairn/{path.name}", True)
            for path in sorted((ROOT / "guest").glob("*.py"))
        ]
    )


def upload_source_tree(guest: LiveGuest, source_root: Path) -> dict[str, Any]:
    """Upload a validated user source tree and return its manifest identity."""

    files = collect_source_files(source_root)
    guest.upload_files(
        [
            (path, f"/input/source/{relative}", False)
            for path, relative in files
        ]
    )
    return {
        "file_count": len(files),
        "source_hash": source_digest(files),
        "files": [relative for _path, relative in files],
    }


def start_subject(guest: LiveGuest, spec: InvestigationSpec) -> dict[str, Any]:
    """Start an application inside the guest using a fixed no-shell launcher."""

    if spec.subject_type != "http_app":
        raise LiveRuntimeError("start_subject currently requires an http_app spec")
    adapter = guest.adapter(port=spec.port or 5000)
    working_directory = spec.working_directory
    result = adapter.run_guest_helper(
        "process-launch",
        [spec.runtime, working_directory, *spec.start_argv],
    )
    if not result.ok:
        raise LiveRuntimeError(result.stderr or result.stdout or "subject failed to start")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise LiveRuntimeError("subject launcher returned invalid JSON") from exc
    if not isinstance(value, dict) or not isinstance(value.get("pid"), int):
        raise LiveRuntimeError("subject launcher did not return a pid")
    return value


def start_fixture(guest: LiveGuest, fixture: Path) -> None:
    command = "python3 /opt/cairn/fixture.py >/tmp/cairn-fixture.log 2>&1 & echo $!"
    result = guest.run(command)
    if not result.ok:
        raise LiveRuntimeError(result.stderr or "fixture failed to start")


def wait_for_fixture(guest: LiveGuest, port: int) -> None:
    command = "python3 -c " + shlex.quote(
        f"import socket; s=socket.create_connection(('127.0.0.1',{port}), 1); s.close()"
    )
    last_error = "fixture did not become ready"
    for _ in range(30):
        result = guest.run(command, timeout=5)
        if result.ok:
            return
        last_error = result.stderr or last_error
        time.sleep(0.2)
    raise LiveRuntimeError(last_error)


def fixture_port(fixture: Path) -> int:
    return 5000 if any(part.startswith("pattern_a") for part in fixture.parts) else 5001


def fixture_route(fixture: Path) -> tuple[str, str]:
    return (
        ("/diagnose", "host")
        if any(part.startswith("pattern_a") for part in fixture.parts)
        else ("/convert", "filename")
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
