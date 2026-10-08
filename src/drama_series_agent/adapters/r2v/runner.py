"""H3 R2V episode runner — parallel to h3_episode; does not modify i2v pipeline."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from drama_series_agent.adapters.r2v.continuity import save_tail
from drama_series_agent.adapters.r2v.first_frame import resolve_first_frame_path
from drama_series_agent.adapters.media_ops import concat_videos, extract_tail_frame
from drama_series_agent.adapters.r2v.cast_refs import (
    resolve_cast_series_id,
    resolve_ref_audio_paths,
    resolve_ref_image_paths,
)
from drama_series_agent.adapters.r2v.comfy_cleanup import free_comfyui_memory
from drama_series_agent.adapters.r2v.context_ir import ContextIRMode, apply_context_ir
from drama_series_agent.adapters.r2v.schema import (
    EpisodeMeta,
    ShotRunLine,
    load_episode_meta,
    load_episode_run_jsonl,
)
from drama_series_agent.adapters.r2v.validate import validate_episode_run
from drama_series_agent.adapters.r2v.workflow_materialize import (
    build_r2v_media_params,
    load_base_workflow,
    materialize_r2v_workflow,
    write_temp_workflow,
)
from drama_series_agent.adapters.paths import get_resource_path

# Optional progress hook for Hermes Job Panel / EventBus.
# Payload keys: type, shot_id?, index?, total?, video?, error?, master?
ProgressCallback = Callable[[dict[str, Any]], None]
CancelCheck = Callable[[], bool]


class JobCancelled(Exception):
    """Raised by runner when cancel_check returns True between shots."""

    def __init__(self, shot_id: Optional[str] = None):
        self.shot_id = shot_id
        super().__init__(f"cancelled at {shot_id}" if shot_id else "cancelled")


def _append_status(status_path: Path, record: dict) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    with status_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _download_or_copy(url_or_path: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = Path(url_or_path)
    if src.is_file():
        shutil.copy2(src, dest)
        return dest
    import urllib.request

    urllib.request.urlretrieve(url_or_path, dest)
    return dest


def _resolve_workflow_file(workflow_key: str) -> Path:
    p = Path(workflow_key)
    if p.is_file():
        return p.resolve()
    # selfhost/video_minimax_h3_r2v.json
    if "/" in workflow_key or "\\" in workflow_key:
        source, name = workflow_key.replace("\\", "/").split("/", 1)
        return Path(get_resource_path("workflows", source, name)).resolve()
    return Path(get_resource_path("workflows", "selfhost", workflow_key)).resolve()


async def run_episode(
    *,
    project_root: Path,
    episode_id: str,
    from_shot: Optional[str] = None,
    force: bool = False,
    force_shot_ids: Optional[list[str]] = None,
    core: Any = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    cast_series: Optional[str] = None,
    context_ir: Optional[str] = None,
    context_ir_force: bool = False,
    context_ir_api_with_media: bool = True,
    free_vram_between_shots: bool = True,
    unload_models_between_shots: bool = True,
    progress_callback: Optional[ProgressCallback] = None,
    cancel_check: Optional[CancelCheck] = None,
) -> Path:
    def _emit(payload: dict[str, Any]) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(payload)
        except Exception as e:  # noqa: BLE001 — never break render for UI hooks
            logger.warning(f"progress_callback failed: {e}")

    project_root = project_root.resolve()
    run_dir = project_root / "run"
    meta_path = run_dir / f"{episode_id}.episode-meta.json"
    run_path = run_dir / f"{episode_id}.episode-run.jsonl"
    if not run_path.is_file():
        raise FileNotFoundError(f"missing run file: {run_path}")

    meta = (
        load_episode_meta(meta_path)
        if meta_path.is_file()
        else EpisodeMeta(episode_id=episode_id)
    )
    shots = load_episode_run_jsonl(run_path)
    errs = validate_episode_run(shots)
    if errs:
        raise ValueError("episode-run validation failed:\n- " + "\n- ".join(errs))

    episode_out = project_root / "output" / episode_id
    episode_out.mkdir(parents=True, exist_ok=True)
    status_path = run_dir / f"{episode_id}.status.jsonl"

    if core is None:
        from drama_series_agent.adapters.media_client import get_media_core

        core = get_media_core()
        await core.initialize()

    base_wf_path = _resolve_workflow_file(meta.h3_workflow)
    base_wf = load_base_workflow(base_wf_path)

    force_set = {str(s).strip() for s in (force_shot_ids or []) if str(s).strip()}
    started = from_shot is None
    video_paths: list[Path] = []
    last_shot: Optional[ShotRunLine] = None
    total = len(shots)

    for index, shot in enumerate(shots):
        if not started:
            if shot.shot_id == from_shot:
                started = True
            else:
                existing = episode_out / "shots" / shot.shot_id / "video.mp4"
                if existing.is_file():
                    video_paths.append(existing)
                    _emit(
                        {
                            "type": "shot_skipped",
                            "shot_id": shot.shot_id,
                            "index": index,
                            "total": total,
                            "reason": "before_from_shot",
                            "video": str(existing),
                        }
                    )
                continue

        if cancel_check and cancel_check():
            _emit(
                {
                    "type": "shot_cancelled",
                    "shot_id": shot.shot_id,
                    "index": index,
                    "total": total,
                }
            )
            raise JobCancelled(shot.shot_id)

        shot_dir = episode_out / "shots" / shot.shot_id
        video_dest = shot_dir / "video.mp4"
        tail_dest = shot_dir / "tail_frame.png"

        force_this = force or (shot.shot_id in force_set)
        if video_dest.is_file() and tail_dest.is_file() and not force_this:
            logger.info(f"skip done {shot.shot_id}")
            video_paths.append(video_dest)
            last_shot = shot
            _emit(
                {
                    "type": "shot_skipped",
                    "shot_id": shot.shot_id,
                    "index": index,
                    "total": total,
                    "reason": "already_done",
                    "video": str(video_dest),
                }
            )
            continue

        series_id = resolve_cast_series_id(
            cli_series=cast_series,
            meta_series=meta.cast_series_id,
            shot_series=shot.cast_series_id,
        )

        _emit(
            {
                "type": "shot_started",
                "shot_id": shot.shot_id,
                "index": index,
                "total": total,
                "phase": "sampling",
            }
        )
        try:
            first_path = resolve_first_frame_path(
                shot, project_root=project_root, episode_out=episode_out
            )
            image_paths = resolve_ref_image_paths(
                series_id, first_path, shot.ref_characters
            )
            audio_paths = resolve_ref_audio_paths(series_id, shot.ref_voices)

            wf = materialize_r2v_workflow(
                base_wf,
                n_images=len(image_paths),
                n_audios=len(audio_paths),
                ref_image_size=meta.ref_image_size or "match",
            )
            # Stable path per shot (no UUID) so ComfyUI graph cache is reusable.
            temp_wf = episode_out / "tmp" / f"r2v_{shot.shot_id}.json"
            write_temp_workflow(wf, temp_wf)

            ir_mode: ContextIRMode = (  # type: ignore[assignment]
                (context_ir or getattr(meta, "context_ir", None) or "local")
                .strip()
                .lower()
            )
            if ir_mode not in ("off", "local", "api"):
                raise ValueError(
                    f"context_ir must be off|local|api, got {ir_mode!r}"
                )
            prompt = apply_context_ir(
                shot.video_prompt,
                mode=ir_mode,
                duration_seconds=shot.duration_seconds,
                cache_dir=shot_dir,
                image_paths=image_paths,
                audio_paths=audio_paths,
                ratio=meta.aspect or "9:16",
                force=context_ir_force or force,
                api_with_media=context_ir_api_with_media,
            )

            media_kwargs = build_r2v_media_params(
                prompt=prompt,
                duration=shot.duration_seconds,
                image_paths=image_paths,
                audio_paths=audio_paths,
                width=width,
                height=height,
            )
            media = await core.media(
                media_kwargs.pop("prompt"),
                workflow=str(temp_wf),
                media_type="video",
                **media_kwargs,
            )
            _download_or_copy(media.url, video_dest)
            extract_tail_frame(video_dest, tail_dest)

            _append_status(
                status_path,
                {
                    "shot_id": shot.shot_id,
                    "status": "done",
                    "at": datetime.now(timezone.utc).isoformat(),
                    "cast_series_id": series_id,
                    "n_images": len(image_paths),
                    "n_audios": len(audio_paths),
                    "context_ir": ir_mode,
                    "prompt_chars": len(prompt),
                    "video": str(video_dest),
                },
            )
            video_paths.append(video_dest)
            last_shot = shot
            _emit(
                {
                    "type": "shot_done",
                    "shot_id": shot.shot_id,
                    "index": index,
                    "total": total,
                    "video": str(video_dest),
                    "tail": str(tail_dest),
                }
            )
        except Exception as e:
            _append_status(
                status_path,
                {
                    "shot_id": shot.shot_id,
                    "status": "failed",
                    "error": str(e),
                    "at": datetime.now(timezone.utc).isoformat(),
                },
            )
            _emit(
                {
                    "type": "shot_failed",
                    "shot_id": shot.shot_id,
                    "index": index,
                    "total": total,
                    "error": str(e),
                }
            )
            raise
        finally:
            # Default: full /free — unload models + drop caches so the next shot
            # starts with a clean VRAM slate (avoids BlockCache / latent bleed).
            # Pass unload_models_between_shots=False to keep weights warm if desired.
            if free_vram_between_shots:
                free_comfyui_memory(
                    core=core,
                    unload_models=unload_models_between_shots,
                    free_memory=True,
                )
                _emit(
                    {
                        "type": "shot_phase",
                        "shot_id": shot.shot_id,
                        "index": index,
                        "total": total,
                        "phase": "freeing_vram",
                    }
                )

    master = episode_out / "master.mp4"
    if video_paths:
        concat_videos(video_paths, master)
    if last_shot is not None:
        tail = episode_out / "shots" / last_shot.shot_id / "tail_frame.png"
        if tail.is_file():
            save_tail(
                project_root / "continuity" / "episode-tails.json",
                episode_id,
                str(tail),
                last_shot.shot_id,
            )
    logger.info(f"R2V episode done: {master}")
    _emit(
        {
            "type": "episode_done",
            "master": str(master),
            "total": total,
            "n_videos": len(video_paths),
        }
    )
    return master
