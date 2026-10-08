# -*- coding: utf-8 -*-
"""Detect develop-intent utterances for series bible (not episode writing)."""

from __future__ import annotations

import re

_DEVELOP_PATTERNS = (
    r"大纲",
    r"世界观",
    r"画风",
    r"立项",
    r"系列圣经",
    r"故事设定",
    r"创作方案",
    r"分集目录",
    r"主要人物",
    r"主要角色",
    r"先做设定",
    r"先确定",
    r"形成文件",
    r"不要写.*第.?集",
    r"别写.*剧本",
    r"先别写",
)

_EPISODE_OVERRIDE = (
    r"写第\s*\d+\s*集",
    r"写ep\s*\d+",
    r"生成第\s*\d+\s*集",
    r"开写",
    r"直接写剧本",
    r"出片",
    r"渲染",
)


def is_series_develop_intent(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if any(re.search(p, t, re.I) for p in _EPISODE_OVERRIDE):
        # Explicit episode request wins unless clearly "不要写第一集"
        if re.search(r"不要写|别写|先别", t):
            return True
        return False
    return any(re.search(p, t, re.I) for p in _DEVELOP_PATTERNS)
