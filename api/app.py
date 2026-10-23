"""Cairn ledger HTTP API."""

from __future__ import annotations

import os
import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flask import Flask, current_app, request

from core.bundles import BundleValidationError, validate_source_archive

from .investigation_validation import validate_investigation_form
from .repository import RepositoryError, RunRepository
from .security import ApiRequestGuard
from .validation import ValidationError, validate_run_payload


def create_app(
    config: Mapping[str, Any] | None = None,
    repository: RunRepository | Any | None = None,
) -> Flask:
    """Create an API app, optionally with an injected repository."""

    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE_URL=os.getenv("DATABASE_URL"),
        UPLOAD_ROOT=os.getenv("CAIRN_UPLOAD_ROOT", "/var/lib/cairn/uploads"),
        MAX_CONTENT_LENGTH=250 * 1024 * 1024,
        JSON_SORT_KEYS=True,
        API_KEY=os.getenv("CAIRN_API_KEY", ""),
        REQUIRE_API_AUTH=os.getenv("CAIRN_REQUIRE_API_AUTH", "false").lower() == "true",
        API_RATE_LIMIT=int(os.getenv("CAIRN_API_RATE_LIMIT", "60")),
        API_RATE_WINDOW_S=float(os.getenv("CAIRN_API_RATE_WINDOW_S", "60")),
    )
    if config:
        app.config.update(config)

    app.extensions["run_repository"] = (
        repository
        if repository is not None
        else RunRepository(dsn=app.config.get("DATABASE_URL"))
    )
    app.extensions["api_guard"] = ApiRequestGuard(
        api_key=str(app.config["API_KEY"]),
        require_auth=bool(app.config["REQUIRE_API_AUTH"] or app.config["API_KEY"]),
        rate_limit=int(app.config["API_RATE_LIMIT"]),
        window_s=float(app.config["API_RATE_WINDOW_S"]),
    )

    @app.before_request
    def protect_api() -> tuple[dict[str, str], int] | tuple[dict[str, str], int, dict[str, str]] | None:
        if not request.path.startswith("/api/"):
            return None
        guard: ApiRequestGuard = app.extensions["api_guard"]
        supplied = request.headers.get("X-Cairn-API-Key")
        if not supplied:
            authorization = request.headers.get("Authorization", "")
            if authorization.startswith("Bearer "):
                supplied = authorization[7:].strip()
        message, status, retry_after = guard.check(
            client_id=request.remote_addr or "unknown",
            supplied_key=supplied,
        )
        if status == 200:
            return None
        if retry_after is not None:
            return {"error": message}, status, {"Retry-After": str(retry_after)}
        return {"error": message}, status

    @app.get("/health")
    def health() -> tuple[dict[str, str], int]:
        # Health is intentionally process-level and does not force a lazy DB
        # connection. Database readiness is reported by /ready.
        return {"status": "ok"}, 200

    @app.get("/ready")
    def ready() -> tuple[dict[str, str], int]:
        """Report whether the API can reach its ledger dependency."""

        guard: ApiRequestGuard = app.extensions["api_guard"]
        if guard.configuration_error:
            return {"status": "not_ready", "error": "api authentication is not configured"}, 503
        try:
            _repository().list_runs()
        except RepositoryError:
            app.logger.exception("ledger is not ready")
            return {"status": "not_ready", "error": "database unavailable"}, 503
        return {"status": "ready"}, 200

    @app.get("/api/runs")
    def list_runs() -> tuple[list[dict[str, Any]], int]:
        try:
            runs = _repository().list_runs()
        except RepositoryError:
            app.logger.exception("unable to list ledger runs")
            return [{"error": "database unavailable"}], 503
        return runs, 200

    @app.post("/api/runs")
    def create_run() -> tuple[dict[str, Any], int]:
        if not request.is_json:
            return {"error": "request body must be JSON"}, 400

        payload = request.get_json(silent=True)
        try:
            values = validate_run_payload(payload)
        except ValidationError as exc:
            return {"error": "invalid request", **exc.as_dict()}, 400

        try:
            run = _repository().create_run(**values)
        except RepositoryError:
            app.logger.exception("unable to create ledger run")
            return {"error": "database unavailable"}, 503
        return run, 201

    @app.post("/api/investigations")
    def create_investigation() -> tuple[dict[str, Any], int]:
        source = request.files.get("source")
        if source is None:
            return {"error": "invalid request", "field": "source", "message": "file is required"}, 400
        try:
            spec = validate_investigation_form(
                request.form.get("report"),
                request.form.get("manifest"),
            )
        except ValueError as exc:
            return {"error": "invalid request", "field": "manifest", "message": str(exc)}, 400

        investigation_id = f"inv-{secrets.token_hex(12)}"
        upload_root = Path(app.config["UPLOAD_ROOT"])
        upload_root.mkdir(parents=True, exist_ok=True)
        temporary = upload_root / f".{investigation_id}.upload"
        final_path = upload_root / f"{investigation_id}.tar.gz"
        try:
            source.save(temporary)
            validate_source_archive(temporary)
            temporary.replace(final_path)
            _repository().create_investigation(
                investigation_id=investigation_id,
                report=spec.report,
                manifest=spec.as_dict(),
                source_path=final_path.name,
            )
        except BundleValidationError as exc:
            temporary.unlink(missing_ok=True)
            return {"error": "invalid source archive", "message": str(exc)}, 400
        except RepositoryError:
            temporary.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
            app.logger.exception("unable to queue investigation")
            return {"error": "database unavailable"}, 503
        except OSError:
            temporary.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
            app.logger.exception("unable to store investigation source")
            return {"error": "source storage unavailable"}, 503
        return {"investigation_id": investigation_id, "status": "queued"}, 202

    @app.get("/api/investigations/<investigation_id>")
    def get_investigation(investigation_id: str) -> tuple[dict[str, Any], int]:
        try:
            investigation = _repository().get_investigation(investigation_id)
        except RepositoryError:
            app.logger.exception("unable to get investigation")
            return {"error": "database unavailable"}, 503
        if investigation is None:
            return {"error": "not found"}, 404
        public = {key: value for key, value in investigation.items() if key != "source_path"}
        return public, 200

    return app


def _repository() -> RunRepository | Any:
    return current_app.extensions["run_repository"]


app = create_app()


if __name__ == "__main__":  # pragma: no cover - used by the container.
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", "8080")),
    )
