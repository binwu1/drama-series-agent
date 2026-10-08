# -*- coding: utf-8 -*-
"""S1-B enrich: one-liner → literary draft + cast image drafts + Accept gates.

Workers are synchronous-by-default (or background thread) and emit JobEvents.
Real LLM/Flux hooks can replace the stub generators later; Accept rules stay.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from drama_series_agent.drama.comfy_worker import upsert_job_snapshot
from drama_series_agent.drama.decisions import append_decision, hash_paths
from drama_series_agent.drama.event_bus import InMemoryEventBus, get_event_bus
from drama_series_agent.drama.job_events import (
    JobEvent,
    JobEventType,
    JobKind,
    append_event_jsonl,
)
from drama_series_agent.drama.runtime import load_runtime, save_runtime
from drama_series_agent.intake.fs_util import file_sha256
from drama_series_agent.intake.manifest import (
    build_handoff,
    gap_report_text,
    load_manifest,
    write_handoff,
    write_manifest,
)
from drama_series_agent.intake.scaffold import load_project

# 1x1 PNG
_MIN_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mounts(project_dir: Path) -> dict[str, str]:
    return dict((load_project(project_dir).get("mounts") or {}))


def resolve_literary_premise(*, project_dir: Path, fallback: str = "") -> str:
    """Prefer creative-plan / literary_index / develop-brief for write-episode context."""
    project_dir = Path(project_dir)
    dramas = Path(_mounts(project_dir).get("dramas_dir") or "")
    chunks: list[str] = []
    for name in ("creative-plan.md", "develop-brief.md"):
        p = dramas / name
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8").strip()
            except Exception:  # noqa: BLE001
                continue
            if text:
                chunks.append(text[:1800])
                break
    idx = dramas / "literary_index.json"
    if idx.is_file():
        try:
            prev = json.loads(idx.read_text(encoding="utf-8"))
            prem = (prev.get("premise") or "").strip()
            if prem:
                chunks.append(prem[:800])
        except Exception:  # noqa: BLE001
            pass
    fb = (fallback or "").strip()
    if fb:
        chunks.append(fb[:500])
    joined = "\n\n".join(chunks).strip()
    return joined or "竖屏微短剧，按分集目录写可拍摄单集。"


def _to_ep_folder_id(raw: str) -> str:
    m = re.match(r"^(?:EP|ep)?(\d+)$", str(raw).strip(), re.I)
    if m:
        return f"EP{int(m.group(1)):03d}"
    s = str(raw).strip().upper()
    return s if s.startswith("EP") else s


def _chain_s2_after_literary(
    *,
    project_dir: Path,
    episode_ids: list[str],
    bus: InMemoryEventBus,
) -> dict[str, Any]:
    """Accept literary package then build → validate → Comfy for each episode."""
    from drama_series_agent.agent.chat_store import append_message
    from drama_series_agent.drama.build_worker import run_s2_build_and_comfy

    project_dir = Path(project_dir)
    try:
        accept_literary_package(project_dir=project_dir, decided_by="auto_chain_s2")
    except Exception as e:  # noqa: BLE001
        # Still try S2 — soft gate in build worker
        accept_err = str(e)
    else:
        accept_err = None

    results: list[dict[str, Any]] = []
    targets = [_to_ep_folder_id(e) for e in (episode_ids or ["EP001"])]
    # de-dup
    seen: set[str] = set()
    ordered: list[str] = []
    for ep in targets:
        if ep not in seen:
            seen.add(ep)
            ordered.append(ep)

    for ep in ordered:
        append_message(
            project_dir,
            role="assistant",
            content=(
                f"开始 S2 流水线（{ep}）：\n"
                "1. 构建分镜脚本 episode-run.jsonl …\n"
                "2. 校验资源完整性 …\n"
                "3. 后台入队 Comfy 渲染 …"
            ),
            tool_name="run_s2_build_and_comfy",
            ui_hints={"open_workbench": True, "open_progress": True},
        )
        try:
            out = run_s2_build_and_comfy(
                project_dir=project_dir,
                episode_id=ep,
                force_build=True,
                run_comfy_in_background=True,
                skip_comfy=False,
                bus=bus,
            )
            results.append({"episode_id": ep, **out})
            val = out.get("validation") or {}
            comfy = out.get("comfy") or {}
            if not out.get("ok"):
                errs = val.get("errors") or [out.get("error") or "unknown"]
                append_message(
                    project_dir,
                    role="assistant",
                    content=(
                        f"⚠️ {ep} 分镜已构建但未入队 Comfy："
                        f"{'; '.join(str(x) for x in errs[:5])}。"
                        "可补齐角色图/资源后说「出片」重试。"
                    ),
                    tool_name="run_s2_build_and_comfy",
                    ui_hints={"open_workbench": True, "open_progress": True},
                )
            else:
                append_message(
                    project_dir,
                    role="assistant",
                    content=(
                        f"✅ {ep} S2 完成：\n"
                        f"- 分镜 jsonl：已构建（{val.get('shot_count') or (out.get('build') or {}).get('shot_count') or '?'} 镜）\n"
                        f"- 校验：通过\n"
                        f"- Comfy：已入队 `{comfy.get('job_id') or '—'}`\n"
                        "请打开「生成进度」页查看渲染。"
                    ),
                    tool_name="run_s2_build_and_comfy",
                    ui_hints={"open_workbench": True, "open_progress": True},
                )
        except Exception as e:  # noqa: BLE001
            results.append({"episode_id": ep, "ok": False, "error": str(e)})
            append_message(
                project_dir,
                role="assistant",
                content=f"❌ {ep} S2 流水线失败：{e}",
                tool_name="run_s2_build_and_comfy",
                ui_hints={"open_workbench": True, "open_progress": True},
            )

    return {
        "ok": all(r.get("ok") for r in results) if results else False,
        "accept_error": accept_err,
        "episodes": results,
    }


def _jobs_log(project_dir: Path) -> Path:
    p = Path(project_dir) / "jobs" / "events.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _track_enrich_job(project_dir: Path, job_id: str, job_kind: str, status: str) -> None:
    rt = load_runtime(project_dir)
    rt.stage = "s1_enrich"
    found = False
    for row in rt.enrich_jobs:
        if row.get("job_id") == job_id:
            row["status"] = status
            found = True
            break
    if not found:
        rt.enrich_jobs.append(
            {
                "job_id": job_id,
                "job_kind": job_kind,
                "status": status,
                "created_at": _now(),
            }
        )
    if job_id not in rt.active_job_ids and status in ("queued", "running"):
        rt.active_job_ids.append(job_id)
    if status in ("done", "failed", "cancelled") and job_id in rt.active_job_ids:
        rt.active_job_ids = [j for j in rt.active_job_ids if j != job_id]
    save_runtime(project_dir, rt)


def _publish(
    bus: InMemoryEventBus,
    project_dir: Path,
    event: JobEvent,
) -> None:
    bus.publish(event)
    append_event_jsonl(_jobs_log(project_dir), event)


# ---------------------------------------------------------------------------
# Literary generate
# ---------------------------------------------------------------------------


def run_literary_generate(
    *,
    project_dir: Path,
    premise: str,
    episode_count: int = 1,
    genre: str = "短剧",
    episode_ids: Optional[list[str]] = None,
    revision_notes: Optional[str] = None,
    run_in_background: bool = False,
    use_skill: bool = False,
    force: bool = False,
    chain_s2: bool = False,
    bus: Optional[InMemoryEventBus] = None,
    generate_fn: Optional[Callable[..., dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Enqueue literary package generation.

    use_skill=False keeps the deterministic stub (tests).
    The Agent tool sets use_skill=True so drafts follow 0xsline-short-drama.
    Blocks when series bible incomplete unless force=True.
    chain_s2: after literary lands, auto Accept → build jsonl → validate → Comfy.
    """
    project_dir = Path(project_dir)
    from drama_series_agent.drama.series_bible import assert_bible_ready_for_episodes

    blocked = assert_bible_ready_for_episodes(project_dir=project_dir, force=force)
    if blocked:
        return blocked
    bus = bus or get_event_bus()
    rt = load_runtime(project_dir)
    job_id = f"job_lit_{rt.series_id}_{uuid.uuid4().hex[:6]}"
    kind = JobKind.LITERARY_GENERATE

    queued = JobEvent(
        event_type=JobEventType.JOB_QUEUED,
        job_id=job_id,
        job_kind=kind,
        series_id=rt.series_id,
        phase="queued",
        progress=0.0,
        message="Queued literary generate",
    )
    _publish(bus, project_dir, queued)
    _track_enrich_job(project_dir, job_id, kind.value, "queued")
    upsert_job_snapshot(
        job_id,
        series_id=rt.series_id,
        episode_id=None,
        status="queued",
        phase="queued",
        progress=0.0,
        job_kind=kind.value,
        error=None,
    )

    kwargs = dict(
        project_dir=project_dir,
        premise=premise,
        episode_count=max(1, int(episode_count)),
        genre=genre or "短剧",
        episode_ids=list(episode_ids) if episode_ids else None,
        revision_notes=(revision_notes or "").strip() or None,
        use_skill=bool(use_skill),
        chain_s2=bool(chain_s2),
        job_id=job_id,
        series_id=rt.series_id,
        bus=bus,
        generate_fn=generate_fn,
    )

    if run_in_background:
        threading.Thread(
            target=_literary_worker,
            kwargs=kwargs,
            name=f"lit-{job_id}",
            daemon=True,
        ).start()
        return {"ok": True, "job_id": job_id, "background": True, "chain_s2": bool(chain_s2)}

    result = _literary_worker(**kwargs)
    return {"ok": True, "job_id": job_id, "background": False, "chain_s2": bool(chain_s2), **result}


def _default_literary_package(
    *,
    project_dir: Path,
    premise: str,
    episode_count: int,
    genre: str,
    series_id: str,
    episode_ids: Optional[list[str]] = None,
    revision_notes: Optional[str] = None,
) -> dict[str, Any]:
    mounts = _mounts(project_dir)
    dramas = Path(mounts["dramas_dir"])
    episodes_dir = dramas / "episodes"
    episodes_dir.mkdir(parents=True, exist_ok=True)

    names = _hint_names_from_premise(premise) or ["主角A", "主角B"]
    index_path = dramas / "literary_index.json"
    if index_path.is_file():
        try:
            prev = json.loads(index_path.read_text(encoding="utf-8"))
            if prev.get("characters"):
                names = list(prev["characters"])
        except Exception:  # noqa: BLE001
            pass

    if episode_ids:
        targets: list[str] = []
        for raw in episode_ids:
            m = re.match(r"^(?:EP|ep)?(\d+)$", raw.strip(), re.I)
            targets.append(f"ep{int(m.group(1)):03d}" if m else raw.strip().lower())
    else:
        targets = [f"ep{i:03d}" for i in range(1, episode_count + 1)]

    rev_line = f"> revision: {revision_notes}\n" if revision_notes else ""
    paths: dict[str, str] = {}
    from drama_series_agent.drama.series_bible import episode_directory_brief

    for ep_id in targets:
        mnum = re.match(r"ep(\d+)$", ep_id, re.I)
        n = int(mnum.group(1)) if mnum else 1
        beat = episode_directory_brief(project_dir=project_dir, episode_n=n)
        beat_line = (
            f"> episode-directory: {beat.get('row') or '（目录无本集行）'}\n"
            if beat.get("row") or beat.get("error")
            else ""
        )
        body = (
            f"# {series_id} · 第{n}集（草稿）\n\n"
            f"> genre: {genre}\n"
            f"> premise: {premise.strip()}\n"
            f"{beat_line}"
            f"{rev_line}"
            f"> status: draft — awaiting Accept\n\n"
            f"## 出场\n"
            + "".join(f"- {nm}\n" for nm in names)
            + "\n## 场次\n\n"
            f"### 场1 · 开场\n\n"
            f"{names[0]}：（望向远方）……"
            f"{(beat.get('row') or premise.strip())[:40]}\n\n"
            f"{names[1] if len(names) > 1 else names[0]}：我们开始吧。\n"
        )
        if revision_notes:
            body += f"\n### 修订意图\n\n{revision_notes}\n"
        path = episodes_dir / f"{ep_id}.md"
        path.write_text(body, encoding="utf-8")
        paths[f"dramas/{series_id}/episodes/{ep_id}.md"] = str(path)

    existing_eps = sorted(p.stem for p in episodes_dir.glob("*.md"))
    index = {
        "series_id": series_id,
        "premise": premise.strip(),
        "genre": genre,
        "episode_count": max(episode_count, len(existing_eps)),
        "characters": names,
        "episodes": existing_eps,
        "status": "draft",
        "revision_notes": revision_notes,
        "updated_at": _now(),
    }
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    paths[f"dramas/{series_id}/literary_index.json"] = str(index_path)
    return {"paths": paths, "index": index, "characters": names}


def _hint_names_from_premise(premise: str) -> list[str]:
    names: list[str] = []
    for m in re.finditer(
        r"(?:主角|角色|名叫|叫做)[：:\s]*([\u4e00-\u9fff]{2,4})", premise
    ):
        names.append(m.group(1))
    # 「A和B」粗提
    for m in re.finditer(r"([\u4e00-\u9fff]{2,3})(?:和|与|、)([\u4e00-\u9fff]{2,3})", premise):
        names.extend([m.group(1), m.group(2)])
    # de-dup preserve order
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out[:8]


def _literary_worker(
    *,
    project_dir: Path,
    premise: str,
    episode_count: int,
    genre: str,
    job_id: str,
    series_id: str,
    bus: InMemoryEventBus,
    episode_ids: Optional[list[str]] = None,
    revision_notes: Optional[str] = None,
    use_skill: bool = False,
    chain_s2: bool = False,
    generate_fn: Optional[Callable[..., dict[str, Any]]] = None,
) -> dict[str, Any]:
    try:
        _track_enrich_job(project_dir, job_id, JobKind.LITERARY_GENERATE.value, "running")
        upsert_job_snapshot(
            job_id, status="running", phase="building", progress=0.1, job_kind="literary_generate"
        )
        _publish(
            bus,
            project_dir,
            JobEvent(
                event_type=JobEventType.ENRICH_STARTED,
                job_id=job_id,
                job_kind=JobKind.LITERARY_GENERATE,
                series_id=series_id,
                phase="building",
                progress=0.1,
                message="Literary generate started",
            ),
        )

        fn = generate_fn
        if fn is None and use_skill:
            from drama_series_agent.drama.literary_skill import write_with_skill

            fn = write_with_skill
        if fn is None:
            fn = _default_literary_package
        try:
            pkg = fn(
                project_dir=project_dir,
                premise=premise,
                episode_count=episode_count,
                genre=genre,
                series_id=series_id,
                episode_ids=episode_ids,
                revision_notes=revision_notes,
            )
        except Exception as skill_err:  # noqa: BLE001
            if not use_skill or generate_fn is not None:
                raise
            pkg = _default_literary_package(
                project_dir=project_dir,
                premise=premise,
                episode_count=episode_count,
                genre=genre,
                series_id=series_id,
                episode_ids=episode_ids,
                revision_notes=revision_notes,
            )
            pkg["writer"] = "stub_fallback"
            pkg["skill_error"] = str(skill_err)

        from drama_series_agent.drama.asset_studio import (
            invalidate_accept,
            propagate_literary_write,
        )

        invalidate_accept(
            project_dir=project_dir,
            scope="literary",
            reason="run_literary_generate",
        )

        # Sync screenplay.md + literary_dirty for every episode md just written
        # (skill path and stub both write dramas/episodes/*.md directly).
        synced: list[dict[str, Any]] = []
        for rel, abs_p in (pkg.get("paths") or {}).items():
            if not str(abs_p).endswith(".md"):
                continue
            if "literary_index" in str(rel).replace("\\", "/"):
                continue
            ep_path = Path(abs_p)
            if not ep_path.is_file():
                continue
            try:
                synced.append(
                    propagate_literary_write(
                        project_dir=project_dir,
                        episode_id=ep_path.stem,
                        content=ep_path.read_text(encoding="utf-8"),
                    )
                )
            except Exception:  # noqa: BLE001
                pass
        pkg["propagated"] = synced

        # Mark intake script as present (draft — Accept still required for s1_gate)
        m = load_manifest(project_dir)
        m.script.status = "present"
        m.script_kind = "outline"
        m.script.notes = "enrich_draft_awaiting_accept"
        m.script.files = [
            {
                "path": rel,
                "sha256": file_sha256(Path(abs_p)),
                "role": "literary_draft",
            }
            for rel, abs_p in (pkg.get("paths") or {}).items()
            if str(abs_p).endswith(".md")
        ]
        m.character_name_hints = list(
            dict.fromkeys(list(m.character_name_hints) + list(pkg.get("characters") or []))
        )
        write_manifest(project_dir, m)
        handoff = build_handoff(project_dir, m)
        write_handoff(project_dir, handoff)
        (project_dir / "gap_report.md").write_text(
            gap_report_text(m, handoff), encoding="utf-8"
        )

        _track_enrich_job(project_dir, job_id, JobKind.LITERARY_GENERATE.value, "done")
        upsert_job_snapshot(
            job_id,
            status="done",
            phase="done",
            progress=1.0,
            paths=pkg.get("paths") or {},
        )
        _publish(
            bus,
            project_dir,
            JobEvent(
                event_type=JobEventType.ENRICH_DONE,
                job_id=job_id,
                job_kind=JobKind.LITERARY_GENERATE,
                series_id=series_id,
                phase="done",
                progress=1.0,
                paths={k: str(v) for k, v in (pkg.get("paths") or {}).items()},
                message="Literary draft ready — Web Accept required",
            ),
        )
        _publish(
            bus,
            project_dir,
            JobEvent(
                event_type=JobEventType.MILESTONE,
                job_id=job_id,
                job_kind=JobKind.LITERARY_GENERATE,
                series_id=series_id,
                message="文学草稿已生成，请在 Asset 面板 Accept",
            ),
        )
        try:
            from drama_series_agent.agent.chat_store import append_message

            ep_list = episode_ids or list((pkg.get("index") or {}).get("episodes") or [])
            ep_label = "、".join(str(e) for e in ep_list[:6]) or "目标集"
            paths = pkg.get("paths") or {}
            path_lines = "\n".join(
                f"- `{rel}`" for rel in list(paths)[:8] if str(rel).endswith(".md")
            )
            writer = (pkg.get("index") or {}).get("writer") or pkg.get("writer") or ""
            note = ""
            if pkg.get("skill_error"):
                note = f"\n（技能写集异常已回退 stub：{pkg.get('skill_error')}）"
            if chain_s2:
                msg = (
                    f"✅ 文学草稿已落盘（{ep_label}）"
                    f"{' · ' + writer if writer else ''}。\n"
                    f"{path_lines}\n"
                    "接下来自动：\n"
                    "1. 构建分镜脚本（episode-run.jsonl）\n"
                    "2. 校验资源完整性\n"
                    "3. 后台入队 Comfy 渲染\n"
                    "进度见「生成进度」页。"
                    f"{note}"
                )
            else:
                msg = (
                    f"✅ 文学草稿已落盘（{ep_label}）"
                    f"{' · ' + writer if writer else ''}。\n"
                    f"{path_lines}\n"
                    f"请打开「文学产出」页查看；满意后再验收。"
                    f"{note}"
                )
            append_message(
                project_dir,
                role="assistant",
                content=msg,
                tool_name="run_literary_generate",
                ui_hints={
                    "open_workbench": True,
                    "open_literary": True,
                    "open_progress": bool(chain_s2),
                },
            )
        except Exception:  # noqa: BLE001
            pass

        if chain_s2:
            try:
                s2_out = _chain_s2_after_literary(
                    project_dir=project_dir,
                    episode_ids=episode_ids
                    or list((pkg.get("index") or {}).get("episodes") or []),
                    bus=bus,
                )
                pkg["s2_chain"] = s2_out
            except Exception as s2_err:  # noqa: BLE001
                pkg["s2_chain"] = {"ok": False, "error": str(s2_err)}
                try:
                    from drama_series_agent.agent.chat_store import append_message

                    append_message(
                        project_dir,
                        role="assistant",
                        content=(
                            f"文学已落盘，但自动 S2（分镜/校验/Comfy）失败：{s2_err}。"
                            "可在聊天说「出片第一集」重试 run_s2_build_and_comfy。"
                        ),
                        tool_name="run_s2_build_and_comfy",
                        ui_hints={"open_workbench": True, "open_progress": True},
                    )
                except Exception:  # noqa: BLE001
                    pass

        return {
            "paths": pkg.get("paths"),
            "index": pkg.get("index"),
            "characters": pkg.get("characters"),
            "s2_chain": pkg.get("s2_chain"),
        }
    except Exception as e:  # noqa: BLE001
        _track_enrich_job(project_dir, job_id, JobKind.LITERARY_GENERATE.value, "failed")
        upsert_job_snapshot(job_id, status="failed", phase="failed", error=str(e), progress=1.0)
        _publish(
            bus,
            project_dir,
            JobEvent(
                event_type=JobEventType.JOB_FAILED,
                job_id=job_id,
                job_kind=JobKind.LITERARY_GENERATE,
                series_id=series_id,
                phase="failed",
                error=str(e),
            ),
        )
        try:
            from drama_series_agent.agent.chat_store import append_message

            append_message(
                project_dir,
                role="assistant",
                content=f"文学生成失败：{e}。可稍后重试「重新生成第N集」。",
                tool_name="run_literary_generate",
            )
        except Exception:  # noqa: BLE001
            pass
        raise


def accept_literary_package(
    *,
    project_dir: Path,
    decided_by: str = "creator",
) -> dict[str, Any]:
    """Creator Accept on literary drafts → s1_gate.literary_accepted."""
    project_dir = Path(project_dir)
    mounts = _mounts(project_dir)
    dramas = Path(mounts["dramas_dir"])
    index_path = dramas / "literary_index.json"
    if not index_path.is_file():
        # Fall back: any episode md under dramas/episodes
        eps = sorted((dramas / "episodes").glob("*.md")) if (dramas / "episodes").is_dir() else []
        if not eps:
            raise FileNotFoundError("No literary package to accept")
        targets = {f"dramas/{project_dir.name}/episodes/{p.name}": p for p in eps}
    else:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        targets = {f"dramas/{project_dir.name}/literary_index.json": index_path}
        for ep in index.get("episodes") or []:
            p = dramas / "episodes" / f"{ep}.md"
            if p.is_file():
                targets[f"dramas/{project_dir.name}/episodes/{ep}.md"] = p
        index["status"] = "accepted"
        index["accepted_at"] = _now()
        index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    hashes = hash_paths(targets)
    rt = load_runtime(project_dir)
    decision = append_decision(
        project_dir,
        decision_kind="artifact_acceptance",
        status="accepted",
        series_id=rt.series_id,
        artifact="literary_package",
        target_hashes=hashes,
        decided_by=decided_by,
        decision_id=f"CD-LIT-{rt.series_id}-001",
    )
    rt.s1_gate["literary_accepted"] = True
    rt.refresh_s1_ready()
    save_runtime(project_dir, rt)

    m = load_manifest(project_dir)
    m.script.status = "present"
    m.script.notes = "accepted"
    write_manifest(project_dir, m)
    handoff = build_handoff(project_dir, m)
    write_handoff(project_dir, handoff)

    mem = project_dir / "memory" / "PROJECT.md"
    if mem.is_file():
        with mem.open("a", encoding="utf-8") as f:
            f.write(f"\n- [{_now()}] literary_package accepted ({decision['decision_id']})\n")

    return {
        "ok": True,
        "decision": decision,
        "s1_gate": rt.s1_gate,
        "ready_for_s2": rt.s1_gate.get("ready_for_s2"),
    }


# ---------------------------------------------------------------------------
# Cast table + images
# ---------------------------------------------------------------------------


def extract_cast_table(*, project_dir: Path) -> dict[str, Any]:
    """Build cast_table.json from accepted literary / name hints."""
    project_dir = Path(project_dir)
    mounts = _mounts(project_dir)
    dramas = Path(mounts["dramas_dir"])
    cast_dir = Path(mounts["cast_dir"])

    names: list[str] = []
    index_path = dramas / "literary_index.json"
    if index_path.is_file():
        idx = json.loads(index_path.read_text(encoding="utf-8"))
        names.extend(idx.get("characters") or [])
    m = load_manifest(project_dir)
    names.extend(m.character_name_hints or [])

    # Scan episode headers for 「## 出场」lists
    eps_dir = dramas / "episodes"
    if eps_dir.is_dir():
        for md in eps_dir.glob("*.md"):
            text = md.read_text(encoding="utf-8")
            in_cast = False
            for line in text.splitlines():
                if line.strip().startswith("## 出场"):
                    in_cast = True
                    continue
                if in_cast:
                    if line.startswith("##"):
                        break
                    mm = re.match(r"^[-*]\s*(.+)$", line.strip())
                    if mm:
                        names.append(mm.group(1).strip())

    seen: set[str] = set()
    characters: list[dict[str, Any]] = []
    for n in names:
        n = n.strip()
        if not n or n in seen:
            continue
        seen.add(n)
        characters.append(
            {
                "name": n,
                "role": "lead" if len(characters) < 4 else "supporting",
                "image_status": "missing",
                "accepted": False,
            }
        )

    table = {
        "series_id": project_dir.name,
        "characters": characters,
        "updated_at": _now(),
    }
    out = cast_dir / "cast_table.json"
    out.write_text(json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "cast_table_path": str(out), "characters": characters}


def run_cast_image_generate(
    *,
    project_dir: Path,
    characters: Optional[list[str]] = None,
    style: str = "cinematic portrait, front view",
    revision_notes: Optional[str] = None,
    run_in_background: bool = False,
    bus: Optional[InMemoryEventBus] = None,
    generate_fn: Optional[Callable[..., dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Generate draft cast PNGs (placeholder by default). Accept still required."""
    project_dir = Path(project_dir)
    bus = bus or get_event_bus()
    rt = load_runtime(project_dir)
    job_id = f"job_cast_{rt.series_id}_{uuid.uuid4().hex[:6]}"
    kind = JobKind.CAST_IMAGE_GENERATE

    if not characters:
        table_path = Path(_mounts(project_dir)["cast_dir"]) / "cast_table.json"
        if table_path.is_file():
            table = json.loads(table_path.read_text(encoding="utf-8"))
            characters = [c["name"] for c in table.get("characters") or [] if c.get("role") == "lead"]
            if not characters:
                characters = [c["name"] for c in table.get("characters") or []]
        else:
            characters = list(load_manifest(project_dir).character_name_hints or [])
    if not characters:
        raise ValueError("No characters to generate — run extract_cast_table first")

    if revision_notes:
        style = f"{style}; revision: {revision_notes.strip()}"

    queued = JobEvent(
        event_type=JobEventType.JOB_QUEUED,
        job_id=job_id,
        job_kind=kind,
        series_id=rt.series_id,
        phase="queued",
        progress=0.0,
        message=f"Queued cast images for {characters}",
    )
    _publish(bus, project_dir, queued)
    _track_enrich_job(project_dir, job_id, kind.value, "queued")
    upsert_job_snapshot(
        job_id,
        series_id=rt.series_id,
        status="queued",
        phase="queued",
        progress=0.0,
        job_kind=kind.value,
        characters=list(characters),
    )

    kwargs = dict(
        project_dir=project_dir,
        characters=list(characters),
        style=style,
        revision_notes=(revision_notes or "").strip() or None,
        job_id=job_id,
        series_id=rt.series_id,
        bus=bus,
        generate_fn=generate_fn,
    )
    if run_in_background:
        threading.Thread(
            target=_cast_image_worker,
            kwargs=kwargs,
            name=f"cast-{job_id}",
            daemon=True,
        ).start()
        return {"ok": True, "job_id": job_id, "background": True, "characters": characters}

    result = _cast_image_worker(**kwargs)
    return {"ok": True, "job_id": job_id, "background": False, **result}


def _default_cast_images(
    *,
    project_dir: Path,
    characters: list[str],
    style: str,
    series_id: str,
) -> dict[str, Any]:
    del style, series_id  # reserved for real image worker
    mounts = _mounts(project_dir)
    cast_dir = Path(mounts["cast_dir"])
    draft = cast_dir / "draft"
    draft.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for name in characters:
        dest = draft / f"{name}.png"
        dest.write_bytes(_MIN_PNG)
        paths[f"data/cast/{project_dir.name}/draft/{name}.png"] = str(dest)
    meta = {
        "characters": characters,
        "status": "draft",
        "updated_at": _now(),
        "note": "placeholder PNG — replace via real image worker; Accept still required",
    }
    meta_path = draft / "draft_manifest.json"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"paths": paths, "draft_dir": str(draft)}


def _cast_image_worker(
    *,
    project_dir: Path,
    characters: list[str],
    style: str,
    job_id: str,
    series_id: str,
    bus: InMemoryEventBus,
    revision_notes: Optional[str] = None,
    generate_fn: Optional[Callable[..., dict[str, Any]]] = None,
) -> dict[str, Any]:
    del revision_notes  # reserved for real image worker prompt
    try:
        _track_enrich_job(project_dir, job_id, JobKind.CAST_IMAGE_GENERATE.value, "running")
        upsert_job_snapshot(
            job_id, status="running", phase="sampling", progress=0.2, job_kind="cast_image_generate"
        )
        _publish(
            bus,
            project_dir,
            JobEvent(
                event_type=JobEventType.ENRICH_STARTED,
                job_id=job_id,
                job_kind=JobKind.CAST_IMAGE_GENERATE,
                series_id=series_id,
                phase="sampling",
                progress=0.2,
                message="Cast image generate started",
            ),
        )
        fn = generate_fn or _default_cast_images
        pkg = fn(
            project_dir=project_dir,
            characters=characters,
            style=style,
            series_id=series_id,
        )

        from drama_series_agent.drama.asset_studio import (
            invalidate_accept,
            mark_episodes_downstream_dirty,
        )

        invalidate_accept(
            project_dir=project_dir,
            scope="cast",
            reason="run_cast_image_generate",
        )
        mark_episodes_downstream_dirty(
            project_dir=project_dir,
            reason="cast",
            memory_note="cast image generate → needs_rebuild",
        )

        # Update cast_table draft status
        table_path = Path(_mounts(project_dir)["cast_dir"]) / "cast_table.json"
        if table_path.is_file():
            table = json.loads(table_path.read_text(encoding="utf-8"))
            for c in table.get("characters") or []:
                if c.get("name") in characters:
                    c["image_status"] = "draft"
                    c["accepted"] = False
            table["updated_at"] = _now()
            table_path.write_text(
                json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

        m = load_manifest(project_dir)
        if m.images.status == "missing":
            m.images.status = "partial"
            m.images.notes = "draft_awaiting_accept"
        write_manifest(project_dir, m)

        _track_enrich_job(project_dir, job_id, JobKind.CAST_IMAGE_GENERATE.value, "done")
        upsert_job_snapshot(
            job_id, status="done", phase="done", progress=1.0, paths=pkg.get("paths") or {}
        )
        _publish(
            bus,
            project_dir,
            JobEvent(
                event_type=JobEventType.ENRICH_DONE,
                job_id=job_id,
                job_kind=JobKind.CAST_IMAGE_GENERATE,
                series_id=series_id,
                phase="done",
                progress=1.0,
                paths={k: str(v) for k, v in (pkg.get("paths") or {}).items()},
                message="Cast drafts ready — Web Accept required",
            ),
        )
        _publish(
            bus,
            project_dir,
            JobEvent(
                event_type=JobEventType.MILESTONE,
                job_id=job_id,
                job_kind=JobKind.CAST_IMAGE_GENERATE,
                series_id=series_id,
                message="角色锚定图草稿已生成，请 Accept",
            ),
        )
        return pkg
    except Exception as e:  # noqa: BLE001
        _track_enrich_job(project_dir, job_id, JobKind.CAST_IMAGE_GENERATE.value, "failed")
        upsert_job_snapshot(job_id, status="failed", phase="failed", error=str(e), progress=1.0)
        _publish(
            bus,
            project_dir,
            JobEvent(
                event_type=JobEventType.JOB_FAILED,
                job_id=job_id,
                job_kind=JobKind.CAST_IMAGE_GENERATE,
                series_id=series_id,
                phase="failed",
                error=str(e),
            ),
        )
        raise


def accept_cast_images(
    *,
    project_dir: Path,
    characters: Optional[list[str]] = None,
    decided_by: str = "creator",
) -> dict[str, Any]:
    """Promote draft cast PNGs to named anchors + Accept (batch if characters=None)."""
    project_dir = Path(project_dir)
    mounts = _mounts(project_dir)
    cast_dir = Path(mounts["cast_dir"])
    draft = cast_dir / "draft"

    if characters is None:
        characters = [p.stem for p in draft.glob("*.png")] if draft.is_dir() else []
    if not characters:
        raise ValueError("No draft cast images to accept")

    rt = load_runtime(project_dir)
    decisions: list[dict[str, Any]] = []
    promoted: dict[str, str] = {}
    series_manifest: dict[str, Any] = {}
    sm_path = cast_dir / "series_manifest.json"
    if sm_path.is_file():
        series_manifest = json.loads(sm_path.read_text(encoding="utf-8"))

    for name in characters:
        src = draft / f"{name}.png"
        if not src.is_file():
            # already promoted?
            existing = cast_dir / f"{name}.png"
            if not existing.is_file():
                raise FileNotFoundError(f"Missing draft image for {name}")
            dest = existing
        else:
            dest = cast_dir / f"{name}.png"
            dest.write_bytes(src.read_bytes())
        rel = f"data/cast/{project_dir.name}/{name}.png"
        promoted[rel] = str(dest)
        series_manifest[name] = {
            "image": f"{name}.png",
            "accepted": True,
            "accepted_at": _now(),
        }
        decisions.append(
            append_decision(
                project_dir,
                decision_kind="cast_image_acceptance",
                status="accepted",
                series_id=rt.series_id,
                artifact="cast_image",
                character=name,
                target_hashes={rel: file_sha256(dest)},
                decided_by=decided_by,
                decision_id=f"CD-CAST-{name}-001",
            )
        )

    sm_path.write_text(
        json.dumps(series_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    table_path = cast_dir / "cast_table.json"
    if table_path.is_file():
        table = json.loads(table_path.read_text(encoding="utf-8"))
        for c in table.get("characters") or []:
            if c.get("name") in characters:
                c["image_status"] = "accepted"
                c["accepted"] = True
        table["updated_at"] = _now()
        table_path.write_text(
            json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    m = load_manifest(project_dir)
    m.images.status = "present"
    m.images.notes = "accepted_leads"
    m.images.files = [
        {"path": rel, "sha256": file_sha256(Path(p)), "character": Path(rel).stem}
        for rel, p in promoted.items()
    ]
    write_manifest(project_dir, m)
    handoff = build_handoff(project_dir, m)
    write_handoff(project_dir, handoff)
    (project_dir / "gap_report.md").write_text(
        gap_report_text(m, handoff), encoding="utf-8"
    )

    rt.s1_gate["cast_leads_accepted"] = True
    rt.refresh_s1_ready()
    save_runtime(project_dir, rt)

    from drama_series_agent.drama.asset_studio import mark_episodes_downstream_dirty

    dirty = mark_episodes_downstream_dirty(
        project_dir=project_dir,
        reason="cast",
        memory_note=(
            f"cast images accepted → needs_rebuild ({', '.join(characters)})"
        ),
    )

    mem = project_dir / "memory" / "PROJECT.md"
    if mem.is_file():
        with mem.open("a", encoding="utf-8") as f:
            f.write(
                f"\n- [{_now()}] cast images accepted: {', '.join(characters)}\n"
            )

    return {
        "ok": True,
        "characters": characters,
        "decisions": decisions,
        "promoted": promoted,
        "s1_gate": rt.s1_gate,
        "ready_for_s2": rt.s1_gate.get("ready_for_s2"),
        "downstream_dirty": dirty,
    }


def mark_audio_deferred(*, project_dir: Path) -> dict[str, Any]:
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    rt.s1_gate["audio_status"] = "deferred"
    rt.refresh_s1_ready()
    save_runtime(project_dir, rt)

    m = load_manifest(project_dir)
    m.audio.status = "deferred"
    m.audio.notes = "soft_voice_r2v_ok"
    write_manifest(project_dir, m)
    handoff = build_handoff(project_dir, m)
    write_handoff(project_dir, handoff)

    return {"ok": True, "s1_gate": rt.s1_gate, "audio_status": "deferred"}


def get_s1_gate_status(*, project_dir: Path) -> dict[str, Any]:
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    m = load_manifest(project_dir) if (project_dir / "intake_manifest.json").is_file() else None
    return {
        "ok": True,
        "series_id": rt.series_id,
        "stage": rt.stage,
        "s1_gate": rt.s1_gate,
        "enrich_jobs": rt.enrich_jobs,
        "case_code": m.case_code if m else None,
        "gaps": m.gaps if m else [],
    }
