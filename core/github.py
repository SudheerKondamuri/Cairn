"""Safe, control-plane GitHub source acquisition for dynamic investigations."""

from __future__ import annotations

import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class GitHubSourceError(ValueError):
    """Raised when a GitHub source URL or archive cannot be safely acquired."""


MAX_ARCHIVE_BYTES = 250 * 1024 * 1024
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")


def repository_parts(repository_url: str) -> tuple[str, str]:
    """Return the owner/repository pair from a canonical GitHub URL."""

    if not isinstance(repository_url, str) or not repository_url:
        raise GitHubSourceError("github_url must be a non-empty string")
    parsed = urllib.parse.urlsplit(repository_url)
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise GitHubSourceError("github_url must use https://github.com")
    if parsed.query or parsed.fragment:
        raise GitHubSourceError("github_url must not contain a query or fragment")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise GitHubSourceError("github_url must identify exactly one repository")
    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not _NAME.fullmatch(owner) or not _NAME.fullmatch(repository):
        raise GitHubSourceError("github_url contains an invalid owner or repository")
    return owner, repository


def archive_url(repository_url: str, ref: str = "main") -> str:
    """Build a GitHub archive URL without allowing an arbitrary download host."""

    owner, repository = repository_parts(repository_url)
    if not isinstance(ref, str) or not ref or "\x00" in ref or ref.startswith("/"):
        raise GitHubSourceError("github_ref must be a non-empty relative ref")
    if any(part in {"", ".", ".."} for part in ref.replace("\\", "/").split("/")):
        raise GitHubSourceError("github_ref contains an unsafe path component")
    encoded_ref = urllib.parse.quote(ref, safe="/")
    return f"https://github.com/{owner}/{repository}/archive/{encoded_ref}.tar.gz"


def download_archive(
    repository_url: str,
    destination: str | Path | None = None,
    *,
    ref: str = "main",
    timeout_s: float = 30.0,
) -> Path:
    """Download one GitHub source archive in the trusted control plane.

    The guest never receives the URL and never needs outbound networking. The
    caller still validates the resulting archive before extraction.
    """

    url = archive_url(repository_url, ref=ref)
    if destination is None:
        handle, raw_path = tempfile.mkstemp(prefix="cairn-github-", suffix=".tar.gz")
        Path(raw_path).unlink(missing_ok=True)
        destination = raw_path
        import os

        os.close(handle)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "cairn-source-fetch/1.0", "Accept": "application/gzip"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response, target.open("wb") as stream:
            length = response.headers.get("Content-Length")
            if length is not None and int(length) > MAX_ARCHIVE_BYTES:
                raise GitHubSourceError("GitHub archive exceeds the source size limit")
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise GitHubSourceError("GitHub archive exceeds the source size limit")
                stream.write(chunk)
    except GitHubSourceError:
        target.unlink(missing_ok=True)
        raise
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
        target.unlink(missing_ok=True)
        raise GitHubSourceError(f"GitHub archive download failed: {type(exc).__name__}") from exc
    return target
