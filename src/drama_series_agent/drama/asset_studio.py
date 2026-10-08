# -*- coding: utf-8 -*-
"""S1 Asset Studio — list/edit literary, upload cast, invalidate Accept on change.

Mode C: embedded editor (default) + external file open / reload.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.drama.decisions import append_decision
from drama_series_agent.drama.runtime import load_runtime, save_runtime
from drama_series_agent.intake.fs_util import file_sha256
from drama_series_agent.intake.scaffold import load_project

_IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mounts(project_dir: Path) -> dict[str, str]:
    return dict((load_project(project_dir).get("mounts") or {}))


def _normalize_ep_id(episode_id: str) -> str:
    t = episode_id.strip()
    m = re.match(r"^(?:EP|ep)?(\d+)$", t, re.I)
    if m:
        return f"ep{int(m.group(1)):03d}"
    if t.lower().endswith(".md"):
        return Path(t).stem.lower()
    return t.lower()


def _episode_path(project_dir: Path, episode_id: str) -> Path:
    dramas = Path(_mounts(project_dir)["dramas_dir"])
    eid = _normalize_ep_id(episode_id)
    return dramas / "episodes" / f"{eid}.md"


def _accepted_hashes(project_dir: Path, *, kind: str) -> dict[str, str]:
    """Latest accepted target_hashes for literary_package or cast_image."""
    path = Path(project_dir) / "decisions" / "accept.jsonl"
    if not path.is_file():
        return {}
    latest: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("status") != "accepted":
            continue
        if kind == "literary" and row.get("artifact") == "literary_package":
            latest = dict(row.get("target_hashes") or {})
        if kind == "cast" and row.get("decision_kind") == "cast_image_acceptance":
            latest.update(row.get("target_hashes") or {})
    return latest


# ---------------------------------------------------------------------------
# Accept invalidation
# ---------------------------------------------------------------------------


def invalidate_accept(
    *,
    project_dir: Path,
    scope: str,
    reason: str,
    character: Optional[str] = None,
) -> dict[str, Any]:
    """scope: literary | cast | all — clear s1_gate flags + append superseded."""
    project_dir = Path(project_dir)
    rt = load_runtime(project_dir)
    series_id = rt.series_id
    cleared: list[str] = []

    if scope in ("literary", "all") and rt.s1_gate.get("literary_accepted"):
        append_decision(
            project_dir,
            decision_kind="artifact_acceptance",
            status="superseded",
            series_id=series_id,
            artifact="literary_package",
            decided_by="system",
            decision_id=f"CD-LIT-INV-{uuid_short()}",
        )
        rt.s1_gate["literary_accepted"] = False
        cleared.append("literary")

    if scope in ("cast", "all") and rt.s1_gate.get("cast_leads_accepted"):
        append_decision(
            project_dir,
            decision_kind="cast_image_acceptance",
            status="superseded",
            series_id=series_id,
            artifact="cast_image",
            character=character,
            decided_by="system",
            decision_id=f"CD-CAST-INV-{uuid_short()}",
        )
        rt.s1_gate["cast_leads_accepted"] = False
        cleared.append("cast")

    rt.s1_gate["ready_for_s2"] = False
    if rt.stage == "s2_ready":
        rt.stage = "s1_enrich"
    save_runtime(project_dir, rt)

    mem = project_dir / "memory" / "PROJECT.md"
    if mem.is_file() and cleared:
        with mem.open("a", encoding="utf-8") as f:
            f.write(f"\n- [{_now()}] accept invalidated ({scope}): {reason}\n")

    return {
        "ok": True,
        "cleared": cleared,
        "reason": reason,
        "s1_gate": rt.s1_gate,
    }


def uuid_short() -> str:
    import uuid

    return uuid.uuid4().hex[:8].upper()


# ---------------------------------------------------------------------------
# Literary
# ---------------------------------------------------------------------------


def list_literary_episodes(*, project_dir: Path) -> dict[str, Any]:
    project_dir = Path(project_dir)
    dramas = Path(_mounts(project_dir)["dramas_dir"])
    eps_dir = dramas / "episodes"
    accepted = _accepted_hashes(project_dir, kind="literary")
    rt = load_runtime(project_dir)
    lit_ok = bool(rt.s1_gate.get("literary_accepted"))

    episodes: list[dict[str, Any]] = []
    if eps_dir.is_dir():
        for p in sorted(eps_dir.glob("*.md")):
            rel = f"dramas/{project_dir.name}/episodes/{p.name}"
            sha = file_sha256(p)
            status = "draft"
            if lit_ok and accepted.get(rel) == sha:
                status = "accepted"
            elif lit_ok and accepted and accepted.get(rel) and accepted.get(rel) != sha:
                status = "dirty"
            elif lit_ok:
                # package accepted but this file not in hash set / changed
                status = "dirty" if accepted else "accepted"
            episodes.append(
                {
                    "episode_id": p.stem,
                    "path": str(p),
                    "rel": rel,
                    "bytes": p.stat().st_size,
                    "sha256": sha,
                    "status": status,
                    "mtime": datetime.fromtimestamp(
                        p.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "has_user_first_frame": get_episode_first_frame_path(
                        project_dir=project_dir, episode_id=p.stem
                    )
                    is not None,
                }
            )

    index_path = dramas / "literary_index.json"
    index = None
    if index_path.is_file():
        index = json.loads(index_path.read_text(encoding="utf-8"))

    return {
        "ok": True,
        "episodes": episodes,
        "literary_accepted": lit_ok,
        "index": index,
        "episodes_dir": str(eps_dir),
    }


def get_literary_episode(*, project_dir: Path, episode_id: str) -> dict[str, Any]:
    project_dir = Path(project_dir)
    path = _episode_path(project_dir, episode_id)
    if not path.is_file():
        raise FileNotFoundError(f"Episode not found: {path}")
    listed = list_literary_episodes(project_dir=project_dir)
    meta = next(
        (e for e in listed["episodes"] if e["episode_id"] == path.stem),
        None,
    )
    return {
        "ok": True,
        "episode_id": path.stem,
        "path": str(path),
        "content": path.read_text(encoding="utf-8"),
        "meta": meta,
    }


def save_literary_episode(
    *,
    project_dir: Path,
    episode_id: str,
    content: str,
    invalidate: bool = True,
) -> dict[str, Any]:
    project_dir = Path(project_dir)
    path = _episode_path(project_dir, episode_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    old_sha = file_sha256(path) if path.is_file() else None
    path.write_text(content, encoding="utf-8")
    new_sha = file_sha256(path)

    inv = None
    if invalidate and old_sha != new_sha:
        inv = invalidate_accept(
            project_dir=project_dir,
            scope="literary",
            reason=f"save_literary_episode:{path.stem}",
        )

    # Keep index episode list in sync
    dramas = Path(_mounts(project_dir)["dramas_dir"])
    index_path = dramas / "literary_index.json"
    if index_path.is_file():
        idx = json.loads(index_path.read_text(encoding="utf-8"))
        eps = list(idx.get("episodes") or [])
        if path.stem not in eps:
            eps.append(path.stem)
            idx["episodes"] = eps
        idx["status"] = "draft"
        idx["updated_at"] = _now()
        index_path.write_text(
            json.dumps(idx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # Mirror to templates/.../剧集/EPxxx/screenplay.md (H3 / open-folder path)
    # and mark episode-run dirty so next build does not skip stale jsonl.
    propagated = None
    if old_sha != new_sha:
        propagated = propagate_literary_write(
            project_dir=project_dir,
            episode_id=path.stem,
            content=content,
        )
    else:
        # Content unchanged — still refresh mirror if missing
        propagated = {
            "screenplay_mirror": _sync_screenplay_mirror(
                project_dir=project_dir, episode_id=path.stem, content=content
            ),
            "episode_run_dirty": None,
        }

    return {
        "ok": True,
        "episode_id": path.stem,
        "path": str(path),
        "sha256": new_sha,
        "invalidated": inv,
        "screenplay_mirror": (propagated or {}).get("screenplay_mirror"),
        "episode_run_dirty": (propagated or {}).get("episode_run_dirty"),
    }


def _ep_folder_id(episode_id: str) -> str:
    """ep001 / EP001 / 1 → EP001 (templates 剧集 folder name)."""
    m = re.match(r"^(?:EP|ep)?(\d+)$", episode_id.strip(), re.I)
    if m:
        return f"EP{int(m.group(1)):03d}"
    return episode_id.strip().upper() if episode_id.strip().upper().startswith("EP") else episode_id


def episode_open_dir(*, project_dir: Path) -> Path:
    """templates/{slug}/assets/episode_open/ — per-episode user first frames."""
    from drama_series_agent.drama.comfy_worker import resolve_templates_dir

    d = resolve_templates_dir(Path(project_dir)) / "assets" / "episode_open"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_episode_first_frame_path(
    *, project_dir: Path, episode_id: str
) -> Optional[Path]:
    """Return user-uploaded first-frame image if present."""
    ep = _ep_folder_id(episode_id)
    root = episode_open_dir(project_dir=project_dir)
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        p = root / f"{ep}{ext}"
        if p.is_file():
            return p
    return None


def episode_first_frame_relpath(*, episode_id: str, path: Path) -> str:
    """Path relative to templates root for episode-run.jsonl first_frame."""
    ep = _ep_folder_id(episode_id)
    return f"assets/episode_open/{ep}{path.suffix.lower()}"


def get_episode_first_frame_meta(
    *, project_dir: Path, episode_id: str
) -> dict[str, Any]:
    ep = _ep_folder_id(episode_id)
    path = get_episode_first_frame_path(project_dir=project_dir, episode_id=ep)
    return {
        "ok": True,
        "episode_id": ep,
        "has_user_upload": path is not None,
        "path": str(path) if path else None,
        "relpath": episode_first_frame_relpath(episode_id=ep, path=path) if path else None,
        "bytes": path.stat().st_size if path else 0,
        "priority_hint": (
            "用户上传 > 上一集尾帧"
            if _ep_num_safe(ep) > 1
            else "用户上传 > 角色定妆/默认开场"
        ),
    }


def _ep_num_safe(episode_id: str) -> int:
    m = re.match(r"^EP(\d+)$", _ep_folder_id(episode_id), re.I)
    return int(m.group(1)) if m else 1


def upload_episode_first_frame(
    *,
    project_dir: Path,
    episode_id: str,
    source_path: str | Path,
) -> dict[str, Any]:
    """Save user first-frame for this episode; marks downstream rebuild."""
    project_dir = Path(project_dir)
    src = Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(str(src))
    if src.suffix.lower() not in _IMG_EXT:
        raise ValueError(f"Unsupported image type: {src.suffix}")
    ep = _ep_folder_id(episode_id)
    root = episode_open_dir(project_dir=project_dir)
    # Remove other extensions for same EP
    for old in root.glob(f"{ep}.*"):
        if old.suffix.lower() in _IMG_EXT:
            try:
                old.unlink()
            except Exception:  # noqa: BLE001
                pass
    dest = root / f"{ep}{src.suffix.lower()}"
    shutil.copy2(src, dest)
    dirty = mark_episodes_downstream_dirty(
        project_dir=project_dir,
        reason="literary",
        episode_ids=[ep],
        memory_note=f"user first-frame uploaded → {ep} needs_rebuild",
    )
    return {
        "ok": True,
        "episode_id": ep,
        "path": str(dest),
        "relpath": episode_first_frame_relpath(episode_id=ep, path=dest),
        "sha256": file_sha256(dest),
        "downstream_dirty": dirty,
        **get_episode_first_frame_meta(project_dir=project_dir, episode_id=ep),
    }


def clear_episode_first_frame(
    *, project_dir: Path, episode_id: str
) -> dict[str, Any]:
    """Remove user first-frame; next build falls back to tail / open.png."""
    project_dir = Path(project_dir)
    ep = _ep_folder_id(episode_id)
    root = episode_open_dir(project_dir=project_dir)
    removed: list[str] = []
    for old in root.glob(f"{ep}.*"):
        if old.suffix.lower() in _IMG_EXT:
            removed.append(str(old))
            try:
                old.unlink()
            except Exception:  # noqa: BLE001
                pass
    dirty = None
    if removed:
        dirty = mark_episodes_downstream_dirty(
            project_dir=project_dir,
            reason="literary",
            episode_ids=[ep],
            memory_note=f"user first-frame cleared → {ep} needs_rebuild",
        )
    return {
        "ok": True,
        "episode_id": ep,
        "removed": removed,
        "downstream_dirty": dirty,
        **get_episode_first_frame_meta(project_dir=project_dir, episode_id=ep),
    }


def _sync_screenplay_mirror(
    *, project_dir: Path, episode_id: str, content: str
) -> dict[str, Any]:
    """Keep templates/{series}/剧集/{EP}/screenplay.md aligned with dramas episodes."""
    from drama_series_agent.drama.comfy_worker import resolve_templates_dir

    project_dir = Path(project_dir)
    templates_dir = resolve_templates_dir(project_dir)
    ep = _ep_folder_id(episode_id)
    ep_dir = templates_dir / "剧集" / ep
    ep_dir.mkdir(parents=True, exist_ok=True)
    dest = ep_dir / "screenplay.md"
    dest.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(dest), "episode_id": ep}


def _mark_episode_run_dirty(
    *,
    project_dir: Path,
    episode_id: str,
    reason: str = "literary",
    clear_accepted_shots: bool = True,
) -> dict[str, Any]:
    """Flag episode so next scaffold rebuilds even if jsonl already exists.

    reason: literary | cast | bible — stored as dirty flags; any forces S2 rebuild.
    """
    project_dir = Path(project_dir)
    ep = _ep_folder_id(episode_id)
    rt = load_runtime(project_dir)
    row = dict(rt.episodes.get(ep) or {})
    # literary_dirty remains the force bit build_worker historically checks
    row["literary_dirty"] = True
    if reason == "cast":
        row["cast_dirty"] = True
    elif reason == "bible":
        row["bible_dirty"] = True
    if clear_accepted_shots:
        row["accepted_shots"] = []
        if row.get("failed_shots"):
            row["failed_shots"] = []
    if row.get("status") not in ("building", "rendering", "interrupted"):
        row["status"] = "needs_rebuild"
    row["dirty_reason"] = reason
    row["dirty_at"] = _now()
    rt.episodes[ep] = row
    save_runtime(project_dir, rt)
    return {
        "ok": True,
        "episode_id": ep,
        "literary_dirty": True,
        "reason": reason,
        "accepted_shots_cleared": clear_accepted_shots,
    }


def list_known_episode_ids(*, project_dir: Path) -> list[str]:
    """Union of runtime episodes + dramas/episodes/*.md + templates/run/*.jsonl."""
    project_dir = Path(project_dir)
    found: set[str] = set()
    rt = load_runtime(project_dir)
    for ep in rt.episodes.keys():
        found.add(_ep_folder_id(str(ep)))
    dramas = Path(_mounts(project_dir)["dramas_dir"]) / "episodes"
    if dramas.is_dir():
        for p in dramas.glob("*.md"):
            found.add(_ep_folder_id(p.stem))
    try:
        from drama_series_agent.drama.comfy_worker import resolve_templates_dir

        run_dir = resolve_templates_dir(project_dir) / "run"
        if run_dir.is_dir():
            for p in run_dir.glob("*.episode-run.jsonl"):
                stem = p.name.replace(".episode-run.jsonl", "")
                found.add(_ep_folder_id(stem))
    except Exception:  # noqa: BLE001
        pass
    return sorted(found)


def mark_episodes_downstream_dirty(
    *,
    project_dir: Path,
    reason: str,
    episode_ids: Optional[list[str]] = None,
    clear_accepted_shots: bool = True,
    memory_note: Optional[str] = None,
) -> dict[str, Any]:
    """Mark one/all known episodes dirty so S2 must rebuild after S1 upstream change."""
    project_dir = Path(project_dir)
    targets = (
        [_ep_folder_id(e) for e in episode_ids]
        if episode_ids
        else list_known_episode_ids(project_dir=project_dir)
    )
    if not targets:
        targets = ["EP001"]
    marked: list[dict[str, Any]] = []
    for ep in targets:
        marked.append(
            _mark_episode_run_dirty(
                project_dir=project_dir,
                episode_id=ep,
                reason=reason,
                clear_accepted_shots=clear_accepted_shots,
            )
        )
    if memory_note:
        mem = project_dir / "memory" / "PROJECT.md"
        try:
            mem.parent.mkdir(parents=True, exist_ok=True)
            with mem.open("a", encoding="utf-8") as f:
                f.write(f"\n- [{_now()}] {memory_note}\n")
        except Exception:  # noqa: BLE001
            pass
    return {
        "ok": True,
        "reason": reason,
        "episodes": [m.get("episode_id") for m in marked],
        "count": len(marked),
    }


def propagate_literary_write(
    *,
    project_dir: Path,
    episode_id: str,
    content: Optional[str] = None,
) -> dict[str, Any]:
    """After any write to dramas/episodes/{ep}.md — sync screenplay + mark jsonl dirty.

    Used by literary page save, Agent save_literary_episode, and run_literary_generate
    (0xsline skill / stub) so downstream scaffold always sees the new text.
    """
    project_dir = Path(project_dir)
    path = _episode_path(project_dir, episode_id)
    if content is None:
        if not path.is_file():
            raise FileNotFoundError(f"Episode not found: {path}")
        content = path.read_text(encoding="utf-8")
    mirror = _sync_screenplay_mirror(
        project_dir=project_dir, episode_id=path.stem, content=content
    )
    dirty = _mark_episode_run_dirty(
        project_dir=project_dir,
        episode_id=path.stem,
        reason="literary",
        clear_accepted_shots=True,
    )
    return {
        "ok": True,
        "episode_id": path.stem,
        "path": str(path),
        "screenplay_mirror": mirror,
        "episode_run_dirty": dirty,
    }


def open_path_external(*, path: str | Path) -> dict[str, Any]:
    """Open file or folder in OS default app (explorer / open / xdg-open)."""
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(str(p))
    system = platform.system()
    if system == "Windows":
        os.startfile(str(p))  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])
    return {"ok": True, "path": str(p), "system": system}


def open_literary_external(*, project_dir: Path, episode_id: str) -> dict[str, Any]:
    path = _episode_path(project_dir, episode_id)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return open_path_external(path=path)


def open_literary_folder(*, project_dir: Path) -> dict[str, Any]:
    dramas = Path(_mounts(project_dir)["dramas_dir"]) / "episodes"
    dramas.mkdir(parents=True, exist_ok=True)
    return open_path_external(path=dramas)


def import_literary_file(
    *,
    project_dir: Path,
    source_path: str | Path,
    episode_id: Optional[str] = None,
    copy_to_input: bool = True,
) -> dict[str, Any]:
    """Import an external md/txt into episodes/ (and immutable 输入/)."""
    project_dir = Path(project_dir)
    src = Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(str(src))
    eid = _normalize_ep_id(episode_id or src.stem)
    content = src.read_text(encoding="utf-8", errors="replace")
    if copy_to_input:
        from drama_series_agent.intake.fs_util import copy_immutable

        mounts = _mounts(project_dir)
        copy_immutable(src, Path(mounts["input_dir"]) / "scripts")
    return save_literary_episode(
        project_dir=project_dir,
        episode_id=eid,
        content=content,
        invalidate=True,
    )


# ---------------------------------------------------------------------------
# Cast assets
# ---------------------------------------------------------------------------


def list_cast_assets(*, project_dir: Path) -> dict[str, Any]:
    project_dir = Path(project_dir)
    cast_dir = Path(_mounts(project_dir)["cast_dir"])
    draft_dir = cast_dir / "draft"
    rt = load_runtime(project_dir)
    accepted_hashes = _accepted_hashes(project_dir, kind="cast")

    table: dict[str, Any] = {}
    table_path = cast_dir / "cast_table.json"
    if table_path.is_file():
        table = json.loads(table_path.read_text(encoding="utf-8"))

    names: list[str] = []
    for c in table.get("characters") or []:
        if c.get("name"):
            names.append(c["name"])
    # Discover from files
    for folder in (draft_dir, cast_dir):
        if not folder.is_dir():
            continue
        for p in folder.glob("*"):
            if p.is_file() and p.suffix.lower() in _IMG_EXT and p.parent == folder:
                if p.stem not in names and p.name != "series_manifest.json":
                    names.append(p.stem)

    # series_manifest keys
    sm_path = cast_dir / "series_manifest.json"
    series_manifest: dict[str, Any] = {}
    if sm_path.is_file():
        series_manifest = json.loads(sm_path.read_text(encoding="utf-8"))
        for k in series_manifest:
            if k not in names:
                names.append(k)

    assets: list[dict[str, Any]] = []
    for name in names:
        draft = None
        for ext in _IMG_EXT:
            cand = draft_dir / f"{name}{ext}"
            if cand.is_file():
                draft = cand
                break
        final = None
        for ext in _IMG_EXT:
            cand = cast_dir / f"{name}{ext}"
            if cand.is_file():
                final = cand
                break
        rel_final = f"data/cast/{project_dir.name}/{final.name}" if final else None
        status = "missing"
        if final and rt.s1_gate.get("cast_leads_accepted"):
            if rel_final and accepted_hashes.get(rel_final) == file_sha256(final):
                status = "accepted"
            else:
                status = "dirty"
        elif draft:
            status = "draft"
        elif final:
            status = "promoted_unaccepted"

        role = "supporting"
        for c in table.get("characters") or []:
            if c.get("name") == name:
                role = c.get("role") or role
                break

        assets.append(
            {
                "name": name,
                "role": role,
                "status": status,
                "draft_path": str(draft) if draft else None,
                "final_path": str(final) if final else None,
                "preview_path": str(draft or final) if (draft or final) else None,
            }
        )

    return {
        "ok": True,
        "assets": assets,
        "cast_dir": str(cast_dir),
        "draft_dir": str(draft_dir),
        "cast_leads_accepted": bool(rt.s1_gate.get("cast_leads_accepted")),
    }


def upload_cast_image(
    *,
    project_dir: Path,
    character: str,
    source_path: str | Path,
    invalidate: bool = True,
) -> dict[str, Any]:
    """Copy user file into draft/{character}.ext then optionally invalidate cast Accept."""
    project_dir = Path(project_dir)
    src = Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(str(src))
    if src.suffix.lower() not in _IMG_EXT:
        raise ValueError(f"Unsupported image type: {src.suffix}")
    name = character.strip()
    if not name:
        raise ValueError("character required")

    cast_dir = Path(_mounts(project_dir)["cast_dir"])
    draft_dir = cast_dir / "draft"
    draft_dir.mkdir(parents=True, exist_ok=True)
    # Prefer .png extension naming for consistency; keep original bytes/ext
    dest = draft_dir / f"{name}{src.suffix.lower()}"
    # Remove other ext drafts for same name
    for old in draft_dir.glob(f"{name}.*"):
        if old != dest and old.suffix.lower() in _IMG_EXT:
            hist = draft_dir / "_history"
            hist.mkdir(exist_ok=True)
            shutil.move(str(old), str(hist / f"{old.stem}_{uuid_short()}{old.suffix}"))
    shutil.copy2(src, dest)

    # Immutable input copy
    from drama_series_agent.intake.fs_util import copy_immutable

    copy_immutable(src, Path(_mounts(project_dir)["input_dir"]) / "images")

    inv = None
    if invalidate:
        inv = invalidate_accept(
            project_dir=project_dir,
            scope="cast",
            reason=f"upload_cast_image:{name}",
            character=name,
        )

    dirty = mark_episodes_downstream_dirty(
        project_dir=project_dir,
        reason="cast",
        memory_note=f"cast upload → needs_rebuild ({name})",
    )

    # Update cast_table
    table_path = cast_dir / "cast_table.json"
    if table_path.is_file():
        table = json.loads(table_path.read_text(encoding="utf-8"))
        found = False
        for c in table.get("characters") or []:
            if c.get("name") == name:
                c["image_status"] = "draft"
                c["accepted"] = False
                found = True
        if not found:
            table.setdefault("characters", []).append(
                {
                    "name": name,
                    "role": "lead",
                    "image_status": "draft",
                    "accepted": False,
                }
            )
        table["updated_at"] = _now()
        table_path.write_text(
            json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    return {
        "ok": True,
        "character": name,
        "draft_path": str(dest),
        "sha256": file_sha256(dest),
        "invalidated": inv,
        "downstream_dirty": dirty,
    }


def reject_cast_image(*, project_dir: Path, character: str) -> dict[str, Any]:
    """Move draft to _history; does not promote."""
    project_dir = Path(project_dir)
    cast_dir = Path(_mounts(project_dir)["cast_dir"])
    draft_dir = cast_dir / "draft"
    name = character.strip()
    moved: list[str] = []
    hist = draft_dir / "_history"
    hist.mkdir(parents=True, exist_ok=True)
    for p in draft_dir.glob(f"{name}.*"):
        if p.suffix.lower() in _IMG_EXT:
            dest = hist / f"{p.stem}_{uuid_short()}{p.suffix}"
            shutil.move(str(p), str(dest))
            moved.append(str(dest))
    invalidate_accept(
        project_dir=project_dir,
        scope="cast",
        reason=f"reject_cast_image:{name}",
        character=name,
    )
    dirty = mark_episodes_downstream_dirty(
        project_dir=project_dir,
        reason="cast",
        memory_note=f"cast reject → needs_rebuild ({name})",
    )
    return {
        "ok": True,
        "character": name,
        "moved_to": moved,
        "downstream_dirty": dirty,
    }


def open_cast_folder(*, project_dir: Path, draft: bool = True) -> dict[str, Any]:
    cast_dir = Path(_mounts(project_dir)["cast_dir"])
    target = cast_dir / "draft" if draft else cast_dir
    target.mkdir(parents=True, exist_ok=True)
    return open_path_external(path=target)
