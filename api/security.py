"""Small control-plane request guard for API authentication and abuse limits."""

from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ApiRequestGuard:
    api_key: str = ""
    require_auth: bool = False
    rate_limit: int = 60
    window_s: float = 60.0
    clock: Callable[[], float] = time.monotonic
    _hits: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_key != "replace-me")

    @property
    def configuration_error(self) -> bool:
        return self.require_auth and not self.configured

    def check(self, *, client_id: str, supplied_key: str | None) -> tuple[str, int, int | None]:
        """Return (status, http_code, retry_after_seconds)."""

        if self.configuration_error:
            return "api authentication is not configured", 503, None
        if self.require_auth and (
            not supplied_key or not hmac.compare_digest(supplied_key, self.api_key)
        ):
            return "authentication required", 401, None

        now = self.clock()
        hits = self._hits[client_id]
        cutoff = now - max(self.window_s, 0.1)
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= max(self.rate_limit, 1):
            retry_after = max(1, int((hits[0] + self.window_s) - now))
            return "rate limit exceeded", 429, retry_after
        hits.append(now)
        return "", 200, None
