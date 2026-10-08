# episode-run.jsonl schema notes

Authoritative models: `pixelle_video/h3_r2v_episode/schema.py`.
Structural checks: `validate.validate_episode_run`.

## ShotRunLine

| Field | Required | Notes |
|-------|----------|--------|
| `schema_version` | yes | `"1.0.0"` |
| `episode_id` | yes | e.g. `EP002` |
| `shot_id` | yes | e.g. `SHOT-001` |
| `order` | yes | unique, sorted ascending |
| `duration_seconds` | yes | `(0, 15.5]` |
| `video_prompt` | yes | must include required tags |
| `first_frame` | yes | see sources |
| `ref_characters` | no | max 8 names |
| `ref_voices` | no | max 3 names |
| `audio_mode` | no | `native` (default) \| `tts` |
| `link_mode` | no | `chain` (default) \| `independent` |
| `cast_series_id` | no | overrides meta when set |
| `drama_refs` | no | opaque upstream ids |

## FirstFrameRef.source

- `external` — `path` relative to project or absolute
- `keyframe_file` — `path` required
- `prev_shot_tail` — `prev_shot_id` required (chain)
- `prev_episode_tail` — `prev_episode_id` required; needs `continuity/episode-tails.json` at run time

## EpisodeMeta (sidecar)

Typical path: `run/{EP}.episode-meta.json`

- `h3_workflow`: `selfhost/video_minimax_h3_r2v.json`
- `cast_series_id`, `default_link_mode`, `default_audio_mode`, `aspect`, `ref_image_size`

## Validate mentally vs code

After writing JSONL, if the repo is available:

```bash
# from Pixelle-Video root with portable python
python -c "from pathlib import Path; from pixelle_video.h3_r2v_episode.schema import load_episode_run_jsonl; from pixelle_video.h3_r2v_episode.validate import validate_episode_run; p=Path('templates/h3_r2v_drama_project/run/EP002.episode-run.jsonl'); e=validate_episode_run(load_episode_run_jsonl(p)); print(e or 'ok')"
```
