# -*- coding: utf-8 -*-
"""In-memory Event Bus for Job Panel + Agent milestone hooks."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Callable, Optional

from drama_series_agent.drama.job_events import JobEvent, append_event_jsonl
from pathlib import Path


Listener = Callable[[JobEvent], None]


class InMemoryEventBus:
    """Process-local bus; Web Job Panel and Agent subscribe by series_id or *."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._listeners: dict[str, list[Listener]] = defaultdict(list)
        self._history: list[JobEvent] = []
        self._jsonl_path: Optional[Path] = None

    def set_jsonl_log(self, path: Optional[Path]) -> None:
        self._jsonl_path = Path(path) if path else None

    def subscribe(self, series_id: str, listener: Listener) -> None:
        with self._lock:
            self._listeners[series_id].append(listener)

    def unsubscribe(self, series_id: str, listener: Listener) -> None:
        with self._lock:
            lst = self._listeners.get(series_id) or []
            if listener in lst:
                lst.remove(listener)

    def publish(self, event: JobEvent) -> None:
        with self._lock:
            self._history.append(event)
            if self._jsonl_path is not None:
                append_event_jsonl(self._jsonl_path, event)
            targets = list(self._listeners.get(event.series_id) or [])
            targets += list(self._listeners.get("*") or [])
        for fn in targets:
            try:
                fn(event)
            except Exception:  # noqa: BLE001 — UI listeners must not break workers
                pass

    def history(
        self, *, series_id: Optional[str] = None, job_id: Optional[str] = None
    ) -> list[JobEvent]:
        with self._lock:
            out = list(self._history)
        if series_id:
            out = [e for e in out if e.series_id == series_id]
        if job_id:
            out = [e for e in out if e.job_id == job_id]
        return out

    def clear(self) -> None:
        with self._lock:
            self._history.clear()


# Process singleton for Streamlit / agent embedding
_BUS: Optional[InMemoryEventBus] = None


def get_event_bus() -> InMemoryEventBus:
    global _BUS
    if _BUS is None:
        _BUS = InMemoryEventBus()
    return _BUS
