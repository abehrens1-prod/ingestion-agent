"""Console compatibility helpers."""

import sys


def enable_utf8() -> None:
    """Use UTF-8 for status glyphs on native Windows consoles."""
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
