# -*- coding: utf-8 -*-
"""CLI entry points for drama-series-agent."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path


def _ensure_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    os.environ.setdefault("DRAMA_SERIES_ROOT", str(root))
    return root


def run_api_main() -> None:
    _ensure_path()
    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from drama_series_agent.api.routers.series import router as series_router

    p = argparse.ArgumentParser(description="Drama Series Agent API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()

    app = FastAPI(title="Drama Series Agent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(series_router, prefix="/api")
    uvicorn.run(app, host=args.host, port=args.port)


def run_episode_main() -> None:
    """Entry for console_script drama-series-render."""
    # argparse lives inside; allow `python -m drama_series_agent.cli render`
    if len(sys.argv) > 1 and sys.argv[1] in ("render", "run_episode"):
        sys.argv.pop(1)
    _run_episode_main_impl()


def _run_episode_main_impl() -> None:
    _ensure_path()
    p = argparse.ArgumentParser(description="Render one episode via ComfyUI R2V")
    p.add_argument(
        "--project",
        required=True,
        type=Path,
        help="Episode project root with run/{EP}.episode-run.jsonl",
    )
    p.add_argument("--episode", required=True)
    p.add_argument("--cast-series", default=None)
    p.add_argument("--from-shot", default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--context-ir", default="off", choices=("off", "local", "api"))
    p.add_argument(
        "--comfyui-url",
        default=None,
        help="Override COMFYUI_URL (default http://127.0.0.1:8188)",
    )
    args = p.parse_args()
    if args.comfyui_url:
        os.environ["COMFYUI_URL"] = args.comfyui_url

    from drama_series_agent.adapters.r2v.runner import run_episode

    def _progress(ev: dict) -> None:
        print(
            f"[{ev.get('type')}] shot={ev.get('shot_id')} "
            f"{ev.get('index')}/{ev.get('total')} {ev.get('phase') or ''}",
            flush=True,
        )

    master = asyncio.run(
        run_episode(
            project_root=args.project.resolve(),
            episode_id=args.episode,
            from_shot=args.from_shot,
            force=args.force,
            cast_series=args.cast_series,
            context_ir=args.context_ir,
            progress_callback=_progress,
        )
    )
    print(f"DONE {master}")


if __name__ == "__main__":
    run_api_main()
