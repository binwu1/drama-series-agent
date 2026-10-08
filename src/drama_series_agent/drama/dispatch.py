# -*- coding: utf-8 -*-
"""Dispatch S1 Asset Studio + S1-B enrich + S2/S3 tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drama_series_agent.drama.asset_studio import (
    get_literary_episode,
    import_literary_file,
    invalidate_accept,
    list_cast_assets,
    list_literary_episodes,
    open_cast_folder,
    open_literary_external,
    open_literary_folder,
    open_path_external,
    reject_cast_image,
    save_literary_episode,
    upload_cast_image,
)
from drama_series_agent.drama.build_worker import (
    enqueue_build_episode_jsonl,
    run_s2_build_and_comfy,
    validate_episode_run_project,
)
from drama_series_agent.drama.comfy_worker import (
    enqueue_comfy_episode,
    get_job_snapshot,
    list_active_jobs,
)
from drama_series_agent.drama.completion import on_episode_complete
from drama_series_agent.drama.enrich import (
    accept_cast_images,
    accept_literary_package,
    extract_cast_table,
    get_s1_gate_status,
    mark_audio_deferred,
    run_cast_image_generate,
    run_literary_generate,
)
from drama_series_agent.drama.next_episode import (
    continue_series,
    ensure_literary_for_episode,
    get_series_progress,
    prefetch_next_episode,
    propose_voice_harvest,
)
from drama_series_agent.drama.review import (
    accept_episode,
    accept_shot,
    get_shot_prompt,
    list_episode_shots,
    lock_shot,
    patch_shot_prompt,
    reject_shot,
    rerun_shots,
    unlock_shot,
)
from drama_series_agent.drama.event_bus import get_event_bus
from drama_series_agent.drama.runtime import (
    default_runtime,
    load_runtime,
    save_runtime,
)


def handle_tool_call(name: str, args: dict[str, Any]) -> str:
    try:
        return json.dumps(_dispatch(name, args or {}), ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {"ok": False, "error": str(e), "tool": name}, ensure_ascii=False
        )


def _dispatch(name: str, args: dict[str, Any]) -> Any:
    bus = get_event_bus()

    # --- S1 Asset Studio ---
    if name == "list_literary_episodes":
        return list_literary_episodes(project_dir=Path(args["project_dir"]))

    if name == "get_literary_episode":
        return get_literary_episode(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
        )

    if name == "save_literary_episode":
        return save_literary_episode(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            content=args["content"],
            invalidate=args.get("invalidate", True),
        )

    if name == "open_literary_external":
        return open_literary_external(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
        )

    if name == "open_literary_folder":
        return open_literary_folder(project_dir=Path(args["project_dir"]))

    if name == "import_literary_file":
        return import_literary_file(
            project_dir=Path(args["project_dir"]),
            source_path=args["source_path"],
            episode_id=args.get("episode_id"),
        )

    if name == "list_cast_assets":
        return list_cast_assets(project_dir=Path(args["project_dir"]))

    if name == "upload_cast_image":
        return upload_cast_image(
            project_dir=Path(args["project_dir"]),
            character=args["character"],
            source_path=args["source_path"],
        )

    if name == "reject_cast_image":
        return reject_cast_image(
            project_dir=Path(args["project_dir"]),
            character=args["character"],
        )

    if name == "open_cast_folder":
        return open_cast_folder(
            project_dir=Path(args["project_dir"]),
            draft=args.get("draft", True),
        )

    if name == "open_path_external":
        return open_path_external(path=args["path"])

    if name == "invalidate_accept":
        return invalidate_accept(
            project_dir=Path(args["project_dir"]),
            scope=args.get("scope") or "all",
            reason=args.get("reason") or "manual",
            character=args.get("character"),
        )

    # --- S1 develop / series bible ---
    if name == "get_series_bible_status":
        from drama_series_agent.drama.series_bible import get_series_bible_status

        return get_series_bible_status(project_dir=Path(args["project_dir"]))

    if name == "run_series_develop":
        from drama_series_agent.drama.series_bible import run_series_develop

        return run_series_develop(
            project_dir=Path(args["project_dir"]),
            brief=args["brief"],
            title=args.get("title"),
            genre=args.get("genre"),
            art_direction_hint=args.get("art_direction_hint"),
            run_in_background=args.get("run_in_background", True),
        )

    if name == "save_series_bible_doc":
        from drama_series_agent.drama.series_bible import save_series_bible_doc

        return save_series_bible_doc(
            project_dir=Path(args["project_dir"]),
            file_name=args["file_name"],
            content=args["content"],
        )

    # --- S1-B enrich ---
    if name == "run_literary_generate":
        return run_literary_generate(
            project_dir=Path(args["project_dir"]),
            premise=args["premise"],
            episode_count=int(args.get("episode_count") or 1),
            genre=args.get("genre") or "短剧",
            episode_ids=args.get("episode_ids"),
            revision_notes=args.get("revision_notes"),
            run_in_background=bool(args.get("run_in_background")),
            force=bool(args.get("force")),
            use_skill=True,
            chain_s2=bool(args.get("chain_s2")),
            bus=bus,
        )

    if name == "accept_literary_package":
        return accept_literary_package(
            project_dir=Path(args["project_dir"]),
            decided_by=args.get("decided_by") or "creator",
        )

    if name == "extract_cast_table":
        return extract_cast_table(project_dir=Path(args["project_dir"]))

    if name == "run_cast_image_generate":
        return run_cast_image_generate(
            project_dir=Path(args["project_dir"]),
            characters=args.get("characters"),
            style=args.get("style") or "cinematic portrait, front view",
            revision_notes=args.get("revision_notes"),
            run_in_background=bool(args.get("run_in_background")),
            bus=bus,
        )

    if name == "accept_cast_images":
        return accept_cast_images(
            project_dir=Path(args["project_dir"]),
            characters=args.get("characters"),
            decided_by=args.get("decided_by") or "creator",
        )

    if name == "mark_audio_deferred":
        return mark_audio_deferred(project_dir=Path(args["project_dir"]))

    if name == "get_s1_gate_status":
        return get_s1_gate_status(project_dir=Path(args["project_dir"]))

    # --- S2 ---
    if name == "enqueue_build_episode_jsonl":
        return enqueue_build_episode_jsonl(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            force=bool(args.get("force")),
            shot_count=args.get("shot_count"),
            run_in_background=bool(args.get("run_in_background")),
            bus=bus,
        )

    if name == "validate_episode_run":
        return validate_episode_run_project(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
        )

    if name == "run_s2_build_and_comfy":
        return run_s2_build_and_comfy(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            force_build=bool(args.get("force_build")),
            from_shot=args.get("from_shot"),
            run_comfy_in_background=args.get("run_comfy_in_background", True),
            skip_comfy=bool(args.get("skip_comfy")),
            bus=bus,
        )

    if name == "resume_from_shot":
        return enqueue_comfy_episode(
            hermes_project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            from_shot=args["from_shot"],
            force=bool(args.get("force")),
            run_in_background=args.get("run_in_background", True),
            bus=bus,
        )

    # --- S3 ---
    if name == "prefetch_next_episode":
        return prefetch_next_episode(
            project_dir=Path(args["project_dir"]),
            episode_id=args.get("episode_id"),
            user_text=args.get("user_text") or args.get("text"),
        )

    if name == "ensure_literary_for_episode":
        return ensure_literary_for_episode(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            premise=args.get("premise"),
            revision_notes=args.get("revision_notes"),
            bus=bus,
        )

    if name == "continue_series":
        return continue_series(
            project_dir=Path(args["project_dir"]),
            user_text=args.get("user_text") or args.get("text"),
            episode_id=args.get("episode_id"),
            auto_build_comfy=args.get("auto_build_comfy", True),
            force_build=bool(args.get("force_build")),
            skip_comfy=bool(args.get("skip_comfy")),
            run_comfy_in_background=args.get("run_comfy_in_background", True),
            bus=bus,
        )

    if name == "get_series_progress":
        return get_series_progress(project_dir=Path(args["project_dir"]))

    if name == "propose_voice_harvest":
        return propose_voice_harvest(
            project_dir=Path(args["project_dir"]),
            episode_id=args.get("episode_id"),
        )

    # --- S4 Review ---
    if name == "list_episode_shots":
        return list_episode_shots(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
        )

    if name == "get_shot_prompt":
        return get_shot_prompt(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            shot_id=args["shot_id"],
        )

    if name == "patch_shot_prompt":
        return patch_shot_prompt(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            shot_id=args["shot_id"],
            video_prompt=args.get("video_prompt"),
            duration_seconds=args.get("duration_seconds"),
            validate=args.get("validate", True),
        )

    if name == "accept_shot":
        return accept_shot(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            shot_id=args["shot_id"],
            lock=bool(args.get("lock")),
            decided_by=args.get("decided_by") or "creator",
        )

    if name == "reject_shot":
        return reject_shot(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            shot_id=args["shot_id"],
            reason=args.get("reason") or "",
        )

    if name == "lock_shot":
        return lock_shot(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            shot_id=args["shot_id"],
        )

    if name == "unlock_shot":
        return unlock_shot(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            shot_id=args["shot_id"],
        )

    if name == "accept_episode":
        return accept_episode(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            lock_all=bool(args.get("lock_all")),
            decided_by=args.get("decided_by") or "creator",
        )

    if name == "rerun_shots":
        return rerun_shots(
            project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            shot_ids=args.get("shot_ids"),
            force=bool(args.get("force")),
            run_in_background=args.get("run_in_background", True),
            bus=bus,
        )

    # --- S2/S3 shared ---
    if name == "select_workflow":
        project_dir = Path(args["project_dir"])
        rt = _ensure_runtime(project_dir, args)
        rt.default_workflow = args["workflow"]
        if args.get("aspect"):
            rt.aspect = args["aspect"]
        if args.get("context_ir"):
            rt.context_ir = args["context_ir"]
        save_runtime(project_dir, rt)
        return {"ok": True, "runtime": rt.to_dict()}

    if name == "resolve_episode_intent":
        project_dir = Path(args["project_dir"])
        rt = load_runtime(project_dir)
        ep = rt.resolve_episode_intent(args["text"])
        return {"ok": True, "episode_id": ep, "series_id": rt.series_id}

    if name == "get_job_status":
        job_id = args["job_id"]
        events = bus.history(series_id=args.get("series_id"), job_id=job_id)
        return {
            "ok": True,
            "job_id": job_id,
            "snapshot": get_job_snapshot(job_id),
            "events": [e.to_dict() for e in events],
        }

    if name == "list_active_jobs":
        return {"ok": True, "jobs": list_active_jobs(args.get("series_id"))}

    if name == "on_episode_complete":
        return on_episode_complete(
            Path(args["project_dir"]),
            episode_id=args["episode_id"],
            master_path=args.get("master_path"),
            jsonl_path=args.get("jsonl_path"),
            workflow=args.get("workflow"),
            failed_shots=args.get("failed_shots"),
            bus=bus,
            job_id=args.get("job_id"),
        )

    if name == "enqueue_comfy_episode":
        return enqueue_comfy_episode(
            hermes_project_dir=Path(args["project_dir"]),
            episode_id=args["episode_id"],
            from_shot=args.get("from_shot"),
            force=bool(args.get("force")),
            cast_series=args.get("cast_series"),
            context_ir=args.get("context_ir"),
            run_in_background=args.get("run_in_background", True),
            bus=bus,
        )

    raise ValueError(f"unknown hermes_drama tool: {name}")


def _ensure_runtime(project_dir: Path, args: dict[str, Any]):
    path = project_dir / "series_runtime.json"
    if path.is_file():
        return load_runtime(project_dir)
    series_id = args.get("series_id") or project_dir.name
    rt = default_runtime(series_id)
    save_runtime(project_dir, rt)
    return rt
