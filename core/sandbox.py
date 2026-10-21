"""Sandbox boundaries and safe, encoded guest-helper calls.

The real Celesto adapter is intentionally thin: the control plane owns the
client/session, while all target-app execution is delegated to the guest. A
fake adapter provides deterministic tests without pretending that a local
process is a Celesto evaluation.
"""

from __future__ import annotations

import base64
import binascii
import importlib
import json
import re
import shlex
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


EXECUTION_TARGET = "celesto_sandbox"
_HELPER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class SandboxAdapterError(RuntimeError):
    """Raised when a sandbox operation cannot be completed."""


@dataclass(frozen=True)
class SandboxResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = 0
    status_code: int | None = None
    body: str = ""
    elapsed_ms: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GuestInvocation:
    helper: str
    encoded_args: tuple[str, ...]

    @property
    def argv(self) -> tuple[str, ...]:
        return (self.helper, *self.encoded_args)


def _validate_helper(helper: str) -> str:
    if not isinstance(helper, str) or not _HELPER_NAME.fullmatch(helper):
        raise ValueError("helper must be a simple guest executable name")
    return helper


def encode_guest_arguments(arguments: Sequence[str]) -> tuple[str, ...]:
    """Encode each argument so a payload cannot alter an argument boundary."""

    if isinstance(arguments, (str, bytes)):
        raise TypeError("guest arguments must be a sequence of strings")
    encoded: list[str] = []
    for index, argument in enumerate(arguments):
        if not isinstance(argument, str):
            raise TypeError(f"guest argument {index} must be a string")
        if "\x00" in argument:
            raise ValueError(f"guest argument {index} contains NUL")
        encoded.append(base64.urlsafe_b64encode(argument.encode()).decode("ascii"))
    return tuple(encoded)


def decode_guest_arguments(arguments: Sequence[str]) -> list[str]:
    decoded: list[str] = []
    for index, argument in enumerate(arguments):
        if not isinstance(argument, str):
            raise TypeError(f"encoded guest argument {index} must be a string")
        try:
            raw = base64.b64decode(argument.encode("ascii"), altchars=b"-_", validate=True)
            decoded.append(raw.decode("utf-8"))
        except (binascii.Error, UnicodeDecodeError, UnicodeEncodeError, ValueError) as exc:
            raise ValueError(f"encoded guest argument {index} is invalid") from exc
    return decoded


def safe_guest_helper_argv(helper: str, arguments: Sequence[str]) -> list[str]:
    invocation = GuestInvocation(_validate_helper(helper), encode_guest_arguments(arguments))
    return list(invocation.argv)


def _coerce_result(value: Any) -> SandboxResult:
    if isinstance(value, SandboxResult):
        return value
    if isinstance(value, Mapping):
        return SandboxResult(
            ok=bool(value.get("ok", value.get("exit_code", 1) == 0)),
            stdout=str(value.get("stdout", "")),
            stderr=str(value.get("stderr", "")),
            exit_code=value.get("exit_code", 0),
            status_code=value.get("status_code"),
            body=str(value.get("body", "")),
            elapsed_ms=value.get("elapsed_ms"),
            metadata=value.get("metadata", {}),
        )
    return SandboxResult(
        ok=bool(getattr(value, "ok", True)),
        stdout=str(getattr(value, "stdout", "")),
        stderr=str(getattr(value, "stderr", "")),
        exit_code=getattr(value, "exit_code", 0),
    )


@runtime_checkable
class SandboxAdapter(Protocol):
    execution_target: str
    sandbox_name: str

    def inspect_source(self, path: str, start_line: int, end_line: int) -> str: ...
    def list_source(self, subpath: str) -> list[str]: ...
    def send_request(
        self, path: str, param_name: str, param_value: str, marker: str
    ) -> SandboxResult: ...
    def marker_present(self, marker: str) -> bool: ...
    def marker_any_present(self) -> bool: ...
    def clear_markers(self) -> None: ...
    def independent_request(
        self, path: str, param_name: str, param_value: str, marker: str
    ) -> SandboxResult: ...
    def install_dependencies(self) -> dict[str, Any]: ...
    def run_harness(self, marker: str) -> SandboxResult: ...
    def stop(self) -> None: ...
    def start(self) -> None: ...
    def cleanup(self) -> None: ...


class FakeSandboxAdapter:
    """Offline adapter for tests; it does not execute fixture code on the host."""

    execution_target = EXECUTION_TARGET

    def __init__(
        self,
        *,
        sandbox_name: str = "sbx-faketest1",
        source_files: Mapping[str, str] | None = None,
        request_handler: Callable[..., Any] | None = None,
    ) -> None:
        self.sandbox_name = sandbox_name
        self.source_files = dict(source_files or {})
        self.request_handler = request_handler
        self.requests: list[dict[str, str]] = []
        self.markers: set[str] = set()
        self.start_count = self.stop_count = self.cleanup_count = 0

    def inspect_source(self, path: str, start_line: int, end_line: int) -> str:
        source = self.source_files[path]
        lines = source.splitlines()
        return "\n".join(lines[start_line - 1 : end_line])

    def list_source(self, subpath: str) -> list[str]:
        prefix = "" if subpath in {"", "."} else subpath.rstrip("/") + "/"
        return sorted(
            name for name in self.source_files if name.startswith(prefix) and name != subpath
        )

    def send_request(self, path: str, param_name: str, param_value: str, marker: str) -> SandboxResult:
        self.clear_markers()
        request = {
            "path": path,
            "param_name": param_name,
            "param_value": param_value,
            "marker": marker,
        }
        self.requests.append(request)
        if self.request_handler is None:
            return SandboxResult(ok=True, status_code=200, body="", metadata=request)
        result = _coerce_result(self.request_handler(**request))
        if result.metadata.get("marker_detected") is True:
            self.markers.add(marker)
        return result

    def marker_present(self, marker: str) -> bool:
        return marker in self.markers

    def marker_any_present(self) -> bool:
        return bool(self.markers)

    def clear_markers(self) -> None:
        self.markers.clear()

    def independent_request(self, path: str, param_name: str, param_value: str, marker: str) -> SandboxResult:
        return self.send_request(path, param_name, param_value, marker)

    def install_dependencies(self) -> dict[str, Any]:
        return {
            "installed": False,
            "supported": True,
            "reason": "offline fake adapter has no package manager",
        }

    def run_harness(self, marker: str) -> SandboxResult:
        return SandboxResult(ok=True, stdout="", metadata={"marker_detected": False})

    def stop(self) -> None:
        self.stop_count += 1

    def start(self) -> None:
        self.start_count += 1

    def cleanup(self) -> None:
        self.cleanup_count += 1


class CelestoSandboxAdapter:
    """Adapter around an injected Celesto computer/session.

    ``computer`` must expose the SDK's guest ``run(command)`` operation. The
    adapter never receives a raw model command; it calls fixed helpers with
    URL-safe base64 arguments. The optional import is delayed until
    :meth:`from_environment`, so offline tests do not need Celesto installed.
    """

    execution_target = EXECUTION_TARGET

    def __init__(
        self,
        computer: Any,
        *,
        sandbox_name: str,
        helper_dir: str = "/opt/cairn",
        port: int = 5000,
        runtime: str = "python",
        dependency_mode: str = "offline",
        allow_install_scripts: bool = False,
        working_directory: str = ".",
        test_argv: Sequence[str] = (),
        audit: Callable[[str], None] | None = None,
    ) -> None:
        self.computer = computer
        self.sandbox_name = sandbox_name
        self.helper_dir = helper_dir.rstrip("/")
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("port must be an integer between 1 and 65535")
        self.port = port
        self.runtime = runtime
        self.dependency_mode = dependency_mode
        self.allow_install_scripts = allow_install_scripts
        self.working_directory = working_directory
        self.test_argv = tuple(test_argv)
        self._audit = audit

    @classmethod
    def from_environment(cls, *, sandbox_name: str, **computer_kwargs: Any) -> "CelestoSandboxAdapter":
        try:
            module = importlib.import_module("celesto")
        except ImportError as exc:
            raise SandboxAdapterError(
                "Celesto is not installed; install it before a live run"
            ) from exc
        computer_class = getattr(module, "Computer", None)
        if computer_class is None:
            raise SandboxAdapterError("installed celesto package has no Computer class")
        computer = computer_class(**computer_kwargs)
        return cls(computer, sandbox_name=sandbox_name)

    def _run_helper(self, helper: str, arguments: Sequence[str]) -> SandboxResult:
        argv = safe_guest_helper_argv(helper, arguments)
        helper_filename = argv[0] if argv[0].endswith(".py") else f"{argv[0]}.py"
        command = " ".join(
            [shlex.quote(f"{self.helper_dir}/{helper_filename}")]
            + [shlex.quote(item) for item in argv[1:]]
        )
        if self._audit:
            self._audit(command)
        return _coerce_result(self.computer.run(command))

    def run_guest_helper(self, helper: str, arguments: Sequence[str]) -> SandboxResult:
        return self._run_helper(helper, arguments)

    def inspect_source(self, path: str, start_line: int, end_line: int) -> str:
        result = self._run_helper("source-inspect", [path, str(start_line), str(end_line)])
        if not result.ok:
            raise SandboxAdapterError(result.stderr or "source inspection failed")
        return result.stdout

    def list_source(self, subpath: str) -> list[str]:
        result = self._run_helper("source-list", [subpath])
        if not result.ok:
            raise SandboxAdapterError(result.stderr or "source listing failed")
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SandboxAdapterError("source-list returned invalid JSON") from exc
        if not isinstance(value, list):
            raise SandboxAdapterError("source-list returned a non-list")
        return [str(item) for item in value]

    def send_request(self, path: str, param_name: str, param_value: str, marker: str) -> SandboxResult:
        result = self._run_helper(
            "http-probe", [str(self.port), path, param_name, param_value, marker, "any"]
        )
        try:
            payload = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, Mapping):
            result = SandboxResult(
                ok=result.ok,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                status_code=payload.get("status_code"),
                body=str(payload.get("body", "")),
                elapsed_ms=payload.get("elapsed_ms"),
                metadata={**dict(result.metadata), **payload},
            )
        return self._with_marker(result, marker, any_marker=True)

    def independent_request(self, path: str, param_name: str, param_value: str, marker: str) -> SandboxResult:
        result = self._run_helper(
            "http-probe", [str(self.port), path, param_name, param_value, marker, "exact"]
        )
        try:
            payload = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, Mapping):
            result = SandboxResult(
                ok=result.ok,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                status_code=payload.get("status_code"),
                body=str(payload.get("body", "")),
                elapsed_ms=payload.get("elapsed_ms"),
                metadata={**dict(result.metadata), **payload},
            )
        return self._with_marker(result, marker)

    def install_dependencies(self) -> dict[str, Any]:
        result = self._run_helper(
            "dependency-install",
            [
                self.runtime,
                self.dependency_mode,
                "true" if self.allow_install_scripts else "false",
            ],
        )
        try:
            payload = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError) as exc:
            raise SandboxAdapterError("dependency installer returned invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise SandboxAdapterError("dependency installer returned a non-object")
        return dict(payload)

    def run_harness(self, marker: str) -> SandboxResult:
        if not self.test_argv:
            raise SandboxAdapterError("no package test harness was configured")
        result = self._run_helper(
            "process-run",
            [self.runtime, self.working_directory, marker, *self.test_argv],
        )
        try:
            payload = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError) as exc:
            raise SandboxAdapterError("package harness returned invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise SandboxAdapterError("package harness returned a non-object")
        return SandboxResult(
            ok=bool(payload.get("ok", False)),
            stdout=str(payload.get("stdout", "")),
            stderr=str(payload.get("stderr", "")),
            exit_code=payload.get("exit_code"),
            metadata={"marker_detected": self.marker_present(marker), **dict(payload)},
        )

    def _with_marker(
        self, result: SandboxResult, marker: str, *, any_marker: bool = False
    ) -> SandboxResult:
        # Ignore any marker field emitted by the guest HTTP helper. The
        # control plane obtains the boolean through the separate marker-check
        # helper via the Celesto SDK.
        marker_detected = self.marker_any_present() if any_marker else self.marker_present(marker)
        return SandboxResult(
            **{
                "ok": result.ok,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "status_code": result.status_code,
                "body": result.body,
                "elapsed_ms": result.elapsed_ms,
                "metadata": {**dict(result.metadata), "marker_detected": marker_detected},
            }
        )

    def clear_markers(self) -> None:
        result = self._run_helper("marker-clear", [])
        if not result.ok:
            raise SandboxAdapterError(result.stderr or "marker clear failed")

    def marker_present(self, marker: str) -> bool:
        result = self._run_helper("marker-check", [marker])
        if not result.ok:
            return False
        return result.stdout.strip().lower() == "true"

    def marker_any_present(self) -> bool:
        result = self._run_helper("marker-any", [])
        if not result.ok:
            return False
        return result.stdout.strip().lower() == "true"

    def stop(self) -> None:
        method = getattr(self.computer, "stop", None)
        if not callable(method):
            raise SandboxAdapterError("Celesto computer lacks stop()")
        method()

    def start(self) -> None:
        method = getattr(self.computer, "start", None)
        if not callable(method):
            raise SandboxAdapterError("Celesto computer lacks start()")
        method()

    def cleanup(self) -> None:
        for name in ("delete", "cleanup", "close"):
            method = getattr(self.computer, name, None)
            if callable(method):
                method()
                return
        raise SandboxAdapterError("Celesto computer lacks delete/cleanup/close")
