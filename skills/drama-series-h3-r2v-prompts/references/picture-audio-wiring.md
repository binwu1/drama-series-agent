# Picture / Audio wiring (MiniMax H3 R2V)

## Connection order = tag number

Comfy graph / materializer wires:

1. `ref_image_0` ← resolved `first_frame` path → **`<Picture 1>`**
2. `ref_image_1..` ← Cast anchors for `ref_characters` in list order → **`<Picture 2…>`**
3. `ref_audio_0..` ← Cast voices for `ref_voices` in list order → **`<Audio 1…>`**

Unused slots are **not** wired. Therefore prompts must not reserve holes for absent characters.

## What each Picture means in prose

- **Picture 1**: temporal / spatial start of *this* generation (may be previous shot’s end frame). Describe content briefly; do not treat it as a costume bible unless it already shows the character clearly.
- **Picture 2+**: identity lock only. Prefer “match face / hair / costume to `<Picture N>`” over re-describing the whole design from memory.
- Do not assign the same cast name to two Picture indices in one shot.

## Audio

- One voice ref per speaking character that needs timbre lock (≤3).
- Non-speakers need no Audio slot.
- Dialogue: `using <Audio N>:「…」` (or equivalent clear binding).

## vs upstream motion

Upstream may say: “Bulma shouts; Goku answers; camera tracks left.”

This layer adds: which Picture is start, which Picture is Bulma, which Audio is Bulma — without changing the beat.

## Common failures

| Failure | Fix |
|---------|-----|
| Missing `<Picture 2>` while `ref_characters` non-empty | Add tag or drop unused ref |
| Cast as Picture 1 | Move cast to Picture 2+; keep first_frame as 1 |
| Sparse tags for “future” slots | Dense only |
| Rewriting motion to fit tags | Bind tags around existing motion |
| i2v-only prompt (no Picture tags) | Reject for R2V runner |
