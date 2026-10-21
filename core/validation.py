"""Strict schemas for the bounded tools exposed to the investigation agent."""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit


class ToolValidationError(ValueError):
    """Raised when an agent tool call is outside the Cairn contract."""


TOOL_NAMES = frozenset(
    {
        "inspect_source",
        "list_source",
        "send_request",
        "submit_finding",
        "install_dependencies",
        "run_harness",
    }
)
VERDICTS = frozenset({"verified", "not_reproduced", "inconclusive"})
ROUTES = {
    "/diagnose": "host",
    "/convert": "filename",
}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_PARAMETER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class ToolPolicy:
    """Per-investigation request policy.

    ``routes`` keeps the original fixture contract when provided. ``None``
    enables arbitrary relative HTTP paths and safe parameter names while the
    sandbox adapter still fixes the destination to guest loopback.
    """

    routes: Mapping[str, str] | None
    allow_dependency_install: bool = False
    dependency_mode: str = "offline"
    allow_harness: bool = False
    requires_marker_recheck: bool = True
    allow_http_requests: bool = True

    @classmethod
    def dynamic_http(
        cls,
        *,
        allow_dependency_install: bool = False,
        dependency_mode: str = "offline",
    ) -> "ToolPolicy":
        if dependency_mode not in {"offline", "controlled_network", "prebuilt"}:
            raise ValueError("unsupported dependency mode")
        return cls(
            routes=None,
            allow_dependency_install=allow_dependency_install,
            dependency_mode=dependency_mode,
        )

    @classmethod
    def package_harness(
        cls,
        *,
        allow_dependency_install: bool = True,
        dependency_mode: str = "offline",
    ) -> "ToolPolicy":
        policy = cls.dynamic_http(
            allow_dependency_install=allow_dependency_install,
            dependency_mode=dependency_mode,
        )
        return cls(
            routes=policy.routes,
            allow_dependency_install=policy.allow_dependency_install,
            dependency_mode=policy.dependency_mode,
            allow_harness=True,
            requires_marker_recheck=False,
            allow_http_requests=False,
        )

    @property
    def is_dynamic(self) -> bool:
        return self.routes is None


DEFAULT_TOOL_POLICY = ToolPolicy(routes=ROUTES)

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "inspect_source": {
        "type": "object",
        "additionalProperties": False,
        "required": ["path", "start_line", "end_line"],
        "properties": {
            "path": {"type": "string"},
            "start_line": {"type": "integer", "minimum": 1, "maximum": 200},
            "end_line": {"type": "integer", "minimum": 1, "maximum": 200},
        },
    },
    "list_source": {
        "type": "object",
        "additionalProperties": False,
        "required": ["subpath"],
        "properties": {"subpath": {"type": "string"}},
    },
    "send_request": {
        "type": "object",
        "additionalProperties": False,
        "required": ["path", "param_name", "param_value"],
        "properties": {
            "path": {"type": "string", "enum": sorted(ROUTES)},
            "param_name": {"type": "string"},
            "param_value": {"type": "string", "maxLength": 1024},
        },
    },
    "submit_finding": {
        "type": "object",
        "additionalProperties": False,
        "required": ["verdict", "path", "param_name", "param_value", "rationale"],
        "properties": {
            "verdict": {"type": "string", "enum": sorted(VERDICTS)},
            "path": {"type": "string", "enum": sorted(ROUTES)},
            "param_name": {"type": "string"},
            "param_value": {"type": "string", "maxLength": 1024},
            "rationale": {"type": "string", "minLength": 1, "maxLength": 8192},
        },
    },
}


def tool_schemas_for_policy(policy: ToolPolicy | None = None) -> dict[str, dict[str, Any]]:
    """Return tool schemas adjusted for the selected route policy."""

    selected = policy or DEFAULT_TOOL_POLICY
    schemas = deepcopy(TOOL_SCHEMAS)
    if selected.is_dynamic:
        for tool_name in ("send_request", "submit_finding"):
            schemas[tool_name]["properties"]["path"].pop("enum", None)
    if not selected.allow_http_requests:
        schemas.pop("send_request", None)
    if selected.allow_dependency_install:
        schemas["install_dependencies"] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        }
    if selected.allow_harness:
        schemas["run_harness"] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        }
        schemas["submit_finding"]["required"] = ["verdict", "rationale"]
    return schemas


def _fail(message: str) -> None:
    raise ToolValidationError(message)


def _string(value: Any, field: str, *, max_length: int) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{field} must be a non-empty string")
    if len(value) > max_length:
        _fail(f"{field} exceeds {max_length} characters")
    if _CONTROL.search(value):
        _fail(f"{field} contains a control character")
    return value


def _source_path(value: Any) -> str:
    path = _string(value, "path", max_length=512)
    decoded = unquote(path)
    if path == "/input/source":
        return "."
    if path.startswith("/input/source/"):
        path = path[len("/input/source/") :]
        decoded = unquote(path)
    if path.startswith(('/', '\\')) or '\\' in path or ':' in path:
        _fail("source path must be a relative POSIX path")
    if any(part == ".." for part in decoded.split("/")):
        _fail("source path must not traverse a parent directory")
    return path


def _line(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(f"{field} must be an integer >= 1")
    return value


def _route(value: Any, policy: ToolPolicy, field: str = "path") -> str:
    path = _string(value, field, max_length=512)
    parsed = urlsplit(path)
    if (
        parsed.scheme
        or parsed.netloc
        or not path.startswith("/")
        or path.startswith("//")
        or any(character in path for character in "?#\\")
    ):
        _fail(f"{field} must be a relative local HTTP path")
    if policy.routes is not None and path not in policy.routes:
        _fail(f"{field} must be one of: {', '.join(sorted(policy.routes))}")
    return path


def _param_name(value: Any, path: str, policy: ToolPolicy) -> str:
    name = _string(value, "param_name", max_length=64)
    expected = policy.routes.get(path) if policy.routes is not None else None
    if expected is not None and name != expected:
        _fail(f"param_name must be {expected!r} for {path}")
    if expected is None and not _PARAMETER.fullmatch(name):
        _fail("param_name must be a simple query parameter name")
    return name


def _param_value(value: Any) -> str:
    raw = _string(value, "param_value", max_length=1024)
    # Hosted models sometimes percent-encode an exploit payload before
    # returning it. The guest helper performs the only HTTP encoding step, so
    # normalize one layer here to avoid turning `%3B` into a literal string in
    # the fixture. This still leaves shell syntax inside the controlled guest
    # HTTP request; it never becomes a control-plane command.
    normalized = unquote(raw)
    return _string(normalized, "param_value", max_length=1024)


def validate_tool_call(
    tool_name: str | Mapping[str, Any],
    arguments: Mapping[str, Any] | None = None,
    *,
    policy: ToolPolicy | None = None,
) -> dict[str, Any]:
    """Validate and normalize a model tool call.

    No tool has a shell, host, URL, or filesystem-write argument. The payload
    is kept as structured data until the guest HTTP helper URL-encodes it.
    """

    selected_policy = policy or DEFAULT_TOOL_POLICY
    if arguments is None and isinstance(tool_name, Mapping):
        call = tool_name
        tool_name = call.get("name", "")
        arguments = call.get("arguments")
    if not isinstance(tool_name, str) or tool_name not in TOOL_NAMES:
        _fail(f"unsupported tool: {tool_name!r}")
    if not isinstance(arguments, Mapping):
        _fail(f"arguments for {tool_name} must be an object")
    if tool_name == "install_dependencies" and not selected_policy.allow_dependency_install:
        _fail("dependency installation is not enabled for this investigation")
    if tool_name == "run_harness" and not selected_policy.allow_harness:
        _fail("test harness execution is not enabled for this investigation")
    if tool_name == "send_request" and not selected_policy.allow_http_requests:
        _fail("HTTP requests are not enabled for this investigation")

    specs = {
        "inspect_source": ({"path", "start_line", "end_line"}, set()),
        "list_source": ({"subpath"}, set()),
        "send_request": ({"path", "param_name", "param_value"}, set()),
        "submit_finding": (
            {"verdict", "path", "param_name", "param_value", "rationale"},
            set(),
        ),
        "install_dependencies": (set(), set()),
        "run_harness": (set(), set()),
    }
    required, optional = specs[tool_name]
    if tool_name == "submit_finding" and selected_policy.allow_harness:
        required = {"verdict", "rationale"}
    keys = set(arguments)
    missing = required - keys
    extra = keys - required - optional
    if missing:
        _fail(f"{tool_name} missing fields: {sorted(missing)}")
    if extra:
        _fail(f"{tool_name} has unknown fields: {sorted(extra)}")

    if tool_name == "install_dependencies":
        return {}
    if tool_name == "run_harness":
        return {}

    if tool_name == "inspect_source":
        start_line = _line(arguments["start_line"], "start_line")
        end_line = _line(arguments["end_line"], "end_line")
        if end_line < start_line or end_line - start_line + 1 > 200:
            _fail("source line range must be ordered and at most 200 lines")
        return {
            "path": _source_path(arguments["path"]),
            "start_line": start_line,
            "end_line": end_line,
        }
    if tool_name == "list_source":
        return {"subpath": _source_path(arguments["subpath"])}

    if tool_name == "submit_finding" and selected_policy.allow_harness:
        verdict = _string(arguments["verdict"], "verdict", max_length=32)
        if verdict not in VERDICTS:
            _fail(f"verdict must be one of: {', '.join(sorted(VERDICTS))}")
        result = {
            "verdict": verdict,
            "rationale": _string(arguments["rationale"], "rationale", max_length=8192),
        }
        if any(field in arguments for field in ("path", "param_name", "param_value")):
            for field in ("path", "param_name", "param_value"):
                if field not in arguments:
                    _fail(f"{field} is required when request evidence is supplied")
            path = _route(arguments["path"], selected_policy)
            param_name = _param_name(arguments["param_name"], path, selected_policy)
            result.update(
                {
                    "path": path,
                    "param_name": param_name,
                    "param_value": _param_value(arguments["param_value"]),
                }
            )
        return result

    path = _route(arguments["path"], selected_policy)
    param_name = _param_name(arguments["param_name"], path, selected_policy)
    param_value = _param_value(arguments["param_value"])
    if tool_name == "send_request":
        return {"path": path, "param_name": param_name, "param_value": param_value}

    verdict = _string(arguments["verdict"], "verdict", max_length=32)
    if verdict not in VERDICTS:
        _fail(f"verdict must be one of: {', '.join(sorted(VERDICTS))}")
    return {
        "verdict": verdict,
        "path": path,
        "param_name": param_name,
        "param_value": param_value,
        "rationale": _string(arguments["rationale"], "rationale", max_length=8192),
    }


validate_tool_arguments = validate_tool_call
validate_tool_input = validate_tool_call
validate_tool = validate_tool_call
