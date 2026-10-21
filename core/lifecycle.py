"""Sandbox lifecycle and named step-7 recovery policy."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from .sandbox import SandboxAdapter


class LifecycleError(RuntimeError):
    """Raised for an invalid lifecycle transition."""


class Step7Failure(RuntimeError):
    """A deliberately classified failure at the first request dispatch."""


class LifecycleState(str, Enum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    MID_TASK_FAILURE = "mid_task_failure"
    RESUMED = "resumed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DELETED = "deleted"


T = TypeVar("T")


class Step7Lifecycle:
    """Keep a persistent guest through a step-7 failure, then always delete it."""

    def __init__(
        self,
        adapter: SandboxAdapter,
        state_path: str | os.PathLike[str],
        *,
        trace_path: str | os.PathLike[str] | None = None,
        run_id: str = "step7-run",
    ) -> None:
        self.adapter = adapter
        self.state_path = Path(state_path)
        self.trace_path = Path(trace_path) if trace_path else None
        self.run_id = run_id
        self.state = LifecycleState.CREATED
        self.checkpoint_data: dict[str, Any] = {}
        self.last_error: str | None = None
        self._load()

    def checkpoint(self, value: Mapping[str, Any]) -> None:
        if not isinstance(value, Mapping):
            raise TypeError("checkpoint must be an object")
        json.dumps(value)
        self.checkpoint_data = dict(value)
        self._persist()

    def mark_ready(self) -> None:
        self._transition({LifecycleState.CREATED, LifecycleState.RESUMED}, LifecycleState.READY)

    def mark_running(self) -> None:
        self._transition({LifecycleState.READY, LifecycleState.RESUMED}, LifecycleState.RUNNING)

    def run_step7(
        self,
        operation: Callable[["Step7Lifecycle"], T],
        *,
        recovery_operation: Callable[["Step7Lifecycle"], T] | None = None,
        policy: str = "resume",
    ) -> T:
        if policy not in {"resume", "rollback", "fresh"}:
            raise LifecycleError("policy must be resume, rollback, or fresh")
        self.adapter.start()
        self.state = LifecycleState.READY
        self._persist()
        result: T
        try:
            self.mark_running()
            try:
                result = operation(self)
            except Step7Failure as exc:
                self.last_error = str(exc)
                self.state = LifecycleState.MID_TASK_FAILURE
                self._persist()
                self._trace({"event": "step_failed", "step": 7, "error": str(exc)})
                self._apply_policy(policy)
                if recovery_operation is None:
                    raise
                self.state = LifecycleState.RESUMED
                self._persist()
                result = recovery_operation(self)
            self.state = LifecycleState.SUCCEEDED
            self._persist()
            return result
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.state = LifecycleState.FAILED
            self._persist()
            raise
        finally:
            try:
                self.adapter.cleanup()
            finally:
                self.state = LifecycleState.DELETED
                self._persist()

    def _apply_policy(self, policy: str) -> None:
        if policy == "resume":
            self.adapter.stop()
            self._trace({"event": "policy_applied", "policy": policy, "step": 7})
            self.adapter.start()
        elif policy == "fresh":
            self._trace({"event": "policy_applied", "policy": policy, "step": 7})
            self.adapter.cleanup()
            self.adapter.start()
        else:
            # Snapshot/rollback is deliberately not used by the MVP. Keep the
            # named branch explicit so a future local-runtime implementation
            # cannot silently pretend rollback happened.
            raise LifecycleError("rollback requires a configured snapshot adapter")
        self._persist()

    def _transition(self, allowed: set[LifecycleState], target: LifecycleState) -> None:
        if self.state not in allowed:
            raise LifecycleError(f"cannot transition from {self.state.value} to {target.value}")
        self.state = target
        self._persist()

    def _trace(self, event: Mapping[str, Any]) -> None:
        if not self.trace_path:
            return
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            **dict(event),
        }
        with self.trace_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        with self.state_path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise LifecycleError("invalid lifecycle state file")
        self.state = LifecycleState(data["state"])
        self.checkpoint_data = dict(data.get("checkpoint", {}))
        self.last_error = data.get("last_error")

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(
            {
                "schema_version": 1,
                "state": self.state.value,
                "checkpoint": self.checkpoint_data,
                "last_error": self.last_error,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            sort_keys=True,
            indent=2,
        ) + "\n"
        fd, temporary = tempfile.mkstemp(dir=self.state_path.parent, prefix=".cairn-state-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.state_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


LifecycleManager = Step7Lifecycle
RecoveryStateMachine = Step7Lifecycle
Step7State = LifecycleState
