from __future__ import annotations

from pathlib import Path

from drama_series_agent.adapters.r2v.continuity import load_tails
from drama_series_agent.adapters.r2v.schema import FirstFrameRef, ShotRunLine


def resolve_frame_ref_path(
    ref: FirstFrameRef,
    *,
    shot_id: str,
    project_root: Path,
    episode_out: Path,
) -> Path:
    """Resolve any frame ref (first or last) to an on-disk image path."""
    src = ref.source
    if src in ("external", "keyframe_file"):
        p = Path(ref.path or "")
        if not p.is_absolute():
            p = project_root / p
        if not p.is_file():
            raise FileNotFoundError(f"{shot_id}: missing frame {p}")
        return p.resolve()
    if src == "prev_shot_tail":
        sid = ref.prev_shot_id
        if not sid:
            raise ValueError(f"{shot_id}: prev_shot_id required")
        p = episode_out / "shots" / sid / "tail_frame.png"
        if not p.is_file():
            raise FileNotFoundError(f"{shot_id}: missing prev tail {p}")
        return p.resolve()
    if src == "prev_episode_tail":
        eid = getattr(ref, "prev_episode_id", None)
        if not eid:
            raise ValueError(f"{shot_id}: prev_episode_id required")
        tails = load_tails(project_root / "continuity" / "episode-tails.json")
        entry = tails.get(eid) or {}
        p = Path(entry.get("tail_frame") or "")
        if not p.is_file():
            raise FileNotFoundError(f"{shot_id}: no registered tail for episode {eid}")
        return p.resolve()
    if src == "generate_keyframe":
        raise NotImplementedError(f"{shot_id}: generate_keyframe is implemented in runner")
    raise ValueError(f"unknown frame source: {src}")


def resolve_first_frame_path(
    shot: ShotRunLine,
    *,
    project_root: Path,
    episode_out: Path,
) -> Path:
    return resolve_frame_ref_path(
        shot.first_frame,
        shot_id=shot.shot_id,
        project_root=project_root,
        episode_out=episode_out,
    )
