"""Dependency-light building blocks for the Cairn reproduction agent."""

from .agent import CairnAgent, OpenAICompatibleClient
from .audit import CommandAuditLog, EXECUTION_TARGET
from .lifecycle import LifecycleState, Step7Failure, Step7Lifecycle
from .metrics import (
    ReportValidationError,
    build_reliability_report,
    build_reliability_summary,
    validate_reliability_report,
    validate_reliability_summary,
)
from .oracle import MarkerOracle, OracleResult
from .sandbox import (
    CelestoSandboxAdapter,
    FakeSandboxAdapter,
    SandboxAdapter,
    SandboxAdapterError,
    SandboxResult,
    decode_guest_arguments,
    encode_guest_arguments,
    safe_guest_helper_argv,
)
from .tools import CairnToolDispatcher, InvestigationBudget, ToolExecutionError
from .validation import (
    TOOL_SCHEMAS,
    ToolValidationError,
    validate_tool,
    validate_tool_call,
)

__all__ = [
    "CelestoSandboxAdapter",
    "CairnAgent",
    "CairnToolDispatcher",
    "CommandAuditLog",
    "EXECUTION_TARGET",
    "FakeSandboxAdapter",
    "InvestigationBudget",
    "LifecycleState",
    "MarkerOracle",
    "OpenAICompatibleClient",
    "OracleResult",
    "ReportValidationError",
    "SandboxAdapter",
    "SandboxAdapterError",
    "SandboxResult",
    "Step7Lifecycle",
    "Step7Failure",
    "ToolExecutionError",
    "TOOL_SCHEMAS",
    "ToolValidationError",
    "build_reliability_summary",
    "decode_guest_arguments",
    "encode_guest_arguments",
    "build_reliability_report",
    "safe_guest_helper_argv",
    "validate_reliability_report",
    "validate_reliability_summary",
    "validate_tool",
    "validate_tool_call",
]
