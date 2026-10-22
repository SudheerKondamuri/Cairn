from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from core.bundles import BundleValidationError, collect_source_files, validate_source_archive
from core.agent import CairnAgent, openai_tool_definitions
from core.investigation import InvestigationSpec, InvestigationSpecError
from core.investigation_report import build_investigation_report, render_markdown
from core.sandbox import FakeSandboxAdapter, SandboxResult
from core.tools import CairnToolDispatcher
from core.validation import ToolPolicy, ToolValidationError, validate_tool_call


def test_dynamic_tool_policy_accepts_arbitrary_local_route_and_parameter() -> None:
    policy = ToolPolicy.dynamic_http()

    result = validate_tool_call(
        "send_request",
        {
            "path": "/upload/avatar",
            "param_name": "filename",
            "param_value": "avatar.png; touch /tmp/cairn-markers/probe; #",
        },
        policy=policy,
    )

    assert result["path"] == "/upload/avatar"
    assert result["param_name"] == "filename"

    with pytest.raises(ToolValidationError):
        validate_tool_call(
            "send_request",
            {"path": "https://attacker.example", "param_name": "q", "param_value": "x"},
            policy=policy,
        )


def test_dynamic_policy_can_expose_controller_validated_dependency_install() -> None:
    policy = ToolPolicy.dynamic_http(allow_dependency_install=True)
    assert validate_tool_call("install_dependencies", {}, policy=policy) == {}

    with pytest.raises(ToolValidationError):
        validate_tool_call("install_dependencies", {"command": "npm install"}, policy=policy)


def test_investigation_spec_validates_http_and_harness_inputs() -> None:
    http_spec = InvestigationSpec.from_mapping(
        {
            "subject_type": "http_app",
            "report": "The upload endpoint may be vulnerable.",
            "runtime": "python",
            "start_argv": ["python3", "app.py"],
            "port": 5000,
        }
    )
    assert http_spec.start_argv == ("python3", "app.py")
    assert http_spec.port == 5000

    harness_spec = InvestigationSpec.from_mapping(
        {
            "subject_type": "package_harness",
            "report": "The merge function may allow prototype pollution.",
            "runtime": "node",
            "test_argv": ["node", "cairn-harness.js"],
        }
    )
    assert harness_spec.test_argv == ("node", "cairn-harness.js")

    with pytest.raises(InvestigationSpecError):
        InvestigationSpec.from_mapping(
            {
                "subject_type": "http_app",
                "report": "missing start command",
                "runtime": "python",
                "port": 5000,
            }
        )


def test_investigation_report_contains_verdict_explanation_and_evidence() -> None:
    report = build_investigation_report(
        investigation_id="inv-test-1",
        spec={
            "subject_type": "http_app",
            "runtime": "python",
            "report": "The upload endpoint may execute commands.",
        },
        finding={
            "verdict": "verified",
            "proposal": {
                "path": "/upload",
                "param_name": "filename",
                "param_value": "x; touch /tmp/cairn-markers/probe; #",
                "rationale": "The marker was observed.",
            },
            "attempts": [{"status": 200, "marker_detected": True}],
            "source_hash": "a" * 64,
            "independent_recheck": {
                "marker_detected": True,
                "request_constructed_by": "control_plane",
            },
        },
        lifecycle={"sandbox_deleted": True},
    )

    assert report["verdict"] == "verified"
    assert report["summary"]
    assert report["evidence"]["independent_recheck"]["marker_detected"] is True
    assert "verified" in render_markdown(report)


def test_source_archive_validation_rejects_parent_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        payload = b"unsafe"
        info = tarfile.TarInfo("../escape.txt")
        info.size = len(payload)
        stream.addfile(info, io.BytesIO(payload))

    with pytest.raises(BundleValidationError):
        validate_source_archive(archive)


def test_source_directory_collection_ignores_generated_python_caches(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('source')\n", encoding="utf-8")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "app.cpython-311.pyc").write_bytes(b"bytecode")

    files = collect_source_files(tmp_path)

    assert [relative for _path, relative in files] == ["app.py"]


def test_package_harness_uses_fresh_marker_recheck() -> None:
    class HarnessAdapter(FakeSandboxAdapter):
        def run_harness(self, marker: str) -> SandboxResult:
            self.markers.add(marker)
            return SandboxResult(ok=True, exit_code=0, stdout="harness passed")

    dispatcher = CairnToolDispatcher(
        HarnessAdapter(sandbox_name="sbx-harness0001"),
        policy=ToolPolicy.package_harness(),
    )
    observation = dispatcher.dispatch("run_harness", {})
    finding = dispatcher.dispatch(
        "submit_finding",
        {"verdict": "verified", "rationale": "The harness marker was observed."},
    )

    assert observation["marker_detected"] is True
    assert finding["verdict"] == "verified"
    assert finding["independent_recheck"]["request_constructed_by"] == "control_plane"


def test_package_policy_exposes_harness_not_http_request_tool() -> None:
    names = {
        item["function"]["name"]
        for item in openai_tool_definitions(ToolPolicy.package_harness())
    }
    assert "run_harness" in names
    assert "send_request" not in names


def test_dependency_failure_forces_inconclusive_instead_of_not_reproduced() -> None:
    class BrokenDependencies(FakeSandboxAdapter):
        def install_dependencies(self) -> dict[str, object]:
            return {"installed": False, "error": "offline cache missing", "exit_code": 1}

    dispatcher = CairnToolDispatcher(
        BrokenDependencies(sandbox_name="sbx-depfail0001"),
        policy=ToolPolicy.dynamic_http(allow_dependency_install=True),
    )
    dispatcher.dispatch("install_dependencies", {})
    finding = dispatcher.dispatch(
        "submit_finding",
        {
            "verdict": "not_reproduced",
            "path": "/upload",
            "param_name": "filename",
            "param_value": "x",
            "rationale": "The app did not show a marker.",
        },
    )
    assert finding["verdict"] == "inconclusive"


def test_dynamic_agent_can_reproduce_a_non_fixture_route() -> None:
    class Client:
        def __init__(self) -> None:
            self.responses = [
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "inspect",
                                        "function": {
                                            "name": "inspect_source",
                                            "arguments": '{"path":"server.py","start_line":1,"end_line":20}',
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "request",
                                        "function": {
                                            "name": "send_request",
                                            "arguments": json.dumps(
                                                {
                                                    "path": "/upload/avatar",
                                                    "param_name": "filename",
                                                    "param_value": "avatar.png; touch /tmp/cairn-markers/probe; #",
                                                }
                                            ),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "finding",
                                        "function": {
                                            "name": "submit_finding",
                                            "arguments": json.dumps(
                                                {
                                                    "verdict": "verified",
                                                    "path": "/upload/avatar",
                                                    "param_name": "filename",
                                                    "param_value": "avatar.png; touch /tmp/cairn-markers/probe; #",
                                                    "rationale": "marker observed",
                                                }
                                            ),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
            ]

        def complete(self, messages, tools):
            return self.responses.pop(0)

    def handler(**request: str):
        return {
            "ok": True,
            "status_code": 200,
            "metadata": {"marker_detected": "/tmp/cairn-markers/" in request["param_value"]},
        }

    adapter = FakeSandboxAdapter(
        sandbox_name="sbx-dynamic0001",
        source_files={"server.py": "unsafe upload handler"},
        request_handler=handler,
    )
    dispatcher = CairnToolDispatcher(adapter, policy=ToolPolicy.dynamic_http())
    result = CairnAgent(Client(), dispatcher).run(
        "The avatar upload filename may execute commands.",
        source_context={"files": ["server.py"]},
    )

    assert result.verdict == "verified"
    assert result.finding["proposal"]["path"] == "/upload/avatar"


def test_dynamic_agent_finalizes_complete_marker_free_attempts_as_not_reproduced() -> None:
    class RepeatingClient:
        def complete(self, messages, tools):
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "request",
                                    "function": {
                                        "name": "send_request",
                                        "arguments": json.dumps(
                                            {
                                                "path": "/lookup",
                                                "param_name": "q",
                                                "param_value": "test; touch /tmp/cairn-markers/probe; #",
                                            }
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

    class NoMarkerAdapter(FakeSandboxAdapter):
        def send_request(self, path: str, param_name: str, param_value: str, marker: str):
            self.clear_markers()
            return SandboxResult(ok=True, status_code=200, body="literal")

    adapter = NoMarkerAdapter(
        sandbox_name="sbx-negative0001",
        source_files={"app.py": "safe"},
    )
    dispatcher = CairnToolDispatcher(adapter, policy=ToolPolicy.dynamic_http())
    dispatcher.budget.max_tool_calls = 1
    result = CairnAgent(RepeatingClient(), dispatcher).run("Investigate /lookup?q.")

    assert result.verdict == "not_reproduced"
    assert result.finding["controller_fallback"] is True
    assert result.finding["independent_recheck"] is None


def test_dynamic_negative_fallback_does_not_downgrade_unknown_attempt() -> None:
    class UnknownAdapter(FakeSandboxAdapter):
        def send_request(self, path: str, param_name: str, param_value: str, marker: str):
            raise OSError("request outcome unknown")

    class RequestClient:
        def complete(self, messages, tools):
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "request",
                                    "function": {
                                        "name": "send_request",
                                        "arguments": json.dumps(
                                            {
                                                "path": "/lookup",
                                                "param_name": "q",
                                                "param_value": "x",
                                            }
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

    dispatcher = CairnToolDispatcher(
        UnknownAdapter(sandbox_name="sbx-negative0002"),
        policy=ToolPolicy.dynamic_http(),
    )
    dispatcher.budget.max_tool_calls = 1
    result = CairnAgent(RequestClient(), dispatcher).run("Investigate /lookup?q.")

    assert result.verdict == "inconclusive"
