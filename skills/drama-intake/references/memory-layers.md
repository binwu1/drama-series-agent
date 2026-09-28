# Stage1 分层记忆

对齐 Hermes：`USER.md` / `MEMORY.md` 会话快照 + 项目文件真相。

```text
L0  USER.md / MEMORY.md     跨会话偏好与习惯（冻结进 system prompt）
L1  projects/{slug}/        权威项目真相（FS）
L2  会话 todo / 对话        工作记忆
L3  tool 原始输出           可压缩丢弃
```

## L1 必有文件

| 文件 | 内容 |
|------|------|
| `project.json` | slug、authority、mounts |
| `intake_manifest.json` | S/I/A 状态 + hash |
| `handoff_stage2.json` | case、suggested_skills、forbid |
| `gap_report.md` | 给人看的缺口 |
| `输入/` | 原件只追加 |
| `memory/PROJECT.md` | 已验证稳定事实 |
| `short-drama.json` | 套件契约钩子 |
| `.short-drama/state.json` | stage / ready_for_stage2 |

## 写入规则

1. 文件系统是唯一权威。
2. `输入/` 不可变；规范化剧本是副本，升 canonical 在 Stage2+ 且需用户接受。
3. 每回合 prompt 只 prefetch：manifest 摘要 + gaps，不灌全剧本文。
4. 跨集连续性（episode-tails、facing-bind）**不属于** Stage1。

## L0 模板位置

见仓库 `hermes/memory/USER.template.md` 与 `MEMORY.template.md`（可复制到 `~/.hermes/`）。
