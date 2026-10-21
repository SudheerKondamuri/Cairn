"""Exact reliability arithmetic required by the Celesto challenge."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from typing import Any


class ReportValidationError(ValueError):
    """Raised when a report is malformed or its arithmetic is inconsistent."""


SANDBOX_NAME = re.compile(r"^sbx-[a-z0-9]{8,}$")


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReportValidationError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ReportValidationError(f"{field} must be finite and >= 0")
    return result


def _nearest_rank(values: list[float], rank: int) -> float:
    return values[rank - 1]


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    if count % 2:
        return ordered[count // 2]
    return (ordered[count // 2 - 1] + ordered[count // 2]) / 2


def validate_run_rows(runs: Iterable[Mapping[str, Any]], *, require_twenty: bool = False) -> list[dict[str, Any]]:
    rows = [dict(row) for row in runs]
    if require_twenty and len(rows) < 20:
        raise ReportValidationError("at least 20 fresh runs are required")
    seen: set[str] = set()
    required = {"sandbox_name", "fresh", "success", "wall_clock_s", "boot_to_ready_s", "cost_usd"}
    for index, row in enumerate(rows):
        if not required.issubset(row):
            raise ReportValidationError(f"run {index} is missing required fields")
        name = row["sandbox_name"]
        if not isinstance(name, str) or not SANDBOX_NAME.fullmatch(name) or name in seen:
            raise ReportValidationError(f"run {index} has an invalid or duplicate sandbox_name")
        seen.add(name)
        if row["fresh"] is not True:
            raise ReportValidationError(f"run {index} fresh must be true")
        if not isinstance(row["success"], bool):
            raise ReportValidationError(f"run {index} success must be boolean")
        for field in ("wall_clock_s", "boot_to_ready_s", "cost_usd"):
            row[field] = _number(row[field], f"runs[{index}].{field}")
    return rows


def build_reliability_report(
    runs: Iterable[Mapping[str, Any]], *, postmortem_path: str = "reports/postmortem.md"
) -> dict[str, Any]:
    rows = validate_run_rows(runs, require_twenty=False)
    if not rows:
        raise ReportValidationError("cannot calculate reliability from zero runs")
    wall = sorted(row["wall_clock_s"] for row in rows)
    boot = [row["boot_to_ready_s"] for row in rows]
    p90_rank = math.ceil(0.90 * len(wall))
    successes = sum(1 for row in rows if row["success"])
    return {
        "run_count": len(rows),
        "runs": sorted(rows, key=lambda row: row["wall_clock_s"]),
        "success_rate": successes / len(rows),
        "median_wall_clock_s": _median(wall),
        "p90_wall_clock_s": _nearest_rank(wall, p90_rank),
        "median_boot_to_ready_s": _median(boot),
        "total_cost_usd": sum(row["cost_usd"] for row in rows),
        "postmortem_path": postmortem_path,
    }


def validate_reliability_report(report: Mapping[str, Any], *, require_twenty: bool = False) -> dict[str, Any]:
    required = {
        "run_count",
        "runs",
        "success_rate",
        "median_wall_clock_s",
        "p90_wall_clock_s",
        "median_boot_to_ready_s",
        "total_cost_usd",
        "postmortem_path",
    }
    if not isinstance(report, Mapping) or not required.issubset(report):
        raise ReportValidationError("reliability report is missing required fields")
    runs = validate_run_rows(report["runs"], require_twenty=require_twenty)
    if report["run_count"] != len(runs):
        raise ReportValidationError("run_count does not equal runs length")
    if [row["wall_clock_s"] for row in runs] != sorted(row["wall_clock_s"] for row in runs):
        raise ReportValidationError("runs must be sorted by wall_clock_s ascending")
    expected = build_reliability_report(runs, postmortem_path=report["postmortem_path"])
    for field in (
        "success_rate",
        "median_wall_clock_s",
        "p90_wall_clock_s",
        "median_boot_to_ready_s",
        "total_cost_usd",
    ):
        actual = _number(report[field], field)
        if field == "success_rate" and actual > 1:
            raise ReportValidationError("success_rate must be between 0 and 1")
        if abs(actual - float(expected[field])) > (0.01 if field == "total_cost_usd" else 0.001):
            raise ReportValidationError(f"{field} does not match runs")
    if report["postmortem_path"] != "reports/postmortem.md":
        raise ReportValidationError("postmortem_path must be reports/postmortem.md")
    return dict(report)


def build_reliability_summary(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Compatibility summary used by unit tests for generic attempt records."""

    values = list(records)
    attempts = len(values)
    successes = sum(1 for row in values if row.get("status") == "success")
    failures = sum(1 for row in values if row.get("status") == "failure")
    errors = attempts - successes - failures
    recovery_attempted = sum(1 for row in values if row.get("recovery_attempted", row.get("recovered", False)))
    recovery_succeeded = sum(1 for row in values if row.get("recovered", False))
    return {
        "attempts": attempts,
        "successes": successes,
        "failures": failures,
        "errors": errors,
        "recoveries_attempted": recovery_attempted,
        "recoveries_succeeded": recovery_succeeded,
        "marker_confirmed": sum(1 for row in values if row.get("marker_confirmed", False)),
        "false_positives": sum(1 for row in values if row.get("false_positive", False)),
        "success_rate": None if not attempts else successes / attempts,
        "recovery_rate": None if not recovery_attempted else recovery_succeeded / recovery_attempted,
    }


def validate_reliability_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "attempts", "successes", "failures", "errors", "recoveries_attempted",
        "recoveries_succeeded", "marker_confirmed", "false_positives", "success_rate", "recovery_rate",
    }
    if set(summary) != required:
        raise ReportValidationError("generic reliability summary has wrong fields")
    if summary["successes"] + summary["failures"] + summary["errors"] != summary["attempts"]:
        raise ReportValidationError("generic status counts do not partition attempts")
    return dict(summary)


summarize_reliability = build_reliability_summary
