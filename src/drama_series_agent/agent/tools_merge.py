# -*- coding: utf-8 -*-
"""Merge intake + drama OpenAI-style tool schemas."""

from __future__ import annotations

from typing import Any


def merged_tool_schemas() -> list[dict[str, Any]]:
    from drama_series_agent.drama.tool_schemas import tool_schemas_all
    from drama_series_agent.intake.tool_schemas import tool_schemas as intake_schemas

    schemas: list[dict[str, Any]] = []
    schemas.extend(intake_schemas())
    schemas.extend(tool_schemas_all())

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in schemas:
        fn = (item.get("function") or {}) if isinstance(item, dict) else {}
        name = fn.get("name") or ""
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(item)
    return out
