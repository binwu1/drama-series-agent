# Stage1 Case 矩阵

三位码：`S` 剧本 / `I` 角色图 / `A` 参考音频。`1`=可用，`0`=无，`P`=部分。

## 判定规则

- **有剧本** = 可定位非空文件（小说/大纲/分集 md 均可），不要求已是 `screenplay.md`。
- **有图** = 至少 1 张可映射到命名角色的锚点；未命名进 `unassigned/` → 通常 `partial`。
- **有音频** = 2–15s 相对干净人声；带 BGM 整集轨 → `partial`，不直接当 `ref_voices`。
- `script_kind` ∈ {novel, fragment} 时脚本旗标强制为 `P`。

## 路由表

| Case | 含义 | Stage1 主动作 | Stage2+ 建议 skill |
|------|------|---------------|-------------------|
| S0I0A0 | 只有题材 | 立项问卷 + 空骨架 | 0xsline-short-drama / short-drama-develop |
| S1I0A0 | 有剧本无图无声 | 剧本入库；角色名粗提取 | write → assets → image-prompts |
| S1I1A0 | 剧本+图 | 图入库；声 deferred | assets；可 soft-voice R2V |
| S1I0A1 | 剧本+声 | 声入库；图阻断视觉 | 必须 image-prompts/出图 |
| S1I1A1 | 三件齐 | 三向校验 + cast 草稿 | storyboard / video-prompts / drama_series-h3-r2v |
| S0I1A0 / S0I1A1 | 有图无剧本 | 图建卡；剧本 missing | develop/write；禁止擅自编全剧 |
| S0I0A1 | 仅音频 | 声登记 | 先要剧名+至少一角色名 |
| SP** | 残缺/长文 | 原件 + 不自动 canonical | develop 导入流 |

实现：`drama_series_agent/hermes_intake/case_matrix.py`。
