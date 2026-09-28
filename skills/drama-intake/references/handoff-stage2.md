# Stage1 → Stage2 Handoff

`handoff_stage2.json` 由 `intake_gap_report` / `run_intake` 写出。

## 关键字段

```json
{
  "ready": true,
  "exit_gate": "ready_for_develop_assets",
  "case": {"script": "1", "image": "0", "audio": "0", "code": "S1I0A0"},
  "suggested_skills": ["short-drama-write", "short-drama-assets"],
  "blocks_visual": true,
  "blocks_audio_hardlock": true,
  "gaps": ["cast_images_missing_or_deferred", "voices_missing_or_deferred"],
  "forbid": [
    "load_storyboard_skill_in_stage1",
    "auto_promote_script_to_canonical",
    "generate_images_or_audio_in_stage1"
  ],
  "next_stage": "stage2_develop_or_assets"
}
```

## Stage2 入口约定（预留，本阶段不实现）

1. 读 `projects/{slug}/handoff_stage2.json`。
2. 若 `blocks_visual` 且目标是成片 → 先 assets / image-prompts。
3. 若 `script` 为 P → develop 导入流，不得静默覆盖 `输入/`。
4. 直到用户接受前，不写 HostApp `run/*.episode-run.jsonl`。
