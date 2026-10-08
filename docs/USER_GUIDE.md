# Drama Series Agent — User Guide

**English** · [中文](USER_GUIDE.zh-CN.md)

End-user manual for the Web workbench and chat-driven short-drama pipeline.  
For install and developer setup, see the [root README](../README.md).

---

## 1. What you get

One **conversation** is bound to one **series**. In chat you drive:

1. **Develop** — outline, world, characters, art style, episode directory  
2. **Write** — per-episode screenplay  
3. **Cast** — character look (and optional voice refs)  
4. **Render** — MiniMax H3 Ref2VA shots → episode `master.mp4`

UI home after launch: **http://localhost:5173/**  
API (must be running): **http://127.0.0.1:8000**

---

## 2. Before you start

| Need | Why |
|------|-----|
| API + workbench started (`.\start.ps1 -WithWeb` / `./start.sh --with-web`) | UI talks to the API |
| LLM configured (System config) | Agent chat / develop / write |
| **Install [ComfyUI](https://github.com/comfyanonymous/ComfyUI) yourself** and download **all models + custom nodes** named in [`workflows/selfhost/`](../workflows/selfhost/) | Actual video render (this repo does not ship ComfyUI or weights) |
| Cast portraits under `data/cast/{series}/` when rendering | Picture refs for Ref2VA |

Model filenames and setup steps: [README · ComfyUI](../README.md#comfyui-required-for-video-render--install-yourself).

Open **http://localhost:5173/**. If the page loads but chat fails, the API on port **8000** is down.

---

## 3. Interface map

| Area | What it is |
|------|------------|
| Left — conversation list | One series per chat; **New chat** creates a series |
| Center — chat | Talk to the Agent in Chinese; tools run in the background |
| Right — **Workbench** | Stage gates, bible / literary / cast shortcuts, render progress |
| Top / modal — **System config** | LLM, ComfyUI URL, **video workflow**, aspect ratio |
| Hash pages | `#/c/{id}/bible`, `literary`, `cast`, `jobs` |

---

## 4. First-time setup (System config)

1. Open **System config**.  
2. Fill **API Key / Base URL / Model** (OpenAI-compatible, e.g. ModelScope). Use **Test** / **Load models** if available.  
3. Set **ComfyUI URL** (default `http://127.0.0.1:8188`) and test connectivity.  
4. Choose **video workflow** and **aspect** (default `9:16`):

| Workflow | When to use |
|----------|-------------|
| `…_fast.json` | Default balanced / clearer dialogue tier |
| `…_lora.json` | Lightning LoRA 4-step (faster, quality tradeoff) |
| `…_turbo.json` | Aggressive speed |
| `…_r2v.json` | Higher quality / fl2va path |

5. Click **Save**. If a series is open, workflow/aspect are also written into that series’ runtime.

---

## 5. Recommended end-to-end flow

### Step A — Create a series

1. **New chat** → title (+ optional premise).  
2. One conversation ↔ one `series_id`. Do not mix unrelated shows in the same chat.

### Step B — Develop the series bible

In chat, say things like:

- 「根据这个点子做立项，写大纲、世界观、主要角色、画风和分集目录」  
- 「确定大纲、世界观、主要角色、画风并形成文件」

The Agent should call **develop** (background job). When done:

- Open Workbench → **系列设定** / Bible page  
- Check: `creative-plan`, `world`, `characters`, `art-style`, `episode-directory`  
- Edit in the Bible page (keeps headings/tables) or ask in chat to revise  

**Do not** ask to write EP001 until the bible (including episode directory) is ready.

### Step C — Write an episode

Examples:

- 「写第1集」 / 「生成第1集剧本」  
- 「重新生成第3集剧情」 → **script only** (does not render video)

Open Workbench → **文学** / Literary page to read, edit, and **accept** the episode.

### Step D — Cast images

- Ask in chat to generate cast images, **or** open **角色** / Cast page to upload portraits.  
- Accept leads on the Cast page (gate: cast accepted).  
- Optional: put short voice clips in `data/cast/{series}/voices/{角色}.wav` (2–15s) for clearer dialogue binding.

### Step E — Render video

Only when literary + cast gates are ready, say clearly:

- 「出片第1集」 / 「生成第1集视频」 / 「渲染 EP001」

This builds `episode-run.jsonl` and queues ComfyUI. It is **not** the same as「写第1集」.

- Watch progress: Workbench → **生成进度** / Jobs page  
- Outputs: `templates/{series}/output/{EPxxx}/` (per-shot + `master.mp4`)

Changing the video workflow in System config applies to new renders; force re-render if a shot already exists.

---

## 6. Useful chat phrases

| Intent | Example phrases |
|--------|-----------------|
| Develop | 立项；写大纲/世界观/角色/画风/分集目录 |
| Write episode | 写第N集；重新生成第N集剧情 |
| Write + render same turn | 写第N集并出片 / 渲染（only if you say both） |
| Render only | 出片第N集；生成第N集视频 |
| Revise bible | 改大纲…；改分集目录… |
| Cast | 生成角色图；上传定妆 |

---

## 7. Workbench gates (S1 → S2)

| Gate | Meaning |
|------|---------|
| Literary accepted | Episode package accepted on Literary page |
| Cast accepted | Lead portraits accepted on Cast page |
| Audio | `missing` / deferred / ready (voices optional) |
| Ready for S2 | Can build jsonl + Comfy queue |

If S2 is not ready, finish accept steps first; the Agent should not skip gates.

---

## 8. Pages in more detail

### Bible (系列设定)

- Files under `dramas/{series}/`  
- Hand-edit with format preserve, or「填入聊天」to revise via Agent  
- Changing bible affects **next** write; it does not auto-delete old videos

### Literary (文学)

- Per-episode Markdown screenplay  
- Optional **episode first frame** upload (used as Picture 1 for shot 1)  
- Accept before render

### Cast (角色)

- Preview / upload / generate  
- Accept leads for the S1 gate

### Jobs (generation progress)

- **Per episode**: progress is grouped by episode (done / total shots)  
- **Resume per episode**: Cancel and **Resume from breakpoint** independently for each episode  
- **Download master**: when all shots are done, **Download** `master.mp4` (or **Rebuild master** to re-concat)  
- **Shot preview & regenerate**: expand all shots to preview; for a bad shot, enter a note and **Regenerate shot** — the job re-renders that shot then re-concats the master  
- After queueing, watch this page instead of repeating the same chat message

---

## 9. Where files live

| Path | Content |
|------|---------|
| `dramas/{series}/` | Bible + literary sources |
| `data/cast/{series}/` | Portraits + `voices/` |
| `templates/{series}/run/` | `*.episode-run.jsonl`, `*.episode-meta.json` |
| `templates/{series}/output/` | Shot videos, tails, `master.mp4` |
| `projects/{series}/` | Runtime, chat memory, jobs |

---

## 10. Troubleshooting

| Symptom | What to try |
|---------|-------------|
| http://localhost:5173/ blank / API error | Start API on `:8000`; check `VITE_HERMES_API_BASE` |
| Agent says “generating” but nothing happens | Prefer Tool-backed replies; refresh messages / Workbench |
| Rewrite episode also started Comfy | Use「重新生成第N集剧情」only; say「出片」separately |
| Unclear dialogue | Add `voices/*.wav`; prefer `fast` workflow over 4-step LoRA |
| Shot 1 OK, later shots fail | ffmpeg missing — run `python scripts/doctor.py` (venv `imageio-ffmpeg` is enough) |
| Wrong workflow in tmp json | Save System config with series open; force re-render shot |
| Comfy errors | Confirm ComfyUI URL, H3 models, and selected workflow file exist |

---

## 11. Related docs

- [README (install / Quick Start)](../README.md)  
- [Chinese user guide](USER_GUIDE.zh-CN.md)  
- [Development](DEVELOPMENT.md) · [Architecture notes](README.md)
