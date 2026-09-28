# -*- coding: utf-8 -*-
"""Workspace paths for workflows + cast data."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def workspace_root(explicit: Optional[Path] = None) -> Path:
    if explicit is not None:
        return Path(explicit).resolve()
    env = os.environ.get("DRAMA_SERIES_ROOT")
    if env:
        return Path(env).resolve()
    # src/drama_series_agent/adapters/paths.py → parents[3] = repo root
    return Path(__file__).resolve().parents[3]


def get_resource_path(resource_type: str, *paths: str) -> str:
    """Resolve workflows/… under the repo (or DRAMA_SERIES_ROOT)."""
    root = workspace_root()
    p = root / resource_type
    for part in paths:
        p = p / part
    return str(p.resolve())


def get_data_path(*paths: str) -> str:
    """Resolve data/… (cast library lives under data/cast/{series})."""
    root = workspace_root()
    p = root / "data"
    for part in paths:
        p = p / part
    return str(p.resolve())
