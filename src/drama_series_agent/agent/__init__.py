# -*- coding: utf-8 -*-
"""Hermes Agent shell: sessions, chat, LLM tool loop."""

from __future__ import annotations

__all__ = [
    "default_workspace_root",
    "create_conversation",
    "list_conversations",
    "get_conversation",
    "append_message",
    "load_messages",
]

from drama_series_agent.agent.paths import default_workspace_root
from drama_series_agent.agent.session_store import (
    create_conversation,
    get_conversation,
    list_conversations,
)
from drama_series_agent.agent.chat_store import append_message, load_messages
