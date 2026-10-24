from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import worker  # noqa: E402


def test_worker_waits_when_queue_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    sleeps: list[float] = []

    def fake_process_once(*_args, **_kwargs) -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            return False
        raise RuntimeError("stop test loop")

    monkeypatch.setattr(worker, "process_once", fake_process_once)

    with pytest.raises(RuntimeError, match="stop test loop"):
        worker.run_worker(
            object(),
            upload_root=ROOT / ".cairn/uploads",
            output_dir=ROOT / "reports/investigations",
            poll_seconds=2,
            sleep=sleeps.append,
        )

    assert calls == 2
    assert sleeps == [2]
