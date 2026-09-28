# -*- coding: utf-8 -*-
"""Hermes drama loop contracts: job events, series runtime, completion hooks."""

from drama_series_agent.drama.job_events import JobEvent, JobEventType, JobKind
from drama_series_agent.drama.runtime import (
    SeriesRuntime,
    load_runtime,
    save_runtime,
    default_runtime,
)
from drama_series_agent.drama.completion import on_episode_complete
from drama_series_agent.drama.event_bus import InMemoryEventBus
from drama_series_agent.drama.comfy_worker import enqueue_comfy_episode, get_job_snapshot
from drama_series_agent.drama.enrich import (
    accept_cast_images,
    accept_literary_package,
    run_literary_generate,
)

__all__ = [
    "JobEvent",
    "JobEventType",
    "JobKind",
    "SeriesRuntime",
    "load_runtime",
    "save_runtime",
    "default_runtime",
    "on_episode_complete",
    "InMemoryEventBus",
    "enqueue_comfy_episode",
    "get_job_snapshot",
    "run_literary_generate",
    "accept_literary_package",
    "accept_cast_images",
]
