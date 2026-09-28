# -*- coding: utf-8 -*-
"""Lightweight config shim — replace with your host config manager."""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

from drama_series_agent.adapters.config.schema import HostAppVideoConfig


class _Manager:
    def __init__(self) -> None:
        self.config = HostAppVideoConfig()

    def get(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def update(self, updates: dict[str, Any]) -> None:
        data = self.config.to_dict()
        for k, v in (updates or {}).items():
            if isinstance(v, dict) and isinstance(data.get(k), dict):
                data[k].update(v)
            else:
                data[k] = v
        cfg = HostAppVideoConfig()
        cfg._data = data
        self.config = cfg

    def save(self) -> None:
        return None


config_manager = _Manager()

__all__ = ["config_manager", "HostAppVideoConfig"]
