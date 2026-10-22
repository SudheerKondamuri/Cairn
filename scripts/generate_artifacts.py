#!/usr/bin/env python3
"""Generate honest initial Cairn evidence/report JSON artifacts offline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_reporting():
    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from core.reporting import make_initial_evidence, make_initial_report, validate_artifact

    return make_initial_evidence, make_initial_report, validate_artifact


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("scripts/artifacts"))
    args = parser.parse_args(argv)
    make_initial_evidence, make_initial_report, validate_artifact = _load_reporting()

    evidence = make_initial_evidence()
    report = make_initial_report()
    validate_artifact(evidence)
    validate_artifact(report)
    evidence_path = args.output_dir / "initial_evidence.json"
    report_path = args.output_dir / "initial_report.json"
    _write_json(evidence_path, evidence)
    _write_json(report_path, report)
    print(f"WROTE {evidence_path} live_results=false")
    print(f"WROTE {report_path} live_results=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
