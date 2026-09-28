# -*- coding: utf-8 -*-
"""R2V / episode-run adapter surface.

Open-source core does not ship a proprietary Comfy workflow runner.
Provide your own module or monkey-patch:

  drama_series_agent.adapters.r2v.run_episode = my_run_episode
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional


class JobCancelled(Exception):
    """Raised when a render job is cancelled."""


@dataclass
class ShotRunLine:
    shot_id: str
    order: int = 0
    duration_seconds: float = 8.0
    video_prompt: str = ""
    ref_characters: List[str] = field(default_factory=list)
    ref_voices: List[str] = field(default_factory=list)
    first_frame: str = "prev_shot_tail"
    cast_series_id: Optional[str] = None
    audio_mode: str = "native"
    link_mode: str = "chain"


@dataclass
class EpisodeMeta:
    episode_id: str
    h3_workflow: str = ""
    cast_series_id: Optional[str] = None
    ref_image_size: str = "match"
    aspect: str = "9:16"
    context_ir: str = "off"


def load_episode_meta(path: Path) -> EpisodeMeta:
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return EpisodeMeta(
        episode_id=data.get("episode_id") or Path(path).stem.split(".")[0],
        h3_workflow=data.get("h3_workflow") or "",
        cast_series_id=data.get("cast_series_id"),
        ref_image_size=data.get("ref_image_size") or "match",
        aspect=data.get("aspect") or "9:16",
        context_ir=data.get("context_ir") or "off",
    )


def load_episode_run_jsonl(path: Path) -> List[ShotRunLine]:
    import json

    rows: List[ShotRunLine] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        rows.append(
            ShotRunLine(
                shot_id=d["shot_id"],
                order=int(d.get("order") or 0),
                duration_seconds=float(d.get("duration_seconds") or 8),
                video_prompt=d.get("video_prompt") or "",
                ref_characters=list(d.get("ref_characters") or []),
                ref_voices=list(d.get("ref_voices") or []),
                first_frame=d.get("first_frame") or "prev_shot_tail",
                cast_series_id=d.get("cast_series_id"),
                audio_mode=d.get("audio_mode") or "native",
                link_mode=d.get("link_mode") or "chain",
            )
        )
    return rows


def validate_episode_run(shots: List[ShotRunLine]) -> List[str]:
    errs: List[str] = []
    if not shots:
        errs.append("empty episode-run")
    for s in shots:
        if not s.shot_id:
            errs.append("shot missing shot_id")
        if not (s.video_prompt or "").strip():
            errs.append(f"{s.shot_id}: empty video_prompt")
    return errs


async def run_episode(**kwargs: Any) -> Path:
    raise NotImplementedError(
        "Install a video backend adapter implementing run_episode(...). "
        "See README adapters section."
    )


# optional symbols referenced by workers
ProgressCallback = Callable[[dict], None]
