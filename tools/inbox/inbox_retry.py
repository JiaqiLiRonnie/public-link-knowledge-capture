#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出（并可重抓）收件箱里抓取失败 / 需要浏览器的链接。

  python3 inbox_retry.py                列出待重试条目（只读）
  python3 inbox_retry.py --run          逐条用 capture_public_link.py --no-analyze 重抓，然后重建看板
  python3 inbox_retry.py --include-partial   连"部分抓取"也算
抖音链接不走这里（请用 douyin_tools.py）。某 URL 后来已抓取成功则不再列出。
"""
import argparse
import json
import os
import subprocess
import sys

INBOX = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(INBOX)
KNOWLEDGE = os.environ.get("PUBLIC_LINK_KNOWLEDGE_DIR") or os.path.join(ROOT, "public-links")
CAPTURE = os.environ.get("PUBLIC_LINK_CAPTURE_SCRIPT") or os.path.expanduser(
    "~/.agents/skills/public-link-knowledge-capture/scripts/capture_public_link.py")


def norm(u):
    return (u or "").strip().rstrip("/").split("?")[0]


def pending(include_partial):
    last = {}
    path = os.path.join(KNOWLEDGE, "index.jsonl")
    for line in open(path, encoding="utf-8"):
        if line.strip():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            last[norm(d.get("url") or d.get("resolved_url"))] = d  # 同 URL 以最后一条为准
    bad = {"failed", "needs_browser"} | ({"partial"} if include_partial else set())
    return [d for d in last.values() if d.get("capture_status") in bad]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--include-partial", action="store_true")
    a = ap.parse_args()
    items = pending(a.include_partial)
    if not items:
        print("没有待重试条目")
        return
    for d in items:
        print(f"[{d.get('capture_status')}] {d.get('platform')}\t{d.get('url')}")
    if not a.run:
        print(f"\n共 {len(items)} 条。加 --run 重抓（抖音请改用 douyin_tools.py）。")
        return
    env = dict(os.environ)
    env.setdefault("https_proxy", "")  # 本机统一代理
    for d in items:
        if d.get("platform") == "douyin":
            print("跳过抖音:", d.get("url"))
            continue
        r = subprocess.run([sys.executable, CAPTURE, "--no-analyze", d["url"]], env=env,
                           capture_output=True, text=True, timeout=300)
        try:
            out = json.loads(r.stdout.strip().splitlines()[-1])
            print(f"{out.get('status')}\t{d['url']}\t{out.get('error') or ''}")
        except (ValueError, IndexError):
            print("未知输出\t", d["url"], r.stderr[-200:])
    subprocess.run([sys.executable, os.path.join(INBOX, "build_inbox.py")], check=True)


if __name__ == "__main__":
    main()
