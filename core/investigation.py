"""Validated, user-supplied investigation specifications."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


class InvestigationSpecError(ValueError):
    """Raised when a user-supplied investigation manifest is unsafe or incomplete."""


SUBJECT_TYPES = frozenset({"http_app", "package_harness"})
RUNTIMES = frozenset({"python", "node", "go"})
DEPENDENCY_MODES = frozenset({"offline", "controlled_network", "prebuilt"})
_RELATIVE_PATH = re.compile(r"^[^\\\x00]+$")


@dataclass(frozen=True)
class InvestigationSpec:
    """The non-secret runtime contract for one dynamic investigation."""

    subject_type: str
    report: str
    runtime: str
    start_argv: tuple[str, ...] = ()
    test_argv: tuple[str, ...] = ()
    port: int | None = None
    working_directory: str = "."
    dependency_mode: str = "offline"
    allow_network_during_install: bool = False
    allow_install_scripts: bool = False

    @classmethod
    def from_mapping(cls, value: object) -> "InvestigationSpec":
        if not isinstance(value, dict):
            raise InvestigationSpecError("investigation manifest must be an object")

        allowed = {
            "subject_type",
            "report",
            "runtime",
            "start_argv",
            "test_argv",
            "port",
            "working_directory",
            "dependency_mode",
            "allow_network_during_install",
            "allow_install_scripts",
        }
        unknown = set(value) - allowed
        if unknown:
            raise InvestigationSpecError(f"unknown manifest fields: {sorted(unknown)}")

        subject_type = _choice(value.get("subject_type"), "subject_type", SUBJECT_TYPES)
        runtime = _choice(value.get("runtime"), "runtime", RUNTIMES)
        report = _text(value.get("report"), "report", maximum=20_000)
        working_directory = _working_directory(value.get("working_directory", "."))
        start_argv = _argv(value.get("start_argv", ()), "start_argv")
        test_argv = _argv(value.get("test_argv", ()), "test_argv")

        port = value.get("port")
        if port is not None:
            if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
                raise InvestigationSpecError("port must be an integer between 1 and 65535")

        if subject_type == "http_app":
            if not start_argv:
                raise InvestigationSpecError("http_app requires start_argv")
            if port is None:
                raise InvestigationSpecError("http_app requires port")
        elif not test_argv:
            raise InvestigationSpecError("package_harness requires test_argv")

        dependency_mode = _choice(
            value.get("dependency_mode", "offline"),
            "dependency_mode",
            DEPENDENCY_MODES,
        )
        allow_network = value.get("allow_network_during_install", False)
        allow_scripts = value.get("allow_install_scripts", False)
        if not isinstance(allow_network, bool) or not isinstance(allow_scripts, bool):
            raise InvestigationSpecError("install permissions must be boolean")
        if dependency_mode == "controlled_network" and not allow_network:
            raise InvestigationSpecError(
                "controlled_network requires allow_network_during_install=true"
            )

        return cls(
            subject_type=subject_type,
            report=report,
            runtime=runtime,
            start_argv=start_argv,
            test_argv=test_argv,
            port=port,
            working_directory=working_directory,
            dependency_mode=dependency_mode,
            allow_network_during_install=allow_network,
            allow_install_scripts=allow_scripts,
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _choice(value: object, field: str, allowed: set[str] | frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise InvestigationSpecError(f"{field} must be one of: {', '.join(sorted(allowed))}")
    return value


def _text(value: object, field: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvestigationSpecError(f"{field} must be a non-empty string")
    if len(value) > maximum or "\x00" in value:
        raise InvestigationSpecError(f"{field} is too long or contains NUL")
    return value


def _argv(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise InvestigationSpecError(f"{field} must be an array of arguments")
    if len(value) > 32:
        raise InvestigationSpecError(f"{field} has too many arguments")
    arguments: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item or len(item) > 1024 or "\x00" in item:
            raise InvestigationSpecError(f"{field}[{index}] is invalid")
        arguments.append(item)
    return tuple(arguments)


def _working_directory(value: object) -> str:
    if not isinstance(value, str) or not value or not _RELATIVE_PATH.fullmatch(value):
        raise InvestigationSpecError("working_directory must be a relative POSIX path")
    if value.startswith("/") or any(part == ".." for part in value.split("/")):
        raise InvestigationSpecError("working_directory must stay inside the source bundle")
    return value.rstrip("/") or "."
