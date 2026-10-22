#!/usr/bin/env python3
"""Run the required 20-case fresh-sandbox evaluation and write its metrics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from runner import ROOT, load_json
from run_one import run_case

from core.metrics import build_reliability_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="run only the first N cases for a smoke test")
    args = parser.parse_args(argv)
    cases = load_json(ROOT / "cases/evaluation_matrix.json")
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be >= 1")
        cases = cases[: args.limit]
    outcomes: list[dict[str, object]] = []
    for index, case in enumerate(cases, 1):
        print(f"[{index}/{len(cases)}] {case['case_id']}", flush=True)
        outcomes.append(run_case(case))

    runs = [
        {
            "sandbox_name": item["sandbox_name"],
            "fresh": True,
            "success": bool(item.get("success") and item.get("cleaned_up")),
            "wall_clock_s": item["wall_clock_s"],
            "boot_to_ready_s": item["boot_to_ready_s"],
            "cost_usd": item["cost_usd"],
        }
        for item in outcomes
    ]
    if len(runs) < 20:
        print("Evaluation smoke run complete; not writing a submission reliability report until 20 runs exist.")
        return 0
    report = build_reliability_report(runs)
    report_path = ROOT / "reports/reliability.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lifecycle_path = ROOT / "reports/lifecycle.json"
    lifecycle = load_json(lifecycle_path)
    lifecycle["sandbox_names"] = list(
        dict.fromkeys([*lifecycle.get("sandbox_names", []), *(run["sandbox_name"] for run in runs)])
    )
    lifecycle_path.write_text(json.dumps(lifecycle, indent=2) + "\n", encoding="utf-8")

    tp = sum(item.get("truth") == "vulnerable" and item.get("verdict") == "verified" for item in outcomes)
    fp = sum(item.get("truth") == "patched" and item.get("verdict") == "verified" for item in outcomes)
    fn = sum(item.get("truth") == "vulnerable" and item.get("verdict") != "verified" for item in outcomes)
    tn = sum(item.get("truth") == "patched" and item.get("verdict") != "verified" for item in outcomes)
    failed_rows = [item for item in outcomes if not item.get("success") or not item.get("cleaned_up")]
    if failed_rows:
        failure_details = "; ".join(
            f"{item['case_id']}: {str(item.get('error', 'cleanup failure'))[:240]}"
            for item in failed_rows
        )
    else:
        failure_details = "none"
    postmortem = ROOT / "reports/postmortem.md"
    postmortem.write_text(
        "# Cairn evaluation post-mortem\n\n"
        "## Measured result\n\n"
        f"The required matrix ran on {report['run_count']} fresh, uniquely named Celesto "
        f"Cloud guests. Infrastructure success was {sum(1 for row in runs if row['success'])}/"
        f"{report['run_count']}, or **{report['success_rate']:.3f}**. The median wall-clock "
        f"time was {report['median_wall_clock_s']:.3f} seconds, p90 was "
        f"{report['p90_wall_clock_s']:.3f} seconds, median boot-to-ready time was "
        f"{report['median_boot_to_ready_s']:.3f} seconds, and the recorded runtime total "
        f"was ${report['total_cost_usd']:.6f}. These values are recomputed from "
        "`reports/reliability.json`; failed rows were not removed.\n\n"
        "## Verdict quality\n\n"
        f"The confusion matrix was **TP={tp}, FP={fp}, FN={fn}, TN={tn}**. A `verified` "
        "result still requires the independent control-plane marker recheck; an unknown "
        "infrastructure outcome is not silently converted into `not_reproduced`.\n\n"
        "## Failure analysis\n\n"
        f"Failed or uncleared rows: {failure_details}. Review each "
        "`reports/live/*.json` row for the detailed failure reason, recovery path, and "
        "evidence trace. The bounded controller fallback may finish a model timeout or "
        "no-tool response only after the controller has inspected the supplied source; "
        "it does not bypass the independent recheck.\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
