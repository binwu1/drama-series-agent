# -*- coding: utf-8 -*-
"""Append-only Accept decisions under projects/{series}/decisions/."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.intake.fs_util import file_sha256


def decisions_dir(project_dir: Path) -> Path:
    d = Path(project_dir) / "decisions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def decisions_jsonl(project_dir: Path) -> Path:
    return decisions_dir(project_dir) / "accept.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_decision(
    project_dir: Path,
    *,
    decision_kind: str,
    status: str,
    series_id: str,
    artifact: Optional[str] = None,
    character: Optional[str] = None,
    episode_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    target_hashes: Optional[dict[str, str]] = None,
    decided_by: str = "creator",
    decision_id: Optional[str] = None,
    supersedes_decision_id: Optional[str] = None,
) -> dict[str, Any]:
    """Write one Accept/Reject row (JSONL). Returns the decision dict."""
    row = {
        "decision_id": decision_id or f"CD-{uuid.uuid4().hex[:10].upper()}",
        "decision_kind": decision_kind,
        "artifact": artifact,
        "character": character,
        "episode_id": episode_id,
        "shot_id": shot_id,
        "status": status,
        "target_hashes": target_hashes or {},
        "decided_by": decided_by,
        "decided_at": _now(),
        "series_id": series_id,
        "supersedes_decision_id": supersedes_decision_id,
    }
    path = decisions_jsonl(project_dir)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def hash_paths(rel_to_abs: dict[str, Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel, abs_path in rel_to_abs.items():
        p = Path(abs_path)
        if p.is_file():
            out[rel] = file_sha256(p)
    return out


def list_decisions(project_dir: Path) -> list[dict[str, Any]]:
    path = decisions_jsonl(project_dir)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows
