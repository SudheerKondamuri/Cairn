"""The bounded tool surface exposed to the Cairn reasoning loop."""

from __future__ import annotations

import hashlib
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .audit import CommandAuditLog
from .sandbox import SandboxAdapter, SandboxAdapterError
from .validation import DEFAULT_TOOL_POLICY, ToolPolicy, ToolValidationError, validate_tool_call


class ToolExecutionError(RuntimeError):
    """Raised when a valid tool cannot complete inside the guest."""


@dataclass
class InvestigationBudget:
    max_tool_calls: int = 8
    max_requests: int = 4
    deadline_s: float = 150.0
    started_at: float = field(default_factory=time.monotonic)
    tool_calls: int = 0
    request_calls: int = 0

    def consume(self, tool_name: str) -> None:
        if time.monotonic() - self.started_at > self.deadline_s:
            raise ToolExecutionError("investigation wall-clock budget exhausted")
        if self.tool_calls >= self.max_tool_calls:
            raise ToolExecutionError("total tool-call budget exhausted")
        if tool_name == "send_request" and self.request_calls >= self.max_requests:
            raise ToolExecutionError("send_request budget exhausted")
        self.tool_calls += 1
        if tool_name == "send_request":
            self.request_calls += 1


class CairnToolDispatcher:
    """Validate, audit, and execute only the four supported tool calls."""

    def __init__(
        self,
        adapter: SandboxAdapter,
        *,
        audit: CommandAuditLog | None = None,
        budget: InvestigationBudget | None = None,
        policy: ToolPolicy | None = None,
    ) -> None:
        self.adapter = adapter
        self.audit = audit
        self.budget = budget or InvestigationBudget()
        self.policy = policy or DEFAULT_TOOL_POLICY
        self.attempts: list[dict[str, Any]] = []
        self.source_hashes: list[str] = []
        self.dependency_events: list[dict[str, Any]] = []
        self.dependency_failure = False
        self.final_finding: dict[str, Any] | None = None

    def dispatch(self, tool_name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        try:
            validated = validate_tool_call(tool_name, arguments, policy=self.policy)
            self.budget.consume(tool_name)
        except ToolValidationError:
            self._audit_block(tool_name)
            raise
        except ToolExecutionError:
            self._audit_block(tool_name)
            raise

        self._audit_allow(f"tool:{tool_name}")
        if tool_name == "inspect_source":
            return self.inspect_source(**validated)
        if tool_name == "list_source":
            return self.list_source(**validated)
        if tool_name == "send_request":
            return self.send_request(**validated)
        if tool_name == "install_dependencies":
            return self.install_dependencies()
        if tool_name == "run_harness":
            return self.run_harness()
        return self.submit_finding(**validated)

    def inspect_source(self, *, path: str, start_line: int, end_line: int) -> dict[str, Any]:
        try:
            text = self.adapter.inspect_source(path, start_line, end_line)
        except (OSError, KeyError, SandboxAdapterError) as exc:
            raise ToolExecutionError(f"source inspection failed: {exc}") from exc
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        marker = "# source_sha256="
        for line in reversed(text.splitlines()):
            if line.startswith(marker) and len(line) == len(marker) + 64:
                digest = line[len(marker) :]
                break
        self.source_hashes.append(digest)
        return {
            "path": path,
            "start_line": start_line,
            "end_line": end_line,
            "text": text,
            "source_hash": digest,
        }

    def list_source(self, *, subpath: str) -> dict[str, Any]:
        try:
            entries = self.adapter.list_source(subpath)
        except (OSError, KeyError, SandboxAdapterError) as exc:
            raise ToolExecutionError(f"source listing failed: {exc}") from exc
        return {"subpath": subpath, "entries": entries[:200]}

    def send_request(self, *, path: str, param_name: str, param_value: str) -> dict[str, Any]:
        marker = f"cairn-{secrets.token_hex(8)}"
        try:
            started = time.monotonic()
            result = self.adapter.send_request(path, param_name, param_value, marker)
            elapsed_ms = result.elapsed_ms
            if elapsed_ms is None:
                elapsed_ms = round((time.monotonic() - started) * 1000, 3)
            # The response helper is untrusted guest output. The control plane
            # is the only marker oracle and must query the marker directory
            # directly after every request.
            marker_detected = self.adapter.marker_any_present()
        except (OSError, SandboxAdapterError) as exc:
            self.attempts.append(
                {
                    "path": path,
                    "param_name": param_name,
                    "param_value": param_value,
                    "marker_detected": False,
                    "outcome": "unknown",
                    "error": str(exc),
                }
            )
            raise ToolExecutionError(f"request outcome unknown: {exc}") from exc

        observation = {
            "path": path,
            "param_name": param_name,
            "param_value": param_value,
            "status": result.status_code,
            "body": (result.body or result.stdout)[:500],
            "elapsed_ms": elapsed_ms,
            "marker_detected": marker_detected,
            "outcome": "complete" if result.ok else "unknown",
        }
        self.attempts.append(observation)
        return observation

    def install_dependencies(self) -> dict[str, Any]:
        try:
            result = self.adapter.install_dependencies()
        except (OSError, SandboxAdapterError) as exc:
            self.dependency_failure = True
            raise ToolExecutionError(f"dependency installation failed: {exc}") from exc
        if (
            result.get("error")
            or result.get("exit_code") not in (None, 0)
            or result.get("supported") is False
        ):
            self.dependency_failure = True
        self.dependency_events.append(dict(result))
        return dict(result)

    def run_harness(self) -> dict[str, Any]:
        marker = f"cairn-harness-{secrets.token_hex(8)}"
        try:
            self.adapter.clear_markers()
            result = self.adapter.run_harness(marker)
            marker_detected = self.adapter.marker_present(marker)
        except (OSError, SandboxAdapterError) as exc:
            observation = {
                "kind": "harness",
                "marker_detected": False,
                "outcome": "unknown",
                "error": str(exc),
            }
            self.attempts.append(observation)
            raise ToolExecutionError(f"test harness outcome unknown: {exc}") from exc
        observation = {
            "kind": "harness",
            "ok": result.ok,
            "exit_code": result.exit_code,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "marker_detected": marker_detected,
            "outcome": "complete" if result.ok else "unknown",
        }
        self.attempts.append(observation)
        return observation

    def submit_finding(
        self,
        *,
        verdict: str,
        rationale: str,
        path: str | None = None,
        param_name: str | None = None,
        param_value: str | None = None,
    ) -> dict[str, Any]:
        proposal = {
            "verdict": verdict,
            "rationale": rationale,
        }
        if path is not None:
            proposal["path"] = path
        if param_name is not None:
            proposal["param_name"] = param_name
        if param_value is not None:
            proposal["param_value"] = param_value
        final_verdict = verdict
        recheck: dict[str, Any] | None = None
        if self.dependency_failure:
            final_verdict = "inconclusive"
            recheck = {
                "marker_detected": False,
                "outcome": "unknown",
                "error": "dependency installation did not complete successfully",
            }
        elif verdict == "verified" and self.policy.requires_marker_recheck:
            if not all(value is not None for value in (path, param_name, param_value)):
                recheck = {
                    "marker_detected": False,
                    "outcome": "unknown",
                    "error": "verified request evidence is incomplete",
                }
                final_verdict = "inconclusive"
            else:
                recheck = self._independent_recheck(path, param_name, param_value)
                if not recheck["marker_detected"]:
                    final_verdict = "inconclusive"
        elif verdict == "verified" and self.policy.allow_harness:
            recheck = self._independent_harness_recheck()
            if not recheck["marker_detected"]:
                final_verdict = "inconclusive"
        self.final_finding = {
            "proposal": proposal,
            "verdict": final_verdict,
            "independent_recheck": recheck,
            "attempts": list(self.attempts),
            "source_hash": self.source_hashes[-1] if self.source_hashes else None,
        }
        return self.final_finding

    def _independent_recheck(self, path: str, param_name: str, param_value: str) -> dict[str, Any]:
        token = f"cairn-independent-{secrets.token_hex(8)}"
        safe_prefix = self._safe_prefix(param_value, param_name)
        payload = f"{safe_prefix}; touch /tmp/cairn-markers/{token}; #"
        try:
            result = self.adapter.independent_request(path, param_name, payload, token)
            # Never accept a marker boolean supplied by the fixture or helper;
            # the independent recheck is decided by a fresh control-plane query.
            marker_detected = self.adapter.marker_present(token)
        except (OSError, SandboxAdapterError) as exc:
            return {"marker_detected": False, "outcome": "unknown", "error": str(exc)}
        return {
            "marker_detected": marker_detected,
            "outcome": "complete" if result.ok else "unknown",
            "status": result.status_code,
            "request_constructed_by": "control_plane",
            "fresh_token": token,
        }

    def _independent_harness_recheck(self) -> dict[str, Any]:
        token = f"cairn-independent-{secrets.token_hex(8)}"
        try:
            self.adapter.clear_markers()
            result = self.adapter.run_harness(token)
            marker_detected = self.adapter.marker_present(token)
        except (OSError, SandboxAdapterError) as exc:
            return {
                "marker_detected": False,
                "outcome": "unknown",
                "error": str(exc),
                "request_constructed_by": "control_plane",
            }
        return {
            "marker_detected": marker_detected,
            "outcome": "complete" if result.ok else "unknown",
            "exit_code": result.exit_code,
            "request_constructed_by": "control_plane",
            "fresh_token": token,
        }

    @staticmethod
    def _safe_prefix(value: str, param_name: str) -> str:
        for separator in (";", "|", "&", "\n", "\r"):
            value = value.split(separator, 1)[0]
        value = value.strip()
        return value or ("sample.txt" if param_name == "filename" else "127.0.0.1")

    def _audit_allow(self, command: str) -> None:
        if self.audit:
            self.audit.allow(command, sandbox_name=self.adapter.sandbox_name)

    def _audit_block(self, tool_name: str) -> None:
        if self.audit:
            self.audit.block(f"tool:{tool_name}", sandbox_name=self.adapter.sandbox_name)
