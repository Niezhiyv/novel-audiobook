from __future__ import annotations

import sys
from pathlib import Path


def application_root() -> Path:
    """Return the directory that owns external models and project data."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]
