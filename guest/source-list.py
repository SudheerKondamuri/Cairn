#!/usr/bin/env python3
"""List regular files beneath /input/source."""

from __future__ import annotations

import base64
import json
import pathlib
import sys


ROOT = pathlib.Path("/input/source").resolve()


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    try:
        subpath = base64.urlsafe_b64decode(sys.argv[1].encode("ascii")).decode("utf-8")
        base = (ROOT / subpath).resolve()
        base.relative_to(ROOT)
        entries = []
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.is_symlink():
                path.relative_to(ROOT)
                entries.append(str(path.relative_to(ROOT)))
                if len(entries) >= 200:
                    break
        print(json.dumps(entries))
        return 0
    except (OSError, UnicodeError, ValueError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
