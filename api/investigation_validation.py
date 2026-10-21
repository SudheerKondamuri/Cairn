"""Validation for user-submitted investigation jobs."""

from __future__ import annotations

import json
from typing import Any

from core.investigation import InvestigationSpec, InvestigationSpecError


def validate_investigation_form(report: object, manifest: object) -> InvestigationSpec:
    if not isinstance(report, str) or not report.strip():
        raise InvestigationSpecError("report is required")
    if not isinstance(manifest, str) or not manifest.strip():
        raise InvestigationSpecError("manifest is required")
    try:
        payload = json.loads(manifest)
    except json.JSONDecodeError as exc:
        raise InvestigationSpecError("manifest must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise InvestigationSpecError("manifest must be a JSON object")
    return InvestigationSpec.from_mapping({**payload, "report": report})
