# Drama Series Agent（短剧系列智能体）

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-MiniMax%20H3%20R2V-orange.svg)](https://github.com/comfyanonymous/ComfyUI)

[English](README.md) · **中文**

> 从一句点子到竖屏短剧成片——  
> **立项 → 写集 → 定妆 → Ref2VA 出片**，一个绑定系列的 Agent 跑通全链路。

<p align="center">
  <img src="docs/assets/showcase-still.jpg" alt="Drama Series Agent 竖屏宣传静帧" width="320" />
</p>

<p align="center"><em>本地 H3 R2V 跑通后的 9:16 静帧。将成片放到 <code>docs/assets/demo.mp4</code> 即可在 README 嵌入动态预览。</em></p>

<!-- 放入 docs/assets/demo.mp4 后取消注释：
<p align="center">
  <video src="docs/assets/demo.mp4" controls width="360" poster="docs/assets/showcase-still.jpg">
    浏览器不支持 video 标签时，可 <a href="docs/assets/demo.mp4">下载演示视频</a>
  </video>
</p>
-->

聊天即产线：系列圣经与分集地图、文学剧本、角色定妆、MiniMax H3 Reference-to-Video 分镜、下一集交接——全部挂在同一个 `series_id` 上。

---

## 为什么做这个？

| 痛点 | 我们提供 |
|------|----------|
| 点子停在备忘录 | [`skills/`](skills/) 立项 / 写集 / H3 接线技能包 |
| 剧本拍不出来 | episode-run JSONL + Picture/Audio 绑定 Ref2VA |
| 只会出单条、接不上集 | chain：上镜尾帧 → 下镜首帧 |
| 工具碎片化 | 统一 API + React 工作台 + CLI 出片 |

---

## 功能亮点

- **系列会话** — 一个对话窗口 ↔ 一个 `series_id`
- **技能包**（与编辑器无关）— 进件 · 立项 · 文学 · H3 R2V，见 [`skills/`](skills/)
- **本机 ComfyUI 出片** — MiniMax H3 Ref2VA 工作流在 [`workflows/selfhost/`](workflows/selfhost/)
- **角色库** — `data/cast/{series}/` 定妆图 + 可选音色参考
- **工作台** — FastAPI + React（`web/`）：聊天、圣经、文学、任务
- **CLI** — `drama-series-render` 无头渲染整集

---

## 流水线

```text
点子 → 立项（圣经）→ 写集（EP）→ 定妆验收
    → 构建 episode-run.jsonl → ComfyUI H3 R2V → master.mp4 → 下一集
```

---

## 快速开始

### 环境要求

- Python **3.10+**
- **ffmpeg**（见下方 [安装 ffmpeg](#安装-ffmpeg)）
- 本机 [ComfyUI](https://github.com/comfyanonymous/ComfyUI)，已加载 MiniMax H3 Ref2VA 模型与节点（真正出片时需要）
- 可选：Node **18+**（React 工作台）
- 可选：OpenAI 兼容 LLM（Agent 对话，如 ModelScope）

### 安装 ffmpeg

每个镜头成片后需要用 ffmpeg **抽尾帧**（接下一镜）并 **拼接** 为 `master.mp4`。  
查找顺序：`FFMPEG_PATH` → 系统 `PATH` → 随依赖安装的 **`imageio-ffmpeg`** 内置二进制。

**推荐安装系统版 ffmpeg**（排错更直观）：

<details>
<summary><strong>Windows</strong></summary>

```powershell
# 方式 A — winget
winget install --id Gyan.FFmpeg -e

# 方式 B — scoop
scoop install ffmpeg

# 方式 C — chocolatey
choco install ffmpeg
```

或从 [gyan.dev ffmpeg builds](https://www.gyan.dev/ffmpeg/builds/) / [BtbN](https://github.com/BtbN/FFmpeg-Builds/releases) 下载解压后：

1. 将 `...\ffmpeg\bin` 加入**用户 PATH**，或  
2. 在 `.env` 中指定：

```env
FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe
```

在**新开**的终端中验证：

```powershell
ffmpeg -version
```

</details>

<details>
<summary><strong>macOS</strong></summary>

```bash
brew install ffmpeg
ffmpeg -version
```

</details>

<details>
<summary><strong>Linux（Debian/Ubuntu）</strong></summary>

```bash
sudo apt update
sudo apt install -y ffmpeg
ffmpeg -version
```

</details>

**无系统 ffmpeg 时的兜底：** `pip install -e .` 已依赖 `imageio-ffmpeg`，会把静态 ffmpeg 装进虚拟环境，足够跑通快速开始。只有需要指定某份构建时才设 `FFMPEG_PATH`。

### 安装本项目

```bash
git clone https://github.com/<your-org>/drama-series-agent.git
cd drama-series-agent

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

python -m pip install -U pip
pip install -e ".[render,dev]"
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
# 编辑 .env → COMFYUI_URL / LLM_* / 可选 FFMPEG_PATH
```

### 验证安装

```bash
python scripts/doctor.py
```

应看到 ffmpeg、skills、comfykit、API 路由、CLI 均为 `[OK]`。  
若 ffmpeg 失败：按上文安装系统版，或确认当前 venv 里已有 `imageio-ffmpeg`。

### 启动 API（含 Web 工作台）

```bash
# Windows — API + Vite 前端
.\start.ps1 -WithWeb

# macOS / Linux
./start.sh --with-web
```

| 入口 | 地址 | 说明 |
|------|------|------|
| **Web 工作台** | **http://localhost:5173/** | Vite 默认端口（`web/`）。聊天、系列圣经、文学、定妆、任务、系统配置。 |
| API 文档 | http://127.0.0.1:8000/docs | 后端 OpenAPI |
| 前端调用的 API 根 | `http://127.0.0.1:8000/api/series` | 可在 `web/.env` 设置 `VITE_HERMES_API_BASE=...` 覆盖 |

两边都起来后，浏览器打开 **http://localhost:5173/**。若页面能开但聊天/配置失败，多半是 **8000** 上的 API 未启动（先起 API，或改 `VITE_HERMES_API_BASE`）。

不用启动脚本时：

```bash
# 终端 1 — API
python scripts/run_api.py --host 127.0.0.1 --port 8000

# 终端 2 — 工作台（http://localhost:5173/）
cd web
npm install
npm run dev
```

### CLI 渲染一集

1. 定妆：`data/cast/{series}/{角色}.png`（可选 `voices/{角色}.wav`）
2. 运行文件：`templates/{series}/run/EP001.episode-run.jsonl` + `EP001.episode-meta.json`
3. ComfyUI 地址：`COMFYUI_URL`（默认 `http://127.0.0.1:8188`）

```bash
drama-series-render \
  --project templates/<series> \
  --episode EP001 \
  --cast-series <series> \
  --context-ir off \
  --comfyui-url http://127.0.0.1:8188
```

输出：`templates/{series}/output/{EP}/master.mp4`（分镜拼接时带短片头裁切）。

---

## 工作流分档

| 工作流 | 用途 |
|--------|------|
| `selfhost/video_minimax_h3_r2v_fast.json` | 默认加速档（20 step + 加速节点） |
| `selfhost/video_minimax_h3_r2v_lora.json` | Lightning LoRA 4-step |
| `selfhost/video_minimax_h3_r2v_turbo.json` | 极速 / 实验档 |
| `selfhost/video_minimax_h3_r2v.json` | 质量档 / fl2va |

在系统配置页或 `config.json` → `comfyui.video.default_workflow` 中选择。

---

## 目录结构

```text
skills/                         # 权威技能目录（开源布局）
src/drama_series_agent/
  agent/  drama/  intake/  api/ # 编排与工具
  adapters/r2v/                 # H3 分集 runner
workflows/selfhost/             # ComfyUI API 图
data/cast/{series}/             # 角色定妆 + 音色
projects/{series}/              # series_runtime、记忆、任务
templates/{series}/             # run/ + output/
web/                            # React 工作台
docs/                           # 架构、契约、宣传素材
```

若需 Cursor 项目技能自动发现，可运行 `scripts/link_cursor_skills.ps1` / `.sh`（链接默认 gitignore）。**只改 `skills/` 下的内容。**

---

## 文档

- [**用户使用手册**](docs/USER_GUIDE.zh-CN.md) · [User Guide (English)](docs/USER_GUIDE.md)
- [开发约定](docs/DEVELOPMENT.md)
- [架构与契约](docs/README.md)
- [技能索引](skills/README.md)
- [宣传素材说明](docs/assets/README.md)

---

## 参与贡献

欢迎 Issue 与 PR。请保持改动聚焦，小步提交并写清「为什么」。

1. Fork 并从 `main` 拉分支  
2. `pip install -e ".[render,dev]"`  
3. 提交 PR：简述变更 + 测试说明  

---

## 许可证

[Apache License 2.0](LICENSE)

`skills/0xsline-short-drama/` 内上游技能若另有许可证声明，以该目录说明为准。
