# -*- coding: utf-8 -*-
"""Write episode drafts with the 0xsline short-drama skill, via the configured LLM."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

_SKILL_NAME = "0xsline-short-drama"
_REF_FILES = (
    "references/opening-rules.md",
    "references/rhythm-curve.md",
    "references/hook-design.md",
    "references/satisfaction-matrix.md",
)
_REF_CHARS = 1800


def skill_root() -> Optional[Path]:
    """Repo `.cursor/skills/0xsline-short-drama`, not a runtime tool the chat model can open."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / ".cursor" / "skills" / _SKILL_NAME,
        here.parents[2] / ".cursor" / "skills" / _SKILL_NAME,
    ]
    for path in candidates:
        if (path / "SKILL.md").is_file():
            return path
    return None


def _clip(text: str, limit: int = _REF_CHARS) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…（节选）"


def skill_prompt_pack() -> str:
    root = skill_root()
    if root is None:
        raise FileNotFoundError(f"missing skill {_SKILL_NAME}")
    parts = [
        "你是微短剧编剧。按 0xsline-short-drama 的国内单集格式写可拍摄剧本，不要写策划说明。",
        "单集 1–3 分钟，至少 3 个场次。第 1 集遵守开篇黄金法则，结尾必须有钩子。",
        "禁止把 premise 原文贴成一句台词，禁止「我们开始吧」这类空对白。",
        "文首必须有角色名单，便于下游抽角色：",
        "## 出场",
        "- 角色名",
        "然后再写技能规定的正文（# 第N集、场次、△ 画面、对白、本集钩子）。",
    ]
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    start = skill.find("**单集剧本格式（国内模式）：**")
    end = skill.find("**单集剧本格式（出海模式")
    if start >= 0:
        block = skill[start:end if end > start else start + 1600]
        parts.append(_clip(block, 1600))
    for rel in _REF_FILES:
        path = root / rel
        if path.is_file():
            parts.append(f"\n## 参考 {rel}\n" + _clip(path.read_text(encoding="utf-8")))
    return "\n".join(parts)


def _chat(system: str, user: str) -> str:
    from openai import OpenAI

    from drama_series_agent.adapters.config import config_manager

    cfg = config_manager.config
    llm = getattr(cfg, "llm", None) or {}
    if hasattr(llm, "model_dump"):
        llm = llm.model_dump()
    api_key = (llm.get("api_key") if isinstance(llm, dict) else None) or ""
    base_url = (llm.get("base_url") if isinstance(llm, dict) else None) or None
    model = (llm.get("model") if isinstance(llm, dict) else None) or "gpt-4o-mini"
    client = OpenAI(api_key=api_key or "sk-placeholder", base_url=base_url, timeout=180)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
        max_tokens=4000,
    )
    return (resp.choices[0].message.content or "").strip()


def _strip_fence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", text, re.S)
    if m:
        return m.group(1).strip()
    # Model sometimes wraps only the body after a cast list
    text = re.sub(r"^```(?:markdown|md)?\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def names_from_script(text: str) -> list[str]:
    names: list[str] = []
    in_cast = False
    for line in text.splitlines():
        if line.strip().startswith("## 出场"):
            in_cast = True
            continue
        if in_cast:
            if line.startswith("#"):
                in_cast = False
            else:
                m = re.match(r"^[-*]\s*(.+)$", line.strip())
                if m:
                    names.append(m.group(1).strip())
        m2 = re.match(r"^\*\*出场人物[：:]\*\*\s*(.+)$", line.strip())
        if m2:
            for part in re.split(r"[、,，/]", m2.group(1)):
                part = re.sub(r"[*_`]", "", part).strip()
                if part:
                    names.append(part)
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out[:8]


def write_with_skill(
    *,
    project_dir: Path,
    premise: str,
    episode_count: int,
    genre: str,
    series_id: str,
    episode_ids: Optional[list[str]] = None,
    revision_notes: Optional[str] = None,
) -> dict[str, Any]:
    """One episode markdown per target, written by the configured LLM + skill pack."""
    from drama_series_agent.drama.enrich import _mounts, _now

    system = skill_prompt_pack()
    mounts = _mounts(Path(project_dir))
    dramas = Path(mounts["dramas_dir"])
    episodes_dir = dramas / "episodes"
    episodes_dir.mkdir(parents=True, exist_ok=True)

    if episode_ids:
        targets: list[str] = []
        for raw in episode_ids:
            m = re.match(r"^(?:EP|ep)?(\d+)$", str(raw).strip(), re.I)
            targets.append(f"ep{int(m.group(1)):03d}" if m else str(raw).strip().lower())
    else:
        targets = [f"ep{i:03d}" for i in range(1, max(1, int(episode_count)) + 1)]

    paths: dict[str, str] = {}
    names: list[str] = []
    for ep_id in targets:
        mnum = re.match(r"ep(\d+)$", ep_id, re.I)
        n = int(mnum.group(1)) if mnum else 1
        user = (
            f"系列：{series_id}\n题材：{genre}\n第{n}集\n"
            f"premise：{premise.strip()}\n"
        )
        if revision_notes:
            user += f"修订要求：{revision_notes}\n"
        body = _strip_fence(_chat(system, user))
        if "场次" not in body or len(body) < 400:
            raise ValueError("skill draft too short or missing 场次")
        if not body.lstrip().startswith("#"):
            body = f"# {series_id} · 第{n}集\n\n{body}"
        path = episodes_dir / f"{ep_id}.md"
        path.write_text(body.rstrip() + "\n", encoding="utf-8")
        paths[f"dramas/{series_id}/episodes/{ep_id}.md"] = str(path)
        for name in names_from_script(body):
            if name not in names:
                names.append(name)

    if not names:
        names = ["主角"]
    existing_eps = sorted(p.stem for p in episodes_dir.glob("*.md"))
    index = {
        "series_id": series_id,
        "premise": premise.strip(),
        "genre": genre,
        "episode_count": max(int(episode_count), len(existing_eps)),
        "characters": names,
        "episodes": existing_eps,
        "status": "draft",
        "writer": _SKILL_NAME,
        "revision_notes": revision_notes,
        "updated_at": _now(),
    }
    index_path = dramas / "literary_index.json"
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths[f"dramas/{series_id}/literary_index.json"] = str(index_path)
    return {"paths": paths, "index": index, "characters": names, "writer": _SKILL_NAME}

