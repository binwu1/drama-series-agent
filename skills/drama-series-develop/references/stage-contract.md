# 开发阶段契约（Hermes / drama-series-agent）

自包含契约：不依赖 short-drama 套件校验器。

## 运行时预检

1. 确认项目存在：`projects/{slug}/project.json` 与 mounts（`dramas_dir` 等）。
2. 调用 `get_series_bible_status` 查看缺失文件。
3. 用 `run_series_develop` 或 `save_series_bible_doc` 写入；禁止只在对话里口述「已完成设定」。
4. 创作者接受前，不调用 `run_literary_generate`（除非用户明确 force）。

## 所有权

- **拥有**：`creative-plan.md` / `world.md` / `characters.md` / `art-style.md` / `episode-directory.md` / `develop-brief.md`
- **不拥有**：`episodes/ep*.md`、cast 图、jsonl、Comfy 任务
- **交接**：圣经确认后 → 文学写集；角色造型确认后 → 出图

## 规则分级（摘自 short-drama-develop）

- `structural_invariant`：文件是否存在、引用是否可解析
- `reviewed_invariant`：升级是否改状态、承诺是否兑现（需人审）
- `craft_default`：戏剧承诺五问、冲突引擎回路（可说明理由覆盖）
- `taste_option`：题材、钩子、结局气质

## 制作形态

画风写入 `art-style.md`，回答：叙事职责、运动预算、未决试验。不在此阶段写供应商字段或分镜。
