#!/usr/bin/env python3
"""Run one dynamic Cairn investigation from a user source bundle and report."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
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

from core.control import InvestigationCancelled
from core.agent import CairnAgent, OpenAICompatibleClient
from core.audit import CommandAuditLog
from core.bundles import extract_source_archive
from core.github import GitHubSourceError, download_archive
from core.investigation import InvestigationSpec
from core.investigation_report import build_investigation_report, render_markdown
from core.tools import CairnToolDispatcher
from core.validation import ToolPolicy


def _progress(message: str) -> None:
    """Emit human-readable progress without exposing credentials or payloads."""

    print(f"[cairn] {message}", flush=True)


def run_investigation(
    spec: InvestigationSpec,
    source_root: Path,
    *,
    investigation_id: str,
    sandbox_name: str | None = None,
    output_dir: Path = ROOT / "reports/investigations",
    on_progress=None,
    audit_path: Path | None = None,
) -> dict[str, object]:
    def emit(message):
        _progress(message)
        if on_progress is not None and not message.startswith(('deleting ', 'Celesto guest deleted', 'investigation stopped:', 'reports written')):
            on_progress(message)

    load_env()
    name = sandbox_name or unique_sandbox_name("cairn")
    audit_file = audit_path or ROOT / "logs/commands.jsonl"
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
        "isolation": "celesto_firecracker_microvm",
        "network_policy": "controlled_network" if spec.dependency_mode == "controlled_network" else "enforced_offline",
    }

    try:
        emit(f"creating Celesto guest {name}")
        guest = LiveGuest(name, audit_path=audit_file, dependency_network=spec.dependency_mode == "controlled_network")
        guest.start()
        emit(f"guest ready {name}")
        upload_guest_helpers(guest)
        subject_manifest = upload_source_tree(guest, source_root)
        lifecycle["source_uploaded"] = True
        emit("source and fixed guest helpers uploaded")

        # Zero-config smart entrypoint auto-detection
        files = set(subject_manifest.get("files") or [])
        if spec.subject_type == "http_app":
            if list(spec.start_argv) == ["python3", "app.py"] and spec.working_directory == ".":
                if "app.py" not in files:
                    if "app/app.py" in files:
                        spec = dataclasses.replace(spec, working_directory="app", start_argv=["python3", "app.py"])
                        emit("zero-config: auto-detected application in app/ directory: python3 app.py (cwd: app)")
                    elif "src/app.py" in files:
                        spec = dataclasses.replace(spec, working_directory="src", start_argv=["python3", "app.py"])
                        emit("zero-config: auto-detected application in src/ directory: python3 app.py (cwd: src)")
                    elif "start.sh" in files:
                        spec = dataclasses.replace(spec, start_argv=["sh", "start.sh"])
                        emit("zero-config: auto-detected startup script sh start.sh")
                    elif "main.py" in files:
                        spec = dataclasses.replace(spec, start_argv=["python3", "main.py"])
                        emit("zero-config: auto-detected entrypoint python3 main.py")
                    elif "server.py" in files:
                        spec = dataclasses.replace(spec, start_argv=["python3", "server.py"])
                        emit("zero-config: auto-detected entrypoint python3 server.py")

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
            audit=CommandAuditLog(audit_file, sandbox_name=name),
            policy=policy,
        )
        original_dispatch = dispatcher.dispatch
        def observed_dispatch(name, arguments):
            emit("Tool: " + name)
            result = original_dispatch(name, arguments)
            emit("Tool completed: " + name)
            return result
        dispatcher.dispatch = observed_dispatch
        emit("installing dependencies inside Celesto" if spec.dependency_mode == "controlled_network" else "preparing offline dependencies")
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
            emit("starting supplied application inside the guest")
            start_subject(guest, spec)
            lifecycle["process_launched"] = True
            target_port = spec.port or 5000
            try:
                wait_for_fixture(guest, target_port)
                if spec.port is None:
                    spec = dataclasses.replace(spec, port=target_port)
                adapter.port = target_port
                lifecycle["application_started"] = True
                emit(f"application ready on guest loopback port {target_port}")
            except LiveRuntimeError as exc:
                match = re.search(r"Listening TCP ports:\s*\[([0-9, ]+)\]", str(exc))
                adopted = False
                SYSTEM_RESERVED_PORTS = {22, 53, 68, 8445, 9999, 10000, 2375, 2376}
                if match:
                    discovered = [int(p.strip()) for p in match.group(1).split(",") if p.strip()]
                    candidates = [p for p in discovered if p not in SYSTEM_RESERVED_PORTS and p != target_port]
                    chosen = None
                    if len(candidates) == 1:
                        chosen = candidates[0]
                    elif len(candidates) > 1:
                        common_web = [p for p in candidates if p in {5000, 5001, 8000, 8080, 3000, 8888, 4000}]
                        chosen = common_web[0] if common_web else candidates[0]
                    if chosen is not None:
                        if spec.port is not None:
                            emit(f"configured port {spec.port} closed; auto-adopting discovered port {chosen}")
                        else:
                            emit(f"zero-config mode: auto-adopting discovered port {chosen}")
                        try:
                            wait_for_fixture(guest, chosen)
                            adapter.port = chosen
                            spec = dataclasses.replace(spec, port=chosen)
                            lifecycle["application_started"] = True
                            lifecycle["auto_discovered_port"] = chosen
                            emit(f"application ready on guest loopback port {chosen}")
                            adopted = True
                        except LiveRuntimeError:
                            pass
                if not adopted:
                    raise

        emit("running bounded investigation tools")
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
        if finding is not None and getattr(dispatcher, "inspections", None) and "inspections" not in finding:
            finding = {**finding, "inspections": list(dispatcher.inspections)}
        emit(f"investigation finished with verdict {agent_result.verdict}")
    except InvestigationCancelled:
        error = "Investigation cancelled by its owner."
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        emit(f"investigation stopped: {error}")
    finally:
        if dispatcher is not None:
            dependency_events = list(dispatcher.dependency_events)
        if guest is not None:
            try:
                emit(f"deleting Celesto guest {name}")
                guest.delete()
                lifecycle["sandbox_deleted"] = True
                emit("Celesto guest deleted")
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
    emit(f"reports written under {output_dir}")
    return report


def _read_report(report: str | None, report_file: Path | None) -> str:
    if bool(report) == bool(report_file):
        raise ValueError("provide exactly one of --report or --report-file")
    return report if report is not None else report_file.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source", type=Path, help="source directory or tar archive")
    source_group.add_argument("--github-url", help="HTTPS GitHub repository URL to fetch in the control plane")
    parser.add_argument("--github-ref", default="main", help="GitHub branch, tag, or commit (default: main)")
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
        with tempfile.TemporaryDirectory(prefix="cairn-source-") as temporary:
            source_root = Path(temporary)
            if args.github_url:
                archive = Path(temporary) / "github-source.tar.gz"
                download_archive(args.github_url, archive, ref=args.github_ref)
                extract_source_archive(archive, source_root)
            else:
                source = args.source.resolve()
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
    except (GitHubSourceError, OSError, ValueError, LiveRuntimeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
