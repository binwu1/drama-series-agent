# -*- coding: utf-8 -*-
"""Host adapters: Comfy media client, R2V runner, paths, media_ops.

Import submodules directly — do **not** eager-load r2v/media here.
``from drama_series_agent.adapters.config import config_manager`` must stay light
(settings API); pulling runner caused circular import deadlocks.
"""

from __future__ import annotations

__all__ = ["get_media_core", "run_episode"]


def __getattr__(name: str):
    if name == "get_media_core":
        from drama_series_agent.adapters.media_client import get_media_core

        return get_media_core
    if name == "run_episode":
        from drama_series_agent.adapters.r2v.runner import run_episode

        return run_episode
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
