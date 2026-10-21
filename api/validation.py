"""Validation rules for the hackathon's run-ledger API."""

from __future__ import annotations

import re
from collections.abc import Mapping


SANDBOX_NAME_PATTERN = re.compile(r"^sbx-[a-z0-9]{8,}$")
VALID_STATES = frozenset({"created", "ready", "running", "succeeded", "failed", "deleted"})
VALID_EXECUTION_TARGET = "celesto_sandbox"
REQUIRED_RUN_FIELDS = frozenset(
    {"run_id", "sandbox_name", "problem_id", "state", "execution_target"}
)


class ValidationError(ValueError):
    """A client-supplied run payload failed the API contract."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(message)

    def as_dict(self) -> dict[str, str]:
        return {"field": self.field, "message": self.message}


def validate_run_payload(payload: object) -> dict[str, str]:
    """Validate the exact POST /api/runs contract.

    The API accepts metadata only.  It never treats ``execution_target`` as a
    request to execute on the host; the only accepted target is the literal
    ``celesto_sandbox``.
    """

    if not isinstance(payload, Mapping):
        raise ValidationError("body", "JSON body must be an object")

    missing = REQUIRED_RUN_FIELDS - payload.keys()
    if missing:
        field = sorted(missing)[0]
        raise ValidationError(field, "field is required")

    unknown = set(payload.keys()) - REQUIRED_RUN_FIELDS
    if unknown:
        field = sorted(unknown, key=str)[0]
        raise ValidationError(str(field), "unknown field")

    values: dict[str, str] = {}
    for field in ("run_id", "problem_id"):
        value = payload[field]
        if type(value) is not str or not value.strip():
            raise ValidationError(field, "must be a non-empty string")
        if len(value) > 512:
            raise ValidationError(field, "must be at most 512 characters")
        values[field] = value

    sandbox_name = payload["sandbox_name"]
    if type(sandbox_name) is not str or not SANDBOX_NAME_PATTERN.fullmatch(sandbox_name):
        raise ValidationError(
            "sandbox_name",
            "must match sbx- followed by at least 8 lowercase letters or digits",
        )
    values["sandbox_name"] = sandbox_name

    state = payload["state"]
    if type(state) is not str or state not in VALID_STATES:
        allowed = ", ".join(sorted(VALID_STATES))
        raise ValidationError("state", f"must be one of: {allowed}")
    values["state"] = state

    execution_target = payload["execution_target"]
    if execution_target != VALID_EXECUTION_TARGET:
        raise ValidationError("execution_target", f"must be {VALID_EXECUTION_TARGET}")
    values["execution_target"] = execution_target
    return values
