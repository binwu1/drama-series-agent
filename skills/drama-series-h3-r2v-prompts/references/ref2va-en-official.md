# Ref2VA English execution format (MiniMax H3 official + Pixelle wiring)

Fused from [MiniMax-H3 `h3-prompt-writing`](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing) `references/ref-en.txt`, adapted for Pixelle `episode-run.jsonl` (one generate clip per shot).

## Six sections (required order)

| Section | Language | Role |
|---------|----------|------|
| `subject_definitions` | English | Dense `<Picture N>` / `<Subject N>` / optional `<Audio N>` |
| `summary` | English | `[task types] …` one short paragraph |
| `retention_analysis` | English | One line per label: `fully_preserved` / `reference` / … |
| `detailed_description` | English body; dialogue original language in `<d>` | Single `[Shot 1]` continuous beat |
| `overall_soundscape` | English | Ambience / physical SFX summary (not dialogue) |
| `non_diegetic_music` | English | Score for audience only, or `N/A` |

## Pixelle wiring overrides (do not follow raw official examples that put cast on Picture 1)

| Label | Pixelle meaning |
|-------|-----------------|
| `<Picture 1>` | This shot’s `first_frame` only |
| `<Picture 2…>` | `ref_characters[0…]` identity locks |
| `<Subject N>` | Character matching `ref_characters[N-1]` → `<Picture N+1>` |
| `<Audio N>` | Only if `ref_voices[N-1]` is wired |

## One jsonl shot = one H3 generate

- Prefer a **single** `[Shot 1]` (no multi-shot cut list inside one clip).
- Match described duration to `duration_seconds` (约 7–10s for 《起死》).
- Dialogue: `<Subject N> (Sx) says…, <d>[Chinese] …</d>` then **visible** closed lips / held pose.
- **Chinese only inside `<d>[Chinese]…</d>`.** All other sections (including names in `subject_definitions`) stay English romanization — no 庄周/杨大 outside `<d>`.
- Silence: `lips closed` / `holds the pose` — never “does not speak” / “no dialogue” / `不说话` (H3 may vocalize meta).
- No narrated “says to X” / `对X说` outside `<d>`; use facing/gaze.
- No audibility meta (`barely audible` / `几乎听不见`).
- **Dialogue ↔ facing + partner reaction (add-on hard rule):** see [dialogue-facing-bind.md](dialogue-facing-bind.md). Each spoken line must bind **facing toward partner/prop**, **eyeline (not camera)**, and **≥1 partner reaction**; nest speech in reach/step/point. Does not replace speech-meta bans or Chinese-only-in-`<d>`.

## Upstream vs execution

- Upstream `video-prompts.md` stays **Chinese 前/中/后** (tag-free). See [timed-motion-template.md](timed-motion-template.md).
- Rebuild (`_build_run.py`) emits this **English six-section** shell + converted `<d>` dialogue.
- Prefer hand-polish of `detailed_description` in English when A/B shows auto-wrap is weak.

## Task-type prefix (summary)

Common for 《起死》 chain shots:

`[keyframe completion + reference generation]`

Add `+ audio reference` when `<Audio N>` is present.
