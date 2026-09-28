# -*- coding: utf-8 -*-
"""Resolve workspace / projects paths for Drama Series Agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def default_workspace_root() -> Path:
    env = os.environ.get("DRAMA_SERIES_ROOT")
    if env:
        return Path(env).resolve()
    # src/drama_series_agent/agent/paths.py → parents[3] = repo root
    return Path(__file__).resolve().parents[3]


def projects_root(drama_series_root: Optional[Path] = None) -> Path:
    root = Path(drama_series_root) if drama_series_root is not None else default_workspace_root()
    return root / "projects"


def sessions_index_path(drama_series_root: Optional[Path] = None) -> Path:
    return projects_root(drama_series_root) / "_series_sessions.json"
