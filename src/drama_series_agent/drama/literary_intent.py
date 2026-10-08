# -*- coding: utf-8 -*-
"""Detect literary / rewrite-episode utterances (must call run_literary_generate)."""

from __future__ import annotations

import re
from typing import Any, Optional


_REWRITE_MARKERS = (
    r"重新生成",
    r"再生成",
    r"重写",
    r"再写一?遍",
    r"重做",
    r"不满意",
    r"改写",
    r"重出",
)

_WRITE_MARKERS = (
    r"写第\s*\d+\s*集",
    # 「生成第N集」 alone is ambiguous; exclude 「…视频」
    r"生成第\s*\d+\s*集(?!\s*视频)",
    r"开写",
    r"写剧本",
    r"生成剧本",
    r"写\s*ep\s*\d+",
    r"出\s*ep\s*\d+",
    r"第一集剧情",
    r"第\s*\d+\s*集剧情",
    r"第\s*\d+\s*集剧本",
)

# Pure render / Comfy — must NOT trigger literary rewrite.
_VIDEO_PIPELINE_RE = re.compile(
    r"出片|渲染|构建分镜|分镜脚本|episode-run|入队\s*comfy|入队渲染|可以出片|"
    r"生成视频|做视频|跑(?:一?集)?视频|视频生成|"
    r"生成.{0,24}视频|"
    r"第\s*[一二三四五六七八九十百零\d]+\s*集\s*视频|"
    r"(?:ep\s*0*\d+)\s*视频",
    re.I,
)

_SCRIPT_LEX = re.compile(r"剧本|剧情|文学|写集|对白|重写剧本|改剧本", re.I)

_EP_NUM = re.compile(
    r"(?:第\s*([一二三四五六七八九十百零\d]+)\s*集)|(?:ep\s*0*(\d+))",
    re.I,
)

_CN_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _cn_to_int(raw: str) -> Optional[int]:
    s = (raw or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s in _CN_DIGITS:
        return _CN_DIGITS[s]
    if s.startswith("十"):
        rest = s[1:]
        return 10 + (_CN_DIGITS.get(rest, 0) if rest else 0)
    if "十" in s:
        left, _, right = s.partition("十")
        return _CN_DIGITS.get(left, 0) * 10 + (_CN_DIGITS.get(right, 0) if right else 0)
    return None


def extract_episode_ids(text: str) -> list[str]:
    """Parse ep001-style ids from user text; default ep001 when '第一集' implied."""
    t = (text or "").strip()
    found: list[int] = []
    for m in _EP_NUM.finditer(t):
        raw = m.group(1) or m.group(2)
        n = _cn_to_int(raw) if m.group(1) else int(raw)
        if n and n > 0:
            found.append(n)
    if not found and re.search(r"第一集|首集|开篇", t):
        found.append(1)
    # de-dup preserve order
    out: list[str] = []
    seen: set[int] = set()
    for n in found:
        if n not in seen:
            seen.add(n)
            out.append(f"ep{n:03d}")
    return out


def is_video_render_intent(text: str) -> bool:
    """True when user asks to render / generate video (S2+Comfy), not rewrite script."""
    t = (text or "").strip()
    if not t:
        return False
    if not _VIDEO_PIPELINE_RE.search(t):
        return False
    # 「重写剧本并出片」→ literary+chain, not pure video
    if _SCRIPT_LEX.search(t) and re.search(
        r"重写|重新生成|再写|改写|写剧本|生成剧本", t
    ):
        return False
    return True


def is_literary_generate_intent(text: str) -> bool:
    """True when user wants episode script written/regenerated (not develop-only)."""
    t = (text or "").strip()
    if not t:
        return False
    if re.search(r"不要写|别写|先别写|只要大纲|先做设定|先确定大纲", t):
        return False
    # 「生成第1集视频」→ S2 only
    if is_video_render_intent(t) and not _SCRIPT_LEX.search(t):
        return False
    has_write = any(re.search(p, t, re.I) for p in _WRITE_MARKERS)
    has_rewrite = any(re.search(p, t, re.I) for p in _REWRITE_MARKERS)
    if has_rewrite and (
        has_write
        or re.search(r"第.?集|剧本|剧情|文学|ep\s*\d+", t, re.I)
        or re.search(r"重新生成|再生成|重写", t)
    ):
        # 「重新生成第一集剧情」/「不满意，重新生成剧本」
        return True
    if has_write:
        return True
    return False


def literary_intent_payload(text: str) -> Optional[dict[str, Any]]:
    """Return {episode_ids, revision_notes, chain_s2} when intent matches, else None."""
    if not is_literary_generate_intent(text):
        return None
    eps = extract_episode_ids(text)
    if not eps:
        eps = ["ep001"]
    return {
        "episode_ids": eps,
        "revision_notes": text.strip()[:500],
        "episode_count": len(eps),
        "chain_s2": wants_chain_s2_after_literary(text),
    }


def wants_chain_s2_after_literary(text: str) -> bool:
    """After literary write, also build jsonl → validate → Comfy.

    Default is **script only**. Chain S2 only when user explicitly asks to
    render / 出片 / build storyboard in the same utterance (or after writing).
    「重新生成第N集剧情」 alone must NOT enqueue Comfy.
    """
    t = (text or "").strip()
    if not t:
        return False
    if re.search(r"只要剧本|只要文学|先别渲染|不要出片|不要渲染|别入队|先别出片", t):
        return False
    return bool(_VIDEO_PIPELINE_RE.search(t))


def is_s2_pipeline_intent(text: str) -> bool:
    """True when user wants build/validate/Comfy without rewriting literary."""
    t = (text or "").strip()
    if not t:
        return False
    if is_literary_generate_intent(t) and wants_chain_s2_after_literary(t):
        # Handled by literary+chain path
        return False
    if re.search(r"只要剧本|不要渲染|先别出片", t):
        return False
    return is_video_render_intent(t) or bool(_VIDEO_PIPELINE_RE.search(t))


def s2_pipeline_payload(text: str) -> Optional[dict[str, Any]]:
    if not is_s2_pipeline_intent(text):
        return None
    eps = extract_episode_ids(text)
    if not eps:
        eps = ["ep001"]
    return {"episode_ids": eps}
