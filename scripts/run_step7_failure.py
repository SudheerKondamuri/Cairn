#!/usr/bin/env python3
"""Demonstrate step-7 failure, persistence resume, and unconditional cleanup."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from runner import ROOT, LiveGuest, load_env, unique_sandbox_name, upload_guest_helpers

from core.lifecycle import Step7Failure, Step7Lifecycle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-live", action="store_true", help="exercise the state machine with its fake adapter")
    args = parser.parse_args(argv)
    load_env()
    trace_path = ROOT / "reports/failure_trace.jsonl"
    if args.no_live:
        trace_path = Path(tempfile.mkdtemp(prefix="cairn-step7-trace-")) / "trace.jsonl"
    else:
        trace_path.unlink(missing_ok=True)
    name = unique_sandbox_name("step7")
    guest = None
    try:
        fixture_pid: str | None = None
        if args.no_live:
            from core.sandbox import FakeSandboxAdapter

            adapter = FakeSandboxAdapter(sandbox_name=name)
        else:
            guest = LiveGuest(name, audit_path=ROOT / "logs/commands.jsonl")
            guest.start()
            upload_guest_helpers(guest)
            guest.upload_file(
                ROOT / "fixtures/pattern_a_vulnerable/app.py",
                "/opt/cairn/fixture.py",
            )
            guest.stop()

            class RecoveryAdapter:
                def start(self) -> None:
                    guest.start()

                def stop(self) -> None:
                    guest.stop()

                def cleanup(self) -> None:
                    guest.delete()

            adapter = RecoveryAdapter()
        with tempfile.TemporaryDirectory(prefix="cairn-step7-") as directory:
            lifecycle = Step7Lifecycle(
                adapter,
                Path(directory) / "state.json",
                trace_path=trace_path,
                run_id="demo-step7",
            )
            failed = {"value": False}

            def fail_at_step7(_context: Step7Lifecycle) -> None:
                failed["value"] = True
                if guest is not None:
                    started = guest.run(
                        "python3 /opt/cairn/fixture.py >/tmp/cairn-step7-fixture.log 2>&1 & echo $!"
                    )
                    fixture_pid = started.stdout.strip().splitlines()[-1]
                    guest.run(f"kill {fixture_pid}")
                raise Step7Failure("deliberate first request dispatch failure after fixture termination")

            def resume(_context: Step7Lifecycle) -> str:
                if guest is not None:
                    restarted = guest.run(
                        "python3 /opt/cairn/fixture.py >/tmp/cairn-step7-fixture.log 2>&1 & echo $!"
                    )
                    if not restarted.stdout.strip():
                        raise RuntimeError("fixture did not restart during recovery")
                return "resumed"

            output = lifecycle.run_step7(fail_at_step7, recovery_operation=resume)
        policy = {
            "failed_step": 7,
            "total_steps": 10,
            "policy": "resume",
            "rationale": "The failed operation is the first request dispatch after the fixture process is deliberately terminated inside the Celesto guest. The source tree and guest workspace remain valid, while the marker directory is deliberately disposable and is cleared before a fresh attempt. Stop/start persistence preserves the known-good fixture and avoids expensive re-transfer and re-probing. Recovery restarts the fixture in the resumed guest, records the policy before the resumed operation, and the finalizer deletes the guest on both success and failure.",
            "trace_path": "reports/failure_trace.jsonl",
        }
        if not args.no_live:
            (ROOT / "reports/failure_policy.json").write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"sandbox_name": name, "failed": failed["value"], "result": output}, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if guest is not None:
            guest.delete()


if __name__ == "__main__":
    raise SystemExit(main())
