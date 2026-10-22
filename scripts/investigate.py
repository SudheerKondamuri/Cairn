#!/usr/bin/env python3
"""Run one dynamic Cairn investigation from a user source bundle and report."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from runner import (
    ROOT,
    LiveGuest,
    LiveRuntimeError,
    load_env,
    start_subject,
    upload_guest_helpers,
    upload_source_tree,
    unique_sandbox_name,
    wait_for_fixture,
)

from core.agent import CairnAgent, OpenAICompatibleClient
from core.audit import CommandAuditLog
from core.bundles import extract_source_archive
from core.investigation import InvestigationSpec
from core.investigation_report import build_investigation_report, render_markdown
from core.tools import CairnToolDispatcher
from core.validation import ToolPolicy


def run_investigation(
    spec: InvestigationSpec,
    source_root: Path,
    *,
    investigation_id: str,
    sandbox_name: str | None = None,
    output_dir: Path = ROOT / "reports/investigations",
) -> dict[str, object]:
    load_env()
    name = sandbox_name or unique_sandbox_name("cairn")
    started = time.monotonic()
    guest: LiveGuest | None = None
    finding: dict[str, object] | None = None
    error: str | None = None
    dependency_events: list[dict[str, object]] = []
    dispatcher: CairnToolDispatcher | None = None
    subject_manifest: dict[str, object] = {}
    lifecycle: dict[str, object] = {
        "sandbox_name": name,
        "sandbox_deleted": False,
        "source_uploaded": False,
        "application_started": False,
    }

    try:
        guest = LiveGuest(name, audit_path=ROOT / "logs/commands.jsonl")
        guest.start()
        upload_guest_helpers(guest)
        subject_manifest = upload_source_tree(guest, source_root)
        lifecycle["source_uploaded"] = True
        adapter = guest.adapter(
            port=spec.port or 5000,
            runtime=spec.runtime,
            dependency_mode=spec.dependency_mode,
            allow_install_scripts=spec.allow_install_scripts,
            working_directory=spec.working_directory,
            test_argv=spec.test_argv,
        )
        policy = (
            ToolPolicy.package_harness(
                allow_dependency_install=True,
                dependency_mode=spec.dependency_mode,
            )
            if spec.subject_type == "package_harness"
            else ToolPolicy.dynamic_http(
                allow_dependency_install=True,
                dependency_mode=spec.dependency_mode,
            )
        )
        dispatcher = CairnToolDispatcher(
            adapter,
            audit=CommandAuditLog(ROOT / "logs/commands.jsonl", sandbox_name=name),
            policy=policy,
        )
        dependency_result = dispatcher.install_dependencies()
        if (
            dependency_result.get("error")
            or dependency_result.get("exit_code") not in (None, 0)
            or dependency_result.get("supported") is False
        ):
            raise LiveRuntimeError(
                f"dependency preparation failed: {dependency_result.get('error', dependency_result)}"
            )
        if spec.subject_type == "http_app":
            start_subject(guest, spec)
            lifecycle["application_started"] = True
            if spec.port is not None:
                wait_for_fixture(guest, spec.port)

        client = OpenAICompatibleClient(
            base_url=os.getenv("LLM_BASE_URL", ""),
            api_key=os.getenv("LLM_API_KEY", ""),
            model=os.getenv("LLM_MODEL", ""),
            timeout_s=float(os.getenv("LLM_TIMEOUT_S", "20")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "512")),
        )
        agent_result = CairnAgent(
            client,
            dispatcher,
            max_wall_clock_s=float(os.getenv("INVESTIGATION_TIMEOUT_S", "150")),
        ).run(
            spec.report,
            source_root="/input/source",
            source_context={
                "files": subject_manifest.get("files", []),
                "source_hash": subject_manifest.get("source_hash"),
            },
        )
        finding = agent_result.finding
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if dispatcher is not None:
            dependency_events = list(dispatcher.dependency_events)
        if guest is not None:
            try:
                guest.delete()
                lifecycle["sandbox_deleted"] = True
            except Exception as exc:
                lifecycle["cleanup_error"] = f"{type(exc).__name__}: {exc}"

    report = build_investigation_report(
        investigation_id=investigation_id,
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
    (output_dir / f"{investigation_id}.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / f"{investigation_id}.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    return report


def _read_report(report: str | None, report_file: Path | None) -> str:
    if bool(report) == bool(report_file):
        raise ValueError("provide exactly one of --report or --report-file")
    return report if report is not None else report_file.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="source directory or tar archive")
    parser.add_argument("--report")
    parser.add_argument("--report-file", type=Path)
    parser.add_argument("--subject-type", default="http_app", choices=["http_app", "package_harness"])
    parser.add_argument("--runtime", required=True, choices=["python", "node", "go"])
    parser.add_argument("--start-argv", nargs="+")
    parser.add_argument("--test-argv", nargs="+")
    parser.add_argument("--port", type=int)
    parser.add_argument("--working-directory", default=".")
    parser.add_argument("--dependency-mode", default="offline", choices=["offline", "prebuilt", "controlled_network"])
    parser.add_argument("--allow-network-during-install", action="store_true")
    parser.add_argument("--allow-install-scripts", action="store_true")
    parser.add_argument("--investigation-id", default=None)
    parser.add_argument("--sandbox-name")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/investigations")
    args = parser.parse_args(argv)

    try:
        spec = InvestigationSpec.from_mapping(
            {
                "subject_type": args.subject_type,
                "report": _read_report(args.report, args.report_file),
                "runtime": args.runtime,
                "start_argv": args.start_argv or (),
                "test_argv": args.test_argv or (),
                "port": args.port,
                "working_directory": args.working_directory,
                "dependency_mode": args.dependency_mode,
                "allow_network_during_install": args.allow_network_during_install,
                "allow_install_scripts": args.allow_install_scripts,
            }
        )
        investigation_id = args.investigation_id or f"inv-{int(time.time())}"
        source = args.source.resolve()
        with tempfile.TemporaryDirectory(prefix="cairn-source-") as temporary:
            source_root = Path(temporary)
            if source.is_dir():
                source_root = source
            else:
                extract_source_archive(source, source_root)
            report = run_investigation(
                spec,
                source_root,
                investigation_id=investigation_id,
                sandbox_name=args.sandbox_name,
                output_dir=args.output_dir,
            )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["verdict"] != "inconclusive" and report["lifecycle"]["sandbox_deleted"] else 1
    except (OSError, ValueError, LiveRuntimeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
