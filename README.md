# drama-series-agent

**Series-scoped agent** for short-drama production (intake → enrich → build → async render → next episode).

> One conversation window ↔ one `series_id`.

This repository is the **orchestration core** (agent, tools, job events, contracts, web shell).  
Video backends (Comfy / R2V runners) plug in via `drama_series_agent.adapters`.

## Why this name

GitHub already has several Hermes-prefixed short-drama skills (`hermes-short-drama-team`, `hermes-skill-short-drama-master`, `hermes-audio-drama`, …).  
**`drama-series-agent`** highlights the product shape (series agent + jobs) without colliding with those skill packs or any host-app brand.

## Layout

```text
src/drama_series_agent/
  agent/       # chat loop, sessions, tool merge
  drama/       # runtime, workers, enrich, review
  intake/      # S1 detect / scaffold / manifest
  api/         # FastAPI series routes
  adapters/    # video backend / config shims
web/           # React workbench (chat + jobs)
docs/          # architecture + contracts
skills/        # Stage1 intake skill
scripts/run_api.py
```

## Quick start

```bash
cd drama-series-agent
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python scripts/run_api.py --host 127.0.0.1 --port 8000
```

API prefix: `/api/series/...`

## Adapters

Replace or monkey-patch:

- `drama_series_agent.adapters.r2v.run_episode` — episode render
- `drama_series_agent.adapters.config.config_manager` — LLM / Comfy URLs
- `drama_series_agent.adapters.media_ops.concat_videos` — master concat (default trims 0.3s head)

## Status

Extracted OSS skeleton from an internal host integration. Core agent/drama/intake packages are included; proprietary workflow JSON and cast assets are **not** shipped.

## License

Apache-2.0
