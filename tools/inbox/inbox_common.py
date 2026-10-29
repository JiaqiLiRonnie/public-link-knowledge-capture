# -*- coding: utf-8 -*-
"""收件箱各脚本共用的小工具：链接规范化、写入锁。"""
import contextlib
import fcntl
import os
from urllib.parse import parse_qsl, urlencode, urlsplit

INBOX = os.path.dirname(os.path.abspath(__file__))

# 这些参数只是追踪/来源标记，不决定"是哪一页"，规范化时丢掉
TRACKING = {"fbclid", "gclid", "spm", "scene", "chksm", "from", "share_token", "sessionid", "subscene",
            "clicktime", "enterid", "ascene", "devicetype", "version", "lang", "nettype", "abtest_cookie",
            "wx_header", "exportkey", "pass_ticket", "srcid", "share_from", "source", "ref", "xsec_token",
            "xsec_source", "app_platform", "app_version", "share_id", "timestamp", "si", "feature", "spm_id_from", "vd_source", "share_source", "share_medium",
            "share_plat", "share_session_id", "share_tag", "unique_k", "bbid", "buvid", "from_spmid"}
# 这些主机/路径下，只有列出的参数才决定"是哪一页"
IDENTITY_ONLY = {("mp.weixin.qq.com", "/s"): ("__biz", "mid", "idx", "sn"),
                 ("www.youtube.com", "/watch"): ("v",), ("youtube.com", "/watch"): ("v",),
                 ("news.ycombinator.com", "/item"): ("id",),
                 ("www.douyin.com", "/jingxuan"): ("modal_id",)}
# 这些主机的"是哪一页"完全由路径决定，参数一律丢掉（与旧行为一致）
STRIP_ALL_QUERY = {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com",
                   "github.com", "www.github.com", "www.reddit.com", "reddit.com", "old.reddit.com",
                   "www.xiaohongshu.com", "xhslink.com", "v.douyin.com", "www.iesdouyin.com", "b23.tv"}


def norm_url(u):
    """规范化链接用作去重键。

    旧做法是把 ? 之后全部丢掉，会让 mp.weixin.qq.com/s?__biz=..&mid=.. 的不同文章、
    wfdata.com/skill-detail?id=.. 的不同页面全部撞成同一个键。现在只丢追踪参数，保留其余参数（排序）。
    """
    raw = (u or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        return raw.rstrip("/").split("?")[0]
    host = parts.netloc.lower()
    path = parts.path.rstrip("/")
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    only = IDENTITY_ONLY.get((host, path))
    if host in STRIP_ALL_QUERY and only is None and not path.startswith("/search"):
        pairs = []  # 搜索页的 ?q= 决定内容，不能丢（下面走"只丢追踪参数"分支）
    elif only is not None:
        kept = [(k, v) for k, v in pairs if k in only]
        # 微信临时链接（如 /s?src=11&signature=..）没有 __biz 等身份参数：宁可不合并，也不能把不同文章并成一条
        pairs = kept if kept else [(k, v) for k, v in pairs if k.lower() not in TRACKING]
    else:
        pairs = [(k, v) for k, v in pairs if k.lower() not in TRACKING and not k.lower().startswith("utm_")]
    query = urlencode(sorted(pairs))
    return "%s://%s%s%s" % (parts.scheme.lower(), host, path, ("?" + query) if query else "")


@contextlib.contextmanager
def write_lock(name=".inbox.lock"):
    """跨进程互斥：多个 agent 同时 读-改-写 inbox_extra.jsonl 时，后写的不会吃掉先写的。"""
    fd = os.open(os.path.join(INBOX, name), os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)
