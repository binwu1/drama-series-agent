# -*- coding: utf-8 -*-
"""projects/_hermes_sessions.json — 1 conversation ↔ 1 series."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.agent.chat_store import append_message
from drama_series_agent.agent.paths import sessions_index_path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_index(drama_series_root: Path) -> dict[str, Any]:
    path = sessions_index_path(drama_series_root)
    if not path.is_file():
        return {"conversations": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"conversations": []}
    if not isinstance(data, dict):
        return {"conversations": []}
    data.setdefault("conversations", [])
    return data


def _save_index(drama_series_root: Path, data: dict[str, Any]) -> None:
    path = sessions_index_path(drama_series_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def create_conversation(
    *,
    title: str,
    drama_series_root: Path,
    premise: Optional[str] = None,
) -> dict[str, Any]:
    from drama_series_agent.drama.runtime import load_runtime, save_runtime
    from drama_series_agent.intake.scaffold import scaffold_project

    drama_series_root = Path(drama_series_root)
    title = (title or "").strip() or "未命名系列"
    sc = scaffold_project(title=title, drama_series_root=drama_series_root)
    project_dir = Path(sc["project_dir"])
    cid = f"conv_{uuid.uuid4().hex[:12]}"
    rt = load_runtime(project_dir)
    rt.conversation_id = cid
    try:
        from drama_series_agent.adapters.config import config_manager

        video = config_manager.get_comfyui_config().get("video") or {}
        if video.get("default_workflow"):
            rt.default_workflow = video["default_workflow"]
        if video.get("aspect"):
            rt.aspect = video["aspect"]
    except Exception:  # noqa: BLE001
        pass
    save_runtime(project_dir, rt)

    row = {
        "conversation_id": cid,
        "series_id": sc["project_id"],
        "project_dir": str(project_dir),
        "title": title,
        "updated_at": _now(),
    }
    index = _load_index(drama_series_root)
    index["conversations"] = [
        c
        for c in index.get("conversations") or []
        if c.get("conversation_id") != cid
    ]
    index["conversations"].append(row)
    _save_index(drama_series_root, index)

    welcome = (
        f"欢迎使用 Hermes。本会话绑定系列「{title}」。"
        "直接说你想做什么（例如生成文学、验收角色、出 EP001）。"
    )
    if premise and premise.strip():
        welcome += f"\n\n已记录梗概：{premise.strip()}"
    append_message(project_dir, role="assistant", content=welcome)
    return row


def list_conversations(*, drama_series_root: Optional[Path] = None) -> list[dict[str, Any]]:
    from drama_series_agent.agent.paths import default_workspace_root

    root = Path(drama_series_root) if drama_series_root is not None else default_workspace_root()
    index = _load_index(root)
    rows = list(index.get("conversations") or [])
    rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    return rows


def get_conversation(
    conversation_id: str, *, drama_series_root: Optional[Path] = None
) -> Optional[dict[str, Any]]:
    from drama_series_agent.agent.paths import default_workspace_root

    root = Path(drama_series_root) if drama_series_root is not None else default_workspace_root()
    for row in list_conversations(drama_series_root=root):
        if row.get("conversation_id") == conversation_id:
            return row
    return None
