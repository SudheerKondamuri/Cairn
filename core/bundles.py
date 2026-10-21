"""Safe source-bundle inspection for dynamic investigations."""

from __future__ import annotations

import os
import hashlib
import tarfile
from pathlib import Path, PurePosixPath
from typing import Iterable


class BundleValidationError(ValueError):
    """Raised when a source bundle cannot be safely inspected or uploaded."""


MAX_SOURCE_BYTES = 250 * 1024 * 1024
MAX_SOURCE_FILES = 10_000


def collect_source_files(root: str | os.PathLike[str]) -> list[tuple[Path, str]]:
    """Return regular files and relative POSIX names from a source directory."""

    base = Path(root).resolve()
    if not base.is_dir():
        raise BundleValidationError("source path must be a directory")
    files: list[tuple[Path, str]] = []
    total_bytes = 0
    for path in sorted(base.rglob("*")):
        if path.is_symlink():
            raise BundleValidationError(f"source symlink is not allowed: {path.relative_to(base)}")
        if not path.is_file():
            continue
        relative = path.relative_to(base).as_posix()
        # Generated Python caches are not source evidence. Excluding them keeps
        # the bundle small and prevents the agent from spending tool calls
        # inspecting opaque bytecode instead of the submitted source.
        parts = Path(relative).parts
        if "__pycache__" in parts or path.suffix == ".pyc":
            continue
        size = path.stat().st_size
        total_bytes += size
        files.append((path, relative))
        if len(files) > MAX_SOURCE_FILES:
            raise BundleValidationError("source bundle contains too many files")
        if total_bytes > MAX_SOURCE_BYTES:
            raise BundleValidationError("source bundle exceeds the size limit")
    if not files:
        raise BundleValidationError("source bundle contains no regular files")
    return files


def source_digest(files: Iterable[tuple[Path, str]]) -> str:
    """Hash relative names and bytes in stable order for report identity."""

    digest = hashlib.sha256()
    for path, relative in sorted(files, key=lambda item: item[1]):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
        digest.update(b"\x00")
    return digest.hexdigest()


def validate_source_archive(path: str | os.PathLike[str]) -> list[tarfile.TarInfo]:
    """Validate a tar archive without extracting or executing its contents."""

    archive = Path(path)
    if not archive.is_file() or not tarfile.is_tarfile(archive):
        raise BundleValidationError("source archive must be a readable tar file")

    try:
        with tarfile.open(archive, "r:*") as stream:
            members = stream.getmembers()
    except (OSError, tarfile.TarError) as exc:
        raise BundleValidationError("source archive cannot be read") from exc

    if not members:
        raise BundleValidationError("source archive is empty")
    if len(members) > MAX_SOURCE_FILES:
        raise BundleValidationError("source archive contains too many members")

    total_bytes = 0
    for member in members:
        _validate_member(member)
        if member.isfile():
            total_bytes += member.size
            if total_bytes > MAX_SOURCE_BYTES:
                raise BundleValidationError("source archive exceeds the size limit")
    return members


def extract_source_archive(
    archive: str | os.PathLike[str], destination: str | os.PathLike[str]
) -> Path:
    """Validate and extract a safe tar archive into a fresh directory."""

    members = validate_source_archive(archive)
    target = Path(destination).resolve()
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:*") as stream:
        stream.extractall(target, members=members)
    return target


def _validate_member(member: tarfile.TarInfo) -> None:
    name = member.name.replace("\\", "/")
    parts = PurePosixPath(name).parts
    if not name or name.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise BundleValidationError(f"archive member has an unsafe path: {member.name!r}")
    if member.issym() or member.islnk():
        raise BundleValidationError(f"archive links are not allowed: {member.name!r}")
    if not (member.isdir() or member.isfile()):
        raise BundleValidationError(f"archive member is not a regular file or directory: {member.name!r}")
