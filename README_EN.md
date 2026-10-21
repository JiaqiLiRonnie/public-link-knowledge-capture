# Public Link Knowledge Capture

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![OpenAI Compatible](https://img.shields.io/badge/OpenAI-Compatible-green.svg)](https://platform.openai.com)

**[English](README_EN.md)** | **[中文说明](README.md)**

A resilient, agent-centric knowledge capture toolkit for **Codex, autonomous AI agents, and developer workflows**. 

It transforms unstructured public links from rich-media platforms—including **WeChat Articles, Xiaohongshu (RED), Douyin (TikTok China), X (Twitter), Bilibili, and standard web pages**—into self-contained, reproducible, multimodal knowledge packages (`article.md`, `article.json`, `media.json`, and `transcript.md`).

---

## 🌟 Key Highlights

- **Multi-Platform Resilience**: Automatic fallback routing across standard HTTP, headless Playwright with mobile user-agent hydration, and Chrome CLI / DevTools Protocol (CDP).
- **Multimodal Artifacts**: Preserves ordered carousel images for vision-language models without destructive downsampling or heuristic stripping.
- **Audio & Video Pipelines**: Automatically extracts video audio tracks via FFmpeg, normalizes audio to 16 kHz mono WAV, and integrates with speech-to-text models.
- **Native OpenAI & Codex Integration**: Built-in support for OpenAI-compatible APIs (using modern reasoning models like `gpt-6-luna`, `gpt-6.1-sol`, and `gpt-6-astra` for deep distillation, and Whisper for automated transcription).
- **Honest Status Reporting**: Never fabricates or truncates silent errors. Explicitly reports `complete`, `partial` (e.g., shell pages, dynamic paywalls), `blocked`, or `needs_browser`.

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
# 1. Text Analysis & Reasoning Service (OpenAI API / Azure / Compatible)
export PUBLIC_LINK_AI_BASE_URL="https://api.openai.com/v1"
export PUBLIC_LINK_AI_API_KEY="sk-..."
export PUBLIC_LINK_AI_MODEL="gpt-6-luna"      # Or gpt-6.1-sol / gpt-6-astra for deeper analysis

# 2. Audio Transcription Service (OpenAI Whisper or compatible ASR)
export PUBLIC_LINK_ASR_BASE_URL="https://api.openai.com/v1"
export PUBLIC_LINK_ASR_MODEL="whisper-1"       # Or local Qwen-ASR / Whisper endpoints
export PUBLIC_LINK_ASR_API_KEY="sk-..."
```

### Knowledge Extraction Flow

```
                      ┌───────────────────────────────────────┐
                      │          Target Public Link           │
                      └───────────────────┬───────────────────┘
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   │ Fallback Engine (HTTP -> Playwright -> CDP) │
                   └──────────────────────┬──────────────────────┘
                                          │
             ┌────────────────────────────┼────────────────────────────┐
             │                            │                            │
             ▼                            ▼                            ▼
      [Clean Content]             [Image Carousel]             [Audio Track]
      `article.md`                `media/image-*.jpg`          (FFmpeg 16kHz WAV)
             │                            │                            │
             ▼                            ▼                            ▼
  ┌───────────────────────┐    ┌─────────────────────┐      ┌─────────────────────┐
  │ OpenAI Analysis Model │    │ Multimodal Context  │      │ OpenAI Whisper ASR  │
  │ (`gpt-6-luna` / `sol`)│    │ (Passed to Agent)   │      │ (Generates transcript)
  └──────────┬────────────┘    └─────────────────────┘      └──────────┬──────────┘
             │                                                         │
             └────────────────────────────┬────────────────────────────┘
                                          ▼
                      ┌───────────────────────────────────────┐
                      │ Structured Package for Coding Agents  │
                      │ (`article.json`, `analysis.json`)     │
                      └───────────────────────────────────────┘
```

---

## 📂 Output Artifacts

For each captured target, a standardized artifact bundle is preserved in `~/.public-link-knowledge/public-links/`:

| Artifact | Purpose |
| :--- | :--- |
| `article.md` | Normalized markdown containing headings, paragraphs, and metadata. |
| `article.json` | Comprehensive metadata (author, publication time, engagement metrics, original URL). |
| `article.html` | Raw captured DOM snapshot for debugging or deterministic parsing. |
| `media.json` | Manifest of all discovered image, audio, and video URLs with download statuses. |
| `analysis.json` | Structured summary, key points, entity mapping, and tags produced by the LLM. |
| `transcript.md` | Timestamped, high-precision speech-to-text transcript from video/audio streams. |
| `processing.json` | Execution telemetry (fallback route taken, retry counts, latency). |
| `media/` | Downloaded media binaries (images, extracted audio, or video files). |

---

## 🛡️ Anti-Bot & Platform Resilience

- **Mobile UA Emulation**: Dynamic platforms (such as Douyin / RED) collapse full post descriptions or block desktop headless user-agents. The built-in toolkit (`scripts/douyin_tools.py`) leverages mobile viewport and user-agent emulation to extract full descriptions and authentic media streams.
- **Signed URL & Fingerprinting**: Gracefully handles CDN signature requirements, bypassing cookie expirations by utilizing active browser sessions.
- **Safe Network Guardrails**: Only accepts public `http(s)` URLs. Validates DNS resolutions and redirects to prevent SSRF against localhost, link-local, or private subnets.

---

## 🤝 Contributing & License

Contributions, issues, and feature requests are welcome!

This project is open-source under the [MIT License](LICENSE).
