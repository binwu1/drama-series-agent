---
name: drama-series-h3-r2v-prompts
description: >-
  Maps vendor-agnostic short-drama motion specs into MiniMax H3 Reference-to-Video
  episode-run.jsonl with dense <Picture N> / <Audio N> tags, ref_characters,
  ref_voices, and first_frame chain rules. Default execution prompt is official
  Ref2VA English six-section format (h3-prompt-writing). Use when authoring or
  converting drama-series-agent H3 R2V episode runs, MiniMax R2V prompts,
  Picture/Audio wiring, cast refs, or templates/{series} shot lines — not for
  generic upstream motion writing alone.
---

# Drama Series MiniMax H3 R2V Prompts

Fuses [MiniMax-H3 `h3-prompt-writing`](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing) **Full-Reference (Ref2VA)** English rewrite format with dense Picture/Audio wiring for **drama-series-agent**.

## Boundary (do not blur)

| Layer | Owner | Output |
|-------|--------|--------|
| Motion | **前中后模版** [timed-motion-template.md](references/timed-motion-template.md)（方案 A：因果链 / 动作预算 / 空间连续 / 剧情保真 / 微反应 / 对白预算 / 运镜；**无**秒区间、无 Picture/Audio/`<d>`） | 通用中文运动正文 |
| Execution wiring | **本 skill** + `drama_series_agent.drama.build_worker` | `run/{EP}.episode-run.jsonl`：**六段键英文 + 正文默认中文** |

- Never push MiniMax tag spelling into upstream motion text.
- Never invent Flux keyframes for style lock (Policy B); continuity is `first_frame` chain + refs.
- Do not use i2v `h3_episode_run.py` for these lines.

## When invoked

1. Read accepted motion (storyboard / video-prompts / hand-off notes).
2. **If prose is thin:** run **运动润色** below → write back `video-prompts.md`.
3. Resolve cast series + Cast Library names (`data/cast/{series}/`).
4. Rebuild via `build_worker` / project `_build_run.py` → 中文六段正文 `video_prompt`（接线层不扩写剧情）。
5. Optional: hand-polish `detailed_description`（本仓默认中文；官方文档示例多为英文）。
6. Validate + run H3 (`--context-ir off` preferred).

## 运动润色（画面感）— before rebuild · 方案 A

**Owner:** upstream `剧集/{EP}/storyboard/video-prompts.md` (tag-free Chinese).  
细则见 [timed-motion-template.md](references/timed-motion-template.md)。

**Motion Golden Sentence：**  
`空间站位 + 主体动作 + 目标/方向 + 对方反应 + 状态变化 + 微反应 + 短对白 + 嵌入物理声`

硬规则摘要：Story Fidelity / Action Causality / Action Budget(1主+1转+1结) / Spatial Continuity / Micro-reaction / **Dialogue Required（每镜 ≥1 句）** / Diegetic Sound / 一句运镜 / H3 Feasibility / `结束帧:` 接线剥离。

**每镜必有对白（硬规则）**：上游 `video-prompts.md` 与接线 `episode-run.jsonl` **每一镜**至少一句 `角色名：「…」` / `<d>[Chinese]…</d>`。禁止纯动作静默镜；拆镜时勿把对白全堆到邻镜而留空镜。短动作镜可用极短喊话（≤6 字）。

### Flow

1. 剧情保真解析 → 空间/动作规划 → 前中后润色写回 md。
2. Rebuild：`python scripts/h3_r2v_episode_run.py --project templates/{series} --episode EP00N` 或由 Agent `run_s2_build_and_comfy` → **EN Ref2VA** jsonl。
3. 抽检 `video_prompt`：六段键齐全；`<Picture 1>` + Subjects；对白用 `<d>[Chinese]…</d>`；**正文默认中文**；无 `不说话` / `does not speak` / `几乎听不见` / `barely audible` / `对X说` / `结束帧`。
4. 按需 `--force` / `--from-shot` 重跑。

## Wiring law (dense indices)

| Tag | Maps to | Notes |
|-----|---------|--------|
| `<Picture 1>` | `first_frame` | Always |
| `<Picture 2>`… | `ref_characters[0]`… | Identity only |
| `<Audio 1>`… | `ref_voices[0]`… | Max 3; omit if empty |
| Caps | Images ≤ 9; audio ≤ 3 | |

**Forbidden:** sparse indices; cast as Picture 1; unused Audio tags.

## Prompt body recipe (default = official Ref2VA EN)

See [ref2va-en-official.md](references/ref2va-en-official.md). Section order:

```text
subject_definitions:
<Picture 1> is the first frame of [Shot 1], ….
<Subject 1> is {Name}, whose appearance must strictly match <Picture 2>.
…
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).   # only if wired

summary:
[keyframe completion + reference generation] The target video begins from <Picture 1> …

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - …
<Subject 1> (appears in [Shot 1]): fully_preserved - identity locked to <Picture 2>.
…

detailed_description:
The target video is a restrained literary short-drama clip in vertical 9:16, …
[Shot 1] The shot begins from <Picture 1>. … 
<Subject N> (Sx) says in a …, <d>[Chinese] …</d> He closes his lips and holds the pose.
… Match total duration to about Ns. Lips stay closed except during spoken lines.

overall_soundscape:
…

non_diegetic_music:
N/A
```

### Hard bans (H3 may speak them)

| Ban | Prefer |
|-----|--------|
| `不说话` / does not speak / no dialogue / remain silent | `lips closed` / holds pose |
| `几乎听不见` / barely audible / almost inaudible | physical soft SFX only |
| `对X说` / narrated “says to X” outside `<d>` | facing / gaze |
| Literary smile VO (`笑僵了一寸`) | visible `嘴角` / mouth-corner |
| Timed `【画面与动作】` / `[0s-` lean ZH (legacy) | default off; `--format timed` only for A/B |

### Dialogue ↔ facing + partner reaction (**add-on**; does not replace bans above)

See [dialogue-facing-bind.md](references/dialogue-facing-bind.md) (PixelDojo eyelines / observable acting; official H3 actions+composition; avoid ad-style eye-contact-with-camera).

For **each** spoken `<d>` beat in EN `detailed_description`:

1. **Facing** — body/face toward partner or prop (3/4 or profile), not the lens  
2. **Eyeline** — gaze on partner/prop during the line  
3. **Partner reaction** — ≥1 visible response in the same beat  
4. **Action nest** — point/reach/step while speaking; do not stack bare lines then one late grab  

Camera: prefer OTS / profile / readable two-shot over dual frontal talking heads.

### Legacy

`--format timed` keeps Chinese second-interval lean body (subject_definitions + detailed_description only). Default is `--format en` (six-section English).

## `first_frame` / `link_mode`

| Situation | `first_frame.source` |
|-----------|----------------------|
| EP001 shot 1 | `external` / `keyframe_file` + `path` |
| Later EP shot 1 | `prev_episode_tail` + `prev_episode_id` |
| Within-ep chain | `prev_shot_tail` + `prev_shot_id`, `link_mode=chain` |

## JSONL minimum fields

```json
{
  "schema_version": "1.0.0",
  "episode_id": "EP00N",
  "shot_id": "SHOT-00N",
  "order": 1,
  "duration_seconds": 8.0,
  "audio_mode": "native",
  "link_mode": "chain",
  "ref_characters": ["庄周916"],
  "ref_voices": [],
  "first_frame": { "source": "external", "path": "assets/open.png" },
  "video_prompt": "subject_definitions:\n…\nsummary:\n…\n…"
}
```

## Self-check

### Upstream motion

- [ ] 前→中→后因果链；动作预算；无 STYLE / upstream `<d>` / Picture tags

### Wiring (jsonl)

- [ ] Six English section keys present (unless `--format timed`)
- [ ] `<Picture 1>` + `<Subject i>` / `<Picture i+1>` for each cast
- [ ] `<Audio i>` iff `ref_voices`
- [ ] Dialogue only inside `<d>[Chinese]…</d>`; post-line = closed lips
- [ ] **Every shot has ≥1 `<d>[Chinese]…</d>`** (no silent shots)
- [ ] **Each `<d>` has facing + eyeline to partner/prop + partner reaction** ([dialogue-facing-bind.md](references/dialogue-facing-bind.md))
- [ ] **Multi-speaker: speaker lips open / listener lips closed; no ambiguous He** (anti-swap)
- [ ] No speech/audibility/literary meta (ZH or EN)
- [ ] Chain `prev_shot_tail` after order 1

## Run

```bash
python scripts/h3_r2v_episode_run.py --project templates/起死 --episode EP00N --context-ir off
```

## References

- [Ref2VA EN official fuse](references/ref2va-en-official.md)
- [Dialogue ↔ facing + partner reaction](references/dialogue-facing-bind.md)
- [前中后运动模版](references/timed-motion-template.md)
- [Picture/Audio wiring](references/picture-audio-wiring.md)
- [Episode-run schema](references/episode-run-schema.md)
- [Worked example](examples.md)
- Upstream skill: https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing
- Eyeline / observable acting: https://pixeldojo.ai/guides/minimax-h3-prompting-guide
- Code: `drama_series_agent.adapters.r2v` · `drama_series_agent.drama.build_worker` · `scripts/h3_r2v_episode_run.py`
- Skill path: `skills/drama-series-h3-r2v-prompts/`
