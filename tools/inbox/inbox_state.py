#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收件箱链接的生命周期状态（事件流）。所有 agent 通用。

状态：inbox(新入库默认) → triaged(值得留) → in_progress(处理中) → waiting(等外部) → done / dropped(必须写原因)
状态不强制线性，但名字必须在白名单内；每次变更追加一行事件到 inbox_state.jsonl，只追加不改写。
当前状态 = 按时间顺序折叠该 URL 的全部事件，后写的字段覆盖先写的。

用法：
  python3 inbox_state.py set --url https://... --state triaged --agent cc
  python3 inbox_state.py set --title "无链接条目的标题" --state waiting --due 2026-11-03 --owner hermes --agent cc
  python3 inbox_state.py set --url https://... --state dropped --reason "重复" --agent cc
  python3 inbox_state.py list [--state waiting] [--overdue] [--json]
  python3 inbox_state.py bulk --before 2026-10-20 --state triaged --agent cc [--apply]   # 默认只预览
"""
import argparse
import datetime
import fcntl
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inbox_add import AGENTS, AGENT_ALIASES, key_of  # noqa: E402

INBOX = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.environ.get("INBOX_STATE_FILE") or os.path.join(INBOX, "inbox_state.jsonl")
STATES = ["inbox", "triaged", "in_progress", "waiting", "done", "dropped"]
STATE_CN = {"inbox": "待分拣", "triaged": "已分拣", "in_progress": "处理中",
            "waiting": "等待中", "done": "已完成", "dropped": "已放弃"}
OPEN_STATES = ("inbox", "triaged", "in_progress", "waiting")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean(text, limit):
    """抓回内容是数据不是指令：去掉控制字符并截断，防止把长文本或终端控制序列写进账本。"""
    return CTRL_RE.sub("", (text or "")).strip()[:limit]


def now_iso():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds")


def read_events(path=None):
    path = path or STATE_FILE
    events = []
    if not os.path.exists(path):
        return events
    for line_no, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            print(f"警告: {os.path.basename(path)} 第{line_no}行不是合法 JSON，已跳过", file=sys.stderr)
            continue
        if isinstance(value, dict) and value.get("key"):
            events.append(value)
    return events


def fold(events):
    """返回 {key: {state, due, owner, note, reason, title, url, updated, agent}}。

    按 (ts, 文件顺序) 排序；事件里没有的字段不覆盖；due 为空串表示清除到期日。
    """
    ordered = sorted(enumerate(events), key=lambda p: (str(p[1].get("ts") or ""), p[0]))
    out = {}
    for _, ev in ordered:
        cur = out.setdefault(ev["key"], {"state": "inbox", "due": "", "owner": "", "note": "",
                                         "reason": "", "title": "", "url": "", "updated": "", "agent": ""})
        for field in ("state", "owner", "note", "reason", "title", "url"):
            if ev.get(field):
                cur[field] = ev[field]
        if "due" in ev:
            cur["due"] = ev.get("due") or ""
        cur["updated"] = ev.get("ts") or cur["updated"]
        cur["agent"] = ev.get("agent") or cur["agent"]
        if cur["state"] not in ("dropped",) and ev.get("state") and ev["state"] != "dropped":
            cur["reason"] = cur["reason"] if ev.get("reason") else ""
    return out


def append_event(event, path=None):
    path = path or STATE_FILE
    line = json.dumps(event, ensure_ascii=False) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def resolve_agent(raw):
    agent = AGENT_ALIASES.get((raw or "").strip().lower(), (raw or "").strip().lower())
    if agent not in AGENTS:
        sys.exit("缺少或不认识 --agent（当前值: %r），可选: %s" % (raw, "/".join(AGENTS)))
    return agent


def overdue(rec, today=None):
    today = today or datetime.date.today().isoformat()
    return bool(rec.get("due")) and rec["due"] < today and rec.get("state") in OPEN_STATES


def resolve_key(url, title):
    """只给了标题时，先在现有条目里找：精确匹配优先，其次唯一的包含匹配；找不到才按"无链接条目"处理。"""
    if url:
        return key_of({"url": url, "title": title})
    from build_inbox import load_extra, load_index, load_pending, dedupe
    rows = dedupe(load_extra() + load_index() + load_pending())
    exact = [r for r in rows if (r.get("title") or "").strip() == title.strip()]
    hits = exact or [r for r in rows if title.strip() and title.strip() in (r.get("title") or "")]
    if len(hits) > 1:
        sys.exit("标题 %r 匹配到 %d 条，请改用 --url 指明是哪一条:\n%s" % (
            title, len(hits), "\n".join("  %s %s" % (r.get("date"), (r.get("url") or r.get("title"))[:80]) for r in hits[:5])))
    return key_of(hits[0]) if hits else key_of({"url": "", "title": title})


def cmd_set(a):
    if not (a.url or a.title):
        sys.exit("需要 --url 或 --title 指明是哪一条")
    if a.url and not a.url.startswith(("http://", "https://", "file:///")):
        sys.exit("url 必须以 http(s):// 开头，本地文档可用绝对 file:/// URI")
    if a.state and a.state not in STATES:
        sys.exit("状态 %r 不合法，可选: %s" % (a.state, "/".join(STATES)))
    if a.state == "dropped" and not a.reason:
        sys.exit("放弃一条必须写 --reason")
    if a.due and a.due != "none" and not DATE_RE.match(a.due):
        sys.exit("--due 必须是 YYYY-MM-DD，或写 none 清除")
    if not any([a.state, a.due, a.owner, a.note]):
        sys.exit("至少要改一项：--state/--due/--owner/--note")
    agent = resolve_agent(a.agent)
    owner = ""
    if a.owner:
        owner = AGENT_ALIASES.get(a.owner.strip().lower(), a.owner.strip().lower())
        if owner not in AGENTS:
            sys.exit("--owner 不认识: %r，可选: %s" % (a.owner, "/".join(AGENTS)))
    key = resolve_key(a.url, a.title)
    event = {"ts": now_iso(), "key": key, "agent": agent, "url": a.url.strip(), "title": clean(a.title, 120)}
    if a.state:
        event["state"] = a.state
    if a.due:
        event["due"] = "" if a.due == "none" else a.due
    if owner:
        event["owner"] = owner
    if a.note:
        event["note"] = clean(a.note, 500)
    if a.reason:
        event["reason"] = clean(a.reason, 200)
    if a.entry:
        event["entry"] = clean(a.entry, 30)
    append_event(event)
    cur = fold(read_events())[key]
    print("已记录: %s → %s%s%s" % (key[:70], STATE_CN.get(cur["state"], cur["state"]),
                               ("，到期 " + cur["due"]) if cur["due"] else "",
                               ("，负责 " + cur["owner"]) if cur["owner"] else ""))
    if not a.no_build:
        import subprocess
        subprocess.run([sys.executable, os.path.join(INBOX, "build_inbox.py")], check=True,
                       stdout=subprocess.DEVNULL)


def cmd_list(a):
    folded = fold(read_events())
    rows = []
    for key, rec in sorted(folded.items(), key=lambda kv: kv[1]["updated"], reverse=True):
        if a.state and rec["state"] != a.state:
            continue
        if a.overdue and not overdue(rec):
            continue
        rows.append(dict(rec, key=key))
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for r in rows:
        print("%-8s %-10s %-10s %-8s %s" % (STATE_CN.get(r["state"], r["state"]), r["due"] or "-",
                                            r["owner"] or "-", r["agent"] or "-", (r["title"] or r["key"])[:60]))
    print("共 %d 条有状态记录（未出现的条目默认为\"待分拣\"）" % len(rows))


def cmd_bulk(a):
    """批量把某日期之前、且尚无状态记录的条目标成同一状态。默认只预览。"""
    from build_inbox import load_extra, load_index, load_pending, dedupe
    rows = dedupe(load_extra() + load_index() + load_pending())
    folded = fold(read_events())
    todo = []
    for r in rows:
        key = key_of(r)
        if key in folded or not r.get("date") or r["date"] >= a.before:
            continue
        todo.append((key, r))
    print("符合条件（%s 之前、尚无状态记录）: %d 条" % (a.before, len(todo)))
    for _, r in todo[:5]:
        print("  ", r.get("date"), (r.get("title") or "")[:50])
    if not a.apply:
        print("这是预览；确认无误后加 --apply 才会写入")
        return
    if a.state not in STATES:
        sys.exit("状态不合法")
    agent = resolve_agent(a.agent)
    for key, r in todo:
        append_event({"ts": now_iso(), "key": key, "agent": agent, "url": r.get("url") or "",
                      "title": clean(r.get("title"), 120), "state": a.state,
                      "note": "批量标记(%s 之前)" % a.before})
    print("已写入 %d 条" % len(todo))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set", help="改某一条的状态/到期/负责人/备注")
    s.add_argument("--url", default="")
    s.add_argument("--title", default="", help="无链接条目用标题（取前 40 字做键，与 inbox_add 一致）")
    s.add_argument("--state", choices=STATES)
    s.add_argument("--due", default="", help="YYYY-MM-DD；写 none 清除")
    s.add_argument("--owner", default="", help="谁来跟进：" + "/".join(AGENTS))
    s.add_argument("--note", default="")
    s.add_argument("--reason", default="", help="放弃(dropped)时必填")
    s.add_argument("--entry", default="", help="从哪个入口说的，如 wechat/desktop/telegram")
    s.add_argument("--agent", default=os.environ.get("PUBLIC_LINK_AGENT", ""), help="【必填】你是谁")
    s.add_argument("--no-build", action="store_true", help="只写事件，不重建看板")
    l = sub.add_parser("list", help="列出有状态记录的条目")
    l.add_argument("--state", choices=STATES)
    l.add_argument("--overdue", action="store_true")
    l.add_argument("--json", action="store_true")
    b = sub.add_parser("bulk", help="批量处理历史条目（默认只预览）")
    b.add_argument("--before", required=True, help="YYYY-MM-DD，早于此日期的条目")
    b.add_argument("--state", choices=STATES, default="triaged")
    b.add_argument("--agent", default=os.environ.get("PUBLIC_LINK_AGENT", ""))
    b.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    {"set": cmd_set, "list": cmd_list, "bulk": cmd_bulk}[a.cmd](a)


if __name__ == "__main__":
    main()
