# Architecture decisions (Hermes Drama Loop v1)

Locked for implementation planning. Do not diverge without a new decision record.

## D1 — Web shell

**Original:** Extend HostApp Streamlit with Chat | Asset Studio | Job Panel.

### D1-bis (2026-09-20) — Product shell is React + Agent API

**Choice:** Hermes Series Agent **target UX** is an independent **React** app + **FastAPI Agent API** (LLM tool calling → `hermes_drama`/`hermes_intake` dispatch).

- **1 conversation window ↔ 1 `series_id`**; user can open additional windows (= new series).
- Stages advance via Agent tools, not stage radios; page shows **status bar** only.
- Chat-primary + **collapsible right workbench** (Accept / preview / Job), auto-opens when needed.
- Streamlit Hermes stage panels remain **dev/fallback**; Home/History/Cast stay on Streamlit for v1.
- Spec: [`docs/superpowers/specs/2026-09-20-hermes-agent-chat-shell-design.md`](../../../docs/superpowers/specs/2026-09-20-hermes-agent-chat-shell-design.md)

HostApp remains worker host (Comfy, enrich, build). Independent Hermes-only deploy without workers is out of scope.

## D2 — S1 exit gate

**S1-A** intake (detect/ingest/scaffold) + **S1-B** enrich (literary generate + cast image generate when gaps).

Exit requires Web **Accept** on:

- literary package (or uploaded canonical index)
- cast anchors for lead characters

Audio may stay `deferred`.

## D3 — Async jobs

Agent tools **enqueue** only. Comfy / jsonl build / image gen run in workers and emit Job Events. Chat posts milestones only.

## D4 — S4–S7 scope (same Agent v1)

Same Series Agent owns:

| Stage | In v1? |
|-------|--------|
| S4 Review / rerun shots | Yes |
| S5 Series maintain (cast/voice/style) | Yes |
| S6 Deliver package | Yes (minimal export) |
| S7 Resume after browser close | Yes (L1 `series_runtime` + session bind) |

New series = new conversation (or explicit `switch_series`).

## D5 — Truth root

`projects/{series_id}/` with mounts to `dramas/`, `templates/`, `data/cast/` (see Stage1 intake).
