# -*- coding: utf-8 -*-
"""series_runtime.json load/save — L1 truth for Series Agent."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

CONTRACT_VERSION = "1.0.0"

STAGES = (
    "idle",
    "s1_intake",
    "s1_enrich",
    "s2_ready",
    "s2_building",
    "s2_rendering",
    "s3_episode_done",
    "s4_review",
    "s5_maintain",
    "s6_deliver",
    "series_idle",
)

# Process-local locks: literary worker + API often touch the same file concurrently.
_RUNTIME_LOCKS: dict[str, threading.RLock] = {}
_RUNTIME_LOCKS_GUARD = threading.Lock()


def _runtime_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _RUNTIME_LOCKS_GUARD:
        lock = _RUNTIME_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _RUNTIME_LOCKS[key] = lock
        return lock


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def next_episode_id(ep: str) -> str:
    m = re.match(r"^EP(\d+)$", ep.strip().upper())
    if not m:
        return "EP001"
    return f"EP{int(m.group(1)) + 1:03d}"


@dataclass
class SeriesRuntime:
    series_id: str
    stage: str = "idle"
    conversation_id: Optional[str] = None
    default_workflow: Optional[str] = None
    aspect: str = "9:16"
    context_ir: str = "off"
    last_completed_episode: Optional[str] = None
    next_episode: Optional[str] = "EP001"
    active_job_ids: list[str] = field(default_factory=list)
    enrich_jobs: list[dict[str, Any]] = field(default_factory=list)
    episodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    s1_gate: dict[str, Any] = field(
        default_factory=lambda: {
            "literary_accepted": False,
            "cast_leads_accepted": False,
            "audio_status": "missing",
            "ready_for_s2": False,
        }
    )
    deliveries: list[dict[str, Any]] = field(default_factory=list)
    contract_version: str = CONTRACT_VERSION
    updated_at: str = field(default_factory=_now)

    def touch(self) -> None:
        self.updated_at = _now()

    def to_dict(self) -> dict[str, Any]:
        self.touch()
        return {
            "contract_version": self.contract_version,
            "series_id": self.series_id,
            "conversation_id": self.conversation_id,
            "stage": self.stage,
            "default_workflow": self.default_workflow,
            "aspect": self.aspect,
            "context_ir": self.context_ir,
            "last_completed_episode": self.last_completed_episode,
            "next_episode": self.next_episode,
            "active_job_ids": list(self.active_job_ids),
            "enrich_jobs": deepcopy(self.enrich_jobs),
            "episodes": deepcopy(self.episodes),
            "s1_gate": deepcopy(self.s1_gate),
            "deliveries": deepcopy(self.deliveries),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SeriesRuntime":
        return cls(
            series_id=data["series_id"],
            stage=data.get("stage") or "idle",
            conversation_id=data.get("conversation_id"),
            default_workflow=data.get("default_workflow"),
            aspect=data.get("aspect") or "9:16",
            context_ir=data.get("context_ir") or "off",
            last_completed_episode=data.get("last_completed_episode"),
            next_episode=data.get("next_episode"),
            active_job_ids=list(data.get("active_job_ids") or []),
            enrich_jobs=list(data.get("enrich_jobs") or []),
            episodes=dict(data.get("episodes") or {}),
            s1_gate=dict(
                data.get("s1_gate")
                or {
                    "literary_accepted": False,
                    "cast_leads_accepted": False,
                    "audio_status": "missing",
                    "ready_for_s2": False,
                }
            ),
            deliveries=list(data.get("deliveries") or []),
            contract_version=data.get("contract_version") or CONTRACT_VERSION,
            updated_at=data.get("updated_at") or _now(),
        )

    def refresh_s1_ready(self) -> bool:
        g = self.s1_gate
        ready = bool(g.get("literary_accepted")) and bool(
            g.get("cast_leads_accepted")
        )
        g["ready_for_s2"] = ready
        if ready and self.stage in ("idle", "s1_intake", "s1_enrich"):
            self.stage = "s2_ready"
        return ready

    def resolve_episode_intent(self, text: str) -> str:
        """Parse『第二集』/ EP002 / default next_episode."""
        t = text.strip()
        m = re.search(r"EP\s*(\d+)", t, re.I)
        if m:
            return f"EP{int(m.group(1)):03d}"
        m = re.search(r"第\s*(\d+)\s*集", t)
        if m:
            return f"EP{int(m.group(1)):03d}"
        ordinals = {
            "一": 1,
            "二": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
        }
        m = re.search(r"第\s*([一二三四五六七八九十])\s*集", t)
        if m and m.group(1) in ordinals:
            return f"EP{ordinals[m.group(1)]:03d}"
        return self.next_episode or "EP001"


def default_runtime(series_id: str, *, conversation_id: Optional[str] = None) -> SeriesRuntime:
    return SeriesRuntime(
        series_id=series_id,
        conversation_id=conversation_id,
        stage="s1_intake",
        next_episode="EP001",
    )


def runtime_path(project_dir: Path) -> Path:
    return Path(project_dir) / "series_runtime.json"


def _series_id_from_project(project_dir: Path) -> str:
    series_id = project_dir.name
    pj = project_dir / "project.json"
    if pj.is_file():
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
            series_id = (
                data.get("slug")
                or data.get("project_id")
                or data.get("title")
                or series_id
            )
        except Exception:  # noqa: BLE001
            pass
    return str(series_id)


def _read_runtime_dict(path: Path) -> Optional[dict[str, Any]]:
    """Parse runtime JSON; return None if empty/corrupt."""
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not data.get("series_id"):
        return None
    return data


def load_runtime(project_dir: Path, *, create_if_missing: bool = True) -> SeriesRuntime:
    """Load series_runtime.json; tolerate empty/corrupt mid-write; recreate if needed."""
    project_dir = Path(project_dir)
    path = runtime_path(project_dir)
    lock = _runtime_lock(path)
    with lock:
        if path.is_file():
            data = _read_runtime_dict(path)
            if data is None:
                # Concurrent writer may briefly leave empty file — retry a few times
                for _ in range(5):
                    time.sleep(0.05)
                    data = _read_runtime_dict(path)
                    if data is not None:
                        break
            if data is None:
                bak = path.with_suffix(path.suffix + ".bak")
                if bak.is_file():
                    data = _read_runtime_dict(bak)
            if data is not None:
                return SeriesRuntime.from_dict(data)
            if not create_if_missing:
                raise FileNotFoundError(f"corrupt series_runtime.json: {path}")
            # Last resort: rebuild default (keeps series usable after race truncate)
            rt = default_runtime(_series_id_from_project(project_dir))
            save_runtime(project_dir, rt)
            return rt

        if not create_if_missing:
            raise FileNotFoundError(f"missing series_runtime.json: {path}")

        rt = default_runtime(_series_id_from_project(project_dir))
        save_runtime(project_dir, rt)
        return rt


def save_runtime(project_dir: Path, runtime: SeriesRuntime) -> Path:
    """Atomic write to avoid empty/partial JSON during concurrent API + worker access."""
    path = runtime_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(runtime.to_dict(), ensure_ascii=False, indent=2) + "\n"
    lock = _runtime_lock(path)
    with lock:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            if path.is_file() and path.stat().st_size > 0:
                try:
                    bak = path.with_suffix(path.suffix + ".bak")
                    # Best-effort backup of last good file
                    bak.write_bytes(path.read_bytes())
                except Exception:  # noqa: BLE001
                    pass
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
    return path
