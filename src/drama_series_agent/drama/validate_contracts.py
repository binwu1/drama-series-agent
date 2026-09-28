# -*- coding: utf-8 -*-
"""Validate examples / payloads against hermes/contracts/*.schema.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_CONTRACTS = Path(__file__).resolve().parents[3] / "docs" / "contracts"


@lru_cache(maxsize=8)
def _load_schema(name: str) -> dict[str, Any]:
    path = _CONTRACTS / name
    return json.loads(path.read_text(encoding="utf-8"))


def validate_job_event(data: dict[str, Any]) -> list[str]:
    return _validate(data, "job_events.schema.json")


def validate_series_runtime(data: dict[str, Any]) -> list[str]:
    return _validate(data, "series_runtime.schema.json")


def validate_accept_decision(data: dict[str, Any]) -> list[str]:
    return _validate(data, "accept_decision.schema.json")


def _validate(data: dict[str, Any], schema_name: str) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        # Lightweight fallback when jsonschema not installed
        return _lightweight(data, schema_name)

    schema = _load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(schema)
    return sorted({e.message for e in validator.iter_errors(data)})


def _lightweight(data: dict[str, Any], schema_name: str) -> list[str]:
    schema = _load_schema(schema_name)
    errs: list[str] = []
    for key in schema.get("required") or []:
        if key not in data:
            errs.append(f"missing required property: {key}")
    enums = {}
    for prop, spec in (schema.get("properties") or {}).items():
        if "enum" in spec and prop in data and data[prop] not in spec["enum"]:
            # allow null if type includes null — skip complex union
            if data[prop] is not None:
                enums[prop] = data[prop]
    for prop, val in enums.items():
        errs.append(f"{prop} value {val!r} not in enum")
    return errs
