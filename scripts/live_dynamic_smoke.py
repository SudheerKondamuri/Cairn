#!/usr/bin/env python3
"""Exercise one non-fixture dynamic HTTP investigation on Celesto Cloud.

This deliberately skips the LLM so it can isolate the Celesto guest, dynamic
route/parameter policy, marker oracle, independent recheck, and cleanup after a
provider timeout. It writes the same JSON/Markdown report shape as the normal
investigation runner.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from runner import (
    ROOT,
    LiveGuest,
    LiveRuntimeError,
    load_env,
    start_subject,
    unique_sandbox_name,
    upload_guest_helpers,
    upload_source_tree,
    wait_for_fixture,
)

from core.audit import CommandAuditLog
from core.investigation import InvestigationSpec
from core.investigation_report import build_investigation_report, render_markdown
from core.tools import CairnToolDispatcher
from core.validation import ToolPolicy


INVESTIGATION_ID = "inv-real-dynamic-control-20261023"


def main() -> int:
    load_env()
    spec = InvestigationSpec.from_mapping(
        {
            "subject_type": "http_app",
            "report": (ROOT / "real-test-subject/security-report.txt").read_text(
                encoding="utf-8"
            ),
            "runtime": "python",
            "start_argv": ["python3", "app.py"],
            "port": 5002,
            "working_directory": ".",
            "dependency_mode": "offline",
        }
    )
    source_root = ROOT / "real-test-subject"
    output_dir = ROOT / "reports/investigations"
    sandbox_name = unique_sandbox_name("dynamiccontrol")
    started = time.monotonic()
    guest: LiveGuest | None = None
    dispatcher: CairnToolDispatcher | None = None
    subject_manifest: dict[str, object] = {}
    lifecycle: dict[str, object] = {
        "sandbox_name": sandbox_name,
        "sandbox_deleted": False,
        "source_uploaded": False,
        "application_started": False,
        "llm_called": False,
        "test_mode": "direct_control_plane_smoke",
    }
    finding: dict[str, object] | None = None
    error: str | None = None

    try:
        guest = LiveGuest(sandbox_name, audit_path=ROOT / "logs/commands.jsonl")
        guest.start()
        upload_guest_helpers(guest)
        subject_manifest = upload_source_tree(guest, source_root)
        lifecycle["source_uploaded"] = True
        adapter = guest.adapter(
            port=spec.port or 5000,
            runtime=spec.runtime,
            dependency_mode=spec.dependency_mode,
            working_directory=spec.working_directory,
        )
        dispatcher = CairnToolDispatcher(
            adapter,
            audit=CommandAuditLog(ROOT / "logs/commands.jsonl", sandbox_name=sandbox_name),
            policy=ToolPolicy.dynamic_http(
                allow_dependency_install=True,
                dependency_mode=spec.dependency_mode,
            ),
        )
        dependency_result = dispatcher.install_dependencies()
        if (
            dependency_result.get("error")
            or dependency_result.get("exit_code") not in (None, 0)
            or dependency_result.get("supported") is False
        ):
            raise LiveRuntimeError(f"dependency preparation failed: {dependency_result}")
        start_subject(guest, spec)
        lifecycle["application_started"] = True
        wait_for_fixture(guest, spec.port or 5000)
        inspected = dispatcher.inspect_source(path="app.py", start_line=1, end_line=200)
        marker_payload = "localhost; touch /tmp/cairn-markers/cairn-control-smoke; #"
        observation = dispatcher.dispatch(
            "send_request",
            {"path": "/lookup", "param_name": "q", "param_value": marker_payload},
        )
        finding = dispatcher.dispatch(
            "submit_finding",
            {
                "verdict": "verified" if observation["marker_detected"] else "not_reproduced",
                "path": "/lookup",
                "param_name": "q",
                "param_value": marker_payload,
                "rationale": (
                    "The direct Celesto control-plane smoke found the non-fixture /lookup route "
                    "and q parameter, observed marker evidence, and requested an independent "
                    "fresh-token recheck."
                ),
            },
        )
        if finding.get("verdict") != "verified":
            raise LiveRuntimeError(f"dynamic smoke did not verify: {finding}")
        lifecycle["inspected_source"] = inspected["path"]
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if dispatcher is not None:
            dependency_events = list(dispatcher.dependency_events)
        else:
            dependency_events = []
        if guest is not None:
            try:
                guest.delete()
                lifecycle["sandbox_deleted"] = True
            except Exception as exc:
                lifecycle["cleanup_error"] = f"{type(exc).__name__}: {exc}"

    report = build_investigation_report(
        investigation_id=INVESTIGATION_ID,
        spec=spec.as_dict(),
        finding=finding,
        lifecycle={
            **lifecycle,
            "wall_clock_s": round(time.monotonic() - started, 3),
            "subject_manifest": subject_manifest,
        },
        dependencies={
            "mode": spec.dependency_mode,
            "network_during_install_allowed": spec.allow_network_during_install,
            "install_scripts_allowed": spec.allow_install_scripts,
            "events": dependency_events,
        },
        error=error,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{INVESTIGATION_ID}.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / f"{INVESTIGATION_ID}.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verdict"] == "verified" and report["lifecycle"]["sandbox_deleted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
