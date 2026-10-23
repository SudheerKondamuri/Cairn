from __future__ import annotations

import io
import json
import tarfile
from datetime import datetime, timezone

from api.app import create_app
from api.repository import RepositoryError, RunRepository
from api.validation import ValidationError, validate_run_payload


VALID_PAYLOAD = {
    "run_id": "run-test-1",
    "sandbox_name": "sbx-test0001",
    "problem_id": "pattern-a-vulnerable-accurate",
    "state": "created",
    "execution_target": "celesto_sandbox",
}


class MemoryRepository:
    def __init__(self) -> None:
        self.runs: list[dict[str, object]] = []

    def list_runs(self) -> list[dict[str, object]]:
        return list(self.runs)

    def create_run(self, **values: str) -> dict[str, object]:
        run = {
            **values,
            "outcome": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        self.runs.append(run)
        return run


def test_validation_accepts_exact_contract() -> None:
    assert validate_run_payload(VALID_PAYLOAD) == VALID_PAYLOAD


def test_validation_rejects_bad_target_state_and_name() -> None:
    for field, value in (
        ("execution_target", "host"),
        ("state", "queued"),
        ("sandbox_name", "sbx-too-short"),
    ):
        payload = dict(VALID_PAYLOAD)
        payload[field] = value
        try:
            validate_run_payload(payload)
        except ValidationError as exc:
            assert exc.field == field
        else:  # pragma: no cover - assertion branch
            raise AssertionError(f"{field} was accepted")


def test_health_does_not_open_lazy_database_connection() -> None:
    calls: list[str | None] = []

    def connection_factory(dsn: str | None) -> object:
        calls.append(dsn)
        raise AssertionError("health must not connect")

    app = create_app(
        {"TESTING": True},
        repository=RunRepository("postgresql://unused", connection_factory=connection_factory),
    )
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert calls == []


def test_ready_checks_the_ledger_dependency() -> None:
    ready_client = create_app({"TESTING": True}, repository=MemoryRepository()).test_client()
    ready = ready_client.get("/ready")
    assert ready.status_code == 200
    assert ready.get_json() == {"status": "ready"}

    class BrokenRepository:
        def list_runs(self) -> list[dict[str, object]]:
            raise RepositoryError("database unavailable")

    broken_client = create_app({"TESTING": True}, repository=BrokenRepository()).test_client()
    not_ready = broken_client.get("/ready")
    assert not_ready.status_code == 503
    assert not_ready.get_json() == {"status": "not_ready", "error": "database unavailable"}


def test_run_endpoints_return_an_array_and_round_trip() -> None:
    repository = MemoryRepository()
    client = create_app({"TESTING": True}, repository=repository).test_client()

    assert client.get("/api/runs").get_json() == []
    invalid = client.post("/api/runs", json={**VALID_PAYLOAD, "execution_target": "host"})
    assert invalid.status_code == 400
    assert repository.runs == []

    created = client.post("/api/runs", json=VALID_PAYLOAD)
    assert created.status_code == 201
    assert created.get_json()["sandbox_name"] == "sbx-test0001"
    listed = client.get("/api/runs")
    assert listed.status_code == 200
    assert listed.get_json()[0] == created.get_json()


class InvestigationMemoryRepository:
    def __init__(self) -> None:
        self.investigations: dict[str, dict[str, object]] = {}

    def create_investigation(self, **values: object) -> dict[str, object]:
        row = {
            **values,
            "status": "queued",
            "result": None,
            "error": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        self.investigations[str(values["investigation_id"])] = row
        return row

    def get_investigation(self, investigation_id: str) -> dict[str, object] | None:
        return self.investigations.get(investigation_id)


def _source_tar_bytes() -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        data = b"print('hello')\n"
        info = tarfile.TarInfo("app.py")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    return output.getvalue()


def test_investigation_endpoint_accepts_source_report_and_manifest(tmp_path) -> None:
    repository = InvestigationMemoryRepository()
    app = create_app(
        {"TESTING": True, "UPLOAD_ROOT": str(tmp_path)},
        repository=repository,
    )
    client = app.test_client()
    response = client.post(
        "/api/investigations",
        data={
            "report": "The upload filename may execute an operating-system command.",
            "manifest": json.dumps(
                {
                    "subject_type": "http_app",
                    "runtime": "python",
                    "start_argv": ["python3", "app.py"],
                    "port": 5000,
                }
            ),
            "source": (io.BytesIO(_source_tar_bytes()), "subject.tar.gz"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 202
    payload = response.get_json()
    assert payload["status"] == "queued"
    assert payload["investigation_id"].startswith("inv-")
    assert len(list(tmp_path.iterdir())) == 1

    detail = client.get(f"/api/investigations/{payload['investigation_id']}")
    assert detail.status_code == 200
    assert detail.get_json()["status"] == "queued"
    assert "source_path" not in detail.get_json()


def test_investigation_endpoint_rejects_missing_source(tmp_path) -> None:
    app = create_app(
        {"TESTING": True, "UPLOAD_ROOT": str(tmp_path)},
        repository=InvestigationMemoryRepository(),
    )
    response = app.test_client().post(
        "/api/investigations",
        data={"report": "missing source", "manifest": "{}"},
    )
    assert response.status_code == 400


def test_sensitive_api_routes_require_configured_api_key(tmp_path) -> None:
    repository = MemoryRepository()
    app = create_app(
        {
            "TESTING": True,
            "UPLOAD_ROOT": str(tmp_path),
            "API_KEY": "test-secret",
            "REQUIRE_API_AUTH": True,
        },
        repository=repository,
    )
    client = app.test_client()

    assert client.get("/api/runs").status_code == 401
    authorized = client.get("/api/runs", headers={"X-Cairn-API-Key": "test-secret"})
    assert authorized.status_code == 200


def test_ready_fails_closed_when_production_auth_is_missing() -> None:
    app = create_app(
        {"TESTING": True, "REQUIRE_API_AUTH": True},
        repository=MemoryRepository(),
    )

    response = app.test_client().get("/ready")

    assert response.status_code == 503
    assert response.get_json() == {
        "status": "not_ready",
        "error": "api authentication is not configured",
    }


def test_ready_rejects_placeholder_production_auth_key() -> None:
    app = create_app(
        {"TESTING": True, "API_KEY": "replace-me", "REQUIRE_API_AUTH": True},
        repository=MemoryRepository(),
    )

    assert app.test_client().get("/ready").status_code == 503


def test_api_rate_limit_returns_retry_after(tmp_path) -> None:
    app = create_app(
        {
            "TESTING": True,
            "UPLOAD_ROOT": str(tmp_path),
            "API_RATE_LIMIT": 1,
            "API_RATE_WINDOW_S": 60,
        },
        repository=MemoryRepository(),
    )
    client = app.test_client()

    assert client.get("/api/runs").status_code == 200
    limited = client.get("/api/runs")
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection
        self.rows: list[tuple[object, ...]] = []
        self.row: tuple[object, ...] | None = None

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[str, ...] | None = None) -> None:
        self.connection.queries.append((query, params))
        if query.lstrip().upper().startswith("SELECT"):
            self.rows = [
                (
                    "seed-demo-1",
                    "sbx-seeddemo1",
                    "seed",
                    "deleted",
                    "succeeded",
                    "celesto_sandbox",
                    datetime(2026, 1, 1, tzinfo=timezone.utc),
                    datetime(2026, 1, 1, tzinfo=timezone.utc),
                )
            ]
        else:
            assert params is not None
            self.row = (
                params[0], params[1], params[2], params[3], None, params[4],
                datetime(2026, 1, 2, tzinfo=timezone.utc),
                datetime(2026, 1, 2, tzinfo=timezone.utc),
            )

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows

    def fetchone(self) -> tuple[object, ...] | None:
        return self.row


class FakeConnection:
    closed = False

    def __init__(self) -> None:
        self.queries: list[tuple[str, tuple[str, ...] | None]] = []
        self.commits = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def test_repository_is_lazy_and_parameterized() -> None:
    connections: list[FakeConnection] = []

    def factory(dsn: str | None) -> FakeConnection:
        assert dsn == "postgresql://test"
        connection = FakeConnection()
        connections.append(connection)
        return connection

    repository = RunRepository("postgresql://test", connection_factory=factory)
    assert connections == []
    runs = repository.list_runs()
    created = repository.create_run(**VALID_PAYLOAD)
    assert len(connections) == 1
    assert runs[0]["sandbox_name"] == "sbx-seeddemo1"
    assert created["run_id"] == "run-test-1"
    query, params = connections[0].queries[1]
    assert "%s" in query
    assert "run-test-1" not in query
    assert params == (
        "run-test-1", "sbx-test0001", "pattern-a-vulnerable-accurate", "created", "celesto_sandbox"
    )
