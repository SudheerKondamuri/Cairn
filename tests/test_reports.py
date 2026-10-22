from __future__ import annotations

from pathlib import Path

from core.report_contract import validate_submission_reports


def test_submission_report_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    validate_submission_reports(root, require_live=True)
