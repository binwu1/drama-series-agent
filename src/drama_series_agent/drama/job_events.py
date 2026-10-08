# -*- coding: utf-8 -*-
"""Job event model aligned with hermes/contracts/job_events.schema.json."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class JobEventType(str, Enum):
    JOB_QUEUED = "JobQueued"
    BUILD_STARTED = "BuildStarted"
    BUILD_DONE = "BuildDone"
    SHOT_STARTED = "ShotStarted"
    SHOT_PROGRESS = "ShotProgress"
    SHOT_DONE = "ShotDone"
    SHOT_FAILED = "ShotFailed"
    EPISODE_DONE = "EpisodeDone"
    JOB_CANCELLED = "JobCancelled"
    JOB_FAILED = "JobFailed"
    ENRICH_STARTED = "EnrichStarted"
    ENRICH_DONE = "EnrichDone"
    MILESTONE = "Milestone"


class JobCancelled(Exception):
    """Soft-stop a render/build at the next shot boundary."""

    def __init__(self, job_id: str, shot_id: Optional[str] = None, message: str = ""):
        self.job_id = job_id
        self.shot_id = shot_id
        detail = message or f"job {job_id} cancelled"
        if shot_id:
            detail = f"{detail} at {shot_id}"
        super().__init__(detail)


class JobKind(str, Enum):
    LITERARY_GENERATE = "literary_generate"
    SERIES_DEVELOP = "series_develop"
    CAST_IMAGE_GENERATE = "cast_image_generate"
    INTAKE_FINALIZE = "intake_finalize"
    BUILD_EPISODE_JSONL = "build_episode_jsonl"
    COMFY_EPISODE = "comfy_episode"
    EXPORT_PACKAGE = "export_package"


_PHASES = frozenset(
    {
        None,
        "queued",
        "building",
        "validating",
        "uploading",
        "sampling",
        "downloading",
        "freeing_vram",
        "concat",
        "done",
        "failed",
        "cancelled",
    }
)


@dataclass
class JobEvent:
    event_type: JobEventType
    job_id: str
    job_kind: JobKind
    series_id: str
    episode_id: Optional[str] = None
    shot_id: Optional[str] = None
    workflow: Optional[str] = None
    index: Optional[int] = None
    total: Optional[int] = None
    ratio: Optional[float] = None
    phase: Optional[str] = None
    progress: Optional[float] = None
    paths: dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    message: Optional[str] = None
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:16]}")
    ts: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if isinstance(self.event_type, str):
            self.event_type = JobEventType(self.event_type)
        if isinstance(self.job_kind, str):
            self.job_kind = JobKind(self.job_kind)
        if self.phase not in _PHASES:
            raise ValueError(f"invalid phase: {self.phase!r}")
        if self.ratio is not None and not 0.0 <= self.ratio <= 1.0:
            raise ValueError("ratio must be in [0,1]")
        if self.progress is not None and not 0.0 <= self.progress <= 1.0:
            raise ValueError("progress must be in [0,1]")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        d["job_kind"] = self.job_kind.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobEvent":
        payload = dict(data)
        paths = dict(payload.pop("paths") or {})
        return cls(paths=paths, **payload)

    def to_progress_event(self):
        """Bridge to optional host ProgressEvent (best-effort)."""
        from drama_series_agent.adapters.progress import ProgressEvent

        prog = self.progress
        if prog is None and self.index is not None and self.total:
            prog = (self.index + (self.ratio or 0.0)) / max(self.total, 1)
        if prog is None:
            prog = 0.0
        action = self.phase
        return ProgressEvent(
            event_type=self.event_type.value,
            progress=min(max(prog, 0.0), 1.0),
            frame_current=(self.index + 1) if self.index is not None else None,
            frame_total=self.total,
            action=action,
            extra_info=self.shot_id or self.message,
        )


def append_event_jsonl(path: Path, event: JobEvent) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(event.to_json() + "\n")
