from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional


def extract_tail_frame(video_path: Path, out_png: Path) -> Path:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-sseof",
        "-0.05",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        str(out_png),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    if not out_png.is_file():
        raise RuntimeError(f"tail frame not written: {out_png}")
    return out_png


def _trim_head(src: Path, dest: Path, seconds: float) -> Path:
    """Drop the first ``seconds`` of video+audio (accurate output seek)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-ss",
        f"{seconds:.3f}",
        "-map",
        "0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    if not dest.is_file():
        raise RuntimeError(f"trim failed: {src} -> {dest}")
    return dest


def concat_videos(
    paths: List[Path],
    out_path: Path,
    *,
    trim_head_seconds: float = 0.3,
) -> Path:
    """Concatenate shot clips into ``out_path``.

    By default drops the first 0.3s of each shot (opening noise / boom on H3).
    Pass ``trim_head_seconds=0`` to disable.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not paths:
        raise ValueError("concat_videos: empty paths")

    trim_dir: Optional[Path] = None
    concat_inputs: List[Path] = list(paths)
    try:
        if trim_head_seconds and trim_head_seconds > 0:
            trim_dir = Path(
                tempfile.mkdtemp(
                    prefix="h3_concat_trim_", dir=str(out_path.parent)
                )
            )
            trimmed: List[Path] = []
            for i, p in enumerate(paths):
                dest = trim_dir / f"{i:04d}_{p.stem}_t{trim_head_seconds:.1f}.mp4"
                trimmed.append(_trim_head(p, dest, trim_head_seconds))
            concat_inputs = trimmed

        lst = out_path.with_suffix(".txt")
        lines = []
        for p in concat_inputs:
            # ffmpeg concat demuxer: escape single quotes in path
            pos = p.resolve().as_posix().replace("'", "'\\''")
            lines.append(f"file '{pos}'\n")
        lst.write_text("".join(lines), encoding="utf-8")

        # Re-encode when we trimmed (codecs already aligned); copy when untouched.
        if trim_head_seconds and trim_head_seconds > 0:
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(lst),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(out_path),
            ]
        else:
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(lst),
                "-c",
                "copy",
                str(out_path),
            ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path
    finally:
        if trim_dir is not None and trim_dir.is_dir():
            for f in trim_dir.glob("*"):
                try:
                    f.unlink()
                except OSError:
                    pass
            try:
                trim_dir.rmdir()
            except OSError:
                pass
