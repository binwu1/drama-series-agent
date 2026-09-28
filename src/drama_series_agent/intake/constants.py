# -*- coding: utf-8 -*-
"""Stage1 constants — normalize-only exit gate (plan default)."""

from __future__ import annotations

STAGE_ID = "stage1_intake"
STAGE_EXIT_GATE = "ready_for_develop_assets"  # not ready_to_comfy
CONTRACT_VERSION = "1.0.0"

ASSET_STATUS = ("present", "missing", "partial", "deferred")

DEFAULT_ASPECT = "9:16"
DEFAULT_PRODUCTION_PROFILE = "h3_ref2va"
DEFAULT_LANGUAGE = "zh-CN"

# Hermes projects/{slug} is authoritative; mounts point at short-drama + HostApp trees.
MOUNT_KEYS = ("dramas_dir", "templates_dir", "cast_dir", "input_dir")

SCRIPT_EXTENSIONS = {".md", ".txt", ".docx", ".pdf", ".fountain", ".fdx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}

VOICE_MIN_SECONDS = 2.0
VOICE_MAX_SECONDS = 15.0
