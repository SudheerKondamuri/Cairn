"""Schemas and constructors for honest evidence/report artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from .metrics import ReportValidationError, validate_reliability_summary


ARTIFACT_SCHEMA_VERSION = 1
ARTIFACT_TYPES = frozenset({"evidence", "report"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_initial_evidence(*, generated_at: str | None = None) -> dict[str, Any]:
    """Create an explicit empty evidence artifact, never a fake live result."""

    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "evidence",
        "generated_at": generated_at or _utc_now(),
        "live_results": False,
        "source": "initial_offline_artifact",
        "items": [],
    }


def make_initial_report(*, generated_at: str | None = None) -> dict[str, Any]:
    """Create an explicit report shell without claiming Celesto execution."""

    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "report",
        "generated_at": generated_at or _utc_now(),
        "live_results": False,
        "source": "initial_offline_artifact",
        "results": [],
        "reliability": {
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "errors": 0,
            "recoveries_attempted": 0,
            "recoveries_succeeded": 0,
            "marker_confirmed": 0,
            "false_positives": 0,
            "success_rate": None,
            "recovery_rate": None,
        },
    }


def validate_artifact(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an evidence or report object and return a plain copy."""

    if not isinstance(artifact, Mapping):
        raise ReportValidationError("artifact must be an object")
    required = {"schema_version", "artifact_type", "generated_at", "live_results", "source"}
    missing = required - set(artifact)
    if missing:
        raise ReportValidationError(f"artifact missing fields: {sorted(missing)}")
    if artifact["schema_version"] != ARTIFACT_SCHEMA_VERSION:
        raise ReportValidationError("unsupported artifact schema_version")
    if artifact["artifact_type"] not in ARTIFACT_TYPES:
        raise ReportValidationError("artifact_type must be evidence or report")
    if not isinstance(artifact["generated_at"], str) or not artifact["generated_at"]:
        raise ReportValidationError("generated_at must be a non-empty string")
    if not isinstance(artifact["live_results"], bool):
        raise ReportValidationError("live_results must be boolean")
    if not isinstance(artifact["source"], str) or not artifact["source"]:
        raise ReportValidationError("source must be a non-empty string")

    result = dict(artifact)
    if artifact["artifact_type"] == "evidence":
        items = artifact.get("items")
        if not isinstance(items, list):
            raise ReportValidationError("evidence items must be an array")
        _validate_evidence_items(items)
        if "results" in artifact or "reliability" in artifact:
            raise ReportValidationError("evidence cannot contain report fields")
    else:
        results = artifact.get("results")
        if not isinstance(results, list):
            raise ReportValidationError("report results must be an array")
        _validate_result_items(results)
        if "items" in artifact:
            raise ReportValidationError("report cannot contain evidence items")
        reliability = artifact.get("reliability")
        result["reliability"] = validate_reliability_summary(reliability)
    return result


def _validate_evidence_items(items: Sequence[Any]) -> None:
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ReportValidationError(f"evidence item {index} must be an object")
        if "kind" not in item or "value" not in item:
            raise ReportValidationError(f"evidence item {index} needs kind and value")
        if not isinstance(item["kind"], str) or not item["kind"]:
            raise ReportValidationError(f"evidence item {index} kind must be a string")


def _validate_result_items(items: Sequence[Any]) -> None:
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ReportValidationError(f"report result {index} must be an object")
        if "status" not in item:
            raise ReportValidationError(f"report result {index} needs a status")
        if item["status"] not in {"success", "failure", "error"}:
            raise ReportValidationError(f"report result {index} has an invalid status")


def validate_artifacts(artifacts: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate one or more artifacts for script and CI callers."""

    if isinstance(artifacts, Mapping):
        return [validate_artifact(artifacts)]
    return [validate_artifact(artifact) for artifact in artifacts]


validate_report = validate_artifact
