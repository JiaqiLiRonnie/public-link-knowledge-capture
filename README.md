# Public Link Knowledge Capture

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![OpenAI Compatible](https://img.shields.io/badge/OpenAI-Compatible-green.svg)](https://platform.openai.com)

**[English](README.md)** | **[中文说明](README_zh.md)**

A resilient, multimodal knowledge capture and structured distillation pipeline built for **Codex, autonomous AI coding agents, and developer workflows**.

It transforms unstructured public URLs across global social networks, developer hubs, and rich-media platforms—including **X (Twitter), Reddit, YouTube, GitHub, Hacker News, WeChat, Xiaohongshu (RED), Douyin (TikTok China), Bilibili, and standard web pages**—into self-contained, reproducible, multimodal knowledge packages (`article.md`, `article.json`, `media.json`, and `transcript.md`).

---

## 🌟 Key Highlights & Supported Platforms

### Global Social Media & Developer Hubs
- **X (Twitter)**: Full tweet body extraction, thread unfolding, carousel image deduplication (eliminating low-res thumbnail variants like `&name=small` in favor of high-res originals), and audio extraction.
- **Reddit**: Deep post parsing with client-side hydration (handling `<shreddit-post>` / `<shreddit-comment>` dynamic elements) and gallery image extraction (`i.redd.it` / `preview.redd.it`).
- **YouTube**: Direct audio stream acquisition via `yt-dlp` and automated Whisper speech-to-text pipeline.
- **GitHub & Hacker News**: Clean extraction of technical discussions, issues, READMEs, and developer threads without clutter.
- **Standard Web & Tech Blogs**: Robust readability engine stripping navigation bars, sidebars, cookie banners, and paywall shells.

### Regional & Multimodal Platforms
- **Xiaohongshu (RED)**: Complete image carousel retention in original order; signed video/audio stream capture.
- **Douyin (TikTok China)**: Mobile UA emulation bypassing Argus/anti-crawler blocks; uncollapsed full caption extraction; FFmpeg-normalized audio transcription.
- **WeChat Official Accounts & Channels**: Authentic article rendering; structured publication metadata.
- **Bilibili**: Clean article/video metadata with optional audio extraction.

### Core Architecture Strengths
- **Resilient Fallback Pipeline**: Automatic cascading across standard HTTP → Headless Playwright (with mobile user-agent hydration) → Chrome CLI / DevTools Protocol (CDP).
- **Multimodal Context Preservation**: Preserves ordered carousel images for vision-language models without destructive downsampling.
- **Audio & Video Pipelines**: Automatically extracts video audio tracks via FFmpeg, normalizes audio to 16 kHz mono WAV, and feeds into automated speech recognition.
- **Native OpenAI & Codex Integration**: Built-in support for OpenAI-compatible APIs (using modern reasoning models like `gpt-6-luna`, `gpt-6.1-sol`, and `gpt-6-astra` for deep distillation, and Whisper for automated transcription).
- **Honest Telemetry**: Explicitly reports `complete`, `partial` (e.g., shell pages, dynamic paywalls), `blocked`, or `needs_browser`.

---

## 🚀 Quick Start

### Installation

Requires Python 3.10+ and BeautifulSoup:

```bash
python3 -m pip install -r requirements.txt
```

Optional dependencies for dynamic browser fallback, media extraction, and ASR:

```bash
# Install Playwright and optional media toolchains
python3 -m pip install yt-dlp playwright websockets brotli
playwright install chromium
```

*(Ensure `ffmpeg` is installed and available on your system `$PATH` for audio extraction.)*

### Basic Usage

Capture an article or public link:

```bash
python3 scripts/capture_public_link.py "https://example.com/article"
```

Common options:

```bash
# Capture and structure locally without triggering AI analysis
python3 scripts/capture_public_link.py --no-analyze <URL>

# Download all referenced carousel images (for downstream multimodal tasks)
python3 scripts/capture_public_link.py --download-images <URL>

# Extract/download audio track from video content
python3 scripts/capture_public_link.py --download-audio <URL>

# Force audio extraction + automated speech transcription
python3 scripts/capture_public_link.py --transcribe-audio <URL>

# Download the complete video binary
python3 scripts/capture_public_link.py --download-video <URL>
```

---

## 🤖 AI & OpenAI Integration

The core capture and DOM normalization operate completely locally. To enable derived capabilities—such as automated executive summaries, structured entity extraction, and audio transcription—configure OpenAI-compatible endpoints:

```bash
# 1. Text Analysis & Reasoning Service (OpenAI API / Responses API architecture)
export PUBLIC_LINK_AI_BASE_URL="https://api.openai.com/v1"
export PUBLIC_LINK_AI_API_KEY="sk-..."
export PUBLIC_LINK_AI_MODEL="gpt-6-luna"      # Fast distillation; or gpt-6.1-sol / gpt-6-astra for deep analysis

# 2. Audio Transcription Service (OpenAI Whisper or compatible ASR)
export PUBLIC_LINK_ASR_BASE_URL="https://api.openai.com/v1"
export PUBLIC_LINK_ASR_MODEL="whisper-1"
export PUBLIC_LINK_ASR_API_KEY="sk-..."
```

### Knowledge Extraction Flow

```
                      ┌────────────────────────────────────────────────────────┐
                      │ Target Public Link (X, Reddit, Douyin, YouTube, Web)   │
                      └───────────────────────────┬────────────────────────────┘
                                                  │
                   ┌──────────────────────────────┴──────────────────────────────┐
                   │ Fallback Engine (HTTP -> Playwright Mobile -> Chrome CDP)  │
                   └──────────────────────────────┬──────────────────────────────┘
                                                  │
             ┌────────────────────────────────────┼────────────────────────────────────┐
             │                                    │                                    │
             ▼                                    ▼                                    ▼
      [Clean Content]                     [Image Carousel]                     [Audio Track]
      `article.md`                        `media/image-*.jpg`                  (FFmpeg 16kHz WAV)
             │                                    │                                    │
             ▼                                    ▼                                    ▼
  ┌───────────────────────┐            ┌─────────────────────┐              ┌─────────────────────┐
  │ OpenAI Analysis Model │            │ Multimodal Context  │              │ OpenAI Whisper ASR  │
  │ (`gpt-6-luna` / `sol`)│            │ (Passed to Agent)   │              │ (Generates transcript)
  └──────────┬────────────┘            └─────────────────────┘              └──────────┬──────────┘
             │                                                                         │
             └────────────────────────────────────┬────────────────────────────────────┘
                                                  ▼
                              ┌───────────────────────────────────────┐
                              │ Structured Package for Coding Agents  │
                              │ (`article.json`, `analysis.json`)     │
                              └───────────────────────────────────────┘
```

---

## 📂 Standardized Output Artifacts

For each captured target, a standardized artifact bundle is preserved under `~/.public-link-knowledge/public-links/`:

| Artifact | Purpose |
| :--- | :--- |
| `article.md` | Clean markdown containing hierarchical headings, body text, and metadata. |
| `article.json` | Comprehensive metadata (author, publication time, engagement metrics, original URL). |
| `article.html` | Raw captured DOM snapshot for debugging or deterministic parsing. |
| `media.json` | Manifest of all discovered image, audio, and video URLs with download statuses. |
| `analysis.json` | Structured summary, key points, entity mapping, and tags produced by the LLM. |
| `transcript.md` | Timestamped, high-precision speech-to-text transcript from video/audio streams. |
| `processing.json` | Execution telemetry (fallback route taken, retry counts, latency). |
| `media/` | Downloaded media binaries (images, extracted audio, or video files). |

---

## 🛡️ Anti-Bot & Platform Resilience

- **Mobile Viewport Emulation**: Dynamic platforms (e.g., Douyin, RED) collapse long descriptions or block desktop headless user-agents. The toolkit (`scripts/douyin_tools.py`) leverages mobile viewport and iPhone UA emulation to extract uncollapsed descriptions and authentic media streams.
- **Client-Side Hydration**: Awaits JavaScript hydration for client-rendered frameworks (like Reddit's custom web components).
- **Safe Network Guardrails**: Only accepts public `http(s)` URLs. Validates DNS resolutions and redirects to prevent SSRF against localhost, link-local, or private subnets.
- **Proxy & Forced Render**: `--proxy http://host:port` (or `PUBLIC_LINK_PROXY`) routes both the HTTP fetch and Playwright through a proxy, so a page that fails with a bare `URLError` outside the proxy region can still be captured; `--browser` forces a render for JavaScript-only pages that only return a navigation shell.
- **Honest Status**: Login walls and bot challenges (e.g. "Prove your humanity") are reported as `blocked`, and a short shell page as `partial` — never as a complete article. `index.jsonl` keeps one row per URL and upgrades it in place when a later capture is stronger, so a page that failed once does not stay failed forever.
- **PDF Links**: A direct `application/pdf` URL is read by downloading it and extracting text with PyMuPDF, falling back to poppler `pdftotext`.

---

## 📄 Local Documents (optional companion)

Inbox writes require `--agent` (or `PUBLIC_LINK_AGENT`); document ingestion forwards it to the inbox. Use `--channel test` for agent-generated test captures.

`tools/ingest_doc.py` archives a document the user hands over directly (docx / pdf / pptx / xlsx / md): the original file is copied untouched into `document/<hash>-<slug>/original.<ext>`, its text is converted to `article.md` (pandoc, PyMuPDF/`pdftotext`, or openpyxl), a `meta.json` and `index.jsonl` row are written, and the entry is added to the share inbox when `tools/inbox/inbox_add.py` exists.

```bash
python3 tools/ingest_doc.py ~/Downloads/report.docx --title "季度报告" --author someone --agent codex --channel manual
```

---

## 📥 Share Inbox (optional companion)

Captured links shouldn't scatter across chat logs. `tools/inbox/` builds a browsable dashboard from three sources (knowledge-package index + manual entries + pending queue) and emits **CSV / XLSX / HTML** — the web view supports search, filters, read-marks and light/dark themes.

```bash
python3 tools/inbox/build_inbox.py          # writes inbox.csv / inbox.xlsx / inbox.html
python3 -m http.server 8787 --bind 127.0.0.1 --directory ~/.public-link-knowledge/inbox
```

Full guide: [`tools/inbox/README.md`](tools/inbox/README.md).

**Why it matters**: after each capture an agent appends one JSON line to `inbox_extra.jsonl`; the user then scans one page instead of scrolling a chat. Local-only data (`inbox_extra.jsonl`) is git-ignored.

---

## 🤝 Contributing & License

Contributions, issues, and feature requests are welcome!

This project is open-source under the [MIT License](LICENSE).
