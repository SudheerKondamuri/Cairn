"""Minimal, lazily connected Postgres repository for ledger runs."""

from __future__ import annotations

import os
import json
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, Callable

try:  # Keep validation and test imports useful before dependencies are installed.
    import psycopg
except ModuleNotFoundError:  # pragma: no cover - exercised only in bare environments.
    psycopg = None  # type: ignore[assignment]


ConnectionFactory = Callable[[str | None], Any]


class RepositoryError(RuntimeError):
    """A database operation could not be completed."""


def _default_connection_factory(dsn: str | None) -> Any:
    if psycopg is None:
        raise RepositoryError("psycopg is not installed")
    return psycopg.connect(dsn) if dsn else psycopg.connect()


class RunRepository:
    """Persist and retrieve runs without opening a connection at import time.

    A connection is created only when the first repository operation is
    invoked.  Supplying ``connection_factory`` keeps the helper straightforward
    to exercise with a fake connection in tests.
    """

    _select_columns = (
        "run_id, sandbox_name, problem_id, state, outcome, execution_target, "
        "created_at, updated_at"
    )
    _investigation_columns = (
        "investigation_id, status, report, manifest, source_path, result, error, "
        "created_at, updated_at"
    )

    def __init__(
        self,
        dsn: str | None = None,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self.dsn = dsn if dsn is not None else os.getenv("DATABASE_URL")
        self._connection_factory = connection_factory or _default_connection_factory
        self._connection: Any | None = None
        self._investigations_schema_ready = False

    def _connection_for_operation(self) -> Any:
        if self._connection is None or bool(getattr(self._connection, "closed", False)):
            try:
                self._connection = self._connection_factory(self.dsn)
            except RepositoryError:
                raise
            except Exception as exc:
                raise RepositoryError("could not connect to database") from exc
        return self._connection

    def list_runs(self) -> list[dict[str, Any]]:
        """Return runs in insertion order."""

        connection = self._connection_for_operation()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT {self._select_columns} FROM runs ORDER BY created_at ASC, run_id ASC"
                )
                rows = cursor.fetchall()
            return [_row_to_dict(row) for row in rows]
        except Exception as exc:
            raise RepositoryError("could not list runs") from exc

    def create_run(
        self,
        *,
        run_id: str,
        sandbox_name: str,
        problem_id: str,
        state: str,
        execution_target: str,
    ) -> dict[str, Any]:
        """Insert one run and return the stored row."""

        connection = self._connection_for_operation()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO runs
                        (run_id, sandbox_name, problem_id, state, execution_target)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING run_id, sandbox_name, problem_id, state, outcome,
                              execution_target, created_at, updated_at
                    """,
                    (run_id, sandbox_name, problem_id, state, execution_target),
                )
                row = cursor.fetchone()
            connection.commit()
            if row is None:
                raise RepositoryError("database did not return the created run")
            return _row_to_dict(row)
        except RepositoryError:
            raise
        except Exception as exc:
            try:
                connection.rollback()
            except Exception:
                pass
            raise RepositoryError("could not create run") from exc

    def close(self) -> None:
        """Close the cached connection, if one was opened."""

        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def create_investigation(
        self,
        *,
        investigation_id: str,
        report: str,
        manifest: Mapping[str, Any],
        source_path: str,
    ) -> dict[str, Any]:
        connection = self._connection_for_operation()
        try:
            self._ensure_investigations_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO investigations
                        (investigation_id, status, report, manifest, source_path)
                    VALUES (%s, 'queued', %s, %s::jsonb, %s)
                    RETURNING investigation_id, status, report, manifest, source_path,
                              result, error, created_at, updated_at
                    """,
                    (investigation_id, report, json.dumps(dict(manifest)), source_path),
                )
                row = cursor.fetchone()
            connection.commit()
            if row is None:
                raise RepositoryError("database did not return the investigation")
            return _investigation_to_dict(row)
        except RepositoryError:
            raise
        except Exception as exc:
            try:
                connection.rollback()
            except Exception:
                pass
            raise RepositoryError("could not create investigation") from exc

    def get_investigation(self, investigation_id: str) -> dict[str, Any] | None:
        connection = self._connection_for_operation()
        try:
            self._ensure_investigations_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT {self._investigation_columns} FROM investigations WHERE investigation_id = %s",
                    (investigation_id,),
                )
                row = cursor.fetchone()
            return None if row is None else _investigation_to_dict(row)
        except Exception as exc:
            raise RepositoryError("could not get investigation") from exc

    def claim_next_investigation(self) -> dict[str, Any] | None:
        connection = self._connection_for_operation()
        try:
            self._ensure_investigations_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._investigation_columns}
                    FROM investigations
                    WHERE status = 'queued'
                    ORDER BY created_at ASC, investigation_id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
                if row is None:
                    connection.commit()
                    return None
                cursor.execute(
                    "UPDATE investigations SET status = 'running', updated_at = now() WHERE investigation_id = %s",
                    (row[0],),
                )
            connection.commit()
            value = _investigation_to_dict(row)
            value["status"] = "running"
            return value
        except Exception as exc:
            try:
                connection.rollback()
            except Exception:
                pass
            raise RepositoryError("could not claim investigation") from exc

    def complete_investigation(self, investigation_id: str, result: Mapping[str, Any]) -> None:
        self._update_investigation(investigation_id, "completed", json.dumps(dict(result)), None)

    def fail_investigation(self, investigation_id: str, error: str) -> None:
        self._update_investigation(investigation_id, "failed", None, error)

    def _update_investigation(
        self,
        investigation_id: str,
        status: str,
        result: str | None,
        error: str | None,
    ) -> None:
        connection = self._connection_for_operation()
        try:
            self._ensure_investigations_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE investigations
                    SET status = %s, result = %s::jsonb, error = %s, updated_at = now()
                    WHERE investigation_id = %s
                    """,
                    (status, result, error, investigation_id),
                )
            connection.commit()
        except Exception as exc:
            try:
                connection.rollback()
            except Exception:
                pass
            raise RepositoryError("could not update investigation") from exc

    def _ensure_investigations_schema(self, connection: Any) -> None:
        if self._investigations_schema_ready:
            return
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS investigations (
                        investigation_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
                        report TEXT NOT NULL,
                        manifest JSONB NOT NULL,
                        source_path TEXT NOT NULL,
                        result JSONB,
                        error TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
            connection.commit()
            self._investigations_schema_ready = True
        except Exception as exc:
            try:
                connection.rollback()
            except Exception:
                pass
            raise RepositoryError("could not initialize investigations table") from exc


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert either a regular tuple row or a mapping row to API data."""

    if isinstance(row, Mapping):
        values = [row[column] for column in RunRepository._select_columns.split(", ")]
    else:
        values = list(row)

    if len(values) != 8:
        raise RepositoryError("unexpected run row shape")

    keys = (
        "run_id",
        "sandbox_name",
        "problem_id",
        "state",
        "outcome",
        "execution_target",
        "created_at",
        "updated_at",
    )
    return {key: _serialize_timestamp(value) for key, value in zip(keys, values, strict=True)}


def _investigation_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        columns = RunRepository._investigation_columns.split(", ")
        values = [row[column] for column in columns]
    else:
        values = list(row)
    if len(values) != 9:
        raise RepositoryError("unexpected investigation row shape")
    keys = (
        "investigation_id",
        "status",
        "report",
        "manifest",
        "source_path",
        "result",
        "error",
        "created_at",
        "updated_at",
    )
    output = {key: _serialize_timestamp(value) for key, value in zip(keys, values, strict=True)}
    for key in ("manifest", "result"):
        if isinstance(output[key], str):
            try:
                output[key] = json.loads(output[key])
            except json.JSONDecodeError:
                pass
    return output


def _serialize_timestamp(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


# A short alias keeps imports pleasant for callers that do not need the class's
# more descriptive name.
Repository = RunRepository
