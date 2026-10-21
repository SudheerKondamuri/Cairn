#!/usr/bin/env python3
from __future__ import annotations

import base64
import pathlib
import re
import sys


TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
MARKERS = pathlib.Path("/tmp/cairn-markers")


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    token = base64.urlsafe_b64decode(sys.argv[1].encode("ascii")).decode("utf-8")
    if not TOKEN.fullmatch(token):
        return 2
    print("true" if (MARKERS / token).is_file() else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
