from __future__ import annotations

import json
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator

FirstFrameSource = Literal[
    "external",
    "prev_shot_tail",
    "prev_episode_tail",
    "keyframe_file",
]
AudioMode = Literal["native", "tts"]
LinkMode = Literal["chain", "independent"]

MAX_REF_IMAGES = 9  # including first_frame as Picture 1
MAX_REF_AUDIOS = 3


class FirstFrameRef(BaseModel):
    source: FirstFrameSource
    path: Optional[str] = None
    prev_shot_id: Optional[str] = None
    prev_episode_id: Optional[str] = None
    notes: Optional[str] = None


class ShotRunLine(BaseModel):
    schema_version: str = "1.0.0"
    episode_id: str
    shot_id: str
    order: int
    duration_seconds: float
    video_prompt: str
    first_frame: FirstFrameRef
    ref_characters: List[str] = []
    ref_voices: List[str] = []
    audio_mode: AudioMode = "native"
    link_mode: LinkMode = "chain"
    cast_series_id: Optional[str] = None
    drama_refs: Optional[dict] = None

    @field_validator("duration_seconds")
    @classmethod
    def duration_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("duration_seconds must be > 0")
        if v > 15.5:
            raise ValueError("duration_seconds exceeds H3 ~15s cap; split the shot")
        return v

    @field_validator("ref_characters")
    @classmethod
    def lim_chars(cls, v: List[str]) -> List[str]:
        if len(v) > MAX_REF_IMAGES - 1:
            raise ValueError(f"ref_characters max {MAX_REF_IMAGES - 1} (Picture 1 is first_frame)")
        return v

    @field_validator("ref_voices")
    @classmethod
    def lim_voices(cls, v: List[str]) -> List[str]:
        if len(v) > MAX_REF_AUDIOS:
            raise ValueError(f"ref_voices max {MAX_REF_AUDIOS}")
        return v


class EpisodeMeta(BaseModel):
    episode_id: str
    default_audio_mode: AudioMode = "native"
    default_link_mode: LinkMode = "chain"
    aspect: str = "9:16"
    h3_workflow: str = "selfhost/video_minimax_h3_r2v.json"
    cast_series_id: Optional[str] = None
    ref_image_size: str = "match"
    # off | local (Prompting Guidance enricher) | api (MiniMax /v2/h3_context_ir)
    context_ir: Optional[str] = "local"


def load_episode_run_jsonl(path: Path) -> List[ShotRunLine]:
    shots: List[ShotRunLine] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            shots.append(ShotRunLine.model_validate(json.loads(line)))
        except Exception as e:
            raise ValueError(f"{path}:{i}: {e}") from e
    shots.sort(key=lambda s: s.order)
    return shots


def load_episode_meta(path: Path) -> EpisodeMeta:
    return EpisodeMeta.model_validate(json.loads(path.read_text(encoding="utf-8")))
