# -*- coding: utf-8 -*-
"""intake_manifest.json + Stage2 handoff packet."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from drama_series_agent.intake.case_matrix import CaseCode, classify_case, routing_for
from drama_series_agent.intake.constants import CONTRACT_VERSION, STAGE_EXIT_GATE, STAGE_ID


@dataclass
class AssetBucket:
    status: str = "missing"  # present|missing|partial|deferred
    files: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""


@dataclass
class IntakeManifest:
    project_id: str
    script: AssetBucket = field(default_factory=AssetBucket)
    images: AssetBucket = field(default_factory=AssetBucket)
    audio: AssetBucket = field(default_factory=AssetBucket)
    script_kind: Optional[str] = None  # screenplay|novel|fragment|outline|None
    case_code: Optional[str] = None
    gaps: list[str] = field(default_factory=list)
    character_name_hints: list[str] = field(default_factory=list)
    contract_version: str = CONTRACT_VERSION
    stage: str = STAGE_ID
    exit_gate: str = STAGE_EXIT_GATE
    updated_at: str = ""

    def refresh_case(self) -> CaseCode:
        case = classify_case(
            script_status=self.script.status,
            image_status=self.images.status,
            audio_status=self.audio.status,
            script_kind=self.script_kind,
        )
        self.case_code = case.code
        self.gaps = _compute_gaps(self)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return case

    def to_dict(self) -> dict[str, Any]:
        self.refresh_case()
        return {
            "contract_version": self.contract_version,
            "project_id": self.project_id,
            "stage": self.stage,
            "exit_gate": self.exit_gate,
            "script": asdict(self.script),
            "images": asdict(self.images),
            "audio": asdict(self.audio),
            "script_kind": self.script_kind,
            "case_code": self.case_code,
            "gaps": self.gaps,
            "character_name_hints": self.character_name_hints,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntakeManifest":
        def bucket(key: str) -> AssetBucket:
            b = data.get(key) or {}
            return AssetBucket(
                status=b.get("status", "missing"),
                files=list(b.get("files") or []),
                notes=b.get("notes") or "",
            )

        m = cls(
            project_id=data["project_id"],
            script=bucket("script"),
            images=bucket("images"),
            audio=bucket("audio"),
            script_kind=data.get("script_kind"),
            character_name_hints=list(data.get("character_name_hints") or []),
        )
        m.case_code = data.get("case_code")
        m.gaps = list(data.get("gaps") or [])
        m.updated_at = data.get("updated_at") or ""
        return m


def _compute_gaps(m: IntakeManifest) -> list[str]:
    gaps: list[str] = []
    if m.script.status in ("missing",):
        gaps.append("script_missing")
    elif m.script.status == "partial" or m.script_kind in ("novel", "fragment"):
        gaps.append("script_not_canonical")
    if m.images.status in ("missing", "deferred"):
        gaps.append("cast_images_missing_or_deferred")
    elif m.images.status == "partial":
        gaps.append("cast_images_partial_unassigned")
    if m.audio.status in ("missing", "deferred"):
        gaps.append("voices_missing_or_deferred")
    elif m.audio.status == "partial":
        gaps.append("voices_partial_quality")
    return gaps


def write_manifest(project_dir: Path, manifest: IntakeManifest) -> Path:
    project_dir = Path(project_dir)
    path = project_dir / "intake_manifest.json"
    data = manifest.to_dict()
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def load_manifest(project_dir: Path) -> IntakeManifest:
    path = Path(project_dir) / "intake_manifest.json"
    return IntakeManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))


def build_handoff(project_dir: Path, manifest: IntakeManifest) -> dict[str, Any]:
    case = manifest.refresh_case()
    route = routing_for(case)
    # Normalize-only gate: pass when project scaffold + manifest written +
    # authority fields exist (checked by caller). Visual/audio gaps may remain.
    ready = True
    forbid = list(route.get("forbid") or [])
    forbid.extend(
        [
            "load_storyboard_skill_in_stage1",
            "load_video_prompts_skill_in_stage1",
            "load_drama_series_h3_r2v_in_stage1",
            "auto_promote_script_to_canonical",
            "generate_images_or_audio_in_stage1",
        ]
    )
    packet = {
        "ready": ready,
        "project_id": manifest.project_id,
        "project_dir": str(Path(project_dir).resolve()),
        "exit_gate": STAGE_EXIT_GATE,
        "case": case.to_dict(),
        "case_label": route.get("label"),
        "stage1_action_done": route.get("stage1_action"),
        "suggested_skills": route.get("suggested_skills") or [],
        "blocks_visual": bool(route.get("blocks_visual")),
        "blocks_audio_hardlock": bool(route.get("blocks_audio_hardlock")),
        "gaps": list(manifest.gaps),
        "forbid": forbid,
        "character_name_hints": list(manifest.character_name_hints),
        "next_stage": "stage2_develop_or_assets",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return packet


def write_handoff(project_dir: Path, packet: dict[str, Any]) -> Path:
    path = Path(project_dir) / "handoff_stage2.json"
    path.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Update .short-drama/state.json
    state_path = Path(project_dir) / ".short-drama" / "state.json"
    state = {}
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(
        {
            "stage": "intake_done" if packet.get("ready") else "intake",
            "case_code": (packet.get("case") or {}).get("code"),
            "ready_for_stage2": bool(packet.get("ready")),
            "updated_at": packet.get("updated_at"),
        }
    )
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def gap_report_text(manifest: IntakeManifest, handoff: dict[str, Any]) -> str:
    lines = [
        f"## Stage1 gap report — {manifest.project_id}",
        f"- case: `{handoff.get('case', {}).get('code')}` — {handoff.get('case_label')}",
        f"- exit_gate: `{STAGE_EXIT_GATE}`",
        f"- script: {manifest.script.status} ({len(manifest.script.files)} files)",
        f"- images: {manifest.images.status} ({len(manifest.images.files)} files)",
        f"- audio: {manifest.audio.status} ({len(manifest.audio.files)} files)",
        "",
        "### Gaps",
    ]
    if manifest.gaps:
        for g in manifest.gaps:
            lines.append(f"- {g}")
    else:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "### Suggested Stage2+ skills",
            *[f"- {s}" for s in handoff.get("suggested_skills") or []],
            "",
            "### Blocks",
            f"- visual production blocked: {handoff.get('blocks_visual')}",
            f"- audio hard-lock blocked: {handoff.get('blocks_audio_hardlock')}",
            "",
            "### Forbid",
            *[f"- {f}" for f in handoff.get("forbid") or []],
        ]
    )
    return "\n".join(lines) + "\n"
