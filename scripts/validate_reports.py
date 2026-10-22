#!/usr/bin/env python3
"""Validate the exact report files consumed by the hackathon grader."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--live",
        action="store_true",
        help="require 20 measured fresh runs and completed containment evidence",
    )
    args = parser.parse_args(argv)
    sys.path.insert(0, str(args.root))
    from core.report_contract import validate_submission_reports
    from core.metrics import ReportValidationError

    try:
        validate_submission_reports(args.root, require_live=args.live)
    except (ReportValidationError, OSError, ValueError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"VALID: Cairn submission reports under {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
