# -*- coding: utf-8 -*-
"""OpenAI-style tool schemas for Hermes Agent Stage1 intake."""

from __future__ import annotations

from typing import Any


def tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "intake_detect_inputs",
                "description": (
                    "Scan file/dir paths; classify script|image|audio|unknown; "
                    "return sha256, size, optional duration/resolution."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Absolute or project-relative paths",
                        }
                    },
                    "required": ["paths"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "intake_ask_slot",
                "description": (
                    "Return ≤3 structured Stage1 questions for missing slots "
                    "(title, has_script, has_images, has_audio, goal, …)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "missing": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "max_ask": {"type": "integer", "default": 3},
                    },
                    "required": ["missing"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "project_scaffold",
                "description": (
                    "Create Hermes projects/{slug} truth tree and mount targets "
                    "dramas/{slug}, templates/{slug}, data/cast/{slug}."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "slug": {"type": "string"},
                        "projects_root": {"type": "string"},
                        "drama_series_root": {"type": "string"},
                        "goal": {"type": "string"},
                    },
                    "required": ["title"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "script_ingest",
                "description": (
                    "Copy scripts into 输入/ (immutable) and dramas/{slug}/输入 mirror; "
                    "update intake_manifest. Does NOT promote to canonical screenplay."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "script_kind": {
                            "type": "string",
                            "enum": [
                                "screenplay",
                                "outline",
                                "novel",
                                "fragment",
                            ],
                        },
                    },
                    "required": ["project_dir", "paths"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "cast_image_ingest",
                "description": (
                    "Ingest cast images into data/cast/{slug}; unassigned if no names."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "character_names": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["project_dir", "paths"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "voice_ingest",
                "description": (
                    "Ingest 2–15s reference voices into data/cast/{slug}/voices/."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "character_names": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["project_dir", "paths"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "intake_write_manifest",
                "description": "Write intake_manifest.json and refresh case_code/gaps.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "defer_images": {"type": "boolean"},
                        "defer_audio": {"type": "boolean"},
                    },
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "intake_gap_report",
                "description": (
                    "Build Stage2 handoff packet + human gap_report.md."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                    },
                    "required": ["project_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "memory_upsert_project",
                "description": (
                    "Append verified facts to projects/{slug}/memory/PROJECT.md."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string"},
                        "facts": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "hermes_memory_md": {"type": "string"},
                    },
                    "required": ["project_dir", "facts"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_intake",
                "description": (
                    "One-shot Stage1: scaffold + detect + ingest + manifest + handoff."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "slug": {"type": "string"},
                        "script_kind": {"type": "string"},
                        "image_names": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "voice_names": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "defer_images": {"type": "boolean"},
                        "defer_audio": {"type": "boolean"},
                        "projects_root": {"type": "string"},
                        "drama_series_root": {"type": "string"},
                    },
                    "required": ["title"],
                },
            },
        },
    ]
