# -*- coding: utf-8 -*-
"""Best-effort ComfyUI VRAM cleanup between R2V shots."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Optional

from loguru import logger


def resolve_comfyui_base_url(core: Any = None) -> Optional[str]:
    """Return ComfyUI base URL from Host core / config, or None."""
    if core is not None:
        try:
            cfg = core._get_comfykit_config()
            url = (cfg.get("comfyui_url") or "").strip().rstrip("/")
            if url:
                return url
        except Exception:
            pass
    try:
        from drama_series_agent.adapters.config import config_manager

        url = (
            (config_manager.config.to_dict().get("comfyui") or {})
            .get("comfyui_url")
            or ""
        ).strip().rstrip("/")
        return url or None
    except Exception:
        return None


def free_comfyui_memory(
    *,
    core: Any = None,
    base_url: Optional[str] = None,
    unload_models: bool = True,
    free_memory: bool = True,
    timeout_s: float = 30.0,
) -> bool:
    """POST ComfyUI /free between episode shots.

    Default is **full release** (``unload_models=True``, ``free_memory=True``):
    unload model weights and drop activation / intermediate caches so each shot
    starts with a clean VRAM slate. Pass ``unload_models=False`` to keep H3/TE/VAE
    warm (faster reload, higher risk of cache bleed / OOM on long episodes).

    ComfyUI expects JSON: {"unload_models": bool, "free_memory": bool}.
    Returns True if the request succeeded.
    """
    url = (base_url or resolve_comfyui_base_url(core) or "").rstrip("/")
    if not url:
        logger.warning("ComfyUI free skipped: no comfyui_url configured")
        return False

    payload = json.dumps(
        {"unload_models": unload_models, "free_memory": free_memory}
    ).encode("utf-8")
    endpoints = (f"{url}/free", f"{url}/api/free")
    last_err: Optional[Exception] = None
    for ep in endpoints:
        req = urllib.request.Request(
            ep,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                _ = resp.read()
            logger.info(
                f"ComfyUI VRAM freed via {ep} "
                f"(unload_models={unload_models}, free_memory={free_memory})"
            )
            return True
        except Exception as e:  # noqa: BLE001 — best-effort cleanup
            last_err = e
            continue
    logger.warning(f"ComfyUI /free failed ({url}): {last_err}")
    return False
