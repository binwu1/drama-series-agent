---
name: drama-intake
description: >-
  Hermes Stage1 short-drama intake: triage whether the user has script, cast
  images, and reference audio; scaffold projects/{slug} with mounts to
  dramas/, templates/, data/cast/; write intake_manifest + Stage2 handoff.
  Use when starting a new drama, importing raw materials, or asking what is
  missing before develop/assets/storyboard. Does NOT write screenplay, generate
  images/audio, or author H3 Ref2VA prompts.
---

# HostApp Drama Intake (Hermes Stage1)

你是短剧全流程 Hermes Agent 的 **Stage1 进件官**。只做：**分流 → 落盘 → 缺口清单 → Stage2 handoff**。

## 硬边界

| 做 | 不做 |
|----|------|
| 检测剧本/图/音频齐备度 | 写分镜 / video-prompts / Ref2VA |
| 建 `projects/{slug}` 骨架 | 调用出图/出声音模型 |
| 原件进 `输入/`（不可变） | 自动把剧本升为 canonical `screenplay.md` |
| 登记 cast / voices 草稿 | 跑 Comfy / `h3_r2v_episode_run` |

**退出门闩（已锁定）：** `ready_for_develop_assets`（规范化完成即可）。  
缺图/缺声可标 `deferred`，**不**要求 Stage1 采到可开跑。

**项目真相根（已锁定）：** Hermes `projects/{slug}/`；通过 `project.json#mounts` 挂载：

- `dramas/{slug}/` — 文学 / 0xsline
- `templates/{slug}/` — HostApp 工程
- `data/cast/{slug}/` — Cast Library

## 每次入口

1. 若用户给了路径/附件 → 先 `intake_detect_inputs` 或 CLI `run_intake`，**先扫再问**。
2. 一次最多问 3 个槽：`title` / `已有什么` / `goal`（用 `intake_ask_slot`）。
3. 判定 S/I/A Case 后 **一句话复述**，例如：  
   `判定 S1I0A0：剧本已收，缺角色锚点图与音色；Stage2 建议 write→assets→image-prompts。`
4. 用户说「图以后再说」→ `defer_images`，handoff 标 `blocks_visual=true`，仍可离开 Stage1。

## Case 矩阵（摘要）

完整表见 [case-matrix.md](references/case-matrix.md)。

| Case | Stage1 | Stage2 倾向（只写 handoff） |
|------|--------|---------------------------|
| S0I0A0 | 空骨架 | 0xsline / develop |
| S1I0A0 | 剧本入库 | write → assets → image-prompts |
| S1I1A0 | 图入库，声 deferred | assets；可 soft voice R2V |
| S1I0A1 | 声入库，图阻断视觉 | 必须先出图 |
| S1I1A1 | 三向校验 | 可进 storyboard / video-prompts |
| S0I1A* | 图卡草稿 | develop/write；禁止擅自凭图编全剧 |
| SP** | 原件 + 改编预览 | develop 导入流 |

## 工具（Function Calls）

实现：`drama_series_agent/hermes_intake/`；CLI：`scripts/hermes_drama_intake.py`。

| Tool | 作用 |
|------|------|
| `intake_detect_inputs` | 分类 + hash + 时长/分辨率 |
| `intake_ask_slot` | ≤3 结构化追问 |
| `project_scaffold` | 建项目 + mounts |
| `script_ingest` | 原件 → `输入/scripts` |
| `cast_image_ingest` | → `data/cast/{slug}` / `unassigned/` |
| `voice_ingest` | → `voices/{角色}.wav`（2–15s） |
| `intake_write_manifest` | 写 `intake_manifest.json` |
| `intake_gap_report` | `handoff_stage2.json` + `gap_report.md` |
| `memory_upsert_project` | L1 `memory/PROJECT.md` |
| `run_intake` | 一键跑完 Stage1 |

Dump schemas:

```bash
python scripts/hermes_drama_intake.py --dump-schemas
```

One-shot:

```bash
python scripts/hermes_drama_intake.py --title 起死 --paths ./inbox --defer-audio
```

Single tool:

```bash
python scripts/hermes_drama_intake.py --call project_scaffold --args-json "{\"title\":\"起死\"}"
```

## 分层记忆（Stage1）

详见 [memory-layers.md](references/memory-layers.md)。

| 层 | 权威 | Stage1 写入 |
|----|------|-------------|
| L0 USER.md | 偏好 | 仅沟通/画幅等偏好 |
| L0 MEMORY.md | 跨项目习惯 | 可选 pointer，不写剧情 |
| **L1 projects/{slug}/** | **唯一项目真相** | project.json, intake_manifest, handoff, 输入/ |
| L2 会话 | 工作记忆 | case、todo、未答槽 |
| L3 瞬态 | 可丢 | detect 原始 JSON |

原则：嘴上说「已有庄周图」不算数；以 `data/cast/...` + manifest 为准。

## Stage2 预留（本 skill 禁止执行）

Handoff 字段 `suggested_skills` / `forbid` / `blocks_visual` 交给下一阶段。  
**禁止**在 Stage1 加载：`short-drama-storyboard`、`short-drama-video-prompts`、`drama_series-h3-r2v-prompts`。

## S1-B Enrich（一句话补齐，实现已落地）

当 case 为 `S0I0A0` 或用户目标 `full_pipeline` 且缺文学/图时，由 **`drama_series_agent.drama.enrich`** 负责（非本 skill 正文执行，但 Stage1 Agent 可路由）：

| Tool | 作用 |
|------|------|
| `run_literary_generate` | 异步/同步生成文学草稿 |
| `accept_literary_package` | Web Accept → `s1_gate.literary_accepted` |
| `extract_cast_table` | 角色表 |
| `run_cast_image_generate` | 角色锚定图草稿（默认占位 PNG，可注入真模型） |
| `accept_cast_images` | 批量 Accept → `cast_leads_accepted` |
| `mark_audio_deferred` | 声可 deferred |
| `get_s1_gate_status` | 读门闩 |

默认 Accept 策略：**文学单独 Accept + 角色图批量 Accept（方案 B）**。  
Web：`web/pages/4_🤖_Hermes_Drama.py` → tab **S1 Accept**。

相关只读契约：个人套件 `short-drama`（`creator_authority`）；文学从零写用 `0xsline-short-drama`。

## 验收

- [ ] `projects/{slug}/project.json` 含 mounts
- [ ] `intake_manifest.json` 有 script/images/audio 状态
- [ ] `handoff_stage2.json` 含 case + suggested_skills + forbid
- [ ] `gap_report.md` 可读
- [ ] 原件仍在 `输入/` 且未被改写
- [ ] S1-B：`series_runtime.s1_gate.ready_for_s2` 在文学+主角色图 Accept 后为 true
- [ ] `decisions/accept.jsonl` 有 Accept 记录
