# -*- coding: utf-8 -*-
"""Legacy service shim — prefer media_client.get_media_core()."""

from drama_series_agent.adapters.media_client import get_media_core

pixelle_video = get_media_core()  # noqa: N816 — historical inject name in some call sites
