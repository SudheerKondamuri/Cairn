#!/usr/bin/env python3
"""Gate 0: prove a real Celesto Cloud guest can be isolated and resumed."""

from __future__ import annotations

import argparse
import json
import sys
import time

from runner import ROOT, LiveGuest, LiveRuntimeError, load_env, unique_sandbox_name, upload_guest_helpers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="do not delete the guest (not recommended)")
    args = parser.parse_args(argv)
    load_env()
    name = unique_sandbox_name("gate0")
    guest: LiveGuest | None = None
    result: dict[str, object] = {"sandbox_name": name, "execution_target": "celesto_sandbox"}
    try:
        guest = LiveGuest(name)
        started = time.monotonic()
        guest.start()
        result["boot_to_ready_s"] = round(guest.boot_to_ready_s or (time.monotonic() - started), 3)
        upload_guest_helpers(guest)
        guest.run("python3 -m http.server 8765 --bind 127.0.0.1 >/tmp/cairn-gate0.log 2>&1 &")
        probe = guest.run("python3 /opt/cairn/network-probe.py 8765", timeout=10)
        result["network_probe"] = probe.stdout.strip()
        if not probe.ok:
            raise LiveRuntimeError(probe.stderr or "network containment probe failed")

        guest.upload_bytes(b"cairn-persistence-check\n", "/tmp/cairn-persistence-check.txt")
        guest.stop()
        guest.start()
        persisted = guest.run("test \"$(cat /tmp/cairn-persistence-check.txt)\" = cairn-persistence-check")
        result["persistence"] = persisted.ok
        if not persisted.ok:
            raise LiveRuntimeError("file did not survive Celesto stop/start")
        evidence_dir = ROOT / "reports/evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "network_policy_probe.log").write_text(
            json.dumps(
                {
                    "sandbox_name": name,
                    "execution_target": "celesto_sandbox",
                    "network_probe": result["network_probe"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (evidence_dir / "persistence_probe.log").write_text(
            json.dumps(
                {
                    "sandbox_name": name,
                    "file_survived_stop_start": True,
                    "boot_to_ready_s": result["boot_to_ready_s"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result["status"] = "passed"
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(result, indent=2), file=sys.stderr)
        return 1
    finally:
        if guest is not None and not args.keep:
            try:
                guest.delete()
            except Exception as exc:
                print(f"cleanup failed for {name}: {type(exc).__name__}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
