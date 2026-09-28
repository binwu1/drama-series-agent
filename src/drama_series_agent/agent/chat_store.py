# -*- coding: utf-8 -*-
"""Append/load projects/{slug}/memory/chat.jsonl."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_message(
    project_dir: Path,
    *,
    role: str,
    content: str,
    tool_name: Optional[str] = None,
    ui_hints: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    project_dir = Path(project_dir)
    path = project_dir / "memory" / "chat.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "role": role,
        "content": content,
        "ts": _now(),
        "tool_name": tool_name,
        "ui_hints": ui_hints or {},
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def load_messages(
    project_dir: Path, *, limit: Optional[int] = None
) -> list[dict[str, Any]]:
    path = Path(project_dir) / "memory" / "chat.jsonl"
    if not path.is_file():
        return []
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if limit is not None and limit > 0:
        return rows[-limit:]
    return rows
