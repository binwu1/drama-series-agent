# -*- coding: utf-8 -*-
"""S3 next-episode prefetch + continue (same conversation / series)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.drama.build_worker import run_s2_build_and_comfy
from drama_series_agent.drama.comfy_worker import resolve_templates_dir
from drama_series_agent.drama.enrich import run_literary_generate
from drama_series_agent.drama.event_bus import InMemoryEventBus, get_event_bus
from drama_series_agent.drama.job_events import JobEvent, JobEventType, JobKind
from drama_series_agent.drama.runtime import load_runtime, save_runtime
from drama_series_agent.intake.scaffold import load_project


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mounts(project_dir: Path) -> dict[str, str]:
    return dict((load_project(project_dir).get("mounts") or {}))


def literary_exists(project_dir: Path, episode_id: str) -> Optional[Path]:
    from drama_series_agent.drama.build_worker import _literary_path

    return _literary_path(Path(project_dir), episode_id)


def load_episode_tails(templates_dir: Path) -> dict[str, Any]:
    path = templates_dir / "continuity" / "episode-tails.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_tail_for_episode(templates_dir: Path, episode_id: str) -> Optional[dict[str, Any]]:
    tails = load_episode_tails(templates_dir)
    row = tails.get(episode_id)
    return dict(row) if isinstance(row, dict) else None


def prefetch_next_episode(
    *,
    project_dir: Path,
    episode_id: Optional[str] = None,
    user_text: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve target EP and report readiness for S2 (or S1-B literary gap)."""
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    if user_text:
        target = rt.resolve_episode_intent(user_text)
    else:
        target = episode_id or rt.next_episode or "EP001"

    templates_dir = resolve_templates_dir(project_dir)
    lit = literary_exists(project_dir, target)
    prev = rt.last_completed_episode
    prev_tail = get_tail_for_episode(templates_dir, prev) if prev else None

    cast_dir = Path(_mounts(project_dir)["cast_dir"])
    cast_pngs = list(cast_dir.glob("*.png")) if cast_dir.is_dir() else []

    jsonl = templates_dir / "run" / f"{target}.episode-run.jsonl"
    gaps: list[str] = []
    if not lit:
        gaps.append("literary_missing")
    if not rt.s1_gate.get("cast_leads_accepted") and not cast_pngs:
        gaps.append("cast_missing")
    if not rt.default_workflow:
        gaps.append("workflow_unset")
    # EP002+ ideally has prev tail (soft)
    if target != "EP001" and prev and not prev_tail:
        gaps.append("prev_episode_tail_missing")

    hard_gaps = [g for g in gaps if g in ("literary_missing", "cast_missing")]
    soft_gaps = [g for g in gaps if g not in hard_gaps]
    ready_for_s2 = len(hard_gaps) == 0
    action = "s2_build_and_comfy"
    if "literary_missing" in hard_gaps:
        action = "s1b_literary_then_accept"
    elif hard_gaps:
        action = "fix_gaps_then_s2"
    elif soft_gaps:
        action = "s2_build_and_comfy_with_warnings"

    return {
        "ok": True,
        "series_id": rt.series_id,
        "episode_id": target,
        "last_completed_episode": rt.last_completed_episode,
        "next_episode": rt.next_episode,
        "literary_path": str(lit) if lit else None,
        "literary_exists": lit is not None,
        "jsonl_exists": jsonl.is_file(),
        "jsonl_path": str(jsonl),
        "default_workflow": rt.default_workflow,
        "prev_tail": prev_tail,
        "cast_count": len(cast_pngs),
        "s1_gate": rt.s1_gate,
        "gaps": gaps,
        "hard_gaps": hard_gaps,
        "soft_gaps": soft_gaps,
        "ready_for_s2": ready_for_s2,
        "suggested_action": action,
        "stage": rt.stage,
    }


def ensure_literary_for_episode(
    *,
    project_dir: Path,
    episode_id: str,
    premise: Optional[str] = None,
    revision_notes: Optional[str] = None,
    bus: Optional[InMemoryEventBus] = None,
) -> dict[str, Any]:
    """If literary missing, enqueue S1-B literary for that episode only (still needs Accept)."""
    project_dir = Path(project_dir)
    existing = literary_exists(project_dir, episode_id)
    if existing:
        return {
            "ok": True,
            "skipped": True,
            "literary_path": str(existing),
            "needs_accept": False,
        }

    rt = load_runtime(project_dir)
    dramas = Path(_mounts(project_dir)["dramas_dir"])
    index_path = dramas / "literary_index.json"
    base_premise = premise
    if not base_premise and index_path.is_file():
        idx = json.loads(index_path.read_text(encoding="utf-8"))
        base_premise = idx.get("premise") or rt.series_id
    base_premise = base_premise or f"续写 {rt.series_id} {episode_id}"

    from drama_series_agent.drama.build_worker import _ep_num

    n = _ep_num(episode_id)
    out = run_literary_generate(
        project_dir=project_dir,
        premise=base_premise,
        episode_count=n,
        episode_ids=[f"ep{n:03d}"],
        revision_notes=revision_notes or f"Generate literary for {episode_id}",
        use_skill=True,
        bus=bus or get_event_bus(),
    )
    # Clear literary accept so user re-confirms new ep
    rt = load_runtime(project_dir)
    rt.s1_gate["literary_accepted"] = False
    rt.s1_gate["ready_for_s2"] = False
    rt.stage = "s1_enrich"
    save_runtime(project_dir, rt)

    return {
        "ok": True,
        "skipped": False,
        "needs_accept": True,
        "job_id": out.get("job_id"),
        "message": f"{episode_id} literary draft ready — Accept in Asset Studio before S2",
    }


def continue_series(
    *,
    project_dir: Path,
    user_text: Optional[str] = None,
    episode_id: Optional[str] = None,
    auto_build_comfy: bool = True,
    force_build: bool = False,
    skip_comfy: bool = False,
    run_comfy_in_background: bool = True,
    bus: Optional[InMemoryEventBus] = None,
) -> dict[str, Any]:
    """「生成第二集」入口：prefetch → 缺文学则 S1-B → 否则 S2 pipeline."""
    project_dir = Path(project_dir)
    bus = bus or get_event_bus()
    pref = prefetch_next_episode(
        project_dir=project_dir,
        episode_id=episode_id,
        user_text=user_text,
    )
    target = pref["episode_id"]
    result: dict[str, Any] = {"ok": True, "prefetch": pref, "episode_id": target}

    if pref["suggested_action"] == "s1b_literary_then_accept":
        lit = ensure_literary_for_episode(
            project_dir=project_dir,
            episode_id=target,
            bus=bus,
        )
        result["literary"] = lit
        result["blocked"] = True
        result["next_ui"] = "s1_accept_literary"
        bus.publish(
            JobEvent(
                event_type=JobEventType.MILESTONE,
                job_id=lit.get("job_id") or f"s3_{target}",
                job_kind=JobKind.LITERARY_GENERATE,
                series_id=pref["series_id"],
                episode_id=target,
                message=lit.get("message")
                or f"{target} needs literary Accept before generate",
            )
        )
        return result

    if not auto_build_comfy:
        result["blocked"] = False
        result["next_ui"] = "s2_panel"
        return result

    s2 = run_s2_build_and_comfy(
        project_dir=project_dir,
        episode_id=target,
        force_build=force_build or not pref.get("jsonl_exists"),
        run_comfy_in_background=run_comfy_in_background,
        skip_comfy=skip_comfy,
        bus=bus,
    )
    result["s2"] = s2
    result["blocked"] = not s2.get("ok")
    result["next_ui"] = "job_panel"
    bus.publish(
        JobEvent(
            event_type=JobEventType.MILESTONE,
            job_id=(s2.get("comfy") or s2.get("build") or {}).get("job_id")
            or f"s3_{target}",
            job_kind=JobKind.COMFY_EPISODE,
            series_id=pref["series_id"],
            episode_id=target,
            message=f"Continuing series → {target}",
        )
    )
    return result


def get_series_progress(*, project_dir: Path) -> dict[str, Any]:
    """Dashboard snapshot for S3 Web panel."""
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    templates_dir = resolve_templates_dir(project_dir)
    tails = load_episode_tails(templates_dir)
    episodes = []
    for ep_id, row in sorted(rt.episodes.items()):
        master = row.get("master_path")
        master_ok = bool(master and Path(master).is_file())
        episodes.append(
            {
                "episode_id": ep_id,
                "status": row.get("status"),
                "master_path": master,
                "master_exists": master_ok,
                "jsonl_path": row.get("jsonl_path"),
                "resume_from_shot": row.get("resume_from_shot"),
                "failed_shots": row.get("failed_shots") or [],
                "has_tail": ep_id in tails,
            }
        )
    return {
        "ok": True,
        "series_id": rt.series_id,
        "stage": rt.stage,
        "last_completed_episode": rt.last_completed_episode,
        "next_episode": rt.next_episode,
        "default_workflow": rt.default_workflow,
        "s1_gate": rt.s1_gate,
        "episodes": episodes,
        "tails": tails,
        "updated_at": rt.updated_at,
    }


def propose_voice_harvest(
    *,
    project_dir: Path,
    episode_id: Optional[str] = None,
) -> dict[str, Any]:
    """List candidate shot videos for voice harvest (never auto hard-lock)."""
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    ep = episode_id or rt.last_completed_episode
    if not ep:
        return {"ok": True, "candidates": [], "note": "no completed episode"}
    templates_dir = resolve_templates_dir(project_dir)
    shots_dir = templates_dir / "output" / ep / "shots"
    candidates = []
    if shots_dir.is_dir():
        for d in sorted(shots_dir.iterdir()):
            vid = d / "video.mp4"
            if not vid.is_file():
                # common alternate names
                alts = list(d.glob("*.mp4"))
                vid = alts[0] if alts else None
            if vid and vid.is_file():
                candidates.append(
                    {
                        "shot_id": d.name,
                        "path": str(vid),
                        "bytes": vid.stat().st_size,
                    }
                )
    return {
        "ok": True,
        "episode_id": ep,
        "candidates": candidates,
        "note": "Manual harvest only — do not auto hard-lock voices in S3",
    }
