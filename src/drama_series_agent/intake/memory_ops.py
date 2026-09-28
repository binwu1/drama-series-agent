# -*- coding: utf-8 -*-
"""Memory helpers for Stage1 (L0/L1 project facts)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def memory_upsert_project(
    project_dir: Path,
    facts: list[str],
    *,
    hermes_memory_md: Optional[Path] = None,
) -> dict[str, Any]:
    """Append filesystem-verified facts to projects/{slug}/memory/PROJECT.md.

    Optionally mirror a one-line pointer into Hermes MEMORY.md (L0) if path given.
    Does not write plot guesses.
    """
    project_dir = Path(project_dir)
    mem = project_dir / "memory" / "PROJECT.md"
    mem.parent.mkdir(parents=True, exist_ok=True)
    if not mem.is_file():
        mem.write_text("# Project memory\n\n## Stable facts\n\n", encoding="utf-8")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = []
    existing = mem.read_text(encoding="utf-8")
    for fact in facts:
        fact = fact.strip()
        if not fact:
            continue
        bullet = f"- ({stamp}) {fact}"
        if fact in existing or bullet in existing:
            continue
        lines.append(bullet)

    if lines:
        with mem.open("a", encoding="utf-8") as f:
            if not existing.endswith("\n"):
                f.write("\n")
            f.write("\n".join(lines) + "\n")

    mirrored = False
    if hermes_memory_md is not None and lines:
        hm = Path(hermes_memory_md)
        hm.parent.mkdir(parents=True, exist_ok=True)
        pointer = (
            f"- ({stamp}) drama series project "
            f"`{project_dir.name}` facts updated — see `{mem}`.\n"
        )
        prev = hm.read_text(encoding="utf-8") if hm.is_file() else "# MEMORY\n\n"
        if str(mem) not in prev[-2000:]:
            with hm.open("a", encoding="utf-8") as f:
                if not prev.endswith("\n"):
                    f.write("\n")
                f.write(pointer)
            mirrored = True

    return {
        "project_memory": str(mem),
        "appended": lines,
        "hermes_memory_mirrored": mirrored,
    }


def ask_slots(missing: list[str], *, max_ask: int = 3) -> dict[str, Any]:
    """Structured Stage1 questions — agent presents these; does not invent answers."""
    catalog = {
        "title": "剧名（或工作标题）是什么？",
        "has_script": "是否已有剧本/大纲/小说原文？路径？",
        "has_images": "是否已有角色定妆/锚点图？路径与角色名？",
        "has_audio": "是否已有角色参考音色（2–15s 干声）？",
        "goal": "目标是只写剧本，还是要一路做到 H3 成片？",
        "aspect": "画幅？（默认 9:16）",
        "cast_series": "是否沿用已有 Cast 系列 id？",
        "at_least_one_character_name": "至少给出一个角色名以便登记音频/图像。",
    }
    ask = []
    for key in missing:
        if key in catalog:
            ask.append({"slot": key, "prompt": catalog[key]})
        if len(ask) >= max_ask:
            break
    return {"max_ask": max_ask, "questions": ask}
