#!/usr/bin/env python3
"""Compatibility wrapper for the packaged harness_logic CLI."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness_logic.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
