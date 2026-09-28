"""Materialize R2V workflow: keep only used ref_image / ref_audio slots wired."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


IMAGE_NODE_IDS = [str(200 + i) for i in range(9)]
AUDIO_NODE_IDS = [str(210 + i) for i in range(3)]
MINIMAX_NODE = "136"


def load_base_workflow(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def materialize_r2v_workflow(
    base: Dict[str, Any],
    *,
    n_images: int,
    n_audios: int,
    ref_image_size: str = "match",
) -> Dict[str, Any]:
    if not (1 <= n_images <= 9):
        raise ValueError("n_images must be 1..9")
    if not (0 <= n_audios <= 3):
        raise ValueError("n_audios must be 0..3")

    wf = copy.deepcopy(base)
    mm = wf[MINIMAX_NODE]["inputs"]
    mm["ref_image_size"] = ref_image_size

    for k in list(mm.keys()):
        if k.startswith("ref_images.") or k.startswith("ref_audios."):
            del mm[k]

    # Drop unused load nodes so ComfyUI won't require placeholder files
    for i, nid in enumerate(IMAGE_NODE_IDS):
        if i < n_images:
            mm[f"ref_images.ref_image_{i}"] = [nid, 0]
        else:
            wf.pop(nid, None)

    for i, nid in enumerate(AUDIO_NODE_IDS):
        if i < n_audios:
            mm[f"ref_audios.ref_audio_{i}"] = [nid, 0]
        else:
            wf.pop(nid, None)

    return wf


def write_temp_workflow(wf: Dict[str, Any], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def build_r2v_media_params(
    *,
    prompt: str,
    duration: float,
    image_paths: List[Path],
    audio_paths: List[Path],
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Dict[str, Any]:
    """ComfyKit flat params matching $~ref_image_N.image / $~ref_audio_N.audio."""
    params: Dict[str, Any] = {
        "prompt": prompt,
        "duration": float(duration),
    }
    if width is not None:
        params["width"] = width
    if height is not None:
        params["height"] = height
    for i, p in enumerate(image_paths):
        params[f"ref_image_{i}"] = str(p.resolve())
    for i, p in enumerate(audio_paths):
        params[f"ref_audio_{i}"] = str(p.resolve())
    return params
