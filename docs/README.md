# Hermes drama agent (HostApp) — architecture + Stage1 intake

## Status

| Layer | Status |
|-------|--------|
| Architecture S1–S7 | Documented under `hermes/architecture/` |
| Job Event / series_runtime contracts | `hermes/contracts/*.schema.json` |
| Stage1-A intake tools | `drama_series_agent/hermes_intake/` |
| Stage1-B enrich + Accept | `drama_series_agent/hermes_drama/enrich.py` + `decisions.py` |
| Stage1 Asset Studio | `drama_series_agent/hermes_drama/asset_studio.py` |
| S2 build jsonl + validate | `drama_series_agent/hermes_drama/build_worker.py` |
| S2/S3 runtime + event bus + completion hook | `drama_series_agent/hermes_drama/` |
| Comfy / jsonl workers | **Comfy worker wired** (`comfy_worker.enqueue_comfy_episode`) |
| Streamlit S1+S2+Job | `web/pages/4_🤖_Hermes_Drama.py` |

## Locked decisions

See [architecture/DECISIONS.md](architecture/DECISIONS.md):

- Web shell = **extend HostApp Streamlit** (Chat + Assets + Job panel)
- One conversation ↔ one `series_id`
- S1 = intake + enrich (one-liner → script + cast images with Accept)
- S2 = async jsonl + async Comfy; Chat milestones only
- S3 = `on_episode_complete` updates runtime for「生成第二集」
- S4–S7 in same Agent v1

## Quick start (Stage1)

```bash
cd drama-series-agent
python scripts/hermes_drama_intake.py --title 我的短剧
python scripts/hermes_drama_intake.py --dump-schemas
```

S1-B one-liner (API):

```python
from drama_series_agent.drama.dispatch import handle_tool_call
# after scaffold: run_literary_generate → accept_literary_package
# → extract_cast_table → run_cast_image_generate → accept_cast_images
# → mark_audio_deferred → get_s1_gate_status (ready_for_s2)
```

## Layout

| Path | Role |
|------|------|
| `hermes/architecture/` | S1-B, S2–S3 sequence, S4–S7 scope, decisions |
| `hermes/contracts/` | JSON Schema + examples |
| `projects/{slug}/` | L1 truth (`series_runtime.json`, intake, handoff, decisions/) |
| `dramas/{slug}/` | Literary mount |
| `templates/{slug}/` | HostApp episode mount |
| `data/cast/{slug}/` | Cast + voices mount |
| `.cursor/skills/drama-intake/` | Stage1-A skill |

## Python packages

- `drama_series_agent.intake` — detect / scaffold / ingest / handoff
- `drama_series_agent.drama` — JobEvent, SeriesRuntime, EventBus, S1-B enrich, S3 hook, Comfy worker
