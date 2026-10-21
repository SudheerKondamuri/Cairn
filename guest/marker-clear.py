#!/usr/bin/env python3
from __future__ import annotations

import pathlib

MARKERS = pathlib.Path("/tmp/cairn-markers")
MARKERS.mkdir(parents=True, exist_ok=True)
for child in MARKERS.iterdir():
    if child.is_file() or child.is_symlink():
        child.unlink()
    elif child.is_dir():
        import shutil

        shutil.rmtree(child)
