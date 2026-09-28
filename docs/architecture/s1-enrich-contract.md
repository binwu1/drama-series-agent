# S1-B Enrich contract — one-liner → script + cast images

Applies when intake case is `S0I0A0` (or S/I gaps after S1-A). Agent must not stop at a gap list alone if user goal is `full_pipeline` and L0 allows auto enrich.

## Flow

```text
User one-liner
  → project_scaffold(series_id)
  → enrich_job literary (async)
  → Web Accept literary  [gate]
  → extract_cast_table
  → enrich_job cast_images (async, per character)
  → Web Accept each lead image OR batch Accept  [gate]
  → intake_write_manifest (S/I present; A deferred ok)
  → handoff unlocks S2 workflow panel
```

## Accept records (L1)

Written under `projects/{series}/decisions/` as JSONL append-only:

```json
{
  "decision_id": "CD-LIT-EPALL-001",
  "decision_kind": "artifact_acceptance",
  "artifact": "literary_package",
  "status": "accepted",
  "target_hashes": {"dramas/七龙珠/episodes/ep001.md": "<sha256>"},
  "decided_by": "creator",
  "decided_at": "<ISO-8601>",
  "series_id": "七龙珠"
}
```

```json
{
  "decision_id": "CD-CAST-悟空-001",
  "decision_kind": "cast_image_acceptance",
  "artifact": "cast_image",
  "character": "悟空",
  "status": "accepted",
  "target_hashes": {"data/cast/七龙珠/悟空.png": "<sha256>"},
  "decided_by": "creator",
  "decided_at": "<ISO-8601>",
  "series_id": "七龙珠"
}
```

**Rule:** Draft paths without Accept do not count toward S1 exit gate.

## Enrich job kinds (Job Event `job_kind`)

| job_kind | Worker | Success artifact |
|----------|--------|------------------|
| `literary_generate` | S1-B literary | `dramas/{series}/episodes/*.md` + index |
| `cast_image_generate` | image worker | PNG under `data/cast/{series}/` (still draft until Accept) |
| `intake_finalize` | sync | `intake_manifest.json` + `handoff_stage2.json` |

## FunctionCalls (S1-B)

| Name | Sync/Async | Notes |
|------|------------|-------|
| `run_literary_generate` | async enqueue | args: series_id, premise, episode_count, genre |
| `accept_literary_package` | sync | writes decision; updates manifest script=present |
| `extract_cast_table` | sync | from accepted literary |
| `run_cast_image_generate` | async enqueue | args: series_id, characters[], style |
| `accept_cast_images` | sync | characters[] or all pending |
| `mark_audio_deferred` | sync | allow S2 with soft voice |

## Web UI slots

- Chat: premise confirmation (≤3 slots: title, episode_count, style); revision intents
- **Asset Studio** (Mode C): literary embed editor + external open/reload; cast wall + upload/reject/regen — see [s1-asset-studio.md](s1-asset-studio.md)
- Accept tab: literary + batch cast Accept
- Job panel: enrich job bars (`literary_generate`, `cast_image_generate`)

## Memory writes

| Layer | On enrich |
|-------|-----------|
| L1 | `enrich_jobs[]` in `series_runtime.json`; decision JSONL; manifest |
| L2 | pending Accept flags |
| L0 | only if user toggles “always auto-enrich one-liners” |

## Forbidden in S1-B

- Loading storyboard / H3 R2V skills
- Auto-promote draft literary to canonical without Accept
- Hard-locking voices from generated video (S3 candidate only)
