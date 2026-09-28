# -*- coding: utf-8 -*-
"""Config object used by settings API (host-agnostic stub)."""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any


class HostAppVideoConfig:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {
            "comfyui": {
                "comfyui_url": os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188"),
                "video": {},
                "tts": {},
                "image": {},
            },
            "llm": {
                "api_key": os.environ.get("LLM_API_KEY", ""),
                "base_url": os.environ.get("LLM_BASE_URL", ""),
                "model": os.environ.get("LLM_MODEL", ""),
            },
            "template": {"default_template": "9:16"},
        }

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)
