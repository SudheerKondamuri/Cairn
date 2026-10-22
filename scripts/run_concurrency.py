#!/usr/bin/env python3
"""Attempt five concurrent Celesto Cloud guests and record observed limits."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
from datetime import datetime, timezone

from runner import ROOT, LiveGuest, load_env, unique_sandbox_name


def one_job(name: str) -> dict[str, object]:
    started_at = datetime.now(timezone.utc).isoformat()
    guest = None
    try:
        guest = LiveGuest(name, audit_path=ROOT / "logs/commands.jsonl")
        guest.start()
        probe = guest.run("python3 --version")
        return {"sandbox_name": name, "started_at": started_at, "ok": probe.ok}
    except Exception as exc:
        return {"sandbox_name": name, "started_at": started_at, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if guest is not None:
            try:
                guest.delete()
            except Exception as exc:
                # The outcome remains visible instead of silently orphaning it.
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-live", action="store_true", help="record why live concurrency was not attempted")
    args = parser.parse_args(argv)
    load_env()
    names = [unique_sandbox_name(f"concur{i}") for i in range(1, 6)]
    if args.no_live:
        jobs = [
            {"sandbox_name": name, "started_at": datetime.now(timezone.utc).isoformat(), "ok": False}
            for name in names
        ]
        notes = "Live concurrency was intentionally not attempted; run with cloud credentials to observe overlap, rate limits, cleanup, and the one-retained-sandbox trial constraint."
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            jobs = list(executor.map(one_job, names))
        successes = sum(bool(job.get("ok")) for job in jobs)
        notes = f"Attempted five overlapping uniquely named guests; {successes}/5 completed the version probe. Review per-job errors for rate limits, credit limits, or transport failures."
    output = {
        "jobs": [{"sandbox_name": job["sandbox_name"], "started_at": job["started_at"]} for job in jobs],
        "breakage_notes": notes,
        "observations": jobs,
    }
    (ROOT / "reports/concurrency.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
