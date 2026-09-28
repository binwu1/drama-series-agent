# Development home: drama-series-agent

## Principle

| Concern | Lives in |
|---------|----------|
| Agent, intake, jobs, API, web, R2V runner, workflows | **this repo** |
| Experimental host UI / other products | optional consumers |

## Daily loop

1. Open / clone `E:\Projects\aigc\drama-series-agent` (or your GitHub fork).
2. `pip install -e ".[render,dev]"`
3. Start ComfyUI → set `COMFYUI_URL`
4. Edit code under `src/drama_series_agent/`
5. Render with `drama-series-render` or enqueue via API/Web

## Cursor / IDE

Prefer opening **`drama-series-agent` as the workspace root**, not the old host tree.

## Porting from an old host

If you still have an older host checkout:

- Keep it only as a reference for assets or historical runs
- New features land here first
- Host can `pip install -e /path/to/drama-series-agent` and delete duplicated `hermes_*` packages later
