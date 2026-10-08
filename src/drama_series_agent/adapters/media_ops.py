# -*- coding: utf-8 -*-
"""Local media helpers (ffmpeg): tail frame extract + shot concat."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import List, Optional


@lru_cache(maxsize=1)
def resolve_ffmpeg() -> str:
    """Locate ffmpeg binary. Raises FileNotFoundError with a clear message."""
    env = (
        os.environ.get("FFMPEG_PATH")
        or os.environ.get("FFMPEG_BINARY")
        or os.environ.get("IMAGEIO_FFMPEG_EXE")
        or ""
    ).strip().strip('"')
    candidates: list[str] = []
    if env:
        candidates.append(env)
    which = shutil.which("ffmpeg")
    if which:
        candidates.append(which)
    try:
        import imageio_ffmpeg

        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:  # noqa: BLE001
        pass
    # Common Windows / portable layouts
    home = Path.home()
    candidates.extend(
        [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            str(home / "scoop" / "shims" / "ffmpeg.exe"),
            str(
                home
                / "AppData"
                / "Local"
                / "Microsoft"
                / "WinGet"
                / "Links"
                / "ffmpeg.exe"
            ),
            r"E:\Program Files\Pixelle-Video-v0.1.15-win64\ffmpeg\bin\ffmpeg.exe",
            r"E:\Program Files\Pixelle-Video-v0.1.15-win64\ffmpeg\ffmpeg.exe",
        ]
    )
    for c in candidates:
        p = Path(c)
        if p.is_file():
            return str(p.resolve())
    raise FileNotFoundError(
        "找不到 ffmpeg（WinError 2）。镜头成片后需要它抽取尾帧才能续拍下一镜。\n"
        "请任选其一：\n"
        "1) 安装 ffmpeg 并加入 PATH；\n"
        "2) 设置环境变量 FFMPEG_PATH=完整路径\\ffmpeg.exe；\n"
        "3) pip install imageio-ffmpeg（本仓库已声明依赖）。"
    )


def _run_ffmpeg(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"执行失败（找不到程序）：{cmd[0]!r}。{resolve_ffmpeg.__doc__}"
        ) from e
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"ffmpeg failed ({e.returncode}): {err}") from e


def extract_tail_frame(video_path: Path, out_png: Path) -> Path:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    ff = resolve_ffmpeg()
    cmd = [
        ff,
        "-y",
        "-sseof",
        "-0.05",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        str(out_png),
    ]
    _run_ffmpeg(cmd)
    if not out_png.is_file():
        raise RuntimeError(f"tail frame not written: {out_png}")
    return out_png


def _trim_head(src: Path, dest: Path, seconds: float) -> Path:
    """Drop the first ``seconds`` of video+audio (accurate output seek)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    ff = resolve_ffmpeg()
    cmd = [
        ff,
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
    _run_ffmpeg(cmd)
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

    ff = resolve_ffmpeg()
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
                ff,
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
                ff,
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
        _run_ffmpeg(cmd)
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
