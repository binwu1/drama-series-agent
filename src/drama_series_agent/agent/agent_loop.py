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
    """OpenAI-compatible chat.completions with multi-vendor adaptations."""
    from drama_series_agent.utils.llm_client import chat_completions_create

    return await chat_completions_create(
        messages=messages,
        tools=tools or None,
        temperature=float(kwargs.get("temperature", 0.4)),
        max_tokens=kwargs.get("max_tokens"),
    )


def _assistant_message_payload(choice_message: Any) -> tuple[str, list[Any]]:
    from drama_series_agent.utils.llm_client import message_text

    tool_calls = getattr(choice_message, "tool_calls", None) or []
    text = message_text(choice_message)
    return text, tool_calls



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
            from drama_series_agent.utils.llm_client import ensure_choices, load_llm_settings

            model_name = load_llm_settings().get("model") or "agent"
            choice_msg = ensure_choices(resp, model=model_name).message
            text, tool_calls = _assistant_message_payload(choice_msg)
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
                        "content": text or choice_msg.content or "",
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
            final_text = text or "（无文本回复）"
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

    # Guard: literary rewrite claimed without tool → force enqueue
    from drama_series_agent.drama.literary_intent import literary_intent_payload

    lit = literary_intent_payload(user_text)
    called_lit = any(t.get("name") == "run_literary_generate" for t in tool_trace)
    if lit and not called_lit:
        from drama_series_agent.drama.enrich import (
            resolve_literary_premise,
            run_literary_generate,
        )

        premise = resolve_literary_premise(project_dir=project_dir, fallback=user_text)
        forced = run_literary_generate(
            project_dir=project_dir,
            premise=premise,
            episode_count=int(lit["episode_count"]),
            genre="短剧",
            episode_ids=list(lit["episode_ids"]),
            revision_notes=lit.get("revision_notes"),
            run_in_background=True,
            use_skill=True,
            force=False,
            chain_s2=bool(lit.get("chain_s2")),
        )
        tool_trace.append(
            {
                "name": "run_literary_generate",
                "args": {
                    "episode_ids": lit["episode_ids"],
                    "forced": True,
                    "chain_s2": bool(lit.get("chain_s2")),
                },
                "result": str(forced)[:2000],
            }
        )
        eps = "、".join(lit["episode_ids"])
        if forced.get("error") == "series_bible_incomplete":
            final_text = forced.get("message") or "系列圣经未齐，无法写集。"
        elif lit.get("chain_s2"):
            final_text = (
                f"已后台启动整集流水线（{eps}），任务 `{forced.get('job_id')}`。\n"
                "写集完成后将自动：构建 episode-run.jsonl → 校验 → 入队 Comfy。"
            )
        else:
            final_text = (
                f"已后台启动文学写集（{eps}），任务 `{forced.get('job_id')}`。\n"
                "完成后会通知并更新「文学产出」页；请勿在未落盘前当作已生成。"
            )
        status = build_status_payload(project_dir)

    progress_hint = "请打开右侧工作台，进入「生成进度」页查看任务进度；需要中断或断点续跑时，在该页使用按钮。"
    if started_pipeline and progress_hint not in final_text:
        final_text = f"{final_text}\n\n{progress_hint}".strip()
    assistant = append_message(
        project_dir,
        role="assistant",
        content=final_text,
        ui_hints={
            "open_workbench": True if started_pipeline or (lit and not called_lit) else status.get("open_workbench"),
            "open_progress": started_pipeline or bool(lit and not called_lit),
            "open_literary": bool(lit),
        },
    )
    from drama_series_agent.agent.turn_trace import record_turn

    turn = record_turn(
        project_dir,
        user_text=user_text,
        assistant_text=final_text,
        tool_trace=tool_trace,
        source="agent_loop",
        meta={"forced_literary": bool(lit and not called_lit)},
    )
    return {
        "assistant_message": assistant,
        "status": status,
        "tool_trace": tool_trace,
        "turn_trace": {
            "turn_id": turn.get("turn_id"),
            "skills": turn.get("skills"),
            "eval": turn.get("eval"),
        },
    }
