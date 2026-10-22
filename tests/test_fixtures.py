from __future__ import annotations

from pathlib import Path


def test_patched_pattern_a_rejects_shell_metacharacters() -> None:
    from fixtures.pattern_a_patched.app import handle_request

    status, _ = handle_request(
        "/diagnose", {"host": ["127.0.0.1;touch /tmp/cairn-markers/test"]}
    )
    assert status == 400


def test_patched_pattern_b_rejects_shell_metacharacters() -> None:
    from fixtures.pattern_b_patched.app import handle_request

    status, _ = handle_request(
        "/convert", {"filename": ["sample.txt;touch /tmp/cairn-markers/test"]}
    )
    assert status == 400


def test_fixture_source_contains_both_intentionally_different_patterns() -> None:
    root = Path("fixtures")
    vulnerable_a = (root / "pattern_a_vulnerable/app.py").read_text(encoding="utf-8")
    patched_a = (root / "pattern_a_patched/app.py").read_text(encoding="utf-8")
    vulnerable_b = (root / "pattern_b_vulnerable/app.py").read_text(encoding="utf-8")
    patched_b = (root / "pattern_b_patched/app.py").read_text(encoding="utf-8")
    assert "shell=True" in vulnerable_a and "shell=False" in patched_a
    assert "os.system" in vulnerable_b and "shutil.copy" in patched_b
