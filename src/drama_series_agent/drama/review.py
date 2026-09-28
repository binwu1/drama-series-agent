# -*- coding: utf-8 -*-
"""S4 Review: list/patch/accept/lock shots + rerun via Comfy."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.drama.comfy_worker import (
    enqueue_comfy_episode,
    resolve_templates_dir,
)
from drama_series_agent.drama.decisions import append_decision, hash_paths
from drama_series_agent.drama.event_bus import InMemoryEventBus, get_event_bus
from drama_series_agent.drama.job_events import JobEvent, JobEventType, JobKind
from drama_series_agent.drama.runtime import load_runtime, save_runtime
from drama_series_agent.adapters.r2v.schema import ShotRunLine, load_episode_run_jsonl
from drama_series_agent.adapters.r2v.validate import validate_episode_run


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonl_path(project_dir: Path, episode_id: str) -> Path:
    return resolve_templates_dir(project_dir) / "run" / f"{episode_id}.episode-run.jsonl"


def _ep_state(rt, episode_id: str) -> dict[str, Any]:
    return dict(rt.episodes.get(episode_id) or {})


def _save_ep(project_dir: Path, episode_id: str, ep: dict[str, Any], *, stage: Optional[str] = None) -> None:
    rt = load_runtime(project_dir)
    rt.episodes[episode_id] = ep
    if stage:
        rt.stage = stage
    save_runtime(project_dir, rt)


def list_episode_shots(*, project_dir: Path, episode_id: str) -> dict[str, Any]:
    """List shots from jsonl + output artifacts + accept/lock flags."""
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    templates = resolve_templates_dir(project_dir)
    jsonl = _jsonl_path(project_dir, episode_id)
    if not jsonl.is_file():
        return {
            "ok": False,
            "error": f"missing jsonl: {jsonl}",
            "episode_id": episode_id,
            "shots": [],
        }

    shots = load_episode_run_jsonl(jsonl)
    ep = _ep_state(rt, episode_id)
    accepted = set(ep.get("accepted_shots") or [])
    locked = set(ep.get("locked_shots") or [])
    failed = set(ep.get("failed_shots") or [])

    rows: list[dict[str, Any]] = []
    for s in shots:
        shot_dir = templates / "output" / episode_id / "shots" / s.shot_id
        video = None
        if shot_dir.is_dir():
            mp4s = sorted(shot_dir.glob("*.mp4"))
            if mp4s:
                video = str(mp4s[0])
            elif (shot_dir / "video.mp4").is_file():
                video = str(shot_dir / "video.mp4")
        tail = shot_dir / "tail_frame.png"
        rows.append(
            {
                "shot_id": s.shot_id,
                "order": s.order,
                "duration_seconds": s.duration_seconds,
                "link_mode": s.link_mode,
                "ref_characters": list(s.ref_characters),
                "prompt_chars": len(s.video_prompt or ""),
                "prompt_preview": (s.video_prompt or "")[:180],
                "accepted": s.shot_id in accepted,
                "locked": s.shot_id in locked,
                "failed": s.shot_id in failed,
                "has_video": video is not None,
                "video_path": video,
                "has_tail": tail.is_file(),
                "tail_path": str(tail) if tail.is_file() else None,
            }
        )

    return {
        "ok": True,
        "episode_id": episode_id,
        "jsonl_path": str(jsonl),
        "episode_status": ep.get("status"),
        "accepted_shots": sorted(accepted),
        "locked_shots": sorted(locked),
        "failed_shots": sorted(failed),
        "shots": rows,
        "shot_count": len(rows),
    }


def get_shot_prompt(*, project_dir: Path, episode_id: str, shot_id: str) -> dict[str, Any]:
    project_dir = Path(project_dir)
    jsonl = _jsonl_path(project_dir, episode_id)
    shots = load_episode_run_jsonl(jsonl)
    for s in shots:
        if s.shot_id == shot_id:
            return {
                "ok": True,
                "episode_id": episode_id,
                "shot_id": shot_id,
                "order": s.order,
                "video_prompt": s.video_prompt,
                "duration_seconds": s.duration_seconds,
                "ref_characters": list(s.ref_characters),
                "ref_voices": list(s.ref_voices),
                "first_frame": s.first_frame.model_dump(),
            }
    raise FileNotFoundError(f"{shot_id} not in {jsonl}")


def patch_shot_prompt(
    *,
    project_dir: Path,
    episode_id: str,
    shot_id: str,
    video_prompt: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Rewrite one shot's prompt (and optional duration) in episode-run.jsonl."""
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    ep = _ep_state(rt, episode_id)
    locked = set(ep.get("locked_shots") or [])
    if shot_id in locked:
        raise PermissionError(
            f"{shot_id} is locked — unlock_shot first or pass force via unlock"
        )

    jsonl = _jsonl_path(project_dir, episode_id)
    raw_lines = jsonl.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines: list[str] = []
    for line in raw_lines:
        if not line.strip() or line.strip().startswith("#"):
            new_lines.append(line)
            continue
        obj = json.loads(line)
        if obj.get("shot_id") == shot_id:
            if video_prompt is not None:
                obj["video_prompt"] = video_prompt
            if duration_seconds is not None:
                obj["duration_seconds"] = float(duration_seconds)
            ShotRunLine.model_validate(obj)  # schema check
            new_lines.append(json.dumps(obj, ensure_ascii=False))
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        raise FileNotFoundError(f"{shot_id} not found in {jsonl}")

    # Backup then write
    bak = jsonl.with_suffix(jsonl.suffix + ".bak")
    bak.write_text(jsonl.read_text(encoding="utf-8"), encoding="utf-8")
    jsonl.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    shots = load_episode_run_jsonl(jsonl)
    errors: list[str] = []
    if validate:
        errors = validate_episode_run(shots)

    # Patch clears shot accept for this shot
    accepted = [s for s in (ep.get("accepted_shots") or []) if s != shot_id]
    ep["accepted_shots"] = accepted
    if ep.get("status") == "accepted":
        ep["status"] = "done" if ep.get("master_path") else "ready"
    rt.episodes[episode_id] = ep
    rt.stage = "s4_review"
    save_runtime(project_dir, rt)

    return {
        "ok": True,
        "episode_id": episode_id,
        "shot_id": shot_id,
        "jsonl_path": str(jsonl),
        "backup": str(bak),
        "validation_errors": errors,
        "valid": len(errors) == 0,
    }


def accept_shot(
    *,
    project_dir: Path,
    episode_id: str,
    shot_id: str,
    lock: bool = False,
    decided_by: str = "creator",
) -> dict[str, Any]:
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    # Ensure shot exists
    get_shot_prompt(project_dir=project_dir, episode_id=episode_id, shot_id=shot_id)
    ep = _ep_state(rt, episode_id)
    accepted = list(ep.get("accepted_shots") or [])
    if shot_id not in accepted:
        accepted.append(shot_id)
    ep["accepted_shots"] = accepted
    locked = list(ep.get("locked_shots") or [])
    if lock and shot_id not in locked:
        locked.append(shot_id)
    ep["locked_shots"] = locked
    # clear failed flag for this shot
    ep["failed_shots"] = [s for s in (ep.get("failed_shots") or []) if s != shot_id]
    rt.episodes[episode_id] = ep
    rt.stage = "s4_review"
    save_runtime(project_dir, rt)

    jsonl = _jsonl_path(project_dir, episode_id)
    decision = append_decision(
        project_dir,
        decision_kind="shot_acceptance",
        status="accepted",
        series_id=rt.series_id,
        episode_id=episode_id,
        shot_id=shot_id,
        artifact="shot",
        target_hashes=hash_paths({f"run/{episode_id}.episode-run.jsonl#{shot_id}": jsonl}),
        decided_by=decided_by,
        decision_id=f"CD-SHOT-{episode_id}-{shot_id}",
    )
    return {
        "ok": True,
        "decision": decision,
        "accepted_shots": accepted,
        "locked_shots": locked,
    }


def lock_shot(*, project_dir: Path, episode_id: str, shot_id: str) -> dict[str, Any]:
    project_dir = Path(project_dir)
    get_shot_prompt(project_dir=project_dir, episode_id=episode_id, shot_id=shot_id)
    rt = load_runtime(project_dir)
    ep = _ep_state(rt, episode_id)
    locked = list(ep.get("locked_shots") or [])
    if shot_id not in locked:
        locked.append(shot_id)
    ep["locked_shots"] = locked
    rt.episodes[episode_id] = ep
    rt.stage = "s4_review"
    save_runtime(project_dir, rt)
    return {"ok": True, "locked_shots": locked}


def unlock_shot(*, project_dir: Path, episode_id: str, shot_id: str) -> dict[str, Any]:
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    ep = _ep_state(rt, episode_id)
    locked = [s for s in (ep.get("locked_shots") or []) if s != shot_id]
    ep["locked_shots"] = locked
    rt.episodes[episode_id] = ep
    save_runtime(project_dir, rt)
    return {"ok": True, "locked_shots": locked}


def accept_episode(
    *,
    project_dir: Path,
    episode_id: str,
    lock_all: bool = False,
    decided_by: str = "creator",
) -> dict[str, Any]:
    """Accept all shots in episode; optionally lock all."""
    project_dir = Path(project_dir)
    listed = list_episode_shots(project_dir=project_dir, episode_id=episode_id)
    if not listed.get("ok"):
        raise FileNotFoundError(listed.get("error"))
    shot_ids = [s["shot_id"] for s in listed["shots"]]
    rt = load_runtime(project_dir)
    ep = _ep_state(rt, episode_id)
    ep["accepted_shots"] = list(shot_ids)
    if lock_all:
        ep["locked_shots"] = list(shot_ids)
    ep["status"] = "accepted"
    rt.episodes[episode_id] = ep
    rt.stage = "s4_review"
    save_runtime(project_dir, rt)

    decision = append_decision(
        project_dir,
        decision_kind="episode_acceptance",
        status="accepted",
        series_id=rt.series_id,
        episode_id=episode_id,
        artifact="episode",
        decided_by=decided_by,
        decision_id=f"CD-EP-{episode_id}-ACCEPT",
    )
    mem = project_dir / "memory" / "PROJECT.md"
    if mem.is_file():
        with mem.open("a", encoding="utf-8") as f:
            f.write(f"\n- [{_now()}] episode `{episode_id}` accepted ({len(shot_ids)} shots)\n")
    return {
        "ok": True,
        "decision": decision,
        "accepted_shots": shot_ids,
        "locked_shots": ep.get("locked_shots") or [],
        "status": "accepted",
    }


def rerun_shots(
    *,
    project_dir: Path,
    episode_id: str,
    shot_ids: Optional[list[str]] = None,
    force: bool = False,
    run_in_background: bool = True,
    bus: Optional[InMemoryEventBus] = None,
) -> dict[str, Any]:
    """Rerun from earliest requested shot (Comfy from_shot). Respects locked_shots unless force."""
    project_dir = Path(project_dir)
    bus = bus or get_event_bus()
    listed = list_episode_shots(project_dir=project_dir, episode_id=episode_id)
    if not listed.get("ok"):
        raise FileNotFoundError(listed.get("error"))

    all_shots = listed["shots"]
    by_id = {s["shot_id"]: s for s in all_shots}
    if not shot_ids:
        # default: failed shots, else last shot
        shot_ids = list(listed.get("failed_shots") or [])
        if not shot_ids and all_shots:
            shot_ids = [all_shots[-1]["shot_id"]]

    missing = [s for s in shot_ids if s not in by_id]
    if missing:
        raise ValueError(f"unknown shots: {missing}")

    rt = load_runtime(project_dir)
    ep = _ep_state(rt, episode_id)
    locked = set(ep.get("locked_shots") or [])
    blocked = [s for s in shot_ids if s in locked]
    if blocked and not force:
        raise PermissionError(
            f"locked shots cannot rerun without force=True: {blocked}"
        )

    # earliest by order
    ordered = sorted(shot_ids, key=lambda sid: by_id[sid]["order"])
    from_shot = ordered[0]

    # Clear accept flags for shots being regenerated (and later chain shots)
    from_order = by_id[from_shot]["order"]
    affected = [s["shot_id"] for s in all_shots if s["order"] >= from_order]
    if not force:
        affected = [s for s in affected if s not in locked]
    ep["accepted_shots"] = [
        s for s in (ep.get("accepted_shots") or []) if s not in affected
    ]
    # If force, unlock affected locked shots that are being overwritten
    if force:
        ep["locked_shots"] = [
            s for s in (ep.get("locked_shots") or []) if s not in shot_ids
        ]
    ep["status"] = "rendering"
    ep["resume_from_shot"] = from_shot
    rt.episodes[episode_id] = ep
    rt.stage = "s4_review"
    save_runtime(project_dir, rt)

    bus.publish(
        JobEvent(
            event_type=JobEventType.MILESTONE,
            job_id=f"s4_rerun_{episode_id}_{from_shot}",
            job_kind=JobKind.COMFY_EPISODE,
            series_id=rt.series_id,
            episode_id=episode_id,
            shot_id=from_shot,
            message=f"S4 rerun from {from_shot} (shots={ordered})",
        )
    )

    result = enqueue_comfy_episode(
        hermes_project_dir=project_dir,
        episode_id=episode_id,
        from_shot=from_shot,
        force=True,  # overwrite existing shot videos
        run_in_background=run_in_background,
        bus=bus,
    )
    return {
        "ok": True,
        "from_shot": from_shot,
        "requested_shots": ordered,
        "affected_shots": affected,
        "comfy": result,
        "job_id": result.get("job_id"),
    }


def reject_shot(
    *,
    project_dir: Path,
    episode_id: str,
    shot_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """Mark shot failed / not accepted (does not delete video)."""
    project_dir = Path(project_dir)
    get_shot_prompt(project_dir=project_dir, episode_id=episode_id, shot_id=shot_id)
    rt = load_runtime(project_dir)
    ep = _ep_state(rt, episode_id)
    ep["accepted_shots"] = [s for s in (ep.get("accepted_shots") or []) if s != shot_id]
    failed = list(ep.get("failed_shots") or [])
    if shot_id not in failed:
        failed.append(shot_id)
    ep["failed_shots"] = failed
    ep["resume_from_shot"] = shot_id
    if ep.get("status") == "accepted":
        ep["status"] = "partial"
    rt.episodes[episode_id] = ep
    rt.stage = "s4_review"
    save_runtime(project_dir, rt)
    append_decision(
        project_dir,
        decision_kind="shot_acceptance",
        status="rejected",
        series_id=rt.series_id,
        episode_id=episode_id,
        shot_id=shot_id,
        artifact="shot",
        decided_by="creator",
        decision_id=f"CD-SHOT-REJ-{episode_id}-{shot_id}",
    )
    return {
        "ok": True,
        "shot_id": shot_id,
        "failed_shots": failed,
        "reason": reason,
    }
