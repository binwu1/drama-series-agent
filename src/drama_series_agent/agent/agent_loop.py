# -*- coding: utf-8 -*-
"""LLM tool loop for one user turn."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from drama_series_agent.agent.chat_store import append_message, load_messages
from drama_series_agent.agent.dispatch_bridge import run_tool
from drama_series_agent.agent.prompts import build_system_prompt
from drama_series_agent.agent.tools_merge import merged_tool_schemas
from drama_series_agent.agent.ui_hints import build_status_payload

LLMChatFn = Callable[..., Awaitable[Any]]


async def _default_llm_chat(*, messages: list[dict], tools: list[dict], **kwargs: Any) -> Any:
    """OpenAI-compatible chat.completions with tools."""
    from drama_series_agent.adapters.config import config_manager
    from openai import AsyncOpenAI

    cfg = config_manager.config
    llm = getattr(cfg, "llm", None) or {}
    if hasattr(llm, "model_dump"):
        llm = llm.model_dump()
    api_key = (llm.get("api_key") if isinstance(llm, dict) else None) or ""
    base_url = (llm.get("base_url") if isinstance(llm, dict) else None) or None
    model = (llm.get("model") if isinstance(llm, dict) else None) or "gpt-4o-mini"
    client = AsyncOpenAI(api_key=api_key or "sk-placeholder", base_url=base_url)
    return await client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools or None,
        tool_choice="auto" if tools else None,
        temperature=0.4,
    )


def _history_as_openai(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        role = r.get("role") or "assistant"
        if role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": r.get("tool_name") or "tool",
                    "content": r.get("content") or "",
                }
            )
        elif role in ("user", "assistant", "system"):
            out.append({"role": role, "content": r.get("content") or ""})
    return out


async def run_agent_turn(
    *,
    project_dir: Path,
    user_text: str,
    llm_chat: Optional[LLMChatFn] = None,
    max_rounds: int = 8,
) -> dict[str, Any]:
    """Run one user→assistant turn with optional tool calls. Persists chat."""
    project_dir = Path(project_dir)
    # user message already appended by API layer when used via HTTP;
    # still safe if caller didn't append — avoid duplicate by checking last
    history = load_messages(project_dir, limit=40)
    if not history or history[-1].get("role") != "user" or history[-1].get("content") != user_text:
        append_message(project_dir, role="user", content=user_text)
        history = load_messages(project_dir, limit=40)

    status = build_status_payload(project_dir)
    system = build_system_prompt(status)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    # drop the trailing user — we add explicitly below from history
    prior = [m for m in history[:-1] if m.get("role") in ("user", "assistant")]
    messages.extend(_history_as_openai(prior[-20:]))
    messages.append({"role": "user", "content": user_text})

    tools = merged_tool_schemas()
    chat_fn = llm_chat or _default_llm_chat
    tool_trace: list[dict[str, Any]] = []
    final_text = ""

    try:
        for _ in range(max_rounds):
            resp = await chat_fn(messages=messages, tools=tools)
            choice = resp.choices[0].message
            tool_calls = getattr(choice, "tool_calls", None) or []
            if tool_calls:
                # assistant message with tool_calls
                tc_payload = []
                for tc in tool_calls:
                    tc_payload.append(
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                    )
                messages.append(
                    {
                        "role": "assistant",
                        "content": choice.content or "",
                        "tool_calls": tc_payload,
                    }
                )
                for tc in tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except Exception:  # noqa: BLE001
                        args = {}
                    raw = run_tool(name, args, project_dir=project_dir)
                    tool_trace.append({"name": name, "args": args, "result": raw[:2000]})
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": raw,
                        }
                    )
                continue
            final_text = (choice.content or "").strip() or "（无文本回复）"
            break
        else:
            final_text = final_text or "工具调用轮次已达上限，请再试一次或缩小请求。"
    except Exception as e:  # noqa: BLE001
        final_text = f"Agent 暂时无法调用模型（{e}）。已记录你的消息；可稍后重试或使用工作台验收。"

    status = build_status_payload(project_dir)
    pipeline_tools = {
        "run_s2_build_and_comfy",
        "enqueue_comfy_episode",
        "continue_series",
        "resume_from_shot",
    }
    started_pipeline = any(t.get("name") in pipeline_tools for t in tool_trace)
    progress_hint = "请打开右侧工作台，进入「生成进度」页查看任务进度；需要中断或断点续跑时，在该页使用按钮。"
    if started_pipeline and progress_hint not in final_text:
        final_text = f"{final_text}\n\n{progress_hint}".strip()
    assistant = append_message(
        project_dir,
        role="assistant",
        content=final_text,
        ui_hints={
            "open_workbench": True if started_pipeline else status.get("open_workbench"),
            "open_progress": started_pipeline,
        },
    )
    return {
        "assistant_message": assistant,
        "status": status,
        "tool_trace": tool_trace,
    }
