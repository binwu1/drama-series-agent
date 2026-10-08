# -*- coding: utf-8 -*-
"""Series bible / develop package under dramas/{slug}/.

Before writing ep001, Agent must land outline + world + cast + art style files.
Aligns with 0xsline-short-drama develop flow (/start→/plan→/characters→/outline).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.intake.scaffold import load_project

BIBLE_DOCS: tuple[tuple[str, str], ...] = (
    ("creative-plan.md", "故事大纲 / 创作方案"),
    ("world.md", "世界观背景"),
    ("characters.md", "主要人物角色"),
    ("art-style.md", "画风 / 视觉方向"),
    ("episode-directory.md", "分集目录（可先粗纲）"),
)

_MIN_CHARS = 80  # below this counts as empty stub


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mounts(project_dir: Path) -> dict[str, str]:
    return dict((load_project(project_dir).get("mounts") or {}))


def dramas_dir(project_dir: Path) -> Path:
    d = Path(_mounts(project_dir)["dramas_dir"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "episodes").mkdir(parents=True, exist_ok=True)
    return d


def bible_paths(project_dir: Path) -> dict[str, Path]:
    root = dramas_dir(project_dir)
    return {name: root / name for name, _ in BIBLE_DOCS}


def _nonempty(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception:
        return False
    return len(text) >= _MIN_CHARS


def get_series_bible_status(*, project_dir: Path) -> dict[str, Any]:
    """Report which develop docs exist under dramas/{slug}/."""
    project_dir = Path(project_dir)
    root = dramas_dir(project_dir)
    docs: list[dict[str, Any]] = []
    missing: list[str] = []
    for name, label in BIBLE_DOCS:
        path = root / name
        ok = _nonempty(path)
        docs.append(
            {
                "file": name,
                "label": label,
                "path": str(path),
                "ready": ok,
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
        if not ok:
            missing.append(name)
    # five develop docs required before episode writing (directory drives each ep)
    core_missing = list(missing)
    state_path = root / ".drama-state.json"
    state: dict[str, Any] = {}
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    return {
        "ok": True,
        "dramas_dir": str(root),
        "docs": docs,
        "missing": missing,
        "core_missing": core_missing,
        "bible_ready": not core_missing,
        "current_step": state.get("currentStep") or ("plan" if core_missing else "episode"),
        "state_path": str(state_path),
    }


def _heading_lines(text: str) -> list[str]:
    return [
        ln.strip()
        for ln in text.splitlines()
        if ln.startswith("#") and not ln.startswith("####")
    ]


def _ep_cells(text: str) -> list[str]:
    found = re.findall(r"\|\s*(EP\d{3})\s*\|", text, flags=re.I)
    return [x.upper() for x in found]


def validate_bible_structure(
    file_name: str,
    previous: str,
    new: str,
) -> Optional[str]:
    """Ensure edits keep markdown skeleton (headings / EP table cells)."""
    prev = (previous or "").strip()
    cur = (new or "").strip()
    if not prev:
        return None
    prev_h = _heading_lines(prev)
    cur_h = set(_heading_lines(cur))
    missing_h = [h for h in prev_h if h not in cur_h]
    if missing_h:
        sample = "、".join(missing_h[:5])
        more = f" 等{len(missing_h)}个" if len(missing_h) > 5 else ""
        return f"请保留原有标题结构，勿删改标题行：{sample}{more}"
    if file_name == "episode-directory.md":
        prev_eps = _ep_cells(prev)
        cur_eps = set(_ep_cells(cur))
        missing_eps = [e for e in prev_eps if e not in cur_eps]
        if missing_eps:
            sample = "、".join(missing_eps[:8])
            more = f" 等{len(missing_eps)}集" if len(missing_eps) > 8 else ""
            return f"分集目录须保留原有集号单元格（| EPxxx |）：缺失 {sample}{more}"
        prev_tables = sum(1 for ln in prev.splitlines() if ln.strip().startswith("|"))
        cur_tables = sum(1 for ln in cur.splitlines() if ln.strip().startswith("|"))
        if prev_tables >= 3 and cur_tables < max(3, prev_tables // 2):
            return "请保留分集目录的 Markdown 表格格式（| 列 |）"
    return None


def get_series_bible_doc(
    *,
    project_dir: Path,
    file_name: str,
) -> dict[str, Any]:
    """Read one bible markdown file (empty content if missing)."""
    allowed = {n: label for n, label in BIBLE_DOCS}
    if file_name not in allowed:
        return {
            "ok": False,
            "error": f"file_name must be one of {sorted(allowed)}",
        }
    path = dramas_dir(project_dir) / file_name
    content = ""
    if path.is_file():
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e), "file": file_name}
    return {
        "ok": True,
        "file": file_name,
        "label": allowed[file_name],
        "path": str(path),
        "content": content,
        "ready": _nonempty(path),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "mtime": path.stat().st_mtime if path.is_file() else None,
    }


def save_series_bible_doc(
    *,
    project_dir: Path,
    file_name: str,
    content: str,
    preserve_format: bool = False,
) -> dict[str, Any]:
    """Write one bible markdown file."""
    allowed = {n for n, _ in BIBLE_DOCS}
    if file_name not in allowed:
        return {
            "ok": False,
            "error": f"file_name must be one of {sorted(allowed)}",
        }
    text = (content or "").strip()
    if len(text) < _MIN_CHARS:
        return {
            "ok": False,
            "error": f"content too short (<{_MIN_CHARS} chars); refuse empty stub",
        }
    root = dramas_dir(project_dir)
    path = root / file_name
    previous = ""
    if path.is_file():
        try:
            previous = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            previous = ""
    if preserve_format:
        fmt_err = validate_bible_structure(file_name, previous, text)
        if fmt_err:
            return {"ok": False, "error": fmt_err, "file": file_name}
    path.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
    _touch_state(root, step=_step_for_file(file_name))

    dirty = None
    changed = (previous or "").strip() != text
    # Bible / directory changes must invalidate stale S2 for existing episodes
    if changed and file_name in {
        "episode-directory.md",
        "creative-plan.md",
        "characters.md",
        "world.md",
        "art-style.md",
    }:
        from drama_series_agent.drama.asset_studio import mark_episodes_downstream_dirty

        dirty = mark_episodes_downstream_dirty(
            project_dir=project_dir,
            reason="bible",
            memory_note=(
                f"bible updated ({file_name}) → episodes needs_rebuild; "
                "rewrite literary or run S2 with force"
            ),
        )

    return {
        "ok": True,
        "path": str(path),
        "file": file_name,
        "status": get_series_bible_status(project_dir=project_dir),
        "downstream_dirty": dirty,
        "hint": (
            "设定已更新并标记下游需重建；若分集目录/角色有实质变化，"
            "建议重新生成对应集文学后再出片。"
            if dirty
            else None
        ),
    }


def save_series_bible_package(
    *,
    project_dir: Path,
    docs: dict[str, str],
) -> dict[str, Any]:
    """Write multiple bible docs in one call. keys = file names."""
    written: list[str] = []
    errors: list[str] = []
    for name, body in (docs or {}).items():
        out = save_series_bible_doc(
            project_dir=project_dir, file_name=name, content=body
        )
        if out.get("ok"):
            written.append(name)
        else:
            errors.append(f"{name}: {out.get('error')}")
    status = get_series_bible_status(project_dir=project_dir)
    return {
        "ok": not errors and bool(written),
        "written": written,
        "errors": errors,
        "status": status,
    }


def _step_for_file(file_name: str) -> str:
    return {
        "creative-plan.md": "plan",
        "world.md": "plan",
        "characters.md": "characters",
        "art-style.md": "plan",
        "episode-directory.md": "outline",
    }.get(file_name, "plan")


def _touch_state(root: Path, *, step: str) -> None:
    path = root / ".drama-state.json"
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["currentStep"] = step
    data["updated_at"] = _now()
    if "language" not in data:
        data["language"] = "zh-CN"
    if "mode" not in data:
        data["mode"] = "domestic"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _chat_develop(system: str, user: str) -> str:
    from drama_series_agent.utils.llm_client import (
        create_sync_client,
        ensure_choices,
        load_llm_settings,
        message_text,
        prepare_request_kwargs,
    )

    cfg = load_llm_settings()
    # Develop packs are long; give vendors more room than default chat.
    client = create_sync_client(
        api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=240.0
    )
    kwargs = prepare_request_kwargs(
        base_url=cfg["base_url"],
        model=cfg["model"],
        kwargs={
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
            "max_tokens": 4500,
        },
    )
    resp = client.chat.completions.create(**kwargs)
    return message_text(ensure_choices(resp, model=cfg["model"]).message)


def _split_bible_blob(text: str) -> dict[str, str]:
    """Parse LLM output marked with ## FILE: name.md sections."""
    text = text.strip()
    parts = re.split(r"(?m)^##\s*FILE:\s*([^\n]+)\s*$", text)
    out: dict[str, str] = {}
    if len(parts) < 3:
        if text:
            out["creative-plan.md"] = text
        return out
    i = 1
    while i + 1 < len(parts):
        name = parts[i].strip().strip("`").strip()
        body = parts[i + 1].strip()
        if name in {n for n, _ in BIBLE_DOCS} and body:
            out[name] = body
        i += 2
    return out


def _develop_worker(
    *,
    project_dir: Path,
    brief: str,
    title: str,
    series_id: str,
    genre: Optional[str],
    art_direction_hint: Optional[str],
    job_id: str,
    bus: Any,
) -> dict[str, Any]:
    from drama_series_agent.agent.chat_store import append_message
    from drama_series_agent.drama.comfy_worker import upsert_job_snapshot
    from drama_series_agent.drama.develop_skill import develop_skill_prompt_pack
    from drama_series_agent.drama.enrich import _publish, _track_enrich_job
    from drama_series_agent.drama.event_bus import get_event_bus
    from drama_series_agent.drama.job_events import JobEvent, JobEventType, JobKind

    bus = bus or get_event_bus()
    kind = JobKind.SERIES_DEVELOP
    try:
        _track_enrich_job(project_dir, job_id, kind.value, "running")
        upsert_job_snapshot(
            job_id,
            series_id=series_id,
            episode_id=None,
            status="running",
            phase="building",
            progress=0.1,
            job_kind=kind.value,
            error=None,
        )
        _publish(
            bus,
            project_dir,
            JobEvent(
                event_type=JobEventType.ENRICH_STARTED,
                job_id=job_id,
                job_kind=kind,
                series_id=series_id,
                phase="building",
                progress=0.1,
                message="Series develop started",
            ),
        )

        system = develop_skill_prompt_pack()
        user = (
            f"剧名：{title}\n"
            f"系列 id：{series_id}\n"
            f"题材提示：{genre or '（未指定）'}\n"
            f"画风提示：{art_direction_hint or '（未指定，请自拟统一视觉方向）'}\n"
            f"开发需求：\n{brief}\n"
            f"请按 ## FILE: 分段输出五份开发文件，内容填满实质设定，不要输出剧本场次。\n"
        )
        raw = _chat_develop(system, user)
        docs = _split_bible_blob(raw)
        if len(docs) < 3:
            raise RuntimeError(
                "model did not return enough FILE sections: " + (raw[:300] or "(empty)")
            )
        saved = save_series_bible_package(project_dir=project_dir, docs=docs)
        if not saved.get("ok"):
            raise RuntimeError(
                "save failed: " + "; ".join(saved.get("errors") or ["unknown"])
            )

        root = dramas_dir(project_dir)
        _touch_state(root, step="outline")
        note = root / "develop-brief.md"
        note.write_text(
            f"# 开发简报\n\n- title: {title}\n- updated: {_now()}\n\n{brief}\n",
            encoding="utf-8",
        )
        paths = {k: str(v) for k, v in bible_paths(project_dir).items()}
        written = saved.get("written") or []
        msg = (
            "系列开发文件已生成，请确认后再写第一集：\n"
            + "\n".join(f"- {n}: `{paths.get(n, '')}`" for n in written)
        )
        append_message(
            project_dir,
            role="assistant",
            content=msg,
            tool_name="run_series_develop",
            ui_hints={"open_workbench": True, "series_bible_ready": True},
        )
        _track_enrich_job(project_dir, job_id, kind.value, "done")
        upsert_job_snapshot(
            job_id,
            series_id=series_id,
            episode_id=None,
            status="done",
            phase="done",
            progress=1.0,
            job_kind=kind.value,
            error=None,
        )
        _publish(
            bus,
            project_dir,
            JobEvent(
                event_type=JobEventType.ENRICH_DONE,
                job_id=job_id,
                job_kind=kind,
                series_id=series_id,
                phase="done",
                progress=1.0,
                message="Series develop done",
            ),
        )
        return {
            "ok": True,
            "written": written,
            "paths": paths,
            "status": saved.get("status"),
            "message": msg,
        }
    except Exception as e:  # noqa: BLE001
        err = str(e)
        _track_enrich_job(project_dir, job_id, kind.value, "failed")
        upsert_job_snapshot(
            job_id,
            series_id=series_id,
            episode_id=None,
            status="failed",
            phase="failed",
            progress=0.0,
            job_kind=kind.value,
            error=err,
        )
        _publish(
            bus,
            project_dir,
            JobEvent(
                event_type=JobEventType.JOB_FAILED,
                job_id=job_id,
                job_kind=kind,
                series_id=series_id,
                phase="failed",
                progress=0.0,
                message=err,
            ),
        )
        append_message(
            project_dir,
            role="assistant",
            content=f"系列开发失败：{err}。可稍后重试 run_series_develop。",
            tool_name="run_series_develop",
        )
        return {"ok": False, "error": err}


def run_series_develop(
    *,
    project_dir: Path,
    brief: str,
    title: Optional[str] = None,
    genre: Optional[str] = None,
    art_direction_hint: Optional[str] = None,
    run_in_background: bool = True,
) -> dict[str, Any]:
    """LLM-generate series bible files (NOT episode 1). Default: background job."""
    import threading
    import uuid

    from drama_series_agent.drama.comfy_worker import upsert_job_snapshot
    from drama_series_agent.drama.enrich import _publish, _track_enrich_job
    from drama_series_agent.drama.event_bus import get_event_bus
    from drama_series_agent.drama.job_events import JobEvent, JobEventType, JobKind
    from drama_series_agent.drama.runtime import load_runtime

    project_dir = Path(project_dir)
    brief = (brief or "").strip()
    if len(brief) < 8:
        return {"ok": False, "error": "brief too short"}

    proj = load_project(project_dir)
    series_id = proj.get("series_id") or proj.get("slug") or project_dir.name
    title = (title or proj.get("title") or series_id).strip()
    bus = get_event_bus()
    rt = load_runtime(project_dir)
    job_id = f"job_dev_{rt.series_id}_{uuid.uuid4().hex[:6]}"
    kind = JobKind.SERIES_DEVELOP

    _publish(
        bus,
        project_dir,
        JobEvent(
            event_type=JobEventType.JOB_QUEUED,
            job_id=job_id,
            job_kind=kind,
            series_id=series_id,
            phase="queued",
            progress=0.0,
            message="Queued series develop",
        ),
    )
    _track_enrich_job(project_dir, job_id, kind.value, "queued")
    upsert_job_snapshot(
        job_id,
        series_id=series_id,
        episode_id=None,
        status="queued",
        phase="queued",
        progress=0.0,
        job_kind=kind.value,
        error=None,
    )

    kwargs = dict(
        project_dir=project_dir,
        brief=brief,
        title=title,
        series_id=series_id,
        genre=genre,
        art_direction_hint=art_direction_hint,
        job_id=job_id,
        bus=bus,
    )
    if run_in_background:
        threading.Thread(
            target=_develop_worker,
            kwargs=kwargs,
            name=f"dev-{job_id}",
            daemon=False,
        ).start()
        return {
            "ok": True,
            "job_id": job_id,
            "background": True,
            "message": (
                "系列开发已在后台启动。"
                "请稍后刷新消息或打开工作台查看进度；完成后会写入 dramas/{slug}/ 开发文件。"
            ),
            "expected_files": [n for n, _ in BIBLE_DOCS],
            "dramas_dir": str(dramas_dir(project_dir)),
        }

    result = _develop_worker(**kwargs)
    return {"ok": bool(result.get("ok")), "job_id": job_id, "background": False, **result}


def _table_row_for_ep(text: str, n: int) -> Optional[str]:
    """Return episode beat row; ignore mapping cells like EP001–EP008."""
    n = int(n)
    cell = re.compile(
        rf"\|\s*(?:EP{n:03d}|ep{n:03d}|第{n}集)\s*\|",
        re.I,
    )
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        if cell.search(s):
            return s
    return None


def _phase_header_near_ep(text: str, n: int) -> str:
    """Nearest ## phase heading above the EPnnn beat row."""
    lines = text.splitlines()
    cell = re.compile(rf"\|\s*(?:EP{int(n):03d}|ep{int(n):03d})\s*\|", re.I)
    last_h = ""
    for line in lines:
        if line.startswith("## "):
            last_h = line.strip()
        if line.strip().startswith("|") and cell.search(line):
            return last_h
    return last_h


def episode_directory_brief(*, project_dir: Path, episode_n: int) -> dict[str, Any]:
    """Pull this-ep beat (+ neighbors) from dramas/{slug}/episode-directory.md."""
    project_dir = Path(project_dir)
    path = dramas_dir(project_dir) / "episode-directory.md"
    out: dict[str, Any] = {
        "path": str(path),
        "episode": f"EP{int(episode_n):03d}",
        "found": False,
        "phase": "",
        "row": "",
        "prev_row": "",
        "next_row": "",
        "excerpt": "",
    }
    if not path.is_file():
        out["error"] = "missing episode-directory.md"
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
        return out
    n = int(episode_n)
    row = _table_row_for_ep(text, n)
    out["phase"] = _phase_header_near_ep(text, n)
    out["row"] = row or ""
    out["prev_row"] = _table_row_for_ep(text, n - 1) or ""
    out["next_row"] = _table_row_for_ep(text, n + 1) or ""
    out["found"] = bool(row)
    parts = [
        f"【分集目录依据】来源：{path.name} · 目标 {out['episode']}",
        "必须落实本集「进入压力 / 追求与阻力 / 出去时留下的新问题」；"
        "不得另起与目录冲突的主线。",
    ]
    if out["phase"]:
        parts.append(f"阶段：{out['phase']}")
    if out["prev_row"]:
        parts.append(f"上一集：{out['prev_row']}")
    if row:
        parts.append(f"本集：{row}")
    else:
        parts.append(
            f"警告：目录中未找到 {out['episode']} 行，仍须整体遵守 episode-directory.md。"
        )
    if out["next_row"]:
        parts.append(f"下一集（本集钩子须指向）：{out['next_row']}")
    out["excerpt"] = "\n".join(parts)
    return out


def bible_context_for_episode(*, project_dir: Path, episode_n: int, limit: int = 1200) -> str:
    """Compact bible + episode-directory brief for literary prompts."""
    root = dramas_dir(project_dir)
    chunks: list[str] = []
    brief = episode_directory_brief(project_dir=project_dir, episode_n=episode_n)
    if brief.get("excerpt"):
        chunks.append(brief["excerpt"])
    for name in ("creative-plan.md", "characters.md", "world.md"):
        p = root / name
        if not p.is_file():
            continue
        try:
            raw = p.read_text(encoding="utf-8").strip()
        except Exception:  # noqa: BLE001
            continue
        if len(raw) > limit:
            raw = raw[:limit] + "\n…（节选）"
        chunks.append(f"## 系列文件 {name}\n{raw}")
    return "\n\n".join(chunks).strip()


def assert_bible_ready_for_episodes(
    *,
    project_dir: Path,
    force: bool = False,
) -> Optional[dict[str, Any]]:
    """Return an error dict if literary generate should be blocked."""
    if force:
        return None
    st = get_series_bible_status(project_dir=project_dir)
    if st.get("bible_ready"):
        return None
    missing = st.get("core_missing") or []
    return {
        "ok": False,
        "error": "series_bible_incomplete",
        "message": (
            "系列圣经未齐，禁止直接写集。请先调用 run_series_develop 或 "
            "save_series_bible_doc 写齐：creative-plan.md / world.md / "
            "characters.md / art-style.md / episode-directory.md。"
            f" 缺失：{missing}"
        ),
        "status": st,
        "hint": (
            "用户若只要大纲/世界观/角色/画风/分集目录，用 run_series_develop；"
            "写某一集时必须依据 dramas/{slug}/episode-directory.md 对应行。"
        ),
    }
