# -*- coding: utf-8 -*-
"""Hermes projects/{slug} scaffold with mounts to short-drama + HostApp trees."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.intake.constants import (
    CONTRACT_VERSION,
    DEFAULT_ASPECT,
    DEFAULT_LANGUAGE,
    DEFAULT_PRODUCTION_PROFILE,
    STAGE_EXIT_GATE,
    STAGE_ID,
)


def slugify(title: str) -> str:
    s = (title or "").strip()
    s = re.sub(r"[\\/:*?\"<>|]+", "-", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or "untitled"


def default_workspace_root() -> Path:
    import os

    env = os.environ.get("DRAMA_SERIES_ROOT")
    if env:
        return Path(env).resolve()
    # src/drama_series_agent/intake/scaffold.py → parents[3] = repo root
    return Path(__file__).resolve().parents[3]


def scaffold_project(
    *,
    title: str,
    projects_root: Optional[Path] = None,
    drama_series_root: Optional[Path] = None,
    slug: Optional[str] = None,
    language: str = DEFAULT_LANGUAGE,
    aspect: str = DEFAULT_ASPECT,
    production_profile: str = DEFAULT_PRODUCTION_PROFILE,
    goal: str = "full_pipeline",
) -> dict[str, Any]:
    """Create Hermes project truth tree + mount targets (no symlinks required).

    Layout:
      projects/{slug}/
        project.json
        intake_manifest.json   (stub until filled)
        handoff_stage2.json    (stub)
        输入/
        memory/PROJECT.md
        .short-drama/state.json
        short-drama.json
      + ensures:
        dramas/{slug}/
        templates/{slug}/
        data/cast/{slug}/voices/unassigned/
    """
    drama_series_root = (drama_series_root or default_workspace_root()).resolve()
    projects_root = (projects_root or (drama_series_root / "projects")).resolve()
    sid = slug or slugify(title)
    project_dir = projects_root / sid

    dramas_dir = drama_series_root / "dramas" / sid
    templates_dir = drama_series_root / "templates" / sid
    cast_dir = drama_series_root / "data" / "cast" / sid
    input_dir = project_dir / "输入"
    memory_dir = project_dir / "memory"
    unassigned = cast_dir / "unassigned"
    voices = cast_dir / "voices"

    for d in (
        project_dir,
        input_dir,
        memory_dir,
        project_dir / ".short-drama",
        dramas_dir / "episodes",
        templates_dir / "run",
        templates_dir / "剧集",
        templates_dir / "assets",
        templates_dir / "continuity",
        cast_dir,
        voices,
        unassigned,
    ):
        d.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    mounts = {
        "dramas_dir": str(dramas_dir),
        "templates_dir": str(templates_dir),
        "cast_dir": str(cast_dir),
        "input_dir": str(input_dir),
        "drama_series_root": str(drama_series_root),
    }

    project = {
        "contract_version": CONTRACT_VERSION,
        "stage": STAGE_ID,
        "exit_gate": STAGE_EXIT_GATE,
        "project_id": sid,
        "title": title,
        "slug": sid,
        "created_at": now,
        "updated_at": now,
        "language": language,
        "aspect": aspect,
        "production_profile": production_profile,
        "goal": goal,
        "mounts": mounts,
        "authority": {
            "title": title,
            "language": language,
            "aspect": aspect,
            "production_profile": {
                "status": "accepted" if production_profile else "unset",
                "value": production_profile or None,
            },
        },
    }
    _write_json(project_dir / "project.json", project)

    short_drama = {
        "title": title,
        "language": language,
        "aspect": aspect,
        "hermes_project_id": sid,
        "hermes_project_dir": str(project_dir),
        "creator_authority": {
            "visual_direction": {"status": "unset"},
            "production_profile": {
                "status": "accepted",
                "value": production_profile,
            },
        },
    }
    _write_json(project_dir / "short-drama.json", short_drama)

    state = {
        "stage": "intake",
        "stage_id": STAGE_ID,
        "exit_gate": STAGE_EXIT_GATE,
        "updated_at": now,
        "case_code": None,
        "ready_for_stage2": False,
    }
    _write_json(project_dir / ".short-drama" / "state.json", state)

    # Cast stubs
    manifest_path = cast_dir / "series_manifest.json"
    if not manifest_path.is_file():
        _write_json(manifest_path, {})
    style_path = cast_dir / "series_style.json"
    if not style_path.is_file():
        _write_json(
            style_path,
            {
                "style": "unset",
                "notes": "Set after creator accepts visual_direction",
            },
        )
    voices_readme = voices / "README.md"
    if not voices_readme.is_file():
        voices_readme.write_text(
            "# Voices\n\nPlace 2–15s clean character wavs as `{角色}.wav`.\n"
            "Status is tracked in Hermes `intake_manifest.json`.\n",
            encoding="utf-8",
        )

    memory_path = memory_dir / "PROJECT.md"
    if not memory_path.is_file():
        memory_path.write_text(
            f"# Project memory — {title}\n\n"
            f"- project_id: `{sid}`\n"
            f"- stage: `{STAGE_ID}`\n"
            f"- exit_gate: `{STAGE_EXIT_GATE}`\n"
            f"- mounts: dramas / templates / cast (see project.json)\n\n"
            "## Stable facts\n\n"
            "(Agent appends only filesystem-verified facts.)\n",
            encoding="utf-8",
        )

    # Stub intake + handoff so paths always exist
    intake_stub = {
        "contract_version": CONTRACT_VERSION,
        "project_id": sid,
        "stage": STAGE_ID,
        "script": {"status": "missing", "files": []},
        "images": {"status": "missing", "files": []},
        "audio": {"status": "missing", "files": []},
        "case_code": None,
        "gaps": [],
        "updated_at": now,
    }
    intake_path = project_dir / "intake_manifest.json"
    if not intake_path.is_file():
        _write_json(intake_path, intake_stub)

    handoff_path = project_dir / "handoff_stage2.json"
    if not handoff_path.is_file():
        _write_json(
            handoff_path,
            {
                "ready": False,
                "project_id": sid,
                "reason": "intake_incomplete",
            },
        )

    # Series Agent L1 runtime (S1–S7 state machine)
    runtime_path = project_dir / "series_runtime.json"
    if not runtime_path.is_file():
        try:
            from drama_series_agent.drama.runtime import (
                default_runtime,
                save_runtime,
            )

            save_runtime(project_dir, default_runtime(sid))
        except Exception:  # noqa: BLE001 — intake must work without drama pkg
            _write_json(
                runtime_path,
                {
                    "contract_version": "1.0.0",
                    "series_id": sid,
                    "stage": "s1_intake",
                    "next_episode": "EP001",
                    "updated_at": now,
                },
            )

    return {
        "project_dir": str(project_dir),
        "project_id": sid,
        "mounts": mounts,
        "project": project,
    }


def load_project(project_dir: Path) -> dict[str, Any]:
    path = Path(project_dir) / "project.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
