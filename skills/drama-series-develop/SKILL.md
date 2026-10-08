---
name: drama-series-develop
description: >-
  Hermes 系列立项与开发：把点子/梗概落成可确认的故事大纲、世界观、主要角色、画风与分集目录。
  用户说「立项」「写大纲」「定世界观/角色/画风」「做系列设定」「先别写第一集」「导入想法做短剧开发」时使用。
  不写单集剧本场次对白；写集交给 0xsline-short-drama / run_literary_generate。
  运行时由 Agent 工具 run_series_develop / save_series_bible_doc 落盘。
---

# 短剧系列开发（drama-series-agent）

参考个人套件 `$short-drama-develop` 的方法，适配本仓 Hermes 布局与工具。

目标：把创作者意图变成**可确认、可交接**的系列圣经，而不是直接开写 ep001。

## 硬边界

| 做 | 不做 |
|----|------|
| 大纲 / 世界观 / 主角色 / 画风 / 分集目录 | 单集场次、对白、△ 画面 |
| 落盘 `dramas/{slug}/*.md` | 出图、分镜、H3 Ref2VA |
| 请创作者确认后再进入写集 | 未经确认擅自 `run_literary_generate` |

下游：文学 → `$0xsline-short-drama`；进件 → `$drama-intake`；出片接线 → `$drama-series-h3-r2v-prompts`。

## Agent 工具（必须用工具落盘，不要只聊天）

| Tool | 作用 |
|------|------|
| `get_series_bible_status` | 查圣经是否齐 |
| `run_series_develop` | 根据 brief 一键生成五份开发文件 |
| `save_series_bible_doc` | 修订单文件（`creative-plan.md` / `world.md` / `characters.md` / `art-style.md` / `episode-directory.md`） |

实现：`drama_series_agent.drama.series_bible`。

## 产物路径（L1 文学挂载）

```text
dramas/{slug}/
├── develop-brief.md          # 用户原文需求存档
├── creative-plan.md          # 故事大纲 / 创作方案
├── world.md                  # 世界观背景
├── characters.md             # 主要人物
├── art-style.md              # 画风 / 视觉方向（非分镜）
├── episode-directory.md      # 分集一句话目录
├── .drama-state.json
└── episodes/                 # 本技能不写入此处
```

模板见 [assets/](assets/)。方法见 [references/story-craft.md](references/story-craft.md)。

## 每次执行

1. **读状态**：`get_series_bible_status`；已有文件则修订而非盲目覆盖。
2. **锁定契约**：哪些事实不可改（如「孙悟空取经后穿越现代」）、哪些可探索、画风/尺度边界。
3. **写戏剧承诺**（进 `creative-plan.md`）：主体 / 追求 / 昂贵阻力 / 独特矛盾 / 反复回报 / 终止条件。  
   工作陈述自检见 story-craft；不要用题材标签代替冲突引擎。
4. **世界观**：规则与代价边界（能力限制、现代社会摩擦），禁止百科堆砌。
5. **角色**：3–8 人；目标、筹码、盲区、关系压力；穿越/重生等为**前提装置**，必须写边界与代价。
6. **画风**：竖屏气质、色调、人物造型锚点关键词；不写镜头表。可投影到后续 `visual_direction` 候选，但本技能不改 creator authority。
7. **分集目录**：必须先读（或同次生成）`creative-plan.md` 的集数与三阶段大纲，写满全部集数（如 24 集则 EP001–EP024）；每集进入压力→追求/阻力→出去问题；禁止只写 8–12 集交差。细则见 [episode-design.md](references/episode-design.md)。
8. **交接**：列出写入路径，请创作者确认；确认前禁止写集。

## 入口判断

| 用户说法 | 动作 |
|----------|------|
| 大纲/世界观/角色/画风/立项/设定 | `run_series_develop` |
| 只改角色表 / 只改画风 | `save_series_bible_doc` |
| 明确「写第 N 集」且圣经已齐 | 才可 `run_literary_generate` |
| 已有完整剧本要改 | 不虚构开发包；转文学修订工具 |

## 验收

- [ ] 四份核心文件非空（≥约 80 字实质内容）
- [ ] 无 ep001 场次对白混入开发文件
- [ ] 戏剧承诺可被一句话复述，且含阻力与代价
- [ ] 画风可指导后续角色锚点图，但不含分镜
- [ ] 已请用户确认
