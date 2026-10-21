"""Detailed, human-readable reports for one Cairn investigation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def build_investigation_report(
    *,
    investigation_id: str,
    spec: Mapping[str, Any],
    finding: Mapping[str, Any] | None,
    lifecycle: Mapping[str, Any] | None = None,
    dependencies: Mapping[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build a report whose status is evidence-backed rather than model-only."""

    finding = dict(finding or {})
    proposal = dict(finding.get("proposal") or {})
    verdict = str(finding.get("verdict") or "inconclusive")
    attempts = list(finding.get("attempts") or [])
    independent = finding.get("independent_recheck")
    source_hash = finding.get("source_hash")
    summary, why, remediation, next_action = _explanation(
        verdict=verdict,
        finding=finding,
        error=error,
    )

    return {
        "schema_version": 1,
        "investigation_id": investigation_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "summary": summary,
        "claim": {
            "report": spec.get("report", ""),
            "subject_type": spec.get("subject_type"),
            "runtime": spec.get("runtime"),
        },
        "subject": {
            "source_hash": source_hash,
            "working_directory": spec.get("working_directory", "."),
            "port": spec.get("port"),
        },
        "evidence": {
            "source_hash": source_hash,
            "request": {
                key: proposal.get(key)
                for key in ("path", "param_name", "param_value")
                if key in proposal
            },
            "agent_rationale": proposal.get("rationale"),
            "attempts": attempts,
            "independent_recheck": independent,
        },
        "explanation": {
            "why": why,
            "remediation": remediation,
            "next_action": next_action,
        },
        "dependencies": dict(dependencies or {}),
        "lifecycle": dict(lifecycle or {}),
        "error": error,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render the stable report fields into a ticket-friendly Markdown report."""

    evidence = report.get("evidence") or {}
    explanation = report.get("explanation") or {}
    request = evidence.get("request") or {}
    lines = [
        f"# Cairn investigation `{report.get('investigation_id', 'unknown')}`",
        "",
        f"**Verdict:** `{report.get('verdict', 'inconclusive')}`",
        "",
        str(report.get("summary", "")),
        "",
        "## Claim",
        "",
        str((report.get("claim") or {}).get("report", "")),
        "",
        "## Evidence",
        "",
        f"- Source hash: `{evidence.get('source_hash') or 'unavailable'}`",
        f"- Route: `{request.get('path', 'not recorded')}`",
        f"- Parameter: `{request.get('param_name', 'not recorded')}`",
        f"- Attempts: `{len(evidence.get('attempts') or [])}`",
        f"- Independent recheck: `{_recheck_status(evidence.get('independent_recheck'))}`",
        f"- Agent evidence rationale: {evidence.get('agent_rationale') or 'not provided'}",
        "",
        "## Why",
        "",
    ]
    lines.extend(f"- {item}" for item in explanation.get("why", []))
    lines.extend(["", "## Remediation", ""])
    lines.extend(f"- {item}" for item in explanation.get("remediation", []))
    lines.extend(["", "## Next action", "", str(explanation.get("next_action", "")), ""])
    dependencies = report.get("dependencies") or {}
    lines.extend(
        [
            "## Dependencies",
            "",
            f"- Mode: `{dependencies.get('mode', 'not recorded')}`",
            f"- Installation events: `{len(dependencies.get('events') or [])}`",
            "",
            "## Cleanup",
            "",
            f"- Sandbox deleted: `{(report.get('lifecycle') or {}).get('sandbox_deleted', False)}`",
            "",
        ]
    )
    if report.get("error"):
        lines.extend(["## Error", "", f"`{report['error']}`", ""])
    return "\n".join(lines)


def _explanation(
    *, verdict: str, finding: Mapping[str, Any], error: str | None
) -> tuple[str, list[str], list[str], str]:
    independent = finding.get("independent_recheck") or {}
    attempts = finding.get("attempts") or []
    if verdict == "verified":
        return (
            "The reported behavior was reproduced and confirmed by an independent control-plane recheck.",
            [
                "At least one investigation request produced marker evidence.",
                "The control plane constructed a fresh independent request and observed its marker.",
            ],
            [
                "Review the source location identified in the evidence.",
                "Replace shell composition with an argument vector or a safe library API.",
                "Validate attacker-controlled input before invoking operating-system functionality.",
            ],
            "Open a remediation ticket with the source hash and reproduction recipe.",
        )
    if verdict == "not_reproduced":
        status = attempts[-1].get("status") if attempts and isinstance(attempts[-1], Mapping) else None
        return (
            "The supplied security claim was not reproduced under the supplied runtime and test conditions.",
            [
                f"The investigation completed without marker evidence{f' (last HTTP status: {status})' if status else ''}.",
                "This result does not prove that every code path or configuration is safe.",
            ],
            ["Review the tested path, parameter, source revision, and dependency versions."],
            "Confirm the application version and expand the harness if the report covers another path.",
        )
    return (
        "The investigation did not produce enough reliable evidence for a vulnerability verdict.",
        [error or "The application, dependency setup, request, or evidence check did not complete."],
        [],
        "Resolve the recorded failure and retry in a fresh sandbox.",
    )


def _recheck_status(value: object) -> str:
    if not isinstance(value, Mapping):
        return "not requested"
    if value.get("marker_detected") is True and value.get("request_constructed_by") == "control_plane":
        return "confirmed"
    return "not confirmed"
