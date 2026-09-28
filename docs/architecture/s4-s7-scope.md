# S4–S7 scope (Agent v1)

All stages share **one Hermes Series Agent** per conversation / `series_id`.

## S4 Review (landed)

Module: `drama_series_agent/hermes_drama/review.py`  
Web: `web/components/hermes_s4_panel.py` + Hermes Drama **S4 Review** tab  
Tools (via `dispatch` / `tool_schemas`):

| Tool | Behavior |
|------|----------|
| `list_episode_shots` | jsonl + accept/lock/failed/video flags |
| `get_shot_prompt` | full `video_prompt` for one shot |
| `patch_shot_prompt` | edit prompt/duration; **blocked if locked**; clears that shot's accept |
| `accept_shot` / `reject_shot` | per-shot accept (+optional lock) / mark failed |
| `lock_shot` / `unlock_shot` | gate patch & rerun |
| `accept_episode` | accept all; optional `lock_all` |
| `rerun_shots` | Comfy from earliest requested shot; **locked need `force=True`** |

Runtime keys under `episodes.{EP}`: `accepted_shots[]`, `locked_shots[]`, `failed_shots[]`, `resume_from_shot`, status `accepted` / `rendering` / `partial`.

## S5 Series maintain

- Tools: `cast_image_ingest`, `voice_ingest`, `update_series_style`, `mark_character_look`
- Elevates `creator_authority` only after Accept

## S6 Deliver (minimal v1)

- Tool: `export_series_package(series_id, episode_ids?)`
- Outputs: masters playlist, manifest of paths, version stamp in runtime `deliveries[]`

## S7 Resume

- On Web reload: bind conversation ↔ `series_id` via session store
- Prefetch `series_runtime` + active `job_id`s; Job Panel resubscribes Event Bus
- Agent does not require full chat history if L1 runtime is intact

## Out of v1

- Multi-series parallel in one chat
- Independent Hermes-only Web shell
- Auto publish to social platforms
