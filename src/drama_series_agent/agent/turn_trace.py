# -*- coding: utf-8 -*-
"""Local turn-span trace log + deterministic trajectory quality eval.

Persists to ``projects/{slug}/memory/traces.jsonl`` (one JSON object per turn).
No external observability backend — OTel-shaped field names for later export.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# tool → Cursor skill id (best-effort annotation for traces)
TOOL_SKILL_MAP: dict[str, str] = {
    "run_series_develop": "drama-series-develop",
    "save_series_bible_doc": "drama-series-develop",
    "get_series_bible_status": "drama-series-develop",
    "list_series_bible_docs": "drama-series-develop",
    "run_literary_generate": "0xsline-short-drama",
    "get_literary_episode": "0xsline-short-drama",
    "save_literary_episode": "0xsline-short-drama",
    "list_literary_episodes": "0xsline-short-drama",
    "accept_literary_package": "0xsline-short-drama",
    "run_s2_build_and_comfy": "drama-series-h3-r2v-prompts",
    "enqueue_comfy_episode": "drama-series-h3-r2v-prompts",
    "enqueue_build_episode_jsonl": "drama-series-h3-r2v-prompts",
    "validate_episode_run": "drama-series-h3-r2v-prompts",
    "scaffold_drama_project": "drama-intake",
    "run_intake_pipeline": "drama-intake",
    "write_intake_manifest": "drama-intake",
}

COMFY_TOOLS = frozenset(
    {
        "run_s2_build_and_comfy",
        "enqueue_comfy_episode",
        "continue_series",
        "resume_from_shot",
    }
)

_TRUNC = 2000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trunc(value: Any, limit: int = _TRUNC) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        raw = json.dumps(value, ensure_ascii=False)
        if len(raw) <= limit:
            return value
        return raw[:limit] + "…"
    s = str(value)
    return s if len(s) <= limit else s[:limit] + "…"


def traces_path(project_dir: Path) -> Path:
    return Path(project_dir) / "memory" / "traces.jsonl"


def skill_for_tool(name: str) -> Optional[str]:
    return TOOL_SKILL_MAP.get(name)


def build_tool_spans(tool_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for i, t in enumerate(tool_trace or []):
        name = str(t.get("name") or "")
        spans.append(
            {
                "span_id": f"tool-{i}",
                "type": "tool",
                "name": name,
                "skill": skill_for_tool(name),
                "input": _trunc(t.get("args")),
                "output": _trunc(t.get("result")),
                "forced": bool((t.get("args") or {}).get("forced"))
                if isinstance(t.get("args"), dict)
                else bool(t.get("forced")),
            }
        )
    return spans


def evaluate_trajectory(
    *,
    user_text: str,
    tool_trace: list[dict[str, Any]],
    source: str = "agent",
) -> dict[str, Any]:
    """Deterministic trajectory quality checks for one turn."""
    from drama_series_agent.drama.develop_intent import is_series_develop_intent
    from drama_series_agent.drama.literary_intent import (
        literary_intent_payload,
        s2_pipeline_payload,
        wants_chain_s2_after_literary,
    )

    text = (user_text or "").strip()
    names = [str(t.get("name") or "") for t in (tool_trace or [])]
    name_set = set(names)
    issues: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    def _fail(code: str, msg: str) -> None:
        issues.append({"severity": "error", "code": code, "message": msg})
        checks.append({"code": code, "pass": False, "message": msg})

    def _warn(code: str, msg: str) -> None:
        issues.append({"severity": "warn", "code": code, "message": msg})
        checks.append({"code": code, "pass": True, "warn": True, "message": msg})

    def _ok(code: str, msg: str = "") -> None:
        checks.append({"code": code, "pass": True, "message": msg})

    lit = literary_intent_payload(text)
    s2p = s2_pipeline_payload(text)
    develop = is_series_develop_intent(text)

    # --- literary: script-only must not touch Comfy ---
    if lit:
        chain = bool(lit.get("chain_s2")) or wants_chain_s2_after_literary(text)
        if "run_literary_generate" in name_set:
            _ok("literary_tool_present", "run_literary_generate called")
        else:
            _fail("literary_tool_missing", "写集意图但未调用 run_literary_generate")

        if any(
            isinstance(t.get("args"), dict) and t.get("args", {}).get("forced")
            for t in tool_trace
            if t.get("name") == "run_literary_generate"
        ):
            _warn(
                "literary_forced_recovery",
                "模型未主动调写集工具，由系统强制补调",
            )

        if not chain:
            bad = sorted(name_set & COMFY_TOOLS)
            if bad:
                _fail(
                    "literary_script_only_no_comfy",
                    f"只要剧本却调用了出片工具：{', '.join(bad)}",
                )
            else:
                _ok("literary_script_only_no_comfy")
            # chain_s2 flag on literary tool must stay false
            for t in tool_trace:
                if t.get("name") != "run_literary_generate":
                    continue
                args = t.get("args") if isinstance(t.get("args"), dict) else {}
                if args.get("chain_s2"):
                    _fail(
                        "literary_chain_s2_unexpected",
                        "剧本-only 意图但 run_literary_generate.chain_s2=true",
                    )
                    break
            else:
                _ok("literary_chain_s2_off")
        else:
            _ok("literary_chain_s2_allowed", "用户明确要求出片/渲染")

    # --- S2-only path ---
    if s2p and not lit:
        if name_set & COMFY_TOOLS or "run_s2_build_and_comfy" in name_set:
            _ok("s2_tool_present")
        else:
            _fail("s2_tool_missing", "出片意图但未调用 run_s2_build_and_comfy / enqueue")

    # --- develop ---
    if develop and not lit and not s2p:
        if "run_series_develop" in name_set:
            _ok("develop_tool_present")
        else:
            # Fast-path may skip when bible already ready — soft warn only if
            # user text looks like a fresh develop ask.
            if re.search(r"确定大纲|立项|写大纲|系列设定|世界观", text):
                _warn(
                    "develop_tool_missing",
                    "开发意图未看到 run_series_develop（可能圣经已齐走了 Agent）",
                )
            else:
                _ok("develop_skipped_or_agent")

    # --- empty trajectory with strong intent ---
    if not names and (lit or s2p):
        _fail("empty_trajectory", "强意图（写集/出片）但 tool_trace 为空")

    errors = [i for i in issues if i["severity"] == "error"]
    warns = [i for i in issues if i["severity"] == "warn"]
    passed = len(errors) == 0
    score = 1.0
    score -= 0.35 * len(errors)
    score -= 0.1 * len(warns)
    score = max(0.0, min(1.0, round(score, 3)))
    label = "ok" if passed and not warns else ("warn" if passed else "fail")

    return {
        "pass": passed,
        "score": score,
        "label": label,
        "issues": issues,
        "checks": checks,
        "intent": {
            "literary": bool(lit),
            "chain_s2": bool(lit.get("chain_s2")) if lit else False,
            "s2_pipeline": bool(s2p),
            "develop": bool(develop),
        },
        "source": source,
    }


def record_turn(
    project_dir: Path,
    *,
    user_text: str,
    assistant_text: str,
    tool_trace: list[dict[str, Any]],
    source: str = "agent_loop",
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append one turn record (spans + eval) to traces.jsonl."""
    project_dir = Path(project_dir)
    spans = build_tool_spans(tool_trace)
    skills = sorted(
        {s["skill"] for s in spans if s.get("skill")}
    )
    evaluation = evaluate_trajectory(
        user_text=user_text, tool_trace=tool_trace, source=source
    )
    turn: dict[str, Any] = {
        "type": "turn",
        "turn_id": str(uuid.uuid4()),
        "ts": _now(),
        "source": source,
        "user_input": _trunc(user_text, 1500),
        "assistant_output": _trunc(assistant_text, 1500),
        "skills": skills,
        "spans": spans,
        "tool_names": [s["name"] for s in spans],
        "eval": evaluation,
        "meta": meta or {},
    }
    path = traces_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(turn, ensure_ascii=False) + "\n")
    return turn


def load_turns(
    project_dir: Path, *, limit: Optional[int] = None
) -> list[dict[str, Any]]:
    path = traces_path(project_dir)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if limit is not None and limit > 0:
        return rows[-limit:]
    return rows
