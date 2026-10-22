# Public Link Knowledge Capture

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![OpenAI Compatible](https://img.shields.io/badge/OpenAI-Compatible-green.svg)](https://platform.openai.com)

**[English](README.md)** | **[中文说明](README_zh.md)**

一个专为 **Codex 与自主 AI Coding Agent** 设计的开源公开链接知识捕获与结构化工具库：将全球主流社交媒体、富媒体平台和技术论坛（**X / Twitter、Reddit、YouTube、微信公众号、小红书、抖音、Bilibili、GitHub、Hacker News 以及普通网页**）的非结构化内容，保存为自包含、可复现、面向大模型的多模态知识包（`article.md`、`article.json`、`media.json` 与 `transcript.md`）。

---

## 🌟 核心特性与支持平台

- **全平台支持（全球社媒 + 国内主流生态）**：
  - **全球平台**：**X (Twitter)**（正文展开、多图去重去缩略图、音视频提取）、**Reddit**（`<shreddit-post>` 动态组件渲染、`i.redd.it` 轮播原图）、**YouTube**（音频流解析与字幕/转录）、**GitHub / Hacker News**（结构化技术讨论与代码仓）、普通 Web / 技术博客。
  - **国内多模态生态**：**小红书**（图文笔记轮播原图与顺序保真）、**抖音**（移动 UA 仿真绕过风控、完整长文案提取、口播音频转录）、**微信公众号与视频号预览**、**Bilibili**。
- **韧性降级架构**：自动在“纯 Python HTTP → Playwright 无头浏览器（移动端 UA 仿真）→ 原生 Chrome CLI / DevTools 协议 (CDP)”之间智能分流降级。
- **多模态上下文保真**：严格保留图文帖的原始图片与阅读顺序，不进行破坏性抽样；自动通过 FFmpeg 将视频音频提取并归一化为 16kHz 单声道 WAV。
- **原生 OpenAI / Codex 深度集成**：开箱即用支持 OpenAI 最新一代推理与总结模型（如 `gpt-6-luna`、`gpt-6.1-sol`、`gpt-6-astra`），并原生集成 OpenAI Whisper 自动语音转写。
- **真实状态报告**：绝不隐瞒抓取阻断或截断，如实返回 `complete`、`partial`（如短壳页/登录墙）、`blocked` 或 `needs_browser`。

---

## 🚀 快速上手

### 安装

必需依赖（Python 3.10+ 与 BeautifulSoup）：

```bash
python3 -m pip install -r requirements.txt
```

可选依赖（动态浏览器渲染、媒体提取与 ASR 支持）：

```bash
python3 -m pip install yt-dlp playwright websockets brotli
playwright install chromium
```

*(请确保系统环境变量 `$PATH` 中已安装 `ffmpeg` 以支持音频提取)*

### 常用命令

捕获任意公开链接：

```bash
python3 scripts/capture_public_link.py "https://example.com/article"
```

常见参数：

```bash
# 仅抓取并保存本地知识包，不触发 AI 接口分析
python3 scripts/capture_public_link.py --no-analyze <URL>

# 下载图文帖所有原图（供后续多模态视觉模型消费）
python3 scripts/capture_public_link.py --download-images <URL>

# 仅下载/提取视频音频轨道
python3 scripts/capture_public_link.py --download-audio <URL>

# 强制提取音频并调用 ASR 生成转写文本 (transcript.md)
python3 scripts/capture_public_link.py --transcribe-audio <URL>

# 保存视频完整二进制文件
python3 scripts/capture_public_link.py --download-video <URL>
```

---

## 🤖 AI 与 OpenAI 生态集成

基础的网页捕获与 DOM 提取完全在本地离线运行。若需开启结构化要点提取、实体关系梳理或音频转写，只需配置 OpenAI 兼容环境变量：

```bash
# 1. 文本分析与总结服务 (OpenAI API / Responses API 架构)
export PUBLIC_LINK_AI_BASE_URL="https://api.openai.com/v1"
export PUBLIC_LINK_AI_API_KEY="sk-..."
export PUBLIC_LINK_AI_MODEL="gpt-6-luna"      # 推荐高性价比模型，或用 gpt-6.1-sol 进行深度提炼

# 2. 语音转写服务 (OpenAI Whisper 或本地兼容端点)
export PUBLIC_LINK_ASR_BASE_URL="https://api.openai.com/v1"
export PUBLIC_LINK_ASR_MODEL="whisper-1"
export PUBLIC_LINK_ASR_API_KEY="sk-..."
```

---

## 📂 输出产物结构

每个捕获的目标链接都会在 `~/.public-link-knowledge/public-links/` 下生成一套标准化的自包含产物包：

| 产物文件 | 说明 |
| :--- | :--- |
| `article.md` | 干净规范的 Markdown 正文，含层级标题与元数据 |
| `article.json` | 完整结构化元数据（作者、发布时间、互动量、原始 URL 等） |
| `article.html` | 原始页面 DOM 镜像快照（便于调试与确定性重放） |
| `media.json` | 发现的所有图片、音频、视频链接及本地下载状态清单 |
| `analysis.json` | 由 LLM 派生生成的结构化摘要、要点清单、实体与分类标签 |
| `transcript.md` | 从音视频流中提取并由 Whisper 转写的逐句文本 |
| `processing.json` | 运行遥测数据（降级路径、重试次数、耗时） |
| `media/` | 本地媒体目录（原图、音频切片或视频本体） |

---

## 🛡️ 反爬对抗与平台风控应对

- **移动端 UA 真实仿真**：抖音、小红书等平台在桌面 UA 下常拦截正文或强制弹窗。内置的 `scripts/douyin_tools.py` 采用移动端视口与 iPhone UA，完整恢复折叠文案与播放流；
- **全球社媒格式对齐**：针对 X (Twitter) 图片自动过滤各种缩略图变体并锁定原图；针对 Reddit 自动等待 `<shreddit-post>` 客户端水合完成；
- **严格的安全边界**：仅允许公开合法的 `http(s)` 域名，校验 DNS 与重定向目的地，严禁内网、回环或私有 IP（防范 SSRF）。

---

## 📥 分享收件箱（可选配套）

抓到的链接不该散落在聊天记录里。`tools/inbox/` 把三个来源（知识包索引 + 手工补录 + 待办台账）合成一个可浏览看板，输出 **CSV / XLSX / HTML**——网页版支持搜索、筛选、已读标记、深浅色切换。

```bash
python3 tools/inbox/build_inbox.py          # 生成 inbox.csv / inbox.xlsx / inbox.html
python3 -m http.server 8787 --bind 127.0.0.1 --directory ~/.public-link-knowledge/inbox
```

完整说明见 [`tools/inbox/README.md`](tools/inbox/README.md)。

**为什么值得装**：Agent 每次抓完只需往 `inbox_extra.jsonl` 追加一行 JSON，用户就能在一个页面里扫完，而不是在聊天记录里翻链接。本地数据（`inbox_extra.jsonl`）已加入 `.gitignore`，不会误提交。

---

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
