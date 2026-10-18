---
name: public-link-knowledge-capture
description: Capture and understand public URLs from WeChat, Xiaohongshu, Douyin, X, Bilibili, and ordinary webpages. Use automatically when a user sends a public link and expects it to be read, summarized, saved, compared, or used as context, without requiring the user to name this skill.
---

# Public Link Knowledge Capture

## Quick start

Run the bundled script for each public URL:

```bash
python3 <skill-dir>/scripts/capture_public_link.py "https://..."
```

Replace `<skill-dir>` with the installed skill directory. The script writes a portable package under `~/.public-link-knowledge/public-links/<platform>/` by default and prints JSON containing the current-conversation context, source URL, status, summary (when available), and local paths.

## Default workflow

1. Treat an explicit public `http(s)` URL as a request to read it, even when the user does not mention this skill.
2. Capture HTML and structured metadata, extract readable text, and save `article.html`, `article.md`, `article.json`, `media.json`, and `processing.json`.
3. Unless the user asks for capture-only, send only the public extracted text and metadata to the optional OpenAI-compatible analysis service configured by `PUBLIC_LINK_AI_BASE_URL` and `PUBLIC_LINK_AI_API_KEY`. The model is configurable with `PUBLIC_LINK_AI_MODEL`; the derived result is saved as `analysis.json`; never send local files or secrets.
4. For a supported playable video, the normal capture command automatically downloads/extracts its audio and runs the configured Qwen-compatible ASR when `PUBLIC_LINK_ASR_BASE_URL` is set. Direct media and browser capture are tried first; Bilibili and X can use the optional `yt-dlp` command-line fallback when no direct stream is exposed. Use `--no-transcribe-audio` for metadata/media-only capture, or `--transcribe-audio` to force an ASR attempt even when the page has no detected media. The ASR path normalizes audio to mono 16 kHz WAV with FFmpeg, calls the endpoint, and saves `transcript.md`; a successful transcript upgrades the video capture to complete.
5. Return the script's JSON to the conversation: title, author, platform, capture/analysis status, concise summary or excerpt, citations, package paths, any `audio_files`/`video_files`, and `transcript_file`/`transcription` when produced. This is the bridge that makes the saved knowledge immediately usable as context instead of merely reporting “saved”.
6. Be explicit when a platform is `partial`, `blocked`, or when analysis is unavailable/failed. Never present metadata or a short shell page as complete article content. `media.json` is a URL manifest by default; retained video binaries still require `--download-video`, while automatic video audio is retained because it feeds the transcript.

## Browser fallback priority

The bundled script keeps the cheapest path first and starts a browser only when a supported dynamic post returns a JavaScript challenge or an unusable short shell:

1. Plain Python HTTP (`urllib`) and the normal HTML/metadata parser.
2. Python Playwright with a headless Chromium-compatible browser, when the `playwright` package and a browser runtime are available.
3. Native Chrome/Chromium CLI through a local DevTools Protocol port, without requiring Playwright. If the optional `websockets` package is unavailable, the script makes a final `--dump-dom` attempt.
4. `needs_browser` with a diagnostic error when no browser route can recover reliable content.

The browser path executes the page's JavaScript, retains its temporary browser cookies, waits for hydration, and parses the resulting DOM/RSC data. It does not manually recreate Douyin's rotating `a_bogus`, `verifyFp`, or `__ac_signature` values. Set `PUBLIC_LINK_BROWSER_EXECUTABLE` to select a specific Chrome/Chromium binary; `PUBLIC_LINK_BROWSER_CLI_TIMEOUT` and `PUBLIC_LINK_BROWSER_VIRTUAL_TIME` tune the CLI fallback when needed. A fresh, unauthenticated browser context is used for public pages.

The fallback is currently enabled for Douyin post URLs (`/note/<id>` and `/video/<id>`), XHS video/note shells without an HTTP media URL, Bilibili video shells that are blocked or too short to parse, and WeChat Channels public previews (`weixin.qq.com/sph/<id>`). X and Bilibili text pages normally stay on the HTTP path; X video posts are reported as `partial` when only a video thumbnail is exposed. Platform homepages remain `partial`. `processing.json` records `capture_method` and `capture_attempts` so a browser-assisted capture is auditable.

For a Douyin or Xiaohongshu video, the normal capture command automatically attempts audio extraction and transcription when ASR is configured. Add `--download-audio` when the user only wants the audio, `--no-transcribe-audio` for a fast metadata/media-only run, or `--transcribe-audio` to force transcription. Douyin uses the Playwright network path to recognize its `media-audio-…` MP4/AAC stream, retry the signed URL without the browser's initial partial `Range` request, and save the first complete stream under `media/audio-001.*`. Xiaohongshu commonly exposes a signed MP4 directly in HTML; the script downloads it temporarily and uses FFmpeg to extract the first audio track. Bilibili and X use `yt-dlp` as an optional command-line fallback when their page exposes no direct media URL; the original public share URL, including any required query parameters, is passed through unchanged. The ASR step normalizes that audio and calls the endpoint configured by `PUBLIC_LINK_ASR_BASE_URL` with `PUBLIC_LINK_ASR_MODEL` (default `Qwen3-ASR-1.7B`). No local ASR endpoint is assumed when the variable is absent. Use `--download-video` when the video binary itself is requested. The Chrome CLI DOM fallback can recover page text but does not currently provide browser-network media capture. A WeChat Channels preview may expose only a caption and cover image; in that case it remains `partial` and no audio is fabricated from the cover.

## Image-heavy and carousel posts

Xiaohongshu, Douyin, and similar platforms may put the substantive content in a carousel while the HTML contains only a title, description, navigation shell, and the first visible image. Treat a short shell plus referenced images as `partial`, not as a complete post.

- When the user asks to use the post's images, rerun the bundled script with `--download-images` so the original files are available to the consuming model.
- `--download-images` only saves the media. This capture skill does not OCR, transcribe, or summarize pixels; image interpretation is a downstream model responsibility and is outside the capture completeness check.
- The capture script enumerates repeated Open Graph images, JSON-LD image arrays, platform SSR image lists, and hydrated Douyin `aweme_images` URLs. Keep the source image order, collapse browser-generated format/watermark variants, and exclude obvious platform share/branding and recommendation assets.
- If images cannot be downloaded, report the package as partial and state exactly what is missing.

Image understanding is intentionally delegated to the consuming multimodal
model. This skill keeps the original image files and their order but does not
make an OCR engine a required dependency. Use `--download-images` when the
images need to be handed to a vision-capable model.

## Douyin: when the page won't render

Douyin's web API is behind Argus (`Uifid`/`a_bogus` device checks). When the
normal capture returns `partial` with a "视频数据加载中" shell, fall back to
`scripts/douyin_tools.py`, which renders with a **mobile UA** (this still works
when the desktop page does not):

- `douyin_tools.py resolve <short-url>` — 短链 → `aweme_id` (`video`/`note`).
- `douyin_tools.py desc <aweme_id>` — recover the full caption (the desktop page
  folds it behind "展开"; the mobile page's embedded `desc` is complete).
- `douyin_tools.py full <aweme_id>` — render + fetch `play_addr` + download +
  ffmpeg → 16 kHz mono wav → ASR for the spoken transcript.
- `douyin_tools.py author <sec_uid>` — open the author page, intercept its own
  `aweme/post` XHR, and list the works (web shows ~15; more needs the App).

Media downloads need a Netscape cookie jar pointed at by
`PUBLIC_LINK_COOKIE_FILE`, and must use `curl` (Douyin's CDN resets urllib's
non-browser TLS fingerprint with `Errno 54`). `yt-dlp` fails on Douyin once its
cookie jar goes stale (`Fresh cookies ... are needed`); prefer `douyin_tools.py`
then. These are adversarial techniques and may break as Douyin changes.

## Reusing a captured package in later sessions

When another session should use an existing capture, give it the absolute local path to `article.md` and tell it to read the local package without revisiting the source. Do not paste the original public URL into that handoff prompt: an installation-level trigger may intentionally run capture whenever an explicit public URL appears.

## Options and safety

- Add `--no-analyze` for local capture only, `--download-images` for referenced images, `--download-audio` to extract audio without requiring transcription, `--transcribe-audio` to force the configured Qwen-compatible ASR, `--no-transcribe-audio` to skip the automatic video path, or `--download-video` to save the first usable video. Install `yt-dlp` to enable the Bilibili/X audio fallback. Supported playable videos are transcribed automatically by default when ASR is configured and consume local GPU time.
- Multiple URLs can be passed in one invocation. URL hashes make repeated captures de-duplicate into the same package and `index.jsonl`.
- The script accepts public hosts only, validates DNS results and redirects/media destinations, and does not read local/private addresses. Do not print API keys, signed URLs, or `reasoning_content`.
- If the output is `needs_browser`, install/enable a local Chromium-compatible browser or set `PUBLIC_LINK_BROWSER_EXECUTABLE` to its exact path, then retry the same URL. The saved package is not complete in this state.

For durable design decisions, verification evidence, status semantics, and known limitations, see [REFERENCE.md](REFERENCE.md).
