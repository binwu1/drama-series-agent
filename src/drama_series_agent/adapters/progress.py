# -*- coding: utf-8 -*-
"""Minimal progress event bridge (host UI optional)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProgressEvent:
    event_type: str
    progress: float
    frame_current: Optional[int] = None
    frame_total: Optional[int] = None
    step: Optional[int] = None
    action: Optional[str] = None
    extra_info: Optional[str] = None
