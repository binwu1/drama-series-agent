# Agent skills (drama-series-agent)

Canonical skill pack for this repository (editor-agnostic). Runtime resolves via
`drama_series_agent.utils.skills_paths`.

| Skill folder | Role | Code wiring |
|--------------|------|-------------|
| `drama-intake` | Stage1 进件 | `drama_series_agent.intake` · `scripts/hermes_drama_intake.py` |
| `drama-series-develop` | 立项/大纲/世界观/角色/画风 | `drama.series_bible` · `run_series_develop` · `develop_skill` |
| `0xsline-short-drama` | 文学写集 | `drama.literary_skill` · `run_literary_generate` |
| `drama-series-h3-r2v-prompts` | H3 Ref2VA 接线 | `drama.build_worker` · `adapters.r2v` · `scripts/h3_r2v_episode_run.py` |

`drama-series-develop` 方法参考个人套件 `short-drama-develop`，产物适配本仓 `dramas/{slug}/`.

Legacy Cursor path `.cursor/skills/` is a pointer only; do not edit skills there.
