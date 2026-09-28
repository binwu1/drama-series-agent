# -*- coding: utf-8 -*-
"""Host adapters: Comfy media client, R2V runner, paths, media_ops."""

from drama_series_agent.adapters.media_client import get_media_core
from drama_series_agent.adapters.r2v import run_episode

__all__ = ["get_media_core", "run_episode"]
