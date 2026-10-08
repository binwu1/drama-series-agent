# -*- coding: utf-8 -*-
"""Load drama-series-develop skill pack for run_series_develop."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

_SKILL = "drama-series-develop"
# Keep pack small — large system prompts + ModelScope often hang / empty choices.
_REF_FILES = (
    "references/stage-contract.md",
    "assets/creative-plan.md",
)
_REF_CHARS = 700


def skill_root() -> Optional[Path]:
    from drama_series_agent.utils.skills_paths import skill_root as resolve

    return resolve(_SKILL)


def _clip(text: str, limit: int = _REF_CHARS) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…（节选）"


def develop_skill_prompt_pack() -> str:
    """Compact system pack for series bible generation."""
    root = skill_root()
    parts = [
        "你是微短剧系列开发编辑（drama-series-develop），不是分集编剧。",
        "禁止输出第1集剧本、场次、对白、△画面。",
        "戏剧承诺须含：主体、追求、昂贵阻力、独特矛盾、反复回报、终止条件。",
        "穿越/神力是前提装置：必须写边界与代价。",
        "严格按下列标记分段输出（每段≥200汉字实质内容）：",
        "## FILE: creative-plan.md",
        "## FILE: world.md",
        "## FILE: characters.md",
        "## FILE: art-style.md",
        "## FILE: episode-directory.md",
        "episode-directory 必须围绕 creative-plan：写满其「集数规模」"
        "（如 24 集则 EP001–EP024），分三阶段对应开端/中段/高潮结局；"
        "禁止只写前十几集就结束。",
    ]
    if root is None:
        return "\n".join(parts)
    for rel in _REF_FILES:
        path = root / rel
        if path.is_file():
            parts.append(f"\n## 参考 {rel}\n" + _clip(path.read_text(encoding="utf-8")))
    return "\n".join(parts)
