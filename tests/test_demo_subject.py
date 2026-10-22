from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_subject_exposes_realistic_local_routes() -> None:
    module = _load(ROOT / "demo-subject/app.py")

    status, health = module.handle_request("/health", {})
    assert status == 200
    assert health["service"] == "northstar-operations-diagnostics"

    status, latest = module.handle_request("/api/v1/jobs/latest", {})
    assert status == 200
    assert latest["job"]["status"] == "completed"

    status, diagnostic = module.handle_request(
        "/api/v1/diagnostics/resolve", {"host": ["localhost"]}
    )
    assert status == 200
    assert diagnostic["target"] == "localhost"


def test_patched_demo_subject_uses_the_same_contract() -> None:
    module = _load(ROOT / "demo-subject-patched/app.py")
    status, diagnostic = module.handle_request(
        "/api/v1/diagnostics/resolve", {"host": ["localhost"]}
    )
    assert status == 200
    assert diagnostic["service"] == "northstar-operations-diagnostics"
    assert diagnostic["target"] == "localhost"
