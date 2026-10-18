#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""douyin_tools.py — 抖音抓取的绕过工具（应对 Argus 风控 / 未登录态）。

背景：抖音 web 端对「未登录 + 自动化」相当严格——
  - 桌面 UA 打开视频页常停在「视频数据加载中」；
  - `aweme/v1/web/aweme/detail` 直接请求会被 Argus 拦：先 `Uifid Not Found`，
    补 uifid 后报 `Signature Not Found`（a_bogus 签名 + 设备指纹一致性）。
本脚本用**移动 UA 渲染真实页面**绕过上述限制（2026-10 实测有效）。

能做什么
  resolve  短链 → aweme_id
  render   移动 UA 渲染视频页 → 标题 / 作者 / 点赞等（拿不到时降级）
  desc     从页面内嵌数据里抠出**完整文案**（含 emoji、换行）
  full     渲染 + 取播放地址 + 下载 + ffmpeg 归一化 + ASR 转写（口播全文）
  author   移动 UA 打开作者主页，拦截页面自身的 post API，批量列出作品

依赖：playwright（含 Chromium 或系统 Chrome）、ffmpeg、curl。
cookie：登录态能拿到更多（图片/视频 CDN 是登录门槛）。用 Netscape 格式 cookie jar，
        路径由 PUBLIC_LINK_COOKIE_FILE 指定（默认 ~/.public-link-knowledge/cookies.txt）。

用法：
  python3 douyin_tools.py resolve https://v.douyin.com/XXXX/
  python3 douyin_tools.py desc <aweme_id>
  python3 douyin_tools.py full <aweme_id>            # 含 ASR 转写
  python3 douyin_tools.py author <sec_uid>           # 批量列出该号作品
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

CHROME_CANDIDATES = [
    os.environ.get("PUBLIC_LINK_BROWSER_EXECUTABLE", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]
CHROME = next((c for c in CHROME_CANDIDATES if c and os.path.exists(c)), "")
COOKIE_FILE = os.environ.get("PUBLIC_LINK_COOKIE_FILE") or str(
    os.path.expanduser("~/.public-link-knowledge/cookies.txt"))
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
             "Mobile/15E148 Safari/604.1")
ASR_BASE = os.environ.get("PUBLIC_LINK_ASR_BASE_URL", "http://127.0.0.1:18195")
ASR_MODEL = os.environ.get("PUBLIC_LINK_ASR_MODEL", "Qwen3-ASR-0.6B")
ASR_KEY_FILE = os.environ.get("PUBLIC_LINK_ASR_API_KEY_FILE", "")


def _playwright():
    from playwright.sync_api import sync_playwright  # noqa: F401
    return sync_playwright


def load_cookies(path=COOKIE_FILE):
    out = []
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8", errors="ignore"):
        if line.startswith("#") or not line.strip():
            continue
        p = line.rstrip("\n").split("\t")
        if len(p) >= 7 and "douyin" in p[0].replace("#HttpOnly_", "").lstrip("."):
            if p[5].strip():
                out.append({"name": p[5].strip(), "value": p[6],
                            "domain": p[0].replace("#HttpOnly_", "").lstrip("."),
                            "path": "/", "secure": False, "expires": -1})
    return out


def new_page(pw):
    b = pw.chromium.launch(executable_path=CHROME or None, headless=True)
    ctx = b.new_context(locale="zh-CN", user_agent=MOBILE_UA,
                        viewport={"width": 390, "height": 844},
                        is_mobile=True, has_touch=True)
    ctx.add_cookies(load_cookies())
    return b, ctx.new_page()


def cmd_resolve(short_url):
    ua = MOBILE_UA
    loc = subprocess.run(["curl", "-sI", "-m", "20", "-A", ua, short_url],
                         capture_output=True, text=True).stdout
    m = re.search(r"/(?:video|note)/(\d+)", loc)
    if not m:
        print(json.dumps({"error": "cannot resolve", "raw": loc[:200]}, ensure_ascii=False))
        return
    kind = "note" if "/note/" in loc else "video"
    print(json.dumps({"aweme_id": m.group(1), "kind": kind}, ensure_ascii=False))


def cmd_render(aweme_id):
    sp = _playwright()
    with sp() as pw:
        b, pg = new_page(pw)
        pg.goto(f"https://www.douyin.com/video/{aweme_id}",
                wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(11000)
        html = pg.evaluate("document.documentElement.outerHTML") or ""
        desc = re.findall(r'"desc"\s*:\s*"((?:[^"\\]|\\.){4,2000})"', html)
        desc = [d.encode("latin-1", "ignore").decode("utf-8", "ignore") if "\\u" not in d else d
                for d in desc]
        nick = re.search(r'"nickname"\s*:\s*"([^"]{1,40})"', html)
        txt = pg.evaluate("document.body.innerText") or ""
        print(json.dumps({"title": pg.title(), "nickname": nick.group(1) if nick else "",
                          "descs": desc[:3], "body_head": txt[:500]}, ensure_ascii=False, indent=1))
        b.close()


def cmd_desc(aweme_id):
    sp = _playwright()
    with sp() as pw:
        b, pg = new_page(pw)
        pg.goto(f"https://www.douyin.com/video/{aweme_id}",
                wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(11000)
        for sel in ("text=展开", "text=... 展开"):
            try:
                el = pg.query_selector(sel)
                if el:
                    el.click()
                    pg.wait_for_timeout(2500)
                    break
            except Exception:
                pass
        html = pg.evaluate("document.documentElement.outerHTML") or ""
        descs = re.findall(r'"desc"\s*:\s*"((?:[^"\\]|\\.){10,2000})"', html)
        seen = []
        for d in descs:
            if "\\u" in d:
                d = d.encode().decode("unicode_escape", "ignore")
            else:
                try:
                    d = d.encode("latin-1").decode("utf-8", "ignore")
                except Exception:
                    pass
            if d not in seen and len(d) > 10:
                seen.append(d)
        print(json.dumps({"descs": seen[:8]}, ensure_ascii=False, indent=1))
        b.close()


def _asr(wav):
    key = ""
    if ASR_KEY_FILE and os.path.exists(ASR_KEY_FILE):
        key = open(ASR_KEY_FILE, encoding="utf-8", errors="ignore").read().strip()
    else:
        key = os.environ.get("PUBLIC_LINK_ASR_API_KEY", "")
    cmd = ["curl", "-s", "-m", "900", "-X", "POST",
           f"{ASR_BASE.rstrip('/')}/v1/audio/transcriptions",
           "-F", f"file=@{wav}", "-F", f"model={ASR_MODEL}"]
    if key:
        cmd += ["-H", f"Authorization: Bearer {key}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout).get("text", "")
    except Exception:
        return ""


def cmd_full(aweme_id):
    sp = _playwright()
    out = {"aweme_id": aweme_id, "play_url": None, "desc": "", "like": None,
           "author": "", "transcript": ""}
    mp4 = wav = None
    with sp() as pw:
        b, pg = new_page(pw)
        play = {"url": None}

        def on_resp(resp):
            if play["url"] is None and ("aweme/v1/play" in resp.url or "/play/" in resp.url):
                play["url"] = resp.url

        pg.on("response", on_resp)
        pg.goto(f"https://www.douyin.com/video/{aweme_id}",
                wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(9000)
        html = pg.evaluate("document.documentElement.outerHTML") or ""
        m = re.search(r'"play_addr"\s*:\s*\{[^}]*"url_list"\s*:\s*\[\s*"([^"]+)"', html)
        if m:
            play["url"] = play["url"] or m.group(1)
        d = re.search(r'"desc"\s*:\s*"((?:[^"\\]|\\.){4,2000})"', html)
        if d:
            dd = d.group(1)
            out["desc"] = dd.encode().decode("unicode_escape", "ignore") if "\\u" in dd else dd
        lk = re.search(r'"digg_count"\s*:\s*(\d+)', html)
        out["like"] = int(lk.group(1)) if lk else None
        au = re.search(r'"nickname"\s*:\s*"([^"]{1,40})"', html)
        out["author"] = au.group(1) if au else ""
        out["play_url"] = play["url"]
        b.close()

    if out["play_url"]:
        tmp = tempfile.mkdtemp(prefix="dyfull_")
        mp4 = os.path.join(tmp, "v.mp4")
        r = subprocess.run(["curl", "-sS", "-m", "180", "-A", MOBILE_UA,
                            "-e", "https://www.douyin.com/",
                            "-b", COOKIE_FILE, "-o", mp4, out["play_url"]],
                           capture_output=True, text=True)
        if os.path.exists(mp4) and os.path.getsize(mp4) > 0:
            wav = os.path.join(tmp, "a.wav")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4,
                            "-ac", "1", "-ar", "16000", wav], capture_output=True)
            if os.path.exists(wav) and os.path.getsize(wav) > 0:
                out["transcript"] = _asr(wav)
    print(json.dumps(out, ensure_ascii=False))


def cmd_author(sec_uid):
    sp = _playwright()
    seen = {}
    with sp() as pw:
        b, pg = new_page(pw)

        def on_resp(resp):
            if "aweme/post" in resp.url and resp.status == 200:
                try:
                    d = json.loads(resp.text())
                except Exception:
                    return
                for it in d.get("aweme_list") or []:
                    aid = it.get("aweme_id")
                    if aid and aid not in seen:
                        st = it.get("statistics") or {}
                        seen[aid] = {
                            "aweme_id": aid, "desc": (it.get("desc") or "").replace("\n", " "),
                            "digg": st.get("digg_count"), "images": len(it.get("images") or []),
                            "duration": (it.get("video") or {}).get("duration"),
                        }

        pg.on("response", on_resp)
        pg.goto(f"https://www.douyin.com/user/{sec_uid}",
                wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(9000)
        for _ in range(10):
            pg.mouse.wheel(0, 1700)
            pg.wait_for_timeout(1500)
        out = sorted(seen.values(), key=lambda x: -(x.get("digg") or 0))
        print(json.dumps({"sec_uid": sec_uid, "count": len(out), "videos": out},
                         ensure_ascii=False, indent=1))
        b.close()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    cmd, arg = sys.argv[1], sys.argv[2]
    {"resolve": cmd_resolve, "render": cmd_render, "desc": cmd_desc,
     "full": cmd_full, "author": cmd_author}[cmd](arg)


if __name__ == "__main__":
    main()
