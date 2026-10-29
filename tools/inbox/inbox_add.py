#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""向分享收件箱追加/更新一条记录（所有 agent 通用入口），并自动重建看板。

用法示例：
  python3 inbox_add.py --title "标题" --url "https://..." --source 公众号 \
      --summary "2–5 句要点" --status 已抓取 --tags "科研,Skill" --agent codex --channel manual

同一规范化 URL 已存在时合并更新而不是重复追加（只去追踪参数，保留页面身份参数）：
新值非空才覆盖旧值。无 URL 的条目按标题去重。写入是原子的（临时文件 + rename）。
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inbox_common import norm_url, write_lock  # noqa: E402

INBOX = os.path.dirname(os.path.abspath(__file__))
EXTRA = os.path.join(INBOX, "inbox_extra.jsonl")
FIELDS = ["date", "source", "title", "author", "url", "type", "stats",
          "summary", "status", "tags", "package", "notes", "detail", "agent", "channel"]
STICKY = ("agent", "channel")  # 首次写入后不再被别的 agent 的更新覆盖
AGENTS = ["hermes", "cc", "codex", "agy", "grok", "grokbot", "muse", "user"]
AGENT_ALIASES = {"claude": "cc", "claude-code": "cc", "antigravity": "agy", "grok-bot": "grokbot"}
SOURCES = {"抖音": "抖音", "douyin": "抖音", "公众号": "公众号", "wechat": "公众号", "weixin": "公众号",
           "网页": "网页", "web": "网页", "x": "X", "twitter": "X", "小红书": "小红书",
           "xiaohongshu": "小红书", "xhs": "小红书", "b站": "B站", "bilibili": "B站",
           "youtube": "YouTube", "reddit": "Reddit", "github": "GitHub", "hn": "HN",
           "手工": "手工", "manual": "手工", "微信": "微信", "视频号": "视频号",
           "asr": "ASR", "通话": "ASR"}
STATUSES = ["已抓取", "部分抓取", "抓取失败", "需浏览器", "待补链接", "提示词/要点", "手工记录"]


def key_of(r):
    return norm_url(r.get("url")) or ("T:" + (r.get("title") or "")[:40])


def load():
    rows, invalid_lines = [], []
    if os.path.exists(EXTRA):
        for line_no, line in enumerate(open(EXTRA, encoding="utf-8"), 1):
            raw = line.rstrip("\r\n")
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                print(f"警告: inbox_extra.jsonl 第{line_no}行不是合法 JSON，已跳过处理并保留原文")
                invalid_lines.append(raw)
                continue
            if not isinstance(value, dict):
                print(f"警告: inbox_extra.jsonl 第{line_no}行不是 JSON 对象，已跳过处理并保留原文")
                invalid_lines.append(raw)
                continue
            rows.append(value)
    return rows, invalid_lines


def save(rows, invalid_lines):
    fd, tmp = tempfile.mkstemp(dir=INBOX, prefix=".extra-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        for line in invalid_lines:
            f.write(line + "\n")
    os.replace(tmp, EXTRA)


def snapshot_private_data():
    script = os.path.join(INBOX, "snapshot_private_data.py")
    try:
        result = subprocess.run([sys.executable, script], capture_output=True, text=True)
    except OSError as exc:
        print(f"警告: 私有数据快照未运行: {exc}")
        return
    if result.returncode == 0:
        if result.stdout.strip():
            print(result.stdout.strip())
    else:
        detail = result.stderr.strip() or result.stdout.strip() or f"退出码 {result.returncode}"
        print(f"警告: 私有数据快照失败: {detail}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--title", required=True)
    ap.add_argument("--url", default="")
    ap.add_argument("--source", default=None, help="抖音/公众号/网页/X/小红书/B站/YouTube/Reddit/GitHub/HN/手工/ASR")
    ap.add_argument("--author", default="")
    ap.add_argument("--type", default=None, help="视频|图文|文章|Skill|工具/开源|提示词|信息")
    ap.add_argument("--stats", default="", help="如：赞1234 藏567 转89")
    ap.add_argument("--summary", default="", help="2–5 句要点，让人不点开原文也知道是什么")
    ap.add_argument("--status", default=None, help="/".join(STATUSES))
    ap.add_argument("--tags", default="", help="逗号分隔")
    ap.add_argument("--package", default="", help="知识包绝对路径")
    ap.add_argument("--notes", default="")
    ap.add_argument("--detail", default="", help="收件箱目录下的详细记录相对路径")
    ap.add_argument("--agent", default=os.environ.get("PUBLIC_LINK_AGENT", ""),
                    help="【必填】谁在入库：" + "/".join(AGENTS) + "（也可设环境变量 PUBLIC_LINK_AGENT）")
    ap.add_argument("--channel", default=os.environ.get("PUBLIC_LINK_CHANNEL", ""),
                    help="链接来自哪里：wechat/manual/test/cron（也可设 PUBLIC_LINK_CHANNEL）；agent 自己测试用的链接请标 test")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--no-build", action="store_true", help="只写入，不重建看板")
    a = ap.parse_args()

    # 来源必须可追溯：不写 --agent 就拒绝入库（2026-10-29 起），避免再出现"未知"来源
    agent = AGENT_ALIASES.get(a.agent.strip().lower(), a.agent.strip().lower())
    if agent not in AGENTS:
        sys.exit("缺少或不认识 --agent（当前值: %r）。请写明你是谁，可选: %s\n"
                 "例: python3 inbox_add.py --agent cc --channel wechat ...；"
                 "自己测试用的链接加 --channel test。" % (a.agent, "/".join(AGENTS)))
    a.agent = agent

    # 更新已有条目时，没显式传的字段不能被默认值覆盖；默认值只在新建时补
    source = SOURCES.get((a.source or "").strip().lower(), SOURCES.get((a.source or "").strip())) if a.source else ""
    if a.source and not source:
        sys.exit(f"来源 '{a.source}' 不认识，可选: {sorted(set(SOURCES.values()))}")
    if a.status and a.status not in STATUSES:
        sys.exit(f"状态 '{a.status}' 不合法，可选: {STATUSES}")
    local_document = a.type == "文档" and a.url.startswith("file:///")
    if a.url and not (a.url.startswith(("http://", "https://")) or local_document):
        sys.exit("url 必须以 http(s):// 开头；本地文档允许绝对 file:/// URI；没有链接请留空")
    detail = a.detail.strip().replace("\\", "/")
    if detail:
        inbox_real = os.path.realpath(INBOX)
        detail_real = os.path.realpath(os.path.join(INBOX, detail))
        if (os.path.isabs(detail) or detail_real == inbox_real
                or not detail_real.startswith(inbox_real + os.sep)
                or not os.path.isfile(detail_real)):
            sys.exit("detail 必须是收件箱目录内已存在文件的相对路径")
        detail = os.path.relpath(detail_real, inbox_real).replace(os.sep, "/")

    new = {"date": a.date, "source": source, "title": a.title.strip(), "author": a.author,
           "url": a.url.strip(), "type": a.type or "", "stats": a.stats, "summary": a.summary,
           "status": a.status or "", "tags": a.tags, "package": a.package, "notes": a.notes,
           "detail": detail, "agent": a.agent.strip().lower(), "channel": a.channel.strip().lower()}
    with write_lock():  # 读-改-写必须互斥，否则两个 agent 同时入库时后写的会吃掉先写的
        rows, invalid_lines = load()
        k = key_of(new)
        for r in rows:
            if key_of(r) == k:
                for f in FIELDS:
                    if f in STICKY and r.get(f):
                        continue
                    if new.get(f):
                        r[f] = new[f]
                action = "已更新"
                break
        else:
            new["source"] = new["source"] or "网页"
            new["type"] = new["type"] or "文章"
            new["status"] = new["status"] or "已抓取"
            rows.append(new)
            action = "已追加"
        save(rows, invalid_lines)
    snapshot_private_data()
    print(f"{action}: {new['title']}（共 {len(rows)} 条补录）")
    if not a.no_build:
        subprocess.run([sys.executable, os.path.join(INBOX, "build_inbox.py")], check=True)


if __name__ == "__main__":
    main()
