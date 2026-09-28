# -*- coding: utf-8 -*-
"""Ingest script / cast images / voices into Hermes project + mount targets."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.intake.fs_util import (
    copy_immutable,
    detect_inputs,
    file_sha256,
    voice_quality_status,
)
from drama_series_agent.intake.manifest import AssetBucket, IntakeManifest, load_manifest
from drama_series_agent.intake.scaffold import load_project


_NAME_HINT_RE = re.compile(
    r"(?:角色|人物|主演)[:：\s]*([^\n,，、]{1,12})"
    r"|《[^》]+》\s*([^\s，。]{1,8})"
)


def _character_hints_from_text(text: str, limit: int = 20) -> list[str]:
    found: list[str] = []
    for m in _NAME_HINT_RE.finditer(text):
        name = (m.group(1) or m.group(2) or "").strip()
        if name and name not in found:
            found.append(name)
    # Also pull markdown ## headings that look like character cards
    for line in text.splitlines():
        if line.startswith("## ") and 1 < len(line) < 20:
            title = line[3:].strip()
            if title and title not in found and "集" not in title:
                found.append(title)
    return found[:limit]


def script_ingest(
    project_dir: Path,
    sources: list[Path],
    *,
    script_kind: Optional[str] = None,
    character_name: Optional[str] = None,
) -> IntakeManifest:
    project_dir = Path(project_dir)
    project = load_project(project_dir)
    input_dir = Path(project["mounts"]["input_dir"])
    dramas_dir = Path(project["mounts"]["dramas_dir"])
    manifest = _safe_load(project_dir)

    ingested: list[dict[str, Any]] = []
    hints: list[str] = list(manifest.character_name_hints)
    for src in sources:
        src = Path(src)
        if not src.is_file():
            continue
        dest = copy_immutable(src, input_dir / "scripts")
        # Mirror copy into dramas for literary suite discovery (still non-canonical)
        mirror = copy_immutable(src, dramas_dir / "输入")
        rec = {
            "source": str(src.resolve()),
            "stored": str(dest),
            "mirror": str(mirror),
            "sha256": file_sha256(dest),
            "name": dest.name,
        }
        ingested.append(rec)
        if dest.suffix.lower() in {".md", ".txt"}:
            try:
                text = dest.read_text(encoding="utf-8", errors="replace")
                for h in _character_hints_from_text(text):
                    if h not in hints:
                        hints.append(h)
            except Exception:  # noqa: BLE001
                pass

    if character_name and character_name not in hints:
        hints.insert(0, character_name)

    if ingested:
        status = "partial" if script_kind in ("novel", "fragment") else "present"
        manifest.script = AssetBucket(status=status, files=ingested)
        if script_kind:
            manifest.script_kind = script_kind
        elif not manifest.script_kind:
            manifest.script_kind = "outline"
    manifest.character_name_hints = hints
    return manifest


def cast_image_ingest(
    project_dir: Path,
    sources: list[Path],
    *,
    character_names: Optional[list[str]] = None,
) -> IntakeManifest:
    """Copy images into cast_dir; named → {name}.png, else unassigned/."""
    project_dir = Path(project_dir)
    project = load_project(project_dir)
    cast_dir = Path(project["mounts"]["cast_dir"])
    input_dir = Path(project["mounts"]["input_dir"])
    manifest = _safe_load(project_dir)
    names = list(character_names or [])
    series_manifest_path = cast_dir / "series_manifest.json"
    series = {}
    if series_manifest_path.is_file():
        series = json.loads(series_manifest_path.read_text(encoding="utf-8"))

    assigned = 0
    unassigned_n = 0
    files: list[dict[str, Any]] = list(manifest.images.files)
    for i, src in enumerate(sources):
        src = Path(src)
        if not src.is_file():
            continue
        # Always keep raw in 输入/
        raw = copy_immutable(src, input_dir / "images")
        name = names[i] if i < len(names) else None
        if name:
            dest = cast_dir / f"{name}{src.suffix.lower()}"
            if dest.suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                dest = cast_dir / f"{name}.png"
            # Prefer png stem for cast; keep original extension if already png/jpg
            dest = cast_dir / f"{name}{src.suffix.lower()}"
            if not dest.exists() or file_sha256(dest) != file_sha256(src):
                dest.write_bytes(src.read_bytes())
            series[name] = {
                "path": str(dest.resolve()),
                "source": "intake",
                "appearance": series.get(name, {}).get("appearance") or "",
            }
            assigned += 1
            files.append(
                {
                    "character": name,
                    "stored": str(dest),
                    "raw": str(raw),
                    "sha256": file_sha256(dest),
                    "assigned": True,
                }
            )
        else:
            dest = copy_immutable(src, cast_dir / "unassigned")
            unassigned_n += 1
            files.append(
                {
                    "character": None,
                    "stored": str(dest),
                    "raw": str(raw),
                    "sha256": file_sha256(dest),
                    "assigned": False,
                }
            )

    series_manifest_path.write_text(
        json.dumps(series, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if assigned == 0 and unassigned_n == 0:
        pass
    elif assigned > 0 and unassigned_n == 0:
        manifest.images = AssetBucket(status="present", files=files)
    elif assigned > 0 and unassigned_n > 0:
        manifest.images = AssetBucket(
            status="partial",
            files=files,
            notes="some images unassigned",
        )
    else:
        manifest.images = AssetBucket(
            status="partial",
            files=files,
            notes="all images unassigned — map to character names",
        )
    return manifest


def voice_ingest(
    project_dir: Path,
    sources: list[Path],
    *,
    character_names: Optional[list[str]] = None,
) -> IntakeManifest:
    project_dir = Path(project_dir)
    project = load_project(project_dir)
    cast_dir = Path(project["mounts"]["cast_dir"])
    voices_dir = cast_dir / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)
    input_dir = Path(project["mounts"]["input_dir"])
    manifest = _safe_load(project_dir)
    names = list(character_names or [])

    files: list[dict[str, Any]] = list(manifest.audio.files)
    present = 0
    partial = 0
    for i, src in enumerate(sources):
        src = Path(src)
        if not src.is_file():
            continue
        raw = copy_immutable(src, input_dir / "audio")
        detected = detect_inputs([src])
        dur = (detected[0].get("duration_seconds") if detected else None)
        vstatus = voice_quality_status(dur)
        name = names[i] if i < len(names) else src.stem
        dest = voices_dir / f"{name}{src.suffix.lower()}"
        if dest.suffix.lower() != ".wav" and src.suffix.lower() == ".wav":
            dest = voices_dir / f"{name}.wav"
        dest.write_bytes(src.read_bytes())
        rec = {
            "character": name,
            "stored": str(dest),
            "raw": str(raw),
            "sha256": file_sha256(dest),
            "duration_seconds": dur,
            "status": vstatus,
        }
        files.append(rec)
        if vstatus == "present":
            present += 1
        else:
            partial += 1

    if present == 0 and partial == 0:
        pass
    elif present > 0 and partial == 0:
        manifest.audio = AssetBucket(status="present", files=files)
    else:
        manifest.audio = AssetBucket(
            status="partial",
            files=files,
            notes="one or more voices outside 2–15s or duration unknown",
        )
    return manifest


def mark_deferred(manifest: IntakeManifest, which: str) -> IntakeManifest:
    which = which.lower()
    if which in ("image", "images", "i"):
        if manifest.images.status == "missing":
            manifest.images.status = "deferred"
            manifest.images.notes = "creator deferred cast images"
    elif which in ("audio", "voice", "voices", "a"):
        if manifest.audio.status == "missing":
            manifest.audio.status = "deferred"
            manifest.audio.notes = "creator deferred voices"
    elif which in ("script", "s"):
        if manifest.script.status == "missing":
            manifest.script.status = "deferred"
            manifest.script.notes = "creator deferred script"
    return manifest


def _safe_load(project_dir: Path) -> IntakeManifest:
    path = Path(project_dir) / "intake_manifest.json"
    if path.is_file():
        return load_manifest(project_dir)
    from drama_series_agent.intake.scaffold import load_project as lp

    pid = lp(project_dir)["project_id"]
    return IntakeManifest(project_id=pid)
