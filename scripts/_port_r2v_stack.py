# -*- coding: utf-8 -*-
"""Port runnable R2V stack into drama-series-agent (brand-scrubbed)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

SRC_ROOT = Path(r"e:\Program Files\Pixelle-Video-v0.1.15-win64\Pixelle-Video")
DST_ROOT = Path(r"E:\Projects\aigc\drama-series-agent")
R2V_DST = DST_ROOT / "src" / "drama_series_agent" / "adapters" / "r2v"

REPLACEMENTS = [
    (r"from pixelle_video\.h3_r2v_episode\.", "from drama_series_agent.adapters.r2v."),
    (r"import pixelle_video\.h3_r2v_episode\.", "import drama_series_agent.adapters.r2v."),
    (r"from pixelle_video\.h3_episode\.continuity", "from drama_series_agent.adapters.r2v.continuity"),
    (r"from pixelle_video\.h3_episode\.first_frame", "from drama_series_agent.adapters.r2v.first_frame"),
    (r"from pixelle_video\.h3_episode\.media_ops", "from drama_series_agent.adapters.media_ops"),
    (r"from pixelle_video\.h3_episode\.schema", "from drama_series_agent.adapters.r2v.schema"),
    (r"from pixelle_video\.utils\.os_util import get_resource_path", "from drama_series_agent.adapters.paths import get_resource_path"),
    (r"from pixelle_video\.utils\.os_util import get_data_path", "from drama_series_agent.adapters.paths import get_data_path"),
    (r"from pixelle_video\.utils\.cast_registry import[^\n]+", ""),
    (r"from pixelle_video\.utils\.ref_audio_util import[^\n]+", ""),
    (r"from pixelle_video\.config import config_manager", "from drama_series_agent.adapters.config import config_manager"),
    (r"from pixelle_video\.service import pixelle_video as core", "from drama_series_agent.adapters.media_client import get_media_core as _get_core"),
    (r"Pixelle-Video", "drama-series-agent"),
    (r"Pixelle", "Host"),
    (r"pixelle_video", "drama_series_agent"),
]


def scrub(text: str) -> str:
    for a, b in REPLACEMENTS:
        text = re.sub(a, b, text)
    return text


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(scrub(src.read_text(encoding="utf-8")), encoding="utf-8")


def main() -> None:
    if R2V_DST.exists():
        for p in R2V_DST.glob("*.py"):
            p.unlink()

    r2v_src = SRC_ROOT / "pixelle_video" / "h3_r2v_episode"
    for name in (
        "runner.py",
        "schema.py",
        "validate.py",
        "workflow_materialize.py",
        "comfy_cleanup.py",
        "context_ir.py",
        "cast_refs.py",
        "__init__.py",
    ):
        copy_file(r2v_src / name, R2V_DST / name)

    h3 = SRC_ROOT / "pixelle_video" / "h3_episode"
    copy_file(h3 / "continuity.py", R2V_DST / "continuity.py")
    # first_frame imports ShotRunLine from schema — use r2v schema
    ff = scrub((h3 / "first_frame.py").read_text(encoding="utf-8"))
    ff = ff.replace(
        "from drama_series_agent.adapters.r2v.schema import FirstFrameRef, LastFrameRef, ShotRunLine",
        "from drama_series_agent.adapters.r2v.schema import FirstFrameRef, ShotRunLine",
    )
    # remove LastFrameRef usage if any — keep resolve_frame_ref_path typing simple
    ff = ff.replace("FirstFrameRef | LastFrameRef", "FirstFrameRef")
    (R2V_DST / "first_frame.py").write_text(ff, encoding="utf-8")

    # workflows
    wf_src = SRC_ROOT / "workflows" / "selfhost"
    wf_dst = DST_ROOT / "workflows" / "selfhost"
    wf_dst.mkdir(parents=True, exist_ok=True)
    for name in (
        "video_minimax_h3_r2v.json",
        "video_minimax_h3_r2v_fast.json",
    ):
        shutil.copy2(wf_src / name, wf_dst / name)

    # data/cast placeholder
    cast = DST_ROOT / "data" / "cast" / "_example"
    cast.mkdir(parents=True, exist_ok=True)
    (cast / "voices").mkdir(exist_ok=True)
    (cast / "README.md").write_text(
        "# Cast library\n\nPut series folders here: `data/cast/{series_id}/{character}.png`\n"
        "Optional voices: `data/cast/{series_id}/voices/{character}.wav` (2–15s).\n",
        encoding="utf-8",
    )

    print("ported r2v + workflows")


if __name__ == "__main__":
    main()
