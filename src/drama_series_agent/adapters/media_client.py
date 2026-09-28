# -*- coding: utf-8 -*-
"""ComfyKit-backed media core used by the R2V episode runner."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger


@dataclass
class _MediaResult:
    status: str
    url: str
    msg: str = ""
    videos: Optional[list] = None


class MediaService:
    """Thin wrapper: ``await media(prompt, workflow=..., media_type='video', **params)``."""

    def __init__(self, core: "MediaCore") -> None:
        self.core = core

    async def __call__(
        self,
        prompt: str,
        *,
        workflow: str,
        media_type: str = "video",
        **params: Any,
    ) -> Any:
        kit = await self.core._get_or_create_comfykit()
        workflow_params = {"prompt": prompt, **params}
        logger.info(f"Comfy execute: {workflow}")
        result = await kit.execute(workflow, workflow_params)
        status = getattr(result, "status", None) or "failed"
        if status != "completed":
            msg = (getattr(result, "msg", None) or "").strip() or f"workflow {status}"
            raise RuntimeError(f"Media generation failed: {msg}")

        url = ""
        if media_type == "video":
            videos = getattr(result, "videos", None) or []
            if not videos:
                raise RuntimeError("Media generation completed but no video output")
            first = videos[0]
            url = first if isinstance(first, str) else getattr(first, "url", None) or str(first)
        else:
            images = getattr(result, "images", None) or []
            if not images:
                raise RuntimeError("Media generation completed but no image output")
            first = images[0]
            url = first if isinstance(first, str) else getattr(first, "url", None) or str(first)

        out = _MediaResult(status="completed", url=url, videos=getattr(result, "videos", None))
        return out


class MediaCore:
    """Drop-in replacement for the host ``pixelle_video`` core used by R2V runner."""

    def __init__(self) -> None:
        self.media = MediaService(self)
        self._kit = None
        self._comfyui_url = (
            os.environ.get("COMFYUI_URL")
            or os.environ.get("COMFY_URL")
            or "http://127.0.0.1:8188"
        ).rstrip("/")

    def _get_comfykit_config(self) -> dict[str, Any]:
        try:
            from drama_series_agent.adapters.config import config_manager

            cfg = (config_manager.config.to_dict().get("comfyui") or {})
            url = (cfg.get("comfyui_url") or self._comfyui_url).strip().rstrip("/")
            if url:
                self._comfyui_url = url
        except Exception:
            pass
        return {"comfyui_url": self._comfyui_url}

    async def initialize(self) -> None:
        await self._get_or_create_comfykit()

    async def _get_or_create_comfykit(self):
        if self._kit is not None:
            return self._kit
        try:
            from comfykit import ComfyKit
        except ImportError as e:
            raise ImportError(
                "comfykit is required for rendering. "
                "pip install 'drama-series-agent[render]' or pip install comfykit"
            ) from e
        cfg = self._get_comfykit_config()
        logger.info(f"Creating ComfyKit → {cfg.get('comfyui_url')}")
        self._kit = ComfyKit(**cfg)
        return self._kit


_CORE: Optional[MediaCore] = None


def get_media_core() -> MediaCore:
    global _CORE
    if _CORE is None:
        _CORE = MediaCore()
    return _CORE
