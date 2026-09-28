# -*- coding: utf-8 -*-
"""S3 completion hook: update runtime + tails + memory after EpisodeDone."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.drama.job_events import JobEvent, JobEventType, JobKind
from drama_series_agent.drama.runtime import (
    load_runtime,
    next_episode_id,
    save_runtime,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_templates_dir(project_dir: Path) -> Path:
    """Local copy to avoid circular import with comfy_worker."""
    project_json = Path(project_dir) / "project.json"
    if project_json.is_file():
        data = json.loads(project_json.read_text(encoding="utf-8"))
        td = (data.get("mounts") or {}).get("templates_dir")
        if td and Path(td).is_dir():
            return Path(td)
    if (Path(project_dir) / "run").is_dir():
        return Path(project_dir)
    raise FileNotFoundError(f"templates_dir not found for {project_dir}")


def _ensure_episode_tail(
    templates_dir: Path,
    episode_id: str,
    *,
    master_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Ensure continuity/episode-tails.json has an entry (runner may already write it)."""
    continuity = templates_dir / "continuity"
    continuity.mkdir(parents=True, exist_ok=True)
    path = continuity / "episode-tails.json"
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = {}

    existing = data.get(episode_id)
    if isinstance(existing, dict) and existing.get("tail_frame"):
        tf = Path(str(existing["tail_frame"]))
        if tf.is_file():
            return existing

    # Discover last shot tail_frame under output/{EP}/shots
    shots_root = templates_dir / "output" / episode_id / "shots"
    best: Optional[Path] = None
    best_shot = None
    if shots_root.is_dir():
        for d in sorted(shots_root.iterdir()):
            cand = d / "tail_frame.png"
            if cand.is_file():
                best = cand
                best_shot = d.name
    if best is None:
        return existing if isinstance(existing, dict) else None

    row = {
        "tail_frame": str(best.resolve()),
        "tail_shot_id": best_shot,
        "master_path": master_path,
        "updated_at": _now(),
    }
    data[episode_id] = row
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return row


def on_episode_complete(
    project_dir: Path,
    *,
    episode_id: str,
    master_path: Optional[str] = None,
    jsonl_path: Optional[str] = None,
    workflow: Optional[str] = None,
    failed_shots: Optional[list[str]] = None,
    bus: Any = None,
    job_id: Optional[str] = None,
) -> dict[str, Any]:
    """Patch series_runtime + tails + memory after a successful (or partial) render."""
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    failed = list(failed_shots or [])

    master_ok = bool(master_path and Path(str(master_path)).is_file())

    ep = dict(rt.episodes.get(episode_id) or {})
    if failed and master_path:
        status = "partial"
    elif failed and not master_path:
        status = "failed"
    else:
        status = "done"
    ep.update(
        {
            "status": status,
            "workflow": workflow or ep.get("workflow") or rt.default_workflow,
            "master_path": master_path or ep.get("master_path"),
            "jsonl_path": jsonl_path or ep.get("jsonl_path"),
            "failed_shots": failed,
            "resume_from_shot": failed[0]
            if failed and failed[0] != "master_missing"
            else ep.get("resume_from_shot"),
            "completed_at": _now(),
        }
    )
    rt.episodes[episode_id] = ep

    if status in ("done", "partial", "accepted"):
        rt.last_completed_episode = episode_id
        rt.next_episode = next_episode_id(episode_id)
        rt.stage = "s3_episode_done" if status != "failed" else "s2_rendering"

    if job_id and job_id in rt.active_job_ids:
        rt.active_job_ids = [j for j in rt.active_job_ids if j != job_id]

    # Continuity tails (best-effort)
    tail_row = None
    try:
        templates_dir = _resolve_templates_dir(project_dir)
        tail_row = _ensure_episode_tail(
            templates_dir, episode_id, master_path=master_path
        )
        if tail_row:
            ep["tail_frame"] = tail_row.get("tail_frame")
            ep["tail_shot_id"] = tail_row.get("tail_shot_id")
            rt.episodes[episode_id] = ep
    except Exception:  # noqa: BLE001
        tail_row = None

    save_runtime(project_dir, rt)

    # L1 project memory fact
    mem = project_dir / "memory" / "PROJECT.md"
    mem.parent.mkdir(parents=True, exist_ok=True)
    line = (
        f"- episode `{episode_id}` status={status}"
        f" next={rt.next_episode}"
        f" master={ep.get('master_path') or '-'}"
        f" tail={ep.get('tail_shot_id') or '-'}\n"
    )
    if not mem.is_file():
        mem.write_text("# Project memory\n\n## Stable facts\n\n", encoding="utf-8")
    prev = mem.read_text(encoding="utf-8")
    if line.strip() not in prev:
        with mem.open("a", encoding="utf-8") as f:
            f.write(line)

    if rt.next_episode and status in ("done", "partial"):
        msg = (
            f"{rt.series_id} {episode_id} {status}; "
            f"say「生成{rt.next_episode}」or continue_series to proceed"
        )
    else:
        msg = f"{rt.series_id} {episode_id} {status}"
    milestone = JobEvent(
        event_type=JobEventType.MILESTONE,
        job_id=job_id or f"complete_{episode_id}",
        job_kind=JobKind.COMFY_EPISODE,
        series_id=rt.series_id,
        episode_id=episode_id,
        message=msg,
        progress=1.0 if status == "done" else None,
        paths={"master": master_path} if master_path else {},
        phase="done" if status == "done" else "failed",
    )
    if bus is not None:
        bus.publish(milestone)
        if status == "done":
            bus.publish(
                JobEvent(
                    event_type=JobEventType.EPISODE_DONE,
                    job_id=job_id or milestone.job_id,
                    job_kind=JobKind.COMFY_EPISODE,
                    series_id=rt.series_id,
                    episode_id=episode_id,
                    workflow=ep.get("workflow"),
                    progress=1.0,
                    phase="done",
                    paths={"master": master_path} if master_path else {},
                )
            )

    return {
        "ok": True,
        "runtime": rt.to_dict(),
        "milestone": milestone.to_dict(),
        "tail": tail_row,
        "master_exists": master_ok,
        "voice_harvest_hint": (
            "Call propose_voice_harvest for optional manual voice clips"
            if status == "done"
            else None
        ),
    }
