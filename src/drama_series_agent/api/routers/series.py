# -*- coding: utf-8 -*-
"""Hermes Agent API — conversations, chat, workbench actions, job SSE."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from drama_series_agent.api.schemas.hermes import (
    ActionResponse,
    CastGenerateRequest,
    CastUploadResponse,
    ConversationDetail,
    ConversationOut,
    CreateConversationRequest,
    HermesSettingsOut,
    HermesSettingsUpdate,
    JobControlRequest,
    LiteraryEpisodeOut,
    LiterarySaveRequest,
    LlmTestRequest,
    LlmTestResponse,
    PostMessageRequest,
    PostMessageResponse,
    S2ActionRequest,
)
from drama_series_agent.agent.chat_store import append_message, load_messages
from drama_series_agent.agent.paths import default_workspace_root
from drama_series_agent.agent.session_store import (
    create_conversation,
    get_conversation,
    list_conversations,
)
from drama_series_agent.agent.ui_hints import build_status_payload

router = APIRouter(prefix="/series", tags=["Drama Series Agent"])


def _drama_series_root() -> Path:
    env = os.environ.get("DRAMA_SERIES_ROOT")
    if env:
        return Path(env)
    return default_workspace_root()


def _require_conv(cid: str) -> dict[str, Any]:
    row = get_conversation(cid, drama_series_root=_drama_series_root())
    if not row:
        raise HTTPException(status_code=404, detail=f"conversation not found: {cid}")
    return row


def _project(row: dict[str, Any]) -> Path:
    return Path(row["project_dir"])


@router.get("/conversations", response_model=list[ConversationOut])
def api_list_conversations() -> list[dict[str, Any]]:
    return list_conversations(drama_series_root=_drama_series_root())


@router.post("/conversations", response_model=ConversationOut)
def api_create_conversation(body: CreateConversationRequest) -> dict[str, Any]:
    return create_conversation(
        title=body.title,
        drama_series_root=_drama_series_root(),
        premise=body.premise,
    )


@router.get("/conversations/{cid}", response_model=ConversationDetail)
def api_get_conversation(cid: str) -> dict[str, Any]:
    row = _require_conv(cid)
    status = build_status_payload(_project(row))
    return {**row, "status": status}


@router.get("/conversations/{cid}/messages")
def api_list_messages(cid: str) -> list[dict[str, Any]]:
    row = _require_conv(cid)
    return load_messages(_project(row))


@router.post("/conversations/{cid}/messages", response_model=PostMessageResponse)
async def api_post_message(cid: str, body: PostMessageRequest) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    text = (body.content or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="content required")

    append_message(project, role="user", content=text)

    from drama_series_agent.agent.agent_loop import run_agent_turn

    return await run_agent_turn(project_dir=project, user_text=text)


@router.post(
    "/conversations/{cid}/actions/accept_literary",
    response_model=ActionResponse,
)
def api_accept_literary(cid: str) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.enrich import accept_literary_package

    try:
        accept_literary_package(project_dir=project)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    msg = "已验收文学包。"
    append_message(project, role="assistant", content=msg)
    return {"ok": True, "status": build_status_payload(project), "message": msg}


@router.post(
    "/conversations/{cid}/actions/accept_cast",
    response_model=ActionResponse,
)
def api_accept_cast(cid: str) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.enrich import accept_cast_images

    try:
        accept_cast_images(project_dir=project)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    msg = "已验收角色图。"
    append_message(project, role="assistant", content=msg)
    return {"ok": True, "status": build_status_payload(project), "message": msg}


@router.post(
    "/conversations/{cid}/actions/defer_audio",
    response_model=ActionResponse,
)
def api_defer_audio(cid: str) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.enrich import mark_audio_deferred

    mark_audio_deferred(project_dir=project)
    msg = "音频已暂缓（Deferred）。"
    append_message(project, role="assistant", content=msg)
    return {"ok": True, "status": build_status_payload(project), "message": msg}


def _episode_id(body: Optional[S2ActionRequest], project: Path) -> str:
    if body and body.episode_id:
        return body.episode_id.strip()
    from drama_series_agent.drama.runtime import load_runtime

    return str(load_runtime(project).next_episode or "EP001")


@router.post("/conversations/{cid}/s2/build", response_model=ActionResponse)
def api_s2_build(cid: str, body: S2ActionRequest | None = None) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.build_worker import enqueue_build_episode_jsonl

    ep = _episode_id(body, project)
    try:
        out = enqueue_build_episode_jsonl(
            project_dir=project,
            episode_id=ep,
            force=bool(body.force) if body else False,
            run_in_background=False,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    msg = f"S2 已构建 {ep} jsonl（{out.get('job_id')}）。"
    append_message(project, role="assistant", content=msg)
    return {"ok": True, "status": build_status_payload(project), "message": msg}


@router.post("/conversations/{cid}/s2/validate", response_model=ActionResponse)
def api_s2_validate(cid: str, body: S2ActionRequest | None = None) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.build_worker import validate_episode_run_project

    ep = _episode_id(body, project)
    val = validate_episode_run_project(project_dir=project, episode_id=ep)
    if val.get("valid"):
        msg = f"S2 校验通过 · {ep} · {val.get('shot_count')} 镜"
        ok = True
    else:
        errs = "; ".join(val.get("errors") or [])
        msg = f"S2 校验失败 · {ep} · {errs}"
        ok = False
    return {
        "ok": ok,
        "status": build_status_payload(project),
        "message": msg,
    }


@router.post("/conversations/{cid}/s2/comfy", response_model=ActionResponse)
def api_s2_comfy(cid: str, body: S2ActionRequest | None = None) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.comfy_worker import enqueue_comfy_episode
    from drama_series_agent.drama.runtime import load_runtime, save_runtime

    ep = _episode_id(body, project)
    rt = load_runtime(project)
    if not rt.default_workflow:
        rt.default_workflow = "selfhost/video_minimax_h3_r2v_fast.json"
        save_runtime(project, rt)
    try:
        result = enqueue_comfy_episode(
            hermes_project_dir=project,
            episode_id=ep,
            from_shot=(body.from_shot.strip() if body and body.from_shot else None),
            run_in_background=True if body is None else body.run_in_background,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    msg = f"S2 已入队 Comfy {ep}（{result.get('job_id')}）。"
    append_message(project, role="assistant", content=msg)
    return {"ok": True, "status": build_status_payload(project), "message": msg}


@router.get("/conversations/{cid}/literary")
def api_list_literary(cid: str) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.asset_studio import list_literary_episodes

    data = list_literary_episodes(project_dir=project)
    return {
        "ok": True,
        "conversation_id": cid,
        "series_id": row["series_id"],
        "title": row.get("title"),
        "episodes": data.get("episodes") or [],
        "index": data.get("index"),
        "literary_accepted": data.get("literary_accepted"),
        "status": build_status_payload(project),
    }


@router.get(
    "/conversations/{cid}/literary/{episode_id}",
    response_model=LiteraryEpisodeOut,
)
def api_get_literary(cid: str, episode_id: str) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.asset_studio import get_literary_episode

    try:
        data = get_literary_episode(project_dir=project, episode_id=episode_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    meta = data.get("meta") or {}
    st = meta.get("status")
    zh = {"draft": "草稿", "accepted": "已验收", "dirty": "已改动"}.get(st or "", st)
    return {
        "episode_id": data["episode_id"],
        "content": data.get("content") or "",
        "status": st,
        "status_zh": zh,
        "series_id": row["series_id"],
        "title": row.get("title"),
    }


@router.put(
    "/conversations/{cid}/literary/{episode_id}",
    response_model=LiteraryEpisodeOut,
)
def api_save_literary(
    cid: str, episode_id: str, body: LiterarySaveRequest
) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.asset_studio import (
        get_literary_episode,
        save_literary_episode,
    )

    try:
        save_literary_episode(
            project_dir=project,
            episode_id=episode_id,
            content=body.content or "",
            invalidate=True,
        )
        data = get_literary_episode(project_dir=project, episode_id=episode_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    meta = data.get("meta") or {}
    st = meta.get("status")
    zh = {"draft": "草稿", "accepted": "已验收", "dirty": "已改动"}.get(st or "", st)
    append_message(
        project,
        role="assistant",
        content=f"已保存文学 {episode_id}（系列「{row.get('title') or row['series_id']}」）。",
    )
    return {
        "episode_id": data["episode_id"],
        "content": data.get("content") or "",
        "status": st,
        "status_zh": zh,
        "series_id": row["series_id"],
        "title": row.get("title"),
    }


@router.get("/conversations/{cid}/cast")
def api_list_cast(cid: str) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.asset_studio import list_cast_assets
    from drama_series_agent.intake.scaffold import load_project
    import json

    data = list_cast_assets(project_dir=project)
    appearance_map: dict[str, str] = {}
    try:
        cast_dir = Path((load_project(project).get("mounts") or {})["cast_dir"])
        table_path = cast_dir / "cast_table.json"
        if table_path.is_file():
            table = json.loads(table_path.read_text(encoding="utf-8"))
            for c in table.get("characters") or []:
                if c.get("name") and c.get("appearance"):
                    appearance_map[str(c["name"])] = str(c["appearance"])
    except Exception:  # noqa: BLE001
        pass
    assets = []
    for a in data.get("assets") or []:
        name = a.get("name") or ""
        has_draft = bool(a.get("draft_path"))
        has_final = bool(a.get("final_path"))
        assets.append(
            {
                **a,
                "appearance": appearance_map.get(name) or a.get("appearance"),
                "has_draft": has_draft,
                "has_final": has_final,
                "image_url": (
                    f"/api/series/conversations/{cid}/cast/{name}/image"
                    if has_draft or has_final or a.get("preview_path")
                    else None
                ),
            }
        )
    # Also include cast_table characters that have no files yet
    for name, appearance in appearance_map.items():
        if any(x.get("name") == name for x in assets):
            continue
        assets.append(
            {
                "name": name,
                "role": "lead",
                "status": "missing",
                "status_zh": "缺失",
                "appearance": appearance,
                "has_draft": False,
                "has_final": False,
                "draft_path": None,
                "final_path": None,
                "preview_path": None,
                "image_url": None,
            }
        )
    return {
        "ok": True,
        "conversation_id": cid,
        "series_id": row["series_id"],
        "title": row.get("title"),
        "assets": assets,
        "cast_leads_accepted": data.get("cast_leads_accepted"),
        "status": build_status_payload(project),
    }


@router.get("/conversations/{cid}/cast/{character}/image")
def api_cast_image(cid: str, character: str):
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.asset_studio import list_cast_assets

    data = list_cast_assets(project_dir=project)
    asset = next(
        (a for a in (data.get("assets") or []) if a.get("name") == character),
        None,
    )
    if not asset:
        raise HTTPException(status_code=404, detail="character not found")
    path = asset.get("preview_path") or asset.get("draft_path") or asset.get("final_path")
    if not path or not Path(path).is_file():
        raise HTTPException(status_code=404, detail="image not found")
    resolved = Path(path).resolve()
    suffix = resolved.suffix.lower()
    media = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "application/octet-stream")
    return FileResponse(resolved, media_type=media)


@router.post(
    "/conversations/{cid}/cast/characters",
    response_model=CastUploadResponse,
)
def api_cast_add_character(cid: str, body: CastGenerateRequest) -> dict[str, Any]:
    """Create a character slot (name + optional appearance) without generating image yet."""
    row = _require_conv(cid)
    project = _project(row)
    character = (body.character or "").strip()
    if not character:
        raise HTTPException(status_code=400, detail="character required")
    _persist_cast_appearance(
        project_dir=project,
        character=character,
        appearance=(body.appearance or "").strip(),
    )
    msg = f"已新增角色「{character}」（系列「{row.get('title') or row['series_id']}」）。"
    append_message(project, role="assistant", content=msg)
    return {
        "ok": True,
        "character": character,
        "status": build_status_payload(project),
        "message": msg,
    }


@router.post(
    "/conversations/{cid}/cast/upload",
    response_model=CastUploadResponse,
)
async def api_cast_upload(
    cid: str,
    character: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    import tempfile

    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.asset_studio import upload_cast_image

    suffix = Path(file.filename or "upload.png").suffix.lower() or ".png"
    tmp_path: Optional[Path] = None
    try:
        raw = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = Path(tmp.name)
        upload_cast_image(
            project_dir=project,
            character=character,
            source_path=tmp_path,
            invalidate=True,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
    append_message(
        project,
        role="assistant",
        content=f"已上传角色图「{character}」（系列「{row.get('title') or row['series_id']}」）。",
    )
    return {
        "ok": True,
        "character": character,
        "status": build_status_payload(project),
        "message": f"已上传 {character}",
    }


def _persist_cast_appearance(*, project_dir: Path, character: str, appearance: str) -> None:
    """Upsert appearance text on cast_table.json for this series only."""
    import json
    from drama_series_agent.intake.scaffold import load_project

    cast_dir = Path((load_project(project_dir).get("mounts") or {})["cast_dir"])
    cast_dir.mkdir(parents=True, exist_ok=True)
    table_path = cast_dir / "cast_table.json"
    table: dict[str, Any]
    if table_path.is_file():
        table = json.loads(table_path.read_text(encoding="utf-8"))
    else:
        table = {"characters": [], "series_id": project_dir.name}
    chars = list(table.get("characters") or [])
    found = False
    for c in chars:
        if c.get("name") == character:
            c["appearance"] = appearance
            c["image_status"] = c.get("image_status") or "missing"
            found = True
            break
    if not found:
        chars.append(
            {
                "name": character,
                "role": "lead",
                "appearance": appearance,
                "image_status": "missing",
                "accepted": False,
            }
        )
    table["characters"] = chars
    table_path.write_text(
        json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


@router.post(
    "/conversations/{cid}/cast/generate",
    response_model=CastUploadResponse,
)
async def api_cast_generate(cid: str, body: CastGenerateRequest) -> dict[str, Any]:
    """Generate cast draft via Flux / configured image workflow, then save under this series."""
    import shutil
    import tempfile

    from api.dependencies import get_drama_series_agent
    from drama_series_agent.adapters.config import config_manager
    from drama_series_agent.drama.asset_studio import upload_cast_image

    row = _require_conv(cid)
    project = _project(row)
    character = (body.character or "").strip()
    appearance = (body.appearance or "").strip()
    if not character:
        raise HTTPException(status_code=400, detail="character required")
    if not appearance:
        raise HTTPException(status_code=400, detail="请填写角色外貌描述")

    _persist_cast_appearance(
        project_dir=project, character=character, appearance=appearance
    )

    style = (body.style or "").strip()
    prompt = f"{character}, {appearance}"
    if style:
        prompt = f"{prompt}, {style}"

    comfy = config_manager.get_comfyui_config()
    image_cfg = comfy.get("image") or {}
    workflow = (
        image_cfg.get("default_workflow")
        or image_cfg.get("reference_workflow")
        or "selfhost/image_flux.json"
    )

    drama_series_agent = await get_drama_series_agent()
    try:
        media_result = await drama_series_agent.media(
            prompt=prompt,
            workflow=workflow,
            width=body.width or 1024,
            height=body.height or 1024,
            media_type="image",
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Flux/图像生成失败：{e}") from e

    if getattr(media_result, "is_video", False):
        raise HTTPException(status_code=400, detail="工作流返回了视频，请改用图像工作流")

    src = Path(str(media_result.url))
    tmp_path: Optional[Path] = None
    try:
        if not src.is_file():
            # URL may be http — download via httpx
            import httpx

            suffix = ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = Path(tmp.name)
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.get(str(media_result.url))
                r.raise_for_status()
                tmp_path.write_bytes(r.content)
            src = tmp_path
        else:
            # Copy into temp with proper suffix for upload_cast_image
            suffix = src.suffix.lower() or ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = Path(tmp.name)
            shutil.copy2(src, tmp_path)
            src = tmp_path

        upload_cast_image(
            project_dir=project,
            character=character,
            source_path=src,
            invalidate=True,
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass

    msg = f"已用 Flux 生成角色图「{character}」（系列「{row.get('title') or row['series_id']}」）。"
    append_message(project, role="assistant", content=msg)
    return {
        "ok": True,
        "character": character,
        "status": build_status_payload(project),
        "message": msg,
    }


@router.get("/conversations/{cid}/jobs")
def api_jobs(cid: str) -> dict[str, Any]:
    """Job snapshots + recent events for the progress page."""
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.comfy_worker import get_job_snapshot, list_active_jobs
    from drama_series_agent.drama.event_bus import get_event_bus
    from drama_series_agent.drama.runtime import load_runtime

    rt = load_runtime(project)
    by_id: dict[str, dict[str, Any]] = {}
    for snap in list_active_jobs(rt.series_id):
        jid = str(snap.get("job_id") or "")
        if jid:
            by_id[jid] = snap
    for jid in list(rt.active_job_ids or []):
        if jid in by_id:
            continue
        snap = get_job_snapshot(jid)
        by_id[jid] = snap or {"job_id": jid, "status": "unknown", "phase": "unknown"}

    events: list[dict[str, Any]] = []
    log = project / "jobs" / "events.jsonl"
    if log.is_file():
        lines = log.read_text(encoding="utf-8").splitlines()
        for line in lines[-60:]:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:  # noqa: BLE001
                continue
    else:
        events = [
            e.to_dict() for e in get_event_bus().history(series_id=rt.series_id)[-60:]
        ]
    status = build_status_payload(project)
    return {
        "ok": True,
        "series_id": rt.series_id,
        "stage": rt.stage,
        "next_episode": rt.next_episode,
        "jobs": list(by_id.values()),
        "events": events,
        "s2": status.get("s2"),
        "status": status,
    }


@router.post("/conversations/{cid}/jobs/cancel", response_model=ActionResponse)
def api_jobs_cancel(cid: str, body: JobControlRequest | None = None) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.comfy_worker import cancel_job

    result = cancel_job(
        hermes_project_dir=project,
        job_id=(body.job_id if body else None),
        episode_id=(body.episode_id if body else None),
    )
    msg = result.get("message") or ("已请求中断" if result.get("ok") else "中断失败")
    return {
        "ok": bool(result.get("ok")),
        "status": build_status_payload(project),
        "message": msg,
    }


@router.post("/conversations/{cid}/jobs/resume", response_model=ActionResponse)
def api_jobs_resume(cid: str, body: JobControlRequest | None = None) -> dict[str, Any]:
    row = _require_conv(cid)
    project = _project(row)
    from drama_series_agent.drama.comfy_worker import resume_episode

    result = resume_episode(
        hermes_project_dir=project,
        episode_id=(body.episode_id if body else None),
        from_shot=(body.from_shot if body else None),
        force=bool(body.force) if body else False,
        run_in_background=True if body is None else body.run_in_background,
    )
    msg = result.get("message") or (
        f"已续跑 {result.get('job_id')}" if result.get("ok") else "续跑失败"
    )
    return {
        "ok": bool(result.get("ok")),
        "status": build_status_payload(project),
        "message": msg if result.get("ok") else (result.get("message") or result.get("error")),
    }


@router.get("/conversations/{cid}/events")
async def api_events(cid: str) -> StreamingResponse:
    row = _require_conv(cid)
    series_id = row["series_id"]

    async def event_gen() -> AsyncIterator[str]:
        from drama_series_agent.drama.event_bus import get_event_bus

        bus = get_event_bus()
        seen = 0
        # Poll up to ~60s then client should reconnect
        for _ in range(60):
            events = bus.history(series_id=series_id)
            if len(events) > seen:
                for e in events[seen:]:
                    payload = e.to_dict() if hasattr(e, "to_dict") else {"message": str(e)}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                seen = len(events)
            status = build_status_payload(_project(row))
            yield f"data: {json.dumps({'type': 'status', 'status': status}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


_HERMES_VIDEO_DEFAULTS = [
    "selfhost/video_minimax_h3_r2v_fast.json",
    "selfhost/video_minimax_h3_r2v.json",
    "selfhost/video_minimax_h3_i2v.json",
]

_ASPECT_TEMPLATE = {
    "9:16": "1080x1920/default.html",
    "16:9": "1920x1080/default.html",
    "1:1": "1080x1080/image_minimal_framed.html",
}


def _scan_workflow_keys(*, prefix: str) -> list[str]:
    """Return relative keys like selfhost/video_xxx.json under workflows/."""
    from drama_series_agent.agent.paths import default_workspace_root

    root = default_workspace_root()
    wf_root = root / "workflows"
    found: list[str] = []
    if wf_root.is_dir():
        for p in sorted(wf_root.rglob("*.json")):
            rel = p.relative_to(wf_root).as_posix()
            name = p.name.lower()
            if prefix == "video" and name.startswith("video_"):
                found.append(rel)
            elif prefix == "image" and name.startswith("image_"):
                found.append(rel)
    if prefix == "video":
        out: list[str] = []
        for k in _HERMES_VIDEO_DEFAULTS + found:
            if k not in out and (wf_root / k).is_file():
                out.append(k)
        return out or list(_HERMES_VIDEO_DEFAULTS)
    return found


def _workflow_from_comfy(comfy: dict[str, Any]) -> dict[str, Any]:
    image = comfy.get("image") or {}
    video = comfy.get("video") or {}
    tts = comfy.get("tts") or {}
    aspect = str(video.get("aspect") or "9:16")
    if aspect not in ("9:16", "16:9", "1:1"):
        aspect = "9:16"
    return {
        "comfyui_url": comfy.get("comfyui_url") or "http://127.0.0.1:8188",
        "comfyui_api_key": comfy.get("comfyui_api_key"),
        "runninghub_api_key": comfy.get("runninghub_api_key"),
        "runninghub_concurrent_limit": int(comfy.get("runninghub_concurrent_limit") or 1),
        "runninghub_instance_type": comfy.get("runninghub_instance_type"),
        "image_default_workflow": image.get("default_workflow"),
        "image_reference_workflow": image.get("reference_workflow"),
        "video_default_workflow": video.get("default_workflow"),
        "tts_default_workflow": tts.get("default_workflow"),
        "aspect": aspect,
    }


def _settings_payload() -> dict[str, Any]:
    from drama_series_agent.adapters.config import config_manager
    from drama_series_agent.llm_presets import LLM_PRESETS

    return {
        "llm": config_manager.get_llm_config(),
        "workflow": _workflow_from_comfy(config_manager.get_comfyui_config()),
        "presets": LLM_PRESETS,
        "configured": bool(config_manager.validate()),
        "video_workflow_options": _scan_workflow_keys(prefix="video"),
        "image_workflow_options": _scan_workflow_keys(prefix="image"),
        "aspect_options": ["9:16", "16:9", "1:1"],
    }


def _apply_series_media(
    *,
    conversation_id: str,
    video_workflow: Optional[str],
    aspect: Optional[str],
) -> None:
    row = get_conversation(conversation_id, drama_series_root=_drama_series_root())
    if not row:
        return
    from drama_series_agent.drama.runtime import load_runtime, save_runtime

    project = Path(row["project_dir"])
    rt = load_runtime(project)
    if video_workflow:
        rt.default_workflow = video_workflow
    if aspect:
        rt.aspect = aspect
    save_runtime(project, rt)


@router.get("/settings", response_model=HermesSettingsOut)
def api_get_settings() -> dict[str, Any]:
    return _settings_payload()


@router.put("/settings", response_model=HermesSettingsOut)
def api_put_settings(body: HermesSettingsUpdate) -> dict[str, Any]:
    from drama_series_agent.adapters.config import config_manager

    if body.llm is not None:
        llm = body.llm
        if not (llm.api_key and llm.base_url and llm.model):
            raise HTTPException(status_code=400, detail="模型配置需填写 api_key、base_url、model")
        config_manager.set_llm_config(llm.api_key, llm.base_url, llm.model)

    if body.workflow is not None:
        wf = body.workflow
        config_manager.set_comfyui_config(
            comfyui_url=wf.comfyui_url or None,
            comfyui_api_key=wf.comfyui_api_key,
            runninghub_api_key=wf.runninghub_api_key,
            runninghub_concurrent_limit=wf.runninghub_concurrent_limit,
            runninghub_instance_type=wf.runninghub_instance_type or "",
        )
        video_update: dict[str, Any] = {}
        if wf.video_default_workflow is not None:
            video_update["default_workflow"] = wf.video_default_workflow or None
        if wf.aspect:
            video_update["aspect"] = wf.aspect
        updates: dict[str, Any] = {"comfyui": {}}
        if wf.image_default_workflow is not None or wf.image_reference_workflow is not None:
            updates["comfyui"]["image"] = {}
            if wf.image_default_workflow is not None:
                updates["comfyui"]["image"]["default_workflow"] = wf.image_default_workflow or None
            if wf.image_reference_workflow is not None:
                updates["comfyui"]["image"]["reference_workflow"] = (
                    wf.image_reference_workflow or None
                )
        if video_update:
            updates["comfyui"]["video"] = video_update
        if wf.tts_default_workflow is not None:
            updates["comfyui"]["tts"] = {
                "default_workflow": wf.tts_default_workflow or None
            }
        if wf.aspect and wf.aspect in _ASPECT_TEMPLATE:
            updates["template"] = {"default_template": _ASPECT_TEMPLATE[wf.aspect]}
        if updates.get("comfyui") or updates.get("template"):
            config_manager.update(updates)

        if body.apply_to_conversation_id:
            _apply_series_media(
                conversation_id=body.apply_to_conversation_id,
                video_workflow=wf.video_default_workflow,
                aspect=wf.aspect,
            )

    config_manager.save()
    return _settings_payload()


@router.post("/settings/reset", response_model=HermesSettingsOut)
def api_reset_settings() -> dict[str, Any]:
    from drama_series_agent.adapters.config import config_manager
    from drama_series_agent.adapters.config.schema import HostAppVideoConfig

    config_manager.config = HostAppVideoConfig()
    config_manager.save()
    return _settings_payload()


@router.post("/settings/test_llm", response_model=LlmTestResponse)
def api_test_llm(body: LlmTestRequest) -> dict[str, Any]:
    from drama_series_agent.utils.llm_util import test_llm_connection

    if not (body.api_key and body.base_url):
        raise HTTPException(status_code=400, detail="请填写 api_key 与 base_url")
    ok, message, count = test_llm_connection(body.api_key, body.base_url)
    models: list[str] = []
    if ok:
        try:
            from drama_series_agent.utils.llm_util import fetch_available_models

            models = fetch_available_models(body.api_key, body.base_url)
        except Exception:  # noqa: BLE001
            models = []
        message = message or f"连接成功！可用 {count} 个模型"
    return {"ok": ok, "message": message, "models": models}


@router.post("/settings/load_models", response_model=LlmTestResponse)
def api_load_models(body: LlmTestRequest) -> dict[str, Any]:
    from drama_series_agent.utils.llm_util import fetch_available_models

    if not (body.api_key and body.base_url):
        raise HTTPException(status_code=400, detail="请填写 api_key 与 base_url")
    try:
        models = fetch_available_models(body.api_key, body.base_url)
        return {
            "ok": True,
            "message": f"已加载 {len(models)} 个模型",
            "models": models,
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"加载模型失败：{e}", "models": []}


@router.post("/settings/test_comfyui", response_model=LlmTestResponse)
def api_test_comfyui(body: dict[str, Any]) -> dict[str, Any]:
    import httpx

    url = (body.get("comfyui_url") or "").rstrip("/")
    if not url:
        raise HTTPException(status_code=400, detail="请填写 ComfyUI 地址")
    try:
        r = httpx.get(f"{url}/system_stats", timeout=5.0)
        if r.status_code == 200:
            return {"ok": True, "message": "ComfyUI 连接成功", "models": []}
        return {"ok": False, "message": f"连接失败：HTTP {r.status_code}", "models": []}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"连接失败：{e}", "models": []}
