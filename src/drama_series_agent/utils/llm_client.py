# -*- coding: utf-8 -*-
"""OpenAI-compatible LLM client with multi-vendor adaptations."""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger
from openai import AsyncOpenAI, OpenAI

from drama_series_agent.llm_presets import find_preset_by_base_url, get_preset


def load_llm_settings() -> dict[str, str]:
    from drama_series_agent.adapters.config import config_manager

    cfg = config_manager.get_llm_config()
    api_key = (cfg.get("api_key") or "").strip()
    base_url = (cfg.get("base_url") or "").strip().rstrip("/")
    model = (cfg.get("model") or "").strip()
    if not api_key or not base_url or not model:
        raise RuntimeError(
            "LLM 未配置完整：请在系统设置中填写 api_key / base_url / model 并保存"
        )
    base_url = normalize_base_url(base_url)
    model = ensure_inference_model(
        api_key=api_key, base_url=base_url, model=model, persist=True
    )
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
    }


# Prefer mid-size chat models currently common on ModelScope MaaS.
_MODELSCOPE_PREFERS = (
    "Qwen/Qwen3.5-27B",
    "Qwen/Qwen3.8-27B",
    "Qwen/Qwen3.5-35B-A3B",
    "Qwen/Qwen3.5-122B-A10B",
    "deepseek-ai/DeepSeek-V4-Pro",
    "ZhipuAI/GLM-5.2",
    "MiniMax/MiniMax-M3",
)


def list_inference_model_ids(*, api_key: str, base_url: str) -> list[str]:
    """GET /v1/models — returns ids currently offered by the OpenAI-compatible host."""
    import httpx

    url = base_url.rstrip("/") + "/models"
    try:
        r = httpx.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20.0,
        )
        r.raise_for_status()
        payload = r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"list models failed ({base_url}): {e}")
        return []
    rows = payload.get("data") or payload.get("models") or []
    out: list[str] = []
    for m in rows:
        mid = (m.get("id") or m.get("name") or "").strip()
        if mid:
            out.append(mid)
    return out


def ensure_inference_model(
    *,
    api_key: str,
    base_url: str,
    model: str,
    persist: bool = False,
) -> str:
    """If ModelScope model is not on /v1/models, pick a live preferred id.

    Avoids silent stub_fallback from ``has no provider supported``.
    """
    vendor = detect_vendor(base_url, model)
    if vendor != "ModelScope":
        return model
    ids = list_inference_model_ids(api_key=api_key, base_url=base_url)
    if not ids:
        return model
    id_set = set(ids)
    if model in id_set:
        return model
    pick = next((p for p in _MODELSCOPE_PREFERS if p in id_set), None)
    if pick is None:
        # Prefer Qwen text models over Image-Edit
        pick = next(
            (
                i
                for i in ids
                if i.startswith("Qwen/") and "Image" not in i and "VL" not in i
            ),
            ids[0],
        )
    logger.warning(
        f"ModelScope 模型「{model}」当前无 provider，已自动改用「{pick}」。"
        "请在设置页保存以固定。"
    )
    if persist and pick != model:
        try:
            from drama_series_agent.adapters.config import config_manager

            config_manager.set_llm_config(
                api_key=api_key, base_url=base_url, model=pick
            )
            config_manager.save()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"persist model fallback failed: {e}")
    return pick


def normalize_base_url(base_url: str) -> str:
    """Normalize vendor base URLs for the OpenAI SDK."""
    u = (base_url or "").strip().rstrip("/")
    if not u:
        return u
    low = u.lower()

    # DeepSeek accepts both; force /v1 for chat.completions path stability
    if low in ("https://api.deepseek.com", "http://api.deepseek.com"):
        return u + "/v1"

    # Anthropic Messages API is not OpenAI chat.completions — keep as-is for
    # compatible gateways that expose /v1/chat/completions under this host.
    if "api.anthropic.com" in low and not low.endswith("/v1"):
        return u + "/v1"

    return u


def detect_vendor(base_url: str, model: str = "") -> str:
    preset = find_preset_by_base_url(base_url)
    if preset:
        return preset["name"]
    low = (base_url or "").lower()
    model_l = (model or "").lower()
    if "modelscope.cn" in low:
        return "ModelScope"
    if "dashscope.aliyuncs.com" in low or "compatible-mode" in low:
        return "Qwen"
    if "api.openai.com" in low:
        return "OpenAI"
    if "anthropic.com" in low:
        return "Claude"
    if "deepseek.com" in low:
        return "DeepSeek"
    if "11434" in low or "ollama" in low:
        return "Ollama"
    if "moonshot.cn" in low:
        return "Moonshot"
    if "qwen" in model_l:
        return "Qwen"
    return "Custom"


def prepare_request_kwargs(
    *,
    base_url: str,
    model: str,
    kwargs: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Provider-specific request tweaks.

    ModelScope / Qwen3 often enable thinking by default; without disabling it,
    content may be empty or choices may be None (crashes on choices[0]).
    """
    request_kwargs = dict(kwargs or {})
    vendor = detect_vendor(base_url, model)
    model_l = (model or "").lower()
    needs_no_thinking = vendor in ("ModelScope", "Qwen") or "qwen3" in model_l or "glm" in model_l

    if needs_no_thinking:
        extra_body = dict(request_kwargs.get("extra_body") or {})
        if "enable_thinking" not in extra_body:
            extra_body["enable_thinking"] = False
        chat_kwargs = dict(extra_body.get("chat_template_kwargs") or {})
        if "enable_thinking" not in chat_kwargs:
            chat_kwargs["enable_thinking"] = False
        extra_body["chat_template_kwargs"] = chat_kwargs
        request_kwargs["extra_body"] = extra_body

    return request_kwargs


def vendor_supports_tools(base_url: str, model: str = "") -> bool:
    """Heuristic: some ModelScope flash / local models reject tools with choices=None."""
    vendor = detect_vendor(base_url, model)
    model_l = (model or "").lower()
    if vendor == "Ollama":
        # Many local tags lack tool calling; still try, with retry fallback
        return True
    if vendor == "ModelScope" and any(
        x in model_l for x in ("flash", "lite", "tiny", "1.5b", "0.5b")
    ):
        return False
    if vendor == "Claude" and "anthropic.com" in (base_url or "").lower():
        # Official Anthropic host is Messages API; OpenAI tools path often breaks
        return False
    return True


def create_async_client(
    *, api_key: str, base_url: str, timeout: float = 120.0
) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key or "sk-placeholder",
        base_url=base_url,
        timeout=timeout,
    )


def create_sync_client(
    *, api_key: str, base_url: str, timeout: float = 180.0
) -> OpenAI:
    return OpenAI(
        api_key=api_key or "sk-placeholder",
        base_url=base_url,
        timeout=timeout,
    )


def ensure_choices(response: Any, *, model: str) -> Any:
    choices = getattr(response, "choices", None)
    if not choices:
        raw = None
        try:
            raw = response.model_dump() if hasattr(response, "model_dump") else repr(response)
        except Exception:
            raw = repr(response)
        raise RuntimeError(
            f"LLM 返回空 choices（model={model}）。"
            f"常见原因：厂商不支持 tools、thinking 未关闭、额度不足或模型 id 无效。"
            f" Raw={raw}"
        )
    return choices[0]


def message_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if content:
        return str(content).strip()
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning:
        logger.warning("content empty; falling back to reasoning_content")
        return str(reasoning).strip()
    return ""


def _is_empty_choices(response: Any) -> bool:
    return not getattr(response, "choices", None)


def _rate_limit_hint(vendor: str, model: str) -> str:
    if vendor == "ModelScope":
        return (
            f"ModelScope 模型 {model} 可能被限流（有时仍返回 HTTP 200 且 choices=null）。"
            f"请稍后再试，或改用当前 /v1/models 列表中的模型（如 Qwen/Qwen3.5-27B）。"
        )
    return f"模型 {model} 返回空 choices，请检查额度/限流后重试。"


async def chat_completions_create(
    *,
    messages: list[dict[str, Any]],
    tools: Optional[list[dict[str, Any]]] = None,
    temperature: float = 0.4,
    max_tokens: Optional[int] = None,
    settings: Optional[dict[str, str]] = None,
    max_retries: int = 3,
) -> Any:
    """
    Create a chat completion with multi-vendor adaptations.

    - Disables thinking for ModelScope / Qwen3 / GLM
    - Skips or retries without tools when the vendor returns choices=None
    - Retries with backoff on empty choices / rate limits
    """
    import asyncio

    from openai import APIStatusError, RateLimitError

    cfg = settings or load_llm_settings()
    api_key = cfg["api_key"]
    base_url = cfg["base_url"]
    model = cfg["model"]
    vendor = detect_vendor(base_url, model)
    client = create_async_client(api_key=api_key, base_url=base_url)

    use_tools = bool(tools) and vendor_supports_tools(base_url, model)
    tool_modes: list[Optional[list[dict[str, Any]]]] = []
    if use_tools:
        tool_modes.append(list(tools or []))
    tool_modes.append(None)  # always have a no-tools attempt

    last_resp: Any = None
    last_err: Optional[Exception] = None

    async def _once(active_tools: Optional[list[dict[str, Any]]]) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if active_tools:
            kwargs["tools"] = active_tools
            kwargs["tool_choice"] = "auto"
        kwargs = prepare_request_kwargs(base_url=base_url, model=model, kwargs=kwargs)
        return await client.chat.completions.create(**kwargs)

    for attempt in range(max_retries):
        for mode_i, active_tools in enumerate(tool_modes):
            try:
                resp = await _once(active_tools)
                last_resp = resp
                if not _is_empty_choices(resp):
                    if active_tools is None and use_tools and mode_i > 0:
                        logger.warning(
                            f"LLM tools unsupported for {vendor}/{model}; continued without tools"
                        )
                    return resp
                logger.warning(
                    f"empty choices attempt={attempt} tools={bool(active_tools)} "
                    f"vendor={vendor} model={model}"
                )
            except RateLimitError as e:
                last_err = e
                logger.warning(f"rate limited: {e}")
            except APIStatusError as e:
                last_err = e
                if e.status_code == 429:
                    logger.warning(f"HTTP 429: {e}")
                else:
                    raise

        if attempt + 1 < max_retries:
            await asyncio.sleep(1.5 * (attempt + 1))

    if last_err is not None:
        raise RuntimeError(_rate_limit_hint(vendor, model) + f" detail={last_err}") from last_err
    if last_resp is not None:
        raise RuntimeError(_rate_limit_hint(vendor, model))
    raise RuntimeError(_rate_limit_hint(vendor, model))
