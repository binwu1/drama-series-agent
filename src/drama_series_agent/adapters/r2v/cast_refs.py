# -*- coding: utf-8 -*-
"""Resolve cast anchors / voices under data/cast/{series}/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from drama_series_agent.adapters.paths import get_data_path


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name.strip())


def resolve_cast_series_id(
    *,
    cli_series: Optional[str],
    meta_series: Optional[str],
    shot_series: Optional[str],
    project_hint: Optional[str] = None,
) -> str:
    for candidate in (cli_series, shot_series, meta_series, project_hint):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    raise ValueError(
        "cast_series_id required: set episode-meta.cast_series_id, "
        "shot.cast_series_id, or pass --cast-series"
    )


def resolve_character_anchor(series_id: str, character_name: str) -> Path:
    series_dir = Path(get_data_path("cast", series_id))
    exts = (".png", ".jpg", ".jpeg", ".webp")
    candidates = [character_name, _safe_filename(character_name)]
    # Prefer 916 portrait stems used by some pipelines
    if not character_name.endswith("916"):
        candidates.append(f"{character_name}916")
        candidates.append(f"{_safe_filename(character_name)}916")

    for folder in (series_dir, series_dir / "draft"):
        for name in candidates:
            for ext in exts:
                direct = folder / f"{name}{ext}"
                if direct.is_file() and direct.stat().st_size > 1024:
                    return direct.resolve()

    manifest = series_dir / "series_manifest.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        entry = data.get(character_name) or {}
        if isinstance(entry, dict) and entry.get("path"):
            p = Path(str(entry["path"]))
            if p.is_file() and p.stat().st_size > 1024:
                return p.resolve()

    raise FileNotFoundError(
        f"Cast anchor not found for [{series_id}] / {character_name} under {series_dir}"
    )


def resolve_character_voice(series_id: str, character_name: str) -> Path:
    series_dir = Path(get_data_path("cast", series_id))
    voices = series_dir / "voices"
    stems = [character_name, _safe_filename(character_name)]
    for stem in stems:
        for ext in (".wav", ".mp3", ".flac", ".m4a"):
            p = voices / f"{stem}{ext}"
            if p.is_file() and p.stat().st_size > 0:
                return p.resolve()
    raise FileNotFoundError(
        f"Cast voice not found for [{series_id}] / {character_name} "
        f"(expected data/cast/{series_id}/voices/)"
    )


def resolve_ref_image_paths(
    series_id: str,
    first_frame: Path,
    ref_characters: List[str],
) -> List[Path]:
    paths = [first_frame.resolve()]
    for name in ref_characters:
        paths.append(resolve_character_anchor(series_id, name))
    if len(paths) > 9:
        raise ValueError("total ref images exceed 9")
    return paths


def resolve_ref_audio_paths(series_id: str, ref_voices: List[str]) -> List[Path]:
    return [resolve_character_voice(series_id, name) for name in (ref_voices or [])]
