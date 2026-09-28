# -*- coding: utf-8 -*-
"""End-to-end Stage1 intake pipeline (tool orchestration)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from drama_series_agent.intake.fs_util import detect_inputs
from drama_series_agent.intake.ingest import (
    cast_image_ingest,
    mark_deferred,
    script_ingest,
    voice_ingest,
)
from drama_series_agent.intake.manifest import (
    IntakeManifest,
    build_handoff,
    gap_report_text,
    load_manifest,
    write_handoff,
    write_manifest,
)
from drama_series_agent.intake.memory_ops import ask_slots, memory_upsert_project
from drama_series_agent.intake.scaffold import scaffold_project


def run_intake(
    *,
    title: str,
    paths: Optional[list[Path]] = None,
    projects_root: Optional[Path] = None,
    drama_series_root: Optional[Path] = None,
    slug: Optional[str] = None,
    script_kind: Optional[str] = None,
    image_names: Optional[list[str]] = None,
    voice_names: Optional[list[str]] = None,
    defer_images: bool = False,
    defer_audio: bool = False,
    goal: str = "full_pipeline",
) -> dict[str, Any]:
    """Scaffold + classify inputs + ingest + manifest + handoff + memory."""
    paths = [Path(p) for p in (paths or [])]
    sc = scaffold_project(
        title=title,
        projects_root=projects_root,
        drama_series_root=drama_series_root,
        slug=slug,
        goal=goal,
    )
    project_dir = Path(sc["project_dir"])

    detected = detect_inputs(paths) if paths else []
    scripts = [Path(r["path"]) for r in detected if r["kind"] == "script"]
    images = [Path(r["path"]) for r in detected if r["kind"] == "image"]
    audios = [Path(r["path"]) for r in detected if r["kind"] == "audio"]

    # Persist after each ingest so the next step loads a consistent manifest.
    if scripts:
        write_manifest(
            project_dir,
            script_ingest(project_dir, scripts, script_kind=script_kind),
        )
    if images:
        write_manifest(
            project_dir,
            cast_image_ingest(
                project_dir, images, character_names=image_names
            ),
        )
    if audios:
        write_manifest(
            project_dir,
            voice_ingest(project_dir, audios, character_names=voice_names),
        )

    intake_path = project_dir / "intake_manifest.json"
    if intake_path.is_file():
        manifest = load_manifest(project_dir)
    else:
        manifest = IntakeManifest(project_id=sc["project_id"])

    if defer_images:
        mark_deferred(manifest, "images")
    if defer_audio:
        mark_deferred(manifest, "audio")

    write_manifest(project_dir, manifest)
    handoff = build_handoff(project_dir, manifest)
    write_handoff(project_dir, handoff)
    report = gap_report_text(manifest, handoff)
    (project_dir / "gap_report.md").write_text(report, encoding="utf-8")

    facts = [
        f"case_code={handoff['case']['code']}",
        f"script={manifest.script.status}",
        f"images={manifest.images.status}",
        f"audio={manifest.audio.status}",
        f"exit_gate={handoff['exit_gate']}",
    ]
    memory_upsert_project(project_dir, facts)

    missing_slots = []
    if not title:
        missing_slots.append("title")
    if manifest.script.status == "missing" and not defer_images:
        missing_slots.append("has_script")
    if handoff["case"]["code"] == "S0I0A1":
        missing_slots.append("at_least_one_character_name")
    questions = ask_slots(missing_slots) if missing_slots else {"questions": []}

    return {
        "project_dir": str(project_dir),
        "project_id": sc["project_id"],
        "mounts": sc["mounts"],
        "detected": detected,
        "manifest": manifest.to_dict(),
        "handoff": handoff,
        "gap_report": report,
        "ask": questions,
        "ready_for_stage2": bool(handoff.get("ready")),
    }
