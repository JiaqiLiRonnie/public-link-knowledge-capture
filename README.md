# Public Link Knowledge Capture

一个面向 Codex/Agent 的公开链接捕获 skill：把微信公众号、小红书、抖音、X、Bilibili、微信视频号预览和普通网页保存为可复用的本地知识包。

当前版本的重点是：

- 抓取网页正文、标题、作者和结构化元数据；
- 保留图文帖中的原图及其顺序，不内置 OCR 或视觉模型；
- 对可播放视频提取音频；
- 通过可选的 OpenAI-compatible Qwen ASR 服务生成 `transcript.md`；
- 将捕获结果以 JSON 返回给当前 Agent，并保存为本地文件。

这是一个 v0.1-beta 发布候选包。平台页面、登录墙、验证码和分享链接的有效性会影响结果；脚本会如实返回 `partial`、`blocked` 或 `needs_browser`，不会把标题、封面或短壳页伪装成完整内容。

## 安装

必需依赖：Python 3.10+ 和 BeautifulSoup。

```bash
python3 -m pip install -r requirements.txt
```

音频提取或 ASR 需要 FFmpeg。Bilibili/X 的命令行音频回退需要 `yt-dlp`；动态页面的优先浏览器回退需要 Playwright 和 Chromium，Chrome CLI/CDP 是另一条可选路径。

```bash
# 按需安装
python3 -m pip install yt-dlp playwright websockets brotli
playwright install chromium
```

## 使用

```bash
python3 scripts/capture_public_link.py "https://example.com/article"
```

常用选项：

```bash
# 仅抓取并保存，不调用文本分析服务
python3 scripts/capture_public_link.py --no-analyze URL

# 下载图文帖图片
python3 scripts/capture_public_link.py --download-images URL

# 只下载/提取视频音频
python3 scripts/capture_public_link.py --download-audio URL

# 强制调用已配置的 ASR；该选项同时下载/提取音频
python3 scripts/capture_public_link.py --transcribe-audio URL

# 保存视频本体
python3 scripts/capture_public_link.py --download-video URL
```

默认情况下，配置了 ASR 的普通捕获会自动尝试对支持的视频转写；使用 `--no-transcribe-audio` 可跳过，使用 `--transcribe-audio` 可强制尝试。`--no-analyze` 适合纯本地捕获；若同时需要转写，请显式加 `--transcribe-audio`。

## 可选服务配置

网页捕获本身不需要 AI 服务。配置下面两组环境变量后，才会启用对应的派生能力：

```bash
# 可选：OpenAI-compatible 文本分析服务
export PUBLIC_LINK_AI_BASE_URL="https://your-service.example/v1"
export PUBLIC_LINK_AI_API_KEY="..."
export PUBLIC_LINK_AI_MODEL="your-model"       # 可选

# 可选：OpenAI-compatible 音频转写服务
export PUBLIC_LINK_ASR_BASE_URL="http://your-asr-host:port"
export PUBLIC_LINK_ASR_MODEL="Qwen3-ASR-1.7B"   # 可选
export PUBLIC_LINK_ASR_LANGUAGE=""              # 可选，空值表示自动识别
export PUBLIC_LINK_ASR_API_KEY="..."            # 可选
```

`PUBLIC_LINK_ASR_BASE_URL` 可以填写服务根地址，也可以直接填写 `/v1/audio/transcriptions` 端点。脚本会先用 FFmpeg 将音频规范化为单声道 16 kHz WAV，再以 multipart 请求发送；本地音频文件不会发送给文本分析服务。

其他常用配置：

- `PUBLIC_LINK_KNOWLEDGE_DIR`：知识包根目录，默认 `~/.public-link-knowledge/public-links`。
- `PUBLIC_LINK_BROWSER_EXECUTABLE`：指定 Chrome/Chromium 可执行文件。
- `PUBLIC_LINK_BROWSER_CLI_TIMEOUT`、`PUBLIC_LINK_BROWSER_VIRTUAL_TIME`：调整 Chrome CLI 回退。

## 输出

脚本对单个 URL 输出一个 JSON 对象；多个 URL 输出 `results` 数组。默认在每个 URL 下生成：

```text
article.html       # 原始 HTML（如果有）
article.md         # 正文、元数据和已生成的语音转写
article.json       # 结构化捕获结果
media.json         # 图片/视频/音频 URL 及下载状态
processing.json    # 捕获、分析、转写状态和错误
analysis.json      # 可选的文本分析
transcript.md      # 可选的独立语音转写
media/             # 用户请求或转写链路实际下载的媒体
```

`partial` 表示只拿到部分可靠内容，例如标题、简介、封面或网页壳；`blocked` 表示平台拦截或登录/验证阻断；`needs_browser` 表示当前浏览器回退不可用或失败。只有得到可读正文，或视频得到非空语音转写，才会被标记为完整捕获。

## 路由与已知边界

捕获顺序是：普通 HTTP → Python Playwright → Chrome/Chromium CLI/CDP → 带诊断信息的部分结果。

- 抖音、小红书：已验证动态正文/图片和部分视频音频链路。
- Bilibili、X：正文优先走 HTTP；无直接媒体 URL 时可选 `yt-dlp` 提取音频，但受登录墙和反爬影响，仍可能是 `partial`。
- 微信视频号预览：常见情况下只能拿到预览文案和封面；二维码门槛下没有可播放媒体时不会伪造音视频。
- 图片：只保存原图和顺序，图片理解交给后续多模态模型。

脚本只接受公开 `http(s)` URL，并检查重定向和媒体目标，拒绝回环、私有和未公开的内网地址。捕获包可能包含公开页面 HTML、签名媒体 URL 和用户请求下载的媒体，不要把运行生成的知识包直接提交到公共仓库。

## 许可证

MIT License，见 [LICENSE](LICENSE)。发布前如需采用其他许可证，可替换该文件。
