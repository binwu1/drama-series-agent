# -*- coding: utf-8 -*-
"""LLM helpers — OpenAI-compatible /models discovery and connection test."""

from __future__ import annotations

from typing import Any, List, Tuple

import httpx
from loguru import logger


def _models_url(base_url: str) -> str:
    base_url = (base_url or "").rstrip("/")
    if base_url.endswith("/v1"):
        return f"{base_url}/models"
    return f"{base_url}/v1/models"


def _extract_model_ids(payload: Any) -> List[str]:
    """Accept OpenAI-shaped {data:[{id}]} and a few vendor variants."""
    if payload is None:
        return []
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("data") or payload.get("models") or []
    else:
        return []

    ids: List[str] = []
    for row in rows:
        if isinstance(row, str):
            mid = row.strip()
        elif isinstance(row, dict):
            mid = str(row.get("id") or row.get("name") or row.get("model") or "").strip()
        else:
            mid = ""
        if mid and mid not in ids:
            ids.append(mid)
    ids.sort()
    return ids


def fetch_available_models(api_key: str, base_url: str, timeout: float = 15.0) -> List[str]:
    """
    GET OpenAI-compatible /v1/models with Bearer auth.

    Raises httpx errors on network/HTTP failure so callers can surface messages.
    """
    if not api_key or not base_url:
        raise ValueError("api_key and base_url are required")

    models_url = _models_url(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    logger.debug(f"Fetching models from: {models_url}")

    with httpx.Client(timeout=timeout) as client:
        response = client.get(models_url, headers=headers)
        response.raise_for_status()
        models = _extract_model_ids(response.json())
        logger.debug(f"Fetched {len(models)} models")
        return models


def test_llm_connection(api_key: str, base_url: str, timeout: float = 15.0) -> Tuple[bool, str, int]:
    """Return (ok, message, model_count)."""
    if not api_key or not base_url:
        return False, "请填写 api_key 与 base_url", 0
    try:
        models = fetch_available_models(api_key, base_url, timeout)
        if models:
            return True, f"连接成功！可用 {len(models)} 个模型", len(models)
        return (
            True,
            "连接成功，但 /models 未返回列表；可手动填写模型名后保存",
            0,
        )
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        detail = ""
        try:
            detail = (e.response.text or "")[:200]
        except Exception:
            detail = ""
        if status_code == 401:
            return False, "认证失败：API Key 无效", 0
        if status_code == 403:
            return False, "无权限：检查 API Key 权限", 0
        if status_code == 404:
            return False, "接口不存在：检查 Base URL", 0
        msg = f"API 错误：HTTP {status_code}"
        if detail:
            msg = f"{msg} — {detail}"
        return False, msg, 0
    except httpx.ConnectError:
        return False, "连接失败：无法访问服务器", 0
    except httpx.TimeoutException:
        return False, "连接超时：服务器未及时响应", 0
    except Exception as e:
        logger.error(f"LLM connection test error: {e}")
        return False, f"错误：{e}", 0
