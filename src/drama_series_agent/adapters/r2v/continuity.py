from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def load_tails(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_tail(path: Path, episode_id: str, tail_frame: str, tail_shot_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_tails(path)
    data[episode_id] = {
        "tail_frame": str(Path(tail_frame).resolve()),
        "tail_shot_id": tail_shot_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
