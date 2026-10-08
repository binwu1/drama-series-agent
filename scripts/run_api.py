#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run Drama Series Agent HTTP API (FastAPI)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("DRAMA_SERIES_ROOT", str(ROOT))


def main() -> None:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from drama_series_agent.api.routers.series import router as series_router

    p = argparse.ArgumentParser()
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


if __name__ == "__main__":
    main()
