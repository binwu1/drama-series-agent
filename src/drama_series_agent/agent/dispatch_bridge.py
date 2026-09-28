# -*- coding: utf-8 -*-
"""Route tool calls to hermes_intake or hermes_drama dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def run_tool(name: str, args: dict[str, Any] | None, *, project_dir: Path) -> str:
    args = dict(args or {})
    # Model often sends the series title; always bind the conversation project.
    args["project_dir"] = str(project_dir)

    from drama_series_agent.drama.dispatch import handle_tool_call as drama_call
    from drama_series_agent.intake.dispatch import handle_tool_call as intake_call

    out = drama_call(name, args)
    try:
        data = json.loads(out)
    except Exception:  # noqa: BLE001
        return out
    err = str(data.get("error") or "")
    if data.get("ok") is False and (
        "unknown" in err.lower() or data.get("tool") == name and "unknown hermes_drama" in err
    ):
        out = intake_call(name, args)
    return out
