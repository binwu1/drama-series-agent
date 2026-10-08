# -*- coding: utf-8 -*-
"""Config object used by settings API (host-agnostic)."""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any


def default_config_data() -> dict[str, Any]:
    return {
        "comfyui": {
            "comfyui_url": os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188"),
            "comfyui_api_key": None,
            "runninghub_api_key": None,
            "runninghub_concurrent_limit": 1,
            "runninghub_instance_type": None,
            "video": {
                "default_workflow": "selfhost/video_minimax_h3_r2v_fast.json",
                "aspect": "9:16",
            },
            "tts": {"default_workflow": None},
            "image": {
                "default_workflow": None,
                "reference_workflow": None,
            },
        },
        "llm": {
            "api_key": os.environ.get("LLM_API_KEY", ""),
            "base_url": os.environ.get("LLM_BASE_URL", ""),
            "model": os.environ.get("LLM_MODEL", ""),
        },
        "template": {"default_template": "9:16"},
    }


def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    for key, value in (updates or {}).items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


class HostAppVideoConfig:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = deep_merge(default_config_data(), data or {})

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    @property
    def llm(self) -> dict[str, Any]:
        return self._data.setdefault("llm", {})

    @property
    def comfyui(self) -> dict[str, Any]:
        return self._data.setdefault("comfyui", {})

    @property
    def template(self) -> dict[str, Any]:
        return self._data.setdefault("template", {})

    def is_llm_configured(self) -> bool:
        llm = self.llm
        return bool(
            str(llm.get("api_key") or "").strip()
            and str(llm.get("base_url") or "").strip()
            and str(llm.get("model") or "").strip()
        )

    def validate_required(self) -> bool:
        return self.is_llm_configured()
