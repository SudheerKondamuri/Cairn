#!/usr/bin/env python3
"""Return whether the control-plane marker directory contains a file."""

from __future__ import annotations

import pathlib


MARKERS = pathlib.Path("/tmp/cairn-markers")


def main() -> int:
    if not MARKERS.is_dir():
        print("false")
        return 0
    print(
        "true"
        if any(child.is_file() and not child.is_symlink() for child in MARKERS.iterdir())
        else "false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
