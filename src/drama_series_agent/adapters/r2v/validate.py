from __future__ import annotations

import re
from typing import List, Tuple

from drama_series_agent.adapters.r2v.schema import ShotRunLine

# H3 native audio often vocalizes these meta-instructions as spoken words.
# Prefer visible lip/pose only (嘴唇闭合 / 只保持姿态). Checked outside <d>…</d>.
# Also ban audibility meta ("几乎听不见") — model may narrate it instead of soft SFX.
SPEECH_META_INDUCING_PHRASES: Tuple[str, ...] = (
    "不说话",
    "不再说话",
    "不念旁白",
    "不念台词",
    "不念白",
    "不念动作描述",
    "不张嘴",
    "不低语",
    "不吟唱",
    "不哼唱",
    "不喊叫",
    "保持沉默",
    "没有任何说话",
    "禁止说话",
    "禁止发声",
    "禁止对白",
    "禁止旁白",
    "禁止念白",
    "禁止吟诵",
    "禁止哼唱",
    "禁止喃喃自语",
    "禁止人物产生任何语言",
    "全程禁止发声",
    "不产生任何可辨识的人声",
    "人物声音行为约束",
    "本镜为纯环境声",
    "本镜纯环境声",
    # Audibility meta-commentary (narrated instead of soft diegetic SFX)
    "几乎听不见",
    "几乎听不到",
    "听不见",
    "听不到",
    "微不可闻",
    "细不可闻",
    "几乎无声",
    "安静得没有声音",
    # Literary expression voiceover (abstract 「笑」as noun → often spoken)
    "笑僵了一寸",
    "的笑已经很稳",
    "笑已经很稳",
    "的笑没了",
    "庄子的笑没了",
    # English Ref2VA meta (same failure mode as ZH)
    "does not speak",
    "doesn't speak",
    "do not speak",
    "don't speak",
    "without speaking",
    "no dialogue",
    "no speech",
    "remain silent",
    "remains silent",
    "stays silent",
    "barely audible",
    "almost inaudible",
    "cannot be heard",
    "can't be heard",
    "inaudible",
)

# Narrated speech verbs outside <d> (e.g. 对巡士说) — H3 often vocalizes them.
_SUBJECT_SAY_LINE_RE = re.compile(
    r"<Subject \d+>\s*\(S\d+\)[^<\n]*(?:说道|says)[，,]?",
    flags=re.I,
)
_NARRATIVE_SAY_FIND_RE = re.compile(
    r"[\u4e00-\u9fff]{1,6}对[\u4e00-\u9fff]{1,8}说"
)
# EN narrated "X says to Y" outside official Subject delivery lines
_NARRATIVE_SAYS_TO_RE = re.compile(
    r"\b(?:he|she|they|[A-Z][a-z]+)\s+says\s+to\b",
    flags=re.I,
)

_D_BLOCK_RE = re.compile(r"<d>\s*\[Chinese\].*?</d>", flags=re.S | re.I)


def prompt_outside_dialogue(prompt: str) -> str:
    """Strip MiniMax dialogue blocks so speech-meta checks ignore spoken lines."""
    return _D_BLOCK_RE.sub(" ", prompt or "")


def find_speech_meta_inducing(prompt: str) -> List[str]:
    """Return inducing phrases found outside <d>…</d> (stable order, unique)."""
    hay = prompt_outside_dialogue(prompt)
    hits: List[str] = []
    for phrase in SPEECH_META_INDUCING_PHRASES:
        if phrase in hay:
            hits.append(phrase)
    # Ignore official <Subject …说道/says> delivery markers; flag narrated 对X说 / says to
    hay2 = _SUBJECT_SAY_LINE_RE.sub(" ", hay)
    for m in _NARRATIVE_SAY_FIND_RE.finditer(hay2):
        hit = m.group(0)
        if hit not in hits:
            hits.append(hit)
    for m in _NARRATIVE_SAYS_TO_RE.finditer(hay2):
        hit = m.group(0)
        if hit not in hits:
            hits.append(hit)
    return hits


def validate_episode_run(shots: List[ShotRunLine]) -> List[str]:
    errors: List[str] = []
    if not shots:
        return ["episode-run is empty"]

    orders = [s.order for s in shots]
    if orders != sorted(orders):
        errors.append("shots must be unique-sorted by order")
    if len(set(orders)) != len(orders):
        errors.append("duplicate order values")

    by_order = {s.order: s for s in shots}
    first = by_order[min(by_order)]
    if first.episode_id == "EP001" and first.order == 1:
        if first.first_frame.source == "prev_episode_tail":
            errors.append("EP001 order=1 cannot use prev_episode_tail")
        if first.first_frame.source == "prev_shot_tail":
            errors.append("order=1 cannot use prev_shot_tail")

    for s in shots:
        if s.link_mode == "chain" and s.order > 1:
            if s.first_frame.source != "prev_shot_tail":
                errors.append(
                    f"{s.shot_id}: link_mode=chain requires first_frame.source=prev_shot_tail"
                )
            elif not s.first_frame.prev_shot_id:
                errors.append(f"{s.shot_id}: prev_shot_tail needs prev_shot_id")
        if s.first_frame.source == "prev_episode_tail" and not s.first_frame.prev_episode_id:
            errors.append(f"{s.shot_id}: prev_episode_tail needs prev_episode_id")
        if s.first_frame.source in ("external", "keyframe_file") and not s.first_frame.path:
            errors.append(f"{s.shot_id}: {s.first_frame.source} needs path")

        # Tag presence (soft structure): Picture 1 always; Picture 2.. if chars; Audio if voices
        prompt = s.video_prompt or ""
        if "<Picture 1>" not in prompt and "<picture 1>" not in prompt.lower():
            errors.append(f"{s.shot_id}: video_prompt should reference <Picture 1> (start frame)")
        for i, _name in enumerate(s.ref_characters, start=2):
            tag = f"<Picture {i}>"
            if tag not in prompt:
                errors.append(f"{s.shot_id}: missing {tag} for ref_characters[{i - 2}]")
        for i, _name in enumerate(s.ref_voices, start=1):
            tag = f"<Audio {i}>"
            if tag not in prompt:
                errors.append(f"{s.shot_id}: missing {tag} for ref_voices[{i - 1}]")

        inducing = find_speech_meta_inducing(prompt)
        if inducing:
            shown = " / ".join(inducing[:4])
            more = f" (+{len(inducing) - 4} more)" if len(inducing) > 4 else ""
            errors.append(
                f"{s.shot_id}: speech/audibility-meta cue may be spoken by H3: {shown}{more} "
                f"(use visible lips closed / 嘴唇闭合 + diegetic SFX; "
                f"ban 不说话/does not speak/几乎听不见/barely audible/…)"
            )

        # Hard rule: every shot must carry spoken dialogue (《起死》/H3 native).
        if not _D_BLOCK_RE.search(prompt):
            errors.append(
                f"{s.shot_id}: missing dialogue — every shot needs ≥1 "
                f"<d>[Chinese]…</d> (no silent shots)"
            )
    return errors
