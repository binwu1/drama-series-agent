# -*- coding: utf-8 -*-
"""Dispatch Hermes Stage1 tool calls by name."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drama_series_agent.intake.fs_util import detect_inputs
from drama_series_agent.intake.ingest import (
    cast_image_ingest,
    mark_deferred,
    script_ingest,
    voice_ingest,
)
from drama_series_agent.intake.manifest import (
    build_handoff,
    gap_report_text,
    load_manifest,
    write_handoff,
    write_manifest,
)
from drama_series_agent.intake.memory_ops import ask_slots, memory_upsert_project
from drama_series_agent.intake.pipeline import run_intake
from drama_series_agent.intake.scaffold import scaffold_project


def handle_tool_call(name: str, args: dict[str, Any]) -> str:
    """Execute a Stage1 tool; return JSON string for Hermes."""
    try:
        result = _dispatch(name, args or {})
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {"ok": False, "error": str(e), "tool": name}, ensure_ascii=False
        )


def _dispatch(name: str, args: dict[str, Any]) -> Any:
    if name == "intake_detect_inputs":
        paths = [Path(p) for p in args["paths"]]
        return {"ok": True, "items": detect_inputs(paths)}

    if name == "intake_ask_slot":
        return {
            "ok": True,
            **ask_slots(list(args.get("missing") or []), max_ask=int(args.get("max_ask") or 3)),
        }

    if name == "project_scaffold":
        return {
            "ok": True,
            **scaffold_project(
                title=args["title"],
                slug=args.get("slug"),
                projects_root=Path(args["projects_root"])
                if args.get("projects_root")
                else None,
                drama_series_root=Path(args["drama_series_root"])
                if args.get("drama_series_root")
                else None,
                goal=args.get("goal") or "full_pipeline",
            ),
        }

    if name == "script_ingest":
        m = script_ingest(
            Path(args["project_dir"]),
            [Path(p) for p in args["paths"]],
            script_kind=args.get("script_kind"),
        )
        write_manifest(Path(args["project_dir"]), m)
        return {"ok": True, "manifest": m.to_dict()}

    if name == "cast_image_ingest":
        m = cast_image_ingest(
            Path(args["project_dir"]),
            [Path(p) for p in args["paths"]],
            character_names=args.get("character_names"),
        )
        write_manifest(Path(args["project_dir"]), m)
        return {"ok": True, "manifest": m.to_dict()}

    if name == "voice_ingest":
        m = voice_ingest(
            Path(args["project_dir"]),
            [Path(p) for p in args["paths"]],
            character_names=args.get("character_names"),
        )
        write_manifest(Path(args["project_dir"]), m)
        return {"ok": True, "manifest": m.to_dict()}

    if name == "intake_write_manifest":
        project_dir = Path(args["project_dir"])
        m = load_manifest(project_dir)
        if args.get("defer_images"):
            mark_deferred(m, "images")
        if args.get("defer_audio"):
            mark_deferred(m, "audio")
        write_manifest(project_dir, m)
        return {"ok": True, "manifest": m.to_dict()}

    if name == "intake_gap_report":
        project_dir = Path(args["project_dir"])
        m = load_manifest(project_dir)
        handoff = build_handoff(project_dir, m)
        write_handoff(project_dir, handoff)
        report = gap_report_text(m, handoff)
        (project_dir / "gap_report.md").write_text(report, encoding="utf-8")
        return {"ok": True, "handoff": handoff, "gap_report": report}

    if name == "memory_upsert_project":
        return {
            "ok": True,
            **memory_upsert_project(
                Path(args["project_dir"]),
                list(args.get("facts") or []),
                hermes_memory_md=Path(args["hermes_memory_md"])
                if args.get("hermes_memory_md")
                else None,
            ),
        }

    if name == "run_intake":
        return {
            "ok": True,
            **run_intake(
                title=args["title"],
                paths=[Path(p) for p in (args.get("paths") or [])],
                slug=args.get("slug"),
                script_kind=args.get("script_kind"),
                image_names=args.get("image_names"),
                voice_names=args.get("voice_names"),
                defer_images=bool(args.get("defer_images")),
                defer_audio=bool(args.get("defer_audio")),
                projects_root=Path(args["projects_root"])
                if args.get("projects_root")
                else None,
                drama_series_root=Path(args["drama_series_root"])
                if args.get("drama_series_root")
                else None,
            ),
        }

    raise ValueError(f"unknown Stage1 tool: {name}")
