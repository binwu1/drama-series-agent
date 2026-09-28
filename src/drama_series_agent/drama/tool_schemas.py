# -*- coding: utf-8 -*-
"""OpenAI-style tool schemas for S1-B enrich + S2/S3."""

from __future__ import annotations

from typing import Any


def tool_schemas_s1_enrich() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "list_literary_episodes",
                "description": "List episode md files + draft/dirty/accepted status.",
                "parameters": {
                    "type": "object",
                    "properties": {"project_dir": {"type": "string"}},
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_literary_episode",
                "description": "Read full episode markdown for Studio / Agent.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                    },
                    "required": ["project_dir", "episode_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "save_literary_episode",
                "description": "Save episode markdown; invalidates literary Accept by default.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "content": {"type": "string"},
                        "invalidate": {"type": "boolean"},
                    },
                    "required": ["project_dir", "episode_id", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "open_literary_external",
                "description": "Open episode file in OS default editor (Mode C).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                    },
                    "required": ["project_dir", "episode_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "open_literary_folder",
                "description": "Open episodes/ folder in file manager.",
                "parameters": {
                    "type": "object",
                    "properties": {"project_dir": {"type": "string"}},
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "import_literary_file",
                "description": "Import external md/txt into episodes/ (+ immutable 输入/).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "source_path": {"type": "string"},
                        "episode_id": {"type": "string"},
                    },
                    "required": ["project_dir", "source_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_cast_assets",
                "description": "Cast wall: draft/final paths + status per character.",
                "parameters": {
                    "type": "object",
                    "properties": {"project_dir": {"type": "string"}},
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "upload_cast_image",
                "description": "User upload → draft/{character}; invalidates cast Accept.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "character": {"type": "string"},
                        "source_path": {"type": "string"},
                    },
                    "required": ["project_dir", "character", "source_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reject_cast_image",
                "description": "Move draft cast image to _history.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "character": {"type": "string"},
                    },
                    "required": ["project_dir", "character"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "open_cast_folder",
                "description": "Open cast draft/ or cast/ in file manager.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "draft": {"type": "boolean"},
                    },
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "invalidate_accept",
                "description": "Clear literary/cast/all Accept gates after edits.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "scope": {
                            "type": "string",
                            "enum": ["literary", "cast", "all"],
                        },
                        "reason": {"type": "string"},
                        "character": {"type": "string"},
                    },
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_literary_generate",
                "description": (
                    "写文学草稿（0xsline 技能）。"
                    "续写第N集时传 episode_ids=['ep00N']（如 ep002），"
                    "不要口头宣称已生成；须等本工具返回成功。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "premise": {"type": "string"},
                        "episode_count": {"type": "integer"},
                        "genre": {"type": "string"},
                        "episode_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "revision_notes": {"type": "string"},
                        "run_in_background": {"type": "boolean"},
                    },
                    "required": ["project_dir", "premise"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "accept_literary_package",
                "description": "Web Accept literary drafts → s1_gate.literary_accepted.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "decided_by": {"type": "string"},
                    },
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "extract_cast_table",
                "description": "Build cast_table.json from literary / name hints.",
                "parameters": {
                    "type": "object",
                    "properties": {"project_dir": {"type": "string"}},
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_cast_image_generate",
                "description": "S1-B: cast drafts; optional revision_notes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "characters": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "style": {"type": "string"},
                        "revision_notes": {"type": "string"},
                        "run_in_background": {"type": "boolean"},
                    },
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "accept_cast_images",
                "description": "Batch or per-character Accept cast drafts → cast_leads_accepted.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "characters": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "decided_by": {"type": "string"},
                    },
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mark_audio_deferred",
                "description": "Allow soft-voice R2V; audio not required for S2 gate.",
                "parameters": {
                    "type": "object",
                    "properties": {"project_dir": {"type": "string"}},
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_s1_gate_status",
                "description": "Read series_runtime.s1_gate + enrich_jobs + gaps.",
                "parameters": {
                    "type": "object",
                    "properties": {"project_dir": {"type": "string"}},
                    "required": ["project_dir"],
                },
            },
        },
    ]


def tool_schemas_s2_s3() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "select_workflow",
                "description": "Persist series default workflow + aspect/context_ir into series_runtime.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "workflow": {"type": "string"},
                        "aspect": {"type": "string"},
                        "context_ir": {
                            "type": "string",
                            "enum": ["off", "local", "api"],
                        },
                    },
                    "required": ["project_dir", "workflow"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "enqueue_build_episode_jsonl",
                "description": "S2: build episode-run.jsonl (+ meta) from literary/cast scaffold.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "force": {"type": "boolean"},
                        "shot_count": {"type": "integer"},
                        "run_in_background": {"type": "boolean"},
                    },
                    "required": ["project_dir", "episode_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "validate_episode_run",
                "description": "S2: validate episode-run.jsonl before Comfy.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                    },
                    "required": ["project_dir", "episode_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_s2_build_and_comfy",
                "description": "用户明确说可以生成视频/出片后调用。一次完成：构建 jsonl → 校验 → 后台入队 Comfy。成片结束后系统自动进入后续阶段。不要让用户自己点构建按钮；入队后提示去工作台的生成进度页。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "force_build": {"type": "boolean"},
                        "from_shot": {"type": "string"},
                        "run_comfy_in_background": {"type": "boolean"},
                        "skip_comfy": {"type": "boolean"},
                    },
                    "required": ["project_dir", "episode_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "resume_from_shot",
                "description": "Resume Comfy episode from shot id (same as enqueue with from_shot).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "from_shot": {"type": "string"},
                        "force": {"type": "boolean"},
                        "run_in_background": {"type": "boolean"},
                    },
                    "required": ["project_dir", "episode_id", "from_shot"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "prefetch_next_episode",
                "description": "S3: resolve EP + check literary/cast/tail/workflow readiness.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "user_text": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ensure_literary_for_episode",
                "description": "S3: if literary missing, generate that episode draft (needs Accept).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "premise": {"type": "string"},
                        "revision_notes": {"type": "string"},
                    },
                    "required": ["project_dir", "episode_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "continue_series",
                "description": (
                    "S3 entry for「生成第二集」: prefetch → literary gap or S2 build/Comfy."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "user_text": {"type": "string"},
                        "text": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "auto_build_comfy": {"type": "boolean"},
                        "force_build": {"type": "boolean"},
                        "skip_comfy": {"type": "boolean"},
                        "run_comfy_in_background": {"type": "boolean"},
                    },
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_series_progress",
                "description": "S3 dashboard: episodes status, tails, next_episode.",
                "parameters": {
                    "type": "object",
                    "properties": {"project_dir": {"type": "string"}},
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "propose_voice_harvest",
                "description": "List shot videos for optional voice harvest (never auto hard-lock).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                    },
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_episode_shots",
                "description": "S4: list shots with accept/lock/video flags.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                    },
                    "required": ["project_dir", "episode_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_shot_prompt",
                "description": "S4: read full video_prompt for one shot.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "shot_id": {"type": "string"},
                    },
                    "required": ["project_dir", "episode_id", "shot_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "patch_shot_prompt",
                "description": "S4: edit shot prompt/duration in jsonl (blocked if locked).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "shot_id": {"type": "string"},
                        "video_prompt": {"type": "string"},
                        "duration_seconds": {"type": "number"},
                        "validate": {"type": "boolean"},
                    },
                    "required": ["project_dir", "episode_id", "shot_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "accept_shot",
                "description": "S4: accept one shot; optional lock.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "shot_id": {"type": "string"},
                        "lock": {"type": "boolean"},
                        "decided_by": {"type": "string"},
                    },
                    "required": ["project_dir", "episode_id", "shot_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reject_shot",
                "description": "S4: mark shot rejected/failed for rerun.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "shot_id": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["project_dir", "episode_id", "shot_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lock_shot",
                "description": "S4: lock shot — no patch/rerun without force.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "shot_id": {"type": "string"},
                    },
                    "required": ["project_dir", "episode_id", "shot_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "unlock_shot",
                "description": "S4: unlock shot for edit/rerun.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "shot_id": {"type": "string"},
                    },
                    "required": ["project_dir", "episode_id", "shot_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "accept_episode",
                "description": "S4: accept all shots; optional lock_all.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "lock_all": {"type": "boolean"},
                        "decided_by": {"type": "string"},
                    },
                    "required": ["project_dir", "episode_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "rerun_shots",
                "description": "S4: Comfy rerun from earliest shot; locked shots need force=True.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "shot_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "force": {"type": "boolean"},
                        "run_in_background": {"type": "boolean"},
                    },
                    "required": ["project_dir", "episode_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "resolve_episode_intent",
                "description": "Parse user text to EPxxx using series_runtime.next_episode fallback.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["project_dir", "text"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_job_status",
                "description": "Return recent JobEvents for a job_id from the event bus / jsonl.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                        "series_id": {"type": "string"},
                    },
                    "required": ["job_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "on_episode_complete",
                "description": "S3 hook: update series_runtime, tails, memory, emit EpisodeDone/Milestone.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "master_path": {"type": "string"},
                        "jsonl_path": {"type": "string"},
                        "workflow": {"type": "string"},
                        "job_id": {"type": "string"},
                        "failed_shots": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["project_dir", "episode_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "enqueue_comfy_episode",
                "description": (
                    "Enqueue async H3 R2V episode render (background thread). "
                    "Returns job_id immediately; progress via EventBus / get_job_status."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "episode_id": {"type": "string"},
                        "from_shot": {"type": "string"},
                        "force": {"type": "boolean"},
                        "cast_series": {"type": "string"},
                        "context_ir": {"type": "string"},
                        "run_in_background": {"type": "boolean"},
                    },
                    "required": ["project_dir", "episode_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_active_jobs",
                "description": "List in-memory Comfy/enrich job snapshots for Job Panel.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "series_id": {"type": "string"},
                    },
                },
            },
        },
    ]


def tool_schemas_all() -> list[dict[str, Any]]:
    return tool_schemas_s1_enrich() + tool_schemas_s2_s3()
