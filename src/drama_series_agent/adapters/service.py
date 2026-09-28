# -*- coding: utf-8 -*-
"""Host media service shim. Wire to your Comfy / video stack."""

from __future__ import annotations

from typing import Any


class _Media:
    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "Wire drama_series_agent.adapters.service.drama_series_agent.media "
            "to your video backend (or inject run_episode_fn)."
        )


class _Core:
    media = _Media()

    async def initialize(self) -> None:
        return None


drama_series_agent = _Core()  # name kept only as inject point legacy; prefer adapters.r2v
