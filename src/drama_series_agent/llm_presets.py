# -*- coding: utf-8 -*-
"""LLM presets for OpenAI-compatible providers (UI quick-select)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


LLM_PRESETS: List[Dict[str, Any]] = [
    {
        "name": "ModelScope",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "model": "Qwen/Qwen3.5-27B",
        "api_key_url": "https://modelscope.cn/my/myaccesstoken",
        "notes": "OpenAI 兼容；可用模型会变，请 GET /v1/models。Qwen2.5-* 常已下架；当前推荐 Qwen3.5-27B。Flash 易限流且常不支持 tools。",
    },
    {
        "name": "Qwen",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-max",
        "api_key_url": "https://bailian.console.aliyun.com/?tab=model#/api-key",
        "notes": "阿里云百炼 compatible-mode；Qwen3 会自动关闭 thinking。",
    },
    {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "api_key_url": "https://platform.openai.com/api-keys",
    },
    {
        "name": "Claude",
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-sonnet-4-5",
        "api_key_url": "https://console.anthropic.com/settings/keys",
        "notes": "官方 Anthropic 非 OpenAI chat.completions；若直连失败请改用兼容网关 Base URL。",
    },
    {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_url": "https://platform.deepseek.com/api_keys",
    },
    {
        "name": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2",
        "api_key_url": "https://ollama.com/download",
        "default_api_key": "ollama",
        "notes": "本地服务；API Key 可填任意非空（默认 ollama）。",
    },
    {
        "name": "Moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "api_key_url": "https://platform.moonshot.cn/console/api-keys",
    },
]


def get_preset_names() -> List[str]:
    return [preset["name"] for preset in LLM_PRESETS]


def get_preset(name: str) -> Dict[str, Any]:
    for preset in LLM_PRESETS:
        if preset["name"] == name:
            return preset
    return {}


def find_preset_by_base_url_and_model(base_url: str, model: str) -> Optional[str]:
    bu = (base_url or "").rstrip("/")
    for preset in LLM_PRESETS:
        if preset["base_url"].rstrip("/") == bu and preset["model"] == model:
            return preset["name"]
    return None


def find_preset_by_base_url(base_url: str) -> Optional[Dict[str, Any]]:
    bu = (base_url or "").rstrip("/").lower()
    if not bu:
        return None
    for preset in LLM_PRESETS:
        pbu = preset["base_url"].rstrip("/").lower()
        if bu == pbu or bu.startswith(pbu) or pbu.startswith(bu):
            return preset
        # DeepSeek with/without /v1
        if "deepseek.com" in bu and "deepseek.com" in pbu:
            return preset
    return None
