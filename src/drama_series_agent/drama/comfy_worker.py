# -*- coding: utf-8 -*-
"""Background Comfy episode worker — enqueue returns job_id immediately."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from drama_series_agent.drama.completion import on_episode_complete
from drama_series_agent.drama.event_bus import InMemoryEventBus, get_event_bus
from drama_series_agent.drama.job_events import (
    JobEvent,
    JobEventType,
    JobKind,
    append_event_jsonl,
)
from drama_series_agent.drama.runtime import load_runtime, save_runtime

# job_id -> status snapshot for Job Panel polling
_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()
# Soft-cancel flags: take effect at the next shot boundary
_CANCEL: dict[str, bool] = {}
_CANCEL_LOCK = threading.Lock()


def request_cancel(job_id: str) -> None:
    with _CANCEL_LOCK:
        _CANCEL[job_id] = True


def is_cancel_requested(job_id: str) -> bool:
    with _CANCEL_LOCK:
        return bool(_CANCEL.get(job_id))


def clear_cancel(job_id: str) -> None:
    with _CANCEL_LOCK:
        _CANCEL.pop(job_id, None)


def get_job_snapshot(job_id: str) -> Optional[dict[str, Any]]:
    with _JOBS_LOCK:
        snap = _JOBS.get(job_id)
        return dict(snap) if snap else None


def list_active_jobs(series_id: Optional[str] = None) -> list[dict[str, Any]]:
    with _JOBS_LOCK:
        rows = [dict(v) for v in _JOBS.values()]
    if series_id:
        rows = [r for r in rows if r.get("series_id") == series_id]
    return rows


def upsert_job_snapshot(job_id: str, **fields: Any) -> dict[str, Any]:
    """Create/update Job Panel snapshot (Comfy + S1-B enrich share this registry)."""
    with _JOBS_LOCK:
        cur = dict(_JOBS.get(job_id) or {"job_id": job_id})
        cur.update(fields)
        cur["job_id"] = job_id
        _JOBS[job_id] = cur
        return dict(cur)


def cancel_job(
    *,
    hermes_project_dir: Path,
    job_id: Optional[str] = None,
    episode_id: Optional[str] = None,
    bus: Optional[InMemoryEventBus] = None,
) -> dict[str, Any]:
    """Request soft-cancel of active Comfy/build jobs. Stops at next shot boundary."""
    hermes_project_dir = canonical_hermes_project(Path(hermes_project_dir))
    bus = bus or get_event_bus()
    rt = load_runtime(hermes_project_dir)
    targets: list[str] = []
    if job_id:
        targets = [str(job_id)]
    else:
        targets = [str(j) for j in (rt.active_job_ids or [])]
        if episode_id:
            filtered: list[str] = []
            for jid in targets:
                snap = get_job_snapshot(jid) or {}
                if snap.get("episode_id") == episode_id or episode_id in jid:
                    filtered.append(jid)
            if filtered:
                targets = filtered
    if not targets:
        # Also consider in-memory running jobs for this series
        for snap in list_active_jobs(rt.series_id):
            if snap.get("status") in ("queued", "running"):
                jid = str(snap.get("job_id") or "")
                if jid and jid not in targets:
                    if not episode_id or snap.get("episode_id") == episode_id:
                        targets.append(jid)
    if not targets:
        return {
            "ok": False,
            "error": "no_active_job",
            "message": "当前没有可中断的生成任务",
        }

    cancelled: list[dict[str, Any]] = []
    for jid in targets:
        request_cancel(jid)
        snap = get_job_snapshot(jid) or {}
        status = str(snap.get("status") or "queued")
        ep = str(snap.get("episode_id") or episode_id or rt.next_episode or "EP001")
        shot = snap.get("shot_id")
        if status in ("queued", "unknown") or not snap:
            _apply_cancel_to_runtime(
                hermes_project_dir=hermes_project_dir,
                job_id=jid,
                episode_id=ep,
                shot_id=shot,
                bus=bus,
            )
        cancelled.append(
            {
                "job_id": jid,
                "episode_id": ep,
                "shot_id": shot,
                "was_status": status,
            }
        )
    return {
        "ok": True,
        "cancelled": cancelled,
        "message": (
            "已请求中断。当前镜头采完后停止，并记下断点；"
            "可在生成进度页点击「断点续跑」。"
        ),
        "resume_hint": "jobs_page",
    }


def resume_episode(
    *,
    hermes_project_dir: Path,
    episode_id: Optional[str] = None,
    from_shot: Optional[str] = None,
    force: bool = False,
    run_in_background: bool = True,
    bus: Optional[InMemoryEventBus] = None,
    run_episode_fn: Optional[Callable[..., Any]] = None,
) -> dict[str, Any]:
    """Resume Comfy from runtime.resume_from_shot or an explicit shot id."""
    hermes_project_dir = canonical_hermes_project(Path(hermes_project_dir))
    rt = load_runtime(hermes_project_dir)
    ep = (episode_id or rt.next_episode or "EP001").strip()
    if ep.lower().startswith("ep") and not ep.startswith("EP"):
        ep = "EP" + ep[2:]
    row = dict(rt.episodes.get(ep) or {})
    shot = (from_shot or row.get("resume_from_shot") or "").strip() or None
    if not shot:
        return {
            "ok": False,
            "error": "no_resume_shot",
            "message": f"{ep} 没有记录断点镜头；请指定 from_shot（如 SHOT-003）",
            "episode_id": ep,
        }
    # Clear stale cancel flags before re-queue
    for jid in list(rt.active_job_ids or []):
        clear_cancel(jid)
    out = enqueue_comfy_episode(
        hermes_project_dir=hermes_project_dir,
        episode_id=ep,
        from_shot=shot,
        force=force,
        run_in_background=run_in_background,
        bus=bus,
        run_episode_fn=run_episode_fn,
    )
    out["resumed_from"] = shot
    out["message"] = f"已从 {ep} / {shot} 断点续跑（job={out.get('job_id')}）"
    return out


def _apply_cancel_to_runtime(
    *,
    hermes_project_dir: Path,
    job_id: str,
    episode_id: str,
    shot_id: Optional[str],
    bus: InMemoryEventBus,
) -> None:
    """Mark job cancelled, persist resume_from_shot, emit JobCancelled."""
    hermes_project_dir = Path(hermes_project_dir)
    rt = load_runtime(hermes_project_dir)
    series_id = rt.series_id
    resume_shot = shot_id
    if not resume_shot:
        resume_shot = (rt.episodes.get(episode_id) or {}).get("resume_from_shot")

    upsert_job_snapshot(
        job_id,
        status="cancelled",
        phase="cancelled",
        error=None,
        message="cancelled_by_user",
        shot_id=resume_shot,
    )
    clear_cancel(job_id)

    ep = dict(rt.episodes.get(episode_id) or {})
    ep["status"] = "interrupted"
    if resume_shot:
        ep["resume_from_shot"] = resume_shot
    rt.episodes[episode_id] = ep
    rt.active_job_ids = [j for j in rt.active_job_ids if j != job_id]
    rt.stage = "s2_interrupted"
    save_runtime(hermes_project_dir, rt)

    evt = JobEvent(
        event_type=JobEventType.JOB_CANCELLED,
        job_id=job_id,
        job_kind=JobKind.COMFY_EPISODE,
        series_id=series_id,
        episode_id=episode_id,
        shot_id=resume_shot,
        phase="cancelled",
        message=f"Cancelled {episode_id}"
        + (f" · resume at {resume_shot}" if resume_shot else ""),
    )
    bus.publish(evt)
    jobs_log = hermes_project_dir / "jobs" / f"{job_id}.jsonl"
    append_event_jsonl(jobs_log, evt)
    append_event_jsonl(hermes_project_dir / "jobs" / "events.jsonl", evt)
    bus.publish(
        JobEvent(
            event_type=JobEventType.MILESTONE,
            job_id=job_id,
            job_kind=JobKind.COMFY_EPISODE,
            series_id=series_id,
            episode_id=episode_id,
            shot_id=resume_shot,
            phase="cancelled",
            message=f"{episode_id} 已中断"
            + (f"，断点 {resume_shot}" if resume_shot else ""),
        )
    )


def canonical_hermes_project(project_dir: Path) -> Path:
    """Map a series slug or relative name back to projects/{series}."""
    project_dir = Path(project_dir)
    if (project_dir / "project.json").is_file():
        return project_dir
    root = Path(__file__).resolve().parents[3]
    candidate = root / "projects" / project_dir.name
    if (candidate / "project.json").is_file():
        return candidate
    return project_dir


def resolve_templates_dir(hermes_project_dir: Path) -> Path:
    """Hermes project.json mounts.templates_dir → episode project root (templates/)."""
    hermes_project_dir = canonical_hermes_project(Path(hermes_project_dir))
    project_json = hermes_project_dir / "project.json"
    if project_json.is_file():
        data = json.loads(project_json.read_text(encoding="utf-8"))
        mounts = data.get("mounts") or {}
        td = mounts.get("templates_dir")
        if td and Path(td).is_dir():
            return Path(td)
    # Fallback: hermes project itself if run/ lives there
    if (hermes_project_dir / "run").is_dir():
        return hermes_project_dir
    raise FileNotFoundError(
        f"templates_dir not found for Hermes project {hermes_project_dir}"
    )


def enqueue_comfy_episode(
    *,
    hermes_project_dir: Path,
    episode_id: str,
    from_shot: Optional[str] = None,
    force: bool = False,
    cast_series: Optional[str] = None,
    context_ir: Optional[str] = None,
    run_in_background: bool = True,
    bus: Optional[InMemoryEventBus] = None,
    run_episode_fn: Optional[Callable[..., Any]] = None,
) -> dict[str, Any]:
    """Queue an R2V episode render. Returns job_id immediately when background=True."""
    hermes_project_dir = canonical_hermes_project(Path(hermes_project_dir))
    bus = bus or get_event_bus()
    rt = load_runtime(hermes_project_dir)
    templates_dir = resolve_templates_dir(hermes_project_dir)
    job_id = f"job_comfy_{rt.series_id}_{episode_id}_{uuid.uuid4().hex[:6]}"

    jsonl_path = templates_dir / "run" / f"{episode_id}.episode-run.jsonl"
    meta_path = templates_dir / "run" / f"{episode_id}.episode-meta.json"
    jobs_log = hermes_project_dir / "jobs" / f"{job_id}.jsonl"
    jobs_log.parent.mkdir(parents=True, exist_ok=True)
    bus.set_jsonl_log(hermes_project_dir / "jobs" / "events.jsonl")

    rt.active_job_ids.append(job_id)
    rt.stage = "s2_rendering"
    ep = dict(rt.episodes.get(episode_id) or {})
    ep["status"] = "rendering"
    ep["workflow"] = rt.default_workflow
    ep["jsonl_path"] = str(jsonl_path)
    if from_shot:
        ep["resume_from_shot"] = from_shot
    rt.episodes[episode_id] = ep
    save_runtime(hermes_project_dir, rt)

    queued = JobEvent(
        event_type=JobEventType.JOB_QUEUED,
        job_id=job_id,
        job_kind=JobKind.COMFY_EPISODE,
        series_id=rt.series_id,
        episode_id=episode_id,
        workflow=rt.default_workflow,
        phase="queued",
        progress=0.0,
        message=f"Queued Comfy render {episode_id}",
        paths={"templates_dir": str(templates_dir), "jsonl": str(jsonl_path)},
    )
    bus.publish(queued)
    append_event_jsonl(jobs_log, queued)

    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "series_id": rt.series_id,
            "episode_id": episode_id,
            "status": "queued",
            "phase": "queued",
            "progress": 0.0,
            "shot_id": None,
            "index": None,
            "total": None,
            "error": None,
            "master_path": None,
            "templates_dir": str(templates_dir),
        }

    kwargs = {
        "hermes_project_dir": hermes_project_dir,
        "templates_dir": templates_dir,
        "episode_id": episode_id,
        "job_id": job_id,
        "series_id": rt.series_id,
        "from_shot": from_shot,
        "force": force,
        "cast_series": cast_series or rt.series_id,
        "context_ir": context_ir or rt.context_ir or "off",
        "workflow": rt.default_workflow,
        "jsonl_path": jsonl_path,
        "meta_path": meta_path,
        "jobs_log": jobs_log,
        "bus": bus,
        "run_episode_fn": run_episode_fn,
    }

    if run_in_background:
        t = threading.Thread(
            target=_thread_main,
            kwargs=kwargs,
            name=f"comfy-{job_id}",
            daemon=True,
        )
        t.start()
        return {
            "ok": True,
            "job_id": job_id,
            "background": True,
            "event": queued.to_dict(),
            "templates_dir": str(templates_dir),
        }

    _thread_main(**kwargs)
    return {
        "ok": True,
        "job_id": job_id,
        "background": False,
        "snapshot": get_job_snapshot(job_id),
        "event": queued.to_dict(),
    }


def _thread_main(**kwargs: Any) -> None:
    try:
        asyncio.run(_run_job(**kwargs))
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Comfy worker crashed: {e}")
        job_id = kwargs["job_id"]
        bus: InMemoryEventBus = kwargs["bus"]
        _update_job(job_id, status="failed", phase="failed", error=str(e))
        bus.publish(
            JobEvent(
                event_type=JobEventType.JOB_FAILED,
                job_id=job_id,
                job_kind=JobKind.COMFY_EPISODE,
                series_id=kwargs["series_id"],
                episode_id=kwargs["episode_id"],
                error=str(e),
                phase="failed",
            )
        )


async def _run_job(
    *,
    hermes_project_dir: Path,
    templates_dir: Path,
    episode_id: str,
    job_id: str,
    series_id: str,
    from_shot: Optional[str],
    force: bool,
    cast_series: str,
    context_ir: str,
    workflow: Optional[str],
    jsonl_path: Path,
    meta_path: Path,
    jobs_log: Path,
    bus: InMemoryEventBus,
    run_episode_fn: Optional[Callable[..., Any]],
) -> None:
    _update_job(job_id, status="running", phase="sampling", progress=0.0)

    def on_progress(payload: dict[str, Any]) -> None:
        _handle_runner_progress(
            payload,
            job_id=job_id,
            series_id=series_id,
            episode_id=episode_id,
            workflow=workflow,
            bus=bus,
            jobs_log=jobs_log,
        )

    run_fn = run_episode_fn
    if run_fn is None:
        from drama_series_agent.adapters.r2v.runner import run_episode as run_fn

    def cancel_check() -> bool:
        return is_cancel_requested(job_id)

    try:
        # Soft-cancel before first shot if already requested
        if cancel_check():
            from drama_series_agent.adapters.r2v.runner import JobCancelled as RunnerCancelled

            raise RunnerCancelled(None)

        master = await run_fn(
            project_root=templates_dir,
            episode_id=episode_id,
            from_shot=from_shot,
            force=force,
            cast_series=cast_series,
            context_ir=context_ir,
            progress_callback=on_progress,
            cancel_check=cancel_check,
        )
        master_s = str(master)
        clear_cancel(job_id)
        _update_job(
            job_id,
            status="done",
            phase="done",
            progress=1.0,
            master_path=master_s,
        )
        on_episode_complete(
            hermes_project_dir,
            episode_id=episode_id,
            master_path=master_s,
            jsonl_path=str(jsonl_path),
            workflow=workflow,
            bus=bus,
            job_id=job_id,
        )
    except Exception as e:  # noqa: BLE001
        from drama_series_agent.adapters.r2v.runner import JobCancelled as RunnerCancelled

        if isinstance(e, RunnerCancelled) or is_cancel_requested(job_id):
            failed_shot = getattr(e, "shot_id", None)
            with _JOBS_LOCK:
                failed_shot = failed_shot or (_JOBS.get(job_id) or {}).get("shot_id")
            _apply_cancel_to_runtime(
                hermes_project_dir=hermes_project_dir,
                job_id=job_id,
                episode_id=episode_id,
                shot_id=failed_shot,
                bus=bus,
            )
            return

        logger.exception(f"Episode render failed {job_id}: {e}")
        failed_shot = None
        with _JOBS_LOCK:
            failed_shot = (_JOBS.get(job_id) or {}).get("shot_id")
        clear_cancel(job_id)
        _update_job(job_id, status="failed", phase="failed", error=str(e))
        fail_evt = JobEvent(
            event_type=JobEventType.JOB_FAILED,
            job_id=job_id,
            job_kind=JobKind.COMFY_EPISODE,
            series_id=series_id,
            episode_id=episode_id,
            shot_id=failed_shot,
            error=str(e),
            phase="failed",
        )
        bus.publish(fail_evt)
        append_event_jsonl(jobs_log, fail_evt)
        on_episode_complete(
            hermes_project_dir,
            episode_id=episode_id,
            master_path=None,
            jsonl_path=str(jsonl_path),
            workflow=workflow,
            failed_shots=[failed_shot] if failed_shot else [],
            bus=bus,
            job_id=job_id,
        )
        raise


def _handle_runner_progress(
    payload: dict[str, Any],
    *,
    job_id: str,
    series_id: str,
    episode_id: str,
    workflow: Optional[str],
    bus: InMemoryEventBus,
    jobs_log: Path,
) -> None:
    ptype = payload.get("type")
    index = payload.get("index")
    total = payload.get("total")
    shot_id = payload.get("shot_id")
    progress = None
    if index is not None and total:
        base = float(index) / float(total)
        if ptype in ("shot_done", "shot_skipped"):
            progress = float(index + 1) / float(total)
        elif ptype == "shot_started":
            progress = base
        else:
            progress = base

    if ptype == "shot_started":
        evt = JobEvent(
            event_type=JobEventType.SHOT_STARTED,
            job_id=job_id,
            job_kind=JobKind.COMFY_EPISODE,
            series_id=series_id,
            episode_id=episode_id,
            shot_id=shot_id,
            workflow=workflow,
            index=index,
            total=total,
            phase=payload.get("phase") or "sampling",
            progress=progress,
            ratio=0.0,
        )
    elif ptype in ("shot_done", "shot_skipped"):
        paths = {}
        if payload.get("video"):
            paths["video"] = payload["video"]
        if payload.get("tail"):
            paths["tail"] = payload["tail"]
        evt = JobEvent(
            event_type=JobEventType.SHOT_DONE,
            job_id=job_id,
            job_kind=JobKind.COMFY_EPISODE,
            series_id=series_id,
            episode_id=episode_id,
            shot_id=shot_id,
            workflow=workflow,
            index=index,
            total=total,
            phase="done",
            progress=progress,
            ratio=1.0,
            paths=paths,
            message=f"{shot_id} skipped" if ptype == "shot_skipped" else None,
        )
    elif ptype == "shot_failed":
        evt = JobEvent(
            event_type=JobEventType.SHOT_FAILED,
            job_id=job_id,
            job_kind=JobKind.COMFY_EPISODE,
            series_id=series_id,
            episode_id=episode_id,
            shot_id=shot_id,
            index=index,
            total=total,
            phase="failed",
            progress=progress,
            error=payload.get("error"),
        )
    elif ptype == "shot_phase":
        evt = JobEvent(
            event_type=JobEventType.SHOT_PROGRESS,
            job_id=job_id,
            job_kind=JobKind.COMFY_EPISODE,
            series_id=series_id,
            episode_id=episode_id,
            shot_id=shot_id,
            index=index,
            total=total,
            phase=payload.get("phase") or "sampling",
            progress=progress,
        )
    elif ptype == "episode_done":
        evt = JobEvent(
            event_type=JobEventType.EPISODE_DONE,
            job_id=job_id,
            job_kind=JobKind.COMFY_EPISODE,
            series_id=series_id,
            episode_id=episode_id,
            workflow=workflow,
            phase="done",
            progress=1.0,
            paths={"master": payload.get("master") or ""},
        )
        _update_job(
            job_id,
            master_path=payload.get("master"),
            progress=1.0,
            phase="done",
        )
    else:
        return

    bus.publish(evt)
    append_event_jsonl(jobs_log, evt)
    _update_job(
        job_id,
        shot_id=shot_id,
        index=index,
        total=total,
        progress=progress,
        phase=evt.phase,
        status="running" if ptype != "episode_done" else "done",
        error=payload.get("error"),
    )


def _update_job(job_id: str, **fields: Any) -> None:
    with _JOBS_LOCK:
        cur = _JOBS.get(job_id) or {"job_id": job_id}
        for k, v in fields.items():
            if v is not None:
                cur[k] = v
        _JOBS[job_id] = cur
