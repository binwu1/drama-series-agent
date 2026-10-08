#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI for Stage1 short-drama intake (drama-series-agent).

Examples:
  python scripts/hermes_drama_intake.py --title 起死
  python scripts/hermes_drama_intake.py --title 起死 --paths ./inbox --defer-audio
  python scripts/hermes_drama_intake.py --dump-schemas
  python scripts/hermes_drama_intake.py --call project_scaffold --args-json "{\"title\":\"起死\"}"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

os.environ.setdefault("DRAMA_SERIES_ROOT", str(_ROOT))


def main() -> None:
    p = argparse.ArgumentParser(description="Stage1 drama intake")
    p.add_argument("--title", default=None, help="Drama title / working title")
    p.add_argument("--slug", default=None)
    p.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Script / image / audio files or directories to ingest",
    )
    p.add_argument(
        "--script-kind",
        default=None,
        choices=("screenplay", "outline", "novel", "fragment"),
    )
    p.add_argument("--image-names", nargs="*", default=None)
    p.add_argument("--voice-names", nargs="*", default=None)
    p.add_argument("--defer-images", action="store_true")
    p.add_argument("--defer-audio", action="store_true")
    p.add_argument("--projects-root", type=Path, default=None)
    p.add_argument("--drama-series-root", type=Path, default=None)
    p.add_argument("--dump-schemas", action="store_true")
    p.add_argument("--call", default=None, help="Dispatch a single tool by name")
    p.add_argument("--args-json", default="{}", help='JSON object for --call')
    args = p.parse_args()

    if args.dump_schemas:
        from drama_series_agent.intake.tool_schemas import tool_schemas

        print(json.dumps(tool_schemas(), ensure_ascii=False, indent=2))
        return

    if args.call:
        from drama_series_agent.intake.dispatch import handle_tool_call

        print(handle_tool_call(args.call, json.loads(args.args_json)))
        return

    if not args.title:
        p.error("--title is required unless --dump-schemas / --call")

    from drama_series_agent.intake.pipeline import run_intake

    result = run_intake(
        title=args.title,
        paths=[Path(x) for x in args.paths],
        slug=args.slug,
        script_kind=args.script_kind,
        image_names=args.image_names,
        voice_names=args.voice_names,
        defer_images=args.defer_images,
        defer_audio=args.defer_audio,
        projects_root=args.projects_root,
        drama_series_root=args.drama_series_root or _ROOT,
    )
    summary = {
        "ok": True,
        "project_id": result["project_id"],
        "project_dir": result["project_dir"],
        "case_code": result["handoff"]["case"]["code"],
        "ready_for_stage2": result["ready_for_stage2"],
        "gaps": result["handoff"]["gaps"],
        "suggested_skills": result["handoff"]["suggested_skills"],
        "blocks_visual": result["handoff"]["blocks_visual"],
        "ask": result["ask"],
        "gap_report_path": str(Path(result["project_dir"]) / "gap_report.md"),
        "handoff_path": str(Path(result["project_dir"]) / "handoff_stage2.json"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
