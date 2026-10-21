"""Marker-based evidence oracle with independent recheck hooks."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OracleResult:
    """The primary observation and every independent confirmation result."""

    marker: str
    primary_match: bool
    rechecks: tuple[bool, ...]
    errors: tuple[str, ...]

    @property
    def confirmed(self) -> bool:
        return self.primary_match and bool(self.rechecks) and not self.errors and all(self.rechecks)

    @property
    def rechecked(self) -> bool:
        return bool(self.rechecks)

    def __bool__(self) -> bool:
        return self.confirmed

    def as_dict(self) -> dict[str, Any]:
        return {
            "marker": self.marker,
            "primary_match": self.primary_match,
            "rechecks": list(self.rechecks),
            "errors": list(self.errors),
            "confirmed": self.confirmed,
        }


RecheckHook = Callable[[Any], bool]


class MarkerOracle:
    """Confirm a marker through a primary response scan and extra hooks.

    Hooks are deliberately supplied by the caller so a second observation
    path can be used (for example, a separate header/body parser or a fresh
    request).  A hook exception is recorded as a failed independent check;
    it never turns an uncertain result into a positive finding.
    """

    def __init__(self, marker: str, *, recheck_hooks: Sequence[RecheckHook] = ()) -> None:
        if not isinstance(marker, str) or not marker or len(marker) > 512:
            raise ValueError("marker must be a non-empty string of at most 512 characters")
        if any(ord(char) < 0x20 or ord(char) == 0x7F for char in marker):
            raise ValueError("marker must not contain control characters")
        self.marker = marker
        self._recheck_hooks = self._validate_hooks(recheck_hooks)

    @staticmethod
    def _validate_hooks(hooks: Sequence[RecheckHook]) -> tuple[RecheckHook, ...]:
        if isinstance(hooks, (str, bytes)):
            raise TypeError("recheck_hooks must be callables")
        result: list[RecheckHook] = []
        for hook in hooks:
            if not callable(hook):
                raise TypeError("every recheck hook must be callable")
            result.append(hook)
        return tuple(result)

    @property
    def recheck_hooks(self) -> tuple[RecheckHook, ...]:
        return self._recheck_hooks

    def check(
        self,
        response: Any,
        *,
        recheck_hooks: Sequence[RecheckHook] | None = None,
    ) -> OracleResult:
        """Observe a response and run all configured independent hooks."""

        text = self._response_text(response)
        primary = self.marker in text
        hooks = self._recheck_hooks if recheck_hooks is None else self._validate_hooks(recheck_hooks)
        rechecks: list[bool] = []
        errors: list[str] = []
        for index, hook in enumerate(hooks):
            try:
                result = hook(response)
                if not isinstance(result, bool):
                    raise TypeError("hook must return bool")
                rechecks.append(result)
            except Exception as exc:  # hooks are evidence inputs, not control flow
                rechecks.append(False)
                errors.append(f"recheck[{index}]: {type(exc).__name__}: {exc}")
        return OracleResult(self.marker, primary, tuple(rechecks), tuple(errors))

    def run_rechecks(self, response: Any) -> tuple[bool, ...]:
        """Run only the independent hooks, useful for a separate audit pass."""

        return self.check(response).rechecks

    def assert_confirmed(self, response: Any) -> OracleResult:
        """Return a positive result or raise a clear evidence error."""

        result = self.check(response)
        if not result.confirmed:
            raise AssertionError("marker was not independently confirmed")
        return result

    def _response_text(self, response: Any) -> str:
        if isinstance(response, bytes):
            return response.decode("utf-8", errors="replace")
        if isinstance(response, str):
            return response
        if isinstance(response, Mapping):
            if "body" in response:
                body = response["body"]
                if isinstance(body, bytes):
                    return body.decode("utf-8", errors="replace")
                return str(body)
            try:
                return json.dumps(response, sort_keys=True, default=str)
            except (TypeError, ValueError):
                return str(response)
        body = getattr(response, "body", None)
        if body is not None:
            return body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
        return str(response)
