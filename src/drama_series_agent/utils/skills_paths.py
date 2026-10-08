# -*- coding: utf-8 -*-
"""Resolve repo-local agent skills under skills/ (canonical)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# Canonical skill folder names in this repo
SKILL_INTAKE = "drama-intake"
SKILL_DEVELOP = "drama-series-develop"
SKILL_LITERARY = "0xsline-short-drama"
SKILL_H3_R2V = "drama-series-h3-r2v-prompts"


def repo_root() -> Path:
    """drama-series-agent repository root (parent of src/)."""
    here = Path(__file__).resolve()
    # utils/ -> drama_series_agent/ -> src/ -> repo
    return here.parents[3]


def skills_dir() -> Path:
    """Canonical skills root: repo ``skills/``."""
    return repo_root() / "skills"


def skill_root(name: str) -> Optional[Path]:
    """Return skill directory if SKILL.md exists.

    Search order:
    1. ``skills/{name}`` (canonical, open-source layout)
    2. ``.cursor/skills/{name}`` (legacy Cursor-local path)
    """
    candidates = [
        skills_dir() / name,
        repo_root() / ".cursor" / "skills" / name,
    ]
    for path in candidates:
        if (path / "SKILL.md").is_file():
            return path
    return None


def require_skill(name: str) -> Path:
    path = skill_root(name)
    if path is None:
        raise FileNotFoundError(
            f"missing skill {name!r}; expected under {skills_dir() / name}"
        )
    return path
