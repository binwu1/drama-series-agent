# -*- coding: utf-8 -*-
"""S/I/A case matrix for Stage1 intake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

AssetFlag = Literal["0", "1", "P"]


@dataclass(frozen=True)
class CaseCode:
    script: AssetFlag
    image: AssetFlag
    audio: AssetFlag

    @property
    def code(self) -> str:
        return f"S{self.script}I{self.image}A{self.audio}"

    def to_dict(self) -> dict:
        return {
            "script": self.script,
            "image": self.image,
            "audio": self.audio,
            "code": self.code,
        }


def status_to_flag(status: str) -> AssetFlag:
    s = (status or "missing").strip().lower()
    if s == "present":
        return "1"
    if s == "partial":
        return "P"
    # missing | deferred → treat as absent for routing matrix
    return "0"


def classify_case(
    *,
    script_status: str,
    image_status: str,
    audio_status: str,
    script_kind: Optional[str] = None,
) -> CaseCode:
    """Map intake statuses to S/I/A case code.

    ``script_kind`` of ``novel`` / ``fragment`` forces script flag ``P`` when
    otherwise present (残缺/长文改编流).
    """
    s = status_to_flag(script_status)
    if s == "1" and script_kind in ("novel", "fragment", "partial"):
        s = "P"
    return CaseCode(
        script=s,
        image=status_to_flag(image_status),
        audio=status_to_flag(audio_status),
    )


# Stage2+ routing hints only — Stage1 writes these into handoff, does not execute.
CASE_ROUTING: dict[str, dict] = {
    "S0I0A0": {
        "label": "只有一句话/题材",
        "stage1_action": "立项问卷 + 空骨架",
        "suggested_skills": ["drama-series-develop", "0xsline-short-drama"],
        "blocks_visual": True,
        "blocks_audio_hardlock": True,
    },
    "S1I0A0": {
        "label": "有剧本，无图无声",
        "stage1_action": "剧本入库；角色名粗提取（只读）",
        "suggested_skills": [
            "short-drama-write",
            "short-drama-assets",
            "short-drama-image-prompts",
        ],
        "blocks_visual": True,
        "blocks_audio_hardlock": True,
    },
    "S1I1A0": {
        "label": "有剧本+图，无声",
        "stage1_action": "图入库 cast；声标 deferred（允许 soft voice）",
        "suggested_skills": ["short-drama-assets", "short-drama-storyboard"],
        "blocks_visual": False,
        "blocks_audio_hardlock": True,
    },
    "S1I0A1": {
        "label": "有剧本+声，无图",
        "stage1_action": "声入库；图缺口阻断视觉生产",
        "suggested_skills": ["short-drama-image-prompts", "short-drama-assets"],
        "blocks_visual": True,
        "blocks_audio_hardlock": False,
    },
    "S1I1A1": {
        "label": "三件齐",
        "stage1_action": "三向校验 + cast 绑定草稿",
        "suggested_skills": [
            "short-drama-storyboard",
            "short-drama-video-prompts",
            "drama-series-h3-r2v-prompts",
        ],
        "blocks_visual": False,
        "blocks_audio_hardlock": False,
    },
    "S0I1A0": {
        "label": "有图无剧本",
        "stage1_action": "图建角色卡草稿；剧本标 missing",
        "suggested_skills": ["short-drama-develop", "short-drama-write"],
        "blocks_visual": False,
        "blocks_audio_hardlock": True,
        "forbid": ["invent_full_plot_from_images_without_auth"],
    },
    "S0I1A1": {
        "label": "有图有声无剧本",
        "stage1_action": "图/声登记；剧本 missing",
        "suggested_skills": ["short-drama-develop", "short-drama-write"],
        "blocks_visual": False,
        "blocks_audio_hardlock": False,
        "forbid": ["invent_full_plot_from_images_without_auth"],
    },
    "S0I0A1": {
        "label": "仅音频",
        "stage1_action": "声纹/说话人登记；其余 missing",
        "suggested_skills": ["short-drama-develop"],
        "blocks_visual": True,
        "blocks_audio_hardlock": False,
        "required_slots": ["title", "at_least_one_character_name"],
    },
}


def routing_for(case: CaseCode) -> dict:
    """Resolve routing; SP* uses develop import stream."""
    if case.script == "P":
        base = {
            "label": "剧本残缺/小说长文",
            "stage1_action": "原件进 输入/ + 改编候选预览，不自动 canonical",
            "suggested_skills": ["short-drama-develop"],
            "blocks_visual": case.image == "0",
            "blocks_audio_hardlock": case.audio == "0",
            "script_canonical": False,
        }
        return base
    key = case.code
    if key in CASE_ROUTING:
        return dict(CASE_ROUTING[key])
    # Fallback: treat P image/audio like 0 for unknown combos
    approx = CaseCode(
        script=case.script if case.script != "P" else "0",
        image="1" if case.image == "1" else "0",
        audio="1" if case.audio == "1" else "0",
    )
    return dict(CASE_ROUTING.get(approx.code, CASE_ROUTING["S0I0A0"]))
