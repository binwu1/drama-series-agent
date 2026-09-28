# -*- coding: utf-8 -*-
"""H3 Context-IR for R2V episode runs.

Official H3-Context-IR is a hosted API (not open-sourced). This module provides:

- ``local``: deterministic enricher following MiniMax Prompting Guidance
  (camera vocabulary, prop constraints, beat prose) for offline/selfhost use.
- ``api``: MiniMax ``POST /v2/h3_context_ir`` with file upload → ``mm_file://``
  reference media (requires ``MINIMAX_API_KEY``).
- ``off``: pass-through.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Iterable, List, Literal, Optional

from loguru import logger

ContextIRMode = Literal["off", "local", "api"]

DEFAULT_API_BASE = "https://api.minimaxi.com"
# International alternate; override with MINIMAX_API_BASE
ALT_API_BASE = "https://api.minimax.io"


# ---------------------------------------------------------------------------
# Local enricher (Prompting Guidance stand-in)
# ---------------------------------------------------------------------------

_CAMERA_LINE = re.compile(
    r"(?im)^(?:Camera|摄影机\s*camera)\s*:\s*(.+)$"
)
_CAMERA_PARAMS = re.compile(
    r"(?im)^(?:Camera params|相机参数)\s*:\s*(.+)$"
)
_BEAT = re.compile(
    r"(?im)^(Early|Mid|Late)\s+beat\s*:\s*"
)
_SFX = re.compile(r"(?im)^SFX\s*:\s*")
_VISUAL = re.compile(r"(?im)^Visual\s*:\s*")
_END_FRAME = re.compile(r"(?im)^End frame\s*:\s*")


def _camera_sentence(camera: str, params: str = "") -> str:
    c = camera.strip().rstrip(".")
    low = c.lower()
    motion = "The camera holds a static shot and the frame never moves (no pan, no push-in, no reframing)"
    if any(k in low for k in ("snap-pull", "pull out", "pulls out", "pull to", "pull-")):
        motion = (
            "The camera pulls out with large amplitude at fast speed"
        )
    elif any(k in low for k in ("push", "push-in", "pushes in", "push in")):
        motion = "The camera pushes in with small amplitude at slow speed"
    elif any(k in low for k in ("side track", "truck", "track on", "follow-fly", "follow")):
        motion = "The camera performs a tracking shot at fast speed"
    elif "arc" in low:
        motion = "The camera arcs with small amplitude at slow speed"
    elif any(k in low for k in ("shake", "micro-shake")):
        motion = "The camera shakes slightly"
    elif any(k in low for k in ("static", "freeze", "holds", "never moves")):
        motion = (
            "The camera holds a static shot and the frame never moves "
            "(no pan, no push-in, no reframing)"
        )
    else:
        motion = f"The camera moves as follows: {c}"

    detail = c
    if params.strip():
        detail = f"{c}; technical notes: {params.strip().rstrip('.')}"
    return f"{motion}, realizing: {detail}."


def enrich_prompt_local(prompt: str) -> str:
    """Expand sparse timeline labels into IR-friendly continuous English prose."""
    if not prompt or not prompt.strip():
        return prompt

    text = prompt
    # Pair Camera + Camera params on consecutive lines
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        m_cam = _CAMERA_LINE.match(lines[i])
        if m_cam:
            cam = m_cam.group(1)
            params = ""
            if i + 1 < len(lines):
                m_p = _CAMERA_PARAMS.match(lines[i + 1])
                if m_p:
                    params = m_p.group(1)
                    i += 1
            out.append(_camera_sentence(cam, params))
            i += 1
            continue
        if _CAMERA_PARAMS.match(lines[i]):
            # orphan params
            out.append(
                "Camera technical notes: "
                + _CAMERA_PARAMS.match(lines[i]).group(1).strip()
            )
            i += 1
            continue
        line = lines[i]
        line = _BEAT.sub(
            lambda m: {
                "Early": "Early in the shot, ",
                "Mid": "Midway through the shot, ",
                "Late": "Late in the shot, ",
            }[m.group(1)],
            line,
        )
        line = _SFX.sub("Diegetic sound: ", line)
        line = _VISUAL.sub("Visible action: ", line)
        line = _END_FRAME.sub(
            "End state held through the final frame: ", line
        )
        out.append(line)
        i += 1

    text = "\n".join(out)

    # Hard constraints block once (idempotent)
    stamp = (
        "IR constraints: the yellow flying nimbus is an inanimate physical cloud "
        "with no face, eyes, limbs, mouth, or mascot features; the capsule box stays "
        "a sealed handheld case for seven dragon balls; no on-screen text, subtitles, "
        "titles, or readable UI glyphs on screens."
    )
    if "IR constraints:" not in text:
        if "detailed_description:" in text:
            text = text.replace(
                "detailed_description:\n",
                f"detailed_description:\n{stamp}\n",
                1,
            )
        else:
            text = stamp + "\n" + text
    return text


# ---------------------------------------------------------------------------
# Official MiniMax API
# ---------------------------------------------------------------------------

def _api_base() -> str:
    return (
        os.environ.get("MINIMAX_API_BASE")
        or os.environ.get("MINIMAX_BASE_URL")
        or DEFAULT_API_BASE
    ).rstrip("/")


def _api_key() -> str:
    return (
        os.environ.get("MINIMAX_API_KEY")
        or os.environ.get("MINIMAX_GROUP_API_KEY")
        or ""
    ).strip()


def _upload_file(path: Path, api_key: str) -> str:
    """Upload local media; return mm_file://{file_id}."""
    import urllib.request

    boundary = f"----HostH3{uuid_hex()}"
    data = path.read_bytes()
    body = b""
    disposition = (
        f'Content-Disposition: form-data; name="purpose"\r\n\r\n'
        f"video_generation_input\r\n"
    ).encode()
    body += f"--{boundary}\r\n".encode() + disposition
    fname = path.name.encode("utf-8", errors="ignore")
    body += (
        f"--{boundary}\r\n".encode()
        + b'Content-Disposition: form-data; name="file"; filename="'
        + fname
        + b'"\r\nContent-Type: application/octet-stream\r\n\r\n'
        + data
        + b"\r\n"
    )
    body += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{_api_base()}/v1/files/upload",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    file_id = (
        payload.get("file", {}).get("file_id")
        or payload.get("file_id")
        or payload.get("file", {}).get("id")
    )
    if not file_id:
        raise RuntimeError(f"upload missing file_id: {payload}")
    return f"mm_file://{file_id}"


def uuid_hex() -> str:
    import uuid

    return uuid.uuid4().hex[:12]


def _build_api_content(
    prompt: str,
    image_paths: List[Path],
    audio_paths: List[Path],
    api_key: str,
    *,
    with_media: bool,
) -> list[dict]:
    content: list[dict] = [{"type": "text", "text": prompt}]
    if not with_media:
        return content

    # r2va: all images/audios as reference_*; never mix first_frame
    for p in image_paths:
        if not p.is_file():
            continue
        try:
            url = _upload_file(p, api_key)
        except Exception as e:
            logger.warning(f"Context-IR upload skip image {p.name}: {e}")
            continue
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": url},
                "role": "reference_image",
            }
        )
    for p in audio_paths:
        if not p.is_file():
            continue
        # Official audio refs must be wav/mp3 and 2–15s; skip non-audio containers
        if p.suffix.lower() not in {".wav", ".mp3"}:
            logger.warning(f"Context-IR skip non-audio voice file: {p.name}")
            continue
        try:
            url = _upload_file(p, api_key)
        except Exception as e:
            logger.warning(f"Context-IR upload skip audio {p.name}: {e}")
            continue
        content.append(
            {
                "type": "audio_url",
                "audio_url": {"url": url},
                "role": "reference_audio",
            }
        )
    return content


def _create_ir_task(payload: dict, api_key: str) -> str:
    import urllib.request

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{_api_base()}/v2/h3_context_ir",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    task_id = body.get("task_id") or body.get("task", {}).get("id")
    if not task_id:
        raise RuntimeError(f"h3_context_ir create failed: {body}")
    return str(task_id)


def _poll_ir_prompt(task_id: str, api_key: str, *, timeout_s: float = 300) -> str:
    import urllib.request

    url = f"{_api_base()}/v2/query/video_generation/{task_id}"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        task = body.get("task") or body
        status = task.get("status")
        if status == "succeeded":
            prompt = (task.get("content") or {}).get("prompt")
            if not prompt:
                raise RuntimeError(f"IR succeeded but empty prompt: {body}")
            return str(prompt)
        if status in ("failed", "cancelled"):
            raise RuntimeError(f"IR task {status}: {task.get('error') or body}")
        time.sleep(5)
    raise TimeoutError(f"IR task {task_id} timed out after {timeout_s}s")


def enrich_prompt_api(
    prompt: str,
    *,
    duration_seconds: float,
    image_paths: Optional[Iterable[Path]] = None,
    audio_paths: Optional[Iterable[Path]] = None,
    ratio: str = "9:16",
    with_media: bool = True,
) -> str:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError(
            "Context-IR api mode requires MINIMAX_API_KEY (or MINIMAX_GROUP_API_KEY)"
        )
    dur = int(round(float(duration_seconds)))
    dur = max(4, min(15, dur))
    images = [Path(p) for p in (image_paths or [])]
    audios = [Path(p) for p in (audio_paths or [])]
    content = _build_api_content(
        prompt, images, audios, api_key, with_media=with_media
    )
    # If media failed to attach, still IR the text; r2va ratio optional
    has_ref = any(
        c.get("role") in ("reference_image", "reference_audio", "reference_video")
        for c in content
    )
    payload = {
        "model": "MiniMax-H3",
        "content": content,
        "duration": dur,
        "ratio": ratio if has_ref or True else ratio,
    }
    if not has_ref and len(content) == 1:
        # text-only IR requires non-adaptive ratio
        payload["ratio"] = ratio if ratio != "adaptive" else "9:16"

    logger.info(
        f"Context-IR API create: duration={dur}s media_items={len(content) - 1}"
    )
    task_id = _create_ir_task(payload, api_key)
    logger.info(f"Context-IR API task_id={task_id}")
    return _poll_ir_prompt(task_id, api_key)


def _cache_key(
    prompt: str,
    mode: str,
    duration: float,
    image_paths: List[Path],
    audio_paths: List[Path],
) -> str:
    h = hashlib.sha256()
    h.update(mode.encode())
    h.update(f"{duration:.3f}".encode())
    h.update(prompt.encode("utf-8"))
    for p in image_paths + audio_paths:
        h.update(str(p).encode("utf-8", errors="ignore"))
        if p.is_file():
            st = p.stat()
            h.update(f"{st.st_size}:{st.st_mtime_ns}".encode())
    return h.hexdigest()[:16]


def apply_context_ir(
    prompt: str,
    *,
    mode: ContextIRMode,
    duration_seconds: float,
    cache_dir: Path,
    image_paths: Optional[List[Path]] = None,
    audio_paths: Optional[List[Path]] = None,
    ratio: str = "9:16",
    force: bool = False,
    api_with_media: bool = True,
) -> str:
    """Return enriched prompt; caches under cache_dir."""
    mode = (mode or "off").lower()  # type: ignore
    if mode == "off":
        return prompt

    images = list(image_paths or [])
    audios = list(audio_paths or [])
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(prompt, mode, duration_seconds, images, audios)
    cache_path = cache_dir / f"context_ir_{mode}_{key}.txt"
    meta_path = cache_dir / f"context_ir_{mode}_{key}.json"

    if cache_path.is_file() and not force:
        logger.info(f"Context-IR cache hit: {cache_path.name}")
        return cache_path.read_text(encoding="utf-8")

    if mode == "local":
        enriched = enrich_prompt_local(prompt)
    elif mode == "api":
        try:
            enriched = enrich_prompt_api(
                prompt,
                duration_seconds=duration_seconds,
                image_paths=images,
                audio_paths=audios,
                ratio=ratio,
                with_media=api_with_media,
            )
        except Exception as e:
            logger.error(f"Context-IR API failed, falling back to local: {e}")
            enriched = enrich_prompt_local(prompt)
            mode = "local"  # type: ignore
    else:
        raise ValueError(f"unknown context_ir mode: {mode}")

    cache_path.write_text(enriched, encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "mode": mode,
                "cache_key": key,
                "duration_seconds": duration_seconds,
                "chars": len(enriched),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # Convenience alias for the latest IR prompt in the shot folder
    latest = cache_dir / "context_ir_prompt.txt"
    latest.write_text(enriched, encoding="utf-8")
    return enriched
