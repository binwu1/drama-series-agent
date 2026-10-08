# -*- coding: utf-8 -*-
"""Aggregate per-episode render progress from run jsonl + output shots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.drama.comfy_worker import resolve_templates_dir
from drama_series_agent.drama.runtime import load_runtime


def _norm_ep(ep: str) -> str:
    ep = (ep or "").strip()
    if ep.lower().startswith("ep") and not ep.startswith("EP"):
        return "EP" + ep[2:]
    return ep


def _shot_rows(jsonl_path: Path) -> list[dict[str, Any]]:
    if not jsonl_path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(obj, dict) and obj.get("shot_id"):
            rows.append(obj)
    rows.sort(key=lambda r: int(r.get("order") or 0))
    return rows


def list_episode_progress(project_dir: Path) -> list[dict[str, Any]]:
    """Return episodes that have a run jsonl and/or runtime row / output."""
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    templates = resolve_templates_dir(project_dir)
    run_dir = templates / "run"
    out_root = templates / "output"

    ep_ids: set[str] = set()
    if run_dir.is_dir():
        for p in run_dir.glob("*.episode-run.jsonl"):
            ep_ids.add(p.name.split(".", 1)[0])
    for ep in (rt.episodes or {}):
        ep_ids.add(_norm_ep(str(ep)))
    if out_root.is_dir():
        for d in out_root.iterdir():
            if d.is_dir() and d.name.upper().startswith("EP"):
                ep_ids.add(_norm_ep(d.name))

    episodes: list[dict[str, Any]] = []
    for ep in sorted(ep_ids):
        episodes.append(build_episode_progress(project_dir, ep, rt=rt, templates=templates))
    return episodes


def build_episode_progress(
    project_dir: Path,
    episode_id: str,
    *,
    rt: Any = None,
    templates: Optional[Path] = None,
) -> dict[str, Any]:
    project_dir = Path(project_dir)
    ep = _norm_ep(episode_id)
    if rt is None:
        rt = load_runtime(project_dir)
    if templates is None:
        templates = resolve_templates_dir(project_dir)

    jsonl_path = templates / "run" / f"{ep}.episode-run.jsonl"
    meta_path = templates / "run" / f"{ep}.episode-meta.json"
    episode_out = templates / "output" / ep
    master = episode_out / "master.mp4"
    shots_root = episode_out / "shots"

    planned = _shot_rows(jsonl_path)
    runtime_ep = dict(rt.episodes.get(ep) or {})
    resume_from = str(runtime_ep.get("resume_from_shot") or "").strip() or None

    shots: list[dict[str, Any]] = []
    done_n = 0
    first_missing: Optional[str] = None
    for row in planned:
        sid = str(row.get("shot_id"))
        video = shots_root / sid / "video.mp4"
        tail = shots_root / sid / "tail_frame.png"
        has_video = video.is_file() and video.stat().st_size > 0
        has_tail = tail.is_file() and tail.stat().st_size > 0
        complete = has_video and has_tail
        if complete:
            done_n += 1
        elif first_missing is None:
            first_missing = sid
        shots.append(
            {
                "shot_id": sid,
                "order": row.get("order"),
                "duration_seconds": row.get("duration_seconds"),
                "has_video": has_video,
                "has_tail": has_tail,
                "complete": complete,
                "video_bytes": video.stat().st_size if has_video else 0,
            }
        )

    total = len(planned)
    all_complete = total > 0 and done_n == total
    master_ready = master.is_file() and master.stat().st_size > 0

    # Prefer explicit resume; else first incomplete shot for continue.
    continue_from = resume_from or first_missing

    status = str(runtime_ep.get("status") or "")
    if all_complete and master_ready:
        progress_status = "complete"
    elif done_n > 0 and done_n < total:
        progress_status = "partial"
    elif status in ("rendering", "interrupted"):
        progress_status = status
    elif total == 0:
        progress_status = "no_jsonl"
    elif done_n == 0:
        progress_status = "pending"
    else:
        progress_status = status or "unknown"

    return {
        "episode_id": ep,
        "jsonl_exists": jsonl_path.is_file(),
        "meta_exists": meta_path.is_file(),
        "shot_total": total,
        "shot_done": done_n,
        "all_shots_complete": all_complete,
        "master_ready": master_ready,
        "master_bytes": master.stat().st_size if master_ready else 0,
        "resume_from_shot": resume_from,
        "continue_from_shot": continue_from,
        "runtime_status": status or None,
        "progress_status": progress_status,
        "workflow": runtime_ep.get("workflow") or rt.default_workflow,
        "shots": shots,
    }


def rebuild_master_from_shots(project_dir: Path, episode_id: str) -> Path:
    """Concat existing shot videos into master.mp4 (order from jsonl)."""
    from drama_series_agent.adapters.media_ops import concat_videos

    ep = _norm_ep(episode_id)
    templates = resolve_templates_dir(Path(project_dir))
    jsonl_path = templates / "run" / f"{ep}.episode-run.jsonl"
    episode_out = templates / "output" / ep
    planned = _shot_rows(jsonl_path)
    if not planned:
        raise FileNotFoundError(f"missing run jsonl for {ep}")
    paths: list[Path] = []
    for row in planned:
        sid = str(row["shot_id"])
        video = episode_out / "shots" / sid / "video.mp4"
        if not video.is_file() or video.stat().st_size <= 0:
            raise FileNotFoundError(f"missing shot video: {sid}")
        paths.append(video)
    master = episode_out / "master.mp4"
    concat_videos(paths, master)
    return master.resolve()
