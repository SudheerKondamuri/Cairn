#!/usr/bin/env python3
"""Read a bounded source range under /input/source."""

from __future__ import annotations

import base64
import hashlib
import pathlib
import sys


ROOT = pathlib.Path("/input/source").resolve()


def decode(value: str) -> str:
    return base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")


def contained(relative: str) -> pathlib.Path:
    original = ROOT / relative
    if any(part.is_symlink() for part in [original, *original.parents] if part.exists()):
        raise ValueError("source symlinks are not allowed")
    candidate = original.resolve()
    candidate.relative_to(ROOT)
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("source file is not a regular file")
    return candidate


def main() -> int:
    if len(sys.argv) != 4:
        return 2
    try:
        path = contained(decode(sys.argv[1]))
        start = int(decode(sys.argv[2]))
        end = int(decode(sys.argv[3]))
        if start < 1 or end < start or end - start + 1 > 200:
            raise ValueError("invalid line range")
        data = path.read_bytes()
        if len(data) > 1_048_576 or b"\x00" in data:
            raise ValueError("source file is binary or oversized")
        lines = data.decode("utf-8").splitlines()
        print("\n".join(lines[start - 1 : end]))
        print(f"\n# source_sha256={hashlib.sha256(data).hexdigest()}")
        return 0
    except (OSError, UnicodeError, ValueError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
