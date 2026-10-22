#!/usr/bin/env python3
"""Run one investigation in one fresh Celesto Cloud guest."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from runner import (
    ROOT,
    LiveGuest,
    LiveRuntimeError,
    fixture_port,
    load_env,
    load_json,
    start_fixture,
    unique_sandbox_name,
    upload_guest_helpers,
    wait_for_fixture,
)

from core.agent import CairnAgent, OpenAICompatibleClient
from core.audit import CommandAuditLog
from core.tools import CairnToolDispatcher


def load_case(case_id: str) -> dict[str, object]:
    cases = load_json(ROOT / "cases/evaluation_matrix.json")
    for case in cases:
        if case["case_id"] == case_id:
            return case
    raise ValueError(f"unknown case_id: {case_id}")


def run_case(case: dict[str, object], *, sandbox_name: str | None = None) -> dict[str, object]:
    load_env()
    name = sandbox_name or unique_sandbox_name("cairn")
    fixture = ROOT / str(case["fixture"])
    audit_path = ROOT / "logs/commands.jsonl"
    started = time.monotonic()
    guest: LiveGuest | None = None
    outcome: dict[str, object] = {
        "case_id": case["case_id"],
        "sandbox_name": name,
        "fresh": True,
        "success": False,
        "truth": case["truth"],
        "variant": case["variant"],
        "wall_clock_s": 0.0,
        "boot_to_ready_s": 0.0,
        "cost_usd": 0.0,
    }
    try:
        guest = LiveGuest(name, audit_path=audit_path)
        guest.start()
        outcome["boot_to_ready_s"] = round(guest.boot_to_ready_s or 0.0, 3)
        upload_guest_helpers(guest)
        guest.upload_files(
            [
                (fixture, "/input/source/app.py", False),
                (ROOT / "fixtures/data/sample.txt", "/srv/uploads/sample.txt", False),
                (fixture, "/opt/cairn/fixture.py", False),
            ]
        )
        start_fixture(guest, fixture)
        wait_for_fixture(guest, fixture_port(fixture))

        adapter = guest.adapter(port=fixture_port(fixture))
        dispatcher = CairnToolDispatcher(
            adapter,
            audit=CommandAuditLog(audit_path, sandbox_name=name),
        )
        source_context = dispatcher.inspect_source(path="app.py", start_line=1, end_line=200)
        llm_key = os.getenv("LLM_API_KEY", "")
        client = OpenAICompatibleClient(
            base_url=os.getenv("LLM_BASE_URL", ""),
            api_key=llm_key,
            model=os.getenv("LLM_MODEL", ""),
            timeout_s=float(os.getenv("LLM_TIMEOUT_S", "20")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "512")),
        )
        agent_result = CairnAgent(
            client,
            dispatcher,
            max_wall_clock_s=float(os.getenv("INVESTIGATION_TIMEOUT_S", "150")),
        ).run(str(case["report"]), source_context=source_context)
        outcome.update(
            {
                "success": agent_result.finding is not None,
                "verdict": agent_result.verdict,
                "finding": agent_result.finding,
                "agent_elapsed_s": round(agent_result.elapsed_s, 3),
                "attempt_count": len(dispatcher.attempts),
                "fixture_port": fixture_port(fixture),
                "source_hash": source_context["source_hash"],
            }
        )
    except Exception as exc:
        outcome.update({"error": f"{type(exc).__name__}: {exc}"})
    finally:
        outcome["wall_clock_s"] = round(time.monotonic() - started, 3)
        rate = float(os.getenv("CELESTO_COST_PER_HOUR", "0.015"))
        outcome["cost_usd"] = round(float(outcome["wall_clock_s"]) / 3600 * rate, 6)
        if guest is not None:
            try:
                guest.delete()
                outcome["cleaned_up"] = True
            except Exception as exc:
                outcome["cleaned_up"] = False
                outcome["cleanup_error"] = f"{type(exc).__name__}: {exc}"
        live_dir = ROOT / "reports/live"
        live_dir.mkdir(parents=True, exist_ok=True)
        (live_dir / f"{case['case_id']}.json").write_text(
            json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return outcome


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id")
    parser.add_argument("--sandbox-name")
    args = parser.parse_args(argv)
    try:
        outcome = run_case(load_case(args.case_id), sandbox_name=args.sandbox_name)
    except (ValueError, LiveRuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(outcome, indent=2, sort_keys=True))
    return 0 if outcome.get("success") and outcome.get("cleaned_up") else 1


if __name__ == "__main__":
    raise SystemExit(main())
