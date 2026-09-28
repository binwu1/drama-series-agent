# -*- coding: utf-8 -*-
"""LLM helpers stub — wire to your OpenAI-compatible client."""

from __future__ import annotations

from typing import List, Tuple


def test_llm_connection(api_key: str, base_url: str) -> Tuple[bool, str, int]:
    if not api_key or not base_url:
        return False, "missing api_key or base_url", 0
    return True, "stub ok (replace drama_series_agent.utils.llm_util)", 0


def fetch_available_models(api_key: str, base_url: str) -> List[str]:
    return []
