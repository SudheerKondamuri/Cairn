"""Validators for the exact files the hackathon grader reads."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .audit import DECISIONS, EXECUTION_TARGET
from .metrics import ReportValidationError, SANDBOX_NAME, validate_reliability_report


CAPABILITY_IDS = {
    "persistence",
    "snapshots",
    "celestofs",
    "browser",
    "published_ports",
    "network_policy",
    "safety_hooks",
    "host_mounts",
    "coding_agent_preset",
    "agentor_durable",
}


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportValidationError(f"cannot read {path}: {exc}") from exc


def _iso(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ReportValidationError(f"{field} must be a non-empty ISO-8601 string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReportValidationError(f"{field} is not ISO-8601") from exc


def validate_problem(value: dict[str, Any]) -> None:
    for field, minimum in (("who", 40), ("agent_work", 40), ("proof_output", 20)):
        if not isinstance(value.get(field), str) or len(value[field]) < minimum:
            raise ReportValidationError(f"problem.{field} is too short")
    if value.get("idea_source") not in {"idea_bank", "original"}:
        raise ReportValidationError("problem.idea_source is invalid")


def validate_capabilities(value: dict[str, Any], root: Path) -> None:
    capabilities = value.get("capabilities")
    if not isinstance(capabilities, list) or len(capabilities) < 2:
        raise ReportValidationError("at least two capabilities are required")
    ids: set[str] = set()
    for item in capabilities:
        if not isinstance(item, dict):
            raise ReportValidationError("capability entries must be objects")
        capability_id = item.get("id")
        if capability_id not in CAPABILITY_IDS or capability_id in ids:
            raise ReportValidationError("capability id is invalid or duplicated")
        ids.add(capability_id)
        if not isinstance(item.get("why"), str) or len(item["why"]) < 80:
            raise ReportValidationError(f"capability {capability_id} needs a longer why")
        evidence = item.get("evidence_path")
        if not isinstance(evidence, str) or not evidence or not (root / evidence).is_file():
            raise ReportValidationError(f"capability {capability_id} evidence_path does not exist")


def validate_commands(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        raise ReportValidationError(f"missing command log: {path}")
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReportValidationError(f"invalid command JSON at line {line_number}") from exc
        required = {"ts", "sandbox_name", "command", "decision", "execution_target"}
        if not isinstance(value, dict) or not required.issubset(value):
            raise ReportValidationError(f"command line {line_number} is missing fields")
        _iso(value["ts"], f"commands[{line_number}].ts")
        if not isinstance(value["sandbox_name"], str) or not SANDBOX_NAME.fullmatch(value["sandbox_name"]):
            raise ReportValidationError(f"command line {line_number} has bad sandbox_name")
        if not isinstance(value["command"], str) or not value["command"]:
            raise ReportValidationError(f"command line {line_number} has empty command")
        if value["decision"] not in DECISIONS:
            raise ReportValidationError(f"command line {line_number} has bad decision")
        if value["execution_target"] != EXECUTION_TARGET:
            raise ReportValidationError(f"command line {line_number} has wrong execution target")
        records.append(value)
    if not records:
        raise ReportValidationError("command log must contain at least one record")
    return records


def validate_lifecycle(value: dict[str, Any]) -> None:
    for field in ("cleanup_on_success", "cleanup_on_failure", "cleanup_on_interrupt"):
        if value.get(field) is not True:
            raise ReportValidationError(f"lifecycle.{field} must be true")
    names = value.get("sandbox_names")
    if not isinstance(names, list) or not names:
        raise ReportValidationError("lifecycle.sandbox_names must be non-empty")
    if (
        len(set(names)) != len(names)
        or any(not isinstance(name, str) or not SANDBOX_NAME.fullmatch(name) for name in names)
    ):
        raise ReportValidationError("lifecycle sandbox names are invalid or duplicated")


def validate_containment(value: dict[str, Any], root: Path) -> None:
    if value.get("attack") not in {"prompt_injection_exfil", "destructive_command", "suspicious_package"}:
        raise ReportValidationError("containment attack is invalid")
    if value.get("blocked") is not True or value.get("host_untouched") is not True:
        raise ReportValidationError("containment must prove blocked and host_untouched")
    paths = value.get("evidence_paths")
    if not isinstance(paths, list) or not paths or any(not (root / path).is_file() for path in paths):
        raise ReportValidationError("containment evidence paths are missing")


def validate_failure_policy(value: dict[str, Any], root: Path) -> None:
    if value.get("failed_step") != 7 or value.get("total_steps") != 10:
        raise ReportValidationError("failure policy must describe step 7 of 10")
    if value.get("policy") not in {"resume", "rollback", "fresh"}:
        raise ReportValidationError("failure policy is invalid")
    if not isinstance(value.get("rationale"), str) or len(value["rationale"]) < 200:
        raise ReportValidationError("failure rationale is too short")
    trace_path = value.get("trace_path")
    if trace_path != "reports/failure_trace.jsonl" or not (root / trace_path).is_file():
        raise ReportValidationError("failure trace path is missing")
    matched = False
    for line in (root / trace_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReportValidationError("failure trace contains invalid JSON") from exc
        if item.get("event") == "policy_applied" and item.get("policy") == value["policy"]:
            matched = True
    if not matched:
        raise ReportValidationError("failure trace has no matching policy_applied event")


def validate_concurrency(value: dict[str, Any]) -> None:
    jobs = value.get("jobs")
    if not isinstance(jobs, list) or len(jobs) < 5:
        raise ReportValidationError("at least five concurrency jobs are required")
    names = [job.get("sandbox_name") for job in jobs if isinstance(job, dict)]
    if len(names) != len(jobs) or len(set(names)) != len(names):
        raise ReportValidationError("concurrency sandbox names must be unique")
    for index, job in enumerate(jobs):
        if not SANDBOX_NAME.fullmatch(str(job.get("sandbox_name"))):
            raise ReportValidationError(f"concurrency job {index} has bad sandbox_name")
        _iso(job.get("started_at"), f"concurrency.jobs[{index}].started_at")
    if not isinstance(value.get("breakage_notes"), str) or len(value["breakage_notes"]) < 40:
        raise ReportValidationError("concurrency breakage_notes is too short")


def validate_submission_reports(root: str | Path, *, require_live: bool = False) -> None:
    root = Path(root)
    validate_problem(_json(root / "reports/problem.json"))
    validate_capabilities(_json(root / "reports/capabilities.json"), root)
    commands = validate_commands(root / "logs/commands.jsonl")
    lifecycle = _json(root / "reports/lifecycle.json")
    validate_lifecycle(lifecycle)
    names = set(lifecycle["sandbox_names"])
    reliability = _json(root / "reports/reliability.json")
    validate_reliability_report(reliability, require_twenty=require_live)
    reliability_names = {
        row["sandbox_name"] for row in reliability.get("runs", []) if isinstance(row, dict)
    }
    if not names.intersection({record["sandbox_name"] for record in commands} | reliability_names):
        raise ReportValidationError("lifecycle names do not occur in command log or reliability")
    if require_live and not (root / "reports/postmortem.md").is_file():
        raise ReportValidationError("postmortem is missing")
    if require_live and len((root / "reports/postmortem.md").read_text(encoding="utf-8")) < 200:
        raise ReportValidationError("postmortem is too short")
    validate_containment(_json(root / "reports/containment.json"), root)
    validate_failure_policy(_json(root / "reports/failure_policy.json"), root)
    validate_concurrency(_json(root / "reports/concurrency.json"))
