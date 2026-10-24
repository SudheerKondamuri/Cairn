#!/usr/bin/env python3
"""Process queued Cairn investigations from the Postgres ledger."""

from __future__ import annotations

import argparse
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from runner import ROOT, load_env
from investigate import run_investigation

from core.bundles import extract_source_archive
from core.investigation import InvestigationSpec
from api.repository import RunRepository


def process_once(
    repository: RunRepository,
    *,
    upload_root: Path = ROOT / ".cairn/uploads",
    output_dir: Path = ROOT / "reports/investigations",
) -> bool:
    job = repository.claim_next_investigation()
    if job is None:
        return False
    source_path = Path(str(job["source_path"]))
    if source_path.name != str(source_path):
        repository.fail_investigation(str(job["investigation_id"]), "invalid source path")
        return True
    archive = (upload_root / source_path.name).resolve()
    try:
        archive.relative_to(upload_root.resolve())
        spec = InvestigationSpec.from_mapping(job["manifest"])
        with tempfile.TemporaryDirectory(prefix="cairn-worker-") as temporary:
            source_root = extract_source_archive(archive, Path(temporary))
            report = run_investigation(
                spec,
                source_root,
                investigation_id=str(job["investigation_id"]),
                output_dir=output_dir,
            )
        repository.complete_investigation(str(job["investigation_id"]), report)
    except Exception as exc:
        repository.fail_investigation(
            str(job["investigation_id"]),
            f"{type(exc).__name__}: {exc}",
        )
    finally:
        archive.unlink(missing_ok=True)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="process at most one queued job")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--upload-root", type=Path, default=ROOT / ".cairn/uploads")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/investigations")
    args = parser.parse_args(argv)
    load_env()
    repository = RunRepository()
    return run_worker(
        repository,
        upload_root=args.upload_root,
        output_dir=args.output_dir,
        once=args.once,
        poll_seconds=args.poll_seconds,
    )


def run_worker(
    repository: RunRepository,
    *,
    upload_root: Path,
    output_dir: Path,
    once: bool = False,
    poll_seconds: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Keep polling so jobs submitted after startup are not stranded."""

    while True:
        processed = process_once(
            repository, upload_root=upload_root, output_dir=output_dir
        )
        if once:
            return 0
        if not processed:
            sleep(max(poll_seconds, 0.1))


if __name__ == "__main__":
    raise SystemExit(main())
