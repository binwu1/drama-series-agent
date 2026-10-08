# -*- coding: utf-8 -*-
"""Config manager — LLM / ComfyUI settings with JSON persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.adapters.config.schema import HostAppVideoConfig, deep_merge


def _config_path() -> Path:
    root = Path(os.environ.get("DRAMA_SERIES_ROOT") or Path.cwd())
    return root / "config.json"


class _Manager:
    def __init__(self) -> None:
        self.config_path = _config_path()
        self.config = self._load()

    def _load(self) -> HostAppVideoConfig:
        path = _config_path()
        self.config_path = path
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return HostAppVideoConfig(data)
            except Exception:
                pass
        return HostAppVideoConfig()

    def reload(self) -> None:
        self.config = self._load()

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.to_dict().get(key, default)

    def update(self, updates: dict[str, Any]) -> None:
        data = self.config.to_dict()
        deep_merge(data, updates or {})
        self.config = HostAppVideoConfig(data)

    def save(self) -> None:
        path = _config_path()
        self.config_path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.config.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def validate(self) -> bool:
        return self.config.validate_required()

    def get_llm_config(self) -> dict[str, Any]:
        llm = self.config.llm
        return {
            "api_key": llm.get("api_key") or "",
            "base_url": llm.get("base_url") or "",
            "model": llm.get("model") or "",
        }

    def set_llm_config(self, api_key: str, base_url: str, model: str) -> None:
        self.update(
            {
                "llm": {
                    "api_key": api_key,
                    "base_url": base_url,
                    "model": model,
                }
            }
        )

    def get_comfyui_config(self) -> dict[str, Any]:
        comfy = self.config.comfyui or {}
        tts = comfy.get("tts") or {}
        image = comfy.get("image") or {}
        video = comfy.get("video") or {}
        return {
            "comfyui_url": comfy.get("comfyui_url") or "http://127.0.0.1:8188",
            "comfyui_api_key": comfy.get("comfyui_api_key"),
            "runninghub_api_key": comfy.get("runninghub_api_key"),
            "runninghub_concurrent_limit": int(comfy.get("runninghub_concurrent_limit") or 1),
            "runninghub_instance_type": comfy.get("runninghub_instance_type"),
            "tts": {"default_workflow": tts.get("default_workflow")},
            "image": {
                "default_workflow": image.get("default_workflow"),
                "reference_workflow": image.get("reference_workflow"),
            },
            "video": {
                "default_workflow": video.get("default_workflow"),
                "aspect": video.get("aspect") or "9:16",
            },
        }

    def set_comfyui_config(
        self,
        comfyui_url: Optional[str] = None,
        comfyui_api_key: Optional[str] = None,
        runninghub_api_key: Optional[str] = None,
        runninghub_concurrent_limit: Optional[int] = None,
        runninghub_instance_type: Optional[str] = None,
    ) -> None:
        updates: dict[str, Any] = {}
        if comfyui_url is not None:
            updates["comfyui_url"] = comfyui_url
        if comfyui_api_key is not None:
            updates["comfyui_api_key"] = comfyui_api_key
        if runninghub_api_key is not None:
            updates["runninghub_api_key"] = runninghub_api_key
        if runninghub_concurrent_limit is not None:
            updates["runninghub_concurrent_limit"] = runninghub_concurrent_limit
        if runninghub_instance_type is not None:
            updates["runninghub_instance_type"] = (
                runninghub_instance_type if runninghub_instance_type else None
            )
        if updates:
            self.update({"comfyui": updates})


config_manager = _Manager()

__all__ = ["config_manager", "HostAppVideoConfig"]
