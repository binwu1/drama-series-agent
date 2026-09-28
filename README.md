# drama-series-agent

Series-scoped agent for short-drama production:

**intake → enrich → build jsonl → ComfyUI render → next episode**

> One chat window ↔ one `series_id`.  
> **Clone → configure ComfyUI → render.** Development home is this repo.

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) on `PATH`
- Local [ComfyUI](https://github.com/comfyanonymous/ComfyUI) with MiniMax H3 Ref2VA nodes/models loaded
- Optional: Node 18+ for the React workbench (`web/`)

## Install

```bash
cd drama-series-agent
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[render,dev]"
```

Environment (optional):

```bash
# Windows PowerShell
$env:DRAMA_SERIES_ROOT = (Get-Location).Path
$env:COMFYUI_URL = "http://127.0.0.1:8188"
```

Copy `.env.example` values as needed.

## Layout

```text
src/drama_series_agent/
  agent/ drama/ intake/ api/   # orchestration
  adapters/
    r2v/           # episode runner (real render)
    media_client.py
    media_ops.py   # concat + trim head 0.3s
workflows/selfhost/
  video_minimax_h3_r2v.json
  video_minimax_h3_r2v_fast.json
data/cast/{series}/            # character anchors + voices/
projects/{series}/             # Hermes project truth
templates/{series}/            # episode run/ + output/
web/                           # React chat + jobs UI
```

## Render one episode (CLI)

Prepare:

1. Cast: `data/cast/{series}/{角色}.png` (+ optional `voices/{角色}.wav`)
2. Episode project: `templates/{series}/run/EP001.episode-run.jsonl` + `EP001.episode-meta.json`
3. ComfyUI running at `COMFYUI_URL`

```bash
drama-series-render `
  --project templates/西游记 `
  --episode EP001 `
  --cast-series 西游记 `
  --context-ir off `
  --comfyui-url http://127.0.0.1:8188
```

Or:

```bash
python -m drama_series_agent.cli run_episode_main   # via entry point drama-series-render
```

Output: `templates/{series}/output/{EP}/master.mp4` (each shot head-trimmed 0.3s on concat).

## Agent API + Web

```bash
python scripts/run_api.py --host 127.0.0.1 --port 8000
# Docs: http://127.0.0.1:8000/docs   routes under /api/series/...

cd web && npm install && npm run dev
```

## Switching development here

This repo is the **source of truth** for agent + render.  
Legacy host apps should depend on / vendor this package (or call its CLI/API), not the other way around.

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## License

Apache-2.0
