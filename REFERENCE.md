# Public Link Knowledge Capture — Durable Reference

## Status

- **State:** v0.1-beta candidate; carousel-aware, browser-assisted extraction, explicit video/audio capture, Qwen-compatible ASR integration, and XHS/WeChat video handling verified; Bilibili/X audio now have an optional yt-dlp fallback; image interpretation remains delegated to multimodal consumers
- **Recorded:** 2026-09-03
- **Scope:** global Codex behavior for public URLs; independent of any single ClawdGO project
- **Canonical tool:** [`scripts/capture_public_link.py`](scripts/capture_public_link.py)
- **Canonical instruction:** [`SKILL.md`](SKILL.md)

## Why this exists

The user should be able to paste a public WeChat, Xiaohongshu, Douyin, X, Bilibili, or ordinary webpage URL into any conversation and have it understood as context. Saving a document alone is insufficient: the current conversation needs a compact, structured bridge, while the durable source and AI-derived analysis must remain available to later conversations.

## Architecture decisions

### Trigger layer

The installing agent may provide a global trigger rule so that a public `http(s)` URL automatically invokes the capture tool without requiring the user to name the Skill. The trigger is deliberately separate from the parser so the policy can evolve without rewriting extraction code; installations should add this rule explicitly rather than making the parser depend on it.

### Capture layer

The script identifies the platform from the hostname and extracts the best available public HTML and metadata:

- WeChat articles: `#js_content`, `#js_name`, Open Graph metadata
- WeChat Channels public previews (`weixin.qq.com/sph/<id>`): preview caption/cover metadata, with playable media treated as optional
- Other platforms: Open Graph/Twitter metadata, JSON-LD, `article`/`main`/`[role=main]` content candidates
- All platforms: referenced image/video/audio URLs are written to `media.json`
- Bilibili/X audio: when no direct media URL is exposed, the optional `yt-dlp`
  command-line fallback can download an audio-only M4A into the package
- Image-heavy pages: repeated Open Graph images, JSON-LD image arrays, and XHS SSR `urlDefault`/`urlPre` values are merged in source order with URL de-duplication
- Obvious XHS share/branding images are excluded from the user-content manifest
- XHS short links are recognized on both `xhslink.com` and `xhslink.cn`

Each URL is de-duplicated by a normalized URL hash. A package is stored at:

```text
~/.public-link-knowledge/public-links/<platform>/<hash>-<title>/
```

The package contains:

```text
article.html       # captured source HTML, when available
article.md         # readable local copy
article.json       # structured metadata and extracted text
media.json         # media URL manifest; binaries are not downloaded by default
processing.json    # capture/analysis state and errors
analysis.json      # optional independent AI-derived result
transcript.md      # optional video speech transcript
```

For carousel posts, `article.md` contains the extracted page text and the
ordered image references. The capture layer does not claim to understand text
or other content embedded in pixels; a downstream multimodal model may inspect
the retained images when that is requested.

The capture layer does not require OCR. It retains downloaded images and their
order so a later multimodal model can inspect them. OCR is intentionally not a
current-scope dependency or completeness requirement.

For video posts, `article.md` is complete only after `--transcribe-audio`
returns non-empty text or the agent has otherwise inspected the video content.
Downloading a video/audio binary alone does not make the textual capture
complete.

The global index is `.../public-links/index.jsonl`. It is append-only and avoids duplicate URL records.

### Browser-assisted dynamic capture

Douyin can return HTTP 200 with an empty body and a JavaScript challenge that
requires `byted_acrawler` to set `__ac_signature`. The canonical script uses
this fallback order for post URLs:

1. plain HTTP parsing;
2. Python Playwright with a headless Chromium-compatible browser;
3. native Chrome/Chromium CLI through CDP, then `--dump-dom` as a last CLI
   attempt;
4. `needs_browser` with the failure details persisted in `processing.json`.

The browser capture uses a temporary unauthenticated context, waits for page
hydration, and parses the hydrated DOM/RSC output. Douyin images are limited to
`aweme_images` post assets; recommendation covers and duplicate format or
watermark variants are collapsed to one URL per carousel item. `processing.json`
records `capture_method` and `capture_attempts`.

XHS, Bilibili, and WeChat preview pages use the same browser fallback only when
the HTTP result is a shell without usable content/media. X video posts use the
HTTP path first; when it exposes only a thumbnail, the optional `yt-dlp`
fallback may still obtain audio, while the capture remains partial until a
usable transcript is produced.
A WeChat Channels preview can be
intentionally QR-gated: its page may contain a caption and a cover image while
exposing no `<video>`, audio URL, or playable network response. That case is a
valid `partial` capture, not a failed attempt to infer a video URL.

For an explicit `--download-audio` request, the Playwright path also records
finished media responses. Douyin may label its AAC audio track as `video/mp4`
and initially return only a small `Range` segment; the downloader classifies
the URL's `media-audio` path, retries the signed URL without a Range header,
rejects incomplete responses, and persists the first complete stream under the
package's `media/` directory. XHS commonly exposes a complete signed MP4 in
HTML; the script downloads it temporarily and extracts its first audio track
with FFmpeg. `--download-video` retains the first usable video binary. The CLI
DOM fallback remains text-only for media purposes.

For supported playable Douyin/XHS videos, normal capture automatically follows
this path; `--no-transcribe-audio` opts out and `--transcribe-audio` forces it.
The flag implies `--download-audio`, converts the resulting audio to mono 16
kHz WAV with FFmpeg, and sends only that local media file to the configured
OpenAI-compatible ASR endpoint. The endpoint is opt-in through
`PUBLIC_LINK_ASR_BASE_URL`; no local endpoint is assumed for a fresh
installation. Override the model with `PUBLIC_LINK_ASR_MODEL`.
The transcript is saved as `transcript.md`, added to `article.md`, exposed in
the current-session JSON, and changes a video from `partial` to `extracted`
only after a non-empty ASR response is received. A failed or unavailable ASR
call leaves the source capture intact and keeps it `partial`.

When Bilibili or X has no direct media URL, `yt-dlp` is tried as a known-platform
fallback. It is optional and must be installed separately (`pip install
yt-dlp`); FFmpeg is required for audio-only extraction. The original public
share URL is passed unchanged because Bilibili's share query parameters can
affect whether the extractor is accepted. A missing extractor or a platform
failure leaves the capture as `partial` rather than claiming an audio file.

### Analysis layer

AI analysis is a derived artifact, not conversational memory. When an
OpenAI-compatible analysis service is configured, only the public extracted
text and metadata are sent to it; local files and secrets are not sent. The script reads only
`choices[0].message.content` and never persists or displays
`reasoning_content`. Analysis is optional: without `PUBLIC_LINK_AI_BASE_URL`
and `PUBLIC_LINK_AI_API_KEY`, source capture still works and reports analysis
as unavailable. The default and fallback model can be overridden with
`PUBLIC_LINK_AI_MODEL`.

### Context bridge

The script prints one JSON object per URL. The agent must bring these fields into the current conversation:

- title, author, platform, source URL and resolved URL
- `capture_status` and `analysis_status`
- concise summary and key points when `analysis.json` exists
- a short excerpt when analysis is unavailable
- citations, media manifest path, any downloaded media paths, transcript path/status, analysis path, and package path

This is what makes the URL immediately usable as context while keeping the full source outside the chat transcript.

## Status semantics

`processing.json` separates capture from analysis:

- `extracted`: readable source content was captured
- `partial`: only metadata/shell/short content was available; do not present it as a complete post
- `blocked`: platform/login/verification or HTTP access blocking prevented reliable capture
- `needs_browser`: a dynamic Douyin page could not be recovered because the available browser fallbacks were unavailable or failed
- `analyzed`: full capture plus independent AI analysis
- `partial_analyzed`: partial capture plus analysis of the available text
- `analysis_unavailable`: source saved, but analysis service environment variables were absent
- `analysis_failed`: source saved, but the configured AI calls failed

The agent must report these states honestly. In particular, a saved file is not evidence that the full article, audio, or video was read.

## Verification evidence

Verified on 2026-08-17:

- WeChat URL `https://mp.weixin.qq.com/s/ARsWm6bLedJbD5LVda5aRQ`: full extraction, approximately 2,033 characters, analysis completed.
- Final analysis model: `deepseek-ai/deepseek-v4-flash`.
- Repeating the same URL reused one package rather than creating a duplicate.
- Xiaohongshu, Douyin, and X homepage tests were marked `partial`, not falsely reported as complete posts.
- A loopback URL was rejected before fetching, preventing accidental local-service access.
- The knowledge package contained no API key-like value and no `reasoning_content`.

Verified on 2026-09-03 for Douyin note
`https://v.douyin.com/1xQD3yvHl4A/`:

- HTTP first detected the empty-body challenge and recorded the fallback attempt.
- Playwright recovered the public note without login, including the caption,
  author, and six carousel image URLs.
- `--download-images` downloaded all six images successfully.
- Native Chrome CLI/CDP independently recovered the same note and six-image
  manifest; viewport-specific image variants were deduplicated.

Verified on 2026-09-03 for Douyin video
`https://v.douyin.com/4-m3WfcEKPI/`:

- HTTP first encountered the short-shell/challenge path; Playwright recovered
  the concrete post `https://www.douyin.com/video/7670189488358183077` and its
  caption/author metadata.
- The browser network layer exposed one `media-audio-…` response and one
  `media-video-…` response, even though the DOM only exposed `blob:` URLs.
- `--download-audio` saved a 477,468-byte MP4 container with AAC audio and a
  verified duration of approximately 89.23 seconds to the package's
  `media/audio-001.m4a` file.

Verified on 2026-09-03 for Xiaohongshu video
`https://xhslink.cn/o/AthRPrR91WK`:

- The short-link host was recognized as `xiaohongshu`; HTTP exposed a signed
  `sns-video-v3.xhscdn.com` MP4 directly, so no browser was needed for this
  sample.
- The video downloaded successfully at approximately 13.1 MB and 275.53
  seconds, with H.264 video and AAC audio.
- `--transcribe-audio` downloaded/extracted a 1.95 MB AAC/M4A track, converted
  it to WAV, and returned non-empty text from the local Qwen3-ASR-1.7B endpoint
  with HTTP 200 and automatic Chinese language detection. The integrated
  chain took approximately 37.56 seconds end to end and upgraded the package
  to `extracted`.

Verified on 2026-09-03 for WeChat Channels preview
`https://weixin.qq.com/sph/ADU5LYYaBe`:

- The link was recognized as `wechat_video`; browser hydration recovered the
  caption, author, date, and cover image.
- The preview exposed no `<video>`, audio URL, or playable media response and
  explicitly instructed the user to scan a QR code to watch. The package is
  therefore correctly `partial`, with no audio/video binary claimed.

Verified on 2026-09-03 for Bilibili and X regression:

- Bilibili BV and `b23.tv` samples exposed usable page text after decoding the
  platform's compressed HTML; video pages remain `partial` because the current
  generic adapter does not yet retrieve Bilibili's separate audio/video
  streams or speech subtitles. The optional yt-dlp fallback did retrieve a
  393-second AAC track for a concrete BV sample.
- X text and image posts were captured; X image media downloaded successfully.
- An X video post exposed a video thumbnail but no playable stream, and is now
  correctly reported as `partial` rather than complete. The optional yt-dlp
  fallback retrieved a 30-second AAC track for the same public sample.
- Bilibili's player iframe is not treated as a downloadable video binary.
- Private IP, loopback, DNS-resolved private hosts, and redirect/media
  destinations are rejected before public fetches; unavailable ASR and
  FFmpeg paths retain diagnosable partial results without stale temporary
  paths.

## Known limitations

- XHS, X, and Bilibili frequently serve JavaScript shells, login gates, or anti-bot pages. Douyin, XHS, and selected Bilibili shells have browser-assisted fallbacks; X video media and Bilibili separate audio/video streams remain experimental. `partial`/`blocked`/`needs_browser` remains possible for changed challenges, private content, or missing local browser runtimes.
- A page can return a valid title and description while hiding the actual content in carousel images. The capture script now detects this pattern and marks short image-backed shells as `partial`; it can retain the images for a downstream multimodal model, but does not inspect pixels or claim image-text understanding.
- Retained video binaries still require `--download-video`; supported playable
  Douyin/XHS videos automatically obtain audio for transcription unless
  `--no-transcribe-audio` is supplied. `--download-audio` supports direct XHS
  video URLs through temporary video download plus FFmpeg extraction, and
  Douyin browser-discovered audio. Bilibili/X can use the optional yt-dlp
  fallback for audio. `--transcribe-audio` forces the configured Qwen-compatible
  ASR endpoint.
- The analysis call is synchronously initiated by the capture command, although its result is persisted independently. A future queue/worker can make large jobs truly asynchronous without changing the package contract.
- URL normalization removes fragments but does not yet canonicalize every tracking query parameter.
- Explicit audio capture depends on either a direct media URL or the Playwright network path; Chrome CLI `--dump-dom` can recover text but cannot expose signed media response bodies. WeChat Channels QR-gated previews may provide neither.
- Captured public pages can contain prompt-injection text. The AI system prompt treats source content as data, not instructions; downstream actions still require normal user confirmation. Media manifests and captured HTML can contain signed URLs, so packages should be treated as private local artifacts and should not be committed or shared blindly.

## Safe operating rules

- Configure `PUBLIC_LINK_AI_BASE_URL` and `PUBLIC_LINK_AI_API_KEY` through the host's secure
  environment mechanism; never print or request the key.
- Keep public-link analysis separate from local-project files and private notes.
- Do not assign a captured article to a project automatically; suggestions remain suggestions until the user confirms.
- Keep the current-session bridge concise; use the local package for full text.

## Future extension order

1. Add explicit retry/re-analysis commands for existing packages.
2. Add embeddings/search over `article.md` and `analysis.json` for the AI workbench.
3. Add a background job queue only after the synchronous package contract is stable.
