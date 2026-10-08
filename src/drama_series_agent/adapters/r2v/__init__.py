# -*- coding: utf-8 -*-
"""R2V episode render adapter (ComfyUI + MiniMax H3 workflows).

Heavy ``runner`` is lazy — importing schema/validate alone must not pull Comfy.
"""

from __future__ import annotations

from drama_series_agent.adapters.r2v.schema import (
    EpisodeMeta,
    FirstFrameRef,
    ShotRunLine,
    load_episode_meta,
    load_episode_run_jsonl,
)
from drama_series_agent.adapters.r2v.validate import validate_episode_run

__all__ = [
    "JobCancelled",
    "run_episode",
    "EpisodeMeta",
    "FirstFrameRef",
    "ShotRunLine",
    "load_episode_meta",
    "load_episode_run_jsonl",
    "validate_episode_run",
]


def __getattr__(name: str):
    if name in ("run_episode", "JobCancelled"):
        from drama_series_agent.adapters.r2v.runner import JobCancelled, run_episode

        if name == "JobCancelled":
            return JobCancelled
        return run_episode
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
