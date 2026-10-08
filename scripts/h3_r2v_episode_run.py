#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI wrapper for MiniMax H3 R2V episode render (drama-series-agent).

Usage:
  python scripts/h3_r2v_episode_run.py --project templates/西游记 --episode EP001
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

os.environ.setdefault("DRAMA_SERIES_ROOT", str(_ROOT))


def main() -> None:
    from drama_series_agent.cli import run_episode_main

    # Allow `python scripts/h3_r2v_episode_run.py --project ...` without subcommand
    run_episode_main()


if __name__ == "__main__":
    main()
