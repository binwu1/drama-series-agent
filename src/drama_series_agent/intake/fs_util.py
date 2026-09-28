# -*- coding: utf-8 -*-
"""Filesystem helpers: hash, copy-immutable, media probes."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.intake.constants import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    SCRIPT_EXTENSIONS,
    VOICE_MAX_SECONDS,
    VOICE_MIN_SECONDS,
)


def file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def classify_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in SCRIPT_EXTENSIONS:
        return "script"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    return "unknown"


def copy_immutable(src: Path, dest_dir: Path, *, prefix: str = "") -> Path:
    """Copy into dest_dir without overwriting; collision → _1, _2…"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}{src.name}" if prefix else src.name
    dest = dest_dir / name
    if dest.exists() and file_sha256(dest) == file_sha256(src):
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 1
    while dest.exists():
        dest = dest_dir / f"{stem}_{n}{suffix}"
        n += 1
    shutil.copy2(src, dest)
    return dest


def probe_audio_duration_seconds(path: Path) -> Optional[float]:
    """Best-effort duration via ffprobe; None if unavailable."""
    import json
    import shutil
    import subprocess

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        out = subprocess.check_output(
            [
                ffprobe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(path),
            ],
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        data = json.loads(out.decode("utf-8", errors="replace"))
        dur = data.get("format", {}).get("duration")
        return float(dur) if dur is not None else None
    except Exception:  # noqa: BLE001 — best-effort
        return None


def voice_quality_status(duration: Optional[float]) -> str:
    if duration is None:
        return "partial"  # cannot verify → do not hard-accept as ref_voice
    if VOICE_MIN_SECONDS <= duration <= VOICE_MAX_SECONDS:
        return "present"
    return "partial"


def probe_image_size(path: Path) -> Optional[tuple[int, int]]:
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as im:
            return im.size
    except Exception:  # noqa: BLE001
        return None


def detect_inputs(paths: list[Path]) -> list[dict[str, Any]]:
    """Scan user paths: files or directories → classified records."""
    results: list[dict[str, Any]] = []
    seen: set[Path] = set()

    def _one(p: Path) -> None:
        p = p.resolve()
        if p in seen or not p.exists():
            return
        seen.add(p)
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file():
                    _one(child)
            return
        kind = classify_path(p)
        rec: dict[str, Any] = {
            "path": str(p),
            "name": p.name,
            "kind": kind,
            "sha256": file_sha256(p),
            "bytes": p.stat().st_size,
        }
        if kind == "audio":
            dur = probe_audio_duration_seconds(p)
            rec["duration_seconds"] = dur
            rec["voice_status_hint"] = voice_quality_status(dur)
        if kind == "image":
            size = probe_image_size(p)
            if size:
                rec["width"], rec["height"] = size
        results.append(rec)

    for raw in paths:
        _one(Path(raw))
    return results
