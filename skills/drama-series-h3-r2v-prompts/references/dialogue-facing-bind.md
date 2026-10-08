# Dialogue ↔ Facing + Partner Reaction (hard rule)

**Add-on** to existing Pixelle H3 rules. Does **not** replace: Chinese-only-in-`<d>`, speech-meta bans, dense Picture wiring, six-section EN Ref2VA, or upstream 前中后方案 A.

## Why

Drama shots that only write `says… <d>…</d>` + `holds the pose` often render as **to-camera recitation**. Community H3 guides stress:

- **Screen geography + eyelines** — name who stands where and **where each pair of eyes goes** ([PixelDojo H3 guide](https://pixeldojo.ai/guides/minimax-h3-prompting-guide)).
- **Observable behaviour, not emotion summaries** — eyes / hands / breath / what stays still; abstract “anxious” collapses to generic camera address (same guide).
- **Actions and reactions on the timeline** — official [h3-prompt-writing](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing) asks for composition, subjects, **actions**, camera — not plot-only or delivery-only lines.
- **Inter-character eye contact** for two-handers (shot–reverse / mutual look), not phone-ad “eye contact with camera” ([SuperMaker](https://supermaker.ai/blog/minimax-h3-prompting-guide-how-to-create-better-ai-videos/), [Kapwing](https://www.kapwing.com/resources/how-to-prompt-minimax-h3-hailuo-3-0-a-guide-for-ai-video-creators/)).

## Hard rule (every spoken line in `detailed_description`)

For **each** `<Subject N> (Sx) says… <d>[Chinese] …</d>` beat, the surrounding English **must** bind all of:

| Slot | Required visible content | Prefer | Avoid |
|------|--------------------------|--------|--------|
| **Facing** | Body/face oriented to partner or prop target | `turns toward <Subject M>`, `3/4 profile toward…`, `chin toward the robe hem` | Frontal to lens; unspecified facing |
| **Eyeline** | Where eyes go **during** the line | `gaze locked on <Subject M>'s face/sleeve` | `eye contact with the camera` (unless intentional direct address) |
| **Partner reaction** | Other subject’s visible response overlapping or immediately after | lean back, flinch, grip tighten, look away then back, reach | Speaker freezes alone with `holds the pose` for the rest of the clip |
| **Action nest** | At least one hand/body verb tied to the line | point / reach / step in / pull hem **while** or **as** they speak | Stack 2–3 bare `<d>` lines then put the only grab at the end |
| **Speaker lock** | Who owns the line + listener mouth | `only <Subject N>'s lips open; <Subject M> listens with lips closed` | Ambiguous `He says`; `stays silent` / `does not speak`; group “they argue” |

Still **forbidden** outside `<d>` (unchanged): `says to X` / `对X说` / `不说话` / `no dialogue` / audibility meta.  
Facing is written as **visible orientation**, not narrated speech verbs.

**Also required (upstream + wiring):** every shot has **≥1** spoken `<d>` / `角色名：「…」` — no silent bridge shots. See Dialogue Budget in [timed-motion-template.md](timed-motion-template.md).

### Anti-swap (multi-speaker one shot)

H3 often **swaps mouths/voices** when two speakers share a two-shot ([community writeup](https://punsnest.com/how-to-stop-minimax-h3-from-giving-dialogue-to-the-wrong-character/); [MiniMax#17](https://github.com/MiniMax-AI/MiniMax-H3/issues/17) voice bleed). Mitigate:

1. Restate cast key once: `(S1)=<Subject 1>=Name + visible trait + Picture tag`  
2. On each handoff: **speaker lips open / listener lips closed**  
3. Prefer `<Subject N> closes his lips` over bare `He closes…`  
4. Keep turn-taking short; avoid “both argue” while only one `<d>` is owned  
5. Wav `<Audio N>` hard-locks timbre better than Voice notes (when cast files exist)

## Camera preference for dialogue two-shots

- Prefer **over-shoulder**, **profile / 3/4**, or **medium two-shot with both eyelines readable**.
- Avoid defaulting to two front-facing talking heads unless the beat is intentional address to camera.
- Keep **one** dominant camera idea (community tip: don’t stack orbit + track + push).

## Mini template (EN execution)

```text
<Subject 2> stands left-of-frame, body angled toward <Subject 1> on the right (not toward the lens).
Gaze on <Subject 1>'s robe hem. As he leans in and points at the cloth,
<Subject 2> (S2) says in a hard short rural voice, <d>[Chinese] …</d>
He closes his lips; hand still extended.
<Subject 1> leans a half-step back, eyes on <Subject 2>'s face, then answers…
```

## Self-check (add to wiring checklist)

- [ ] Every `<d>` line has facing + eyeline to partner/prop (not camera)
- [ ] Partner shows ≥1 visible reaction in the same beat
- [ ] Dialogue nested in reach/step/point — not all speech then one late gesture
- [ ] Camera favors OTS / profile / readable two-shot over dual frontal
- [ ] No new speech-meta; Chinese still only inside `<d>`
