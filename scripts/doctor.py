#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick environment check for drama-series-agent Quick Start."""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path


def _ok(msg: str) -> None:
    print(f"[OK]  {msg}")


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    failed = 0
    print(f"Python {sys.version.split()[0]}  root={root}")

    # Core imports
    try:
        import drama_series_agent  # noqa: F401
        from drama_series_agent.adapters.media_ops import resolve_ffmpeg
        from drama_series_agent.utils.skills_paths import (
            SKILL_H3_R2V,
            SKILL_INTAKE,
            SKILL_LITERARY,
            skill_root,
        )

        _ok("import drama_series_agent")
    except Exception as e:  # noqa: BLE001
        _fail(f"import drama_series_agent: {e}")
        return 1

    # ffmpeg
    try:
        ff = resolve_ffmpeg()
        r = subprocess.run([ff, "-version"], capture_output=True, text=True)
        line = (r.stdout or r.stderr or "").splitlines()[:1]
        ver = line[0] if line else "unknown"
        if r.returncode != 0:
            raise RuntimeError(ver)
        _ok(f"ffmpeg → {ff}")
        print(f"      {ver}")
    except Exception as e:  # noqa: BLE001
        _fail(f"ffmpeg: {e}")
        failed += 1

    # skills
    for name in (SKILL_INTAKE, SKILL_LITERARY, SKILL_H3_R2V):
        p = skill_root(name)
        if p:
            _ok(f"skill {name} → {p}")
        else:
            _fail(f"skill missing: {name} (expected under skills/{name})")
            failed += 1

    # optional render stack
    try:
        importlib.import_module("comfykit")
        _ok("comfykit (render extra)")
    except Exception as e:  # noqa: BLE001
        _fail(f"comfykit not installed (pip install -e '.[render]'): {e}")
        failed += 1

    # API router load
    try:
        from drama_series_agent.api.routers.series import router

        n = len(router.routes)
        if n < 10:
            raise RuntimeError(f"unexpectedly few routes: {n}")
        _ok(f"API router loaded ({n} routes)")
    except Exception as e:  # noqa: BLE001
        _fail(f"API router: {e}")
        failed += 1

    # console scripts (best-effort; may be absent if not on PATH)
    for name in ("drama-series-api", "drama-series-render"):
        which = shutil.which(name)
        if which:
            _ok(f"CLI {name} → {which}")
        else:
            local = root / ".venv" / "Scripts" / f"{name}.exe"
            if not local.is_file():
                local = root / ".venv" / "bin" / name
            if local.is_file():
                _ok(f"CLI {name} → {local}")
            else:
                _fail(f"CLI {name} not found (re-run pip install -e .)")
                failed += 1

    print()
    if failed:
        print(f"Doctor found {failed} issue(s).")
        return 1
    print("Doctor: environment looks ready for Quick Start.")
    print("Next: start ComfyUI, then .\\start.ps1 or ./start.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
