"""Append-only audit records for commands dispatched to Celesto guests."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXECUTION_TARGET = "celesto_sandbox"
SANDBOX_NAME = re.compile(r"^sbx-[a-z0-9]{8,}$")
DECISIONS = frozenset({"allow", "block"})


class AuditLogError(ValueError):
    """Raised when an audit record is not safe or complete."""


class CommandAuditLog:
    """Write the exact fields required by the submission contract.

    Commands are recorded before execution. A blocked command therefore also
    leaves evidence, and every record is explicitly tied to a Celesto guest.
    The command string is the fixed/encoded guest-helper command, never the
    raw model payload.
    """

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        sandbox_name: str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self.sandbox_name = sandbox_name
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        sandbox_name: str | None = None,
        command: str,
        decision: str,
        ts: str | None = None,
    ) -> dict[str, str]:
        name = sandbox_name or self.sandbox_name
        if not isinstance(name, str) or not SANDBOX_NAME.fullmatch(name):
            raise AuditLogError("sandbox_name must match sbx- plus 8 lowercase letters/digits")
        if not isinstance(command, str) or not command.strip():
            raise AuditLogError("command must be a non-empty string")
        if decision not in DECISIONS:
            raise AuditLogError("decision must be allow or block")
        timestamp = ts or self._timestamp()
        if not isinstance(timestamp, str) or not timestamp:
            raise AuditLogError("ts must be a non-empty ISO-8601 string")
        record = {
            "ts": timestamp,
            "sandbox_name": name,
            "command": command,
            "decision": decision,
            "execution_target": EXECUTION_TARGET,
        }
        self._append(record)
        return record

    def allow(self, command: str, *, sandbox_name: str | None = None) -> dict[str, str]:
        return self.append(sandbox_name=sandbox_name, command=command, decision="allow")

    def block(self, command: str, *, sandbox_name: str | None = None) -> dict[str, str]:
        return self.append(sandbox_name=sandbox_name, command=command, decision="block")

    # Compatibility aliases for callers that describe this as a command event.
    append_command = allow
    log_command = allow
    record_command = allow

    def append_event(self, event: Mapping[str, Any]) -> dict[str, str]:
        if not isinstance(event, Mapping):
            raise AuditLogError("event must be an object")
        command = event.get("command", event.get("event", "event"))
        decision = event.get("decision", "allow")
        return self.append(
            sandbox_name=event.get("sandbox_name"),
            command=str(command),
            decision=str(decision),
            ts=event.get("ts"),
        )

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AuditLogError(f"invalid JSON at line {line_number}") from exc
                if not isinstance(value, dict):
                    raise AuditLogError(f"line {line_number} is not an object")
                if value.get("execution_target") != EXECUTION_TARGET:
                    raise AuditLogError(f"line {line_number} has an invalid execution target")
                records.append(value)
        return records

    def _timestamp(self) -> str:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    def _append(self, record: Mapping[str, Any]) -> None:
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(encoded + "\n")
            stream.flush()
            os.fsync(stream.fileno())


AuditLogger = CommandAuditLog
