# -*- coding: utf-8 -*-
"""Status bar + workbench open hints from series_runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from drama_series_agent.drama.runtime import load_runtime

_AUDIO_ZH = {
    "missing": "缺失",
    "deferred": "已暂缓",
    "ready": "就绪",
    "accepted": "已验收",
}

_STATUS_ZH = {
    "draft": "草稿",
    "accepted": "已验收",
    "dirty": "已改动",
    "missing": "缺失",
    "promoted_unaccepted": "待验收",
}


def _literary_artifacts(project_dir: Path) -> dict[str, Any]:
    try:
        from drama_series_agent.drama.asset_studio import list_literary_episodes

        raw = list_literary_episodes(project_dir=project_dir)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "episodes": [], "index": None}

    episodes: list[dict[str, Any]] = []
    for ep in raw.get("episodes") or []:
        preview = ""
        path = Path(ep.get("path") or "")
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
                preview = text[:240]
                if len(text) > 240:
                    preview += "…"
            except Exception:  # noqa: BLE001
                preview = ""
        st = str(ep.get("status") or "draft")
        episodes.append(
            {
                "episode_id": ep.get("episode_id"),
                "status": st,
                "status_zh": _STATUS_ZH.get(st, st),
                "bytes": ep.get("bytes"),
                "mtime": ep.get("mtime"),
                "preview": preview,
                "path": ep.get("path"),
            }
        )
    index = raw.get("index") or {}
    return {
        "ok": True,
        "literary_accepted": bool(raw.get("literary_accepted")),
        "premise": index.get("premise"),
        "genre": index.get("genre"),
        "index_status": index.get("status"),
        "episodes": episodes,
        "episodes_dir": raw.get("episodes_dir"),
    }


def _cast_artifacts(project_dir: Path) -> dict[str, Any]:
    try:
        from drama_series_agent.drama.asset_studio import list_cast_assets

        raw = list_cast_assets(project_dir=project_dir)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "assets": []}

    assets = []
    for a in raw.get("assets") or []:
        st = str(a.get("status") or "missing")
        assets.append(
            {
                "name": a.get("name"),
                "role": a.get("role"),
                "status": st,
                "status_zh": _STATUS_ZH.get(st, st),
                "has_draft": bool(a.get("draft_path")),
                "has_final": bool(a.get("final_path")),
            }
        )
    return {"ok": True, "assets": assets}


def _s2_snapshot(project_dir: Path, rt: Any) -> dict[str, Any]:
    episode_id = str(getattr(rt, "next_episode", None) or "EP001")
    snap: dict[str, Any] = {
        "episode_id": episode_id,
        "default_workflow": getattr(rt, "default_workflow", None),
        "aspect": getattr(rt, "aspect", None) or "9:16",
        "context_ir": getattr(rt, "context_ir", None) or "off",
        "ready_for_s2": bool((rt.s1_gate or {}).get("ready_for_s2")),
        "jsonl_exists": False,
        "jsonl_path": None,
        "shot_count": None,
        "valid": None,
        "errors": [],
    }
    try:
        from drama_series_agent.drama.build_worker import validate_episode_run_project

        val = validate_episode_run_project(
            project_dir=project_dir, episode_id=episode_id
        )
        snap["jsonl_path"] = val.get("jsonl_path")
        snap["jsonl_exists"] = bool(val.get("ok"))
        snap["shot_count"] = val.get("shot_count")
        snap["valid"] = val.get("valid")
        snap["errors"] = (val.get("errors") or [])[:6]
    except Exception as e:  # noqa: BLE001
        snap["errors"] = [str(e)]
    ep_row = dict((getattr(rt, "episodes", None) or {}).get(episode_id) or {})
    snap["episode_status"] = ep_row.get("status")
    snap["resume_from_shot"] = ep_row.get("resume_from_shot")
    return snap


def build_status_payload(project_dir: Path) -> dict[str, Any]:
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    gate = dict(rt.s1_gate or {})
    lit_ok = bool(gate.get("literary_accepted"))
    cast_ok = bool(gate.get("cast_leads_accepted"))
    audio = str(gate.get("audio_status") or "missing")
    audio_zh = _AUDIO_ZH.get(audio, audio)
    active = list(rt.active_job_ids or [])
    enrich_jobs = list(getattr(rt, "enrich_jobs", None) or [])
    literary = _literary_artifacts(project_dir)
    cast = _cast_artifacts(project_dir)
    has_lit_files = bool(literary.get("episodes"))
    has_cast = bool(cast.get("assets"))
    job = active[-1] if active else "idle"
    # Open when gates incomplete, jobs running, or there is stage output to review
    open_wb = (
        (not bool(gate.get("ready_for_s2")))
        or bool(active)
        or has_lit_files
        or has_cast
    )
    label = (
        f"阶段={rt.stage} | "
        f"文学{'✓' if lit_ok else '…'} "
        f"角色{'✓' if cast_ok else '…'} "
        f"音频{audio_zh} | Job:{job}"
    )
    return {
        "series_id": rt.series_id,
        "stage": rt.stage,
        "next_episode": rt.next_episode,
        "s1_gate": gate,
        "active_job_ids": active,
        "enrich_jobs": enrich_jobs[-8:],
        "open_workbench": open_wb,
        "status_label_zh": label,
        "artifacts": {
            "literary": literary,
            "cast": cast,
        },
        "s2": _s2_snapshot(project_dir, rt),
    }
